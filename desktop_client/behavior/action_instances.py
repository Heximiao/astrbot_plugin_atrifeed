from __future__ import annotations

from typing import TYPE_CHECKING

from shimeji_actions import ActionCallDefinition, ActionDefinition

from behavior.constants import BORDER_CEILING, BORDER_GROUND, BORDER_WALL
from behavior.types import LostGroundError

if TYPE_CHECKING:
    from behavior_engine import BehaviorEngine


class BaseActionInstance:
    def __init__(self, engine: "BehaviorEngine", definition: ActionDefinition, params: dict[str, str]):
        self.engine = engine
        self.definition = definition
        self.params = dict(definition.params)
        self.params.update(params)
        self.start_tick = engine.tick_count
        self.local_vars: dict[str, object] = {}
        self._param_cache: dict[str, object] | None = None
        self.finished = False

    def tick(self) -> bool:
        if self.finished:
            return True
        if not self._is_effective():
            self.finished = True
            return True
        self._tick()
        if not self._has_next():
            self.finished = True
        return self.finished

    def current_frame(self):
        animation = self._current_animation()
        if not animation or not animation.frames:
            return None
        elapsed = self.elapsed()
        index = elapsed % animation.duration
        for frame in animation.frames:
            index -= frame.duration
            if index < 0:
                return frame
        return animation.frames[-1]

    def elapsed(self) -> float:
        return max(0, self.engine.tick_count - self.start_tick)

    def param_value(self, *keys, default=None):
        values = self._resolved_params()
        for key in keys:
            if key in values:
                return values[key]
        return default

    def _resolved_params(self) -> dict[str, object]:
        if self._param_cache is None:
            self._param_cache = self.engine._resolve_param_values(self.params, self.local_vars)
        return self._param_cache

    def param_bool(self, *keys, default=False) -> bool:
        value = self.param_value(*keys, default=default)
        if isinstance(value, bool):
            return value
        if value in (None, ""):
            return default
        return str(value).strip().lower() == "true"

    def is_draggable(self) -> bool:
        return self.param_bool("ドラッグ可能", "Draggable", default=True)

    def _is_effective(self) -> bool:
        condition = self.param_value("条件", "Condition", default=True)
        if isinstance(condition, bool):
            return condition
        if condition in (None, ""):
            return True
        scope = {**self.engine.config.constants, **self.engine.window.runtime.state_vars, **self.local_vars}
        return self.engine.window.runtime.eval_bool(condition, default=True, variables=scope)

    def _has_next(self) -> bool:
        duration = self.param_value("長さ", "Duration", default=None)
        if isinstance(duration, (int, float)) and duration >= 0:
            return self.elapsed() < int(duration)
        return True

    def _current_animation(self):
        scope = {**self.engine.config.constants, **self.engine.window.runtime.state_vars, **self.local_vars}
        for animation in self.definition.animations:
            if not animation.condition or self.engine.window.runtime.eval_bool(animation.condition, default=False, variables=scope):
                return animation
        return self.definition.animations[0] if self.definition.animations else None

    def _tick(self):
        frame = self.current_frame()
        if frame and self.definition.border in BORDER_GROUND:
            border = self.engine.window.runtime.environment_provider.floor_border()
            if not border.isOn(self.engine.window.anchor_point()):
                raise LostGroundError()
        if frame and self.definition.border in BORDER_CEILING:
            border = self.engine.window.runtime.environment_provider.ceiling_border()
            if not border.isOn(self.engine.window.anchor_point()):
                raise LostGroundError()
        if frame and self.definition.border in BORDER_WALL:
            border = self.engine.window.runtime.environment_provider.wall_border(self.engine.window.facing > 0)
            if not border.isOn(self.engine.window.anchor_point()):
                raise LostGroundError()


class StayActionInstance(BaseActionInstance):
    pass


