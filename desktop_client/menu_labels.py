from __future__ import annotations


ALWAYS_AVAILABLE_COMMANDS = [
    "振り向く",
    "立つ",
    "座る",
    "寝そべる",
    "歩く",
    "走る",
    "猛ダッシュ",
    "ずりずり",
    "跳ねる",
    "転ぶ",
    "落ちる",
    "立ってボーっとする",
    "座ってボーっとする",
    "寝そべってボーっとする",
    "座って足をぶらぶらさせる",
    "座って首が回る",
    "マウスの周りに集まる",
]

ENVIRONMENT_COMMANDS = [
    "壁に掴まってボーっとする",
    "壁から落ちる",
    "天井に掴まってボーっとする",
    "天井から落ちる",
    "ワークエリアの下辺を歩く",
    "ワークエリアの下辺を走る",
    "ワークエリアの下辺でずりずり",
    "ワークエリアの下辺の左の端っこで座る",
    "ワークエリアの下辺の右の端っこで座る",
    "ワークエリアの下辺から左の壁によじのぼる",
    "ワークエリアの下辺から右の壁によじのぼる",
    "走ってワークエリアの下辺の左の端っこで座る",
    "走ってワークエリアの下辺の右の端っこで座る",
    "走ってワークエリアの下辺から左の壁によじのぼる",
    "走ってワークエリアの下辺から右の壁によじのぼる",
    "ワークエリアの壁を途中まで登る",
    "ワークエリアの壁を登る",
    "ワークエリアの上辺を伝う",
    "左の壁に飛びつく",
    "右の壁に飛びつく",
    "IEの下に飛びつく",
    "IEの天井を歩く",
    "IEの天井を走る",
    "IEの天井でずりずり",
    "IEの天井の左の端っこで座る",
    "IEの天井の右の端っこで座る",
    "IEの天井の左の端っこから飛び降りる",
    "IEの天井の右の端っこから飛び降りる",
    "走ってIEの天井の左の端っこで座る",
    "走ってIEの天井の右の端っこで座る",
    "走ってIEの天井の左の端っこから飛び降りる",
    "走ってIEの天井の右の端っこから飛び降りる",
    "猛ダッシュでIEの天井の左の端っこから飛び降りる",
    "猛ダッシュでIEの天井の右の端っこから飛び降りる",
    "IEの壁を途中まで登る",
    "IEの壁を登る",
    "IEの下辺を伝う",
    "IEの下辺から左の壁によじのぼる",
    "IEの下辺から右の壁によじのぼる",
    "IEの左に飛びつく",
    "IEの右に飛びつく",
    "IEを右に投げる",
    "IEを左に投げる",
    "走ってIEを右に投げる",
    "走ってIEを左に投げる",
]

PARAMETER_COMMANDS = [
    "ジャンプ",
    "変位",
    "IEを投げる",
    "IEを持って歩く",
    "IEを持って走る",
    "IEを持って落ちる",
]

HIDDEN_MANUAL_COMMANDS = {
    "つままれる",
    "抵抗する",
    "ドラッグされる",
    "投げられる",
    "落下する",
    "引っこ抜く1",
    "引っこ抜く2",
    "分裂1",
}

EXACT_LABELS = {
    "IEを右に投げる": "把IE窗口扔到右边",
    "IEを左に投げる": "把IE窗口扔到左边",
    "走ってIEを右に投げる": "跑过去把IE窗口扔到右边",
    "走ってIEを左に投げる": "跑过去把IE窗口扔到左边",
    "IEを投げる": "投掷IE窗口",
    "IEを持って落ちる": "抱着IE窗口下落",
    "IEを持って歩く": "抱着IE窗口走",
    "IEを持って走る": "抱着IE窗口跑",
    "立つ": "站立",
    "立ってボーっとする": "站着发呆",
    "座る": "坐下",
    "座ってボーっとする": "坐着发呆",
    "歩く": "走路",
    "走る": "跑步",
    "落下する": "下落",
    "落ちる": "掉落",
    "ドラッグされる": "被拖拽",
    "投げられる": "被扔出",
    "振り向く": "转身",
    "ジャンプ": "跳跃",
    "変位": "位移",
}


