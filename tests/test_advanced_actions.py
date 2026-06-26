import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from behavior.action_instances import (  # noqa: E402
    FallWithIEActionInstance,
    MoveWithTurnActionInstance,
    ThrowIEActionInstance,
    UnsupportedAdvancedActionInstance,
    WalkWithIEActionInstance,
)
from behavior_engine import BehaviorEngine  # noqa: E402
from behavior.param_normalizer import normalize_params  # noqa: E402
from environment_provider import Rect  # noqa: E402
from manual_commands import ManualCommandController  # noqa: E402
from menu_labels import grouped_commands, manual_action_params, menu_label  # noqa: E402
from shimeji_actions import ActionDefinition, AnimationDefinition, BehaviorDefinition, FrameDefinition  # noqa: E402


class DummyWindow:
    current_action_name = ""

    def __init__(self, anchor_x=0, anchor_y=0, facing=-1, active_ie=None):
        self.anchor = SimpleNamespace(x=anchor_x, y=anchor_y)
        self.facing = facing
        self.runtime = SimpleNamespace(
            state_vars={},
            eval_bool=lambda _value, default=True, variables=None: default,
            environment_provider=DummyEnvironmentProvider(self, active_ie or Rect()),
        )

    def anchor_point(self):
        return SimpleNamespace(x=self.anchor.x, y=self.anchor.y)

    def set_anchor(self, x, y):
        self.anchor.x = int(round(x))
        self.anchor.y = int(round(y))

    def set_facing(self, value):
        self.facing = 1 if value > 0 else -1


class DummyEnvironmentProvider:
    def __init__(self, window, active_ie):
        self.window = window
        self.active_ie = active_ie
        self.active_ie_title = "Editor"
        self.work_area = Rect(left=0, top=0, right=800, bottom=580)
        self.move_calls = []

    def floor_border(self, ignore_separator=False):
        anchor = self.window.anchor_point()
        if self.active_ie.topBorder.isOn(anchor):
            return self.active_ie.topBorder
        return self.work_area.bottomBorder

    def ceiling_border(self, ignore_separator=False):
        return self.work_area.topBorder

    def wall_border(self, look_right, ignore_separator=False):
        return self.work_area.rightBorder if look_right else self.work_area.leftBorder

    def freeze_active_ie(self, rect, title, ticks=4):
        self.active_ie.update_from(rect)
        self.active_ie_title = title

    def move_active_ie(self, left, top):
        self.move_calls.append((left, top))
        moved = self.active_ie.copy()
        moved.left = left
        moved.top = top
        moved.right = left + self.active_ie.width
        moved.bottom = top + self.active_ie.height
        self.active_ie.update_from(moved)
        return True


def frame(velocity=(0, 0), duration=6):
    return FrameDefinition(image="", anchor=(64, 128), velocity=velocity, duration=duration)


def action(name, class_name, params=None, animations=None, border=""):
    return ActionDefinition(
        name=name,
        action_type="embedded",
        border=border,
        class_name=f"com.group_finity.mascot.action.{class_name}",
        params=params or {},
        animations=animations or [AnimationDefinition(condition=None, frames=[frame()])],
    )


def engine(window):
    eng = SimpleNamespace()
    eng.tick_count = 0
    eng.tick_scale = 1
    eng.window = window
    eng.config = SimpleNamespace(constants={})

    def resolve_params(params, _local_vars):
        resolved = {}
        for key, value in params.items():
            try:
                number = float(value)
                value = int(number) if number.is_integer() else number
            except (TypeError, ValueError):
                pass
            resolved[key] = value
        return normalize_params(resolved)

    eng._resolve_param_values = resolve_params
    eng.mascot_dragging = False
    return eng


