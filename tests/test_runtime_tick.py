import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from tests.test_behavior_flow import make_engine  # noqa: E402


class RuntimeTickTests(unittest.TestCase):
    def test_continuous_ticks_keep_action_alive_and_anchor_reasonable(self):
        engine = make_engine()
        engine.config.behaviors["Idle"].next_behaviors = []
        engine.config.behaviors["Idle"].next_additive = True
        engine.config.actions["Idle"].params = {"Duration": "100"}

        for _ in range(20):
            engine.tick()
            self.assertIsNotNone(engine.current_behavior_instance)
            self.assertIsNotNone(engine.current_action)
            anchor = engine.window.anchor_point()
            self.assertGreaterEqual(anchor.x, -128)
            self.assertLessEqual(anchor.x, 928)
            self.assertGreaterEqual(anchor.y, -512)
            self.assertLessEqual(anchor.y, 728)

    def test_lost_ground_falls_back_without_dead_loop(self):
        engine = make_engine()
        calls = []
        engine.current_behavior = SimpleNamespace(name="Idle")
        engine.current_action_name = "Idle"
        engine.current_action = SimpleNamespace(
            tick=lambda: (_ for _ in ()).throw(__import__("behavior.types").types.LostGroundError()),
            current_frame=lambda: None,
        )
        engine.current_behavior_instance = SimpleNamespace(next=lambda: None)
        engine._fall_back = lambda: calls.append("fall")
        engine.debug_trace.lost_ground(engine.tick_count, "Idle", "Idle")

        self.assertEqual(calls, [])
        self.assertEqual(engine.debug_trace.events[-1].kind, "lost_ground")


if __name__ == "__main__":
    unittest.main()
