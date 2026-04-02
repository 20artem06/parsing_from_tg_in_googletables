from __future__ import annotations

import logging
import re
from collections import Counter

from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.parsers.best_excel_parser import BestExcelParser
from app.parsers.sonic_text_parser import SonicTextParser
from app.sheets.google_sheets import GoogleSheetsWriter
from app.storage.cache import CacheStore
from app.storage.models import (
    BestSheetState,
    MergeResult,
    RawBestItem,
    RawSonicItem,
    RebuildStats,
    SnapshotFreshness,
    SonicSectionSnapshot,
    SonicSectionState,
    SourcePartState,
    utcnow,
)
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
        if result.stats.best_overrode_stale_sonic:
            self.logger.info(
                "BEST reopened before SONIC: fresh BEST overrides stale SONIC on overlapping rows = %s",
                result.stats.best_overrode_stale_sonic,
            )
        if any(item.snapshot_freshness == SnapshotFreshness.FRESH for item in sonic_normalized):
            self.logger.info("SONIC reopened: returning to SONIC priority for refreshed sections")
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

    async def _load_best(self, stats: RebuildStats) -> list[RawBestItem]:
        previous_states = {
            state.part_key: state for state in self._load_best_states()
        }
        now = utcnow()
        payload: bytes | None = None
        parsed_by_sheet: dict[str, list[RawBestItem]] | None = None

        try:
            payload = await self.telegram_client.download_best_excel_bytes()
            self.cache.save_best_excel(payload)
            self.logger.info("Downloaded new BEST Excel payload")
        except Exception as exc:
            stats.errors.append(f"BEST download failed: {exc}")
            self.logger.exception("BEST download failed, attempting cache fallback")
            payload = None

        if payload is not None:
            try:
                parsed_by_sheet = self.best_parser.parse_bytes_by_sheet(payload)
            except Exception as exc:
                stats.errors.append(f"BEST parse failed: {exc}")
                self.logger.exception("BEST parse failed, falling back to per-sheet cache")

        sheet_states: list[BestSheetState] = []
        effective_rows: list[RawBestItem] = []

        if parsed_by_sheet is not None:
            for sheet_name in parsed_by_sheet:
                part_key = self._best_part_key(sheet_name)
                previous = previous_states.get(part_key)
                fresh_rows = self._mark_best_rows(
                    parsed_by_sheet[sheet_name],
                    part_key=part_key,
                    freshness=SnapshotFreshness.FRESH,
                )
                if fresh_rows:
                    effective_rows.extend(fresh_rows)
                    state = BestSheetState(
                        part_key=part_key,
                        sheet_name=sheet_name,
                        state=SourcePartState.OPEN,
                        current_rows=fresh_rows,
                        last_valid_rows=fresh_rows,
                        last_valid_at=now,
                        last_seen_at=now,
                        source_meta={"row_count": len(fresh_rows)},
                    )
                else:
                    stale_rows = self._reuse_best_rows(previous, part_key)
                    if stale_rows:
                        stats.best_from_cache = True
                        self.logger.info(
                            "Using last valid rows for closed BEST sheet %s",
                            sheet_name,
                        )
                        effective_rows.extend(stale_rows)
                    state = BestSheetState(
                        part_key=part_key,
                        sheet_name=sheet_name,
                        state=SourcePartState.CLOSED,
                        current_rows=[],
                        last_valid_rows=previous.last_valid_rows if previous else [],
                        last_valid_at=previous.last_valid_at if previous else None,
                        last_seen_at=now,
                        source_meta={"row_count": len(stale_rows)},
                    )
                self.logger.info(
                    "BEST sheet %s state=%s rows=%s",
                    sheet_name,
                    state.state.value,
                    len(state.current_rows if state.state == SourcePartState.OPEN else state.last_valid_rows),
                )
                sheet_states.append(state)
        else:
            for part_key, previous in previous_states.items():
                stale_rows = self._reuse_best_rows(previous, part_key)
                if stale_rows:
                    effective_rows.extend(stale_rows)
                    stats.best_from_cache = True
                self.logger.error(
                    "Technical read failure for BEST part %s, using cached rows=%s",
                    previous.sheet_name,
                    len(stale_rows),
                )
                sheet_states.append(
                    BestSheetState(
                        part_key=part_key,
                        sheet_name=previous.sheet_name,
                        state=SourcePartState.FAILED,
                        current_rows=[],
                        last_valid_rows=previous.last_valid_rows,
                        last_valid_at=previous.last_valid_at,
                        last_seen_at=now,
                        source_meta=previous.source_meta,
                    )
                )

        self._save_best_states(sheet_states)
        self.cache.save_best_parsed(effective_rows)
        if not effective_rows and previous_states:
            self.logger.warning("No BEST effective rows available after per-sheet fallback")
        return effective_rows

    async def _load_sonic(self, stats: RebuildStats) -> list[RawSonicItem]:
        previous_states = {
            state.part_key: state for state in self._load_sonic_states()
        }
        now = utcnow()
        try:
            batch = await self.telegram_client.fetch_latest_sonic_batch()
            self.cache.save_sonic_batch_text(batch.raw_text)
            snapshot = self.sonic_parser.parse_channel(batch)
            self.logger.info("Scanned SONIC channel messages = %s", snapshot.scanned_message_count)
            self.logger.info("Detected SONIC price messages = %s", len(snapshot.open_message_ids))
            self.logger.info("Detected SONIC closed messages = %s", len(snapshot.closed_message_ids))
            self.logger.info("Skipped non-price SONIC messages = %s", len(snapshot.ignored_message_ids))

            current_sections = self._merge_sonic_sections(snapshot.sections, previous_states)
            section_states: list[SonicSectionState] = []
            effective_rows: list[RawSonicItem] = []
            open_part_keys = {section.part_key for section in current_sections}

            for section in current_sections:
                fresh_rows = self._mark_sonic_rows(
                    section.items,
                    part_key=section.part_key,
                    block_key=section.block_key,
                    section_key=section.section_key,
                    freshness=SnapshotFreshness.FRESH,
                )
                effective_rows.extend(fresh_rows)
                state = SonicSectionState(
                    part_key=section.part_key,
                    block_key=section.block_key,
                    section_key=section.section_key,
                    section_name=section.section_name,
                    state=SourcePartState.OPEN,
                    current_rows=fresh_rows,
                    last_valid_rows=fresh_rows,
                    last_valid_at=now,
                    last_seen_at=now,
                    source_meta={
                        "message_ids": section.message_ids,
                        "row_count": len(fresh_rows),
                    },
                )
                self.logger.info(
                    "SONIC section %s block=%s state=%s rows=%s",
                    state.section_key,
                    state.block_key,
                    state.state.value,
                    len(state.current_rows),
                )
                section_states.append(state)

            for part_key, previous in previous_states.items():
                if part_key in open_part_keys:
                    continue
                stale_rows = self._reuse_sonic_rows(previous, part_key)
                if stale_rows:
                    stats.sonic_from_cache = True
                    self.logger.info(
                        "Using last valid rows for closed SONIC section %s",
                        previous.section_key,
                    )
                    effective_rows.extend(stale_rows)
                state = SonicSectionState(
                    part_key=part_key,
                    block_key=previous.block_key,
                    section_key=previous.section_key,
                    section_name=previous.section_name,
                    state=SourcePartState.CLOSED,
                    current_rows=[],
                    last_valid_rows=previous.last_valid_rows,
                    last_valid_at=previous.last_valid_at,
                    last_seen_at=now,
                    source_meta=previous.source_meta,
                )
                self.logger.info(
                    "SONIC section %s block=%s state=%s rows=%s",
                    state.section_key,
                    state.block_key,
                    state.state.value,
                    len(state.last_valid_rows),
                )
                section_states.append(state)

            self._save_sonic_states(section_states)
            self.cache.save_sonic_parsed(effective_rows)
            self.logger.info("Parsed SONIC rows = %s", len(effective_rows))
            return effective_rows
        except Exception as exc:
            stats.errors.append(f"SONIC fetch/parse failed: {exc}")
            self.logger.exception("SONIC load failed, falling back to per-section cache")

        section_states: list[SonicSectionState] = []
        effective_rows: list[RawSonicItem] = []
        for part_key, previous in previous_states.items():
            stale_rows = self._reuse_sonic_rows(previous, part_key)
            if stale_rows:
                effective_rows.extend(stale_rows)
                stats.sonic_from_cache = True
            self.logger.error(
                "Technical read failure for SONIC part %s, using cached rows=%s",
                previous.section_key,
                len(stale_rows),
            )
            section_states.append(
                SonicSectionState(
                    part_key=part_key,
                    block_key=previous.block_key,
                    section_key=previous.section_key,
                    section_name=previous.section_name,
                    state=SourcePartState.FAILED,
                    current_rows=[],
                    last_valid_rows=previous.last_valid_rows,
                    last_valid_at=previous.last_valid_at,
                    last_seen_at=now,
                    source_meta=previous.source_meta,
                )
            )

        self._save_sonic_states(section_states)
        self.cache.save_sonic_parsed(effective_rows)
        if not effective_rows and previous_states:
            self.logger.warning("No SONIC effective rows available after per-section fallback")
        return effective_rows

    def _load_best_states(self) -> list[BestSheetState]:
        if hasattr(self.cache, "load_best_parts_state"):
            return self.cache.load_best_parts_state()

        rows = self.cache.load_best_parsed()
        grouped: dict[str, list[RawBestItem]] = {}
        for row in rows:
            part_key = row.part_key or self._best_part_key(row.sheet_name)
            grouped.setdefault(part_key, []).append(row)

        now = utcnow()
        return [
            BestSheetState(
                part_key=part_key,
                sheet_name=items[0].sheet_name,
                state=SourcePartState.OPEN,
                current_rows=[],
                last_valid_rows=self._mark_best_rows(
                    items,
                    part_key=part_key,
                    freshness=SnapshotFreshness.STALE,
                ),
                last_valid_at=now,
                last_seen_at=now,
                source_meta={"row_count": len(items)},
            )
            for part_key, items in grouped.items()
        ]

    def _save_best_states(self, states: list[BestSheetState]) -> None:
        if hasattr(self.cache, "save_best_parts_state"):
            self.cache.save_best_parts_state(states)

    def _load_sonic_states(self) -> list[SonicSectionState]:
        if hasattr(self.cache, "load_sonic_parts_state"):
            return self.cache.load_sonic_parts_state()

        rows = self.cache.load_sonic_parsed()
        grouped: dict[str, list[RawSonicItem]] = {}
        for row in rows:
            block_key = row.block_key or "dynamic::legacy"
            section_key = row.section_key or self._slug(row.section_name or row.full_name or row.raw_name)
            part_key = row.part_key or self._sonic_part_key(block_key, section_key)
            grouped.setdefault(part_key, []).append(
                row.model_copy(
                    update={
                        "block_key": block_key,
                        "section_key": section_key,
                        "part_key": part_key,
                    }
                )
            )

        now = utcnow()
        return [
            SonicSectionState(
                part_key=part_key,
                block_key=items[0].block_key or "dynamic::legacy",
                section_key=items[0].section_key or self._slug(items[0].section_name or items[0].full_name),
                section_name=items[0].section_name,
                state=SourcePartState.OPEN,
                current_rows=[],
                last_valid_rows=self._mark_sonic_rows(
                    items,
                    part_key=part_key,
                    block_key=items[0].block_key or "dynamic::legacy",
                    section_key=items[0].section_key or self._slug(items[0].section_name or items[0].full_name),
                    freshness=SnapshotFreshness.STALE,
                ),
                last_valid_at=now,
                last_seen_at=now,
                source_meta={"row_count": len(items)},
            )
            for part_key, items in grouped.items()
        ]

    def _save_sonic_states(self, states: list[SonicSectionState]) -> None:
        if hasattr(self.cache, "save_sonic_parts_state"):
            self.cache.save_sonic_parts_state(states)

    def _best_part_key(self, sheet_name: str) -> str:
        return f"best::{sheet_name}"

    def _sonic_part_key(self, block_key: str, section_key: str) -> str:
        return f"sonic::{block_key}::{section_key}"

    def _mark_best_rows(
        self,
        rows: list[RawBestItem],
        *,
        part_key: str,
        freshness: SnapshotFreshness,
    ) -> list[RawBestItem]:
        return [
            row.model_copy(update={"part_key": part_key, "snapshot_freshness": freshness})
            for row in rows
        ]

    def _mark_sonic_rows(
        self,
        rows: list[RawSonicItem],
        *,
        part_key: str,
        block_key: str,
        section_key: str,
        freshness: SnapshotFreshness,
    ) -> list[RawSonicItem]:
        return [
            row.model_copy(
                update={
                    "part_key": part_key,
                    "block_key": block_key,
                    "section_key": section_key,
                    "snapshot_freshness": freshness,
                }
            )
            for row in rows
        ]

    def _reuse_best_rows(
        self,
        state: BestSheetState | None,
        part_key: str,
    ) -> list[RawBestItem]:
        if state is None:
            return []
        return self._mark_best_rows(
            state.last_valid_rows,
            part_key=part_key,
            freshness=SnapshotFreshness.STALE,
        )

    def _reuse_sonic_rows(
        self,
        state: SonicSectionState | None,
        part_key: str,
    ) -> list[RawSonicItem]:
        if state is None:
            return []
        return self._mark_sonic_rows(
            state.last_valid_rows,
            part_key=part_key,
            block_key=state.block_key,
            section_key=state.section_key,
            freshness=SnapshotFreshness.STALE,
        )

    def _merge_sonic_sections(
        self,
        sections: list[SonicSectionSnapshot],
        previous_states: dict[str, SonicSectionState] | None = None,
    ) -> list[SonicSectionSnapshot]:
        grouped: dict[str, SonicSectionSnapshot] = {}
        previous_states = previous_states or {}
        used_previous_part_keys: set[str] = set()

        for section in sections:
            if not section.items:
                continue
            normalized_items = self.normalizer.normalize_sonic(section.items)
            block_key = self._classify_sonic_block(section, normalized_items)
            section_key = self._build_sonic_section_key(section, block_key, normalized_items)
            previous_match = self._match_previous_sonic_section(
                block_key=block_key,
                normalized_items=normalized_items,
                previous_states=previous_states,
                used_previous_part_keys=used_previous_part_keys,
            )
            if previous_match is not None:
                used_previous_part_keys.add(previous_match.part_key)
                if previous_match.section_key != section_key:
                    self.logger.info(
                        "SONIC section matched by overlap: block=%s previous=%s candidate=%s",
                        block_key,
                        previous_match.section_key,
                        section_key,
                    )
                section_key = previous_match.section_key
            part_key = self._sonic_part_key(block_key, section_key)
            current = grouped.get(part_key)
            if current is None:
                grouped[part_key] = SonicSectionSnapshot(
                    part_key=part_key,
                    block_key=block_key,
                    section_key=section_key,
                    section_name=section.section_name,
                    message_ids=section.message_ids,
                    items=[
                        item.model_copy(
                            update={
                                "block_key": block_key,
                                "section_key": section_key,
                                "part_key": part_key,
                            }
                        )
                        for item in section.items
                    ],
                )
                continue

            message_ids = sorted(set(current.message_ids) | set(section.message_ids))
            current.message_ids = message_ids
            current.items.extend(
                item.model_copy(
                    update={
                        "block_key": block_key,
                        "section_key": section_key,
                        "part_key": part_key,
                    }
                )
                for item in section.items
            )

        return list(grouped.values())

    def _classify_sonic_block(
        self,
        section: SonicSectionSnapshot,
        normalized_items=None,
    ) -> str:
        normalized_items = normalized_items or self.normalizer.normalize_sonic(section.items)
        category_counts = Counter(item.category for item in normalized_items if item.category)
        if category_counts:
            dominant_category = category_counts.most_common(1)[0][0]
            if dominant_category == "Accessory":
                return "accessories"
            if dominant_category == "iPad":
                return "ipad"
            if dominant_category == "Apple Watch":
                return "watch"
            if dominant_category in {"MacBook", "Mac", "iMac"}:
                return "mac"
            if dominant_category == "iPhone":
                return "iphone"
            if dominant_category == "AirPods":
                return "airpods"
            return f"dynamic::{self._slug(dominant_category)}"

        if section.section_name:
            return f"dynamic::{self._slug(section.section_name)}"
        return "dynamic::unknown"

    def _build_sonic_section_key(
        self,
        section: SonicSectionSnapshot,
        block_key: str,
        normalized_items=None,
    ) -> str:
        normalized_items = normalized_items or self.normalizer.normalize_sonic(section.items)
        explicit_name = self._slug(section.section_name or "")
        semantic_anchor = self._sonic_section_anchor(normalized_items)
        item_stems = list(self._sonic_section_signatures(normalized_items))

        key_parts: list[str] = []
        if explicit_name:
            key_parts.append(explicit_name)
        if semantic_anchor and semantic_anchor not in key_parts:
            key_parts.append(semantic_anchor)
        for stem in item_stems[:2]:
            if stem not in key_parts:
                key_parts.append(stem)

        if key_parts:
            return self._slug("-".join(key_parts))
        return f"{self._slug(block_key)}-section"

    def _match_previous_sonic_section(
        self,
        *,
        block_key: str,
        normalized_items,
        previous_states: dict[str, SonicSectionState],
        used_previous_part_keys: set[str],
    ) -> SonicSectionState | None:
        current_signatures = set(self._sonic_section_signatures(normalized_items))
        if not current_signatures:
            return None

        best_match: SonicSectionState | None = None
        best_score = 0.0

        for previous in previous_states.values():
            if previous.part_key in used_previous_part_keys:
                continue
            if previous.block_key != block_key:
                continue
            previous_normalized = self.normalizer.normalize_sonic(previous.last_valid_rows)
            previous_signatures = set(self._sonic_section_signatures(previous_normalized))
            if not previous_signatures:
                continue
            overlap = current_signatures & previous_signatures
            if not overlap:
                continue
            score = len(overlap) / min(len(current_signatures), len(previous_signatures))
            if score > best_score:
                best_score = score
                best_match = previous

        if best_match is not None and best_score >= 0.6:
            return best_match
        return None

    def _sonic_section_anchor(self, normalized_items) -> str | None:
        identity_counts = Counter(
            self._slug(item.product_line or item.family or item.category or "")
            for item in normalized_items
            if (item.product_line or item.family or item.category)
        )
        if identity_counts:
            return identity_counts.most_common(1)[0][0]
        return None

    def _sonic_section_signatures(self, normalized_items) -> list[str]:
        signatures: list[str] = []
        for item in normalized_items:
            parts = [
                (item.category or "").lower(),
                (item.product_line or "").lower(),
                (item.family or "").lower(),
                (item.generation or "").lower(),
                (item.screen_size or "").lower(),
            ]
            signature = self._slug("-".join(part for part in parts if part))
            if signature and signature not in signatures:
                signatures.append(signature)
        return signatures

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "unknown"
