import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from behavior.action_instances import BaseActionInstance  # noqa: E402
from behavior.behavior_instances import UserBehaviorInstance  # noqa: E402
from debug_trace import DebugTrace  # noqa: E402
from drag_controller import DragController  # noqa: E402
from environment_provider import PointState  # noqa: E402
from shimeji_actions import ActionDefinition, BehaviorDefinition, ShimejiConfiguration  # noqa: E402


class DragFlowTests(unittest.TestCase):
    def _engine(self, draggable=True):
        action = ActionDefinition(
            name="Idle",
            action_type="stay",
            params={"Draggable": "true" if draggable else "false"},
        )
        drag_action = ActionDefinition(name="Dragged", action_type="stay")
        thrown_action = ActionDefinition(name="Thrown", action_type="stay")
        behavior = BehaviorDefinition(name="Idle", action_name="Idle", frequency=1, hidden=False, toggleable=True)
        drag_behavior = BehaviorDefinition(name="Dragged", action_name="Dragged", frequency=0, hidden=False, toggleable=False)
        thrown_behavior = BehaviorDefinition(name="Thrown", action_name="Thrown", frequency=0, hidden=False, toggleable=False)
        engine = SimpleNamespace()
        engine.tick_count = 0
        engine.config = ShimejiConfiguration(
            ROOT,
            {},
            {"Idle": action, "Dragged": drag_action, "Thrown": thrown_action},
            {"Idle": behavior, "Dragged": drag_behavior, "Thrown": thrown_behavior},
        )
        engine.window = SimpleNamespace(
            runtime=SimpleNamespace(
                state_vars={},
                eval_bool=lambda _value, default=True, variables=None: default,
            ),
            current_action_name="Idle",
            set_dragging=lambda _dragging: None,
        )
        engine.debug_trace = DebugTrace(True)
        engine._resolve_param_values = lambda params, _local_vars: dict(params)
        engine.current_action = BaseActionInstance(engine, action, {})
        engine.current_action_name = "Idle"
        engine.mascot_dragging = False
        engine.drag_active = False
        engine._behavior_name = lambda *names: next((name for name in names if name in engine.config.behaviors), None)
        engine._set_behavior_calls = []
        engine._set_behavior = lambda next_behavior, forced: engine._set_behavior_calls.append((next_behavior.name, forced))
        return engine, behavior, action

    def test_non_draggable_action_does_not_enter_dragged(self):
        engine, behavior, action = self._engine(draggable=False)
        instance = UserBehaviorInstance(engine, behavior, action)

        instance.mouse_pressed()

        self.assertEqual(engine._set_behavior_calls, [])
        self.assertEqual(engine.debug_trace.events, [])

    def test_release_without_real_dragging_does_not_throw(self):
        engine, behavior, action = self._engine(draggable=True)
        instance = UserBehaviorInstance(engine, behavior, action)

        instance.mouse_released()

        self.assertEqual(engine._set_behavior_calls, [])

    def test_drag_release_clamps_instant_throw_velocity(self):
        cursor = PointState()
        provider = SimpleNamespace(cursor=cursor)
        engine = SimpleNamespace(
            on_mouse_press=lambda: None,
            on_mouse_release=lambda: None,
            sync_drag_to_cursor=lambda: None,
        )
        window = SimpleNamespace(runtime=SimpleNamespace(environment_provider=provider), engine=engine)
        controller = DragController(window)

        controller.start(SimpleNamespace(x=0, y=0, x_root=100, y_root=100))
        controller.drag(SimpleNamespace(x=0, y=0, x_root=180, y_root=40))
        controller.end(None)

        self.assertEqual(cursor.dx, 48)
        self.assertEqual(cursor.dy, -48)


if __name__ == "__main__":
    unittest.main()
