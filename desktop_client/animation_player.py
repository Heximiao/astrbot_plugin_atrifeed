import time
from pathlib import Path


class AnimationPlayer:
    def __init__(self, window, registry):
        self.window = window
        self.registry = registry
        self.action_name = None
        self.action = registry.resolve("idle")
        self.frame_index = 0
        self.last_tick = time.monotonic()
        self.images = {}

    def play(self, name: str):
        if name == self.action_name:
            return
        self.action_name = name
        self.action = self.registry.resolve(name)
        self.frame_index = 0
        self.last_tick = time.monotonic()
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

    def current_velocity(self) -> tuple[int, int]:
        if isinstance(self.action, str) or not self.action.frames:
            return 0, 0
        frame = self.action.frames[self.frame_index % len(self.action.frames)]
        return frame.velocity

    def _show_current_frame(self):
        if isinstance(self.action, str) or not self.action.frames:
            return
        frame = self.action.frames[self.frame_index % len(self.action.frames)]
        if not frame.image or not Path(frame.image).exists():
            return
        image = self.images.get(frame.image)
        if not image:
            image = self.window.load_image(frame.image)
            self.images[frame.image] = image
        self.window.set_image(image)