class AnimateActionInstance(BaseActionInstance):
    def _has_next(self) -> bool:
        animation = self._current_animation()
        if animation is None:
            return False
        if not super()._has_next():
            return False
        return self.elapsed() < animation.duration


class MoveActionInstance(BaseActionInstance):
    def _tick(self):
        super()._tick()
        frame = self.current_frame()
        if frame is None:
            return
        target_x = self.param_value("目的地X", "TargetX", default=None)
        target_y = self.param_value("目的地Y", "TargetY", default=None)
        anchor = self.engine.window.anchor_point()
        next_x = anchor.x
        next_y = anchor.y
        vx, vy = frame.velocity
        dt = self.engine.tick_scale
        if target_x is not None and abs(float(target_x) - anchor.x) > 1:
            self.engine.window.set_facing(1 if target_x > anchor.x else -1)
        if vx:
            step_x = abs(vx) * self.engine.window.facing * dt
            next_x += step_x
            if target_x is not None:
                if step_x > 0 and next_x >= target_x:
                    next_x = float(target_x)
                elif step_x < 0 and next_x <= target_x:
                    next_x = float(target_x)
        elif target_x is not None and abs(target_x - anchor.x) <= 1:
            next_x = float(target_x)
        if self.definition.border in BORDER_GROUND:
            border = self.engine.window.runtime.environment_provider.floor_border()
            if hasattr(border, "y") and border.y is not None:
                next_y = border.y
        elif self.definition.border in BORDER_CEILING:
            border = self.engine.window.runtime.environment_provider.ceiling_border()
            if hasattr(border, "y") and border.y is not None:
                next_y = border.y
        elif self.definition.border in BORDER_WALL:
            border = self.engine.window.runtime.environment_provider.wall_border(self.engine.window.facing > 0)
            if hasattr(border, "x") and border.x is not None:
                next_x = border.x
            next_y += vy * dt
        else:
            next_y += vy * dt
        if target_y is not None and self.definition.border not in BORDER_GROUND | BORDER_CEILING:
            if vy > 0 and next_y >= target_y:
                next_y = float(target_y)
            elif vy < 0 and next_y <= target_y:
                next_y = float(target_y)
        self.engine.window.set_anchor(next_x, next_y)

    def _has_next(self) -> bool:
        if not super()._has_next():
            return False
        frame = self.current_frame()
        if frame is None:
            return False
        target_x = self.param_value("目的地X", "TargetX", default=None)
        target_y = self.param_value("目的地Y", "TargetY", default=None)
        anchor = self.engine.window.anchor_point()
        reached_x = target_x is None or abs(anchor.x - int(target_x)) <= 1
        reached_y = target_y is None or abs(anchor.y - int(target_y)) <= 1
        return not (reached_x and reached_y)


class SequenceActionInstance(BaseActionInstance):
    def __init__(self, engine: "BehaviorEngine", definition: ActionDefinition, params: dict[str, str]):
        super().__init__(engine, definition, params)
        self.current_index = 0
        self.current_child = None
        self.loop = self.param_bool("繰り返し", "Loop", default=False)
        self._advance()

    def _advance(self):
        while self.current_index < len(self.definition.children):
            call = self.definition.children[self.current_index]
            child = self._child_from_call(call)
            if child is not None and child._is_effective():
                self.current_child = child
                return
            self.current_index += 1
        if self.loop and self.definition.children:
            self.current_index = 0
            self._advance()
            return
        self.current_child = None
        self.finished = True

    def _child_from_call(self, call: ActionCallDefinition):
        definition = call.inline_action or self.engine.config.actions.get(self.engine._resolve_name(call.action_name or ""))
        if definition is None:
            return None
        merged = dict(call.params)
        return self.engine._instantiate_action(definition, merged)

    def _tick(self):
        if self.current_child is None:
            self.finished = True
            return
        child_finished = self.current_child.tick()
        if child_finished:
            self.current_index += 1
            self._advance()

    def current_frame(self):
        if self.current_child is None:
            return None
        return self.current_child.current_frame()

    def is_draggable(self) -> bool:
        if self.current_child is None:
            return True
        return self.current_child.is_draggable()

    def _has_next(self) -> bool:
        return not self.finished


