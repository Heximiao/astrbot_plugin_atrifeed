import ctypes
import os
from dataclasses import dataclass
from types import SimpleNamespace


BORDER_TOLERANCE = 6
DEFAULT_WINDOW_TITLE_BLACKLIST = (
    "NVIDIA GeForce Overlay",
    "Windows Input Experience",
)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


@dataclass
class PointState:
    x: int = 0
    y: int = 0
    dx: float = 0.0
    dy: float = 0.0


@dataclass
class Rect:
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    dleft: int = 0
    dtop: int = 0
    dright: int = 0
    dbottom: int = 0

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def visible(self) -> bool:
        return self.width > 0 and self.height > 0

    def intersects(self, other: "Rect") -> bool:
        if not self.visible or not other.visible:
            return False
        return not (
            self.right <= other.left
            or other.right <= self.left
            or self.bottom <= other.top
            or other.bottom <= self.top
        )

    def update_from(self, other: "Rect") -> None:
        self.dleft = other.left - self.left
        self.dtop = other.top - self.top
        self.dright = other.right - self.right
        self.dbottom = other.bottom - self.bottom
        self.left = other.left
        self.top = other.top
        self.right = other.right
        self.bottom = other.bottom

    def copy(self) -> "Rect":
        return Rect(
            left=self.left,
            top=self.top,
            right=self.right,
            bottom=self.bottom,
            dleft=self.dleft,
            dtop=self.dtop,
            dright=self.dright,
            dbottom=self.dbottom,
        )

    @property
    def topBorder(self):
        return Border(self, "top")

    @property
    def bottomBorder(self):
        return Border(self, "bottom")

    @property
    def leftBorder(self):
        return Border(self, "left")

    @property
    def rightBorder(self):
        return Border(self, "right")


class Border:
    def __init__(self, rect: Rect, side: str):
        self.rect = rect
        self.side = side

    @property
    def x(self) -> int | None:
        if self.side == "left":
            return self.rect.left
        if self.side == "right":
            return self.rect.right
        return None

    @property
    def y(self) -> int | None:
        if self.side == "top":
            return self.rect.top
        if self.side == "bottom":
            return self.rect.bottom
        return None

    def isOn(self, point) -> bool:
        if not self.rect.visible:
            return False
        x = point.x if hasattr(point, "x") else point[0]
        y = point.y if hasattr(point, "y") else point[1]
        if self.side == "top":
            return self.rect.left - BORDER_TOLERANCE <= x <= self.rect.right + BORDER_TOLERANCE and abs(y - self.rect.top) <= BORDER_TOLERANCE
        if self.side == "bottom":
            return self.rect.left - BORDER_TOLERANCE <= x <= self.rect.right + BORDER_TOLERANCE and abs(y - self.rect.bottom) <= BORDER_TOLERANCE
        if self.side == "left":
            return self.rect.top - BORDER_TOLERANCE <= y <= self.rect.bottom + BORDER_TOLERANCE and abs(x - self.rect.left) <= BORDER_TOLERANCE
        if self.side == "right":
            return self.rect.top - BORDER_TOLERANCE <= y <= self.rect.bottom + BORDER_TOLERANCE and abs(x - self.rect.right) <= BORDER_TOLERANCE
        return False

    def move(self, point):
        if not self.rect.visible:
            return point
        x = point.x if hasattr(point, "x") else point[0]
        y = point.y if hasattr(point, "y") else point[1]
        if self.side in {"left", "right"}:
            old_top = self.rect.top - self.rect.dtop
            old_bottom = self.rect.bottom - self.rect.dbottom
            old_height = old_bottom - old_top
            if old_height == 0:
                return point
            dx = self.rect.dright if self.side == "right" else self.rect.dleft
            new_x = x + dx
            new_y = (y - old_top) * self.rect.height / old_height + self.rect.top
            if abs(new_x - x) >= 80 or abs(new_y - y) >= 80:
                return point
            return PointState(int(round(new_x)), int(round(new_y)))
        old_left = self.rect.left - self.rect.dleft
        old_right = self.rect.right - self.rect.dright
        old_width = old_right - old_left
        if old_width == 0:
            return point
        dy = self.rect.dbottom if self.side == "bottom" else self.rect.dtop
        new_x = (x - old_left) * self.rect.width / old_width + self.rect.left
        new_y = y + dy
        if abs(new_x - x) >= 80 or new_y - y > 20 or new_y - y < -80:
            return point
        return PointState(int(round(new_x)), int(round(new_y)))


