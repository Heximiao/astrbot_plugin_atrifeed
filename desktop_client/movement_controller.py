from types import SimpleNamespace

from desktop_environment import get_work_area_bottom, get_work_area_rect


FLOOR_GAP = 8
FALLBACK_FLOOR_MARGIN = 64
TICK_MS = 20
BASE_MOVE_TICK_MS = 40
MOVE_SCALE = TICK_MS / BASE_MOVE_TICK_MS
TYPE_MOVE = "\u79fb\u52d5"
BORDER_GROUND = "\u5730\u9762"
BORDER_CEILING = "\u5929\u4e95"


class MovementController:
    def __init__(self, window):
        self.window = window

    def floor_y(self):
        sh = self.window.winfo_screenheight()
        h = max(self.window.winfo_height(), 96)
        work_bottom = get_work_area_bottom(self.window)
        return work_bottom - h - FLOOR_GAP if work_bottom else sh - h - FALLBACK_FLOOR_MARGIN

    def move(self):
        player = self.window.player
        action = player.action_name
        real_x, real_y = self.window.winfo_x(), self.window.winfo_y()
        if abs(self.window.move_x - real_x) > 2 or abs(self.window.move_y - real_y) > 2:
            self.window.move_x, self.window.move_y = float(real_x), float(real_y)
        x, y = self.window.move_x, self.window.move_y
        work_area = self._work_area()
        bottom = self.floor_y()

        if self._is_xml_move():
            self._move_from_xml_velocity(x, y, work_area, bottom)
        elif action == "jump":
            self.window.vy = -14
            player.play("fall")
        elif action == "fall":
            target_y = self.window.fall_target_y if self.window.fall_target_y is not None else bottom
            self.window.vy += MOVE_SCALE
            y += self.window.vy * MOVE_SCALE
            if y >= target_y:
                y = target_y
                self.window.vy = 0
                self.window.fall_target_y = None
                player.play("idle")
            self.window.place_at(x, y)
        elif action == "climb":
            anchor_x, anchor_y = self.window.runtime.current_frame_anchor()
            edge_x = (
                work_area.left - anchor_x
                if x < work_area.left + work_area.width / 2
                else work_area.right - anchor_x
            )
            self.window.place_at(edge_x, max(work_area.top - anchor_y, y - 2 * MOVE_SCALE))

    def _is_xml_move(self):
        action = self.window.player.action
        return not isinstance(action, str) and action.type == TYPE_MOVE

    def _move_from_xml_velocity(self, x: int, y: int, work_area, bottom: int):
        player = self.window.player
        action = player.action
        raw_vx, raw_vy = player.current_velocity()
        target_x = self.window.runtime.window_target_x(player.target_x)
        target_y = self.window.runtime.window_target_y(player.target_y)
        anchor_x, anchor_y = self.window.runtime.current_frame_anchor()
        min_x = work_area.left - anchor_x
        max_x = work_area.right - anchor_x
        min_y = work_area.top - anchor_y
        next_x, next_y = x, y
        reached_x = target_x is None
        reached_y = target_y is None

        if raw_vx:
            if target_x is not None:
                self.window.set_facing(1 if target_x > x else -1)
            step = abs(raw_vx) * self.window.facing * MOVE_SCALE
            next_x = x + step
            if target_x is not None and ((step > 0 and next_x >= target_x) or (step < 0 and next_x <= target_x)):
                next_x = int(target_x)
                reached_x = True
        elif target_x is not None and abs(target_x - x) <= 1:
            reached_x = True

        if next_x <= min_x:
            next_x = min_x
            if target_x is not None and target_x <= min_x:
                reached_x = True
            self.window.set_facing(-1)
        elif next_x >= max_x:
            next_x = max_x
            if target_x is not None and target_x >= max_x:
                reached_x = True
            self.window.set_facing(1)

        if action.border == BORDER_GROUND:
            next_y = min(y, bottom)
        elif action.border == BORDER_CEILING:
            next_y = min_y
        elif raw_vy:
            next_y = y + raw_vy * MOVE_SCALE
            if target_y is not None and ((raw_vy > 0 and next_y >= target_y) or (raw_vy < 0 and next_y <= target_y)):
                next_y = int(target_y)
                reached_y = True
        elif target_y is not None and abs(target_y - y) <= 1:
            reached_y = True

        self.window.place_at(max(min_x, min(max_x, next_x)), max(min_y, min(bottom, next_y)))
        if reached_x and reached_y:
            player.finish_current_ref()

    def _work_area(self):
        return get_work_area_rect(self.window) or SimpleNamespace(
            left=0,
            top=0,
            right=self.window.winfo_screenwidth(),
            bottom=self.window.winfo_screenheight(),
            width=self.window.winfo_screenwidth(),
            height=self.window.winfo_screenheight(),
        )
