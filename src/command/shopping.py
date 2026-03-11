import random
import os
from pathlib import Path
from datetime import datetime
from astrbot.api.event import AstrMessageEvent

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
        with open(template_path, "r", encoding="utf-8") as f:
            tmpl_html = f.read()

        # 渲染图片
        options = {"type": "jpeg", "quality": 80, "viewport": {"width": 1920, "height": 1080}}
        image_url = await html_render(tmpl_html, render_data, options=options)
        
        yield event.image_result(image_url)
        random.seed() # 重置种子
        return

    # --- 3. 处理“购买商品” ---
    random.seed() # 购买逻辑不需要固定种子
    if item_to_buy not in daily_item_names:
        yield event.plain_result(f"唔... 今天的货架上似乎没有 {item_to_buy} 呢。")
        return

    success, msg = db.buy_item(user_id, group_id, item_to_buy, quantity=1, max_limit=20)
    yield event.plain_result(msg)