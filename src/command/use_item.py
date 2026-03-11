from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

async def run_use_item_logic(event: AstrMessageEvent, db):
    user_id = event.get_sender_id()
    group_id = event.get_group_id()
    message_str = event.message_str.strip()
    
    # 解析指令：使用 [物品名]
    parts = message_str.split()
    if len(parts) < 2:
        yield event.plain_result("你想使用什么呢？请发送：使用 [物品名]")
        return
        
    item_name = parts[1]
    
    # 1. 在数据库中尝试消耗
    item_data, status_msg = db.consume_item(user_id, group_id, item_name)
    
    if not item_data:
        yield event.plain_result(status_msg)
        return

    # 2. 根据 item_type 处理效果
    effect_val = item_data.get('effect_value', 0)
    item_type = item_data.get('item_type')
    name = item_data.get('item_name')

    if item_type == "food":
        # 对应：蛋包饭、菠萝、奶茶
        db.update_signin(user_id, group_id, 0, effect_val)
        yield event.plain_result(f"投喂了亚托莉 {name} ，体力增加了 {effect_val} 点！好吃就是高兴！")

    elif item_type == "apparel":
        # 对应：新鞋子、新衣服
        new_fav = db.update_favorability(user_id, group_id, effect_val)
        yield event.plain_result(f"给亚托莉换上了 {name} 👗，好感度增加了 {effect_val} 点！")

    elif item_type == "tool":
        # 对应：机票、烟花
        if name == "烟花":
            new_fav = db.update_favorability(user_id, group_id, effect_val)
            yield event.plain_result(f"🎆 在夏夜的海岸边放了一场绚烂的烟花。好感度大幅增加了 {effect_val} 点！")
        elif name == "机票":
            # 机票在你的注释里是剧情道具，建议这里做个阻拦
            yield event.plain_result(f"✈️ 虽然已经准备好了机票，但似乎距离出发去『圣地巡礼』还需要达成某种契机呢...（目前仅供持有）")
    
    else:
        yield event.plain_result("这件物品似乎没有什么特殊用途呢。")
