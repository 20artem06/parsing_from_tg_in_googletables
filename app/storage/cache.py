from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from app.storage.models import (
    BestSheetState,
    MergeResult,
    RawBestItem,
    RawSonicItem,
    SonicSectionState,
)


class CacheStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def best_excel_path(self) -> Path:
        return self.base_dir / "latest_best.xlsx"

    @property
    def best_parsed_path(self) -> Path:
        return self.base_dir / "latest_best_parsed.json"

    @property
    def sonic_parsed_path(self) -> Path:
        return self.base_dir / "latest_sonic_parsed.json"

    @property
    def merged_path(self) -> Path:
        return self.base_dir / "latest_merged.json"

    @property
    def stats_path(self) -> Path:
        return self.base_dir / "latest_rebuild_stats.json"

    @property
    def sonic_batch_text_path(self) -> Path:
        return self.base_dir / "latest_sonic_batch.txt"

    @property
    def best_parts_state_path(self) -> Path:
        return self.base_dir / "best_parts_state.json"

    @property
    def sonic_parts_state_path(self) -> Path:
        return self.base_dir / "sonic_parts_state.json"

    def save_best_excel(self, payload: bytes) -> Path:
        self.best_excel_path.write_bytes(payload)
        return self.best_excel_path

    def load_best_excel(self) -> bytes | None:
        if not self.best_excel_path.exists():
            return None
        return self.best_excel_path.read_bytes()

    def save_best_parsed(self, items: list[RawBestItem]) -> None:
        self._save_json(self.best_parsed_path, items)

    def load_best_parsed(self) -> list[RawBestItem]:
        return self._load_json(self.best_parsed_path, list[RawBestItem], default=[])

    def save_best_parts_state(self, parts: list[BestSheetState]) -> None:
        self._save_json(self.best_parts_state_path, parts)

    def load_best_parts_state(self) -> list[BestSheetState]:
        return self._load_json(self.best_parts_state_path, list[BestSheetState], default=[])

    def save_sonic_parsed(self, items: list[RawSonicItem]) -> None:
        self._save_json(self.sonic_parsed_path, items)

    def load_sonic_parsed(self) -> list[RawSonicItem]:
        return self._load_json(self.sonic_parsed_path, list[RawSonicItem], default=[])

    def save_sonic_parts_state(self, parts: list[SonicSectionState]) -> None:
        self._save_json(self.sonic_parts_state_path, parts)

    def load_sonic_parts_state(self) -> list[SonicSectionState]:
        return self._load_json(self.sonic_parts_state_path, list[SonicSectionState], default=[])

    def save_merged(self, result: MergeResult) -> None:
        self._save_json(self.merged_path, result)

    def load_merged(self) -> MergeResult | None:
        return self._load_json(self.merged_path, MergeResult, default=None)

    def save_stats(self, stats: BaseModel) -> None:
        self._save_json(self.stats_path, stats)

    def save_sonic_batch_text(self, text: str) -> None:
        self.sonic_batch_text_path.write_text(text, encoding="utf-8")

    def _save_json(self, path: Path, value: Any) -> None:
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            payload = [item.model_dump(mode="json") for item in value]
        else:
            payload = value
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_json(self, path: Path, type_hint: Any, default: Any) -> Any:
        if not path.exists():
            return default
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TypeAdapter(type_hint).validate_python(payload)
