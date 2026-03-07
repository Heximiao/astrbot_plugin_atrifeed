import random
import time
import os
from datetime import datetime
# 导入同级目录 feeding.py 中的工具函数
from .feeding import send_combined_msg, get_pic_path

async def run_gig_logic(event, db, curr_dir):
    uid = event.get_sender_id()
    gid = event.message_obj.group_id
    
    # 获取经济数据并解包
    economy = db.get_user_economy(uid, gid)
    # 确保这里的顺序和数据库查询语句一致
    coin, curr_stamina, last_signin, last_work_time, last_work_refuse = economy
    
    today = datetime.now().strftime("%Y-%m-%d")
    tired_img = os.path.join(curr_dir, "pic", "emoji", "tired", "atri_tired1.jpg")
    
    # A. 优先检查今天是否已经拒绝过
    if last_work_refuse == today:
        async for result in send_combined_msg(event, "亚托莉今天不想打工...", tired_img):
            yield result
        return

    # B. 罢工随机判断 (为了测试，建议放在 CD 检查前)
    # 0.1 的概率触发
    if random.random() < 0.1: 
        db.set_work_refuse(uid, gid)
        async for result in send_combined_msg(event, "亚托莉今天不想打工...", tired_img):
            yield result
        return

    # C. 检查冷却时间
    now_ts = int(time.time())
    if last_work_time > 0:
        # 5-8小时随机 CD
        cd_seconds = random.randint(5, 8) * 3600
        if now_ts - last_work_time < cd_seconds:
            remaining_mins = int((cd_seconds - (now_ts - last_work_time)) // 60)
            yield event.plain_result(f"亚托莉还在打工呢...大概还需要 {remaining_mins} 分钟才能再次打工。")
            return

    # D. 正常的打工逻辑
    earn_coin = random.randint(10, 15)
    cost_stamina = random.randint(10, 15)
    
    if curr_stamina < cost_stamina:
        yield event.plain_result(f"体力不足！打工需要 {cost_stamina} 体力，当前仅剩 {curr_stamina}。")
        return

    # 更新数据库
    db.update_work_result(uid, gid, earn_coin, -cost_stamina, now_ts)
    
    random_pic = await get_pic_path(curr_dir, ["emoji"])
    msg = f"正在打工！亚托莉赚到了 {earn_coin} 螃蟹币，消耗 {cost_stamina} 体力。\n当前体力: {curr_stamina - cost_stamina}"
    
    async for result in send_combined_msg(event, msg, random_pic):
        yield result