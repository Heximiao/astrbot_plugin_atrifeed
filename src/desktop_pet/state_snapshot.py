import time
from dataclasses import dataclass


@dataclass
class PetState:
    user_id: str
    exists: bool
    favorability: int
    is_blocked: bool
    stamina: int
    crab_coin: int
    last_feed_time: int | None
    mood: str
    recommended_action: str
    inventory: list[dict]

    def as_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "exists": self.exists,
            "favorability": self.favorability,
            "is_blocked": self.is_blocked,
            "stamina": self.stamina,
            "crab_coin": self.crab_coin,
            "last_feed_time": self.last_feed_time,
            "mood": self.mood,
            "recommended_action": self.recommended_action,
            "inventory": self.inventory,
        }


def mood_from_state(favorability: int, stamina: int, last_feed_time: int | None) -> str:
    mood = "happy" if favorability >= 80 else "normal" if favorability >= 30 else "sad" if favorability >= 5 else "angry"
    if stamina < 20 and mood in {"happy", "normal"}:
        return "sad"
    if last_feed_time:
        days = (int(time.time()) - int(last_feed_time)) / 86400
        if days <= 3 and mood == "normal":
            return "happy"
        if days > 14 and mood != "angry":
            return "sad"
    return mood


def action_from_mood(mood: str, stamina: int) -> str:
    if stamina < 20:
        return "sleep"
    return {
        "happy": "sing",
        "normal": "walk",
        "sad": "sit",
        "angry": "run",
    }.get(mood, "idle")


def get_pet_state(db, user_id: str, group_id: str | None = None) -> PetState:
    group_id = db._format_gid(group_id)
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT favorability, is_blocked FROM user_state WHERE user_id=? AND group_id=?",
            (user_id, group_id),
        )
        state_row = cur.fetchone()

        cur.execute(
            "SELECT crab_coin, stamina FROM user_economy WHERE user_id=? AND group_id=?",
            (user_id, group_id),
        )
        economy_row = cur.fetchone()

        cur.execute(
            "SELECT timestamp FROM feed_log WHERE user_id=? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        feed_row = cur.fetchone()

        cur.execute(
            """
            SELECT i.item_name, s.item_icon, i.quantity, s.description
            FROM user_inventory i
            LEFT JOIN shop_items s ON i.item_name = s.item_name
            WHERE i.user_id = ? AND i.group_id = ? AND i.quantity > 0
            """,
            (user_id, group_id),
        )
        inventory_rows = cur.fetchall()

    exists = state_row is not None or economy_row is not None or bool(inventory_rows)
    favorability, is_blocked = state_row if state_row else (0, 0)
    crab_coin, stamina = economy_row if economy_row else (0, 0)
    last_feed_time = feed_row[0] if feed_row else None
    inventory = [
        {"name": row[0], "icon": row[1], "quantity": row[2], "description": row[3]}
        for row in inventory_rows
    ]
    mood = mood_from_state(int(favorability), int(stamina), last_feed_time)
    return PetState(
        user_id=user_id,
        exists=exists,
        favorability=int(favorability),
        is_blocked=bool(is_blocked),
        stamina=int(stamina),
        crab_coin=int(crab_coin),
        last_feed_time=last_feed_time,
        mood=mood,
        recommended_action=action_from_mood(mood, int(stamina)),
        inventory=inventory,
    )
