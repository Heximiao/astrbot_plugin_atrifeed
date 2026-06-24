from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET


TYPE_STAY = "stay"
TYPE_MOVE = "move"
TYPE_ANIMATE = "animate"
TYPE_EMBEDDED = "embedded"
TYPE_SEQUENCE = "sequence"
TYPE_SELECT = "select"

TYPE_BUILTIN = TYPE_EMBEDDED
TYPE_COMPOUND = TYPE_SEQUENCE

TAG_ALIASES = {
    "constant": {"定数", "Constant"},
    "action": {"動作", "Action"},
    "action_ref": {"動作参照", "ActionReference"},
    "animation": {"アニメーション", "Animation"},
    "pose": {"ポーズ", "Pose"},
    "behavior": {"行動", "Behavior"},
    "behavior_ref": {"行動参照", "BehaviorReference"},
    "next_behavior_list": {"次の行動リスト", "NextBehavior"},
    "condition": {"条件", "Condition"},
}

ATTR_ALIASES = {
    "name": {"名前", "Name"},
    "type": {"種類", "Type"},
    "class": {"クラス", "Class"},
    "border": {"枠", "BorderType", "Border"},
    "condition": {"条件", "Condition"},
    "image": {"画像", "Image"},
    "anchor": {"基準座標", "ImageAnchor", "Anchor"},
    "velocity": {"移動速度", "Velocity"},
    "duration": {"長さ", "Duration"},
    "frequency": {"頻度", "Frequency"},
    "action": {"動作", "Action"},
    "hidden": {"非表示", "Hidden"},
    "toggleable": {"トグル可能", "Toggleable"},
    "add": {"追加", "Add"},
    "value": {"値", "Value"},
}

TYPE_ALIASES = {
    "静止": TYPE_STAY,
    "Stay": TYPE_STAY,
    "移動": TYPE_MOVE,
    "Move": TYPE_MOVE,
    "固定": TYPE_ANIMATE,
    "Animate": TYPE_ANIMATE,
    "組み込み": TYPE_EMBEDDED,
    "Embedded": TYPE_EMBEDDED,
    "複合": TYPE_SEQUENCE,
    "Sequence": TYPE_SEQUENCE,
    "選択": TYPE_SELECT,
    "Select": TYPE_SELECT,
}


@dataclass
class FrameDefinition:
    image: str
    anchor: tuple[int, int]
    velocity: tuple[int, int]
    duration: int


@dataclass
class AnimationDefinition:
    condition: str | None
    frames: list[FrameDefinition]

    @property
    def duration(self) -> int:
        return sum(frame.duration for frame in self.frames) or 1


@dataclass
class ActionCallDefinition:
    action_name: str | None = None
    inline_action: "ActionDefinition | None" = None
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class ActionDefinition:
    name: str
    action_type: str
    border: str = ""
    class_name: str = ""
    params: dict[str, str] = field(default_factory=dict)
    animations: list[AnimationDefinition] = field(default_factory=list)
    children: list[ActionCallDefinition] = field(default_factory=list)

    @property
    def type(self) -> str:
        return self.action_type

    @property
    def frames(self) -> list[FrameDefinition]:
        frames: list[FrameDefinition] = []
        for animation in self.animations:
            frames.extend(animation.frames)
        return frames

    @property
    def refs(self) -> list[ActionCallDefinition]:
        return self.children


@dataclass
class BehaviorReferenceDefinition:
    name: str
    frequency: int
    conditions: list[str] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class BehaviorDefinition:
    name: str
    action_name: str
    frequency: int
    hidden: bool
    toggleable: bool
    conditions: list[str] = field(default_factory=list)
    params: dict[str, str] = field(default_factory=dict)
    next_additive: bool = True
    next_behaviors: list[BehaviorReferenceDefinition] = field(default_factory=list)


@dataclass
class ShimejiConfiguration:
    asset_dir: Path
    constants: dict[str, str]
    actions: dict[str, ActionDefinition]
    behaviors: dict[str, BehaviorDefinition]


def parse_configuration(asset_dir: str | Path, action_file: str = "Actions.xml", behavior_file: str = "Behavior.xml") -> ShimejiConfiguration:
    asset_dir = Path(asset_dir)
    action_root = ET.parse(asset_dir / "conf" / action_file).getroot()
    behavior_root = ET.parse(asset_dir / "conf" / behavior_file).getroot()
    constants = _parse_constants(action_root)
    behaviors = _parse_behaviors(behavior_root)
    actions = _parse_actions(asset_dir, action_root)
    return ShimejiConfiguration(asset_dir=asset_dir, constants=constants, actions=actions, behaviors=behaviors)


def parse_actions(asset_dir: str | Path) -> dict[str, ActionDefinition]:
    return parse_configuration(asset_dir).actions


def parse_behaviors(asset_dir: str | Path) -> dict[str, BehaviorDefinition]:
    return parse_configuration(asset_dir).behaviors


def _parse_constants(root) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in root.iter():
        if _matches(node.tag, "constant"):
            name = _attr(node, "name")
            value = _attr(node, "value")
            if name:
                constants[name] = value
    return constants


def _parse_actions(asset_dir: Path, root) -> dict[str, ActionDefinition]:
    actions: dict[str, ActionDefinition] = {}
    for node in root.iter():
        if not _matches(node.tag, "action"):
            continue
        definition = _parse_action_definition(asset_dir, node)
        if definition.name:
            actions[definition.name] = definition
    return actions


