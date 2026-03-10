import random
import time
import os
from datetime import datetime
# 导入同级目录 feeding.py 中的工具函数
from .feeding import send_combined_msg, get_pic_path
import astrbot.api.message_components as Comp

async def run_gig_logic(event, db, curr_dir, html_render):
    uid = event.get_sender_id()
    gid = event.message_obj.group_id
    
    economy = db.get_user_economy(uid, gid)
    coin, curr_stamina, last_signin, last_work_time, last_work_refuse = economy
    
    today = datetime.now().strftime("%Y-%m-%d")
    now_ts = int(time.time())
    tired_img = os.path.join(curr_dir, "pic", "emoji", "tired", "atri_tired1.jpg")

    # === 1. 优先检查 CD (正在打工中) ===
    if last_work_time > 0:
        # 建议 CD 稍微设长一点，你代码里写的 random.randint(5, 8) * 3600 是 5-8 小时
        # 为了测试你可能改成了秒，这里保留原逻辑
        cd_seconds = random.randint(5, 8) * 3600 
        if now_ts - last_work_time < cd_seconds:
            remaining_mins = int((cd_seconds - (now_ts - last_work_time)) // 60)
            yield event.plain_result(f"亚托莉还在打工呢...大概还需要 {remaining_mins} 分钟才能再次打工。")
            return

    # === 2. 检查今天是否已经罢工过 ===
    # 只有 CD 过了，才会走到这一步
    if last_work_refuse == today:
        async for result in send_combined_msg(event, "亚托莉今天已经累坏了，不想再打工了...", tired_img):
            yield result
        return

    # === 3. 随机判定：是否触发今天的罢工 ===
    # 只有今天还没罢工，且 CD 过了，才进行 10% 概率判定
    if random.random() < 0.1: 
        db.set_work_refuse(uid, gid) # 标记今天罢工
        async for result in send_combined_msg(event, "亚托莉突然想偷懒，今天不想打工了！", tired_img):
            yield result
        return

    # === 4. 正常的体力检查与打工逻辑 ===
    earn_coin = random.randint(10, 15)
    cost_stamina = random.randint(10, 15)
    
    if curr_stamina < cost_stamina:
        yield event.plain_result(f"体力不足！打工需要 {cost_stamina} 体力，当前仅剩 {curr_stamina}。")
        return
    # 更新数据库
    db.update_work_result(uid, gid, earn_coin, -cost_stamina, now_ts)
    
    lihui_path = os.path.abspath(os.path.join(curr_dir, "pic", "lihui", "gig", "atri4.png")) 
    
    render_data = {
        "earn_coin": earn_coin,
        "cost_stamina": cost_stamina,
        "lihui_path": lihui_path
    }

    # 读取模板
    tmpl_path = os.path.join(curr_dir, "template", "gig.html")
    if not os.path.exists(tmpl_path):
        yield event.plain_result(f"错误：找不到模板文件 {tmpl_path}")
        return

    with open(tmpl_path, "r", encoding="utf-8") as f:
        tmpl_content = f.read()

    #options = {
        #"type": "png",
        #"omit_background": True, # 透明背景
        #"full_page": True,       # 自动裁切到页面内容大小
        #"animations": "disabled" # 禁用动画防止截图瞬间内容未加载
    #}

    try:
        # 参照 rbq 排行，预估高度
        # header(80) + quote(80) + stats(120) + food(200) + footer(50) 
        # 设为 650 比较稳妥
        render_width = 770
        render_height = 390

        url = await html_render(
            tmpl_content, 
            render_data,
            options={
                "type": "png",
                "quality": None,
                "full_page": False, 
                "clip": {
                    "x": 15,
                    "y": 0,
                    "width": render_width,
                    "height": render_height
                },
                "scale": "device",
                "device_scale_factor_level": "ultra"
            }
        )
        #yield event.image_result(url)
        chain = [
            Comp.Plain("  哼~哼~哼~，打工~"),
            Comp.Image.fromURL(url),
            Comp.At(qq=event.get_sender_id()),
        ]
        yield event.chain_result(chain)
    except Exception as e:
        yield event.plain_result(f"（；´д｀）渲染失败了... 赚到了 {earn_coin} 币")