class SelectActionInstance(SequenceActionInstance):
    def _advance(self):
        if self.current_index >= len(self.definition.children):
            self.current_child = None
            self.finished = True
            return
        while self.current_index < len(self.definition.children):
            call = self.definition.children[self.current_index]
            child = self._child_from_call(call)
            if child is not None and child._is_effective():
                self.current_child = child
                return
            self.current_index += 1
        self.current_child = None
        self.finished = True

    def _tick(self):
        if self.current_child is None:
            self.finished = True
            return
        if self.current_child.tick():
            self.current_child = None
            self.finished = True


class LookActionInstance(BaseActionInstance):
    def _tick(self):
        value = self.param_value("右向き", "LookRight", default=None)
        if value is None:
            self.engine.window.set_facing(-self.engine.window.facing)
        else:
            self.engine.window.set_facing(1 if bool(value) else -1)
        self.finished = True


class OffsetActionInstance(BaseActionInstance):
    def _tick(self):
        dx = self.param_value("X", default=0) or 0
        dy = self.param_value("Y", default=0) or 0
        anchor = self.engine.window.anchor_point()
        self.engine.window.set_anchor(anchor.x + int(dx), anchor.y + int(dy))
        self.finished = True


class JumpActionInstance(BaseActionInstance):
    def _tick(self):
        frame = self.current_frame()
        if frame:
            self.local_vars["VelocityX"] = 0
            self.local_vars["VelocityY"] = 0
        target_x = int(self.param_value("目的地X", "TargetX", default=self.engine.window.anchor_point().x))
        target_y = int(self.param_value("目的地Y", "TargetY", default=self.engine.window.anchor_point().y))
        velocity = float(self.param_value("VelocityParam", default=20) or 20)
        anchor = self.engine.window.anchor_point()
        distance_x = target_x - anchor.x
        distance_y = target_y - anchor.y - abs(distance_x) / 2
        distance = max(0.001, (distance_x * distance_x + distance_y * distance_y) ** 0.5)
        vx = velocity * distance_x / distance
        vy = velocity * distance_y / distance
        self.local_vars["VelocityX"] = vx
        self.local_vars["VelocityY"] = vy
        dt = self.engine.tick_scale
        next_x = anchor.x + vx * dt
        next_y = anchor.y + vy * dt
        if abs(distance_x) <= velocity * dt and abs(distance_y) <= velocity * dt:
            next_x, next_y = target_x, target_y
            self.finished = True
        if abs(target_x - anchor.x) > 1:
            self.engine.window.set_facing(1 if target_x > anchor.x else -1)
        self.engine.window.set_anchor(next_x, next_y)

    def _has_next(self) -> bool:
        return not self.finished


