import json
import urllib.request


FEED_EMOJIS = {
    "\U0001f367",
    "\U0001f35c",
    "\U0001f34e",
    "\U0001f349",
    "\U0001f353",
    "\U0001f354",
    "\U0001f355",
    "\U0001f371",
    "\U0001f344",
    "\U0001f36d",
    "\U0001f359",
}


def is_feed_message(message: str) -> bool:
    return (message or "").strip() in FEED_EMOJIS


def post_json(api_url: str, path: str, payload: dict, timeout: int = 5) -> dict:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}{path}",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(api_url: str, path: str, timeout: int = 3) -> dict:
    with urllib.request.urlopen(f"{api_url.rstrip('/')}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_chat(api_url: str, message: str, user_id: str = "") -> tuple[str, str]:
    payload = {"message": message}
    if user_id and is_feed_message(message):
        payload["user_id"] = user_id
    data = post_json(api_url, "/pet/chat", payload, timeout=50)
    return data.get("reply") or "OK.", data.get("action") or "idle"


def get_pet_user(api_url: str) -> str:
    data = get_json(api_url, "/pet/user", timeout=3)
    return data.get("user_id", "") or ""


def save_pet_user(api_url: str, user_id: str) -> tuple[bool, str, str]:
    data = post_json(api_url, "/pet/user", {"user_id": user_id}, timeout=5)
    ok = bool(data.get("ok"))
    reply = "已保存桌宠 QQ。" if ok else data.get("error", "QQ 号保存失败。")
    return ok, reply, data.get("user_id", "") or ""
