# src/constants.py
from ..keyword_trigger import KeywordRoute, PermissionLevel

_DEFAULT_KEYWORD_ROUTES: tuple[KeywordRoute, ...] = (
    # 投喂逻辑
    KeywordRoute(keyword="🦀", action="feed_crab"),
    
    KeywordRoute(keyword="🍎", action="feed_fruit"),
    KeywordRoute(keyword="🍓", action="feed_fruit"),
    KeywordRoute(keyword="🍜", action="feed_fruit"),
    KeywordRoute(keyword="🍉", action="feed_fruit"),
    KeywordRoute(keyword="🍔", action="feed_fruit"),
    KeywordRoute(keyword="🍕", action="feed_fruit"),
    KeywordRoute(keyword="🍱", action="feed_fruit"),
    KeywordRoute(keyword="🍄", action="feed_fruit"),
    KeywordRoute(keyword="🍭", action="feed_fruit"),
    KeywordRoute(keyword="🍙", action="feed_fruit"),
    KeywordRoute(keyword="🍧", action="feed_fruit"),
    
    KeywordRoute(keyword="✨", action="star_effect"),
    KeywordRoute(keyword="🚬", action="no_smoke"),

    KeywordRoute(keyword="💩", action="poop_effect"),

    KeywordRoute(keyword="我的亚托莉", action="my_atri_card"),
    KeywordRoute(keyword="亚托莉帮助", action="show_help"),
    
    KeywordRoute(keyword="萝卜子", action="radish_cmd"),
    KeywordRoute(keyword="🥕", action="radish_cmd"),
    KeywordRoute(keyword="飞舞萝卜子", action="radish_cmd"),

    KeywordRoute(keyword="💉", action="injection_effect"),
    
    KeywordRoute(keyword="亚托莉签到", action="atri_signin"),
    KeywordRoute(keyword="亚托莉打工", action="atri_work"),

)