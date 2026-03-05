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
from .src.database import AtriDB
from .src.command.feeding import *
from .src.utils import is_group_allowed
from .src.command.help import run_atri_help_logic
from .src.command.abuse import run_abuse_logic
from .src.command.my_atri import run_my_atri_logic
from .src.command.radish import run_radish_logic
from .src.command.other_emoji import run_injection_logic
from .src.command.sign_in import run_sign_in_logic

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
            self.db = AtriDB(db_file)

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
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf):
            return
        message_str = event.message_str
        if not message_str or event.is_at_or_wake_command: return 

        # 只有当消息包含关键词或者是指令前缀时，才继续往下走逻辑
        # 这样普通闲聊就不会触发后面的数据库查询 is_blocked
        is_potential_cmd = message_str.startswith(self._keyword_trigger_block_prefixes)
        route = self._keyword_router.match_route(message_str, mode=self._get_keyword_trigger_mode())
        
        if not is_potential_cmd and not route:
            return
        
        # 黑名单拦截 (除了道歉语句)
        if "亚托莉我错了对不起" not in event.message_str:
            if self.is_blocked(event):
                return
        
        conf = self.config if self.config else (self.context.get_config() or {})
        if not conf.get("keyword_trigger_enabled", True):
            return

        message_str = event.message_str
        if not message_str or event.is_at_or_wake_command: return 

        if message_str.startswith(self._keyword_trigger_block_prefixes):
            return

        mode = self._get_keyword_trigger_mode()
        route = self._keyword_router.match_route(message_str, mode=mode)
        
        if route is None:
            route = self._keyword_router.match_command_route(message_str)
            
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_apology(self, event: AstrMessageEvent):
        conf = self.config if self.config else (self.context.get_config() or {})
        if not is_group_allowed(event, conf): return
        
        if "亚托莉我错了对不起" in event.message_str:
            uid = event.get_sender_id()
            gid = event.get_group_id()
            fav, is_blocked = self.db.get_user_state(uid, gid)
            
            # 如果 is_blocked 为 0，没有被拉黑，直接 return
            if is_blocked == 0:
                yield event.plain_result("亚托莉...才..才没有生气呢！")
                async for res in yield_random_folder_pic(event, self.curr_dir, ["angry"]):
                    yield res
                return
            self.apology_count[uid] = self.apology_count.get(uid, 0) + 1
            
            if self.apology_count[uid] >= 3:
                # 注意这里：通过 self.db 调用
                total_forgiven = self.db.increase_forgiven_and_check_global(uid, gid)
                
                if total_forgiven >= 2:
                    #use_qq_ban = conf.get("global_ban_use_qq", False)
                    
                    # 插件级全局拉黑：锁死当前群的好感度，配合上面的全局检查
                    self.db.update_favorability(uid, gid, -999) 
                    use_qq_ban = conf.get("global_ban_use_qq", True)
                    if use_qq_ban:
                        # QQ级全局拉黑：AstrBot 框架层面直接拦截（目前没用）
                        self.context.block_user(uid) 
                        yield event.plain_result("...这是你最后一次机会，但你已经耗尽了亚托莉的仁慈。再见。")
                    else:
                        yield event.plain_result("亚托莉已经原谅你太多次了。你的名字已被永久记录，亚托莉再也不会理你了。")
                    return

                # 正常原谅逻辑
                self.db.unblock_user(uid, gid)
                self.db.reset_poop_count(uid, gid)
                self.apology_count[uid] = 0
                yield event.plain_result(f"既然你这么诚恳...亚托莉就原谅你这一次吧！(累计原谅次数：{total_forgiven})")
            else:
                yield event.plain_result(f"哼，亚托莉还在生气！（{self.apology_count[uid]}/3）")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("clear_feed_log")
    async def admin_clear(self, event: AstrMessageEvent):
        self.db.clear_daily_log()
        yield event.plain_result("已清理今日投喂记录。")
