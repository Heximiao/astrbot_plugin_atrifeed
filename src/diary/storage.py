from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class DiaryStorage:
    def __init__(self, plugin_data_dir: str):
        self.data_dir = os.path.join(plugin_data_dir, "diary")
        self.diary_dir = os.path.join(self.data_dir, "diaries")
        self.state_path = os.path.join(self.data_dir, "state.json")
        os.makedirs(self.diary_dir, exist_ok=True)

    def was_generated(self, date: str) -> bool:
        try:
            with open(self.state_path, "r", encoding="utf-8") as file:
                return json.load(file).get("last_generated_date") == date
        except (OSError, ValueError, TypeError):
            return False

    def save(self, record: dict[str, Any]) -> str:
        generated_at = float(record.get("generation_time", datetime.now().timestamp()))
        stamp = datetime.fromtimestamp(generated_at).strftime("%H%M%S")
        path = os.path.join(self.diary_dir, f"{record['date']}_{stamp}.json")
        with open(path, "w", encoding="utf-8") as file:
            json.dump(record, file, ensure_ascii=False, indent=2)
        with open(self.state_path, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "last_generated_date": record["date"],
                    "last_generation_time": generated_at,
                    "last_record": path,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )
        return path

    def list_by_date(self, date: str) -> list[tuple[str, dict[str, Any]]]:
        records: list[tuple[str, dict[str, Any]]] = []
        try:
            names = os.listdir(self.diary_dir)
        except OSError:
            return records
        for name in names:
            if not name.startswith(f"{date}_") or not name.endswith(".json"):
                continue
            path = os.path.join(self.diary_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                records.append((path, data))
            except (OSError, ValueError, TypeError):
                continue
        records.sort(key=lambda item: float(item[1].get("generation_time", 0)))
        return records

    def get_record(self, date: str, index: int = 0) -> tuple[str, dict[str, Any]] | None:
        records = self.list_by_date(date)
        if not records:
            return None
        if index <= 0:
            return records[-1]
        if index > len(records):
            return None
        return records[index - 1]

    @staticmethod
    def update_record(path: str, record: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(record, file, ensure_ascii=False, indent=2)
