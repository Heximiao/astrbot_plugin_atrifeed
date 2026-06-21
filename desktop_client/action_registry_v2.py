from pathlib import Path

from shimeji_actions import Action, Frame, parse_actions

ACTION_ALIASES = {
    "idle": "\u7acb\u3064",
    "walk": "\u6b69\u304f",
    "run": "\u8d70\u308b",
    "sit": "\u5ea7\u308b",
    "lie": "\u5bdd\u305d\u3079\u308b",
    "crawl": "\u305a\u308a\u305a\u308a",
    "climb": "\u58c1\u3092\u767b\u308b",
    "sleep": "\u5bdd\u305d\u3079\u308b",
}


class ActionRegistry:
    def __init__(self, asset_dir: str):
        self.asset_dir = Path(asset_dir)
        self.xml_actions = parse_actions(self.asset_dir)
        self.custom_actions = {"jump", "fall", "drag", "sing"}
        self.fallback = self._build_fallback()

    def names(self) -> list[str]:
        return sorted(set(ACTION_ALIASES) | self.custom_actions)

    def resolve(self, name: str):
        if name in self.custom_actions:
            return name
        xml_name = ACTION_ALIASES.get(name, name)
        return self.xml_actions.get(xml_name) or self.fallback

    def _build_fallback(self) -> Action:
        candidates = list(self.asset_dir.glob("shime*.png")) + list(self.asset_dir.glob("*.png"))
        image = str(candidates[0]) if candidates else ""
        return Action(
            name="fallback",
            type="\u9759\u6b62",
            border="",
            frames=[Frame(image=image, anchor=(64, 128), velocity=(0, 0), duration=8)],
        )
