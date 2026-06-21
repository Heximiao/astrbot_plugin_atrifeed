import os
from pathlib import Path

from pet_window_v2 import PetWindow


def main():
    base_dir = Path(__file__).resolve().parents[1]
    asset_dir = os.environ.get("ATRI_PET_ASSET_DIR") or str(base_dir / "pic" / "atri_pet")
    api_url = os.environ.get("ATRI_PET_API", "http://127.0.0.1:47821")
    if not Path(asset_dir).exists():
        raise SystemExit(f"ATRI pet assets not found: {asset_dir}")
    app = PetWindow(asset_dir, api_url)
    app.mainloop()


if __name__ == "__main__":
    main()
