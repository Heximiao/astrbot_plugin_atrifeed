import base64
import mimetypes
from pathlib import Path


def image_file_to_data_uri(path: str | Path) -> str:
    """Embed a local image so remote/containerized HTML renderers can read it."""
    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"图片资源不存在: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"不支持的图片格式: {image_path.suffix or '未知'}")

    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"