class NullBorder:
    def isOn(self, _point) -> bool:
        return False

    def move(self, point):
        return point


NULL_BORDER = NullBorder()


class EnvironmentProvider:
    def __init__(self, window):
        self.window = window
        self.cursor = PointState()
        self.work_area = Rect()
        self.screen = Rect()
        self.screens: list[Rect] = []
        self.active_ie = Rect()
        self.active_ie_title = ""
        self.active_ie_hwnd = None
        self._active_ie_freeze_ticks = 0
        self.refresh()

    def refresh(self):
        work_area = get_work_area_rect(self.window) or Rect(
            left=0,
            top=0,
            right=self.window.winfo_screenwidth(),
            bottom=self.window.winfo_screenheight(),
        )
        screen = get_screen_rect(self.window) or Rect(
            left=0,
            top=0,
            right=self.window.winfo_screenwidth(),
            bottom=self.window.winfo_screenheight(),
        )
        self.work_area.update_from(work_area)
        self.screen.update_from(screen)
        self.screens = get_screen_rects() or [self.screen.copy()]
        cursor = get_cursor_state(self.cursor)
        self.cursor = cursor
        if self._active_ie_freeze_ticks > 0:
            self._active_ie_freeze_ticks -= 1
            return
        active_ie, active_ie_title, active_ie_hwnd = get_active_window_info(self.window)
        if self._is_usable_active_window(active_ie, active_ie_title):
            self.active_ie.update_from(active_ie)
            self.active_ie_title = active_ie_title
            self.active_ie_hwnd = active_ie_hwnd
        elif not self.active_ie.visible:
            self.active_ie.update_from(Rect())
            self.active_ie_title = ""
            self.active_ie_hwnd = None

    def freeze_active_ie(self, rect: Rect, title: str, ticks: int = 240):
        if not rect.visible:
            return
        self.active_ie.update_from(rect.copy())
        self.active_ie_title = title
        self._active_ie_freeze_ticks = max(1, int(ticks))

    def move_active_ie(self, left: int, top: int) -> bool:
        if not self.active_ie.visible:
            return False
        moved = self.active_ie.copy()
        moved.left = int(round(left))
        moved.top = int(round(top))
        moved.right = moved.left + self.active_ie.width
        moved.bottom = moved.top + self.active_ie.height
        moved_real_window = _move_window_rect(self.active_ie_hwnd, moved)
        self.active_ie.update_from(moved)
        if moved_real_window:
            self._active_ie_freeze_ticks = max(self._active_ie_freeze_ticks, 4)
        return moved_real_window

    def mascot_environment(self):
        return SimpleNamespace(
            workArea=self.work_area,
            screen=self.screen,
            activeIE=self.active_ie,
            cursor=self.cursor,
            floor=self.floor_border(),
            ceiling=self.ceiling_border(),
            wall=self.wall_border(getattr(self.window, "facing", -1) > 0),
        )

    def floor_border(self, ignore_separator: bool = False):
        anchor = self.window.anchor_point()
        if self.active_ie.topBorder.isOn(anchor):
            return self.active_ie.topBorder
        if self.work_area.bottomBorder.isOn(anchor):
            if ignore_separator or self.is_screen_top_bottom(anchor):
                return self.work_area.bottomBorder
        return NULL_BORDER

    def ceiling_border(self, ignore_separator: bool = False):
        anchor = self.window.anchor_point()
        if self.active_ie.bottomBorder.isOn(anchor):
            return self.active_ie.bottomBorder
        if self.work_area.topBorder.isOn(anchor):
            if ignore_separator or self.is_screen_top_bottom(anchor):
                return self.work_area.topBorder
        return NULL_BORDER

    def wall_border(self, look_right: bool, ignore_separator: bool = False):
        anchor = self.window.anchor_point()
        if look_right:
            if self.active_ie.leftBorder.isOn(anchor):
                return self.active_ie.leftBorder
            if self.work_area.rightBorder.isOn(anchor):
                if ignore_separator or self.is_screen_left_right(anchor):
                    return self.work_area.rightBorder
        else:
            if self.active_ie.rightBorder.isOn(anchor):
                return self.active_ie.rightBorder
            if self.work_area.leftBorder.isOn(anchor):
                if ignore_separator or self.is_screen_left_right(anchor):
                    return self.work_area.leftBorder
        return NULL_BORDER

    def is_screen_top_bottom(self, anchor=None) -> bool:
        anchor = anchor or self.window.anchor_point()
        return (
            self.work_area.visible
            and (anchor.y <= self.work_area.top + BORDER_TOLERANCE or anchor.y >= self.work_area.bottom - BORDER_TOLERANCE)
            and self._screen_edge_count(anchor, "horizontal") == 1
        )

    def is_screen_left_right(self, anchor=None) -> bool:
        anchor = anchor or self.window.anchor_point()
        return (
            self.work_area.visible
            and (anchor.x <= self.work_area.left + BORDER_TOLERANCE or anchor.x >= self.work_area.right - BORDER_TOLERANCE)
            and self._screen_edge_count(anchor, "vertical") == 1
        )

    def _is_usable_active_window(self, rect: Rect, title: str) -> bool:
        if not rect.visible:
            return False
        if not title:
            return False
        if title == "Program Manager":
            return False
        if self.screen.visible and not rect.intersects(self.screen):
            return False
        return not _matches_window_rect(self.window, rect)

    def _screen_edge_count(self, anchor, axis: str) -> int:
        count = 0
        for rect in getattr(self, "screens", None) or [self.screen]:
            if axis == "horizontal":
                if rect.topBorder.isOn(anchor):
                    count += 1
                if rect.bottomBorder.isOn(anchor):
                    count += 1
            else:
                if rect.leftBorder.isOn(anchor):
                    count += 1
                if rect.rightBorder.isOn(anchor):
                    count += 1
        if count == 0:
            if axis == "horizontal":
                return int(self.work_area.topBorder.isOn(anchor) or self.work_area.bottomBorder.isOn(anchor))
            return int(self.work_area.leftBorder.isOn(anchor) or self.work_area.rightBorder.isOn(anchor))
        return count


