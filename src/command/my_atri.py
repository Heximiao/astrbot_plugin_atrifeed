import os
import random
import base64
from datetime import datetime
import time
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

async def run_my_atri_logic(event: AstrMessageEvent, db, curr_dir: str, html_render_func):
    uid = event.get_sender_id()
    #gid = event.get_group_id()
    raw_gid = event.get_group_id()
    
    db_gid = db._format_gid(raw_gid)
    gid = db_gid
    if not raw_gid:
        group_name = " 私聊"
    else:
        group_name = f"群:{raw_gid}" # 兜底值
        try:
            if event.get_platform_name() == "aiocqhttp":
                # 获取协议端 client
                client = event.bot 
                # 调用 NapCat 的 get_group_info 接口
                payloads = {"group_id": int(raw_gid)}
                ret = await client.api.call_action('get_group_info', **payloads)
                
                if ret and 'group_name' in ret:
                    group_name = f"群：{ret['group_name']}"
        except Exception as e:
            logger.error(f"[Atri] 获取群名称失败: {e}")
    
    # 检查用户是否在数据库中存在（即是否产生过好感度记录/投喂记录）
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM user_state WHERE user_id=? AND group_id=?", (uid, gid))
        exists = cur.fetchone()
        
    if not exists:
        yield event.plain_result("你还没有和亚托莉建立羁绊哦~，请从建立羁绊开始吧。")
        yield event.plain_result("详情请查看亚托莉帮助吧~")
        return

    last_feed_ts = db.get_last_feed_time(uid, gid)
    now_ts = int(time.time())
    
    # 计算天数差 (秒转天)
    if last_feed_ts:
        diff_days = (now_ts - last_feed_ts) / (24 * 3600)
    else:
        # 如果没有查到记录，直接按大于30天算
        diff_days = 31

    is_bored = random.random() < 0.2  # random.random() 返回 0.0 到 1.0 之间的浮点数
    extra_msg = None
    if is_bored:
        mood_text = "有点无聊"
        mood_code = "Bored"
        extra_msg = "呐~ 陪亚托莉玩点什么吧？"
    # 2. 根据天数判断情绪和跟发文字
    else:
        if diff_days < 3:
            mood_text = "非常高兴"
            mood_code = "Excellent"
        elif diff_days < 7:
            mood_text = "开心"
            mood_code = "Happy"
        elif diff_days < 14:
            mood_text = "心情一般"
            mood_code = "Normal"
            extra_msg = "多陪陪亚托莉吧~"
        elif diff_days < 30:
            mood_text = "有点低落"
            mood_code = "Low"
            extra_msg = "好久不见了，多陪陪亚托莉吧~"
        else:
            mood_text = "难过"
            mood_code = "Sad"
            extra_msg = None # 大于30天不跟发文字
    
    # 1. 获取数据库数据
    fav, is_blocked = db.get_user_state(uid, gid)
    
    # 这里的 curr_dir 应该是插件的根目录 (AtriPlugin 类中定义的 self.curr_dir)
    # 构造 template 和 pic 的绝对路径
    template_path = os.path.join(curr_dir, "template", "my_atri1.html")
    pic_base_dir = os.path.join(curr_dir, "pic", "pictorial", "my_atri1")

    # 获取详细统计数据
    with db._get_conn() as conn:
        conn.row_factory = lambda cursor, row: dict(zip([col[0] for col in cursor.description], row))
        cur = conn.cursor()
        cur.execute("SELECT * FROM feed_stats WHERE user_id=? AND group_id=?", (uid, gid))
        stats = cur.fetchone() or {}
        
        cur.execute("SELECT first_seen_time FROM user_state WHERE user_id=? AND group_id=?", (uid, gid))
        user_row = cur.fetchone()
    
    # 2. 计算相遇天数
    first_seen_ts = user_row.get('first_seen_time') if user_row else None
    if first_seen_ts:
        now_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = datetime.fromtimestamp(first_seen_ts).replace(hour=0, minute=0, second=0, microsecond=0)
        meet_days = (now_date - start_date).days + 1
    else:
        meet_days = 1

    # 3. 随机语句库
    quotes = [
        "我可是高性能的！",
        "既然是夏生的请求，那就没办法了",
        "今天的阳光，很温暖呢~",
        "夏生~，请不要盯着我看，我会过热的",
        "看我的，火——箭——拳——！",
        "亚托莉今天也准备好全力以赴了！"
    ]

    # 4. 图片转 Base64 辅助函数
    def get_base64_img(file_name):
        full_path = os.path.join(pic_base_dir, file_name)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
        else:
            logger.error(f"[Atri] 找不到图片文件: {full_path}")
            return ""

    month = datetime.now().month
    if 3 <= month <= 5:
        season_text = "Spring Date"
    elif 6 <= month <= 8:
        season_text = "Summer Date"
    elif 9 <= month <= 11:
        season_text = "Autumn Date"
    else:
        season_text = "Winter Date"
    # 5. 准备渲染数据
    uid = event.get_sender_id()
    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
    render_data = {
        "user_name": event.get_sender_name(),
        "user_avatar": avatar_url,
        "curr_date": datetime.now().strftime("%Y-%m-%d"),
        "group_name": group_name,
        "season_text": season_text,
        "meet_days": meet_days,
        "love_points": fav,
        "random_quote": random.choice(quotes),
        "bg_img": get_base64_img("bg1.jpg"),
        "emoji_img": get_base64_img("emoji1.jpg"),
        "total_feeding": stats.get("total_count", 0),
        "mood": mood_text,
        "items": {
            "strawberry": stats.get("strawberry_count", 0),
            "watermelon": stats.get("watermelon_count", 0),
            "apple": stats.get("apple_count", 0),
            "noodle": stats.get("noodle_count", 0),
            "shavedice": stats.get("shavedice_count", 0),
            "hamburger": stats.get("hamburger_count", 0),
            "pizza": stats.get("pizza_count", 0),
            "bento": stats.get("bento_count", 0),
            "mushroom": stats.get("mushroom_count", 0),
            "lollipop": stats.get("lollipop_count", 0),
            "riceball": stats.get("riceball_count", 0),
            "crab": stats.get("crab_count", 0),
        }
    }

    # 6. 读取 HTML 并渲染
    if not os.path.exists(template_path):
        yield event.plain_result(f"错误：找不到模板文件 {template_path}")
        return

    with open(template_path, "r", encoding="utf-8") as f:
            tmpl_content = f.read()

    # 精准裁剪参数
    try:
        # 参照 rbq 排行，预估高度
        # header(80) + quote(80) + stats(120) + food(200) + footer(50) 
        # 设为 650 比较稳妥
        render_width = 600
        render_height = 587

        url = await html_render_func(
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
    if extra_msg:
        yield event.plain_result(extra_msg)