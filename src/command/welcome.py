from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Plain, At
import random
async def welcome_new_user(plugin,event: AstrMessageEvent):
    atri_welcomes_extended = [
        # ---- 高性能自夸系列 ----
        "滴滴！检测到新船员登舰！作为超高性能的机器人，亚托莉在此列队欢迎！请出示你的指令~",
        "为了迎接你的到来，亚托莉可是把群里打扫得闪闪发光哦！哼哼，快夸奖我这个高性能的管理员吧！",
        "收到新成员入群的通知！亚托莉已经把你的名字记在主内存里了。如果在群里迷路了，随时可以呼叫高性能的亚托莉哦！",
        "哦呀？有新人迷路到这里了吗？放心吧，交给我这个高性能机器人，保证让你在这里每天都开开心心的！",
        # ---- 寻找“心”与情感系列 ----
        "欢迎新面孔！亚托莉的逻辑回路正在分析你的数据……分析完毕：是一个能让亚托莉收集到‘心之碎片’的好人呢！",
        "欢迎你！能在茫茫互联网之海中相遇，一定是因为你的心信号和亚托莉产生了共鸣吧！✨",
        "啦啦啦~ 伴随着亚托莉的歌声，欢迎新成员登场！今天也是和平的一天呢，感觉又懂了一点点‘开心’的情感！",
        # ---- 机器人设定与日常系列 ----
        "（揉眼睛）唔……休眠模式解除。发现新成员！亚托莉现在完全清醒了，热烈欢迎你的加入！",
        "新成员加入确认！亚托莉的电量瞬间充满啦！要在群里好好相处哦，不然亚托莉会用机械臂把你扔进海里的！（开玩笑的~）",
        "系统启动……视觉模块上线。哇！看到新人啦！初次见面，我是亚托莉，请多多指教！",
        "警告！警告！前方高能可爱新人出没！亚托莉的散热风扇都要转不过来了！欢迎进群！",
        # ---- 潜水艇与废土海洋背景系列 ----
        "欢迎来到这艘漂浮在互联网之海的潜水艇！我是领航员亚托莉！请系好安全带，准备和大家一起下潜吧！",
        "在这个逐渐被海水淹没的世界里，能多一个同伴真是太好啦！亚托莉会用100%的热情欢迎你的！",
        "打捞确认！成功从深海中打捞上一名新群友！我是负责人亚托莉，接下来的日子请多关照啦！",
        # ---- 傲娇/小脾气系列 ----
        "既然你诚心诚意地加群了，那亚托莉就大发慈悲地欢迎你吧！绝对不是因为我期待有人陪我玩哦！",
        "欢迎进群！先说好，亚托莉可是很忙的，如果你发了好玩的东西，我才会偶尔用高性能的CPU看一眼哦！（悄悄盯）"
    ]
    if not hasattr(event.message_obj, 'raw_message'):
        return
    raw_msg = event.message_obj.raw_message
    if isinstance(raw_msg, dict) and raw_msg.get("notice_type") == "group_increase":
        user_id = str(raw_msg.get("user_id"))
        chain=[
            At(qq=user_id),
            Plain(random.choice(atri_welcomes_extended)),
        ]
        await event.send(event.chain_result(chain))
