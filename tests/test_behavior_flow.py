import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from behavior_engine import BehaviorEngine  # noqa: E402
from debug_trace import DebugTrace  # noqa: E402
from manual_commands import ManualCommandController  # noqa: E402
from override_controller import OverrideController  # noqa: E402
from shimeji_actions import (  # noqa: E402
    ActionDefinition,
    BehaviorDefinition,
    BehaviorReferenceDefinition,
    ShimejiConfiguration,
)


class DummyBorder:
    def isOn(self, _point):
        return False


def make_engine():
    anchor = SimpleNamespace(x=100, y=100)

    class DummyWindow:
        current_action_name = ""
        facing = -1

        def __init__(self):
            def freeze_active_ie(rect, title, ticks=240):
                provider.active_ie = SimpleNamespace(
                    left=rect.left,
                    top=rect.top,
                    right=rect.right,
                    bottom=rect.bottom,
                    visible=True,
                )
                provider.active_ie_title = title
                provider.freeze_ticks = ticks

            provider = SimpleNamespace(
                screen=SimpleNamespace(left=0, right=800, top=0, bottom=600, visible=True),
                work_area=SimpleNamespace(left=0, right=800, top=0, bottom=580, visible=True),
                active_ie=SimpleNamespace(left=200, top=100, right=600, bottom=500, visible=True),
                active_ie_title="Editor",
                freeze_active_ie=freeze_active_ie,
                floor_border=lambda ignore_separator=False: DummyBorder(),
                ceiling_border=lambda ignore_separator=False: DummyBorder(),
                wall_border=lambda look_right, ignore_separator=False: DummyBorder(),
            )
            self.runtime = SimpleNamespace(
                state_vars={},
                environment_provider=provider,
                refresh_environment=lambda: None,
                set_state_vars=lambda state_vars: setattr(self.runtime, "state_vars", dict(state_vars)),
                eval_bool=lambda value, default=True, variables=None: False if str(value).lower() == "false" else default,
                eval_value=lambda value, default=None, variables=None: value,
            )

        def anchor_point(self):
            return anchor

        def set_anchor(self, x, y):
            anchor.x = int(x)
            anchor.y = int(y)

        def set_dragging(self, _dragging):
            return

        def set_facing(self, value):
            self.facing = 1 if value > 0 else -1

        def place_from_anchor(self, *_anchor):
            return

    actions = {
        "Idle": ActionDefinition(name="Idle", action_type="stay", params={"Duration": "1"}),
        "ジャンプ": ActionDefinition(
            name="ジャンプ",
            action_type="embedded",
            class_name="com.group_finity.mascot.action.Jump",
        ),
        "IEの左に飛びつく": ActionDefinition(name="IEの左に飛びつく", action_type="stay", params={"Duration": "100"}),
        "IEの右に飛びつく": ActionDefinition(name="IEの右に飛びつく", action_type="stay", params={"Duration": "100"}),
        "Look": ActionDefinition(name="Look", action_type="stay", params={"Duration": "100"}),
        "Next": ActionDefinition(name="Next", action_type="stay", params={"Duration": "100"}),
        "Wave": ActionDefinition(name="Wave", action_type="stay", params={"Duration": "100"}),
    }
    behaviors = {
        "Idle": BehaviorDefinition(
            name="Idle",
            action_name="Idle",
            frequency=1,
            hidden=False,
            toggleable=True,
            next_additive=False,
            next_behaviors=[BehaviorReferenceDefinition(name="Next", frequency=1)],
        ),
        "Next": BehaviorDefinition(name="Next", action_name="Next", frequency=0, hidden=False, toggleable=True),
    }
    engine = object.__new__(BehaviorEngine)
    engine.window = DummyWindow()
    engine.config = ShimejiConfiguration(ROOT, {}, actions, behaviors)
    engine.debug_trace = DebugTrace(True)
    engine.override_controller = OverrideController()
    engine.manual_commands = ManualCommandController(engine)
    engine.images = {}
    engine.tick_count = 0
    engine.current_behavior = None
    engine.current_behavior_instance = None
    engine.current_action = None
    engine.current_action_name = ""
    engine.current_frame = None
    engine.current_forced = False
    engine._last_traced_action = ""
    engine.drag_active = False
    engine.mascot_dragging = False
    engine.tick_scale = 1
    engine.disabled_behaviors = set()
    return engine


