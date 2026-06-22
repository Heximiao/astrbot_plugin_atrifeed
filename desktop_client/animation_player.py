import time
from pathlib import Path

from shimeji_actions import TYPE_BUILTIN, TYPE_COMPOUND


ACTION_LOOK = "\u632f\u308a\u5411\u304f"
ACTION_OFFSET = "\u5909\u4f4d"


class AnimationPlayer:
    def __init__(self, window, registry):
        self.window = window
        self.registry = registry
        self.action_name = None
        self.action = registry.resolve("idle")
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

        if not isinstance(self.action, str) and self.action.type == TYPE_COMPOUND:
            self.queue = list(self.action.refs or [])
            self.in_compound = True
            self._advance_queue()
            return

        if not isinstance(self.action, str) and self.action.type == TYPE_BUILTIN and name in {ACTION_LOOK, ACTION_OFFSET}:
            self._run_builtin(name, params)
            self._advance_queue()
            return

        self.frame_index = 0
        self.last_tick = time.monotonic()
        self._preload_action_images()
        self._show_current_frame()

    def tick(self):
        if isinstance(self.action, str):
            return
        frames = self.action.frames
        if not frames:
            return
        frame = frames[self.frame_index % len(frames)]
        if time.monotonic() - self.last_tick >= frame.duration / 20:
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.last_tick = time.monotonic()
            self._show_current_frame()
        if self.deadline and time.monotonic() >= self.deadline:
            self.finish_current_ref()

    def current_velocity(self) -> tuple[int, int]:
        if isinstance(self.action, str) or not self.action.frames:
            return 0, 0
        frame = self.action.frames[self.frame_index % len(self.action.frames)]
        return frame.velocity

    def _show_current_frame(self):
        if isinstance(self.action, str) or not self.action.frames:
            return
        frame = self.action.frames[self.frame_index % len(self.action.frames)]
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
        if isinstance(self.action, str) or not self.action.frames:
            return
        for frame in self.action.frames:
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
