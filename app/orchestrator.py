from __future__ import annotations

import logging

from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.parsers.best_excel_parser import BestExcelParser
from app.parsers.sonic_text_parser import SonicTextParser
from app.sheets.google_sheets import GoogleSheetsWriter
from app.storage.cache import CacheStore
from app.storage.models import MergeResult, RebuildStats, utcnow
from app.telegram_client import TelegramSourceClient


class RebuildOrchestrator:
    def __init__(
        self,
        *,
        telegram_client: TelegramSourceClient,
        cache: CacheStore,
        best_parser: BestExcelParser,
        sonic_parser: SonicTextParser,
        normalizer: ItemNormalizer,
        matcher: MatchingEngine,
        sheets_writer: GoogleSheetsWriter | None = None,
    ) -> None:
        self.telegram_client = telegram_client
        self.cache = cache
        self.best_parser = best_parser
        self.sonic_parser = sonic_parser
        self.normalizer = normalizer
        self.matcher = matcher
        self.sheets_writer = sheets_writer
        self.logger = logging.getLogger(__name__)

    async def rebuild(self, trigger: str) -> MergeResult:
        stats = RebuildStats(trigger=trigger)
        self.logger.info("Rebuild requested by trigger=%s", trigger)

        best_raw = await self._load_best(stats)
        stats.best_raw_count = len(best_raw)
        self.logger.info("Parsed BEST raw rows = %s", stats.best_raw_count)

        sonic_raw = await self._load_sonic(stats)
        stats.sonic_raw_count = len(sonic_raw)
        self.logger.info("Parsed SONIC raw rows = %s", stats.sonic_raw_count)

        best_normalized = self.normalizer.normalize_best(best_raw)
        sonic_normalized = self.normalizer.normalize_sonic(sonic_raw)
        stats.best_normalized_count = len(best_normalized)
        stats.sonic_normalized_count = len(sonic_normalized)
        self.logger.info("Normalized BEST rows = %s", stats.best_normalized_count)
        self.logger.info("Normalized SONIC rows = %s", stats.sonic_normalized_count)

        if not best_normalized and not sonic_normalized:
            cached_merged = self.cache.load_merged()
            if cached_merged is not None:
                stats.used_cached_merged = True
                stats.finished_at = utcnow()
                cached_merged.stats = stats
                self.logger.warning("No fresh sources available, returning cached merged snapshot")
                return cached_merged

        result = self.matcher.merge(best_normalized, sonic_normalized, stats)
        result.stats.finished_at = utcnow()
        self.logger.info(
            "Merged rows = %s | overridden by SONIC = %s | appended new from SONIC = %s",
            result.stats.merged_count,
            result.stats.overridden_by_sonic,
            result.stats.appended_new_from_sonic,
        )

        self.cache.save_merged(result)
        self.cache.save_stats(result.stats)

        if self.sheets_writer is not None:
            try:
                await self.sheets_writer.write_snapshot(result.items)
                self.logger.info("Google Sheets updated successfully")
            except Exception as exc:  # pragma: no cover - network path
                self.logger.exception("Google Sheets update failed")
                result.stats.errors.append(f"Google Sheets update failed: {exc}")
                self.cache.save_stats(result.stats)

        return result

    async def _load_best(self, stats: RebuildStats):
        payload: bytes | None = None
        try:
            payload = await self.telegram_client.download_best_excel_bytes()
            self.cache.save_best_excel(payload)
            self.logger.info("Downloaded new BEST Excel payload")
        except Exception as exc:
            stats.best_from_cache = True
            stats.errors.append(f"BEST download failed: {exc}")
            self.logger.exception("BEST download failed, attempting cache fallback")
            payload = self.cache.load_best_excel()

        if payload is not None:
            try:
                items = self.best_parser.parse_bytes(payload)
                self.cache.save_best_parsed(items)
                return items
            except Exception as exc:
                stats.best_from_cache = True
                stats.errors.append(f"BEST parse failed: {exc}")
                self.logger.exception("BEST parse failed, attempting parsed cache fallback")

        cached_items = self.cache.load_best_parsed()
        if cached_items:
            self.logger.warning("Using cached BEST parsed payload")
        else:
            self.logger.warning("No BEST cache available")
        return cached_items

    async def _load_sonic(self, stats: RebuildStats):
        try:
            batch = await self.telegram_client.fetch_latest_sonic_batch()
            self.cache.save_sonic_batch_text(batch.raw_text)
            self.logger.info(
                "Loaded SONIC batch with %s messages",
                len(batch.message_ids),
            )
            items = self.sonic_parser.parse_batch(batch)
            self.cache.save_sonic_parsed(items)
            return items
        except Exception as exc:
            stats.sonic_from_cache = True
            stats.errors.append(f"SONIC fetch/parse failed: {exc}")
            self.logger.exception("SONIC load failed, attempting parsed cache fallback")

        cached_items = self.cache.load_sonic_parsed()
        if cached_items:
            self.logger.warning("Using cached SONIC parsed payload")
        else:
            self.logger.warning("No SONIC cache available")
        return cached_items
