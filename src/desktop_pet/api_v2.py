import asyncio
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from astrbot.api import logger

from ..command.feeding import run_feed_fruit_logic
from .prompt_builder_v2 import build_user_state_for_prompt, extract_user_id
from .state_snapshot import get_pet_state


QQ_ID_RE = re.compile(r"^[1-9]\d{4,11}$")
FEED_EMOJIS = {"🍧", "🍜", "🍎", "🍉", "🍓", "🍔", "🍕", "🍱", "🍄", "🍭", "🍙"}


class PetApiServer:
    def __init__(self, plugin, host: str = "127.0.0.1", port: int = 47821):
        self.plugin = plugin
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None

    def start(self) -> int:
        if self.server:
            return self.server.server_address[1]

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/pet/state":
                    self._send_json(owner.get_state())
                    return
                if path == "/pet/user":
                    self._send_json(owner.get_user())
                    return
                self._send_json({"error": "not found"}, status=404)

            def do_POST(self):
                path = urlparse(self.path).path
                if path == "/pet/chat":
                    data = self._read_json()
                    self._send_json(owner.chat(data.get("message", ""), data.get("user_id", "")))
                    return
                if path == "/pet/user":
                    data = self._read_json()
                    self._send_json(owner.set_user(data.get("user_id", "")))
                    return
                if path == "/pet/event":
                    self._send_json({"ok": True})
                    return
                self._send_json({"error": "not found"}, status=404)

            def log_message(self, *_):
                return

            def _read_json(self):
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length <= 0:
                    return {}
                try:
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    return {}

            def _send_json(self, data, status=200):
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server.server_address[1]

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def get_state(self) -> dict:
        user_id = self._current_user_id()
        if not user_id:
            return {"user_id": "", "exists": False, "needs_user_id": True}
        return get_pet_state(self.plugin.db, user_id).as_dict()

    def chat(self, message: str, selected_user_id: str = "") -> dict:
        message = message.strip()
        if message in FEED_EMOJIS:
            user_id = self._valid_user_id(selected_user_id) or self._current_user_id()
            if not user_id:
                return {
                    "reply": "请先在桌宠菜单里填写使用桌宠的 QQ 号。",
                    "emotion": "normal",
                    "action": "idle",
                    "needs_user_id": True,
                }
            return self._feed(message, user_id)

        user_id = extract_user_id(message, self._current_user_id())
        if not user_id:
            return {
                "reply": "请先在桌宠菜单里填写使用桌宠的 QQ 号。",
                "emotion": "normal",
                "action": "idle",
                "needs_user_id": True,
            }
        prompt = self._render_prompt(user_id, message)
        reply = self._generate_reply(prompt)
        state = get_pet_state(self.plugin.db, user_id)
        return {"reply": reply, "emotion": state.mood, "action": state.recommended_action}

    def get_user(self) -> dict:
        saved_user_id = self._load_saved_user_id()
        default_user_id = self._default_user_id()
        user_id = saved_user_id or default_user_id
        return {
            "user_id": user_id,
            "saved_user_id": saved_user_id,
            "default_user_id": default_user_id,
            "needs_user_id": not bool(user_id),
        }

    def set_user(self, user_id: str) -> dict:
        user_id = str(user_id or "").strip()
        if not self._valid_user_id(user_id):
            return {"ok": False, "error": "请输入有效的 QQ 号。", **self.get_user()}
        self._settings_path().write_text(
            json.dumps({"desktop_pet_user_id": user_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"ok": True, **self.get_user()}

    def _current_user_id(self) -> str:
        return self._load_saved_user_id() or self._default_user_id()

    def _default_user_id(self) -> str:
        conf = self.plugin.config if self.plugin.config else (self.plugin.context.get_config() or {})
        for key in ("admins_id", "admins", "admin", "bot_admins"):
            user_id = self._first_numeric_id(conf.get(key))
            if user_id:
                return user_id
        return ""

    def _first_numeric_id(self, value) -> str:
        if isinstance(value, str):
            parts = [part.strip() for part in re.split(r"[,，\s]+", value) if part.strip()]
        elif isinstance(value, (list, tuple, set)):
            parts = [str(part).strip() for part in value]
        else:
            parts = []
        for part in parts:
            user_id = self._valid_user_id(part)
            if user_id:
                return user_id
        return ""

    def _valid_user_id(self, user_id: str) -> str:
        user_id = str(user_id or "").strip()
        return user_id if QQ_ID_RE.match(user_id) else ""

    def _settings_path(self) -> Path:
        return Path(self.plugin.data_dir) / "desktop_pet_settings.json"

    def _load_saved_user_id(self) -> str:
        try:
            data = json.loads(self._settings_path().read_text(encoding="utf-8"))
        except Exception:
            return ""
        user_id = str(data.get("desktop_pet_user_id") or "").strip()
        return user_id if QQ_ID_RE.match(user_id) else ""

    def _feed(self, message: str, user_id: str) -> dict:
        if not self.loop:
            return {"reply": "桌宠服务还没有准备好，请稍后再试。", "emotion": "normal", "action": "idle"}
        future = asyncio.run_coroutine_threadsafe(self._run_feed_logic(message, user_id), self.loop)
        try:
            reply = future.result(timeout=10).strip() or "亚托莉收到了。"
        except Exception as exc:
            logger.warning(f"[Atri] desktop pet feed failed: {exc}")
            reply = "投喂时发生了一点小问题，请稍后再试。"
        state = get_pet_state(self.plugin.db, user_id)
        return {"reply": reply, "emotion": state.mood, "action": state.recommended_action}

    async def _run_feed_logic(self, message: str, user_id: str) -> str:
        event = DesktopPetFeedEvent(user_id, message)
        texts = []
        async for result in run_feed_fruit_logic(event, self.plugin.db, self.plugin.curr_dir):
            text = event.result_to_text(result)
            if text:
                texts.append(text)
        return "\n".join(texts)

    def _render_prompt(self, user_id: str, message: str) -> str:
        prompt_path = Path(self.plugin.curr_dir) / "desktop_client" / "prompts" / "atri_chat_prompt.txt"
        try:
            template = prompt_path.read_text(encoding="utf-8")
        except Exception:
            template = (
                "你是 ATRI。请简短自然地回复。\n"
                "当前用户状态：\n{user_state}\n"
                "用户消息：\n{message}"
            )
        return template.format(
            user_state=self._build_safe_user_state(user_id),
            message=message,
        )

    def _build_safe_user_state(self, user_id: str) -> str:
        state = build_user_state_for_prompt(self.plugin.db, user_id)
        return "\n".join(
            line for line in state.splitlines()
            if not line.strip().lower().startswith("qq:")
        )

    def _generate_reply(self, prompt: str) -> str:
        if not self.loop:
            return "嗯，我在这里。只是现在还连不上大模型。"
        future = asyncio.run_coroutine_threadsafe(self._call_llm(prompt), self.loop)
        try:
            return future.result(timeout=45).strip() or "嗯，我听见了。"
        except Exception as exc:
            logger.warning(f"[Atri] desktop pet AI reply failed: {exc}")
            return "嗯，我在这里。现在先陪你待一会儿。"

    async def _call_llm(self, prompt: str) -> str:
        provider_id = await self._get_chat_provider_id()
        response = await self.plugin.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt,
        )
        if isinstance(response, str):
            return response
        return getattr(response, "completion_text", None) or getattr(response, "content", "")

    async def _get_chat_provider_id(self) -> str:
        conf = self.plugin.config if self.plugin.config else (self.plugin.context.get_config() or {})
        for key in (
            "desktop_pet_chat_provider_id",
            "chat_provider_id",
            "provider_id",
            "llm_provider_id",
        ):
            value = conf.get(key)
            if value:
                return str(value)

        umo = "webchat:FriendMessage:desktop_pet"
        return await self.plugin.context.get_current_chat_provider_id(umo=umo)


class DesktopPetFeedEvent:
    def __init__(self, user_id: str, message: str):
        self.message_str = message
        self._user_id = user_id

    def get_sender_id(self) -> str:
        return self._user_id

    def get_group_id(self):
        return None

    def plain_result(self, text: str):
        return {"type": "plain", "text": text}

    def image_result(self, path: str):
        return {"type": "image", "path": path}

    def chain_result(self, chain):
        return {"type": "chain", "chain": chain}

    def result_to_text(self, result) -> str:
        if isinstance(result, dict):
            if result.get("type") == "plain":
                return str(result.get("text") or "")
            if result.get("type") == "chain":
                return self._chain_to_text(result.get("chain") or [])
            return ""
        return self._chain_to_text(getattr(result, "chain", None) or getattr(result, "message", None) or [])

    def _chain_to_text(self, chain) -> str:
        texts = []
        for item in chain:
            text = getattr(item, "text", None)
            if text is None:
                text = getattr(item, "message", None)
            if text is None and item.__class__.__name__.lower() == "plain":
                text = str(item)
            if text:
                texts.append(str(text))
        return "".join(texts)
