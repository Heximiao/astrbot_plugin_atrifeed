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

    def behavior_name(self) -> str | None:
        return None


class UserBehaviorInstance(BaseBehaviorInstance):
    def __init__(self, engine: "BehaviorEngine", definition: BehaviorDefinition, action: ActionDefinition, forced: bool = False):
        super().__init__(engine, forced=forced)
        self.definition = definition
        self.action_definition = action

    def init(self):
        self.engine.current_action = self.engine._instantiate_action(self.action_definition, self.definition.params)
        self.engine.current_action_name = self.action_definition.name
        self.engine.window.current_action_name = self.action_definition.name
        if self.engine.current_action is not None and not self.engine.current_action._has_next():
            self.engine._complete_behavior(self.definition.name, self.forced)

    def next(self):
        self.engine._recover_if_out_of_bounds()
        if self.engine.current_action is None:
            self.engine._complete_behavior(self.definition.name, self.forced)
            return
        try:
            finished = self.engine.current_action.tick()
        except LostGroundError:
            self.engine._trace().lost_ground(
                self.engine.tick_count,
                self.definition.name,
                self.engine.current_action_name,
            )
            self.engine.window.set_dragging(False)
            self.engine.mascot_dragging = False
            self.engine._fall_back()
            return
        self.engine._render_current_frame()
        if finished:
            self.engine._complete_behavior(self.definition.name, self.forced)

    def behavior_name(self) -> str | None:
        return self.definition.name

    def mouse_pressed(self):
        current_action = self.engine.current_action
        if current_action is not None and not current_action.is_draggable():
            return
        dragged_name = self.engine._behavior_name("Dragged", "drag")
        if dragged_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[dragged_name], forced=True)
            self.engine._trace().drag_start(self.engine.tick_count, dragged_name)

    def mouse_released(self):
        if not self.engine.mascot_dragging:
            return
        thrown_name = self.engine._behavior_name("Thrown", "thrown")
        if thrown_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[thrown_name], forced=True)


class ActionBehaviorInstance(BaseBehaviorInstance):
    def __init__(self, engine: "BehaviorEngine", action: ActionDefinition, params: dict[str, object]):
        super().__init__(engine, forced=True)
        self.action_definition = action
        self.params = params

    def init(self):
        self.engine.current_action = self.engine._instantiate_action(self.action_definition, self.params)
        self.engine.current_action_name = self.action_definition.name
        self.engine.window.current_action_name = self.action_definition.name

    def next(self):
        self.engine._recover_if_out_of_bounds()
        if self.engine.current_action is None:
            self.engine._complete_behavior(None, True)
            return
        try:
            finished = self.engine.current_action.tick()
        except LostGroundError:
            self.engine._trace().lost_ground(
                self.engine.tick_count,
                None,
                self.engine.current_action_name,
            )
            self.engine._fall_back()
            return
        self.engine._render_current_frame()
        if finished:
            self.engine._complete_behavior(None, True)

    def mouse_pressed(self):
        current_action = self.engine.current_action
        if current_action is not None and not current_action.is_draggable():
            return
        dragged_name = self.engine._behavior_name("Dragged", "drag")
        if dragged_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[dragged_name], forced=True)
            self.engine._trace().drag_start(self.engine.tick_count, dragged_name)

    def mouse_released(self):
        if not self.engine.mascot_dragging:
            return
        thrown_name = self.engine._behavior_name("Thrown", "thrown")
        if thrown_name is not None:
            self.engine._set_behavior(self.engine.config.behaviors[thrown_name], forced=True)
