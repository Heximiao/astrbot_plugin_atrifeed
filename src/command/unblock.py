import re

from astrbot.api.event import AstrMessageEvent

from ..utils.utils import can_use_unblock_command


def _extract_target_user_id(event: AstrMessageEvent) -> str:
    """从 @ 或指令参数中提取目标 QQ。"""
    message_obj = getattr(event, "message_obj", None)
    message_chain = getattr(message_obj, "message", []) if message_obj else []
    for seg in message_chain:
        qq = getattr(seg, "qq", None)
        if qq:
            return str(qq)

    match = re.search(r"\d{5,}", event.message_str or "")
    return match.group(0) if match else ""


async def run_unblock_logic(event: AstrMessageEvent, db, config: dict):
    if not await can_use_unblock_command(event, config):
        yield event.plain_result("权限不足，无法使用解除拉黑指令。")
        return

    target_user_id = _extract_target_user_id(event)
    if not target_user_id:
        yield event.plain_result("请指定要解除拉黑的 QQ，例如：解除拉黑 123456789，或直接 @ 对方。")
        return

    if not db.check_user_global_block(target_user_id):
        yield event.plain_result(f"{target_user_id} 目前没有被拉黑呢。")
        return

    db.unblock_user(target_user_id, event.get_group_id())
    yield event.plain_result(f"已解除 {target_user_id} 的拉黑状态，好感度已恢复为默认值 10。")
