import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from behavior.action_instances import (  # noqa: E402
    BaseActionInstance,
    FallActionInstance,
    JumpActionInstance,
    LookActionInstance,
    MoveActionInstance,
    SequenceActionInstance,
)
from behavior.param_normalizer import normalize_params  # noqa: E402
from shimeji_actions import ActionDefinition, AnimationDefinition, FrameDefinition  # noqa: E402


class DummyBorder:
    x = None
    y = None

    def isOn(self, _point):
        return True


class ActionParamNormalizerTests(unittest.TestCase):
    def _engine(self, anchor_x=0, anchor_y=0):
        anchor = SimpleNamespace(x=anchor_x, y=anchor_y)

        class DummyWindow:
            current_action_name = ""
            facing = -1

            def __init__(self):
                self.runtime = SimpleNamespace(
                    state_vars={},
                    eval_bool=lambda _value, default=True, variables=None: default,
                    eval_value=lambda value, default=None, variables=None: default,
                    environment_provider=SimpleNamespace(
                        cursor=SimpleNamespace(x=0, y=0, dx=0, dy=0),
                        floor_border=lambda ignore_separator=False: DummyBorder(),
                        ceiling_border=lambda ignore_separator=False: DummyBorder(),
                        wall_border=lambda look_right, ignore_separator=False: DummyBorder(),
                    ),
                )

            def anchor_point(self):
                return anchor

            def set_anchor(self, x, y):
                anchor.x = int(x)
                anchor.y = int(y)

            def set_facing(self, value):
                self.facing = 1 if value > 0 else -1

            def set_dragging(self, _dragging):
                return

        engine = SimpleNamespace(
            tick_count=0,
            tick_scale=1,
            config=SimpleNamespace(constants={}, actions={}),
            window=DummyWindow(),
            _resolve_param_values=lambda params, _local_vars: normalize_params(params),
            _resolve_name=lambda name: name,
            _instantiate_action=lambda definition, params=None: BaseActionInstance(engine, definition, params or {}),
        )
        return engine

    def _frame_action(self, cls, params):
        engine = self._engine()
        definition = ActionDefinition(
            name="action",
            action_type="move",
            params=params,
            animations=[
                AnimationDefinition(
                    condition=None,
                    frames=[FrameDefinition(image="", anchor=(64, 128), velocity=(0, 0), duration=1)],
                )
            ],
        )
        return cls(engine, definition, {})

    def test_normalizer_preserves_raw_keys_and_adds_canonical_keys(self):
        params = normalize_params({"目的地X": 12, "目的地Y": 34, "速度": 9})

        self.assertEqual(params["目的地X"], 12)
        self.assertEqual(params["TargetX"], 12)
        self.assertEqual(params["TargetY"], 34)
        self.assertEqual(params["VelocityParam"], 9)

    def test_move_reads_canonical_target_params_from_japanese_keys(self):
        action = self._frame_action(MoveActionInstance, {"目的地X": 10, "目的地Y": 20})

        self.assertEqual(action.param_value("TargetX"), 10)
        self.assertEqual(action.param_value("TargetY"), 20)

    def test_jump_reads_target_and_velocity_params_from_japanese_keys(self):
        action = self._frame_action(JumpActionInstance, {"目的地X": 10, "目的地Y": 20, "速度": 7})

        self.assertEqual(action.param_value("TargetX"), 10)
        self.assertEqual(action.param_value("TargetY"), 20)
        self.assertEqual(action.param_value("VelocityParam"), 7)

    def test_fall_reads_physics_params_from_japanese_keys(self):
        action = self._frame_action(
            FallActionInstance,
            {"初速X": 3, "初速Y": 4, "重力": 5, "空気抵抗X": 0.2, "空気抵抗Y": 0.3},
        )

        self.assertEqual(action.vx, 3)
        self.assertEqual(action.vy, 4)
        self.assertEqual(action.param_value("Gravity"), 5)
        self.assertEqual(action.param_value("ResistanceX"), 0.2)
        self.assertEqual(action.param_value("ResistanceY"), 0.3)

    def test_sequence_reads_loop_from_japanese_key(self):
        engine = self._engine()
        definition = ActionDefinition(name="sequence", action_type="sequence", params={"繰り返し": "true"})
        action = SequenceActionInstance(engine, definition, {})

        self.assertTrue(action.loop)

    def test_look_reads_direction_from_japanese_key(self):
        action = self._frame_action(LookActionInstance, {"右向き": True})

        action.tick()

        self.assertEqual(action.engine.window.facing, 1)


if __name__ == "__main__":
    unittest.main()
