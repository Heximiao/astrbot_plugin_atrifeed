import ctypes
from dataclasses import dataclass
from types import SimpleNamespace


BORDER_TOLERANCE = 6


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

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def visible(self) -> bool:
        return self.width > 0 and self.height > 0

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

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


class NullBorder:
    def isOn(self, _point) -> bool:
        return False


NULL_BORDER = NullBorder()


class EnvironmentProvider:
    def __init__(self, window):
        self.window = window
        self.cursor = PointState()
        self.work_area = Rect()
        self.screen = Rect()
        self.active_ie = Rect()
        self.active_ie_title = ""
        self.refresh()

    def refresh(self):
        self.work_area = get_work_area_rect(self.window) or Rect(
            left=0,
            top=0,
            right=self.window.winfo_screenwidth(),
            bottom=self.window.winfo_screenheight(),
        )
        self.screen = get_screen_rect(self.window) or Rect(
            left=0,
            top=0,
            right=self.window.winfo_screenwidth(),
            bottom=self.window.winfo_screenheight(),
        )
        cursor = get_cursor_state(self.cursor)
        self.cursor = cursor
        self.active_ie, self.active_ie_title = get_active_window_rect()

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
            self.screen.visible
            and self.work_area.visible
            and self.screen.left <= anchor.x <= self.screen.right
            and (anchor.y <= self.work_area.top + BORDER_TOLERANCE or anchor.y >= self.work_area.bottom - BORDER_TOLERANCE)
        )

    def is_screen_left_right(self, anchor=None) -> bool:
        anchor = anchor or self.window.anchor_point()
        return (
            self.screen.visible
            and self.work_area.visible
            and self.screen.top <= anchor.y <= self.screen.bottom
            and (anchor.x <= self.work_area.left + BORDER_TOLERANCE or anchor.x >= self.work_area.right - BORDER_TOLERANCE)
        )


def get_work_area_rect(window=None):
    work_area = _get_window_monitor_work_area(window)
    if work_area:
        return work_area
    return _get_system_work_area()


def get_work_area_bottom(window=None):
    work_area = get_work_area_rect(window)
    return work_area.bottom if work_area else None


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


def get_active_window_rect() -> tuple[Rect, str]:
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return Rect(), ""
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return Rect(), ""
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, len(title))
        return _rect_from_raw(rect), title.value
    except Exception:
        return Rect(), ""


def _get_window_monitor_work_area(window):
    return _monitor_rect(window, work_area=True)


def _get_window_monitor_rect(window):
    return _monitor_rect(window, work_area=False)


def _monitor_rect(window, work_area: bool):
    if window is None:
        return None
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong),
            ]

        user32 = ctypes.windll.user32
        monitor = user32.MonitorFromWindow(ctypes.c_void_p(int(window.winfo_id())), 2)
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return _rect_from_raw(info.rcWork if work_area else info.rcMonitor)
    except Exception:
        return None


def _get_system_work_area():
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return _rect_from_raw(rect)
    except Exception:
        pass
    return None


def _rect_from_raw(rect):
    return Rect(
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
    )
