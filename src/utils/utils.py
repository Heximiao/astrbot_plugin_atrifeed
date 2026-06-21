# src/utils.py
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger
from astrbot.api.message_components import Node, Plain

UNBLOCK_PERMISSION_BOT_ADMIN = "仅bot管理员"
UNBLOCK_PERMISSION_GROUP_OWNER = "群主和bot管理员"
UNBLOCK_PERMISSION_GROUP_ADMIN = "群主和群管理员和bot管理员"

def is_group_allowed(event: AstrMessageEvent, config: dict) -> bool:
    """
    检查当前群组是否在黑白名单允许范围内
    """
    group_id = event.get_group_id()
    
    # 如果是私聊，默认允许
    if not group_id: 
        return True 

    whitelist_str = config.get("whitelist_groups", "").replace("，", ",")
    blacklist_str = config.get("blacklist_groups", "").replace("，", ",")
    
    # 转换为列表并去除空格
    whitelist = [g.strip() for g in whitelist_str.split(",") if g.strip()]
    blacklist = [g.strip() for g in blacklist_str.split(",") if g.strip()]

    # 1. 白名单逻辑
    if whitelist:
        return str(group_id) in whitelist or group_id in whitelist
    
    # 2. 黑名单逻辑
    if str(group_id) in blacklist or group_id in blacklist:
        return False
        
    return True


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def forward_text_result(event: AstrMessageEvent, text: str, name: str = "亚托莉"):
    """Return a OneBot-style merged-forward text result."""
    self_id = None
    get_self_id = getattr(event, "get_self_id", None)
    if callable(get_self_id):
        self_id = get_self_id()
    if self_id is None:
        self_id = getattr(getattr(event, "message_obj", None), "self_id", None)
    if self_id is None:
        self_id = event.get_sender_id()

    node = Node(
        uin=_safe_int(self_id),
        name=name,
        content=[Plain(text)],
    )
    return event.chain_result([node])


async def get_group_member_role(event: AstrMessageEvent, group_id: str, user_id: str) -> str:
    """
    获取群成员身份。aiocqhttp/NapCat 优先走协议端 API，失败时回退到事件原始数据。
    """
    if not group_id or not user_id:
        return "member"

    try:
        if event.get_platform_name() == "aiocqhttp" and hasattr(event, "bot"):
            ret = await event.bot.api.call_action(
                "get_group_member_info",
                group_id=group_id,
                user_id=user_id,
            )
            data = ret.get("data", {}) if isinstance(ret, dict) else getattr(ret, "data", {})
            role = data.get("role")
            if role:
                return str(role)
    except Exception as e:
        logger.warning(f"[Atri] 获取群成员身份失败，尝试使用事件原始数据: {e}")

    try:
        raw_message = getattr(event.message_obj, "raw_message", None)
        if isinstance(raw_message, dict):
            sender = raw_message.get("sender", {})
            if str(raw_message.get("user_id", "")) == str(user_id):
                return str(sender.get("role", "member"))
    except Exception:
        pass

    return "member"


async def can_use_unblock_command(event: AstrMessageEvent, config: dict) -> bool:
    """
    根据配置判断当前用户是否有权限使用解除拉黑指令。
    """
    if event.is_admin():
        return True

    mode = config.get("unblock_permission", UNBLOCK_PERMISSION_BOT_ADMIN)
    if mode in {UNBLOCK_PERMISSION_BOT_ADMIN, "bot_admin"}:
        return False

    group_id = event.get_group_id()
    if not group_id:
        return False

    role = await get_group_member_role(event, group_id, event.get_sender_id())
    if mode in {UNBLOCK_PERMISSION_GROUP_OWNER, "group_owner_and_bot_admin"}:
        return role == "owner"

    if mode in {UNBLOCK_PERMISSION_GROUP_ADMIN, "group_admin_owner_and_bot_admin"}:
        return role in {"owner", "admin"}

    return False