def get_work_area_rect(window=None):
    work_area = _get_window_monitor_work_area(window)
    if work_area:
        return work_area
    return _get_system_work_area()


def get_screen_rect(window=None):
    rect = _get_window_monitor_rect(window)
    if rect:
        return rect
    return get_work_area_rect(window)


def get_cursor_state(previous: PointState | None = None) -> PointState:
    try:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        point = POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            old = previous or PointState(point.x, point.y, 0.0, 0.0)
            return PointState(
                x=point.x,
                y=point.y,
                dx=point.x - old.x,
                dy=point.y - old.y,
            )
    except Exception:
        pass
    return previous or PointState()


def get_active_window_info(window=None):
    if _title_filters_configured():
        rect, title, hwnd = _get_interactive_window_info(window)
        if rect.visible:
            return rect, title, hwnd
    return _get_foreground_window_info(window)


def _get_interactive_window_info(window=None):
    try:
        user32 = ctypes.windll.user32
        result = {"rect": Rect(), "title": "", "hwnd": None}
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _data):
            rect, title, status = _window_candidate(hwnd, window)
            if status == "usable":
                result["rect"] = rect
                result["title"] = title
                result["hwnd"] = hwnd
                return False
            if status == "invalid":
                return False
            return True

        user32.EnumWindows(callback_type(callback), None)
        return result["rect"], result["title"], result["hwnd"]
    except Exception:
        return Rect(), "", None


def _get_foreground_window_info(window=None):
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return Rect(), "", None
        rect, title, status = _window_candidate(hwnd, window)
        if status == "usable":
            return rect, title, hwnd
        return Rect(), "", None
    except Exception:
        return Rect(), "", None


def _window_candidate(hwnd, window=None, allow_maximized: bool = False) -> tuple[Rect, str, str]:
    try:
        user32 = ctypes.windll.user32
        if not hwnd or not user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            return Rect(), "", "skip"
        if _is_window_cloaked(hwnd):
            return Rect(), "", "skip"
        if user32.IsIconic(ctypes.c_void_p(hwnd)):
            return Rect(), "", "skip"
        if not allow_maximized and user32.IsZoomed(ctypes.c_void_p(hwnd)):
            return Rect(), "", "invalid"
        title = _window_title(hwnd)
        if not _title_is_interactive(title):
            return Rect(), title, "skip"
        raw = _RECT()
        if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(raw)):
            return Rect(), title, "skip"
        rect = _rect_from_raw(raw)
        screen = get_screen_rect(window)
        if screen and not rect.intersects(screen):
            return rect, title, "skip"
        if _matches_window_rect(window, rect):
            return rect, title, "skip"
        return rect, title, "usable"
    except Exception:
        return Rect(), "", "skip"


