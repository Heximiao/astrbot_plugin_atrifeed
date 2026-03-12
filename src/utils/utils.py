# src/utils.py
from astrbot.api.event import AstrMessageEvent

def is_group_allowed(event: AstrMessageEvent, config: dict) -> bool:
    """
    检查当前群组是否在黑白名单允许范围内
    """
    group_id = event.get_group_id()
    
    # 如果是私聊，默认允许
    if not group_id: 
        return True 

    whitelist_str = config.get("whitelist_groups", "").replace("，", ",")
    blacklist_str = config.get("blacklist_groups", "").replace("，", ",")
    
    # 转换为列表并去除空格
    whitelist = [g.strip() for g in whitelist_str.split(",") if g.strip()]
    blacklist = [g.strip() for g in blacklist_str.split(",") if g.strip()]

    # 1. 白名单逻辑
    if whitelist:
        return str(group_id) in whitelist or group_id in whitelist
    
    # 2. 黑名单逻辑
    if str(group_id) in blacklist or group_id in blacklist:
        return False
        
    return True

