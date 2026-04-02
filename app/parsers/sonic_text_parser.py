from __future__ import annotations

import re

from app.storage.models import (
    RawSonicItem,
    SonicBatch,
    SonicChannelSnapshot,
    SonicSectionSnapshot,
    TelegramTextMessage,
    utcnow,
)
from app.utils.parsing import clean_text, extract_flag, extract_model_code, parse_price


ITEM_RE = re.compile(
    r"^(?P<name>.+?)\s*[-\u2013\u2014]\s*(?P<price>\d[\d\s.,]*)\s*(?P<tail>.*)$"
)
PRODUCT_HINTS = (
    "iphone",
    "ipad",
    "macbook",
    "imac",
    "airpods",
    "watch",
    "keyboard",
    "pencil",
    "magsafe",
    "airtag",
    "mouse",
    "trackpad",
    "case",
    "folio",
)
PLACEHOLDER_CHARS = ".•·●-–—_=~*▪▫"
CLOSED_KEYWORDS = (
    "закрыто",
    "закрыли",
    "closed",
    "close",
    "pricesclosed",
    "priceclosed",
)
MIN_PRICE_VALUE = 1000


class SonicTextParser:
    def parse_channel(self, batch: SonicBatch) -> SonicChannelSnapshot:
        messages = batch.messages or [
            TelegramTextMessage(
                message_id=batch.message_ids[0] if batch.message_ids else 0,
                date=batch.started_at or utcnow(),
                text=batch.raw_text,
            )
        ]
        sections: list[SonicSectionSnapshot] = []
        current_section: str | None = None
        current_items: list[RawSonicItem] = []
        current_message_ids: set[int] = set()
        open_message_ids: list[int] = []
        closed_message_ids: list[int] = []
        ignored_message_ids: list[int] = []

        def flush_section() -> None:
            nonlocal current_items, current_message_ids
            if not current_items:
                return
            sections.append(
                SonicSectionSnapshot(
                    section_name=current_section,
                    message_ids=sorted(current_message_ids),
                    items=current_items,
                )
            )
            current_items = []
            current_message_ids = set()

        for message in messages:
            text = clean_text(message.text)
            if not text:
                ignored_message_ids.append(message.message_id)
                continue

            if self._is_placeholder_message(text):
                closed_message_ids.append(message.message_id)
                continue

            valid_price_lines = self.count_valid_price_lines(text)
            if valid_price_lines == 0:
                ignored_message_ids.append(message.message_id)
                continue

            open_message_ids.append(message.message_id)

            for line_number, raw_line in enumerate(message.text.splitlines(), start=1):
                line = clean_text(raw_line)
                if not line:
                    continue

                parsed = self.parse_line(
                    line=line,
                    line_number=line_number,
                    current_section=current_section,
                    batch_message_ids=[message.message_id],
                )
                if parsed is not None:
                    current_items.append(parsed)
                    current_message_ids.add(message.message_id)
                    continue

                next_section = self._next_section(current_section, line)
                if next_section != current_section and next_section is not None:
                    flush_section()
                    current_section = next_section
                    continue

                if next_section is None:
                    current_section = None

        flush_section()

        return SonicChannelSnapshot(
            scanned_message_count=len(messages),
            open_message_ids=open_message_ids,
            closed_message_ids=closed_message_ids,
            ignored_message_ids=ignored_message_ids,
            sections=sections,
        )

    def count_valid_price_lines(self, text: str) -> int:
        current_section: str | None = None
        count = 0

        for raw_line in text.splitlines():
            line = clean_text(raw_line)
            if not line:
                continue

            parsed = self.parse_line(
                line=line,
                line_number=0,
                current_section=current_section,
                batch_message_ids=[],
            )
            if parsed is not None:
                count += 1
                continue

            current_section = self._next_section(current_section, line)

        return count

    def is_price_message(self, text: str) -> bool:
        return self.count_valid_price_lines(text) >= 1

    def parse_batch(self, batch: SonicBatch) -> list[RawSonicItem]:
        snapshot = self.parse_channel(batch)
        items: list[RawSonicItem] = []
        for section in snapshot.sections:
            items.extend(section.items)
        return items

    def parse_line(
        self,
        *,
        line: str,
        line_number: int,
        current_section: str | None,
        batch_message_ids: list[int],
    ) -> RawSonicItem | None:
        match = ITEM_RE.match(line)
        if not match:
            return None

        raw_name = clean_text(match.group("name"))
        raw_price = clean_text(match.group("price"))
        tail = clean_text(match.group("tail"))
        full_name = self._compose_full_name(current_section, raw_name)
        price = parse_price(raw_price)

        if not self._is_valid_price_item(full_name=full_name, price=price):
            return None

        return RawSonicItem(
            batch_message_ids=batch_message_ids,
            line_number=line_number,
            raw_name=raw_name,
            full_name=full_name,
            section_name=current_section,
            raw_price=raw_price,
            price=price,
            raw_flag=tail or None,
            country_flag=extract_flag(tail) or extract_flag(raw_name) or extract_flag(full_name),
            model_code=extract_model_code(raw_name),
        )

    def _compose_full_name(self, section_name: str | None, raw_name: str) -> str:
        if not section_name:
            return raw_name
        lowered = raw_name.lower()
        if section_name.lower() in lowered:
            return raw_name
        return f"{section_name} {raw_name}".strip()

    def _next_section(self, current_section: str | None, line: str) -> str | None:
        if self._is_section_line(line):
            return line
        if not any(char.isalnum() for char in line):
            return None
        return current_section

    def _is_section_line(self, line: str) -> bool:
        normalized = clean_text(line)
        if not normalized:
            return False
        if ITEM_RE.match(normalized):
            return False
        if self._is_placeholder_line(normalized) or self._is_close_keyword_line(normalized):
            return False
        if not any(char.isalnum() for char in normalized):
            return False
        return re.sub(r"[-–—\s]+", "", normalized) != ""

    def _is_valid_price_item(self, *, full_name: str, price: int | None) -> bool:
        if price is None or price < MIN_PRICE_VALUE:
            return False

        normalized_name = clean_text(full_name).lower()
        if not any(char.isalpha() for char in normalized_name):
            return False

        return any(hint in normalized_name for hint in PRODUCT_HINTS)

    def _is_placeholder_message(self, text: str) -> bool:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        if not lines:
            return False
        return all(
            self._is_placeholder_line(line) or self._is_close_keyword_line(line)
            for line in lines
        )

    def _is_placeholder_line(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", clean_text(text))
        if not compact:
            return False
        return re.fullmatch(rf"[{re.escape(PLACEHOLDER_CHARS)}]+", compact) is not None

    def _is_close_keyword_line(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", clean_text(text)).lower()
        if not compact:
            return False
        return any(keyword in compact for keyword in CLOSED_KEYWORDS)
