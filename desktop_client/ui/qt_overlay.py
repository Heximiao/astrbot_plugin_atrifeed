from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import threading

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pet_api_client import get_pet_user, request_chat, save_pet_user


class QtOverlayClient:
    def __init__(self, api_url: str, on_reply, on_command):
        self.api_url = api_url.rstrip("/")
        self.on_reply = on_reply
        self.on_command = on_command
        self._events: mp.Queue = mp.Queue()
        self._results: mp.Queue = mp.Queue()
        self._process: mp.Process | None = None
        self.available = False

    def start(self) -> bool:
        self._process = mp.Process(
            target=_run_qt_overlay,
            args=(self.api_url, self._events, self._results),
            daemon=True,
        )
        self._process.start()
        self.available = True
        return True

    def poll(self):
        if not self.available:
            return
        if not self.is_running():
            self.available = False
            return
        while True:
            try:
                event = self._results.get_nowait()
            except queue.Empty:
                break
            kind = event.get("kind")
            if kind == "reply":
                self.on_reply(event.get("reply", "OK."), event.get("action", "idle"))
            elif kind == "command":
                self.on_command(event.get("name", ""))

    def show_chat(self, x: int, y: int):
        self._send({"kind": "chat", "x": x, "y": y})

    def show_bubble(self, text: str, x: int, y: int):
        self._send({"kind": "bubble", "text": text, "x": x, "y": y})

    def move_bubble(self, x: int, y: int):
        self._send({"kind": "bubble_move", "x": x, "y": y})

    def show_menu(self, x: int, y: int, groups: list[tuple[str, list[tuple[str, str]]]], user_id: str = ""):
        self._send({"kind": "menu", "x": x, "y": y, "groups": groups, "user_id": user_id})

    def stop(self):
        self._send({"kind": "quit"})
        if self._process and self._process.is_alive():
            self._process.join(timeout=0.5)
        self.available = False

    def _send(self, event: dict):
        if self.available and self.is_running():
            self._events.put(event)
        else:
            self.available = False

    def is_running(self) -> bool:
        return bool(self._process and self._process.is_alive())


def _run_qt_overlay(api_url: str, events: mp.Queue, results: mp.Queue):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_STYLE)

    chat = _ChatWindow(api_url, results)
    user_editor = _UserWindow(api_url, results)
    bubble = _BubbleWindow()
    active_menus = []
    outside_click = _OutsideClickWatcher()

    def show_menu(event: dict):
        _close_menus(active_menus)
        menu = QMenu()
        active_menus.append(menu)
        menu.aboutToHide.connect(lambda m=menu: _release_menu(active_menus, m))
        menu.addAction("聊天").triggered.connect(
            lambda: chat.show_near(event.get("x", 100), max(0, event.get("y", 100) - 118))
        )
        user_id = event.get("user_id", "") or ""
        menu.addAction("当前 QQ：" + (user_id or "未填写")).setEnabled(False)
        menu.addAction("填写/修改 QQ").triggered.connect(
            lambda uid=user_id: user_editor.show_near(event.get("x", 100), max(0, event.get("y", 100) - 118), uid)
        )
        menu.addSeparator()
        for group_label, items in event.get("groups", []):
            group = menu.addMenu(group_label)
            active_menus.append(group)
            group.aboutToHide.connect(lambda m=group: _release_menu(active_menus, m))
            for command_name, label in items:
                action = QAction(label, group)
                action.triggered.connect(lambda _=False, name=command_name: results.put({"kind": "command", "name": name}))
                group.addAction(action)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(lambda: results.put({"kind": "command", "name": "__quit__"}))
        menu.popup(QPoint(event.get("x", 100), event.get("y", 100)))
        outside_click.arm_after_release()

    def _release_menu(menus: list[QMenu], menu: QMenu):
        if menu in menus:
            menus.remove(menu)

    def _close_menus(menus: list[QMenu]):
        for menu in list(menus):
            menu.close()
            menu.deleteLater()
        menus.clear()

    def pump():
        if active_menus and outside_click.clicked_outside(active_menus):
            _close_menus(active_menus)
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("kind")
            if kind == "chat":
                chat.show_near(event.get("x", 100), event.get("y", 100))
            elif kind == "bubble":
                bubble.show_text(event.get("text", ""), event.get("x", 100), event.get("y", 100))
            elif kind == "bubble_move":
                bubble.move_near(event.get("x", 100), event.get("y", 100))
            elif kind == "menu":
                show_menu(event)
            elif kind == "quit":
                app.quit()
        chat.poll_done()
        user_editor.poll_done()

    timer = QTimer()
    timer.timeout.connect(pump)
    timer.start(30)
    app.exec()


