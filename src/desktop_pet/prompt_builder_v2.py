import re

from .state_snapshot import get_pet_state

QQ_RE = re.compile(r"(?<!\d)([1-9]\d{4,11})(?!\d)")


def extract_user_id(message: str, default_user_id: str) -> str:
    match = QQ_RE.search(message or "")
    return match.group(1) if match else default_user_id


def build_user_state_for_prompt(db, user_id: str, group_id: str | None = None) -> str:
    state = get_pet_state(db, user_id, group_id)
    if not state.exists:
        return f"QQ: {user_id}\n状态: 暂无记录"

    inventory = "、".join(
        f"{item['name']} x{item['quantity']}" for item in state.inventory
    ) or "暂无记录"
    last_feed = str(state.last_feed_time) if state.last_feed_time else "暂无记录"
    return "\n".join(
        [
            f"QQ: {state.user_id}",
            f"好感度: {state.favorability}",
            f"拉黑状态: {'是' if state.is_blocked else '否'}",
            f"体力: {state.stamina}",
            f"螃蟹币: {state.crab_coin}",
            f"最近投喂时间戳: {last_feed}",
            f"心情: {state.mood}",
            f"背包: {inventory}",
        ]
    )
