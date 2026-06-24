from __future__ import annotations


PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "TargetX": ("目的地X",),
    "TargetY": ("目的地Y",),
    "Duration": ("長さ",),
    "Loop": ("繰り返し",),
    "LookRight": ("右向き",),
    "InitialVX": ("初速X",),
    "InitialVY": ("初速Y",),
    "Gravity": ("重力",),
    "ResistanceX": ("空気抵抗X", "RegistanceX"),
    "ResistanceY": ("空気抵抗Y", "RegistanceY"),
    "Draggable": ("ドラッグ可能",),
    "Condition": ("条件",),
    "OffsetX": ("オフセットX",),
    "OffsetY": ("オフセットY",),
    "VelocityParam": ("速度",),
}


ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in PARAM_ALIASES.items()
    for alias in aliases
}


def canonical_param_name(name: str) -> str:
    return ALIAS_TO_CANONICAL.get(name, name)


def normalize_params(params: dict[str, object]) -> dict[str, object]:
    normalized = dict(params)
    for key, value in params.items():
        canonical = canonical_param_name(key)
        if canonical not in normalized:
            normalized[canonical] = value
    return normalized
