import os
import subprocess
import sys
import time
from pathlib import Path

from astrbot.api import logger

from .api_v2 import PetApiServer


ASSET_DIR = Path("pic") / "atri_pet"


class DesktopPetService:
    def __init__(self, plugin):
        self.plugin = plugin
        self.process = None
        self.api = None
        self.log_file = None

    def _get_config(self) -> dict:
        return self.plugin.config if self.plugin.config else (self.plugin.context.get_config() or {})

    def start_if_enabled(self):
        conf = self._get_config()
        if not conf.get("desktop_pet_enabled", False):
            return
        self.start()

    def start(self):
        if self.process and self.process.poll() is None:
            return
        if os.name != "nt":
            logger.warning("[Atri] 桌宠模式仅建议在 Windows 桌面环境使用，已跳过启动。")
            return

        curr_dir = Path(self.plugin.curr_dir)
        client_entry = curr_dir / "desktop_client" / "main.py"
        asset_dir = curr_dir / ASSET_DIR
        if not client_entry.exists():
            logger.warning(f"[Atri] 桌宠客户端入口不存在: {client_entry}")
            return
        if not (asset_dir / "conf" / "Actions.xml").exists():
            logger.warning(f"[Atri] ATRI 桌宠素材不完整: {asset_dir}")
            return

        try:
            conf = self._get_config()
            self.api = PetApiServer(self.plugin)
            api_port = self.api.start()
            env = os.environ.copy()
            env["ATRI_PET_ASSET_DIR"] = str(ASSET_DIR)
            env["ATRI_PET_API"] = f"http://127.0.0.1:{api_port}"
            env["ATRI_PET_DEBUG_TRACE"] = "1" if conf.get("desktop_pet_debug_trace", False) else "0"

            log_path = Path(self.plugin.data_dir) / "desktop_pet_client.log"
            self.log_file = open(log_path, "ab")
            self.process = subprocess.Popen(
                [sys.executable, str(client_entry)],
                cwd=str(curr_dir),
                env=env,
                stdout=self.log_file,
                stderr=self.log_file,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            time.sleep(0.5)
            if self.process.poll() is not None:
                logger.warning(f"[Atri] 桌宠客户端启动后立即退出，请查看日志: {log_path}")
            else:
                logger.info(f"[Atri] 桌宠客户端已启动，客户端日志: {log_path}")
        except Exception as exc:
            logger.warning(f"[Atri] 桌宠客户端启动失败: {exc}")

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception as exc:
                logger.warning(f"[Atri] 关闭桌宠客户端失败: {exc}")
        self.process = None
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
        if self.api:
            self.api.stop()
            self.api = None

    def dispatch_pet_event(self, event_type: str, payload: dict | None = None) -> None:
        logger.debug(f"[Atri] 桌宠事件: {event_type}, payload={payload or {}}")