class _OutsideClickWatcher:
    def __init__(self):
        self.waiting_for_release = False
        self._last_down = False

        if os.name == "nt":
            import ctypes

            self._get_key_state = ctypes.windll.user32.GetAsyncKeyState
        else:
            self._get_key_state = None

    def arm_after_release(self):
        self.waiting_for_release = True
        self._last_down = self._buttons_down()

    def clicked_outside(self, menus: list[QMenu]) -> bool:
        down = self._buttons_down()
        if self.waiting_for_release:
            if not down:
                self.waiting_for_release = False
            self._last_down = down
            return False

        started_click = down and not self._last_down
        self._last_down = down
        if not started_click:
            return False

        pos = QCursor.pos()
        return not any(menu.isVisible() and menu.geometry().contains(pos) for menu in menus)

    def _buttons_down(self) -> bool:
        if self._get_key_state:
            return bool(self._get_key_state(0x01) & 0x8000 or self._get_key_state(0x02) & 0x8000)
        buttons = QApplication.mouseButtons()
        return bool(buttons & (Qt.LeftButton | Qt.RightButton))


class _ChatWindow(QWidget):
    def __init__(self, api_url: str, results: mp.Queue):
        super().__init__()

        self.api_url = api_url
        self.results = results
        self.done: queue.Queue = queue.Queue()
        self.busy = False
        self.user_id = ""
        self.setWindowTitle("ATRI")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        panel = QFrame()
        panel.setObjectName("panel")
        root.addWidget(panel)

        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 12, 14, 14)
        box.setSpacing(10)
        title_bar = _TitleBar(self)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("想和我说什么？")
        self.entry.returnPressed.connect(self.send)
        self.button = QPushButton("发送")
        self.button.clicked.connect(self.send)

        row = QHBoxLayout()
        row.addWidget(self.entry, 1)
        row.addWidget(self.button)
        box.addWidget(title_bar)
        box.addLayout(row)
        self.resize(390, 112)

    def show_near(self, x: int, y: int):
        self._refresh_user_id()
        self.move(x, max(0, y))
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()

    def send(self):
        text = self.entry.text().strip()
        if self.busy or not text:
            return
        self.entry.clear()
        self._set_busy(True)
        threading.Thread(target=self._request_chat_worker, args=(text,), daemon=True).start()

    def _request_chat_worker(self, message: str):
        try:
            reply, action = request_chat(self.api_url, message, self.user_id)
        except Exception:
            reply = "Cannot connect to plugin service right now."
            action = "sit"
        self.done.put({"kind": "reply", "reply": reply, "action": action})

    def _refresh_user_id(self):
        try:
            self.user_id = get_pet_user(self.api_url)
        except Exception:
            pass

    def poll_done(self):
        while True:
            try:
                event = self.done.get_nowait()
            except queue.Empty:
                break
            self.results.put(event)
            self._set_busy(False)

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.button.setEnabled(not busy)
        self.button.setText("..." if busy else "发送")


