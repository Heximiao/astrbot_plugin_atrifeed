import random
from datetime import datetime
from astrbot.api.event import AstrMessageEvent

async def run_shop_logic(event: AstrMessageEvent, db):
    user_id = event.get_sender_id()
    group_id = event.get_group_id()
    message_str = event.message_str.strip()
    
    # 解析指令
    parts = message_str.split()
    # 假设指令是 /商店 或者是 /商店 蛋包饭
    item_to_buy = parts[1] if len(parts) > 1 else None

    # --- 1. 每日随机逻辑 ---
    all_items = db.get_all_items()
    # 使用当前日期作为随机种子，保证全服每天看到的商品一致，但每天都在变
    seed = datetime.now().strftime("%Y%m%d")
    random.seed(seed)
    
    # 比如：每天从商品库随机上架 4-6 件商品
    num_to_show = min(len(all_items), random.randint(4, 6))
    daily_items = random.sample(all_items, num_to_show)
    daily_item_names = [i['item_name'] for i in daily_items]
    
    # 重置随机种子，避免影响后续其他逻辑
    random.seed()

    # --- 2. 处理“查看商店” ---
    if not item_to_buy:
        shop_msg = "🏪 --- 亚托莉小卖部 --- 🏪\n"
        shop_msg += "今天的商品都是新鲜上架的哦！\n\n"
        for item in daily_items:
            shop_msg += f"{item['item_icon']} {item['item_name']} | 💰{item['price']} 螃蟹币\n"
            shop_msg += f"   - {item['description']}\n"
        shop_msg += "\n💡 输入 [/商店 物品名] 即可购买"
        yield event.plain_result(shop_msg)
        return

    # --- 3. 处理“购买商品” ---
    # 校验商品是否在今日清单中
    if item_to_buy not in daily_item_names:
        yield event.plain_result(f"唔... 今天的货架上似乎没有 {item_to_buy} 呢。")
        return

    # 执行购买
    success, msg = db.buy_item(user_id, group_id, item_to_buy, quantity=1, max_limit=20)
    yield event.plain_result(msg)