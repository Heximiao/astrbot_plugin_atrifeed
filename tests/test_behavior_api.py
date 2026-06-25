from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_CLIENT = ROOT / "desktop_client"
if str(DESKTOP_CLIENT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_CLIENT))

from behavior.api import BehaviorLayerApi, build_current_snapshot


class FakeWindow:
    facing = 1

    def anchor_point(self):
        return SimpleNamespace(x=12, y=34)


class FakeEngine:
    def __init__(self):
        self.window = FakeWindow()
        self.current_behavior = SimpleNamespace(name="idle")
        self.current_action = None
        self.current_action_name = "stand"
        self.current_forced = True
        self.mascot_dragging = False
        self.calls = []

    def available_commands(self):
        return ["idle", "stand"]

    def force_action(self, name):
        self.calls.append(("action", name))

    def force_behavior(self, name):
        self.calls.append(("behavior", name))

    def set_external_state(self, state):
        self.calls.append(("state", state))


class BehaviorApiTest(unittest.TestCase):
    def test_snapshot_hides_internal_instances(self):
        snapshot = build_current_snapshot(FakeEngine())

        self.assertEqual(
            snapshot,
            {
                "behavior": "idle",
                "action": "stand",
                "forced": True,
                "dragging": False,
                "anchor": {"x": 12, "y": 34},
                "facing": 1,
                "available_commands": ["idle", "stand"],
            },
        )

    def test_behavior_layer_api_delegates_to_engine(self):
        engine = FakeEngine()
        api = BehaviorLayerApi(engine)

        api.force_action("jump")
        api.force_behavior("idle")
        api.set_external_state(None)

        self.assertEqual(
            engine.calls,
            [
                ("action", "jump"),
                ("behavior", "idle"),
                ("state", {}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
