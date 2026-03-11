import random
import re
from astrbot.api.event import AstrMessageEvent
from .feeding import yield_random_folder_pic
from ..utils.bayes_filter import AtriBayesFilter

import os

DEBUG_MODE = True

# 获取当前文件 (abuse.py) 的路径 -> src/command/
current_dir = os.path.dirname(__file__)
# 向上跳两级，到达插件根目录 -> astrbot_plugin_atrifeed/
plugin_root = os.path.dirname(os.path.dirname(current_dir))
# 拼接正确的 data 路径
data_path = os.path.join(plugin_root, "data")

# 初始化分类器
filter_instance = AtriBayesFilter(data_path)

# 定义敏感词库
BAD_WORDS = ["傻逼", "你妈死了", "去死", "操你妈", "煞笔", "智障"]



def check_abuse(text: str) -> bool:
    """清理干扰字符并检测脏话"""
    # 移除空格和常见符号，防止 "s b" 绕过
    clean_text = re.sub(r"[\s\.\-\_\~\*\#]", "", text.lower())
    return any(word in clean_text for word in BAD_WORDS)

async def run_abuse_logic(event: AstrMessageEvent, db, curr_dir: str):
    # 提取纯文本
    clean_msg = event.message_str.strip()

    if len(clean_msg) > 100:
        return
    
    # 获取超详细调试信息
    debug = filter_instance.get_debug_info(clean_msg)
    
    # 构造展示文本
    if DEBUG_MODE:
        report = [f"📊 【调试报告】文本：{clean_msg}"]
        report.append(f"📈 总辱骂概率: {debug['total_prob']:.4f}")
        report.append("-" * 20)
        for w in debug['words']:
            report.append(f"词: [{w['词']}] | {w['倾向']} (辱骂{w['辱骂分贡献']} vs 正常{w['正常分贡献']})")
        report.append("-" * 20)
        report.append(f"判定结果: {debug['final_decision']}")

        # 直接发给用户看
        yield event.plain_result("\n".join(report))
    
    # 1. 极其严重的词（零容忍词库），依然保留硬匹配
    HARD_WORDS = ["傻逼", "你妈死了", "去死", "操你妈", "煞笔", "智障"] 
    if any(w in clean_msg.lower() for w in HARD_WORDS):
        is_violation = True
    else:
        # 2. 容易误触的词（垃圾、死、蠢等），交给贝叶斯
        is_violation = filter_instance.is_abuse(clean_msg, threshold=0.73)

    if not is_violation:
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