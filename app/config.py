from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class TelegramConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    api_id: int
    api_hash: str
    session_name: str = "sessions/apple_prices"
    best_channel: str | int
    best_message_id: int
    sonic_channel: str | int
    sonic_history_limit: int = 40
    sonic_batch_window_minutes: int = 20
    sonic_batch_gap_minutes: int = 6


class GoogleSheetsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    spreadsheet_id: str = ""
    worksheet_name: str = "Apple Prices"
    service_account_file: str = "service-account.json"


class MatchingConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    similarity_threshold: float = 0.74
    strong_match_threshold: float = 0.86


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    telegram: TelegramConfig
    google_sheets: GoogleSheetsConfig = Field(default_factory=GoogleSheetsConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    cache_dir: str = "cache"
    log_level: str = "INFO"
    currency: str = "RUB"
    initial_rebuild: bool = True
    rebuild_debounce_seconds: float = 2.0


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = value
    return merged


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _maybe_int(value: str | None) -> str | int | None:
    cleaned = _clean_env_value(value)
    if cleaned is None:
        return None
    if cleaned.lstrip("-").isdigit():
        return int(cleaned)
    return cleaned


def _maybe_bool(value: str | None) -> bool | None:
    cleaned = _clean_env_value(value)
    if cleaned is None:
        return None
    return cleaned.lower() in {"1", "true", "yes", "on"}


def load_config(config_path: str | Path | None = None) -> AppConfig:
    load_dotenv()

    path = Path(config_path or os.getenv("APP_CONFIG_PATH") or Path.cwd() / "config.yaml")

    file_config: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            file_config = yaml.safe_load(handle) or {}

    env_config: dict[str, Any] = {
        "telegram": {
            "api_id": _clean_env_value(os.getenv("TELEGRAM_API_ID")),
            "api_hash": _clean_env_value(os.getenv("TELEGRAM_API_HASH")),
            "session_name": _clean_env_value(os.getenv("TELEGRAM_SESSION_NAME")),
            "best_channel": _maybe_int(os.getenv("BEST_CHANNEL")),
            "best_message_id": _clean_env_value(os.getenv("BEST_MESSAGE_ID")),
            "sonic_channel": _maybe_int(os.getenv("SONIC_CHANNEL")),
            "sonic_history_limit": _clean_env_value(os.getenv("SONIC_HISTORY_LIMIT")),
            "sonic_batch_window_minutes": _clean_env_value(
                os.getenv("SONIC_BATCH_WINDOW_MINUTES")
            ),
            "sonic_batch_gap_minutes": _clean_env_value(
                os.getenv("SONIC_BATCH_GAP_MINUTES")
            ),
        },
        "google_sheets": {
            "enabled": _maybe_bool(os.getenv("GOOGLE_SHEETS_ENABLED")),
            "spreadsheet_id": _clean_env_value(os.getenv("GOOGLE_SPREADSHEET_ID")),
            "worksheet_name": _clean_env_value(os.getenv("GOOGLE_WORKSHEET_NAME")),
            "service_account_file": _clean_env_value(
                os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
            ),
        },
        "matching": {
            "similarity_threshold": _clean_env_value(
                os.getenv("MATCHING_SIMILARITY_THRESHOLD")
            ),
            "strong_match_threshold": _clean_env_value(
                os.getenv("MATCHING_STRONG_MATCH_THRESHOLD")
            ),
        },
        "cache_dir": _clean_env_value(os.getenv("CACHE_DIR")),
        "log_level": _clean_env_value(os.getenv("LOG_LEVEL")),
        "currency": _clean_env_value(os.getenv("CURRENCY")),
        "initial_rebuild": _maybe_bool(os.getenv("INITIAL_REBUILD")),
        "rebuild_debounce_seconds": _clean_env_value(
            os.getenv("REBUILD_DEBOUNCE_SECONDS")
        ),
    }

    merged = _deep_merge(file_config, env_config)
    return AppConfig.model_validate(merged)
