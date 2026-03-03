import os
import base64 # 1. 导入 base64 库
import logging
import random
from astrbot.api.event import AstrMessageEvent

# 获取 AstrBot 的日志对象
logger = logging.getLogger("astrbot")

async def run_atri_help_logic(self, event: AstrMessageEvent, config: dict):
    # 1. 基础数据准备
    trigger_mode = config.get("keyword_trigger_mode", "exact")
    keyword_enabled = config.get("keyword_trigger_enabled", True)
    mode_text = {"exact": "完全匹配", "starts_with": "开头匹配", "contains": "包含关键词"}.get(trigger_mode, "未知")

    help_items = [
        {"command": "🦀", "description": "投喂螃蟹"},
        {"command": "🍓/🍉/🍎/🍜/🍧/🍔/🍕/🍱/🍄/🍭/🍙", "description": "投喂加好感"},
        {"command": "✨/🚬/💩/💉", "description": "触发各种言语"},
        {"command": "我的亚托莉", "description": "查看羁绊值"},
        {"command": "萝卜子", "description": "猜猜看会发生什么（笑）"},
        {"command": "亚托莉我错了对不起", "description": "被拉黑道歉尝试恢复好感"},
    ]

    # 2. 路径处理
    # 假设 main.py 在插件根目录，help.py 在 src/command/ 下
    curr_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    template_path = os.path.join(curr_dir, "template", "atri_help.html")
    # 立绘的本地绝对路径
    #lihui_path_local = os.path.join(curr_dir, "pic", "lihui", "atri1.png")
    
    lihui_dir = os.path.join(curr_dir, "pic", "lihui")
    if not os.path.exists(template_path):
        yield event.plain_result(f"错误：找不到模板 {template_path}")
        return

    # 3. 读取立绘并转为 Base64 (核心修改)
    img_base64 = ""
    if os.path.exists(lihui_dir) and os.path.isdir(lihui_dir):
        try:
            # 筛选文件夹内的图片文件 (支持 png, jpg, jpeg)
            valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
            images = [f for f in os.listdir(lihui_dir) if f.lower().endswith(valid_extensions)]

            if images:
                # 随机选择一个文件名
                chosen_image = random.choice(images)
                lihui_path_local = os.path.join(lihui_dir, chosen_image)
                
                with open(lihui_path_local, "rb") as f:
                    img_data = f.read()
                    # 自动识别后缀名以设置正确的 MIME 类型
                    ext = os.path.splitext(chosen_image)[1][1:].lower()
                    if ext == "jpg": ext = "jpeg"
                    
                    img_base64 = f"data:image/{ext};base64,{base64.b64encode(img_data).decode()}"
                
                logger.info(f"[Atri] 随机抽取的立绘: {chosen_image}")
            else:
                logger.warning(f"lihui 文件夹内没有图片文件")
        except Exception as e:
            logger.error(f"读取随机立绘失败: {e}")
    else:
        logger.warning(f"找不到立绘文件夹: {lihui_dir}")

    # 4. 读取 HTML 模板
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    try:
        # 5. 计算动态高度 (仿照你的参考代码)
        header_h = 120 
        item_h = 70  
        footer_h = 40
        dynamic_height = header_h + (len(help_items) * item_h) + footer_h
        render_width = 600 # 帮助卡片稍微宽一点

        # 6. 渲染
        url = await self.html_render(template_content, {
            "help_items": help_items,
            "mode_text": mode_text,
            "keyword_enabled": keyword_enabled,
            "lihui_path": img_base64 # 将 Base64 字符串传给模板
        }, 
        options={
            "type": "png",
            "quality": None,
            "full_page": False, # 必须配合 clip
            "clip": {
                "x": 0,
                "y": 0,
                "width": render_width,
                "height": dynamic_height 
            },
            "scale": "device",
            # 如果这行报错，可以先注释掉
            "device_scale_factor_level": "ultra" 
        })
        
        yield event.image_result(url)

    except Exception as e:
        logger.error(f"渲染亚托莉帮助失败: {e}")
        yield event.plain_result(f"渲染失败: {str(e)}")