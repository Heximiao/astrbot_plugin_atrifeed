import time
from pathlib import Path


DRAG_STOP_TIMEOUT = 1.0
DRAG_MIN_DELTA_X = 2
DRAG_MIN_SAMPLE_TIME = 0.016
DRAG_VELOCITY_SMOOTHING = 0.22
DRAG_SWING_ENTER_SPEED = 220
DRAG_SWING_EXIT_SPEED = 35
DRAG_RESIST_TRIGGER_SPEED = 700
DRAG_RESIST_EXIT_SPEED = 120
DRAG_DIRECTION_SWITCH_COOLDOWN = 0.14
DEBUG_DRAG_LOG = False


class DragController:
    def __init__(self, window):
        self.window = window
        self.offset = None
        self.last_root_x = None
        self.last_time = None
        self.last_moved_time = None
        self.mode = None
        self.mode_changed_at = 0.0
        self.velocity_x = 0.0
        self.debug_log_path = Path(__file__).with_name("desktop_pet_debug.log")

    @property
    def is_dragging(self):
        return self.offset is not None

    def start(self, event):
        now = time.monotonic()
        self.offset = (event.x, event.y)
        self.last_root_x = event.x_root
        self.last_time = now
        self.last_moved_time = now
        self.mode = None
        self.mode_changed_at = now
        self.velocity_x = 0.0
        self.window.vy = 0
        self._set_mode("held", now)

    def drag(self, event):
        if not self.offset:
            return
        dx, dy = self.offset
        now = time.monotonic()
        elapsed = max(now - self.last_time, DRAG_MIN_SAMPLE_TIME) if self.last_time else DRAG_MIN_SAMPLE_TIME
        delta_x = event.x_root - self.last_root_x if self.last_root_x is not None else 0
        if abs(delta_x) >= DRAG_MIN_DELTA_X:
            speed_x = delta_x / elapsed
            self.velocity_x = (
                self.velocity_x * (1 - DRAG_VELOCITY_SMOOTHING)
                + speed_x * DRAG_VELOCITY_SMOOTHING
            )
            self.last_moved_time = now
        self._update_animation(now)
        self.last_root_x = event.x_root
        self.last_time = now
        self.window.place_at(event.x_root - dx, event.y_root - dy)

    def end(self, _):
        self.offset = None
        self.last_root_x = None
        self.last_time = None
        self.last_moved_time = None
        self.mode = None
        self.velocity_x = 0.0
        self.window.player.play("fall")

    def settle_animation(self):
        if not self.offset or self.last_moved_time is None:
            return
        now = time.monotonic()
        if now - self.last_moved_time < DRAG_STOP_TIMEOUT:
            return
        self.velocity_x *= 0.5
        if abs(self.velocity_x) <= DRAG_SWING_EXIT_SPEED:
            self._set_mode("held", now)

    def _update_animation(self, now: float):
        speed_x = self.velocity_x
        if abs(speed_x) <= DRAG_SWING_EXIT_SPEED:
            self._set_mode("held", now)
            return

        if abs(speed_x) < DRAG_SWING_ENTER_SPEED and self.mode not in {
            "swing_left",
            "swing_right",
            "resist_left",
            "resist_right",
        }:
            self._set_mode("held", now)
            return

        if speed_x >= DRAG_RESIST_TRIGGER_SPEED:
            target_mode = "resist_right"
        elif speed_x <= -DRAG_RESIST_TRIGGER_SPEED:
            target_mode = "resist_left"
        elif self.mode == "resist_right" and speed_x >= DRAG_RESIST_EXIT_SPEED:
            target_mode = "resist_right"
        elif self.mode == "resist_left" and speed_x <= -DRAG_RESIST_EXIT_SPEED:
            target_mode = "resist_left"
        elif self.mode == "swing_right" and speed_x >= DRAG_SWING_EXIT_SPEED:
            target_mode = "swing_right"
        elif self.mode == "swing_left" and speed_x <= -DRAG_SWING_EXIT_SPEED:
            target_mode = "swing_left"
        elif speed_x >= DRAG_SWING_ENTER_SPEED:
            target_mode = "swing_right"
        elif speed_x <= -DRAG_SWING_ENTER_SPEED:
            target_mode = "swing_left"
        else:
            return

        if self._is_direction_switch(target_mode) and now - self.mode_changed_at < DRAG_DIRECTION_SWITCH_COOLDOWN:
            return
        self._set_mode(target_mode, now)

    def _is_direction_switch(self, target_mode: str):
        current_direction = self._drag_direction(self.mode)
        target_direction = self._drag_direction(target_mode)
        return current_direction and target_direction and current_direction != target_direction

    def _drag_direction(self, mode: str | None):
        if mode and mode.endswith("_left"):
            return "left"
        if mode and mode.endswith("_right"):
            return "right"
        return None

    def _set_mode(self, mode: str, now: float):
        if mode == self.mode:
            return
        self.mode = mode
        self.mode_changed_at = now
        action = {
            "held": "drag_hold",
            "swing_left": "drag_swing_left",
            "swing_right": "drag_swing_right",
            "resist_left": "drag_resist_left",
            "resist_right": "drag_resist_right",
        }[mode]
        self.window.player.play(action)
        self._log_mode(mode, action)

    def _log_mode(self, mode: str, action: str):
        if not DEBUG_DRAG_LOG:
            return
        frame = None
        player_action = self.window.player.action
        if not isinstance(player_action, str) and player_action.frames:
            frame = Path(player_action.frames[0].image).name
        message = (
            f"[drag] mode={mode} action={action} frame={frame} "
            f"vx={self.velocity_x:.1f} facing={self.window.facing}"
        )
        print(message, flush=True)
        try:
            with self.debug_log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(message + "\n")
        except Exception:
            pass
