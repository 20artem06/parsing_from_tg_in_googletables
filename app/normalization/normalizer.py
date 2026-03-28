from __future__ import annotations

import re
from collections.abc import Iterable

from app.normalization.aliases import (
    ACCESSORY_KEYWORDS,
    CATEGORY_BY_SHEET,
    CATEGORY_KEYWORDS,
    COLOR_ALIASES,
    CONNECTIVITY_ALIASES,
    STOPWORDS,
)
from app.normalization.patterns import (
    AIRPODS_RE,
    CHIP_RE,
    IMAC_RE,
    IPAD_RE,
    IPHONE_RE,
    MACBOOK_RE,
    MM_SIZE_RE,
    RAM_RE,
    SCREEN_RE,
    STORAGE_RE,
    WATCH_RE,
    YEAR_RE,
)
from app.storage.models import NormalizedItem, RawBestItem, RawSonicItem, SourceKind
from app.utils.parsing import clean_text, extract_flag, extract_model_code


class ItemNormalizer:
    def __init__(self, currency: str = "RUB") -> None:
        self.currency = currency

    def normalize_best(self, items: Iterable[RawBestItem]) -> list[NormalizedItem]:
        return [self._normalize_best_item(item) for item in items]

    def normalize_sonic(self, items: Iterable[RawSonicItem]) -> list[NormalizedItem]:
        return [self._normalize_sonic_item(item) for item in items]

    def _normalize_best_item(self, item: RawBestItem) -> NormalizedItem:
        return self._normalize_common(
            source=SourceKind.BEST,
            source_ref=f"{item.sheet_name}:{item.row_number}",
            raw_name=item.raw_name,
            full_name=item.full_name,
            price=item.price,
            currency=item.currency,
            raw_flag=item.raw_flag,
            country_flag=item.country_flag,
            source_sheet=item.sheet_name,
            source_section=" | ".join(item.section_path) if item.section_path else None,
            forced_category=CATEGORY_BY_SHEET.get(item.sheet_name),
            model_code=extract_model_code(item.full_name),
        )

    def _normalize_sonic_item(self, item: RawSonicItem) -> NormalizedItem:
        return self._normalize_common(
            source=SourceKind.SONIC,
            source_ref=f"messages:{','.join(str(value) for value in item.batch_message_ids)}:{item.line_number}",
            raw_name=item.raw_name,
            full_name=item.full_name,
            price=item.price,
            currency=item.currency,
            raw_flag=item.raw_flag,
            country_flag=item.country_flag,
            source_sheet=None,
            source_section=item.section_name,
            forced_category=None,
            model_code=item.model_code or extract_model_code(item.full_name),
        )

    def _normalize_common(
        self,
        *,
        source: SourceKind,
        source_ref: str,
        raw_name: str,
        full_name: str,
        price: int | None,
        currency: str,
        raw_flag: str | None,
        country_flag: str | None,
        source_sheet: str | None,
        source_section: str | None,
        forced_category: str | None,
        model_code: str | None,
    ) -> NormalizedItem:
        base_text = clean_text(full_name)
        prepared = self._prepare_text(base_text)
        country_flag = country_flag or extract_flag(base_text)
        category = forced_category or self._detect_category(prepared, source_section)
        color = self._extract_alias(prepared, COLOR_ALIASES)
        connectivity = self._extract_connectivity(prepared)
        storage_gb = self._extract_storage_gb(prepared)
        ram_gb = self._extract_ram_gb(prepared)
        year = self._extract_year(prepared)
        chip = self._extract_chip(prepared)
        family, product_line, generation, screen_size, size_label = self._extract_family_bundle(
            prepared,
            category,
        )

        canonical_name = self._build_canonical_name(
            category=category,
            product_line=product_line,
            family=family,
            generation=generation,
            year=year,
            chip=chip,
            screen_size=screen_size,
            storage_gb=storage_gb,
            ram_gb=ram_gb,
            connectivity=connectivity,
            color=color,
            size_label=size_label,
            model_code=model_code,
        )
        canonical_key = self._build_canonical_key(
            category=category,
            product_line=product_line,
            family=family,
            generation=generation,
            year=year,
            chip=chip,
            screen_size=screen_size,
            storage_gb=storage_gb,
            ram_gb=ram_gb,
            connectivity=connectivity,
            color=color,
            size_label=size_label,
            model_code=model_code,
        )

        return NormalizedItem(
            source=source,
            source_ref=source_ref,
            raw_name=raw_name,
            full_name=full_name,
            category=category,
            product_line=product_line,
            family=family,
            generation=generation,
            year=year,
            chip=chip,
            screen_size=screen_size,
            storage_gb=storage_gb,
            ram_gb=ram_gb,
            connectivity=connectivity,
            color=color,
            size_label=size_label,
            model_code=model_code,
            raw_flag=raw_flag,
            country_flag=country_flag,
            price=price,
            currency=currency or self.currency,
            canonical_name=canonical_name,
            canonical_key=canonical_key,
            tokens=self._tokenize(canonical_name or prepared),
            source_sheet=source_sheet,
            source_section=source_section,
        )

    def _prepare_text(self, text: str) -> str:
        prepared = text.lower().replace("ё", "е")
        replacements = {
            "wi-fi": "wifi",
            "wi fi": "wifi",
            "wifi + cellular": "cellular",
            "wi-fi + cellular": "cellular",
            "wi-fi+cellular": "cellular",
            "wifi+cellular": "cellular",
            "гб": "gb",
            "тб": "tb",
            "—": "-",
            "–": "-",
            "_": " ",
            "/": " ",
        }
        for old, new in replacements.items():
            prepared = prepared.replace(old, new)
        prepared = re.sub(r"[(),;]+", " ", prepared)
        prepared = re.sub(r"\s+", " ", prepared)
        return prepared.strip()

    def _detect_category(self, prepared: str, section_name: str | None) -> str:
        text = f"{prepared} {section_name or ''}".strip()
        accessory_keywords = CATEGORY_KEYWORDS["Accessory"]
        if any(keyword in text for keyword in accessory_keywords):
            return "Accessory"
        for category, keywords in CATEGORY_KEYWORDS.items():
            if category == "Accessory":
                continue
            if any(keyword in text for keyword in keywords):
                return category
        return "Accessory"

    def _extract_alias(self, prepared: str, aliases: dict[str, list[str]]) -> str | None:
        for canonical, values in sorted(
            aliases.items(),
            key=lambda item: max(len(alias) for alias in item[1]),
            reverse=True,
        ):
            for alias in values:
                if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", prepared):
                    return canonical
        return None

    def _extract_connectivity(self, prepared: str) -> str | None:
        if "gps+cellular" in prepared or "gps cellular" in prepared:
            return "gps+cellular"
        if "gps" in prepared and "cellular" in prepared:
            return "gps+cellular"
        for canonical, aliases in CONNECTIVITY_ALIASES.items():
            for alias in aliases:
                if alias in prepared:
                    return canonical
        return None

    def _extract_storage_gb(self, prepared: str) -> int | None:
        match = STORAGE_RE.search(prepared)
        if not match:
            return None
        size = int(match.group(1))
        unit = match.group(2).lower()
        return size * 1024 if unit == "tb" else size

    def _extract_ram_gb(self, prepared: str) -> int | None:
        match = RAM_RE.search(prepared)
        return int(match.group(1)) if match else None

    def _extract_year(self, prepared: str) -> int | None:
        match = YEAR_RE.search(prepared)
        return int(match.group(1)) if match else None

    def _extract_chip(self, prepared: str) -> str | None:
        match = CHIP_RE.search(prepared)
        if not match:
            return None
        return match.group(1).upper().replace(" ", "")

    def _extract_family_bundle(
        self,
        prepared: str,
        category: str,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        generation: str | None = None
        screen_size: str | None = None
        size_label: str | None = None

        if category == "iPhone":
            match = IPHONE_RE.search(prepared)
            if match:
                family = f"iphone {match.group(1)}"
                suffix = match.group(2)
                product_line = f"{family} {suffix}".strip() if suffix else family
                return family, product_line, None, None, None
            return "iphone", "iphone", None, None, None

        if category == "iPad":
            match = IPAD_RE.search(prepared)
            if match:
                variant = match.group(1)
                number = match.group(2)
                if variant in {"air", "pro", "mini"}:
                    family = f"ipad {variant}"
                    product_line = family
                    if number:
                        screen_size = number
                elif number:
                    family = f"ipad {number}"
                    product_line = family
                else:
                    family = "ipad"
                    product_line = "ipad"
                return family, product_line, None, screen_size, None
            return "ipad", "ipad", None, None, None

        if category == "MacBook":
            match = MACBOOK_RE.search(prepared)
            if match:
                variant = match.group(1) or ""
                family = f"macbook {variant}".strip()
                product_line = family
                if match.group(2):
                    screen_size = match.group(2)
                return family, product_line, None, screen_size, None
            return "macbook", "macbook", None, None, None

        if category == "iMac":
            match = IMAC_RE.search(prepared)
            if match:
                family = "imac"
                product_line = "imac"
                if match.group(1):
                    screen_size = match.group(1)
                return family, product_line, None, screen_size, None
            return "imac", "imac", None, None, None

        if category == "Apple Watch":
            match = WATCH_RE.search(prepared)
            if match:
                generation = (match.group(1) or "watch").replace("  ", " ").strip()
                mm_match = MM_SIZE_RE.search(prepared)
                size_label = f"{mm_match.group(1)}mm" if mm_match else None
                family = "apple watch"
                product_line = f"apple watch {generation}".strip()
                return family, product_line, generation, None, size_label
            return "apple watch", "apple watch", None, None, None

        if category == "AirPods":
            match = AIRPODS_RE.search(prepared)
            if match:
                variant = match.group(1)
                generation = match.group(2)
                family = "airpods"
                parts = [family]
                if variant:
                    parts.append(variant)
                if generation:
                    parts.append(generation)
                return family, " ".join(parts), generation, None, None
            return "airpods", "airpods", None, None, None

        for keyword, family_name in ACCESSORY_KEYWORDS.items():
            if keyword in prepared:
                screen_match = SCREEN_RE.search(prepared)
                mm_match = MM_SIZE_RE.search(prepared)
                size_label = (
                    screen_match.group(1)
                    if screen_match
                    else (f"{mm_match.group(1)}mm" if mm_match else None)
                )
                return family_name.lower(), family_name, None, None, size_label

        return "accessory", "accessory", None, None, None

    def _build_canonical_name(
        self,
        *,
        category: str,
        product_line: str | None,
        family: str | None,
        generation: str | None,
        year: int | None,
        chip: str | None,
        screen_size: str | None,
        storage_gb: int | None,
        ram_gb: int | None,
        connectivity: str | None,
        color: str | None,
        size_label: str | None,
        model_code: str | None,
    ) -> str:
        parts = [
            product_line or family or category,
            generation,
            str(year) if year else None,
            chip,
            f"{screen_size}in" if screen_size else None,
            f"{storage_gb}GB" if storage_gb else None,
            f"{ram_gb}GB RAM" if ram_gb else None,
            connectivity,
            color,
            size_label,
            model_code,
        ]
        return " ".join(part for part in parts if part)

    def _build_canonical_key(
        self,
        *,
        category: str,
        product_line: str | None,
        family: str | None,
        generation: str | None,
        year: int | None,
        chip: str | None,
        screen_size: str | None,
        storage_gb: int | None,
        ram_gb: int | None,
        connectivity: str | None,
        color: str | None,
        size_label: str | None,
        model_code: str | None,
    ) -> str:
        parts = [
            category.lower(),
            (product_line or family or "").lower(),
            (generation or "").lower(),
            str(year or ""),
            (chip or "").lower(),
            str(screen_size or ""),
            str(storage_gb or ""),
            str(ram_gb or ""),
            (connectivity or "").lower(),
            (color or "").lower(),
            (size_label or "").lower(),
            (model_code or "").lower(),
        ]
        return "|".join(parts)

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9+]+", text.lower())
        return sorted({token for token in tokens if token not in STOPWORDS and len(token) > 1})
