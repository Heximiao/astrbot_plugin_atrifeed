import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from behavior_engine import BehaviorEngine  # noqa: E402
from debug_trace import DebugTrace  # noqa: E402
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
            provider = SimpleNamespace(
                screen=SimpleNamespace(left=0, right=800, top=0, bottom=600, visible=True),
                work_area=SimpleNamespace(left=0, right=800, top=0, bottom=580, visible=True),
                floor_border=lambda ignore_separator=False: DummyBorder(),
                ceiling_border=lambda ignore_separator=False: DummyBorder(),
                wall_border=lambda look_right, ignore_separator=False: DummyBorder(),
            )
            self.runtime = SimpleNamespace(
                state_vars={},
                environment_provider=provider,
                refresh_environment=lambda: None,
                set_state_vars=lambda state_vars: setattr(self.runtime, "state_vars", dict(state_vars)),
                eval_bool=lambda _value, default=True, variables=None: default,
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

    def test_external_state_records_forced_requests(self):
        engine = make_engine()

        engine.set_external_state({"forced_action": "Wave", "state_vars": {"mood": "happy"}})

        self.assertEqual(engine.window.runtime.state_vars["mood"], "happy")
        self.assertEqual(engine.debug_trace.events[0].kind, "forced_action")


if __name__ == "__main__":
    unittest.main()