def _parse_action_definition(asset_dir: Path, node) -> ActionDefinition:
    raw_type = _attr(node, "type")
    action_type = TYPE_ALIASES.get(raw_type, raw_type.lower() if raw_type else TYPE_STAY)
    params = dict(node.attrib)
    definition = ActionDefinition(
        name=_attr(node, "name"),
        action_type=action_type,
        border=_attr(node, "border"),
        class_name=_attr(node, "class"),
        params=params,
    )
    for child in node:
        if _matches(child.tag, "animation"):
            definition.animations.append(_parse_animation(asset_dir, child))
        elif _matches(child.tag, "pose"):
            definition.animations.append(_parse_animation(asset_dir, node))
            break
        elif _matches(child.tag, "action_ref"):
            definition.children.append(
                ActionCallDefinition(
                    action_name=_attr(child, "name"),
                    params=dict(child.attrib),
                )
            )
        elif _matches(child.tag, "action"):
            definition.children.append(
                ActionCallDefinition(
                    inline_action=_parse_action_definition(asset_dir, child),
                    params=dict(child.attrib),
                )
            )
    return definition


def _parse_animation(asset_dir: Path, node) -> AnimationDefinition:
    frames: list[FrameDefinition] = []
    for pose in node:
        if not _matches(pose.tag, "pose"):
            continue
        image = _image_path(asset_dir, _attr(pose, "image"))
        if not image:
            continue
        frames.append(
            FrameDefinition(
                image=image,
                anchor=_pair(_attr(pose, "anchor"), (64, 128)),
                velocity=_pair(_attr(pose, "velocity"), (0, 0)),
                duration=max(1, _pair(_attr(pose, "duration", default="6,0"), (6, 0))[0]),
            )
        )
    return AnimationDefinition(condition=_attr(node, "condition") or None, frames=frames)


def _parse_behaviors(root) -> dict[str, BehaviorDefinition]:
    behaviors: dict[str, BehaviorDefinition] = {}
    _walk_behavior_container(root, [], behaviors)
    return behaviors


def _walk_behavior_container(node, inherited_conditions: list[str], target: dict[str, BehaviorDefinition]):
    for child in node:
        if _matches(child.tag, "condition"):
            next_conditions = list(inherited_conditions)
            condition = _attr(child, "condition")
            if condition:
                next_conditions.append(condition)
            _walk_behavior_container(child, next_conditions, target)
        elif _matches(child.tag, "behavior"):
            definition = _parse_behavior_definition(child, inherited_conditions)
            if definition.name:
                target[definition.name] = definition
        else:
            _walk_behavior_container(child, inherited_conditions, target)


def _parse_behavior_definition(node, inherited_conditions: list[str]) -> BehaviorDefinition:
    params = dict(node.attrib)
    name = _attr(node, "name")
    conditions = [condition for condition in inherited_conditions if condition]
    own_condition = _attr(node, "condition")
    if own_condition:
        conditions.append(own_condition)
    frequency = _int_value(_attr(node, "frequency"), 0)
    next_additive = True
    next_behaviors: list[BehaviorReferenceDefinition] = []
    for child in node:
        if not _matches(child.tag, "next_behavior_list"):
            continue
        next_additive = _bool_value(_attr(child, "add"), True)
        next_behaviors.extend(_parse_next_behaviors(child, []))
    return BehaviorDefinition(
        name=name,
        action_name=_attr(node, "action") or name,
        frequency=frequency,
        hidden=_bool_value(_attr(node, "hidden"), False),
        toggleable=False if name in {"Fall", "Dragged", "Thrown", "落下する", "ドラッグされる", "投げられる"} else _bool_value(_attr(node, "toggleable"), True),
        conditions=conditions,
        params=params,
        next_additive=next_additive,
        next_behaviors=next_behaviors,
    )


def _parse_next_behaviors(node, inherited_conditions: list[str]) -> list[BehaviorReferenceDefinition]:
    result: list[BehaviorReferenceDefinition] = []
    for child in node:
        if _matches(child.tag, "condition"):
            conditions = list(inherited_conditions)
            condition = _attr(child, "condition")
            if condition:
                conditions.append(condition)
            result.extend(_parse_next_behaviors(child, conditions))
        elif _matches(child.tag, "behavior_ref"):
            params = dict(child.attrib)
            own_condition = _attr(child, "condition")
            conditions = list(inherited_conditions)
            if own_condition:
                conditions.append(own_condition)
            result.append(
                BehaviorReferenceDefinition(
                    name=_attr(child, "name"),
                    frequency=_int_value(_attr(child, "frequency"), 0),
                    conditions=conditions,
                    params=params,
                )
            )
    return result


def _matches(tag: str, alias_key: str) -> bool:
    local = tag.rsplit("}", 1)[-1]
    return local in TAG_ALIASES[alias_key]


def _attr(node, alias_key: str, default: str = "") -> str:
    for alias in ATTR_ALIASES[alias_key]:
        if alias in node.attrib:
            return node.attrib[alias]
    return default


def _pair(value: str, default=(0, 0)) -> tuple[int, int]:
    if not value:
        return default
    parts = value.replace("，", ",").split(",")
    if len(parts) < 2:
        return default
    try:
        return int(float(parts[0])), int(float(parts[1]))
    except ValueError:
        return default


def _image_path(asset_dir: Path, value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("\\", "/").lstrip("/")
    return str(asset_dir.joinpath(*normalized.split("/")))


def _int_value(value: str, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bool_value(value: str, default: bool) -> bool:
    if value is None or value == "":
        return default
    return str(value).lower() == "true"
