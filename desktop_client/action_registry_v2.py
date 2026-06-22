from pathlib import Path

from shimeji_actions import Action, Frame, parse_actions, parse_behaviors

ACTION_ALIASES = {
    "idle": "\u7acb\u3064",
    "walk": "\u6b69\u304f",
    "run": "\u8d70\u308b",
    "sit": "\u5ea7\u308b",
    "lie": "\u5bdd\u305d\u3079\u308b",
    "crawl": "\u305a\u308a\u305a\u308a",
    "climb": "\u58c1\u3092\u767b\u308b",
    "sleep": "\u5bdd\u305d\u3079\u308b",
    "drag": "\u30c9\u30e9\u30c3\u30b0\u3055\u308c\u308b",
    "fall": "\u843d\u3061\u308b",
}

GROUND_ACTIONS = {
    "\u7acb\u3064",
    "\u6b69\u304f",
    "\u8d70\u308b",
    "\u731b\u30c0\u30c3\u30b7\u30e5",
    "\u5ea7\u308b",
    "\u5ea7\u3063\u3066\u898b\u4e0a\u3052\u308b",
    "\u5ea7\u3063\u3066\u30de\u30a6\u30b9\u3092\u898b\u4e0a\u3052\u308b",
    "\u5ea7\u3063\u3066\u9996\u304c\u56de\u308b",
    "\u697d\u306b\u5ea7\u308b",
    "\u8db3\u3092\u4e0b\u308d\u3057\u3066\u5ea7\u308b",
    "\u8db3\u3092\u3076\u3089\u3076\u3089\u3055\u305b\u308b",
    "\u5bdd\u305d\u3079\u308b",
    "\u305a\u308a\u305a\u308a",
    "IE\u3092\u6301\u3063\u3066\u6b69\u304f",
    "IE\u3092\u6301\u3063\u3066\u8d70\u308b",
    "IE\u3092\u6295\u3052\u308b",
    "\u8df3\u306d\u308b",
    "\u8ee2\u3076",
}

GROUND_BEHAVIORS = {
    "\u7acb\u3063\u3066\u30dc\u30fc\u3063\u3068\u3059\u308b",
    "\u5ea7\u3063\u3066\u30dc\u30fc\u3063\u3068\u3059\u308b",
    "\u5bdd\u305d\u3079\u3063\u3066\u30dc\u30fc\u3063\u3068\u3059\u308b",
    "\u5ea7\u3063\u3066\u8db3\u3092\u3076\u3089\u3076\u3089\u3055\u305b\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3092\u6b69\u304f",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3092\u8d70\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u3067\u305a\u308a\u305a\u308a",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u5de6\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u53f3\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u304b\u3089\u5de6\u306e\u58c1\u306b\u3088\u3058\u306e\u307c\u308b",
    "\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u304b\u3089\u53f3\u306e\u58c1\u306b\u3088\u3058\u306e\u307c\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u5de6\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u306e\u53f3\u306e\u7aef\u3063\u3053\u3067\u5ea7\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u304b\u3089\u5de6\u306e\u58c1\u306b\u3088\u3058\u306e\u307c\u308b",
    "\u8d70\u3063\u3066\u30ef\u30fc\u30af\u30a8\u30ea\u30a2\u306e\u4e0b\u8fba\u304b\u3089\u53f3\u306e\u58c1\u306b\u3088\u3058\u306e\u307c\u308b",
}


class ActionRegistry:
    def __init__(self, asset_dir: str):
        self.asset_dir = Path(asset_dir)
        self.xml_actions = parse_actions(self.asset_dir)
        self.xml_behaviors = parse_behaviors(self.asset_dir)
        self.drag_actions = self._build_drag_actions()
        self.custom_actions = {"jump", "sing"}
        self.fallback = self._build_fallback()

    def names(self) -> list[str]:
        return sorted(
            set(ACTION_ALIASES)
            | self.custom_actions
            | self.available_ground_actions()
            | self.available_ground_behaviors()
        )

    def resolve(self, name: str):
        if name in self.drag_actions:
            return self.drag_actions[name]
        if name in self.custom_actions:
            return name
        xml_name = ACTION_ALIASES.get(name, name)
        return self.xml_actions.get(xml_name) or self.fallback

    def behavior_choices(self, allowed: set[str]) -> dict[str, int]:
        return {
            name: frequency
            for name, frequency in self.xml_behaviors.items()
            if name in allowed and name in self.xml_actions
        }

    def available_ground_actions(self) -> set[str]:
        return {name for name in GROUND_ACTIONS if name in self.xml_actions}

    def available_ground_behaviors(self) -> set[str]:
        return {name for name in GROUND_BEHAVIORS if name in self.xml_actions}

    def ground_choices(self) -> dict[str, int]:
        choices = {name: 40 for name in self.available_ground_actions()}
        for name in self.available_ground_behaviors():
            choices[name] = max(choices.get(name, 0), self.xml_behaviors.get(name, 40))
        return choices

    def _build_drag_actions(self) -> dict[str, Action]:
        return {
            "drag_hold": self._frames_action(
                "drag_hold",
                [
                    "shime9.png",
                    "shime7.png",
                    "shime1.png",
                    "shime8.png",
                    "shime10.png",
                    "shime10.png",
                    "shime8.png",
                    "shime1.png",
                    "shime7.png",
                    "shime9.png",
                ],
                duration=4,
            ),
            "drag_swing_left": self._frames_action("drag_swing_left", ["shime10.png"], duration=8),
            "drag_swing_right": self._frames_action("drag_swing_right", ["shime9.png"], duration=8),
            "drag_resist_left": self._frames_action("drag_resist_left", ["shime6.png"], duration=8),
            "drag_resist_right": self._frames_action("drag_resist_right", ["shime5.png"], duration=8),
        }

    def _frames_action(self, name: str, images: list[str], duration: int = 6) -> Action:
        return Action(
            name=name,
            type="\u56fa\u5b9a",
            border="",
            frames=[
                Frame(
                    image=str(self.asset_dir / image),
                    anchor=(64, 128),
                    velocity=(0, 0),
                    duration=duration,
                )
                for image in images
            ],
        )

    def _build_fallback(self) -> Action:
        candidates = list(self.asset_dir.glob("shime*.png")) + list(self.asset_dir.glob("*.png"))
        image = str(candidates[0]) if candidates else ""
        return Action(
            name="fallback",
            type="\u9759\u6b62",
            border="",
            frames=[Frame(image=image, anchor=(64, 128), velocity=(0, 0), duration=8)],
        )