class _UserWindow(QWidget):
    def __init__(self, api_url: str, results: mp.Queue):
        super().__init__()

        self.api_url = api_url
        self.results = results
        self.done: queue.Queue = queue.Queue()
        self.busy = False
        self.setWindowTitle("桌宠 QQ")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        panel = QFrame()
        panel.setObjectName("panel")
        root.addWidget(panel)

        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 12, 14, 14)
        box.setSpacing(10)
        title_bar = _TitleBar(self, title_text="桌宠 QQ")
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("填写使用桌宠的 QQ 号")
        self.entry.returnPressed.connect(self.save)
        self.button = QPushButton("保存")
        self.button.clicked.connect(self.save)

        row = QHBoxLayout()
        row.addWidget(self.entry, 1)
        row.addWidget(self.button)
        box.addWidget(title_bar)
        box.addLayout(row)
        self.resize(360, 112)

    def show_near(self, x: int, y: int, user_id: str = ""):
        self.entry.setText(user_id or self._current_user_id())
        self.move(x, max(0, y))
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()
        self.entry.selectAll()

    def save(self):
        if self.busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._request_save, args=(self.entry.text().strip(),), daemon=True).start()

    def _request_save(self, user_id: str):
        try:
            ok, reply, _user_id = save_pet_user(self.api_url, user_id)
            self.done.put({"ok": ok, "reply": reply})
            return
            payload = json.dumps({"user_id": user_id}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_url}/pet/user",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ok = bool(data.get("ok"))
            reply = "已保存桌宠 QQ。" if ok else data.get("error", "QQ 号保存失败。")
        except Exception:
            ok = False
            reply = "Cannot connect to plugin service right now."
        self.done.put({"ok": ok, "reply": reply})

    def _current_user_id(self) -> str:
        try:
            return get_pet_user(self.api_url)
            with urllib.request.urlopen(f"{self.api_url}/pet/user", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("user_id", "") or ""
        except Exception:
            return ""

    def poll_done(self):
        while True:
            try:
                event = self.done.get_nowait()
            except queue.Empty:
                break
            self._set_busy(False)
            if event.get("ok"):
                self.hide()
                self.results.put({"kind": "command", "name": "__refresh_user_id__"})
            self.results.put({"kind": "reply", "reply": event.get("reply", ""), "action": "idle"})

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.button.setEnabled(not busy)
        self.button.setText("..." if busy else "保存")


class _TitleBar(QWidget):
    def __init__(self, window: QWidget, title_text: str = "ATRI"):
        super().__init__(window)
        self.window = window
        self._drag_offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(title_text)
        title.setObjectName("title")
        close_button = QToolButton()
        close_button.setObjectName("closeButton")
        close_button.setText("×")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(window.hide)

        layout.addWidget(title, 1)
        layout.addWidget(close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class _BubbleWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        self.panel = QLabel()
        self.panel.setObjectName("bubble")
        self.panel.setWordWrap(True)
        root.addWidget(self.panel)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_text(self, text: str, x: int, y: int):
        self.panel.setText(text)
        self.panel.setMaximumWidth(380)
        self.adjustSize()
        self.move_near(x, y, force=True)
        self.show()
        self.raise_()
        self.timer.start(6000)

    def move_near(self, x: int, y: int, force: bool = False):
        if force or self.isVisible():
            self.move(x, max(0, y - self.height() - 8))


_STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    color: #2b2b32;
}
QFrame#panel, QLabel#bubble, QMenu {
    background: rgba(255, 252, 246, 238);
    border: 1px solid rgba(82, 92, 120, 42);
    border-radius: 14px;
}
QLabel#title {
    color: #52627a;
    font-size: 13px;
    font-weight: 700;
}
QLabel#bubble {
    padding: 10px 13px;
    font-size: 13px;
    line-height: 1.45;
}
QLineEdit {
    background: rgba(255, 255, 255, 235);
    border: 1px solid rgba(82, 92, 120, 36);
    border-radius: 10px;
    padding: 8px 10px;
    min-height: 22px;
}
QLineEdit:focus {
    border-color: rgba(91, 130, 196, 150);
}
QToolButton#closeButton {
    background: transparent;
    color: #738096;
    border: 0;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 700;
    min-width: 26px;
    min-height: 24px;
}
QToolButton#closeButton:hover {
    background: rgba(214, 96, 96, 32);
    color: #b44747;
}
QPushButton {
    background: #6f98d6;
    color: white;
    border: 0;
    border-radius: 10px;
    padding: 8px 14px;
    min-width: 54px;
}
QPushButton:hover {
    background: #5f89c6;
}
QPushButton:disabled {
    background: #aeb8c8;
}
QMenu {
    padding: 8px;
}
QMenu::item {
    padding: 7px 26px 7px 13px;
    border-radius: 8px;
}
QMenu::item:selected {
    background: rgba(111, 152, 214, 45);
}
QMenu::separator {
    height: 1px;
    background: rgba(82, 92, 120, 32);
    margin: 7px 4px;
}
"""
