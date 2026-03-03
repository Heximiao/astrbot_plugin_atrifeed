# src/command/other_emoji.py
from astrbot.api.event import AstrMessageEvent
from .feeding import yield_random_folder_pic 

async def run_injection_logic(event: AstrMessageEvent, curr_dir: str):
    """处理打针指令逻辑"""
    yield event.plain_result("呜呜，亚托莉不想打针...")
    
    # 复用函数，传入 'scare' 类型
    async for res in yield_random_folder_pic(event, curr_dir, ["scare"]):
        yield res