import random
import re
from astrbot.api.event import AstrMessageEvent
from .feeding import yield_random_folder_pic 

# 定义敏感词库
BAD_WORDS = ["傻逼", "sb", "你妈", "垃圾", "死鱼", "去死", "操你妈", "煞笔", "智障"]

def check_abuse(text: str) -> bool:
    """清理干扰字符并检测脏话"""
    # 移除空格和常见符号，防止 "s b" 绕过
    clean_text = re.sub(r"[\s\.\-\_\~\*\#]", "", text.lower())
    return any(word in clean_text for word in BAD_WORDS)

async def run_abuse_logic(event: AstrMessageEvent, db, curr_dir: str):
    
    # 移除 CQ 码（如果是 QQ 平台）和首尾空格
    clean_msg = re.sub(r"\[CQ:at,.*?\]", "", event.message_str).strip().lower()
    
    if not check_abuse(clean_msg):
        return
    # 这里直接用 message_str，因为我们要检测的是 @ 之后的文本
    if not check_abuse(event.message_str):
        return

    uid, gid = event.get_sender_id(), event.get_group_id()
    
    # 1. 记录次数 (复用 poop 的统计槽位)
    count = db.record_poop_and_get_count(uid, gid)
    
    # 2. 计算阶梯惩罚
    if count <= 3:
        penalty = 1
    else:
        m = count // 2
        penalty = (m * (m + 1)) // 2
        
    # 3. 执行扣分
    db.update_favorability(uid, gid, -penalty)
    
    # 4. 情感化回复
    responses = [
        f"亚托莉虽然是高性能机器人，但听到这种话也会难过的。好感度 -{penalty}",
        f"请自重，不要对亚托莉说这种词。好感度 -{penalty}",
        f"呜……这种话真的很过分。好感度 -{penalty}"
    ]
    yield event.plain_result(random.choice(responses))
        
    # 5. 发送 bed 文件夹里的图片
    async for res in yield_random_folder_pic(event, curr_dir, ["bed"]):
        yield res