class BehaviorFlowTests(unittest.TestCase):
    def test_next_behavior_switches_after_current_finishes(self):
        engine = make_engine()
        engine._set_behavior(engine.config.behaviors["Idle"], forced=False)

        engine.tick()

        self.assertEqual(engine.current_behavior.name, "Next")
        kinds = [event.kind for event in engine.debug_trace.events]
        self.assertIn("behavior_switch", kinds)
        self.assertIn("action_switch", kinds)

    def test_forced_action_can_be_inserted(self):
        engine = make_engine()

        engine.force_action("Wave")
        engine.tick()

        self.assertIsNone(engine.current_behavior)
        self.assertEqual(engine.current_action_name, "Wave")
        self.assertEqual(engine.debug_trace.events[0].kind, "forced_action")

    def test_forced_behavior_can_be_inserted(self):
        engine = make_engine()

        engine.force_behavior("Next")
        engine.tick()

        self.assertEqual(engine.current_behavior.name, "Next")
        self.assertTrue(engine.current_forced)
        self.assertEqual(engine.debug_trace.events[0].kind, "forced_behavior")

    def test_manual_command_prefers_behavior_when_conditions_pass(self):
        engine = make_engine()
        engine.config.behaviors["Wave"] = BehaviorDefinition(
            name="Wave",
            action_name="Wave",
            frequency=0,
            hidden=False,
            toggleable=True,
        )

        engine.force_manual_command("Wave")
        engine.tick()

        self.assertEqual(engine.current_behavior.name, "Wave")
        self.assertEqual(engine.debug_trace.events[0].kind, "manual_command")
        self.assertEqual(engine.debug_trace.events[0].data["mode"], "behavior")
        self.assertEqual(engine.debug_trace.events[1].kind, "forced_behavior")

    def test_manual_command_uses_safe_feedback_when_behavior_condition_fails(self):
        engine = make_engine()
        engine.config.behaviors["Wave"] = BehaviorDefinition(
            name="Wave",
            action_name="Wave",
            frequency=0,
            hidden=False,
            toggleable=True,
            conditions=["false"],
        )

        engine.force_manual_command("Wave")
        engine.tick()

        self.assertIsNone(engine.current_behavior)
        self.assertEqual(engine.current_action_name, "Look")
        self.assertEqual(engine.debug_trace.events[0].kind, "manual_command")
        self.assertEqual(engine.debug_trace.events[0].data["mode"], "feedback")
        self.assertEqual(engine.debug_trace.events[1].kind, "forced_action")

    def test_manual_ie_command_uses_nearest_original_edge_action(self):
        engine = make_engine()
        engine.window.set_anchor(0, 300)
        engine.config.behaviors["IEの右に飛びつく"] = BehaviorDefinition(
            name="IEの右に飛びつく",
            action_name="IEの右に飛びつく",
            frequency=0,
            hidden=False,
            toggleable=True,
            conditions=["false"],
        )

        engine.force_manual_command("IEの右に飛びつく")
        engine.tick()

        self.assertIsNone(engine.current_behavior)
        self.assertEqual(engine.current_action_name, "IEの左に飛びつく")
        self.assertEqual(engine.debug_trace.events[0].kind, "manual_command")
        self.assertEqual(engine.debug_trace.events[0].data["mode"], "ie_edge_action")
        self.assertEqual(engine.debug_trace.events[0].data["selected_action"], "IEの左に飛びつく")

    def test_manual_command_restores_captured_active_window(self):
        engine = make_engine()
        provider = engine.window.runtime.environment_provider
        engine.manual_commands.capture_environment()
        provider.active_ie = SimpleNamespace(left=0, top=0, right=1700, bottom=1000, visible=True)
        provider.active_ie_title = "Windows 输入体验"

        engine.force_manual_command("Wave")

        self.assertEqual(provider.active_ie.left, 200)
        self.assertEqual(provider.active_ie_title, "Editor")

    def test_external_state_records_forced_requests(self):
        engine = make_engine()

        engine.set_external_state({"forced_action": "Wave", "state_vars": {"mood": "happy"}})

        self.assertEqual(engine.window.runtime.state_vars["mood"], "happy")
        self.assertEqual(engine.debug_trace.events[0].kind, "forced_action")


if __name__ == "__main__":
    unittest.main()
