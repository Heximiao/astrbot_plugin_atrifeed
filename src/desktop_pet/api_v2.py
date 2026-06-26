import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from astrbot.api import logger

from .prompt_builder_v2 import build_user_state_for_prompt, extract_user_id
from .state_snapshot import get_pet_state


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
                if urlparse(self.path).path != "/pet/state":
                    self._send_json({"error": "not found"}, status=404)
                    return
                self._send_json(owner.get_state())

            def do_POST(self):
                path = urlparse(self.path).path
                if path == "/pet/chat":
                    data = self._read_json()
                    self._send_json(owner.chat(data.get("message", "")))
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
        user_id = self._default_user_id()
        return get_pet_state(self.plugin.db, user_id).as_dict()

    def chat(self, message: str) -> dict:
        user_id = extract_user_id(message, self._default_user_id())
        prompt = self._render_prompt(user_id, message)
        reply = self._generate_reply(prompt)
        state = get_pet_state(self.plugin.db, user_id)
        return {"reply": reply, "emotion": state.mood, "action": state.recommended_action}

    def _default_user_id(self) -> str:
        conf = self.plugin.config if self.plugin.config else (self.plugin.context.get_config() or {})
        admins = conf.get("admins") or conf.get("admin") or conf.get("bot_admins") or []
        if isinstance(admins, str):
            parts = [part.strip() for part in admins.replace("，", ",").split(",") if part.strip()]
            if parts:
                return parts[0]
        if isinstance(admins, (list, tuple)) and admins:
            return str(admins[0])
        return "0"

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
            user_state=build_user_state_for_prompt(self.plugin.db, user_id),
            message=message,
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
