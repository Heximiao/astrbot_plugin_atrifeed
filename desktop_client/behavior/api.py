from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from behavior_engine import BehaviorEngine


class BehaviorLayerApi:
    """Thin public boundary for UI, AstrBot, and LLM product layers."""

    def __init__(self, engine: "BehaviorEngine"):
        self._engine = engine

    def force_action(self, name: str, **params):
        self._engine.force_action(name, **params)

    def force_behavior(self, name: str, **params):
        self._engine.force_behavior(name, **params)

    def set_external_state(self, state: dict[str, Any] | None):
        self._engine.set_external_state(state or {})

    def available_commands(self) -> list[str]:
        return self._engine.available_commands()

    def current_snapshot(self) -> dict[str, Any]:
        return build_current_snapshot(self._engine)


def build_current_snapshot(engine: "BehaviorEngine") -> dict[str, Any]:
    anchor = engine.window.anchor_point()
    action = _current_leaf_action(engine)
    action_name = getattr(getattr(action, "definition", None), "name", "") or engine.current_action_name
    behavior_name = getattr(engine.current_behavior, "name", None)

    return {
        "behavior": behavior_name or "",
        "action": action_name or "",
        "forced": bool(engine.current_forced),
        "dragging": bool(getattr(engine, "mascot_dragging", False)),
        "anchor": {
            "x": int(getattr(anchor, "x", 0)),
            "y": int(getattr(anchor, "y", 0)),
        },
        "facing": int(getattr(engine.window, "facing", -1)),
        "available_commands": engine.available_commands(),
    }


def _current_leaf_action(engine: "BehaviorEngine"):
    action = getattr(engine, "current_action", None)
    if action is None:
        return None
    leaf_action = getattr(engine, "_leaf_action", None)
    if leaf_action is None:
        return action
    return leaf_action(action)
