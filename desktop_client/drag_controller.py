MAX_THROW_SPEED = 48.0


class DragController:
    def __init__(self, window):
        self.window = window
        self.offset = None

    def start(self, event):
        self.offset = (event.x, event.y)
        self._update_cursor(event)
        self.window.engine.on_mouse_press()

    def drag(self, event):
        if not self.offset:
            return
        self._update_cursor(event)
        sync_drag = getattr(self.window.engine, "sync_drag_to_cursor", None)
        if sync_drag is not None:
            sync_drag()

    def end(self, _):
        self._clamp_throw_velocity()
        self.offset = None
        self.window.engine.on_mouse_release()

    def _update_cursor(self, event):
        cursor = self.window.runtime.environment_provider.cursor
        old_x, old_y = cursor.x, cursor.y
        cursor.x = event.x_root
        cursor.y = event.y_root
        cursor.dx = event.x_root - old_x
        cursor.dy = event.y_root - old_y

    def _clamp_throw_velocity(self):
        cursor = self.window.runtime.environment_provider.cursor
        cursor.dx = self._clamp(cursor.dx)
        cursor.dy = self._clamp(cursor.dy)

    def _clamp(self, value: float) -> float:
        return max(-MAX_THROW_SPEED, min(MAX_THROW_SPEED, value))
