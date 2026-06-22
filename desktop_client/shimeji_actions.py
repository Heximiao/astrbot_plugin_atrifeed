from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


TAG_ACTION = "\u52d5\u4f5c"
TAG_ACTION_REF = "\u52d5\u4f5c\u53c2\u7167"
TAG_BEHAVIOR = "\u884c\u52d5"
TAG_ANIMATION = "\u30a2\u30cb\u30e1\u30fc\u30b7\u30e7\u30f3"
TAG_POSE = "\u30dd\u30fc\u30ba"
ATTR_NAME = "\u540d\u524d"
ATTR_TYPE = "\u7a2e\u985e"
ATTR_BORDER = "\u67a0"
ATTR_CONDITION = "\u6761\u4ef6"
ATTR_IMAGE = "\u753b\u50cf"
ATTR_ANCHOR = "\u57fa\u6e96\u5ea7\u6a19"
ATTR_VELOCITY = "\u79fb\u52d5\u901f\u5ea6"
ATTR_DURATION = "\u9577\u3055"
ATTR_FREQUENCY = "\u983b\u5ea6"
TYPE_BUILTIN = "\u7d44\u307f\u8fbc\u307f"
TYPE_COMPOUND = "\u8907\u5408"
SUPPORTED_TYPES = {"\u9759\u6b62", "\u79fb\u52d5", "\u56fa\u5b9a", TYPE_BUILTIN, TYPE_COMPOUND}


@dataclass
class Frame:
    image: str
    anchor: tuple[int, int]
    velocity: tuple[int, int]
    duration: int


@dataclass
class ActionRef:
    name: str
    params: dict[str, str]


@dataclass
class Animation:
    condition: str
    frames: list[Frame]


@dataclass
class Action:
    name: str
    type: str
    border: str
    frames: list[Frame]
    refs: list[ActionRef] | None = None
    animations: list[Animation] | None = None


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


def _parse_frames(asset_dir: Path, node) -> list[Frame]:
    frames = []
    for pose in node:
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
    return frames


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
        animations = []
        frames = []
        for child in node:
            if _local_name(child.tag) == TAG_ANIMATION:
                animation_frames = _parse_frames(asset_dir, child)
                if animation_frames:
                    animations.append(
                        Animation(
                            condition=_attr(child, ATTR_CONDITION, "Condition"),
                            frames=animation_frames,
                        )
                    )
                    frames.extend(animation_frames)
            elif _local_name(child.tag) == TAG_POSE:
                frames.extend(_parse_frames(asset_dir, node))
                break
        refs = []
        for child in node:
            if _local_name(child.tag) != TAG_ACTION_REF:
                continue
            ref_name = _attr(child, ATTR_NAME, "Name")
            if ref_name:
                refs.append(ActionRef(name=ref_name, params=dict(child.attrib)))
        if frames or refs or action_type == TYPE_BUILTIN:
            actions[name] = Action(
                name=name,
                type=action_type,
                border=_attr(node, ATTR_BORDER, "Border"),
                frames=frames,
                refs=refs,
                animations=animations,
            )
    return actions


def parse_behaviors(asset_dir: str | Path) -> dict[str, int]:
    asset_dir = Path(asset_dir)
    xml_path = asset_dir / "conf" / "Behavior.xml"
    if not xml_path.exists():
        return {}

    root = ET.parse(xml_path).getroot()
    behaviors: dict[str, int] = {}
    for node in root.iter():
        if _local_name(node.tag) != TAG_BEHAVIOR:
            continue
        name = _attr(node, ATTR_NAME, "Name")
        if not name:
            continue
        try:
            frequency = int(float(_attr(node, ATTR_FREQUENCY, "Frequency", default="0")))
        except ValueError:
            frequency = 0
        if frequency > 0:
            behaviors[name] = max(behaviors.get(name, 0), frequency)
    return behaviors
