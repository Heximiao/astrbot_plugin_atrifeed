# src/command/dice.py
import random
from datetime import datetime
from astrbot.api.event import AstrMessageEvent

async def run_dice_logic(event: AstrMessageEvent, db, curr_dir):
    user_id = event.get_sender_id()
    group_id = event.get_group_id()
    
    # 查一下骰子时间
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 获取当前用户的经济数据
    economy = db.get_user_economy(user_id, group_id)
    # 假设你的 get_user_economy 返回的是整个 row，我们需要获取 last_dice_time
    # 如果 row 长度不够，说明需要更新 database.py 的查询语句
    
    # 逻辑判断：一天一次
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_dice_time FROM user_economy WHERE user_id=? AND group_id=?", 
                    (user_id, db._format_gid(group_id)))
        row = cur.fetchone()
        last_dice = row[0] if row else ""

    if last_dice == today:
        yield event.plain_result("今天已经摇过骰子了，明天再来吧！")
        return

    # 摇骰子 1-9
    point = random.randint(1, 9)
    
    # 更新数据库
    db.update_dice_result(user_id, group_id, point)
    
    yield event.plain_result(f"🎲 你摇到了 {point} 点！\n获得了 {point} 螃蟹币和 {point} 点体力。")