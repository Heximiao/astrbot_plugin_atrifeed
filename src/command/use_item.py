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
    item_type = item_data.get('item_type')
    effect_val = item_data.get('effect_value', 0)
    icon = item_data.get('item_icon', '📦')

    result_msg = f"使用了 {icon} {item_name}！\n"

    if item_type == "food":
        # 食物增加体力值
        db.update_signin(user_id, group_id, 0, effect_val) # 复用 update_signin 的逻辑
        result_msg += f"美味！体力值增加了 {effect_val} 点。"
    
    elif item_type == "apparel":
        # 服饰增加好感度
        new_fav = db.update_favorability(user_id, group_id, effect_val)
        result_msg += f"亚托莉很开心！好感度增加了 {effect_val} 点。\n当前好感度：{new_fav}"
    
    elif item_type == "tool":
        # 工具类逻辑（如机票、烟花）
        if item_name == "烟花":
            new_fav = db.update_favorability(user_id, group_id, effect_val)
            result_msg += f"🎆 砰！绚丽的烟花映照着亚托莉的笑脸。\n好感度大幅提升了 {effect_val} 点！"
        else:
            result_msg += f"虽然使用了，但好像还没到时候呢...（该道具目前仅供收藏）"
    
    else:
        result_msg += "这件物品似乎没有什么特殊用途呢。"

    yield event.plain_result(result_msg.strip())