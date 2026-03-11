from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

async def run_backpack_logic(event: AstrMessageEvent, db):
    user_id = event.get_sender_id()
    group_id = event.get_group_id()
    
    # 从数据库获取背包数据
    # 返回格式: [(item_name, item_icon, quantity, description), ...]
    inventory = db.get_user_inventory(user_id, group_id)
    
    if not inventory:
        yield event.plain_result("你的背包空空如也呢... 去商店买点东西吧！")
        return

    # 构造展示文本
    msg = "🎒 --- 我的背包 --- 🎒\n"
    msg += "----------------------\n"
    
    for item_name, icon, quantity, desc in inventory:
        msg += f"{icon} {item_name} x{quantity}\n"
        msg += f"   └ {desc}\n"
        
    msg += "----------------------\n"
    msg += "使用物品请发送：使用 [物品名]" # 预留功能提示
    
    yield event.plain_result(msg.strip())