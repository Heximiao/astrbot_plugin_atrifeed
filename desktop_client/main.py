import os
import logging
from pathlib import Path

from pet_window_engine import PetWindow


def configure_logging(debug_trace_enabled: bool):
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logging.basicConfig(level=logging.WARNING)

    level = logging.DEBUG if debug_trace_enabled else logging.INFO
    logger = logging.getLogger("atri_pet")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def main():
    base_dir = Path(__file__).resolve().parents[1]
    asset_dir = os.environ.get("ATRI_PET_ASSET_DIR") or str(base_dir / "pic" / "atri_pet")
    api_url = os.environ.get("ATRI_PET_API", "http://127.0.0.1:47821")
    debug_trace_enabled = os.environ.get("ATRI_PET_DEBUG_TRACE", "").lower() in {"1", "true", "yes", "on"}
    configure_logging(debug_trace_enabled)
    logging.getLogger("atri_pet").info("desktop pet client starting, debug_trace=%s", debug_trace_enabled)
    if not Path(asset_dir).exists():
        raise SystemExit(f"ATRI pet assets not found: {asset_dir}")
    app = PetWindow(asset_dir, api_url, debug_trace_enabled=debug_trace_enabled)
    app.mainloop()


if __name__ == "__main__":
    main()
