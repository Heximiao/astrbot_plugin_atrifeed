import os
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

async def run_sign_in_logic(event: AstrMessageEvent, db, curr_dir: str, html_render):
    uid = event.get_sender_id()
    gid = event.get_group_id()
    
    # 获取当前经济状态
    coin, stamina, last_signin, *others = db.get_user_economy(uid, gid)
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. 检查重复签到 (重复签到我们依然用文字，省资源)
    if last_signin == today:
        yield event.plain_result("🎉 亚托莉提醒：你今天已经签过到啦！贪心可不是好孩子哦~")
        return

    # 2. 更新数据库
    new_coin = coin + 5
    new_stamina = stamina + 5
    db.update_signin(uid, gid, 5, 5)
    #db.update_favorability(uid, gid, 2)

    # 3. 准备渲染数据
    # 路径处理：将相对路径转为绝对路径，方便 Playwright 读取
    template_path = os.path.join(curr_dir, "template", "atri_sign_in.html")
    emoji_path = os.path.join(curr_dir, "pic", "sign_in", "atri_sign_in1.jpg")
    
    # 读取模板内容
    if not os.path.exists(template_path):
        yield event.plain_result(f"错误：找不到模板文件 {template_path}")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        tmpl_content = f.read()

    # 4. 渲染图片
    # 注意：src 在 HTML 里引用本地文件时，有些环境需要加上 file:///
    render_data = {
        "coin": new_coin,
        "stamina": new_stamina,
        "emoji_path": "file:///" + emoji_path.replace("\\", "/")
    }
    
    try:
        # 参照 rbq 排行，预估高度
        # header(80) + quote(80) + stats(120) + food(200) + footer(50) 
        # 设为 650 比较稳妥
        render_width = 600
        render_height = 350

        url = await html_render(
            tmpl_content, 
            render_data,
            options={
                "type": "png",
                "quality": None,
                "full_page": False, 
                "clip": {
                    "x": 0,
                    "y": 0,
                    "width": render_width,
                    "height": render_height
                },
                "scale": "device",
                "device_scale_factor_level": "ultra"
            }
        )
        yield event.image_result(url)
    except Exception as e:
        logger.error(f"ATRI 渲染失败: {e}")
        yield event.plain_result(f"🌟 签到成功！\n资产：{new_coin}币 | {new_stamina}体力")