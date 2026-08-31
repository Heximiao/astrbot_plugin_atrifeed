from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.api import logger


DIARY_IMAGE_MAX_CHARS = 850


class DiaryRenderer:
    """Render short diary entries with the project's HTML screenshot engine."""

    def __init__(self, plugin: Any):
        self.plugin = plugin
        self.template_path = Path(plugin.curr_dir) / "template" / "diary.html"
        root = Path(plugin.curr_dir)
        self.good_mood_image = root / "pic" / "pictorial" / "my_atri1" / "emoji1.jpg"
        self.bad_mood_image = root / "pic" / "emoji" / "tired" / "atri_tired1.jpg"

    @staticmethod
    def should_render(content: str) -> bool:
        return bool(content.strip()) and len(content) <= DIARY_IMAGE_MAX_CHARS

    @staticmethod
    def _font_size(content_length: int) -> int:
        if content_length <= 100:
            return 31
        if content_length <= 220:
            return 27
        if content_length <= 400:
            return 24
        if content_length <= 600:
            return 21
        return 18

    @staticmethod
    def _image_data_uri(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def _crop_to_page_width(image_path: str) -> str:
        """Crop the 1280px T2I viewport to the template's 1000px body width."""
        try:
            from PIL import Image

            path = Path(image_path)
            with Image.open(path) as source:
                crop_width = round(source.width * 1000 / 1280)
                if crop_width >= source.width:
                    return image_path
                cropped = source.crop((0, 0, crop_width, source.height))
                temporary = path.with_name(f"{path.stem}_diary_crop.png")
                cropped.save(temporary, format="PNG")
            return str(temporary)
        except Exception as exc:
            logger.warning("[日记] 裁切右侧留白失败，保留原图: %s", exc)
            return image_path

    async def render(self, record: dict[str, Any]) -> str | None:
        content = str(record.get("diary_content", "") or "").strip()
        if not self.should_render(content):
            return None
        if not self.template_path.is_file():
            logger.warning("[日记] 图片模板资源缺失: %s", self.template_path)
            return None

        html_render = getattr(self.plugin, "html_render", None)
        if not callable(html_render):
            logger.warning("[日记] 当前环境不支持HTML图片渲染，回退到纯文字")
            return None

        date_text = str(record.get("date", "") or "")
        try:
            date_value = datetime.strptime(date_text, "%Y-%m-%d")
            display_date = f"{date_value.year}年{date_value.month}月{date_value.day}日"
            weekday = [
                "星期一", "星期二", "星期三", "星期四",
                "星期五", "星期六", "星期日",
            ][date_value.weekday()]
        except ValueError:
            display_date = date_text
            weekday = ""

        weather = str(record.get("weather", "") or "多云")
        weather_icon = {
            "晴": "☀",
            "雨": "☂",
            "阴": "☁",
            "多云": "☁",
            "多云转晴": "☀",
        }.get(weather, "☁")
        bad_mood = weather in {"阴", "雨"}
        mood_image_path = self.bad_mood_image if bad_mood else self.good_mood_image
        mood_image_uri = ""
        if mood_image_path.is_file():
            try:
                mood_image_uri = self._image_data_uri(mood_image_path)
            except OSError as exc:
                logger.warning("[日记] 读取心情贴图失败: path=%s, error=%s", mood_image_path, exc)
        else:
            logger.warning("[日记] 心情贴图缺失: %s", mood_image_path)
        try:
            template = self.template_path.read_text(encoding="utf-8")
            font_size = self._font_size(len(content))
            image_url = await html_render(
                template,
                {
                    "content": content,
                    "display_date": display_date,
                    "weekday": weekday,
                    "weather": weather,
                    "weather_icon": weather_icon,
                    "mood_image_uri": mood_image_uri,
                    "mood_caption": "今天有点累了……" if bad_mood else "今天也很有精神！",
                    "mood_class": "mood-bad" if bad_mood else "mood-good",
                    "font_size": font_size,
                    "word_count": len(content),
                },
                return_url=False,
                options={
                    "type": "png",
                    "quality": None,
                    "full_page": True,
                    "scale": "device",
                    "device_scale_factor_level": "high",
                },
            )
            logger.info("[日记] 图片渲染完成: chars=%s", len(content))
            return self._crop_to_page_width(str(image_url)) if image_url else None
        except Exception:
            logger.exception("[日记] 图片渲染失败，回退到纯文字")
            return None
