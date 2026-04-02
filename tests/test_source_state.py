from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from app.config import MatchingConfig
from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.orchestrator import RebuildOrchestrator
from app.parsers.best_excel_parser import BestExcelParser
from app.parsers.sonic_text_parser import SonicTextParser
from app.storage.cache import CacheStore
from app.storage.models import RawBestItem, RawSonicItem, RebuildStats, SnapshotFreshness, TelegramTextMessage


US_FLAG = "\U0001F1FA\U0001F1F8"


class SequencedBestClient:
    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = payloads

    async def download_best_excel_bytes(self) -> bytes:
        return self.payloads.pop(0)


class SequencedSonicClient:
    def __init__(self, batches) -> None:
        self.batches = batches

    async def fetch_latest_sonic_batch(self):
        return self.batches.pop(0)


def _build_best_workbook(*, ipad_rows: list[tuple[str, str | None, str | None]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "iPad"
    sheet.append(["РњРѕРґРµР»СЊ", "РЎС‚РѕРёРјРѕСЃС‚СЊ", "Р¤Р»Р°Рі"])
    for row in ipad_rows:
        sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _build_sonic_batch(*messages: tuple[int, str]):
    telegram_messages = [
        TelegramTextMessage(
            message_id=message_id,
            date=datetime(2026, 4, 2, 12, index, tzinfo=timezone.utc),
            text=text,
        )
        for index, (message_id, text) in enumerate(messages, start=1)
    ]
    return SimpleNamespace(
        requested_message_ids=[],
        scanned_message_count=len(telegram_messages),
        message_ids=[],
        price_message_ids=[],
        closed_message_ids=[],
        missing_message_ids=[],
        non_price_message_ids=[],
        messages=telegram_messages,
        raw_text="\n\n".join(message.text for message in telegram_messages),
        started_at=telegram_messages[0].date if telegram_messages else None,
        finished_at=telegram_messages[-1].date if telegram_messages else None,
    )


def test_best_sheet_uses_last_valid_rows_when_sheet_closes(tmp_path: Path) -> None:
    open_payload = _build_best_workbook(
        ipad_rows=[
            ("iPad 11 (A16) 2025", None, None),
            ("128GB", None, None),
            ("Silver Wi-Fi", "27.900", US_FLAG),
        ]
    )
    closed_payload = _build_best_workbook(ipad_rows=[])

    cache = CacheStore(tmp_path / "cache")
    orchestrator = RebuildOrchestrator(
        telegram_client=SequencedBestClient([open_payload, closed_payload]),
        cache=cache,
        best_parser=BestExcelParser(),
        sonic_parser=SonicTextParser(),
        normalizer=ItemNormalizer(),
        matcher=MatchingEngine(MatchingConfig()),
        sheets_writer=None,
    )

    first = asyncio.run(orchestrator._load_best(RebuildStats(trigger="first")))
    second_stats = RebuildStats(trigger="second")
    second = asyncio.run(orchestrator._load_best(second_stats))

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].full_name == first[0].full_name
    assert second[0].snapshot_freshness == SnapshotFreshness.STALE
    assert second_stats.best_from_cache is True


def test_sonic_open_section_replaces_only_itself_while_closed_section_stays(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "cache")
    client = SequencedSonicClient(
        [
            _build_sonic_batch(
                (
                    101,
                    "iPad 11 (A16) 2025\n"
                    f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}",
                ),
                (
                    102,
                    "Apple Watch S11\n"
                    f"S11 42 Silver SB S/M - 27.500 {US_FLAG}",
                ),
            ),
            _build_sonic_batch(
                (
                    101,
                    "iPad 11 (A16) 2025\n"
                    f"iPad 11 256 Pink Wi-Fi - 35.900 {US_FLAG}",
                ),
                (102, "."),
            ),
        ]
    )
    orchestrator = RebuildOrchestrator(
        telegram_client=client,
        cache=cache,
        best_parser=BestExcelParser(),
        sonic_parser=SonicTextParser(),
        normalizer=ItemNormalizer(),
        matcher=MatchingEngine(MatchingConfig()),
        sheets_writer=None,
    )

    first = asyncio.run(orchestrator._load_sonic(RebuildStats(trigger="first")))
    second = asyncio.run(orchestrator._load_sonic(RebuildStats(trigger="second")))

    assert len(first) == 2
    assert any(item.raw_name == "iPad 11 128 Silver Wi-Fi" for item in first)
    assert any("S11 42 Silver SB S/M" in item.raw_name for item in first)

    assert any(item.raw_name == "iPad 11 256 Pink Wi-Fi" for item in second)
    assert not any(item.raw_name == "iPad 11 128 Silver Wi-Fi" for item in second)
    stale_watch = next(item for item in second if "S11 42 Silver SB S/M" in item.raw_name)
    assert stale_watch.snapshot_freshness == SnapshotFreshness.STALE


def test_sonic_section_key_survives_header_rename_by_overlap(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "cache")
    client = SequencedSonicClient(
        [
            _build_sonic_batch(
                (
                    201,
                    "iPad 11 (A16) 2025\n"
                    f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}\n"
                    f"iPad 11 256 Pink Wi-Fi - 35.900 {US_FLAG}",
                ),
            ),
            _build_sonic_batch(
                (
                    202,
                    "iPad 11 2025 refreshed\n"
                    f"iPad 11 128 Silver Wi-Fi - 27.900 {US_FLAG}\n"
                    f"iPad 11 256 Pink Wi-Fi - 35.900 {US_FLAG}",
                ),
            ),
        ]
    )
    orchestrator = RebuildOrchestrator(
        telegram_client=client,
        cache=cache,
        best_parser=BestExcelParser(),
        sonic_parser=SonicTextParser(),
        normalizer=ItemNormalizer(),
        matcher=MatchingEngine(MatchingConfig()),
        sheets_writer=None,
    )

    asyncio.run(orchestrator._load_sonic(RebuildStats(trigger="first")))
    first_states = cache.load_sonic_parts_state()

    asyncio.run(orchestrator._load_sonic(RebuildStats(trigger="second")))
    second_states = cache.load_sonic_parts_state()

    assert len(first_states) == 1
    assert len(second_states) == 1
    assert second_states[0].section_key == first_states[0].section_key
    assert second_states[0].part_key == first_states[0].part_key


def test_merge_prefers_fresh_best_over_stale_sonic_on_overlap() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="iPad",
                row_number=1,
                raw_name="Silver Wi-Fi",
                full_name="iPad 11 (A16) 2025 128GB Silver Wi-Fi",
                price=31000,
                country_flag=US_FLAG,
                snapshot_freshness=SnapshotFreshness.FRESH,
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[10],
                line_number=1,
                raw_name="iPad 11 128 Silver Wi-Fi",
                full_name="iPad 11 (A16) 2025 iPad 11 128 Silver Wi-Fi",
                price=27900,
                country_flag=US_FLAG,
                snapshot_freshness=SnapshotFreshness.STALE,
            )
        ]
    )
    matcher = MatchingEngine(MatchingConfig())
    stats = RebuildStats(trigger="test")

    merged = matcher.merge(best, sonic, stats)

    assert len(merged.items) == 1
    assert merged.items[0].price_source == "BEST"
    assert merged.items[0].price == 31000
    assert merged.stats.best_overrode_stale_sonic == 1
