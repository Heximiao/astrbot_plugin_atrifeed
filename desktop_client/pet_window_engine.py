import tkinter as tk
import logging
import json
import urllib.request

from behavior_engine import BehaviorEngine, TICK_MS
from chat_box_v2 import ChatBox
from drag_controller import DragController
from menu_labels import grouped_commands, manual_action_params, menu_label
from shimeji_runtime import ShimejiRuntime

try:
    from ui.qt_overlay import QtOverlayClient
except Exception:
    QtOverlayClient = None


TRANSPARENT_COLOR = "#ff00ff"
EDGE_BLEND_COLOR = "#f4f4f4"
ALPHA_VISIBLE_THRESHOLD = 36
LOGGER = logging.getLogger("atri_pet")


class PetWindow(tk.Tk):
    def __init__(self, asset_dir: str, api_url: str, debug_trace_enabled: bool = False):
        super().__init__()
        self.label = tk.Label(self, bd=0, bg=TRANSPARENT_COLOR)
        self.label.pack()
        self._last_image = None
        self._last_geometry = None
        self.bubble_window = tk.Toplevel(self)
        self.bubble_window.withdraw()
        self.bubble_window.overrideredirect(True)
        self.bubble_window.attributes("-topmost", True)
        self.bubble = tk.Label(self.bubble_window, bg="#fff8d8", fg="#222222", bd=1, relief=tk.SOLID)
        self.bubble.pack()
        self._bubble_visible_until = 0.0
        self.api_url = api_url.rstrip("/")
        self.pet_user_id = ""
        self.chat_box = ChatBox(self, api_url, self._on_reply, self._get_pet_user_id)
        self.overlay = None
        if QtOverlayClient:
            self.overlay = QtOverlayClient(api_url, self._on_reply, self._on_overlay_command)
            if not self.overlay.start():
                LOGGER.info("qt overlay unavailable, falling back to tkinter ui")
                self.overlay = None
            else:
                LOGGER.info("qt overlay started")

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=TRANSPARENT_COLOR)
        self.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.anchor_x = 100
        self.anchor_y = 300
        self.facing = -1
        self.mood = "normal"
        self.mascot_total_count = 1
        self.current_action_name = ""
        self.runtime = ShimejiRuntime(self)
        self.drag = DragController(self)
        self.engine = BehaviorEngine(self, asset_dir, debug_trace_enabled=debug_trace_enabled)

        self.bind("<ButtonPress-1>", self.drag.start)
        self.bind("<B1-Motion>", self.drag.drag)
        self.bind("<ButtonRelease-1>", self.drag.end)
        self.bind("<Double-Button-1>", self._open_chat)
        self.bind("<Button-3>", self._menu)

        self.geometry("+100+300")
        self.after(50, self.engine.preload_all_images)
        self.after(300, self._fetch_user)
        self.after(1000, self._fetch_state)
        self.after(30, self._poll_overlay)
        self.after(TICK_MS, self._tick)

    def load_image(self, path: str, mirrored: bool = False):
        try:
            from PIL import Image, ImageOps, ImageTk

            image = Image.open(path).convert("RGBA")
            if mirrored:
                image = ImageOps.mirror(image)
            keyed = Image.new("RGB", image.size, TRANSPARENT_COLOR)
            edge_bg = Image.new("RGBA", image.size, EDGE_BLEND_COLOR)
            visible = Image.alpha_composite(edge_bg, image).convert("RGB")
            alpha = image.getchannel("A").point(
                lambda value: 255 if value >= ALPHA_VISIBLE_THRESHOLD else 0
            )
            keyed.paste(visible, mask=alpha)
            return ImageTk.PhotoImage(keyed)
        except Exception:
            return tk.PhotoImage(file=path)

    def set_image(self, image):
        if image is self._last_image:
            return
        self.label.configure(image=image)
        self.label.image = image
        self._last_image = image

    def anchor_point(self):
        return type("AnchorPoint", (), {"x": int(round(self.anchor_x)), "y": int(round(self.anchor_y))})()

    def set_anchor(self, x: float, y: float):
        self.anchor_x = float(x)
        self.anchor_y = float(y)

    def place_from_anchor(self, frame_anchor_x: int, frame_anchor_y: int):
        x = self.anchor_x - frame_anchor_x
        y = self.anchor_y - frame_anchor_y
        geometry = f"+{int(round(x))}+{int(round(y))}"
        if geometry == self._last_geometry:
            return
        self.geometry(geometry)
        self._last_geometry = geometry

    def current_frame_anchor(self):
        return self.engine.current_frame_anchor()

    def set_facing(self, facing: int):
        self.facing = 1 if facing > 0 else -1

    def set_dragging(self, dragging: bool):
        if not dragging:
            self.drag.offset = None

    def _tick(self):
        self.engine.tick()
        self._sync_overlay_bubble()
        self.after(TICK_MS, self._tick)

    def _fetch_state(self):
        try:
            with urllib.request.urlopen(f"{self.api_url}/pet/state", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.mood = data.get("mood", self.mood)
            self.engine.set_external_state(data)
        except Exception:
            pass
        self.after(30000, self._fetch_state)

    def _open_chat(self, _=None):
        if self._overlay_available():
            self.overlay.show_chat(self.winfo_x(), max(0, self.winfo_y() - 120))
            return
        self.chat_box.open_near(self.winfo_x(), max(0, self.winfo_y() - 120))

    def _menu(self, event):
        self.engine.manual_commands.capture_environment()
        self._fetch_user()
        if self._overlay_available():
            groups = [
                (label, [(name, menu_label(name)) for name in names])
                for label, names in grouped_commands(self.engine.available_commands())
            ]
            self.overlay.show_menu(event.x_root, event.y_root, groups, self.pet_user_id)
            return
        menu = tk.Menu(self, tearoff=False)
        user_menu = tk.Menu(menu, tearoff=False)
        self._populate_user_menu(user_menu)
        menu.add_cascade(label="桌宠 QQ", menu=user_menu)
        action_menu = tk.Menu(menu, tearoff=False)
        self._populate_action_menu(action_menu)
        menu.add_cascade(label="动作选项", menu=action_menu)
        menu.add_command(label="聊天", command=self._open_chat)
        menu.add_command(label="退出", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def _play_manual_action(self, name: str):
        params = self._manual_action_params(name)
        self.engine.force_manual_command(name, **params)

    def _on_overlay_command(self, name: str):
        if name == "__quit__":
            self.destroy()
            return
        if name == "__set_user_id__":
            self._open_user_dialog()
            return
        if name == "__refresh_user_id__":
            self._fetch_user()
            return
        if name:
            self._play_manual_action(name)

    def _get_pet_user_id(self) -> str:
        return self.pet_user_id

    def _fetch_user(self):
        try:
            with urllib.request.urlopen(f"{self.api_url}/pet/user", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.pet_user_id = data.get("user_id", "") or ""
        except Exception:
            pass

    def _save_user_id(self, user_id: str, on_done=None):
        import threading

        def worker():
            ok = False
            reply = ""
            try:
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
                self.pet_user_id = data.get("user_id", "") or self.pet_user_id
                reply = "已保存桌宠 QQ。" if ok else data.get("error", "QQ 号保存失败。")
            except Exception:
                reply = "Cannot connect to plugin service right now."
            self.after(0, self._finish_save_user_id, ok, reply, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_save_user_id(self, ok: bool, reply: str, on_done):
        if on_done:
            on_done(ok, reply)
        self._on_reply(reply, "idle")
        if ok:
            self._fetch_state()

    def _poll_overlay(self):
        if self._overlay_available():
            self.overlay.poll()
        self.after(30, self._poll_overlay)

    def _overlay_available(self) -> bool:
        if not self.overlay or not self.overlay.available:
            return False
        if not self.overlay.is_running():
            LOGGER.warning("qt overlay stopped, falling back to tkinter ui")
            self.overlay.available = False
            return False
        return True

    def _populate_action_menu(self, menu: tk.Menu):
        for label, names in grouped_commands(self.engine.available_commands()):
            self._add_command_group(menu, label, names)

    def _populate_user_menu(self, menu: tk.Menu):
        menu.add_command(label="当前 QQ：" + (self.pet_user_id or "未填写"), state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="填写/修改 QQ", command=self._open_user_dialog)

    def _open_user_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("桌宠 QQ")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.geometry(f"280x92+{self.winfo_rootx()}+{max(0, self.winfo_rooty() - 100)}")
        entry = tk.Entry(dialog, font=("Microsoft YaHei UI", 10))
        entry.insert(0, self.pet_user_id)
        entry.pack(fill=tk.X, padx=10, pady=(10, 6))

        def save():
            self._save_user_id(entry.get().strip(), lambda ok, _reply: dialog.destroy() if ok else None)

        button = tk.Button(dialog, text="保存", command=save)
        button.pack(anchor=tk.E, padx=10)
        entry.bind("<Return>", lambda _event: save())
        entry.focus_set()

    def _add_command_group(self, menu: tk.Menu, label: str, names: list[str]):
        group = tk.Menu(menu, tearoff=False)
        for name in names:
            group.add_command(label=menu_label(name), command=lambda n=name: self._play_manual_action(n))
        menu.add_cascade(label=label, menu=group)

    def _manual_action_params(self, name: str) -> dict[str, object]:
        return manual_action_params(
            name,
            self.anchor_point(),
            self.facing,
            self.runtime.environment_provider.work_area,
        )

    def _on_reply(self, reply: str, action: str):
        self.engine.force_action(action or "idle")
        if self._overlay_available():
            import time

            self._bubble_visible_until = time.monotonic() + 6
            self.overlay.show_bubble(reply, self.winfo_rootx(), self.winfo_rooty())
            return
        wraplength = min(360, max(160, len(reply) * 12))
        self.bubble.configure(text=reply, wraplength=wraplength, justify=tk.LEFT, padx=8, pady=5)
        self.bubble.update_idletasks()
        bubble_width = self.bubble.winfo_reqwidth()
        bubble_height = self.bubble.winfo_reqheight()
        x = self.winfo_rootx()
        y = max(0, self.winfo_rooty() - bubble_height - 8)
        self.bubble_window.geometry(f"{bubble_width}x{bubble_height}+{x}+{y}")
        self.bubble_window.deiconify()
        self.bubble_window.lift()
        self.after(6000, self.bubble_window.withdraw)

    def _sync_overlay_bubble(self):
        if not self._overlay_available() or self._bubble_visible_until <= 0:
            return
        import time

        if time.monotonic() >= self._bubble_visible_until:
            self._bubble_visible_until = 0
            return
        self.overlay.move_bubble(self.winfo_rootx(), self.winfo_rooty())

    def destroy(self):
        if self.overlay:
            self.overlay.stop()
        super().destroy()