def _move_window_rect(hwnd, rect: Rect) -> bool:
    if not hwnd or not rect.visible:
        return False
    try:
        flags = 0x0004 | 0x0010  # SWP_NOZORDER | SWP_NOACTIVATE
        return bool(
            ctypes.windll.user32.SetWindowPos(
                ctypes.c_void_p(hwnd),
                None,
                int(rect.left),
                int(rect.top),
                int(rect.width),
                int(rect.height),
                flags,
            )
        )
    except Exception:
        return False


def _window_title(hwnd) -> str:
    title = ctypes.create_unicode_buffer(1024)
    try:
        length = ctypes.windll.user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, len(title))
        return title.value[:length]
    except Exception:
        return ""


def _title_is_interactive(title: str) -> bool:
    if not title or title == "Program Manager":
        return False
    blacklist = _split_title_filter(os.environ.get("ATRI_PET_INTERACTIVE_WINDOWS_BLACKLIST", ""))
    blacklist.extend(DEFAULT_WINDOW_TITLE_BLACKLIST)
    if any(item in title for item in blacklist):
        return False
    whitelist = _split_title_filter(os.environ.get("ATRI_PET_INTERACTIVE_WINDOWS", ""))
    if whitelist:
        return any(item in title for item in whitelist)
    return True


def _title_filters_configured() -> bool:
    return bool(
        os.environ.get("ATRI_PET_INTERACTIVE_WINDOWS", "").strip()
        or os.environ.get("ATRI_PET_INTERACTIVE_WINDOWS_BLACKLIST", "").strip()
    )


def _split_title_filter(value: str) -> list[str]:
    return [item.strip() for item in value.split("/") if item.strip()]


def _is_window_cloaked(hwnd) -> bool:
    try:
        cloaked = ctypes.c_int(0)
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(hwnd),
            14,
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
        return result == 0 and cloaked.value != 0
    except Exception:
        return False


def _get_window_monitor_work_area(window):
    return _monitor_rect(window, work_area=True)


def _get_window_monitor_rect(window):
    return _monitor_rect(window, work_area=False)


def _matches_window_rect(window, rect: Rect) -> bool:
    if window is None:
        return False
    try:
        left = int(window.winfo_rootx())
        top = int(window.winfo_rooty())
        right = left + int(window.winfo_width())
        bottom = top + int(window.winfo_height())
    except Exception:
        return False
    return (
        abs(rect.left - left) <= BORDER_TOLERANCE
        and abs(rect.top - top) <= BORDER_TOLERANCE
        and abs(rect.right - right) <= BORDER_TOLERANCE
        and abs(rect.bottom - bottom) <= BORDER_TOLERANCE
    )


def _monitor_rect(window, work_area: bool):
    try:
        user32 = ctypes.windll.user32
        monitor = _monitor_from_anchor(window) or _monitor_from_window(window)
        if not monitor:
            return None
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return _rect_from_raw(info.rcWork if work_area else info.rcMonitor)
    except Exception:
        return None


def _monitor_from_anchor(window):
    if window is None:
        return None
    try:
        anchor = window.anchor_point()
        point = _POINT(int(anchor.x), int(anchor.y))
        return ctypes.windll.user32.MonitorFromPoint(point, 2)
    except Exception:
        return None


def _monitor_from_window(window):
    if window is None:
        return None
    try:
        return ctypes.windll.user32.MonitorFromWindow(ctypes.c_void_p(int(window.winfo_id())), 2)
    except Exception:
        return None


def _get_system_work_area():
    try:
        rect = _RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return _rect_from_raw(rect)
    except Exception:
        pass
    return None


def get_screen_rects() -> list[Rect]:
    try:
        rects: list[Rect] = []
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(_RECT),
            ctypes.c_void_p,
        )

        def callback(_monitor, _hdc, rect, _data):
            rects.append(_rect_from_raw(rect.contents))
            return True

        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(callback), None)
        return rects
    except Exception:
        return []


def _rect_from_raw(rect):
    return Rect(
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
    )