class AdvancedActionTests(unittest.TestCase):
    def test_walk_with_ie_moves_cached_active_window_with_mascot(self):
        active_ie = Rect(left=100, top=100, right=300, bottom=240)
        win = DummyWindow(anchor_x=100, anchor_y=304, facing=1, active_ie=active_ie)
        eng = engine(win)
        instance = WalkWithIEActionInstance(
            eng,
            action(
                "walk-ie",
                "WalkWithIE",
                params={"IeOffsetX": "0", "IeOffsetY": "-64", "TargetX": "112"},
                animations=[AnimationDefinition(condition=None, frames=[frame(velocity=(4, 0))])],
                border="Floor",
            ),
            {},
        )

        finished = instance.tick()

        self.assertFalse(finished)
        self.assertEqual((win.anchor.x, win.anchor.y), (104, 304))
        self.assertEqual((active_ie.left, active_ie.top, active_ie.right, active_ie.bottom), (104, 100, 304, 240))

    def test_fall_with_ie_lands_on_active_window_top(self):
        active_ie = Rect(left=100, top=100, right=300, bottom=240)
        win = DummyWindow(anchor_x=150, anchor_y=50, facing=1, active_ie=active_ie)
        eng = engine(win)
        instance = FallWithIEActionInstance(
            eng,
            action("fall-ie", "FallWithIE", params={"Gravity": "80"}),
            {},
        )

        finished = instance.tick()

        self.assertTrue(finished)
        self.assertEqual((win.anchor.x, win.anchor.y), (150, 100))

    def test_move_with_turn_uses_turn_phase_before_moving(self):
        win = DummyWindow(anchor_x=0, anchor_y=0, facing=-1)
        eng = engine(win)
        instance = MoveWithTurnActionInstance(
            eng,
            action(
                "turn-move",
                "MoveWithTurn",
                params={"TargetX": "10"},
                animations=[
                    AnimationDefinition(condition=None, frames=[frame(velocity=(5, 0), duration=6)]),
                    AnimationDefinition(condition=None, frames=[frame(velocity=(0, 0), duration=1)]),
                ],
            ),
            {},
        )

        self.assertFalse(instance.tick())
        self.assertEqual((win.facing, win.anchor.x), (1, 0))

        eng.tick_count = 1
        self.assertFalse(instance.tick())
        self.assertEqual(win.anchor.x, 5)

    def test_throw_ie_moves_real_active_window_adapter(self):
        active_ie = Rect(left=100, top=100, right=300, bottom=240)
        win = DummyWindow(facing=1, active_ie=active_ie)
        eng = engine(win)
        instance = ThrowIEActionInstance(
            eng,
            action("throw-ie", "ThrowIE", params={"InitialVX": "32", "InitialVY": "-10", "Gravity": "0.5"}),
            {},
        )

        self.assertFalse(instance.tick())

        provider = win.runtime.environment_provider
        self.assertEqual(provider.move_calls, [(132, 90)])
        self.assertEqual((active_ie.left, active_ie.top, active_ie.right, active_ie.bottom), (132, 90, 332, 230))

    def test_engine_instantiates_throw_ie_action(self):
        eng = engine(DummyWindow())
        definition = action("throw-ie", "ThrowIE")

        instance = BehaviorEngine._instantiate_embedded(eng, definition, {})

        self.assertIsInstance(instance, ThrowIEActionInstance)

    def test_unimplemented_advanced_actions_use_explicit_fallback(self):
        eng = engine(DummyWindow())
        definition = action("breed", "Breed")

        instance = BehaviorEngine._instantiate_embedded(eng, definition, {})

        self.assertIsInstance(instance, UnsupportedAdvancedActionInstance)
        self.assertEqual(instance.fallback_reason, "unsupported_advanced_action")

    def test_throw_ie_menu_labels_are_chinese(self):
        self.assertEqual(menu_label("IEを右に投げる"), "把IE窗口扔到右边")
        self.assertEqual(menu_label("走ってIEを左に投げる"), "跑过去把IE窗口扔到左边")

    def test_menu_commands_are_grouped_for_manual_menu(self):
        groups = grouped_commands({"振り向く", "ジャンプ", "壁から落ちる", "つままれる", "Custom"})

        self.assertEqual(groups[0], ("1. 任何时候都能点", ["振り向く"]))
        self.assertEqual(groups[1], ("2. 需要环境条件", ["壁から落ちる"]))
        self.assertEqual(groups[2], ("3. 需要参数才有意义", ["ジャンプ"]))
        self.assertEqual(groups[3], ("4. 其他动作", ["Custom"]))

    def test_manual_jump_params_use_forward_target(self):
        anchor = SimpleNamespace(x=200, y=300)
        work_area = SimpleNamespace(left=0, right=800, visible=True)

        params = manual_action_params("ジャンプ", anchor, 1, work_area)

        self.assertEqual(params, {"TargetX": 320, "TargetY": 180})

    def test_manual_command_falls_back_to_action_when_same_named_behavior_condition_fails(self):
        eng = engine(DummyWindow())
        eng.config.actions = {"IEを右に投げる": action("IEを右に投げる", "ThrowIE")}
        eng.config.behaviors = {
            "IEを右に投げる": BehaviorDefinition(
                name="IEを右に投げる",
                action_name="IEを右に投げる",
                frequency=1,
                hidden=False,
                toggleable=True,
                conditions=["false"],
            )
        }
        eng._resolve_name = lambda name: name
        eng._conditions_pass = lambda conditions, params: False
        pushed = []
        eng.override_controller = SimpleNamespace(push_action=lambda name: pushed.append(name))
        eng._trace = lambda: SimpleNamespace(
            forced_action=lambda tick, name: None,
            record=lambda *args, **kwargs: None,
        )

        ManualCommandController(eng).force("IEを右に投げる")

        self.assertEqual(pushed, ["IEを右に投げる"])


if __name__ == "__main__":
    unittest.main()
