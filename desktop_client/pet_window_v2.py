import random
import tkinter as tk

from action_registry_v2 import ActionRegistry
from animation_player import AnimationPlayer
from chat_box_v2 import ChatBox
from drag_controller import DragController
from movement_controller import MovementController, TICK_MS
from shimeji_runtime import ShimejiRuntime


TRANSPARENT_COLOR = "#ff00ff"
EDGE_BLEND_COLOR = "#f4f4f4"
ALPHA_VISIBLE_THRESHOLD = 36
UNINTERRUPTIBLE_ACTIONS = {"fall"}

BEHAVIOR_WEIGHTS = {
    "happy": {"idle": 20, "walk": 25, "sit": 15, "jump": 10, "sing": 10, "crawl": 5, "sleep": 2},
    "normal": {"idle": 30, "walk": 25, "sit": 20, "lie": 8, "crawl": 5, "sleep": 5},
    "sad": {"idle": 20, "sit": 30, "lie": 20, "sleep": 15, "walk": 5},
    "angry": {"idle": 30, "walk": 10, "jump": 5, "sit": 10},
}


class PetWindow(tk.Tk):
    def __init__(self, asset_dir: str, api_url: str):
        super().__init__()
        self.registry = ActionRegistry(asset_dir)
        self.player = AnimationPlayer(self, self.registry)
        self.label = tk.Label(self, bd=0, bg=TRANSPARENT_COLOR)
        self.label.pack()
        self.bubble = tk.Label(self, bg="#fff8d8", fg="#222222", bd=1, relief=tk.SOLID, wraplength=220)
        self.chat_box = ChatBox(self, api_url, self._on_reply)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=TRANSPARENT_COLOR)
        self.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.runtime = ShimejiRuntime(self)
        self.movement = MovementController(self)
        self.drag = DragController(self)
        self.vy = 0
        self.fall_target_y = None
        self.move_x = 100.0
        self.move_y = 300.0
        self.facing = -1
        self.mood = "normal"
        self.next_behavior_ms = 5000
        self.manual_action_locked = False
        self.bind("<ButtonPress-1>", self.drag.start)
        self.bind("<B1-Motion>", self.drag.drag)
        self.bind("<ButtonRelease-1>", self.drag.end)
        self.bind("<Double-Button-1>", self._open_chat)
        self.bind("<Button-3>", self._menu)

        self.geometry("+100+300")
        self.player.play("idle")
        self.after(50, self.player.preload_all_images)
        self.after(1000, self._fetch_state)
        self._schedule_behavior()
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
        self.label.configure(image=image)
        self.label.image = image

    def _tick(self):
        self.drag.settle_animation()
        self.player.tick()
        self.movement.move()
        self.after(TICK_MS, self._tick)

    def place_at(self, x: float, y: float):
        self.move_x, self.move_y = x, y
        self.geometry(f"+{int(round(x))}+{int(round(y))}")

    def set_facing(self, facing: int):
        facing = 1 if facing > 0 else -1
        if facing != self.facing:
            self.facing = facing
            self.player.refresh_frame()

    def set_facing_from_param(self, value: str | None):
        if value is None:
            self.set_facing(-self.facing)
            return
        result = self.eval_action_bool(value)
        self.set_facing(1 if result else -1)

    def offset_by(self, dx: float, dy: float):
        self.place_at(self.move_x + dx, self.move_y + dy)

    def eval_action_bool(self, value: str | None, default: bool = False, variables: dict | None = None) -> bool:
        return self.runtime.eval_bool(value, default=default, variables=variables)

    def eval_action_value(self, value: str | None, default=None, variables: dict | None = None):
        return self.runtime.eval_value(value, default=default, variables=variables)

    def _fetch_state(self):
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(f"{self.chat_box.api_url}/pet/state", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.mood = data.get("mood", self.mood)
            if not self._is_action_locked():
                self.player.play(data.get("recommended_action", "idle"))
        except Exception:
            pass
        self.after(30000, self._fetch_state)

    def _schedule_behavior(self):
        if self._is_action_locked():
            self.next_behavior_ms = 1000
            self.after(self.next_behavior_ms, self._schedule_behavior)
            return

        ground_weights = self.registry.ground_choices()
        if ground_weights:
            actions, values = zip(*ground_weights.items())
            self.player.play(random.choices(actions, weights=values, k=1)[0])
            self.next_behavior_ms = random.randint(6000, 14000)
            self.after(self.next_behavior_ms, self._schedule_behavior)
            return

        weights = BEHAVIOR_WEIGHTS.get(self.mood, BEHAVIOR_WEIGHTS["normal"])
        actions, values = zip(*weights.items())
        self.player.play(random.choices(actions, weights=values, k=1)[0])
        self.next_behavior_ms = random.randint(6000, 14000)
        self.after(self.next_behavior_ms, self._schedule_behavior)

    def _is_action_locked(self):
        return (
            self.manual_action_locked
            or self.drag.is_dragging
            or self.player.in_compound
            or self.player.action_name in UNINTERRUPTIBLE_ACTIONS
        )

    def _open_chat(self, _=None):
        self.chat_box.open_near(self.winfo_x(), max(0, self.winfo_y() - 120))

    def _menu(self, event):
        menu = tk.Menu(self, tearoff=False)
        for name in self.registry.names():
            menu.add_command(label=name, command=lambda n=name: self._play_manual_action(n))
        menu.add_separator()
        menu.add_command(label="聊天", command=self._open_chat)
        menu.add_command(label="退出", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def _play_manual_action(self, name: str):
        self.manual_action_locked = True
        self.player.play(name)

    def _on_reply(self, reply: str, action: str):
        self.player.play(action or "idle")
        self.bubble.configure(text=reply)
        self.bubble.place(x=0, y=0)
        self.after(6000, self.bubble.place_forget)
