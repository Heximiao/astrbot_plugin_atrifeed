import os
import random
from pathlib import Path 
from datetime import datetime, timedelta
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .keyword_trigger import KeywordRouter, MatchMode
from .src.constants import _DEFAULT_KEYWORD_ROUTES
from .src.db.database import AtriDB
from .src.db.database_shop import AtriShopDB
from .src.db.database_story import AtriStoryDB
from .src.command.feeding import *
from .src.command.pet import *
from .src.command.welcome import *
from .src.utils.utils import is_group_allowed, can_use_diary_command
from .src.command.help import run_atri_help_logic
from .src.command.abuse import run_abuse_logic
from .src.command.my_atri import run_my_atri_logic
from .src.command.radish import run_radish_logic
from .src.command.other_emoji import run_injection_logic, run_sleep_logic
from .src.command.sign_in import run_sign_in_logic
from .src.ban import run_apology_logic
from .src.command.gig import run_gig_logic
from .src.command.dice import run_dice_logic
from .src.command.shopping import run_shop_logic
from .src.command.backpack import run_backpack_logic
from .src.command.use_item import run_use_item_logic
from .src.command.unblock import run_unblock_logic
from .src.desktop_pet import DesktopPetService
from .src.diary import DiaryService

from .src.story.story import StoryManager

class AtriPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
            super().__init__(context)
            self.config = config or {}
            self.name = "astrbot_plugin_atrifeed" 
            self.curr_dir = os.path.dirname(__file__)
            
            try:
                from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
                base_dir = get_astrbot_plugin_data_path()
            except ImportError:
                from astrbot.core.utils.astrbot_path import get_astrbot_data_path
                # 兼容处理
                base_dir = os.path.join(get_astrbot_data_path(), "plugin_data")
            self.data_dir = os.path.join(base_dir, self.name)
            
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir, exist_ok=True)
            db_file = os.path.join(self.data_dir, "atri_feed.db")
            
            # 传入数据库
            #self.db = AtriDB(db_file)
            #self.db = AtriShopDB(db_file)
            self.db = AtriStoryDB(db_file)

            self.apology_count = {}
            self._keyword_router = KeywordRouter(routes=_DEFAULT_KEYWORD_ROUTES)
            self.story_mgr = StoryManager(self.curr_dir)
            
            self._keyword_handlers = {
                "feed_crab": self.feed_crab,
                "feed_fruit": self.feed_fruit,
                "star_effect": self.star_effect,
                "no_smoke": self.no_smoke,
                "poop_effect": self.poop_effect,
                "show_help": self.atri_help,
                "my_atri_card": self.my_atri_card,
                "radish_cmd": self.radish_cmd,
                "injection_effect": self.injection_cmd,
                "atri_signin": self.atri_signin,
                "atri_work": self.atri_work,
                "atri_dice": self.atri_dice,
                "sleep_effect": self.sleep_cmd,
                "atri_shop": self.atri_shop,
                "atri_backpack": self.atri_backpack,
                "atri_use": self.atri_use,
                "story_next": self.story_next,
                "story_start": self.story_start,
                "pet_animal": self.pet_animal,
            }
            self._keyword_trigger_block_prefixes = ("/", "!", "！")
            self.desktop_pet_service = DesktopPetService(self)
            self.desktop_pet_service.start_if_enabled()
            self.diary_service = DiaryService(self)
            self.diary_service.start_if_enabled()

    def is_blocked(self, event: AstrMessageEvent) -> bool:
        """检查用户是否被全局拉黑"""
        uid = event.get_sender_id()
        return self.db.check_user_global_block(uid)

    def _get_keyword_trigger_mode(self) -> MatchMode:
        conf = self.config if self.config else (self.context.get_config() or {})
        raw = conf.get("keyword_trigger_mode", "exact")
        try:
            return MatchMode(str(raw))
        except ValueError:
            return MatchMode.EXACT

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_keyword_msg(self, event: AstrMessageEvent):
        """处理关键词触发的消息"""
        conf = self.config if self.config else (self.context.get_config() or {})
        # 1. 基础过滤
        if not is_group_allowed(event, conf): return
        message_str = event.message_str
        if not message_str or event.is_at_or_wake_command: return 

        # 2. 核心开关检查：如果关键词触发关闭，且不是指令前缀，直接返回
        keyword_enabled = conf.get("keyword_trigger_enabled", True)
        is_potential_cmd = message_str.startswith(self._keyword_trigger_block_prefixes)
        
        if not keyword_enabled and not is_potential_cmd:
            return
        # 3. 匹配路由
        mode = self._get_keyword_trigger_mode()
        route = self._keyword_router.match_route(message_str, mode=mode)
        
        # 如果是指令前缀开头的，直接由框架自带的 @filter.command 处理，这里跳过
        if is_potential_cmd:
            return
        if route is None:
            route = self._keyword_router.match_command_route(message_str)
            
        # 4. 执行匹配到的 handler
        if route:
            handler = self._keyword_handlers.get(route.action)
            if handler:
                logger.info(f"[Atri] 关键词匹配成功: {route.keyword} -> {route.action}")
                try:
                    async for result in handler(event):
                        yield result
                except TypeError: 
                    result = await handler(event)
                    if result: yield result
                
                event.stop_event()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1)
    # 监听入群和退群消息
    async def on_group_member_change(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not conf.get("welcome_enabled", False):
            return
        await welcome_new_user(self,event)

    # --- 指令转发区域 ---

    @filter.command("🦀")
    async def feed_crab(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_feed_crab_logic(event, self.db, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("🍧", alias={"🍜","🍎", "🍉", "🍓", "🍔", "🍕", "🍱", "🍄", "🍭", "🍙"})
    async def feed_fruit(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_feed_fruit_logic(event, self.db,self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("🐱", alias={"🐶","🐰", "🦊", "🐼", "🐹", "🐥", "🐦", "🐧", "🐑", "🐴","🐷","🐘","🐨","🦙","🦉","🦦","🦆","🐯"})
    async def pet_animal(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_pet_animal_logic(event,self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("✨")
    async def star_effect(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_star_effect_logic(event):
            yield result
        event.stop_event()

    @filter.command("🚬")
    async def no_smoke(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_no_smoke_logic(event, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("💩")
    async def poop_effect(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_poop_effect_logic(event, self.db, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("亚托莉帮助")
    async def atri_help(self, event: AstrMessageEvent):
        """由于很多helps插件无法显示emoji，所以使用该插件前请务必先阅读亚托莉帮助"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): 
            return
        if self.is_blocked(event): return   
        async for result in run_atri_help_logic(self, event, conf):
            yield result
        event.stop_event()

    @filter.command("我的亚托莉")
    async def my_atri_card(self, event: AstrMessageEvent):
        """查看羁绊值"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render 作为渲染函数
        async for result in run_my_atri_logic(event, self.db, self.curr_dir, self.html_render):
            yield result
        event.stop_event()

    @filter.command("萝卜子", alias={"🥕","飞舞萝卜子"})
    async def radish_cmd(self, event: AstrMessageEvent):
        """违反机器人保护法！"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 调用 radish.py 里的逻辑
        async for result in run_radish_logic(event, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("💉")
    async def injection_cmd(self, event: AstrMessageEvent):
        """不想打针！"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_injection_logic(event, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("亚托莉签到")
    async def atri_signin(self, event: AstrMessageEvent):
        """每日签到，获取螃蟹币和体力"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render 和 self.curr_dir
        async for result in run_sign_in_logic(event, self.db, self.curr_dir, self.html_render):
            yield result
        event.stop_event()

    @filter.command("亚托莉打工")
    async def atri_work(self, event: AstrMessageEvent):
        """努力打工赚取螃蟹币"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render
        async for result in run_gig_logic(event, self.db, self.curr_dir, self.html_render):
            yield result
        event.stop_event()

    @filter.command("亚托莉骰子", alias={"🎲", "dice"})
    async def atri_dice(self, event: AstrMessageEvent):
        """随机获取螃蟹币和体力，每天一次"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_dice_logic(event, self.db, self.curr_dir):
            yield result
        event.stop_event()
    
    @filter.command("💤")
    async def sleep_cmd(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_sleep_logic(event, self.curr_dir):
            yield result
        event.stop_event()

    @filter.command("商店", alias={"购买"})
    async def atri_shop(self, event: AstrMessageEvent):
        """亚托莉小卖部：查看或购买物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 核心修改：增加 self.curr_dir 和 self.html_render 两个参数
        async for result in run_shop_logic(event, self.db, self.curr_dir, self.html_render):
            yield result
        event.stop_event()

    @filter.command("我的背包")
    async def atri_backpack(self, event: AstrMessageEvent):
        """查看你拥有的所有物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_backpack_logic(event, self.db):
            yield result
        event.stop_event()
    
    @filter.command("使用")
    async def atri_use(self, event: AstrMessageEvent):
        """使用背包里的物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_use_item_logic(event, self.db):
            yield result
        event.stop_event()

    # 剧情相关指令
    @filter.command("开始巡礼")
    async def story_start(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return

        result = await self.story_mgr.start_story(event, self.db)
        if result:
            yield result
        event.stop_event()
    
    @filter.command("继续前进")
    async def story_next(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 使用 yield 发送管理器返回的 MessageChain
        async for result in self._call_story_logic(event, action="next"):
            yield result
        event.stop_event()

    @filter.command("选择")
    async def story_select(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return

        import re
        match = re.search(r'\d+', event.message_str)
        selection = match.group() if match else None
        
        logger.info(f"【Debug】提取到的纯数字选项: '{selection}'")
        
        async for result in self._call_story_logic(event, action="select", selection=selection):
            yield result
        event.stop_event()

    async def _call_story_logic(self, event, action, selection=None):
        """统一封装逻辑调用层"""
        result = await self.story_mgr.run_logic(event, self.db, action, selection)
        if isinstance(result, str):
            yield event.plain_result(result)
        else:
            yield result
        event.stop_event()

    # --- 特殊逻辑 ---
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_at_abuse_monitor(self, event: AstrMessageEvent):
        """专门处理 @机器人 时的辱骂检测"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 1. 使用 is_at_me 属性判断是否被 @
        # 也可以结合 message_obj 检查是否有 At 组件
        is_at_me = getattr(event, 'is_at_me', False) 
        
        # 如果 is_at_me 为空，尝试通过 message_str 或框架提供的唤醒判定
        if is_at_me or event.is_at_or_wake_command:
            # 2. 检查黑名单
            if self.is_blocked(event): return
            
            # 3. 调用逻辑层
            async for result in run_abuse_logic(event, self.db, self.curr_dir, self.config):
                yield result

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1)
    async def on_apology(self, event: AstrMessageEvent):
        """处理道歉加封禁逻辑"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): 
            return
        # 2. 直接调用逻辑层
        # 注意：这里传递了 self.apology_count 引用，以便在 ban.py 中修改它
        async for result in run_apology_logic(
            event, 
            self.db, 
            conf, 
            self.curr_dir, 
            self.apology_count
        ):
            yield result

    @filter.command("解除拉黑")
    async def unblock_user(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf):
            return

        async for result in run_unblock_logic(event, self.db, conf):
            yield result
        event.stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("clear_feed_log")
    async def admin_clear(self, event: AstrMessageEvent):
        self.db.clear_daily_log()
        yield event.plain_result("已清理今日投喂记录。")

    async def _check_diary_permission(self, event: AstrMessageEvent) -> bool:
        conf = self.config if self.config else (self.context.get_config() or {})
        return await can_use_diary_command(event, conf)

    @staticmethod
    def _normalize_diary_date(value: str = "") -> str:
        if not value:
            return datetime.now().strftime("%Y-%m-%d")
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError("日期格式错误")

    @filter.command("日记生成", alias={"生成日记"})
    async def diary_generate(self, event: AstrMessageEvent, date: str = ""):
        """手动生成一篇全局日记。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        try:
            target_date = self._normalize_diary_date(date)
        except ValueError:
            yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
            return
        logger.info(
            "[日记] 收到手动生成指令: date=%s, sender=%s, group=%s",
            target_date,
            event.get_sender_id(),
            event.get_group_id() or "private",
        )
        # 进度消息必须直接发送，不能先 yield。某些结果装饰插件会在处理
        # 第一条 yield 结果后停止事件传播，导致后面的日记生成逻辑不再执行。
        await event.send(event.plain_result(f"🔄 正在生成 {target_date} 的日记，请稍候……"))
        logger.info("[日记] 手动生成进度消息已发送，开始执行核心生成流程")
        success, message = await self.diary_service.generate_daily_diary(target_date, force=True)
        prefix = "✅" if success else "❌"
        yield event.plain_result(f"{prefix} {message}")

    @filter.command("日记列表", alias={"日记记录"})
    async def diary_list(self, event: AstrMessageEvent, param: str = ""):
        """显示基础概览、指定日期概况或全部详细统计。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        all_records = self.diary_service.storage.list_all()
        if not all_records:
            yield event.plain_result("📭 还没有任何日记记录。")
            return

        if param.strip().lower() == "all":
            diaries = [record for _, record in all_records]
            total_words = sum(int(item.get("word_count", 0) or 0) for item in diaries)
            published = sum(bool(item.get("is_published_qzone", False)) for item in diaries)
            dates = sorted(str(item.get("date", "")) for item in diaries if item.get("date"))
            longest = max(diaries, key=lambda item: int(item.get("word_count", 0) or 0))
            shortest = min(diaries, key=lambda item: int(item.get("word_count", 0) or 0))
            latest = datetime.fromtimestamp(float(diaries[0].get("generation_time", 0)))
            week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
            weekly = [
                item for item in diaries
                if datetime.fromtimestamp(float(item.get("generation_time", 0))).date() >= week_start
            ]
            weekly_words = sum(int(item.get("word_count", 0) or 0) for item in weekly)
            weekly_published = sum(bool(item.get("is_published_qzone", False)) for item in weekly)
            text = (
                "📚 日记概览\n\n📊 详细统计：\n"
                f"📖 总日记数: {len(diaries)}篇\n"
                f"📝 总字数: {total_words}字 (平均: {total_words // len(diaries)}字/篇)\n"
                f"📅 日期范围: {dates[0]} ~ {dates[-1]} ({len(set(dates))}天)\n"
                f"📱 发布统计: {published}篇成功, {len(diaries)-published}篇未发布/失败 "
                f"(成功率: {published / len(diaries) * 100:.1f}%)\n"
                f"🕐 最近生成: {latest:%Y-%m-%d %H:%M}\n"
                f"⏰ 下次定时: {self.diary_service.status_text().split('下次执行：')[-1]}\n\n"
                "📈 本周统计：\n"
                f"📝 本周平均: {weekly_words // len(weekly) if weekly else 0}字/篇\n"
                f"📱 本周发布: {weekly_published}/{len(weekly)}篇成功\n"
                f"🔥 最长日记: {longest.get('date', '无')} ({longest.get('word_count', 0)}字)\n"
                f"📏 最短日记: {shortest.get('date', '无')} ({shortest.get('word_count', 0)}字)"
            )
            yield event.plain_result(text)
            return

        if param.strip():
            try:
                target_date = self._normalize_diary_date(param)
            except ValueError:
                yield event.plain_result("❌ 参数应为 all 或 YYYY-MM-DD 日期。")
                return
            records = self.diary_service.storage.list_by_date(target_date)
            if not records:
                yield event.plain_result(f"📭 没有找到 {target_date} 的日记。")
                return
            total_words = sum(int(item.get("word_count", 0) or 0) for _, item in records)
            published = sum(bool(item.get("is_published_qzone", False)) for _, item in records)
            lines = [f"📅 {target_date} 日记概况：", ""]
            for index, (_, record) in enumerate(records, 1):
                generated = datetime.fromtimestamp(float(record.get("generation_time", 0)))
                state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
                lines.append(f"{index}. {generated:%H:%M} ({record.get('word_count', 0)}字) {state}")
            first_time = datetime.fromtimestamp(float(records[0][1].get("generation_time", 0)))
            last_time = datetime.fromtimestamp(float(records[-1][1].get("generation_time", 0)))
            lines.extend([
                "", "📊 当天统计：",
                f"📝 总字数: {total_words}字 (平均: {total_words // len(records)}字/篇)",
                f"📱 发布状态: {published}篇成功, {len(records)-published}篇未发布/失败",
                f"🕐 最早生成: {first_time:%H:%M}", f"🕐 最新生成: {last_time:%H:%M}",
                "", f"使用 /日记查看 {target_date} 编号 查看正文。",
            ])
            yield event.plain_result("\n".join(lines))
            return

        total_words = sum(int(item.get("word_count", 0) or 0) for _, item in all_records)
        recent_lines = []
        for _, record in all_records[:10]:
            state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
            recent_lines.append(f"📅 {record.get('date', '无')} ({record.get('word_count', 0)}字) {state}")
        yield event.plain_result(
            "📚 日记概览：\n\n📊 统计信息：\n"
            f"📖 总日记数: {len(all_records)}篇\n📝 总字数: {total_words}字\n"
            f"📏 平均字数: {total_words // len(all_records)}字/篇\n"
            f"📅 最新日记: {all_records[0][1].get('date', '无')}\n\n"
            "📋 最近日记 (10篇)：\n" + "\n".join(recent_lines) +
            "\n\n💡 使用 /日记列表 日期 查看当天概况，或 /日记列表 all 查看详细统计。"
        )

    @filter.command("日记查看", alias={"查看日记"})
    async def diary_view(self, event: AstrMessageEvent, date: str = "", index: int = 0):
        """查看指定日期的一篇日记；不写编号时查看最新一篇。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        try:
            target_date = self._normalize_diary_date(date)
        except ValueError:
            yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
            return
        records = self.diary_service.storage.list_by_date(target_date)
        if not records:
            yield event.plain_result(f"📭 没有找到 {target_date} 的日记。")
            return
        if index <= 0:
            lines = [f"📅 {target_date} 的日记列表："]
            for number, (_, record) in enumerate(records, 1):
                generated = datetime.fromtimestamp(float(record.get("generation_time", 0)))
                state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
                lines.append(f"{number}. {generated:%H:%M}｜{record.get('word_count', 0)}字｜{state}")
            lines.append(f"\n输入 /日记查看 {target_date} 编号 查看具体内容。")
            yield event.plain_result("\n".join(lines))
            return
        item = self.diary_service.storage.get_record(target_date, index)
        if not item:
            yield event.plain_result("❌ 编号无效，请输入正确编号。")
            return
        _, record = item
        published = "已发布QQ空间" if record.get("is_published_qzone", False) else "未发布QQ空间"
        yield event.plain_result(
            f"📖 {target_date}｜{record.get('word_count', 0)}字｜{published}\n\n"
            f"{record.get('diary_content', '')}"
        )

    @filter.command("日记发布", alias={"发布日记"})
    async def diary_publish(self, event: AstrMessageEvent, date: str = "", index: int = 0):
        """将一篇已保存日记发布到QQ空间。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        try:
            target_date = self._normalize_diary_date(date)
        except ValueError:
            yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
            return
        success, message = await self.diary_service.publish_saved_diary(target_date, index)
        yield event.plain_result(f"{'✅' if success else '❌'} {message}")

    @filter.command("日记状态")
    async def diary_status(self, event: AstrMessageEvent):
        """查看日记配置与下次执行时间。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        yield event.plain_result(self.diary_service.status_text())

    @filter.command("日记调试")
    async def diary_debug(self, event: AstrMessageEvent, date: str = ""):
        """实际拉取指定日期群历史并显示消息统计，不调用大模型。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        try:
            target_date = self._normalize_diary_date(date)
        except ValueError:
            yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
            return
        await event.send(event.plain_result(f"🔍 正在检查 {target_date} 的群历史读取情况……"))
        success, message = await self.diary_service.debug_history(target_date)
        yield event.plain_result(f"{'✅' if success else '❌'} {message}")

    @filter.command("日记帮助")
    async def diary_help(self, event: AstrMessageEvent):
        """显示日记管理指令帮助。"""
        event.stop_event()
        if not await self._check_diary_permission(event):
            yield event.plain_result("❌ 您没有权限使用日记管理指令。")
            return
        yield event.plain_result(
            "📖 日记功能帮助\n\n"
            "/日记生成 [日期] - 生成指定日期日记，默认今天\n"
            "/日记列表 - 基础概览和最近10篇\n"
            "/日记列表 [日期] - 指定日期概况\n"
            "/日记列表 all - 全部详细统计\n"
            "/日记查看 [日期] - 显示当天日记列表\n"
            "/日记查看 [日期] [编号] - 查看具体正文\n"
            "/日记发布 [日期] [编号] - 发布或补发QQ空间\n"
            "/日记状态 - 查看配置和下次执行时间\n"
            "/日记调试 [日期] - 检查群历史读取统计\n"
            "/日记帮助 - 显示本帮助\n\n"
            "日期支持 YYYY-MM-DD、YYYY/M/D 或 YYYY.M.D；未填日期时默认今天。"
        )

    async def terminate(self):
        if hasattr(self, "diary_service"):
            await self.diary_service.stop()
        if hasattr(self, "desktop_pet_service"):
            self.desktop_pet_service.stop()
