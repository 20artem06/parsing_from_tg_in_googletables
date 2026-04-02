from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.config import AppConfig
from app.orchestrator import RebuildOrchestrator
from app.parsers.sonic_text_parser import SonicTextParser
from app.storage.models import RawSonicItem, RebuildStats, SnapshotFreshness
from app.telegram_client import TelegramSourceClient
from app.watchers import TelegramWatchers


US_FLAG = "\U0001F1FA\U0001F1F8"


class FakeTelethonClient:
    def __init__(self, messages) -> None:
        self._messages = messages

    async def iter_messages(self, _entity, limit=None):
        yielded = 0
        for message in self._messages:
            if limit is not None and yielded >= limit:
                break
            yielded += 1
            yield message


class FakeRunner:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def request(self, reason: str) -> None:
        self.reasons.append(reason)


class FakeCache:
    def __init__(self, cached_items: list[RawSonicItem] | None = None) -> None:
        self.cached_items = cached_items or []
        self.saved_batch_text: str | None = None
        self.saved_parsed: list[RawSonicItem] | None = None

    def save_sonic_batch_text(self, text: str) -> None:
        self.saved_batch_text = text

    def save_sonic_parsed(self, items: list[RawSonicItem]) -> None:
        self.saved_parsed = items

    def load_sonic_parsed(self) -> list[RawSonicItem]:
        return self.cached_items


class FailingTelegramClient:
    async def fetch_latest_sonic_batch(self):
        raise RuntimeError("SONIC scan failed")


def build_message(message_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=message_id,
        date=datetime(2026, 3, 30, 12, message_id % 60, tzinfo=timezone.utc),
        message=text,
        raw_text=text,
    )


def test_sonic_price_detector_accepts_single_line_message() -> None:
    parser = SonicTextParser()
    line = f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}"

    assert parser.is_price_message(line) is True
    assert parser.count_valid_price_lines(line) == 1


def test_sonic_price_detector_rejects_informational_message() -> None:
    parser = SonicTextParser()
    info_message = (
        "Возврат брака: принимаем устройства в первоначальном виде "
        "и с ненарушенным комплектом"
    )

    assert parser.is_price_message(info_message) is False
    assert parser.count_valid_price_lines(info_message) == 0


def test_sonic_batch_scans_all_messages_and_filters_price_messages() -> None:
    config = AppConfig.model_validate(
        {
            "telegram": {
                "api_id": 1,
                "api_hash": "hash",
                "best_channel": -1001,
                "best_message_id": 10,
                "sonic_channel": -1002,
                "sonic_scan_limit": 200,
            }
        }
    )
    source_client = TelegramSourceClient(config.telegram)
    source_client._client = FakeTelethonClient(
        [
            build_message(103, f"iPad 11 256 Pink Wi-Fi - 35.900 {US_FLAG}"),
            build_message(102, "УЦЕНКА\nhttps://t.me/example"),
            build_message(
                101,
                "iPad 11 (A16) 2025\n"
                f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}\n"
                f"iPad 11 128 Pink LTE - 43.500 {US_FLAG}",
            ),
        ]
    )
    source_client.sonic_entity = object()

    batch = asyncio.run(source_client.fetch_latest_sonic_batch())

    assert batch.scanned_message_count == 3
    assert batch.message_ids == [101, 103]
    assert batch.non_price_message_ids == [102]
    assert batch.raw_text == (
        "iPad 11 (A16) 2025\n"
        f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}\n"
        f"iPad 11 128 Pink LTE - 43.500 {US_FLAG}\n\n"
        f"iPad 11 256 Pink Wi-Fi - 35.900 {US_FLAG}"
    )


def test_any_sonic_new_message_triggers_rebuild() -> None:
    config = AppConfig.model_validate(
        {
            "telegram": {
                "api_id": 1,
                "api_hash": "hash",
                "best_channel": -1001,
                "best_message_id": 10,
                "sonic_channel": -1002,
            }
        }
    )
    runner = FakeRunner()
    source_client = SimpleNamespace(client=object(), best_entity=object(), sonic_entity=object())
    watchers = TelegramWatchers(config, source_client, runner)

    asyncio.run(watchers._on_sonic_new_message(SimpleNamespace(message=build_message(999, "Any"))))

    assert runner.reasons == ["SONIC new:999"]


def test_any_sonic_edit_message_triggers_rebuild() -> None:
    config = AppConfig.model_validate(
        {
            "telegram": {
                "api_id": 1,
                "api_hash": "hash",
                "best_channel": -1001,
                "best_message_id": 10,
                "sonic_channel": -1002,
            }
        }
    )
    runner = FakeRunner()
    source_client = SimpleNamespace(client=object(), best_entity=object(), sonic_entity=object())
    watchers = TelegramWatchers(config, source_client, runner)

    asyncio.run(
        watchers._on_sonic_message_edited(SimpleNamespace(message=build_message(777, "Edited")))
    )

    assert runner.reasons == ["SONIC edited:777"]


def test_orchestrator_uses_cached_sonic_items_when_scan_fails() -> None:
    cached_items = [
        RawSonicItem(
            batch_message_ids=[1],
            line_number=1,
            raw_name="iPad 11 128 Silver Wi-Fi",
            full_name="iPad 11 128 Silver Wi-Fi",
            price=27900,
            country_flag=US_FLAG,
        )
    ]
    cache = FakeCache(cached_items)
    orchestrator = RebuildOrchestrator(
        telegram_client=FailingTelegramClient(),
        cache=cache,
        best_parser=SimpleNamespace(),
        sonic_parser=SonicTextParser(),
        normalizer=SimpleNamespace(),
        matcher=SimpleNamespace(),
        sheets_writer=None,
    )
    stats = RebuildStats(trigger="test")

    items = asyncio.run(orchestrator._load_sonic(stats))

    assert len(items) == 1
    assert items[0].raw_name == cached_items[0].raw_name
    assert items[0].snapshot_freshness == SnapshotFreshness.STALE
    assert stats.sonic_from_cache is True
    assert any("SONIC fetch/parse failed" in error for error in stats.errors)
