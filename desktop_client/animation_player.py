import time
from pathlib import Path

from action_rules import apply_action_target_rules
from shimeji_actions import TYPE_BUILTIN, TYPE_COMPOUND


ACTION_LOOK = "\u632f\u308a\u5411\u304f"
ACTION_OFFSET = "\u5909\u4f4d"


class AnimationPlayer:
    def __init__(self, window, registry):
        self.window = window
        self.registry = registry
        self.action_name = None
        self.action = registry.resolve("idle")
        self.frames = []
        self.frame_index = 0
        self.last_tick = time.monotonic()
        self.images = {}
        self.queue = []
        self.current_params = {}
        self.deadline = None
        self.target_x = None
        self.target_y = None
        self.in_compound = False

    def play(self, name: str, params: dict[str, str] | None = None):
        if name == self.action_name:
            return
        self.queue = []
        self.in_compound = False
        self._start(name, params or {})

    def _start(self, name: str, params: dict[str, str]):
        self.action_name = name
        self.action = self.registry.resolve(name)
        self.current_params = params
        self.deadline = self._deadline_from(params)
        self.target_x = self.window.eval_action_value(params.get("\u76ee\u7684\u5730X"))
        self.target_y = self.window.eval_action_value(params.get("\u76ee\u7684\u5730Y"))
        self.target_x, self.target_y = apply_action_target_rules(
            self.action,
            self.target_x,
            self.target_y,
            self.window.runtime,
        )
        condition_vars = {"\u76ee\u7684\u5730X": self.target_x, "\u76ee\u7684\u5730Y": self.target_y}

        if not isinstance(self.action, str) and self.action.type == TYPE_COMPOUND:
            self.queue = list(self.action.refs or [])
            self.in_compound = True
            self._advance_queue()
            return

        if not isinstance(self.action, str) and self.action.type == TYPE_BUILTIN and name in {ACTION_LOOK, ACTION_OFFSET}:
            self._run_builtin(name, params)
            self._advance_queue()
            return

        self.frames = self._select_frames(condition_vars)
        self.frame_index = 0
        self.last_tick = time.monotonic()
        self.registry.remember_played(name)
        self._preload_action_images()
        self._show_current_frame()

    def tick(self):
        if isinstance(self.action, str):
            return
        frames = self.frames
        if not frames:
            return
        frame = frames[self.frame_index % len(frames)]
        if time.monotonic() - self.last_tick >= frame.duration / 20:
            next_frame_index = self.frame_index + 1
            if self._is_one_shot_finished(next_frame_index):
                self.finish_current_ref()
                return
            self.frame_index = next_frame_index % len(frames)
            self.last_tick = time.monotonic()
            self._show_current_frame()
        if self.deadline and time.monotonic() >= self.deadline:
            self.finish_current_ref()

    def current_velocity(self) -> tuple[int, int]:
        if isinstance(self.action, str) or not self.frames:
            return 0, 0
        frame = self.frames[self.frame_index % len(self.frames)]
        return frame.velocity

    def _show_current_frame(self):
        if isinstance(self.action, str) or not self.frames:
            return
        frame = self.frames[self.frame_index % len(self.frames)]
        mirrored = self._should_mirror_current_action()
        key = (frame.image, mirrored)
        image = self.images.get(key)
        if image:
            self.window.set_image(image)
            return
        if not frame.image or not Path(frame.image).exists():
            return
        if not image:
            image = self.window.load_image(frame.image, mirrored=mirrored)
            self.images[key] = image
        self.window.set_image(image)

    def _should_mirror_current_action(self):
        if isinstance(self.action_name, str) and self.action_name.startswith("drag_"):
            return False
        return self.window.facing > 0

    def preload_all_images(self):
        for action in self.registry.xml_actions.values():
            if isinstance(action, str) or not action.frames:
                continue
            for frame in action.frames:
                self._preload_frame_image(frame.image)

    def _preload_action_images(self):
        if isinstance(self.action, str) or not self.frames:
            return
        for frame in self.frames:
            self._preload_frame_image(frame.image)

    def _preload_frame_image(self, image_path: str):
        if not image_path or not Path(image_path).exists():
            return
        for facing in (-1, 1):
            key = (image_path, facing)
            if key not in self.images:
                self.images[key] = self.window.load_image(image_path, mirrored=facing > 0)

    def refresh_frame(self):
        self._show_current_frame()

    def finish_current_ref(self):
        if self.in_compound:
            self._advance_queue()
        elif self.action_name != "idle":
            self.play("idle")

    def _advance_queue(self):
        if not self.queue:
            self.in_compound = False
            self.play("idle")
            return
        ref = self.queue.pop(0)
        self._start(ref.name, ref.params)

    def _run_builtin(self, name: str, params: dict[str, str]):
        if name == ACTION_LOOK:
            self.window.set_facing_from_param(params.get("\u53f3\u5411\u304d"))
        elif name == ACTION_OFFSET:
            self.window.offset_by(
                self.window.eval_action_value(params.get("X"), 0) or 0,
                self.window.eval_action_value(params.get("Y"), 0) or 0,
            )

    def _deadline_from(self, params: dict[str, str]):
        duration = self.window.eval_action_value(params.get("\u9577\u3055"))
        return time.monotonic() + duration / 20 if duration else None

    def _select_frames(self, condition_vars: dict[str, float | None]):
        if isinstance(self.action, str):
            return []
        for animation in self.action.animations or []:
            if not animation.condition or self.window.eval_action_bool(animation.condition, variables=condition_vars):
                return animation.frames
        return self.action.frames

    def _is_one_shot_finished(self, next_frame_index: int) -> bool:
        return self.registry.is_one_shot(self.action_name) and next_frame_index >= len(self.frames)
