from astrbot.api.event import AstrMessageEvent
from datetime import datetime

async def run_sign_in_logic(event: AstrMessageEvent, db):
    uid = event.get_sender_id()
    gid = event.get_group_id()
    
    # 获取当前经济状态
    coin, stamina, last_signin, _ = db.get_user_economy(uid, gid)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if last_signin == today:
        yield event.plain_result("🎉 亚托莉提醒：你今天已经签过到啦！贪心可不是好孩子哦~")
        return

    # 更新数据库：+5螃蟹币，+5体力
    db.update_signin(uid, gid, 5, 5)
    
    # 也可以顺便加一点点好感度（可选）
    #db.update_favorability(uid, gid, 2)

    msg = (
        f"🌟 签到成功！\n"
        f"获得了 5 🦀螃蟹币 和 5 ⚡体力。\n"
        f"当前资产：{coin + 5} 螃蟹币 | {stamina + 5} 体力"
    )
    yield event.plain_result(msg)