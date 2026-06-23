import ctypes
from types import SimpleNamespace


def get_work_area_rect(window=None):
    work_area = _get_window_monitor_work_area(window)
    if work_area:
        return work_area

    return _get_system_work_area()


def get_work_area_bottom(window=None):
    work_area = get_work_area_rect(window)
    return work_area.bottom if work_area else None


def _get_window_monitor_work_area(window):
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
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = ctypes.c_int

        monitor = user32.MonitorFromWindow(ctypes.c_void_p(int(window.winfo_id())), 2)
        if monitor:
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return _rect_namespace(info.rcWork)
    except Exception:
        pass
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
            return _rect_namespace(rect)
    except Exception:
        pass
    return None


def _rect_namespace(rect):
    return SimpleNamespace(
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
        width=rect.right - rect.left,
        height=rect.bottom - rect.top,
    )
