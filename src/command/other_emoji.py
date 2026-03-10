# src/command/other_emoji.py
from astrbot.api.event import AstrMessageEvent
from .feeding import yield_random_folder_pic
import astrbot.api.message_components as Comp 
import os

async def run_injection_logic(event: AstrMessageEvent, curr_dir: str):
    """处理打针指令逻辑"""
    yield event.plain_result("呜呜，亚托莉不想打针...")
    
    # 复用函数，传入 'scare' 类型
    async for res in yield_random_folder_pic(event, curr_dir, ["scare"]):
        yield res

async def run_sleep_logic(event: AstrMessageEvent, curr_dir: str):
    """处理睡觉指令逻辑"""

    #import random
    #yield event.plain_result(random.choice(responses))
    image_path = os.path.join(curr_dir, "pic", "emoji", "yes", "yes1.jpg")
    chain = [
            Comp.Plain("亚托莉好困...夏生要来一起睡觉吗？"),
            Comp.Image.fromFileSystem(image_path), 
     ]
    
    # 假设你也有个 sleep 文件夹放睡觉相关的图片
    # 如果没有这个文件夹，这段可以注释掉
    yield event.chain_result(chain)