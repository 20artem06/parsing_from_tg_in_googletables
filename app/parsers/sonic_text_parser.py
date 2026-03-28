from __future__ import annotations

import re

from app.storage.models import RawSonicItem, SonicBatch
from app.utils.parsing import clean_text, extract_flag, extract_model_code, parse_price


ITEM_RE = re.compile(r"^(?P<name>.+?)\s*[-–—]\s*(?P<price>\d[\d\s.,]*)\s*(?P<tail>.*)$")


class SonicTextParser:
    def parse_batch(self, batch: SonicBatch) -> list[RawSonicItem]:
        items: list[RawSonicItem] = []
        current_section: str | None = None

        for line_number, raw_line in enumerate(batch.raw_text.splitlines(), start=1):
            line = clean_text(raw_line)
            if not line:
                continue
            parsed = self.parse_line(
                line=line,
                line_number=line_number,
                current_section=current_section,
                batch_message_ids=batch.message_ids,
            )
            if parsed is None:
                current_section = line
                continue
            if parsed.section_name is None:
                parsed.section_name = current_section
            items.append(parsed)

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

        return RawSonicItem(
            batch_message_ids=batch_message_ids,
            line_number=line_number,
            raw_name=raw_name,
            full_name=full_name,
            section_name=current_section,
            raw_price=raw_price,
            price=parse_price(raw_price),
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
