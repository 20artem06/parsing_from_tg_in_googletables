from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceKind(str, Enum):
    BEST = "BEST"
    SONIC = "SONIC"


class TelegramTextMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int
    date: datetime
    text: str


class SonicBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_ids: list[int] = Field(default_factory=list)
    messages: list[TelegramTextMessage] = Field(default_factory=list)
    raw_text: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RawBestItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: SourceKind = SourceKind.BEST
    sheet_name: str
    row_number: int
    raw_name: str
    full_name: str
    section_path: list[str] = Field(default_factory=list)
    raw_price: str | None = None
    price: int | None = None
    currency: str = "RUB"
    raw_flag: str | None = None
    country_flag: str | None = None


class RawSonicItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: SourceKind = SourceKind.SONIC
    batch_message_ids: list[int] = Field(default_factory=list)
    line_number: int
    raw_name: str
    full_name: str
    section_name: str | None = None
    raw_price: str | None = None
    price: int | None = None
    currency: str = "RUB"
    raw_flag: str | None = None
    country_flag: str | None = None
    model_code: str | None = None


class NormalizedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: SourceKind
    source_ref: str
    raw_name: str
    full_name: str
    brand: str = "Apple"
    category: str
    product_line: str | None = None
    family: str | None = None
    generation: str | None = None
    year: int | None = None
    chip: str | None = None
    screen_size: str | None = None
    storage_gb: int | None = None
    ram_gb: int | None = None
    connectivity: str | None = None
    color: str | None = None
    size_label: str | None = None
    model_code: str | None = None
    raw_flag: str | None = None
    country_flag: str | None = None
    price: int | None = None
    currency: str = "RUB"
    canonical_name: str
    canonical_key: str
    tokens: list[str] = Field(default_factory=list)
    source_sheet: str | None = None
    source_section: str | None = None


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    matched: bool
    score: float = 0.0
    strategy: str = "new"
    best_key: str | None = None


class MergedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str
    product_line: str | None = None
    family: str | None = None
    canonical_name: str
    canonical_key: str
    price: int | None = None
    currency: str = "RUB"
    price_source: str
    source_priority: int
    best_price: int | None = None
    sonic_price: int | None = None
    country_flag: str | None = None
    best_country_flag: str | None = None
    sonic_country_flag: str | None = None
    model_code: str | None = None
    color: str | None = None
    storage_gb: int | None = None
    ram_gb: int | None = None
    connectivity: str | None = None
    year: int | None = None
    chip: str | None = None
    screen_size: str | None = None
    size_label: str | None = None
    raw_best_name: str | None = None
    raw_sonic_name: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)
    parsed_from_best: bool = False
    parsed_from_sonic: bool = False
    match_score: float | None = None

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "category",
            "product_line",
            "family",
            "canonical_name",
            "canonical_key",
            "price",
            "currency",
            "price_source",
            "source_priority",
            "best_price",
            "sonic_price",
            "country_flag",
            "best_country_flag",
            "sonic_country_flag",
            "model_code",
            "color",
            "storage_gb",
            "ram_gb",
            "connectivity",
            "year",
            "chip",
            "screen_size",
            "size_label",
            "raw_best_name",
            "raw_sonic_name",
            "updated_at",
            "parsed_from_best",
            "parsed_from_sonic",
            "match_score",
        ]

    def to_sheet_row(self) -> list[str]:
        data = self.model_dump(mode="json")
        return ["" if data.get(column) is None else str(data.get(column)) for column in self.sheet_columns()]


class RebuildStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trigger: str
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    best_raw_count: int = 0
    sonic_raw_count: int = 0
    best_normalized_count: int = 0
    sonic_normalized_count: int = 0
    merged_count: int = 0
    overridden_by_sonic: int = 0
    appended_new_from_sonic: int = 0
    best_from_cache: bool = False
    sonic_from_cache: bool = False
    used_cached_merged: bool = False
    errors: list[str] = Field(default_factory=list)


class MergeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[MergedItem] = Field(default_factory=list)
    stats: RebuildStats
