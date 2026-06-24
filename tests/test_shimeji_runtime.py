import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import random


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_client"))

from shimeji_actions import parse_configuration  # noqa: E402
from shimeji_expression import ExpressionRuntime  # noqa: E402
from behavior_engine import BehaviorEngine  # noqa: E402
from behavior_engine import BaseActionInstance  # noqa: E402
from shimeji_actions import ActionDefinition  # noqa: E402


class DummyBorder:
    def __init__(self, result=False):
        self.result = result

    def isOn(self, _point):
        return self.result


class DummyStateProvider:
    def mascot_proxy(self):
        return SimpleNamespace(
            anchor=SimpleNamespace(x=100, y=200),
            lookRight=True,
            totalCount=3,
            environment=SimpleNamespace(
                workArea=SimpleNamespace(left=0, right=800, width=800, top=0, bottom=600, height=600),
                screen=SimpleNamespace(width=800, height=600),
                activeIE=SimpleNamespace(
                    left=100,
                    right=300,
                    width=200,
                    top=50,
                    bottom=200,
                    height=150,
                    visible=True,
                    topBorder=DummyBorder(False),
                    bottomBorder=DummyBorder(False),
                    leftBorder=DummyBorder(False),
                    rightBorder=DummyBorder(False),
                ),
                cursor=SimpleNamespace(x=150, y=220, dx=5, dy=7),
                floor=DummyBorder(True),
                ceiling=DummyBorder(False),
                wall=DummyBorder(False),
            ),
        )

    def action_proxy(self):
        return SimpleNamespace(name="test")


class DummyEnvProvider:
    pass


class ParseTests(unittest.TestCase):
    def test_parse_current_japanese_config(self):
        config = parse_configuration(ROOT / "pic" / "atri_pet")
        self.assertIn("落下する", config.actions)
        self.assertIn("ドラッグされる", config.behaviors)
        self.assertEqual(config.actions["落下する"].action_type, "sequence")
        self.assertGreaterEqual(len(config.actions["落下する"].children), 2)

    def test_parse_english_reference_config(self):
        config = parse_configuration(ROOT.parent / "ATRI_bot", action_file="actions.xml", behavior_file="behaviors.xml")
        self.assertIn("Fall", config.actions)
        self.assertIn("Dragged", config.behaviors)
        self.assertEqual(config.actions["Fall"].action_type, "sequence")

    def test_system_behaviors_have_actions(self):
        config = parse_configuration(ROOT / "pic" / "atri_pet")
        for name in ("落下する", "ドラッグされる", "投げられる"):
            self.assertIn(name, config.behaviors)
            self.assertIn(name, config.actions)


class EngineNameResolutionTests(unittest.TestCase):
    def test_legacy_names_map_to_current_behavior_names(self):
        engine = object.__new__(BehaviorEngine)
        engine.config = parse_configuration(ROOT / "pic" / "atri_pet")
        self.assertEqual(engine._resolve_name("idle"), "立ってボーっとする")
        self.assertEqual(engine._resolve_name("fall"), "落下する")
        self.assertEqual(engine._resolve_name("drag"), "ドラッグされる")
        self.assertEqual(engine._resolve_name("thrown"), "投げられる")

    def test_system_fall_actions_do_not_loop(self):
        engine = object.__new__(BehaviorEngine)
        engine.config = parse_configuration(ROOT / "pic" / "atri_pet")
        engine.tick_count = 0
        engine.window = SimpleNamespace(
            runtime=SimpleNamespace(
                state_vars={},
                eval_value=lambda _value, default=None, variables=None: 0,
            )
        )

        fall = engine._instantiate_action(engine.config.actions["落下する"], {})
        thrown = engine._instantiate_action(engine.config.actions["投げられる"], {})

        self.assertFalse(fall.loop)
        self.assertFalse(thrown.loop)


class EngineSafetyTests(unittest.TestCase):
    def _make_engine(self):
        engine = object.__new__(BehaviorEngine)
        engine.config = parse_configuration(ROOT / "pic" / "atri_pet")
        engine.override_controller = SimpleNamespace(push_behavior=lambda *args, **kwargs: None, push_action=lambda *args, **kwargs: None)
        engine.images = {}
        engine.tick_count = 0
        engine.current_behavior = None
        engine.current_action = None
        engine.current_action_name = ""
        engine.current_frame = None
        engine.current_forced = False
        engine.drag_active = False
        engine.mascot_dragging = False
        engine.disabled_behaviors = set()

        anchor = SimpleNamespace(x=100, y=100)

        class DummyWindow:
            current_action_name = ""
            facing = -1

            def __init__(self):
                self.runtime = SimpleNamespace(
                    environment_provider=SimpleNamespace(
                        screen=SimpleNamespace(left=0, right=800, top=0, bottom=600, visible=True),
                        work_area=SimpleNamespace(left=0, right=800, top=0, bottom=580, visible=True),
                    )
                )

            def anchor_point(self):
                return anchor

            def set_anchor(self, x, y):
                anchor.x = int(x)
                anchor.y = int(y)

            def set_dragging(self, _dragging):
                return

        engine.window = DummyWindow()
        return engine, anchor

    def test_release_without_dragging_does_not_throw(self):
        engine, _anchor = self._make_engine()
        called = []
        engine._set_behavior = lambda behavior, forced: called.append((behavior.name, forced))
        engine.on_mouse_release()
        self.assertEqual(called, [])

    def test_recover_if_out_of_bounds_resets_to_fall(self):
        engine, anchor = self._make_engine()
        anchor.x = -200
        anchor.y = 900
        fell = []
        engine._fall_back = lambda: fell.append("fall")
        random.seed(1)
        engine._recover_if_out_of_bounds()
        self.assertEqual(fell, ["fall"])
        self.assertTrue(0 <= anchor.x < 800)
        self.assertEqual(anchor.y, -256)


class ActionParamTests(unittest.TestCase):
    def test_action_params_are_resolved_once(self):
        calls = []
        engine = object.__new__(BehaviorEngine)
        engine.tick_count = 0
        engine.config = SimpleNamespace(constants={})
        engine.window = SimpleNamespace(
            runtime=SimpleNamespace(
                state_vars={},
                eval_bool=lambda _value, default=True, variables=None: default,
                eval_value=lambda _value, default=None, variables=None: calls.append("eval") or len(calls),
            )
        )
        action = BaseActionInstance(
            engine,
            ActionDefinition(name="test", action_type="move", params={"TargetX": "${Math.random()*100}"}),
            {},
        )

        self.assertEqual(action.param_value("TargetX"), 1)
        self.assertEqual(action.param_value("TargetX"), 1)
        self.assertEqual(calls, ["eval"])


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = ExpressionRuntime(DummyEnvProvider(), DummyStateProvider())

    def test_eval_math_and_ternary(self):
        value = self.runtime.eval("#{mascot.lookRight ? 10 : 20}", default=None)
        self.assertEqual(value, 10)

    def test_eval_cursor_and_boolean(self):
        result = self.runtime.eval_bool("${mascot.environment.cursor.x > 100 && mascot.totalCount >= 3}", default=False)
        self.assertTrue(result)

    def test_eval_min_max_abs(self):
        value = self.runtime.eval("${Math.max(3, Math.min(9, Math.abs(-4)))}", default=None)
        self.assertEqual(value, 4)


if __name__ == "__main__":
    unittest.main()
