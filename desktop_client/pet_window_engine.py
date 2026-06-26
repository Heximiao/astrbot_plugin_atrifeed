import tkinter as tk

from behavior_engine import BehaviorEngine, TICK_MS
from chat_box_v2 import ChatBox
from drag_controller import DragController
from menu_labels import grouped_commands, manual_action_params, menu_label
from shimeji_runtime import ShimejiRuntime


TRANSPARENT_COLOR = "#ff00ff"
EDGE_BLEND_COLOR = "#f4f4f4"
ALPHA_VISIBLE_THRESHOLD = 36


class PetWindow(tk.Tk):
    def __init__(self, asset_dir: str, api_url: str, debug_trace_enabled: bool = False):
        super().__init__()
        self.label = tk.Label(self, bd=0, bg=TRANSPARENT_COLOR)
        self.label.pack()
        self._last_image = None
        self._last_geometry = None
        self.bubble = tk.Label(self, bg="#fff8d8", fg="#222222", bd=1, relief=tk.SOLID, wraplength=220)
        self.chat_box = ChatBox(self, api_url, self._on_reply)

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
        self.after(1000, self._fetch_state)
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
        self.after(TICK_MS, self._tick)

    def _fetch_state(self):
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(f"{self.chat_box.api_url}/pet/state", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.mood = data.get("mood", self.mood)
            self.engine.set_external_state(data)
        except Exception:
            pass
        self.after(30000, self._fetch_state)

    def _open_chat(self, _=None):
        self.chat_box.open_near(self.winfo_x(), max(0, self.winfo_y() - 120))

    def _menu(self, event):
        self.engine.manual_commands.capture_environment()
        menu = tk.Menu(self, tearoff=False)
        action_menu = tk.Menu(menu, tearoff=False)
        self._populate_action_menu(action_menu)
        menu.add_cascade(label="动作选项", menu=action_menu)
        menu.add_command(label="聊天", command=self._open_chat)
        menu.add_command(label="退出", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def _play_manual_action(self, name: str):
        params = self._manual_action_params(name)
        self.engine.force_manual_command(name, **params)

    def _populate_action_menu(self, menu: tk.Menu):
        for label, names in grouped_commands(self.engine.available_commands()):
            self._add_command_group(menu, label, names)

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
        self.bubble.configure(text=reply)
        self.bubble.place(x=0, y=0)
        self.after(6000, self.bubble.place_forget)