REPLACEMENTS = (
    ("走って", "跑过去"),
    ("猛ダッシュで", "猛冲到"),
    ("ワークエリア", "工作区"),
    ("IE", "IE窗口"),
    ("マウス", "鼠标"),
    ("右", "右"),
    ("左", "左"),
    ("上辺", "上边"),
    ("下辺", "下边"),
    ("天井", "天花板"),
    ("壁", "墙"),
    ("端っこ", "边缘"),
    ("途中まで", "到半路"),
    ("ボーっとする", "发呆"),
    ("ずりずり", "蹭着移动"),
    ("寝そべって", "趴着"),
    ("座って", "坐着"),
    ("立って", "站着"),
    ("飛びつく", "跳上去"),
    ("飛び降りる", "跳下来"),
    ("よじのぼる", "爬上去"),
    ("登る", "爬"),
    ("歩く", "走"),
    ("走る", "跑"),
    ("落ちる", "掉落"),
    ("投げる", "扔"),
    ("持って", "抱着"),
    ("掴まる", "抓住"),
    ("伝う", "沿着走"),
    ("見る", "看"),
    ("見上げる", "抬头看"),
    ("足をぶらぶらさせる", "晃腿"),
    ("首が回る", "转头"),
    ("から", "从"),
    ("に", "到"),
    ("の", "的"),
    ("を", ""),
    ("で", "在"),
)


def menu_label(name: str) -> str:
    if name in EXACT_LABELS:
        return EXACT_LABELS[name]
    label = name
    for source, target in REPLACEMENTS:
        label = label.replace(source, target)
    return label


def grouped_commands(available_commands: list[str] | set[str]) -> list[tuple[str, list[str]]]:
    available = set(available_commands)
    used: set[str] = set()
    groups: list[tuple[str, list[str]]] = []
    for label, names in (
        ("1. 任何时候都能点", ALWAYS_AVAILABLE_COMMANDS),
        ("2. 需要环境条件", ENVIRONMENT_COMMANDS),
        ("3. 需要参数才有意义", PARAMETER_COMMANDS),
    ):
        group = [name for name in names if name in available and name not in HIDDEN_MANUAL_COMMANDS]
        if group:
            groups.append((label, group))
            used.update(group)

    remaining = [
        name
        for name in sorted(available)
        if name not in used and name not in HIDDEN_MANUAL_COMMANDS
    ]
    if remaining:
        groups.append(("4. 其他动作", remaining))
    return groups


def manual_action_params(name: str, anchor, facing: int, work_area) -> dict[str, object]:
    target_x = anchor.x + (180 if facing > 0 else -180)
    if getattr(work_area, "visible", False):
        target_x = max(work_area.left + 64, min(work_area.right - 64, target_x))
    if name in {"歩く", "ずりずり"}:
        return {"TargetX": target_x}
    if name in {"走る", "猛ダッシュ"}:
        far_x = anchor.x + (320 if facing > 0 else -320)
        if getattr(work_area, "visible", False):
            far_x = max(work_area.left + 64, min(work_area.right - 64, far_x))
        return {"TargetX": far_x}
    if name == "ジャンプ":
        jump_x = anchor.x + (120 if facing > 0 else -120)
        if getattr(work_area, "visible", False):
            jump_x = max(work_area.left + 64, min(work_area.right - 64, jump_x))
        return {"TargetX": jump_x, "TargetY": anchor.y - 120}
    if name == "変位":
        return {"X": 24 if facing > 0 else -24, "Y": 0}
    if name in {"IEを持って歩く", "IEを持って走る"}:
        return {"TargetX": target_x}
    return {}
