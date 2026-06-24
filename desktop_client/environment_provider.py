import ctypes
from dataclasses import dataclass
from types import SimpleNamespace


BORDER_TOLERANCE = 6
GA_ROOT = 2
GW_HWNDNEXT = 2
SYSTEM_WINDOW_TITLES = {
    "Program Manager",
    "Windows 输入体验",
    "Windows Input Experience",
}


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
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
        active_ie, active_ie_title = get_active_window_rect(self.window)
        if self._is_usable_active_window(active_ie, active_ie_title):
            self.active_ie = active_ie
            self.active_ie_title = active_ie_title
        elif not self.active_ie.visible:
            self.active_ie = Rect()
            self.active_ie_title = ""

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

    def _is_usable_active_window(self, rect: Rect, title: str) -> bool:
        if not rect.visible:
            return False
        if not title:
            return False
        return not _matches_window_rect(self.window, rect)


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


def get_active_window_rect(window=None) -> tuple[Rect, str]:
    try:
        user32 = ctypes.windll.user32
        nearest = _find_nearest_active_window(user32, window)
        if nearest is not None:
            return nearest
    except Exception:
        pass
    return Rect(), ""


def _get_window_monitor_work_area(window):
    return _monitor_rect(window, work_area=True)


def _get_window_monitor_rect(window):
    return _monitor_rect(window, work_area=False)


def _is_own_window(window, hwnd) -> bool:
    if window is None:
        return False
    try:
        own_hwnd = int(window.winfo_id())
        if int(hwnd) == own_hwnd:
            return True
        user32 = ctypes.windll.user32
        root_hwnd = user32.GetAncestor(ctypes.c_void_p(int(hwnd)), GA_ROOT)
        return bool(root_hwnd and int(root_hwnd) == own_hwnd)
    except Exception:
        return False


def _active_window_from_hwnd(user32, hwnd, window) -> tuple[Rect, str] | None:
    if not hwnd or _is_own_window(window, hwnd):
        return None
    if not user32.IsWindowVisible(ctypes.c_void_p(int(hwnd))):
        return None
    if hasattr(user32, "IsIconic") and user32.IsIconic(ctypes.c_void_p(int(hwnd))):
        return None
    if hasattr(user32, "IsZoomed") and user32.IsZoomed(ctypes.c_void_p(int(hwnd))):
        return None
    length = user32.GetWindowTextLengthW(ctypes.c_void_p(int(hwnd)))
    if length <= 0:
        return None
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(ctypes.c_void_p(int(hwnd)), title, len(title))
    if _is_system_window_title(title.value):
        return None
    rect = _RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(int(hwnd)), ctypes.byref(rect)):
        return None
    parsed = _rect_from_raw(rect)
    if not parsed.visible or _matches_window_rect(window, parsed):
        return None
    if _is_desktop_sized_window(window, parsed):
        return None
    return parsed, title.value


def _find_next_active_window(user32, hwnd, window) -> tuple[Rect, str] | None:
    if hwnd:
        candidate = user32.GetWindow(ctypes.c_void_p(int(hwnd)), GW_HWNDNEXT)
    else:
        candidate = user32.GetTopWindow(None)
    for _ in range(100):
        if not candidate:
            return None
        active = _active_window_from_hwnd(user32, candidate, window)
        if active is not None:
            return active
        candidate = user32.GetWindow(ctypes.c_void_p(int(candidate)), GW_HWNDNEXT)
    return None


def _find_nearest_active_window(user32, window) -> tuple[Rect, str] | None:
    candidates: list[tuple[int, tuple[Rect, str]]] = []

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _data):
        active = _active_window_from_hwnd(user32, hwnd, window)
        if active is not None:
            candidates.append((_active_window_score(window, active[0]), active))
        return True

    if not user32.EnumWindows(callback_type(callback), None):
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _active_window_score(window, rect: Rect) -> int:
    if window is None:
        return 0
    try:
        point = window.anchor_point()
        x = int(point.x)
        y = int(point.y)
    except Exception:
        return 0
    dx = 0
    if x < rect.left:
        dx = rect.left - x
    elif x > rect.right:
        dx = x - rect.right
    dy = 0
    if y < rect.top:
        dy = rect.top - y
    elif y > rect.bottom:
        dy = y - rect.bottom
    return dx * dx + dy * dy


def _is_system_window_title(title: str) -> bool:
    return title.strip() in SYSTEM_WINDOW_TITLES


def _is_desktop_sized_window(window, rect: Rect) -> bool:
    screen = get_screen_rect(window)
    if screen is None or not screen.visible:
        return False
    covers_width = rect.left <= screen.left + BORDER_TOLERANCE and rect.right >= screen.right - BORDER_TOLERANCE
    covers_height = rect.top <= screen.top + BORDER_TOLERANCE and rect.bottom >= screen.bottom - BORDER_TOLERANCE
    return covers_width and covers_height


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
