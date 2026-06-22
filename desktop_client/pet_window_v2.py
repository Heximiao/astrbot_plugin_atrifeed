import random
from types import SimpleNamespace
import tkinter as tk

from action_registry_v2 import ActionRegistry
from animation_player import AnimationPlayer
from chat_box_v2 import ChatBox


TRANSPARENT_COLOR = "#ff00ff"
EDGE_BLEND_COLOR = "#f4f4f4"
ALPHA_VISIBLE_THRESHOLD = 36
FLOOR_GAP = 8
FALLBACK_FLOOR_MARGIN = 64
TICK_MS = 20
BASE_MOVE_TICK_MS = 40
MOVE_SCALE = TICK_MS / BASE_MOVE_TICK_MS
TYPE_MOVE = "\u79fb\u52d5"
BORDER_GROUND = "\u5730\u9762"
BORDER_CEILING = "\u5929\u4e95"

BEHAVIOR_WEIGHTS = {
    "happy": {"idle": 20, "walk": 25, "sit": 15, "jump": 10, "sing": 10, "crawl": 5, "sleep": 2},
    "normal": {"idle": 30, "walk": 25, "sit": 20, "lie": 8, "crawl": 5, "sleep": 5},
    "sad": {"idle": 20, "sit": 30, "lie": 20, "sleep": 15, "walk": 5},
    "angry": {"idle": 30, "walk": 10, "jump": 5, "sit": 10},
}

XML_GROUND_BEHAVIORS = {
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3092\u6b69\u304f",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3092\u8d70\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3067\u305a\u308a\u305a\u308a",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u5de6\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u53f3\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u5de6\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u53f3\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
}


def get_work_area_bottom():
    try:
        import ctypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.bottom
    except Exception:
        pass
    return None


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
        self.move_x = 100.0
        self.move_y = 300.0
        self.facing = -1
        self.mood = "normal"
        self.next_behavior_ms = 5000
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._end_drag)
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
        self.player.tick()
        self._move()
        self.after(TICK_MS, self._tick)

    def _move(self):
        action = self.player.action_name
        real_x, real_y = self.winfo_x(), self.winfo_y()
        if abs(self.move_x - real_x) > 2 or abs(self.move_y - real_y) > 2:
            self.move_x, self.move_y = float(real_x), float(real_y)
        x, y = self.move_x, self.move_y
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = max(self.winfo_width(), 96), max(self.winfo_height(), 96)
        work_bottom = get_work_area_bottom()
        bottom = work_bottom - h - FLOOR_GAP if work_bottom else sh - h - FALLBACK_FLOOR_MARGIN

        if self._is_xml_move():
            self._move_from_xml_velocity(x, y, sw, w, bottom)
        elif action == "jump":
            self.vy = -14
            self.player.play("fall")
        elif action == "fall":
            self.vy += MOVE_SCALE
            y += self.vy * MOVE_SCALE
            if y >= bottom:
                y = bottom
                self.vy = 0
                self.player.play("idle")
            self._place(x, y)
        elif action == "climb":
            edge_x = 0 if x < sw / 2 else sw - w
            self._place(edge_x, max(0, y - 2 * MOVE_SCALE))

    def _is_xml_move(self):
        action = self.player.action
        return not isinstance(action, str) and action.type == TYPE_MOVE

    def _move_from_xml_velocity(self, x: int, y: int, sw: int, w: int, bottom: int):
        action = self.player.action
        raw_vx, raw_vy = self.player.current_velocity()
        target_x = self.player.target_x
        target_y = self.player.target_y
        next_x, next_y = x, y
        reached_x = target_x is None
        reached_y = target_y is None

        if raw_vx:
            if target_x is not None:
                self.set_facing(1 if target_x > x else -1)
            step = abs(raw_vx) * self.facing * MOVE_SCALE
            next_x = x + step
            if target_x is not None and ((step > 0 and next_x >= target_x) or (step < 0 and next_x <= target_x)):
                next_x = int(target_x)
                reached_x = True
        elif target_x is not None and abs(target_x - x) <= 1:
            reached_x = True

        if next_x <= 0:
            next_x = 0
            if raw_vx < 0 or self.facing < 0:
                self.set_facing(1)
        elif next_x >= sw - w:
            next_x = sw - w
            if raw_vx < 0 or self.facing > 0:
                self.set_facing(-1)

        if action.border == BORDER_GROUND:
            next_y = bottom
        elif action.border == BORDER_CEILING:
            next_y = 0
        elif raw_vy:
            next_y = y + raw_vy * MOVE_SCALE
            if target_y is not None and ((raw_vy > 0 and next_y >= target_y) or (raw_vy < 0 and next_y <= target_y)):
                next_y = int(target_y)
                reached_y = True
        elif target_y is not None and abs(target_y - y) <= 1:
            reached_y = True

        self._place(max(0, min(sw - w, next_x)), next_y)
        if reached_x and reached_y:
            self.player.finish_current_ref()

    def _place(self, x: float, y: float):
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
        self._place(self.move_x + dx, self.move_y + dy)

    def eval_action_bool(self, value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        text = value.strip()
        if text.lower() in {"true", "false"}:
            return text.lower() == "true"
        result = self.eval_action_value(text)
        return bool(result) if result is not None else default

    def eval_action_value(self, value: str | None, default=None):
        if value is None or value == "":
            return default
        text = value.strip()
        if (text.startswith("${") or text.startswith("#{")) and text.endswith("}"):
            text = text[2:-1]
        text = (
            text.replace("Math.random()", "random.random()")
            .replace("Math.min", "min")
            .replace("Math.max", "max")
            .replace("true", "True")
            .replace("false", "False")
            .replace("&&", " and ")
            .replace("||", " or ")
        )
        env = self._expression_env()
        try:
            return float(eval(text, {"__builtins__": {}}, env))
        except Exception:
            try:
                return float(text)
            except ValueError:
                return default

    def _expression_env(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        work_bottom = get_work_area_bottom() or sh
        work_area = SimpleNamespace(left=0, top=0, right=sw, bottom=work_bottom, width=sw, height=work_bottom)
        environment = SimpleNamespace(workArea=work_area, screen=SimpleNamespace(width=sw, height=sh))
        anchor = SimpleNamespace(x=self.winfo_x(), y=self.winfo_y())
        mascot = SimpleNamespace(environment=environment, anchor=anchor, lookRight=self.facing > 0)
        return {"mascot": mascot, "random": random, "min": min, "max": max}

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
        xml_weights = self.registry.behavior_choices(XML_GROUND_BEHAVIORS)
        if xml_weights:
            actions, values = zip(*xml_weights.items())
            self.player.play(random.choices(actions, weights=values, k=1)[0])
            self.next_behavior_ms = random.randint(6000, 14000)
            self.after(self.next_behavior_ms, self._schedule_behavior)
            return

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
        self._place(event.x_root - dx, event.y_root - dy)

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
