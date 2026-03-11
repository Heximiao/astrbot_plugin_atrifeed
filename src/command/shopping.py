import random
import os
from pathlib import Path
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger # 别忘了导入 logger

async def run_shop_logic(event: AstrMessageEvent, db, curr_dir, html_render):
    user_id = event.get_sender_id()
    group_id = event.get_group_id()
    message_str = event.message_str.strip()
    
    # 解析指令
    parts = message_str.split()
    item_to_buy = parts[1] if len(parts) > 1 else None

    # --- 1. 每日随机逻辑 ---
    all_items = db.get_all_items()
    seed = datetime.now().strftime("%Y%m%d")
    random.seed(seed)
    
    num_to_show = min(len(all_items), random.randint(4, 6))
    daily_items = random.sample(all_items, num_to_show)
    daily_item_names = [i['item_name'] for i in daily_items]
    
    # --- 2. 处理“查看商店” (渲染图片) ---
    if not item_to_buy:
        # 随机选择一张立绘
        lihui_dir = os.path.join(curr_dir, "pic", "lihui", "shop")
        lihui_files = [f for f in os.listdir(lihui_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        selected_lihui = os.path.join(lihui_dir, random.choice(lihui_files)) if lihui_files else ""
        
        # 商店背景图路径
        bg_path = os.path.join(curr_dir, "pic", "shop", "shop1.jpeg")

        # 构建渲染数据
        render_data = {
            "items": daily_items,
            "bg_path": Path(bg_path).as_uri(),
            "lihui_path": Path(selected_lihui).as_uri() if selected_lihui else "",
            "date": datetime.now().strftime("%Y-%m-%d")
        }

        # 读取模板
        template_path = os.path.join(curr_dir, "template", "shop.html")
        if not os.path.exists(template_path):
            yield event.plain_result(f"错误：找不到模板文件 {template_path}")
            return

        with open(template_path, "r", encoding="utf-8") as f:
            tmpl_html = f.read()

        # --- 关键修改：手动精准裁切 ---
        try:
            # 根据背景图 shop1.jpeg 的实际尺寸设定
            render_width = 1150
            render_height = 700

            options = {
                "type": "jpeg",
                "quality": None,
                "full_page": False, # 禁用自动高度，解决下移立绘带来的白边问题
                "clip": {
                    "x": 0,
                    "y": 0,
                    "width": render_width,
                    "height": render_height
                },
                "scale": "device",
                "device_scale_factor_level": "ultra"
            }

            image_url = await html_render(tmpl_html, render_data, options=options)
            yield event.image_result(image_url)
            
        except Exception as e:
            logger.error(f"商店页面渲染失败: {e}")
            yield event.plain_result("哎呀，商店看板娘不小心摔倒了，图片没画出来...")
        
        random.seed() # 重置种子
        return

    # --- 3. 处理“购买商品” ---
    random.seed() 
    if item_to_buy not in daily_item_names:
        yield event.plain_result(f"唔... 今天的货架上似乎没有 {item_to_buy} 呢。")
        return

    success, msg = db.buy_item(user_id, group_id, item_to_buy, quantity=1, max_limit=20)
    yield event.plain_result(msg)