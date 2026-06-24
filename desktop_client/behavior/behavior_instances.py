from __future__ import annotations

from typing import TYPE_CHECKING

from shimeji_actions import ActionDefinition, BehaviorDefinition

from behavior.types import LostGroundError

if TYPE_CHECKING:
    from behavior_engine import BehaviorEngine


class BaseBehaviorInstance:
    def __init__(self, engine: "BehaviorEngine", forced: bool = False):
        self.engine = engine
        self.forced = forced

    def init(self):
        raise NotImplementedError

    def next(self):
        raise NotImplementedError

    def mouse_pressed(self):
        return

    def mouse_released(self):
        return

    def _start_action(self, action: ActionDefinition, params: dict[str, object]):
        self.engine.current_action = self.engine._instantiate_action(action, params)
        self.engine.current_action_name = action.name
        self.engine.window.current_action_name = action.name

    def _tick_action(
        self,
        previous_name: str | None,
        lost_ground_behavior: str | None,
        forced: bool,
        reset_drag_on_lost_ground: bool = False,
    ):
        self.engine._recover_if_out_of_bounds()
        if self.engine.current_action is None:
            self.engine._complete_behavior(previous_name, forced)
            return
        try:
            finished = self.engine.current_action.tick()
        except LostGroundError:
            self.engine._trace().lost_ground(
                self.engine.tick_count,
                lost_ground_behavior,
                self.engine.current_action_name,
            )
            if reset_drag_on_lost_ground:
                self.engine.window.set_dragging(False)
                self.engine.mascot_dragging = False
            self.engine._fall_back()
            return
        self.engine._render_current_frame()
        if finished:
            self.engine._complete_behavior(previous_name, forced)

    def _start_drag_behavior(self):
        current_action = self.engine.current_action
        if current_action is not None and not current_action.is_draggable():
            self.engine.drag_active = False
            return
        dragged_name = self.engine._behavior_name("Dragged", "drag")
        if dragged_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[dragged_name], forced=True)
            self.engine._trace().drag_start(self.engine.tick_count, dragged_name)
        else:
            self.engine.drag_active = False

    def _throw_if_dragging(self):
        if not self.engine.mascot_dragging:
            return
        thrown_name = self.engine._behavior_name("Thrown", "thrown")
        if thrown_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[thrown_name], forced=True)


class UserBehaviorInstance(BaseBehaviorInstance):
    def __init__(self, engine: "BehaviorEngine", definition: BehaviorDefinition, action: ActionDefinition, forced: bool = False):
        super().__init__(engine, forced=forced)
        self.definition = definition
        self.action_definition = action

    def init(self):
        self._start_action(self.action_definition, self.definition.params)
        if self.engine.current_action is not None and not self.engine.current_action._has_next():
            self.engine._complete_behavior(self.definition.name, self.forced)

    def next(self):
        self._tick_action(
            self.definition.name,
            self.definition.name,
            self.forced,
            reset_drag_on_lost_ground=True,
        )

    def mouse_pressed(self):
        self._start_drag_behavior()

    def mouse_released(self):
        self._throw_if_dragging()


class ActionBehaviorInstance(BaseBehaviorInstance):
    def __init__(self, engine: "BehaviorEngine", action: ActionDefinition, params: dict[str, object]):
        super().__init__(engine, forced=True)
        self.action_definition = action
        self.params = params

    def init(self):
        self._start_action(self.action_definition, self.params)

    def next(self):
        self._tick_action(None, None, True)

    def mouse_pressed(self):
        self._start_drag_behavior()

    def mouse_released(self):
        self._throw_if_dragging()
