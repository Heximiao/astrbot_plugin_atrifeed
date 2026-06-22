import random
from types import SimpleNamespace

from desktop_environment import get_work_area_bottom


WALL_CLIMB_MARGIN = 64
WALL_CLIMB_TOP_ZONE_RATIO = 1 / 3


class ShimejiRuntime:
    def __init__(self, window):
        self.window = window

    def eval_bool(self, value: str | None, default: bool = False, variables: dict | None = None) -> bool:
        if value is None:
            return default
        text = value.strip()
        if text.lower() in {"true", "false"}:
            return text.lower() == "true"
        result = self.eval_value(text, variables=variables)
        return bool(result) if result is not None else default

    def eval_value(self, value: str | None, default=None, variables: dict | None = None):
        if value is None or value == "":
            return default
        text = value.strip()
        if (text.startswith("${") or text.startswith("#{")) and text.endswith("}"):
            text = text[2:-1]
        text = (
            text.replace("Math.random()", "random.random()")
            .replace("Math.min", "min")
            .replace("Math.max", "max")
            .replace("true", "True")
            .replace("false", "False")
            .replace("&&", " and ")
            .replace("||", " or ")
        )
        env = self._expression_env(variables)
        try:
            return float(eval(text, {"__builtins__": {}}, env))
        except Exception:
            try:
                return float(text)
            except ValueError:
                return default

    def current_anchor(self):
        anchor = self.current_frame_anchor()
        return self.window.winfo_x() + anchor[0], self.window.winfo_y() + anchor[1]

    def current_frame_anchor(self):
        anchor = (64, 128)
        player = getattr(self.window, "player", None)
        frames = getattr(player, "frames", None)
        if frames:
            frame = frames[player.frame_index % len(frames)]
            anchor = frame.anchor
        elif player and not isinstance(player.action, str) and player.action.frames:
            anchor = player.action.frames[player.frame_index % len(player.action.frames)].anchor
        return anchor

    def window_target_x(self, target_x: float | None):
        if target_x is None:
            return None
        return target_x - self.current_frame_anchor()[0]

    def window_target_y(self, target_y: float | None):
        if target_y is None:
            return None
        return target_y - self.current_frame_anchor()[1]

    def wall_climb_target_y(self):
        _, anchor_y = self.current_anchor()
        work_bottom = get_work_area_bottom() or self.window.winfo_screenheight()
        if anchor_y <= work_bottom * WALL_CLIMB_TOP_ZONE_RATIO:
            return work_bottom - WALL_CLIMB_MARGIN
        return WALL_CLIMB_MARGIN

    def _expression_env(self, variables: dict | None = None):
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        work_bottom = get_work_area_bottom() or sh
        work_area = SimpleNamespace(left=0, top=0, right=sw, bottom=work_bottom, width=sw, height=work_bottom)
        environment = SimpleNamespace(workArea=work_area, screen=SimpleNamespace(width=sw, height=sh))
        anchor_x, anchor_y = self.current_anchor()
        anchor = SimpleNamespace(x=anchor_x, y=anchor_y)
        mascot = SimpleNamespace(environment=environment, anchor=anchor, lookRight=self.window.facing > 0)
        env = {"mascot": mascot, "random": random, "min": min, "max": max}
        if variables:
            env.update({key: value for key, value in variables.items() if value is not None})
        return env
