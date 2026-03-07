# src/command/ban.py

import random
from astrbot.api.event import AstrMessageEvent
from .command.feeding import yield_random_folder_pic # 假设这个函数在这里定义或导入

async def run_apology_logic(event: AstrMessageEvent, db, config: dict, curr_dir: str, apology_count_map: dict):
    uid = event.get_sender_id()
    gid = event.get_group_id()
    
    # 获取状态
    is_blocked_total = db.get_blocked_total(uid)
    fav, is_blocked = db.get_user_state(uid, gid)
    total_forgiven = db.get_total_forgiven(uid)
    
    message_str = event.message_str
    is_apology_msg = "亚托莉我错了对不起" in message_str
    use_qq_ban = config.get("global_ban_use_qq", True)

    # 1. 处于被拉黑状态且不是在道歉：拦截
    if is_blocked == 1 and not is_apology_msg:
        if use_qq_ban:
            event.stop_event()
        return

    # 2. 达到原谅上限且多次被封：永久拒绝
    if total_forgiven >= 1 and is_blocked_total > 1:
        if use_qq_ban:
            event.stop_event()
            if is_apology_msg:
                yield event.plain_result("...亚托莉已经不想再听到你的声音了。")
        return

    # 3. 处理道歉消息的具体逻辑
    if is_apology_msg:
        # 如果没被拉黑，不需要道歉
        if is_blocked == 0:
            yield event.plain_result("亚托莉...才..才没有生气呢！")
            async for res in yield_random_folder_pic(event, curr_dir, ["angry"]):
                yield res
            return

        # 计数器逻辑
        apology_count_map[uid] = apology_count_map.get(uid, 0) + 1
        
        if apology_count_map[uid] >= 3:
            # 触发原谅
            new_total = db.increase_forgiven_and_check_global(uid, gid)
            db.unblock_user(uid, gid)
            db.reset_poop_count(uid, gid)
            apology_count_map[uid] = 0
            yield event.plain_result(f"既然你这么诚恳...亚托莉就原谅你这一次吧！(累计原谅次数：{new_total})")
        else:
            yield event.plain_result(f"哼，亚托莉还在生气！（{apology_count_map[uid]}/3）")