import random
from pathlib import Path

from behavior.action_instances import (
    AnimateActionInstance,
    BaseActionInstance,
    DraggedActionInstance,
    FallActionInstance,
    JumpActionInstance,
    LookActionInstance,
    MoveActionInstance,
    OffsetActionInstance,
    RegistActionInstance,
    SelectActionInstance,
    SequenceActionInstance,
    StayActionInstance,
)
from behavior.behavior_instances import (
    ActionBehaviorInstance,
    BaseBehaviorInstance,
    UserBehaviorInstance,
)
from behavior.constants import LEGACY_NAME_MAP, MISSING, TICK_MS, TICK_SCALE
from behavior.param_normalizer import normalize_params
from behavior.types import CandidateRef
from debug_trace import DebugTrace
from override_controller import OverrideController
from shimeji_actions import (
    TYPE_ANIMATE,
    TYPE_EMBEDDED,
    TYPE_MOVE,
    TYPE_SELECT,
    TYPE_SEQUENCE,
    ActionDefinition,
    BehaviorDefinition,
    ShimejiConfiguration,
    parse_configuration,
)


class BehaviorEngine:
    def __init__(self, window, asset_dir: str, debug_trace_enabled: bool = False):
        self.window = window
        self.config: ShimejiConfiguration = parse_configuration(asset_dir)
        self.debug_trace = DebugTrace(debug_trace_enabled)
        self.override_controller = OverrideController()
        self.images: dict[tuple[str, bool], object] = {}
        self.tick_count = 0
        self.current_behavior: BehaviorDefinition | None = None
        self.current_behavior_instance: BaseBehaviorInstance | None = None
        self.current_action: BaseActionInstance | None = None
        self.current_action_name = ""
        self.current_frame = None
        self.current_forced = False
        self._last_traced_action = ""
        self.drag_active = False
        self.mascot_dragging = False
        self.tick_scale = TICK_SCALE
        self.disabled_behaviors: set[str] = set()
        self.window.current_action_name = ""
        self._seed_initial_position()

    def _trace(self) -> DebugTrace:
        trace = getattr(self, "debug_trace", None)
        if trace is None:
            trace = DebugTrace(False)
            self.debug_trace = trace
        return trace

    def preload_all_images(self):
        for action in self.config.actions.values():
            for animation in action.animations:
                for frame in animation.frames:
                    self._preload_frame(frame.image)

    def set_external_state(self, state: dict):
        state_vars = {
            "mood": state.get("mood"),
            "favorability": state.get("favorability"),
            "stamina": state.get("stamina"),
            "last_feed_time": state.get("last_feed_time"),
            "recommended_action": state.get("recommended_action"),
        }
        state_vars.update(state.get("state_vars") or {})
        self.window.runtime.set_state_vars(state_vars)
        forced_behavior = state.get("forced_behavior")
        forced_action = state.get("forced_action")
        if forced_behavior:
            self._trace().forced_behavior(self.tick_count, str(forced_behavior))
            self.override_controller.push_behavior(str(forced_behavior))
        if forced_action:
            self._trace().forced_action(self.tick_count, str(forced_action))
            self.override_controller.push_action(str(forced_action))

    def available_commands(self) -> list[str]:
        names = sorted(set(self.config.behaviors) | set(self.config.actions))
        return names

    def force_behavior(self, name: str):
        resolved = self._resolve_name(name)
        if resolved in self.config.behaviors:
            self._trace().forced_behavior(self.tick_count, resolved)
            self.override_controller.push_behavior(resolved)
        elif resolved in self.config.actions:
            self._trace().forced_action(self.tick_count, resolved)
            self.override_controller.push_action(resolved)

    def force_action(self, name: str):
        resolved = self._resolve_name(name)
        self._trace().forced_action(self.tick_count, resolved)
        self.override_controller.push_action(resolved)

    def on_mouse_press(self):
        self.drag_active = True
        instance = getattr(self, "current_behavior_instance", None)
        if instance is not None:
            instance.mouse_pressed()

    def on_mouse_release(self):
        was_dragging = self.mascot_dragging
        self.drag_active = False
        self.window.set_dragging(False)
        instance = getattr(self, "current_behavior_instance", None)
        if instance is not None:
            instance.mouse_released()
        self._trace().drag_end(self.tick_count, bool(was_dragging))

    def sync_drag_to_cursor(self):
        if not self.drag_active or self.current_action is None:
            return
        action = self._leaf_action(self.current_action)
        sync = getattr(action, "sync_to_cursor", None)
        if sync is None:
            return
        sync(reset_timer=True)
        self._render_current_frame()

    def tick(self):
        self.tick_count += self.tick_scale
        self.window.runtime.refresh_environment()
        request = self.override_controller.pop()
        if request:
            if request.kind == "behavior" and request.name in self.config.behaviors:
                self._set_behavior(self.config.behaviors[request.name], forced=True)
            elif request.kind == "action":
                action_name = self._resolve_name(request.name)
                if action_name in self.config.actions:
                    self._set_action_behavior(self.config.actions[action_name], request.params)

        if self.current_behavior_instance is None:
            self._select_next_behavior(None)
            if self.current_behavior_instance is None:
                return

        self.current_behavior_instance.next()
        self._trace_action_if_changed()

    def current_frame_anchor(self):
        if self.current_frame:
            return self.current_frame.anchor
        return (64, 128)

    def _seed_initial_position(self):
        self.window.runtime.refresh_environment()
        work_area = self.window.runtime.environment_provider.work_area
        anchor_x = max(work_area.left + 96, min(work_area.right - 96, work_area.left + 160))
        anchor_y = work_area.bottom
        self.window.set_anchor(anchor_x, anchor_y)

    def _recover_if_out_of_bounds(self):
        anchor = self.window.anchor_point()
        screen = self.window.runtime.environment_provider.screen
        if not screen.visible:
            return
        out_of_bounds = (
            anchor.x + 128 <= screen.left
            or anchor.x - 128 >= screen.right
            or anchor.y - 256 >= screen.bottom
        )
        if not out_of_bounds:
            return
        work_area = self.window.runtime.environment_provider.work_area
        spawn_left = work_area.left if work_area.visible else screen.left
        spawn_right = work_area.right if work_area.visible else screen.right
        spawn_top = work_area.top if work_area.visible else screen.top
        width = max(1, spawn_right - spawn_left)
        self.window.set_anchor(spawn_left + random.randint(0, width - 1), spawn_top - 256)
        self._fall_back()

    def _set_behavior(self, behavior: BehaviorDefinition, forced: bool):
        action_name = self._resolve_name(behavior.action_name)
        action = self.config.actions.get(action_name)
        if not action:
            return
        self.current_behavior = behavior
        self.current_forced = forced
        self.current_action = None
        self.current_frame = None
        self.current_action_name = ""
        self.window.current_action_name = ""
        self.current_behavior_instance = UserBehaviorInstance(self, behavior, action, forced=forced)
        self.current_behavior_instance.init()
        self._trace().behavior_switch(self.tick_count, behavior.name, forced)
        self._trace_action_if_changed(force=True)

    def _set_action_behavior(self, action: ActionDefinition, params: dict[str, object] | None = None):
        self.current_behavior = None
        self.current_forced = True
        self.current_action = None
        self.current_frame = None
        self.current_action_name = ""
        self.window.current_action_name = ""
        self.current_behavior_instance = ActionBehaviorInstance(self, action, params or {})
        self.current_behavior_instance.init()
        self._trace().behavior_switch(self.tick_count, None, True)
        self._trace_action_if_changed(force=True)

    def _complete_behavior(self, previous_name: str | None, forced: bool):
        self.current_behavior = None
        self.current_behavior_instance = None
        self.current_action = None
        self.current_frame = None
        self.current_action_name = ""
        self.window.current_action_name = ""
        self.mascot_dragging = False
        self.current_forced = False
        self._last_traced_action = ""
        self._select_next_behavior(None if forced else previous_name)

    def _behavior_name(self, *names: str) -> str | None:
        for name in names:
            resolved = self._resolve_name(name)
            if resolved in self.config.behaviors:
                return resolved
        return None

    def _select_next_behavior(self, previous_name: str | None):
        candidates = list(self._global_candidates())
        if previous_name and previous_name in self.config.behaviors:
            previous = self.config.behaviors[previous_name]
            if not previous.next_additive:
                candidates = []
            candidates.extend(self._next_candidates(previous))
        if not candidates:
            self._select_environment_fallback()
            return
        total = sum(item.frequency for item in candidates if item.frequency > 0)
        if total <= 0:
            self._select_environment_fallback()
            return
        choice = random.uniform(0, total)
        for candidate in candidates:
            choice -= candidate.frequency
            if choice <= 0:
                behavior = self.config.behaviors.get(candidate.name)
                if behavior:
                    params = dict(behavior.params)
                    params.update(candidate.params)
                    temp_behavior = BehaviorDefinition(
                        name=behavior.name,
                        action_name=behavior.action_name,
                        frequency=behavior.frequency,
                        hidden=behavior.hidden,
                        toggleable=behavior.toggleable,
                        conditions=behavior.conditions,
                        params=params,
                        next_additive=behavior.next_additive,
                        next_behaviors=behavior.next_behaviors,
                    )
                    self._set_behavior(temp_behavior, forced=False)
                    return
        self._select_environment_fallback()

    def _select_environment_fallback(self):
        anchor = self.window.anchor_point()
        floor = self.window.runtime.environment_provider.floor_border(ignore_separator=True)
        if floor.isOn(anchor):
            idle_name = self._behavior_name("idle")
            if idle_name is not None:
                self._set_behavior(self.config.behaviors[idle_name], forced=False)
                return
        self._fall_back()

    def _global_candidates(self):
        for behavior in self.config.behaviors.values():
            if behavior.frequency <= 0 or behavior.name in self.disabled_behaviors:
                continue
            if self._conditions_pass(behavior.conditions, {}):
                yield CandidateRef(behavior.name, behavior.frequency, dict(behavior.params))

    def _next_candidates(self, behavior: BehaviorDefinition):
        for ref in behavior.next_behaviors:
            if ref.frequency <= 0 or ref.name in self.disabled_behaviors:
                continue
            if self._conditions_pass(ref.conditions, ref.params):
                yield CandidateRef(ref.name, ref.frequency, dict(ref.params))

    def _conditions_pass(self, conditions: list[str], params: dict[str, str]) -> bool:
        scope = dict(self.config.constants)
        scope.update(self.window.runtime.state_vars)
        scope.update(self._resolve_param_values(params, {}))
        for condition in conditions:
            if condition and not self.window.runtime.eval_bool(condition, default=False, variables=scope):
                return False
        return True

    def _resolve_name(self, name: str) -> str:
        if name in self.config.actions or name in self.config.behaviors:
            return name
        mapped = LEGACY_NAME_MAP.get(name, name)
        if mapped in self.config.actions or mapped in self.config.behaviors:
            return mapped
        return name

    def _instantiate_action(self, definition: ActionDefinition, params: dict[str, str] | None = None):
        if definition.action_type == TYPE_SEQUENCE:
            return SequenceActionInstance(self, definition, params or {})
        if definition.action_type == TYPE_SELECT:
            return SelectActionInstance(self, definition, params or {})
        if definition.action_type == TYPE_MOVE:
            return MoveActionInstance(self, definition, params or {})
        if definition.action_type == TYPE_ANIMATE:
            return AnimateActionInstance(self, definition, params or {})
        if definition.action_type == TYPE_EMBEDDED:
            return self._instantiate_embedded(definition, params or {})
        return StayActionInstance(self, definition, params or {})

    def _leaf_action(self, action):
        while hasattr(action, "current_child") and action.current_child is not None:
            action = action.current_child
        return action

    def _trace_action_if_changed(self, force: bool = False):
        action = self.current_action
        if action is not None:
            action = self._leaf_action(action)
        name = getattr(getattr(action, "definition", None), "name", "") or self.current_action_name
        if force or name != self._last_traced_action:
            self._last_traced_action = name
            self._trace().action_switch(self.tick_count, name, self.current_forced)

    def _instantiate_embedded(self, definition: ActionDefinition, params: dict[str, str]):
        class_name = definition.class_name.rsplit(".", 1)[-1]
        if class_name == "Look":
            return LookActionInstance(self, definition, params)
        if class_name == "Offset":
            return OffsetActionInstance(self, definition, params)
        if class_name == "Jump":
            return JumpActionInstance(self, definition, params)
        if class_name == "Fall":
            return FallActionInstance(self, definition, params)
        if class_name == "Dragged":
            return DraggedActionInstance(self, definition, params)
        if class_name == "Regist":
            return RegistActionInstance(self, definition, params)
        if class_name in {"FallWithIE"}:
            return FallActionInstance(self, definition, params)
        if class_name in {"WalkWithIE"}:
            return MoveActionInstance(self, definition, params)
        return AnimateActionInstance(self, definition, params)

    def _resolve_param_values(self, params: dict[str, str], local_vars: dict[str, object]) -> dict[str, object]:
        resolved: dict[str, object] = {}
        pending = dict(params)
        for _ in range(len(pending) + 2):
            progress = False
            for key, raw in list(pending.items()):
                value = self._resolve_raw_value(raw, {**self.config.constants, **self.window.runtime.state_vars, **local_vars, **resolved})
                if value is not MISSING:
                    resolved[key] = value
                    pending.pop(key)
                    progress = True
            if not progress:
                break
        for key, raw in pending.items():
            resolved[key] = raw
        return normalize_params(resolved)

    def _resolve_raw_value(self, raw: str | None, scope: dict[str, object]):
        if raw is None:
            return MISSING
        text = str(raw).strip()
        if not text:
            return ""
        if text.startswith("${") or text.startswith("#{"):
            return self.window.runtime.eval_value(text, default=MISSING, variables=scope)
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except ValueError:
            return text

    def _render_current_frame(self):
        frame = self.current_action.current_frame() if self.current_action else None
        if frame is None:
            return
        self.current_frame = frame
        mirrored = self.window.facing > 0
        key = (frame.image, mirrored)
        image = self.images.get(key)
        if image is None and Path(frame.image).exists():
            image = self.window.load_image(frame.image, mirrored=mirrored)
            self.images[key] = image
        if image is not None:
            self.window.set_image(image)
        self.window.place_from_anchor(*self.current_frame.anchor)

    def _preload_frame(self, image_path: str):
        if not image_path or not Path(image_path).exists():
            return
        for facing in (-1, 1):
            key = (image_path, facing > 0)
            if key not in self.images:
                self.images[key] = self.window.load_image(image_path, mirrored=facing > 0)

    def _fall_back(self):
        for candidate in ("落下する", "Fall"):
            behavior = self.config.behaviors.get(candidate)
            if behavior:
                self._trace().fallback_fall(self.tick_count, behavior.name)
                self._set_behavior(behavior, forced=False)
                return