class FallActionInstance(BaseActionInstance):
    def __init__(self, engine: "BehaviorEngine", definition: ActionDefinition, params: dict[str, str]):
        super().__init__(engine, definition, params)
        self.vx = float(self.param_value("初速X", "InitialVX", default=0) or 0)
        self.vy = float(self.param_value("初速Y", "InitialVY", default=0) or 0)

    def _tick(self):
        gravity = float(self.param_value("重力", "Gravity", default=2) or 2)
        resistance_x = float(self.param_value("空気抵抗X", "ResistanceX", "RegistanceX", default=0.05) or 0.05)
        resistance_y = float(self.param_value("空気抵抗Y", "ResistanceY", "RegistanceY", default=0.1) or 0.1)
        dt = self.engine.tick_scale
        self.vx -= self.vx * resistance_x * dt
        self.vy -= self.vy * resistance_y * dt
        self.vy += gravity * dt
        self.local_vars["VelocityX"] = self.vx
        self.local_vars["VelocityY"] = self.vy
        if abs(self.vx) >= 0.5:
            self.engine.window.set_facing(1 if self.vx > 0 else -1)
        dx = self.vx * dt
        dy = self.vy * dt

        anchor = self.engine.window.anchor_point()
        steps = max(1, int(max(abs(dx), abs(dy))))
        landed = False
        for step in range(steps + 1):
            x = anchor.x + dx * step / steps
            y = anchor.y + dy * step / steps
            self.engine.window.set_anchor(x, y)

            floor = self.engine.window.runtime.environment_provider.floor_border(ignore_separator=True)
            wall = self.engine.window.runtime.environment_provider.wall_border(
                self.engine.window.facing > 0,
                ignore_separator=True,
            )

            if dy > 0:
                for offset in range(-80, 1):
                    self.engine.window.set_anchor(x, y + offset)
                    if floor.isOn(self.engine.window.anchor_point()):
                        landed = True
                        break
                if landed:
                    break
                self.engine.window.set_anchor(x, y)

            if wall.isOn(self.engine.window.anchor_point()):
                landed = True
                break

        if landed:
            self.finished = True
            self.engine.mascot_dragging = False

    def _has_next(self) -> bool:
        return not self.finished


class DraggedActionInstance(BaseActionInstance):
    def __init__(self, engine: "BehaviorEngine", definition: ActionDefinition, params: dict[str, str]):
        super().__init__(engine, definition, params)
        self.foot_x = float(self.engine.window.runtime.environment_provider.cursor.x)
        self.foot_dx = 0.0
        self.time_to_regist = 250

    def _tick(self):
        self.engine.mascot_dragging = True
        self.engine.window.set_dragging(True)
        cursor = self.engine.window.runtime.environment_provider.cursor
        offset_x, offset_y = self._cursor_offsets()
        if abs(cursor.x - self.engine.window.anchor_point().x + offset_x) >= 5:
            self.start_tick = self.engine.tick_count
        new_x = cursor.x
        self.foot_dx = (self.foot_dx + ((new_x - self.foot_x) * 0.1)) * 0.8
        self.foot_x += self.foot_dx
        self.local_vars["footX"] = self.foot_x
        self.local_vars["FootX"] = self.foot_x
        self.local_vars["FootDX"] = self.foot_dx
        self.sync_to_cursor(reset_timer=False)
        if self.elapsed() >= self.time_to_regist:
            self.finished = True
            self.engine.mascot_dragging = False

    def _has_next(self) -> bool:
        return not self.finished and self.engine.drag_active

    def sync_to_cursor(self, reset_timer: bool = False):
        cursor = self.engine.window.runtime.environment_provider.cursor
        offset_x, offset_y = self._cursor_offsets()
        if reset_timer and (abs(cursor.dx) >= 1 or abs(cursor.dy) >= 1):
            self.start_tick = self.engine.tick_count
        self.engine.window.set_anchor(cursor.x + offset_x, cursor.y + offset_y)

    def _cursor_offsets(self) -> tuple[int, int]:
        return (
            int(self.param_value("OffsetX", default=0) or 0),
            int(self.param_value("OffsetY", default=120) or 120),
        )


class RegistActionInstance(BaseActionInstance):
    def _tick(self):
        self.engine.mascot_dragging = True
        self.engine.window.set_dragging(True)
        cursor = self.engine.window.runtime.environment_provider.cursor
        offset_x = int(self.param_value("OffsetX", default=0) or 0)
        if abs(cursor.x - self.engine.window.anchor_point().x + offset_x) >= 5:
            raise LostGroundError()
        animation = self._current_animation()
        if animation and self.elapsed() + 1 >= animation.duration:
            self.engine.mascot_dragging = False
            raise LostGroundError()

    def _has_next(self) -> bool:
        return self.engine.drag_active and not self.finished
