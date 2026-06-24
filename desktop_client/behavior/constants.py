BASE_TICK_MS = 40
TICK_MS = 20
TICK_SCALE = TICK_MS / BASE_TICK_MS
MISSING = object()

BORDER_GROUND = {"地面", "Floor"}
BORDER_CEILING = {"天井", "Ceiling"}
BORDER_WALL = {"壁", "Wall"}

LEGACY_NAME_MAP = {
    "idle": "立ってボーっとする",
    "walk": "ワークエリアの下辺を歩く",
    "run": "ワークエリアの下辺を走る",
    "sit": "座ってボーっとする",
    "lie": "寝そべってボーっとする",
    "crawl": "ワークエリアの下辺でずりずり",
    "climb": "ワークエリアの壁を登る",
    "sleep": "寝そべってボーっとする",
    "jump": "ジャンプ",
    "fall": "落下する",
    "drag": "ドラッグされる",
    "thrown": "投げられる",
}
