import os
import random
from pathlib import Path 
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .keyword_trigger import KeywordRouter, MatchMode
from .src.constants import _DEFAULT_KEYWORD_ROUTES
from .src.db.database import AtriDB
from .src.db.database_shop import AtriShopDB
from .src.command.feeding import *
from .src.utils.utils import is_group_allowed
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
            self.db = AtriShopDB(db_file)

            self.apology_count = {}
            self._keyword_router = KeywordRouter(routes=_DEFAULT_KEYWORD_ROUTES)
            
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
            }
            self._keyword_trigger_block_prefixes = ("/", "!", "！")

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

    # --- 指令转发区域 ---

    @filter.command("🦀")
    async def feed_crab(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_feed_crab_logic(event, self.db, self.curr_dir):
            yield result

    @filter.command("🍧", alias={"🍜","🍎", "🍉", "🍓", "🍔", "🍕", "🍱", "🍄", "🍭", "🍙"})
    async def feed_fruit(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_feed_fruit_logic(event, self.db,self.curr_dir):
            yield result

    @filter.command("✨")
    async def star_effect(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_star_effect_logic(event):
            yield result

    @filter.command("🚬")
    async def no_smoke(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_no_smoke_logic(event, self.curr_dir):
            yield result

    @filter.command("💩")
    async def poop_effect(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        async for result in run_poop_effect_logic(event, self.db, self.curr_dir):
            yield result

    @filter.command("亚托莉帮助")
    async def atri_help(self, event: AstrMessageEvent):
        """由于很多helps插件无法显示emoji，所以使用该插件前请务必先阅读亚托莉帮助"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): 
            return
        if self.is_blocked(event): return   
        async for result in run_atri_help_logic(self, event, conf):
            yield result

    @filter.command("我的亚托莉")
    async def my_atri_card(self, event: AstrMessageEvent):
        """查看羁绊值"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render 作为渲染函数
        async for result in run_my_atri_logic(event, self.db, self.curr_dir, self.html_render):
            yield result

    @filter.command("萝卜子", alias={"🥕","飞舞萝卜子"})
    async def radish_cmd(self, event: AstrMessageEvent):
        """违反机器人保护法！"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 调用 radish.py 里的逻辑
        async for result in run_radish_logic(event, self.curr_dir):
            yield result

    @filter.command("💉")
    async def injection_cmd(self, event: AstrMessageEvent):
        """不想打针！"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_injection_logic(event, self.curr_dir):
            yield result

    @filter.command("亚托莉签到")
    async def atri_signin(self, event: AstrMessageEvent):
        """每日签到，获取螃蟹币和体力"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render 和 self.curr_dir
        async for result in run_sign_in_logic(event, self.db, self.curr_dir, self.html_render):
            yield result

    @filter.command("亚托莉打工")
    async def atri_work(self, event: AstrMessageEvent):
        """努力打工赚取螃蟹币"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 传入 self.html_render
        async for result in run_gig_logic(event, self.db, self.curr_dir, self.html_render):
            yield result

    @filter.command("亚托莉骰子", alias={"🎲", "dice"})
    async def atri_dice(self, event: AstrMessageEvent):
        """随机获取螃蟹币和体力，每天一次"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_dice_logic(event, self.db, self.curr_dir):
            yield result
    
    @filter.command("💤")
    async def sleep_cmd(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_sleep_logic(event, self.curr_dir):
            yield result

    @filter.command("商店")
    async def atri_shop(self, event: AstrMessageEvent):
        """亚托莉小卖部：查看或购买物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        # 核心修改：增加 self.curr_dir 和 self.html_render 两个参数
        async for result in run_shop_logic(event, self.db, self.curr_dir, self.html_render):
            yield result

    @filter.command("我的背包")
    async def atri_backpack(self, event: AstrMessageEvent):
        """查看你拥有的所有物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_backpack_logic(event, self.db):
            yield result
    
    @filter.command("使用")
    async def atri_use(self, event: AstrMessageEvent):
        """使用背包里的物品"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        if self.is_blocked(event): return
        
        async for result in run_use_item_logic(event, self.db):
            yield result

    # --- 特殊逻辑 ---

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_at_abuse_monitor(self, event: AstrMessageEvent):
        """专门处理 @机器人 时的辱骂检测"""
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        
        # 1. 使用 is_at_me 属性判断是否被 @
        # 也可以结合 message_obj 检查是否有 At 组件
        is_at_me = getattr(event, 'is_at_me', False) 
        
        # 如果 is_at_me 为空，尝试通过 message_str 或框架提供的唤醒判定
        if is_at_me or event.is_at_or_wake_command:
            # 2. 检查黑名单
            if self.is_blocked(event): return
            
            # 3. 调用逻辑层
            async for result in run_abuse_logic(event, self.db, self.curr_dir):
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

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("clear_feed_log")
    async def admin_clear(self, event: AstrMessageEvent):
        self.db.clear_daily_log()
        yield event.plain_result("已清理今日投喂记录。")
