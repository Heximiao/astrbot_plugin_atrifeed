from __future__ import annotations

import base64
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.api import logger


DIARY_IMAGE_MAX_CHARS = 850

ATRI_ONE_LINERS = (
    "今日も高性能です！",
    "大切な思い出を残しましょう！",
    "今天的回忆也要好好保存。",
    "海风正好，适合记录今天。",
    "能源充足，状态良好！",
    "普通的一天也值得珍藏。",
)

DIARY_TEMPLATE_FILES = {
    "海风手记": "diary.html",
    "经典手账": "diary_legacy.html",
}
DEFAULT_DIARY_TEMPLATE = "经典手账"


class DiaryRenderer:
    """Render short diary entries with the project's HTML screenshot engine."""

    def __init__(self, plugin: Any):
        self.plugin = plugin
        root = Path(plugin.curr_dir)
        self.template_dir = root / "template" / "diary"
        self.good_mood_image = root / "pic" / "pictorial" / "my_atri1" / "emoji1.jpg"
        self.bad_mood_image = root / "pic" / "emoji" / "tired" / "atri_tired1.jpg"
        self.left_entry_illustration = root / "pic" / "lihui" / "shop" / "atri6.png"
        self.right_entry_illustration = root / "pic" / "lihui" / "atri2.png"

    @property
    def template_path(self) -> Path:
        root_config = getattr(self.plugin, "config", {}) or {}
        root_get = getattr(root_config, "get", None)
        diary_config = root_get("diary", {}) if callable(root_get) else {}
        diary_get = getattr(diary_config, "get", None)
        configured = str(
            diary_get("template_style", DEFAULT_DIARY_TEMPLATE)
            if callable(diary_get)
            else DEFAULT_DIARY_TEMPLATE
        )
        filename = DIARY_TEMPLATE_FILES.get(configured)
        if filename is None:
            logger.warning("[日记] 未知图片模板 %r，回退到%s", configured, DEFAULT_DIARY_TEMPLATE)
            filename = DIARY_TEMPLATE_FILES[DEFAULT_DIARY_TEMPLATE]
        return self.template_dir / filename

    @staticmethod
    def should_render(content: str) -> bool:
        return bool(content.strip()) and len(content) <= DIARY_IMAGE_MAX_CHARS

    @staticmethod
    def _font_size(content_length: int, *, legacy: bool = False) -> int:
        if legacy:
            if content_length <= 100:
                return 31
            if content_length <= 220:
                return 27
            if content_length <= 400:
                return 24
            if content_length <= 600:
                return 21
            return 18
        if content_length <= 120:
            return 26
        if content_length <= 260:
            return 23
        if content_length <= 450:
            return 21
        if content_length <= 650:
            return 19
        return 17

    @staticmethod
    def _image_data_uri(path: Path) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime_type};base64,{encoded}"

    def _optional_image_data_uri(self, path: Path, label: str) -> str:
        if not path.is_file():
            logger.warning("[日记] %s缺失: %s", label, path)
            return ""
        try:
            return self._image_data_uri(path)
        except OSError as exc:
            logger.warning("[日记] 读取%s失败: path=%s, error=%s", label, path, exc)
            return ""

    @staticmethod
    def _crop_to_page_width(image_path: str, *, centered: bool) -> str:
        """Crop the 1280px T2I viewport to the selected template's canvas."""
        try:
            from PIL import Image

            path = Path(image_path)
            with Image.open(path) as source:
                crop_width = round(source.width * 1000 / 1280)
                if crop_width >= source.width:
                    return image_path
                left = (source.width - crop_width) // 2 if centered else 0
                cropped = source.crop((left, 0, left + crop_width, source.height))
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
        template_path = self.template_path
        if not template_path.is_file():
            logger.warning("[日记] 图片模板资源缺失: %s", template_path)
            return None

        html_render = getattr(self.plugin, "html_render", None)
        if not callable(html_render):
            logger.warning("[日记] 当前环境不支持HTML图片渲染，回退到纯文字")
            return None

        date_text = str(record.get("date", "") or "")
        try:
            date_value = datetime.strptime(date_text, "%Y-%m-%d")
            display_date = f"{date_value.year}年{date_value.month}月{date_value.day}日"
            weekday_zh = [
                "星期一", "星期二", "星期三", "星期四",
                "星期五", "星期六", "星期日",
            ][date_value.weekday()]
            weekday = [
                "月曜日", "火曜日", "水曜日", "木曜日",
                "金曜日", "土曜日", "日曜日",
            ][date_value.weekday()]
        except ValueError:
            display_date = date_text
            weekday = ""
            weekday_zh = ""

        weather = str(record.get("weather", "") or "多云")
        weather_icon = {
            "晴": "☀",
            "雨": "☂",
            "阴": "☁",
            "多云": "☁",
            "多云转晴": "☀",
        }.get(weather, "☁")
        weather_display = {
            "晴": "晴れ",
            "雨": "雨",
            "阴": "曇り",
            "多云": "くもり",
            "多云转晴": "曇りのち晴れ",
        }.get(weather, weather)
        bad_mood = weather in {"阴", "雨"}
        mood_image_path = self.bad_mood_image if bad_mood else self.good_mood_image
        mood_image_uri = self._optional_image_data_uri(mood_image_path, "心情贴图")
        left_entry_illustration_uri = self._optional_image_data_uri(
            self.left_entry_illustration, "正文左侧立绘"
        )
        right_entry_illustration_uri = self._optional_image_data_uri(
            self.right_entry_illustration, "正文右侧立绘"
        )
        try:
            template = template_path.read_text(encoding="utf-8")
            font_size = self._font_size(
                len(content),
                legacy=template_path.name == DIARY_TEMPLATE_FILES["经典手账"],
            )
            image_url = await html_render(
                template,
                {
                    "content": content,
                    "date_iso": date_text,
                    "display_date": display_date,
                    "weekday": weekday,
                    "weekday_zh": weekday_zh,
                    "weather": weather,
                    "weather_display": weather_display,
                    "weather_icon": weather_icon,
                    "mood_image_uri": mood_image_uri,
                    "mood_caption": random.choice(ATRI_ONE_LINERS),
                    "mood_class": "mood-bad" if bad_mood else "mood-good",
                    "left_entry_illustration_uri": left_entry_illustration_uri,
                    "right_entry_illustration_uri": right_entry_illustration_uri,
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
            logger.info(
                "[日记] 图片渲染完成: template=%s, chars=%s",
                template_path.name,
                len(content),
            )
            return (
                self._crop_to_page_width(
                    str(image_url),
                    centered=template_path.name == DIARY_TEMPLATE_FILES["海风手记"],
                )
                if image_url
                else None
            )
        except Exception:
            logger.exception("[日记] 图片渲染失败，回退到纯文字")
            return None
