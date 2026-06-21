import random
import tkinter as tk

from action_registry_v2 import ActionRegistry
from animation_player import AnimationPlayer
from chat_box_v2 import ChatBox


TRANSPARENT_COLOR = "#ff00ff"
EDGE_BLEND_COLOR = "#f4f4f4"
ALPHA_VISIBLE_THRESHOLD = 36

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

        self.drag_offset = None
        self.vy = 0
        self.mood = "normal"
        self.next_behavior_ms = 5000
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._end_drag)
        self.bind("<Double-Button-1>", self._open_chat)
        self.bind("<Button-3>", self._menu)

        self.geometry("+100+300")
        self.player.play("idle")
        self.after(1000, self._fetch_state)
        self._schedule_behavior()
        self.after(40, self._tick)

    def load_image(self, path: str):
        try:
            from PIL import Image, ImageTk

            image = Image.open(path).convert("RGBA")
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
        self.player.tick()
        self._move()
        self.after(40, self._tick)

    def _move(self):
        action = self.player.action_name
        x, y = self.winfo_x(), self.winfo_y()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = max(self.winfo_width(), 96), max(self.winfo_height(), 96)
        bottom = sh - h - 40

        if action in {"walk", "run", "crawl"}:
            vx = -2 if action == "walk" else -4 if action == "run" else -1
            if x <= 0:
                vx = abs(vx)
            if x >= sw - w:
                vx = -abs(vx)
            self.geometry(f"+{max(0, min(sw - w, x + vx))}+{bottom}")
        elif action == "jump":
            self.vy = -14
            self.player.play("fall")
        elif action == "fall":
            self.vy += 1
            y += self.vy
            if y >= bottom:
                y = bottom
                self.vy = 0
                self.player.play("idle")
            self.geometry(f"+{x}+{y}")
        elif action == "climb":
            edge_x = 0 if x < sw / 2 else sw - w
            self.geometry(f"+{edge_x}+{max(0, y - 2)}")

    def _fetch_state(self):
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(f"{self.chat_box.api_url}/pet/state", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.mood = data.get("mood", self.mood)
            self.player.play(data.get("recommended_action", "idle"))
        except Exception:
            pass
        self.after(30000, self._fetch_state)

    def _schedule_behavior(self):
        weights = BEHAVIOR_WEIGHTS.get(self.mood, BEHAVIOR_WEIGHTS["normal"])
        actions, values = zip(*weights.items())
        self.player.play(random.choices(actions, weights=values, k=1)[0])
        self.next_behavior_ms = random.randint(6000, 14000)
        self.after(self.next_behavior_ms, self._schedule_behavior)

    def _start_drag(self, event):
        self.drag_offset = (event.x, event.y)
        self.player.play("drag")

    def _drag(self, event):
        if not self.drag_offset:
            return
        dx, dy = self.drag_offset
        self.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def _end_drag(self, _):
        self.drag_offset = None
        self.player.play("fall")

    def _open_chat(self, _=None):
        self.chat_box.open_near(self.winfo_x(), max(0, self.winfo_y() - 120))

    def _menu(self, event):
        menu = tk.Menu(self, tearoff=False)
        for name in self.registry.names():
            menu.add_command(label=name, command=lambda n=name: self.player.play(n))
        menu.add_separator()
        menu.add_command(label="聊天", command=self._open_chat)
        menu.add_command(label="退出", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def _on_reply(self, reply: str, action: str):
        self.player.play(action or "idle")
        self.bubble.configure(text=reply)
        self.bubble.place(x=0, y=0)
        self.after(6000, self.bubble.place_forget)
