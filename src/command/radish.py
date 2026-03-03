import os
from astrbot.api.event import AstrMessageEvent

async def run_radish_logic(event: AstrMessageEvent, curr_dir: str):
    """
    处理 /萝卜子 指令
    """
    # 调用现有的图片随机发送函数，指定 radish 文件夹
    async for res in yield_radish_pic(event, curr_dir):
        yield res
    yield event.plain_result("唔...这可是违反了机器人保护法的！")

async def yield_radish_pic(event: AstrMessageEvent, curr_dir: str):
    # 构建萝卜子表情包的绝对路径
    target_dir = os.path.join(curr_dir, "pic", "emoji", "radish")
    
    if os.path.exists(target_dir):
        import random
        valid_pics = [
            f for f in os.listdir(target_dir) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        ]
        if valid_pics:
            pick = random.choice(valid_pics)
            yield event.image_result(os.path.join(target_dir, pick))