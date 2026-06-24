import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

astrbot_module = types.ModuleType("astrbot")
astrbot_api_module = types.ModuleType("astrbot.api")
astrbot_api_module.logger = MagicMock()
sys.modules.setdefault("astrbot", astrbot_module)
sys.modules.setdefault("astrbot.api", astrbot_api_module)

from src.desktop_pet.service_v2 import DesktopPetService  # noqa: E402


class DesktopPetServiceTests(unittest.TestCase):
    def test_start_forces_utf8_client_logging(self):
        root = Path(__file__).resolve().parents[1]
        plugin = MagicMock()
        plugin.curr_dir = str(root)
        plugin.data_dir = str(root)
        plugin.config = {"desktop_pet_debug_trace": True}

        process = MagicMock()
        process.poll.return_value = None

        with (
            patch("src.desktop_pet.service_v2.os.name", "nt"),
            patch("src.desktop_pet.service_v2.PetApiServer") as api_server,
            patch("src.desktop_pet.service_v2.subprocess.Popen", return_value=process) as popen,
            patch("src.desktop_pet.service_v2.open", mock_open()),
            patch("src.desktop_pet.service_v2.time.sleep"),
        ):
            api_server.return_value.start.return_value = 47821

            service = DesktopPetService(plugin)
            service.start()
            service.stop()

        args, kwargs = popen.call_args
        self.assertEqual(args[0][:3], [sys.executable, "-X", "utf8"])
        self.assertEqual(kwargs["env"]["ATRI_PET_DEBUG_TRACE"], "1")
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")
        self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "utf-8")


if __name__ == "__main__":
    unittest.main()
