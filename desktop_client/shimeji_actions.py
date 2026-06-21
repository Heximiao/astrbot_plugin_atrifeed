from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


TAG_ACTION = "\u52d5\u4f5c"
TAG_POSE = "\u30dd\u30fc\u30ba"
ATTR_NAME = "\u540d\u524d"
ATTR_TYPE = "\u7a2e\u985e"
ATTR_BORDER = "\u67a0"
ATTR_IMAGE = "\u753b\u50cf"
ATTR_ANCHOR = "\u57fa\u6e96\u5ea7\u6a19"
ATTR_VELOCITY = "\u79fb\u52d5\u901f\u5ea6"
ATTR_DURATION = "\u9577\u3055"
SUPPORTED_TYPES = {"\u9759\u6b62", "\u79fb\u52d5", "\u56fa\u5b9a"}


@dataclass
class Frame:
    image: str
    anchor: tuple[int, int]
    velocity: tuple[int, int]
    duration: int


@dataclass
class Action:
    name: str
    type: str
    border: str
    frames: list[Frame]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(node, *names, default=""):
    for name in names:
        if name in node.attrib:
            return node.attrib[name]
    return default


def _pair(value: str, default=(0, 0)) -> tuple[int, int]:
    if not value:
        return default
    parts = value.replace("\uff0c", ",").split(",")
    if len(parts) < 2:
        return default
    try:
        return int(float(parts[0])), int(float(parts[1]))
    except ValueError:
        return default


def _image_path(asset_dir: Path, value: str) -> str:
    normalized = value.replace("\\", "/")
    return str(asset_dir.joinpath(*normalized.split("/")))


def parse_actions(asset_dir: str | Path) -> dict[str, Action]:
    asset_dir = Path(asset_dir)
    xml_path = asset_dir / "conf" / "Actions.xml"
    if not xml_path.exists():
        return {}

    root = ET.parse(xml_path).getroot()
    actions: dict[str, Action] = {}
    for node in root.iter():
        if _local_name(node.tag) != TAG_ACTION:
            continue
        name = _attr(node, ATTR_NAME, "Name")
        action_type = _attr(node, ATTR_TYPE, "Type")
        if not name or action_type not in SUPPORTED_TYPES:
            continue
        frames = []
        for pose in node.iter():
            if _local_name(pose.tag) != TAG_POSE:
                continue
            image = _attr(pose, ATTR_IMAGE, "Image")
            if not image:
                continue
            frames.append(
                Frame(
                    image=_image_path(asset_dir, image),
                    anchor=_pair(_attr(pose, ATTR_ANCHOR, "Anchor"), (64, 128)),
                    velocity=_pair(_attr(pose, ATTR_VELOCITY, "Velocity"), (0, 0)),
                    duration=max(1, _pair(_attr(pose, ATTR_DURATION, "Duration", default="6,0"), (6, 0))[0]),
                )
            )
        if frames:
            actions[name] = Action(
                name=name,
                type=action_type,
                border=_attr(node, ATTR_BORDER, "Border"),
                frames=frames,
            )
    return actions
