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
    AIRPODS_MAX_RE,
    AIRPODS_PRO_RE,
    AIRPODS_STD_RE,
    CHIP_RE,
    IMAC_RE,
    IPAD_RE,
    IPHONE_RE,
    MACBOOK_RE,
    MM_SIZE_RE,
    RAM_RE,
    SCREEN_RE,
    SPEC_PAIR_RE,
    STORAGE_RE,
    WATCH_SE_RE,
    WATCH_SERIES_RE,
    WATCH_ULTRA_RE,
    YEAR_RE,
)
from app.storage.models import NormalizedItem, RawBestItem, RawSonicItem, SourceKind
from app.utils.parsing import clean_text, extract_flag, extract_model_code

WATCH_BAND_TERMS = (
    "sport loop",
    "sport band",
    "milanese loop",
    "ocean band",
    "alpine loop",
    "trail loop",
)
SERIES_11_MILANESE_COLORS = {"gold", "natural titanium", "slate"}
SERIES_11_SPORT_BAND_COLORS = {"rose gold", "silver", "space gray", "black"}


class ItemNormalizer:
    def __init__(self, currency: str = "RUB") -> None:
        self.currency = currency

    def normalize_best(self, items: Iterable[RawBestItem]) -> list[NormalizedItem]:
        return [self._normalize_best_item(item) for item in items]

    def normalize_sonic(self, items: Iterable[RawSonicItem]) -> list[NormalizedItem]:
        return [self._normalize_sonic_item(item) for item in items]

    def build_identity(
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
    ) -> tuple[str, str]:
        return (
            self._build_canonical_name(
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
            ),
            self._build_canonical_key(
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
            ),
        )

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
            source_part_key=item.part_key,
            source_block_key=None,
            source_section_key=item.part_key,
            snapshot_freshness=item.snapshot_freshness,
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
            source_part_key=item.part_key,
            source_block_key=item.block_key,
            source_section_key=item.section_key,
            snapshot_freshness=item.snapshot_freshness,
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
        source_part_key: str | None,
        source_block_key: str | None,
        source_section_key: str | None,
        snapshot_freshness,
    ) -> NormalizedItem:
        base_text = clean_text(full_name)
        raw_prepared = base_text.lower().replace("ё", "е").replace("гб", "gb").replace("тб", "tb")
        prepared = self._prepare_text(base_text)
        country_flag = country_flag or extract_flag(base_text)
        category = forced_category or self._detect_category(prepared, source_section)
        if self._contains_term(prepared, "mac mini"):
            category = "Mac"
        color = self._extract_alias(prepared, COLOR_ALIASES)
        connectivity = self._extract_connectivity(prepared)
        storage_gb = self._extract_storage_gb(raw_prepared, prepared)
        ram_gb = self._extract_ram_gb(raw_prepared, prepared)
        year = self._extract_year(prepared)
        chip = self._extract_chip(prepared)
        family, product_line, generation, screen_size, size_label = self._extract_family_bundle(
            prepared,
            category,
        )
        if storage_gb is None:
            storage_gb = self._extract_bare_storage_gb(prepared, category)
        if category == "Apple Watch":
            color = self._extract_watch_case_color(prepared) or color
            size_label = self._apply_watch_default_band_rule(
                prepared=prepared,
                raw_text=f"{raw_name} {full_name}",
                generation=generation,
                color=color,
                size_label=size_label,
            )
        generation, year, model_code = self._dedupe_identity_parts(
            product_line=product_line,
            generation=generation,
            year=year,
            model_code=model_code,
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
            source_part_key=source_part_key,
            source_block_key=source_block_key,
            source_section_key=source_section_key,
            snapshot_freshness=snapshot_freshness,
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
                if self._contains_term(prepared, alias):
                    return canonical
        return None

    def _extract_connectivity(self, prepared: str) -> str | None:
        if self._contains_term(prepared, "gps+cellular") or self._contains_term(
            prepared,
            "gps cellular",
        ):
            return "gps+cellular"
        if self._contains_term(prepared, "gps") and self._contains_term(prepared, "cellular"):
            return "gps+cellular"
        for canonical, aliases in CONNECTIVITY_ALIASES.items():
            for alias in aliases:
                if self._contains_term(prepared, alias):
                    return canonical
        return None

    def _extract_storage_gb(self, raw_prepared: str, prepared: str) -> int | None:
        pair_match = SPEC_PAIR_RE.search(raw_prepared)
        if pair_match:
            size = int(pair_match.group(2))
            unit = pair_match.group(3).lower()
            return size * 1024 if unit == "tb" else size

        match = STORAGE_RE.search(prepared)
        if not match:
            return None
        size = int(match.group(1))
        unit = match.group(2).lower()
        return size * 1024 if unit == "tb" else size

    def _extract_ram_gb(self, raw_prepared: str, prepared: str) -> int | None:
        pair_match = SPEC_PAIR_RE.search(raw_prepared)
        if pair_match:
            return int(pair_match.group(1))

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
        if category == "iPhone":
            match = IPHONE_RE.search(prepared)
            if match:
                base = match.group(1).lower()
                family = f"iphone {base}"
                suffix = match.group(2)
                product_line = f"{family} {suffix}".strip() if suffix else family
                return family, product_line, None, None, None
            return "iphone", "iphone", None, None, None

        if category == "iPad":
            match = self._select_ipad_match(prepared)
            if match:
                variant = match.group(1)
                number = match.group(2)
                if variant in {"air", "pro", "mini"}:
                    family = f"ipad {variant}"
                    product_line = family
                    screen_size = number if number else None
                elif number:
                    family = f"ipad {number}"
                    product_line = family
                    screen_size = None
                else:
                    family = "ipad"
                    product_line = "ipad"
                    screen_size = None
                return family, product_line, None, screen_size, None
            return "ipad", "ipad", None, None, None

        if category == "MacBook":
            match = self._select_macbook_match(prepared)
            if match:
                variant = match.group(1) or ""
                family = f"macbook {variant}".strip()
                product_line = family
                screen_size = match.group(2) if match.group(2) else None
                return family, product_line, None, screen_size, None
            return "macbook", "macbook", None, None, None

        if category == "Mac":
            if self._contains_term(prepared, "mac mini"):
                return "mac mini", "mac mini", None, None, None
            return "mac", "mac", None, None, None

        if category == "iMac":
            match = IMAC_RE.search(prepared)
            if match:
                family = "imac"
                product_line = "imac"
                screen_size = match.group(1) if match.group(1) else None
                return family, product_line, None, screen_size, None
            return "imac", "imac", None, None, None

        if category == "Apple Watch":
            return self._extract_watch_bundle(prepared)

        if category == "AirPods":
            return self._extract_airpods_bundle(prepared)

        for keyword, family_name in ACCESSORY_KEYWORDS.items():
            if keyword in prepared:
                screen_match = SCREEN_RE.search(prepared)
                mm_match = MM_SIZE_RE.search(prepared)
                base_size = (
                    screen_match.group(1)
                    if screen_match
                    else (f"{mm_match.group(1)}mm" if mm_match else None)
                )
                accessory_variant = self._extract_accessory_variant(prepared, keyword)
                size_label = " ".join(
                    part for part in (base_size, accessory_variant) if part
                ) or None
                return family_name.lower(), family_name, None, None, size_label

        return "accessory", "accessory", None, None, None

    def _select_ipad_match(self, prepared: str):
        matches = list(IPAD_RE.finditer(prepared))
        if not matches:
            return None

        def rank(match) -> tuple[int, int]:
            variant = match.group(1)
            number = match.group(2)
            return (
                1 if variant in {"pro", "air", "mini"} else 0,
                1 if number else 0,
            )

        return max(matches, key=rank)

    def _select_macbook_match(self, prepared: str):
        matches = list(MACBOOK_RE.finditer(prepared))
        if not matches:
            return None

        def rank(match) -> tuple[int, int]:
            variant = match.group(1)
            number = match.group(2)
            return (
                1 if variant in {"air", "pro", "neo"} else 0,
                1 if number else 0,
            )

        return max(matches, key=rank)

    def _extract_watch_bundle(
        self,
        prepared: str,
    ) -> tuple[str, str, str | None, None, str | None]:
        watch_size = self._extract_watch_size(prepared)
        watch_variant = self._extract_watch_variant(prepared)
        size_label = " ".join(part for part in (watch_size, watch_variant) if part) or None

        if match := WATCH_ULTRA_RE.search(prepared):
            generation = match.group(1).strip() or None
            return "apple watch", "apple watch ultra", generation, None, size_label

        if match := WATCH_SE_RE.search(prepared):
            generation = match.group(1).strip() or None
            return "apple watch", "apple watch se", generation, None, size_label

        if match := WATCH_SERIES_RE.search(prepared):
            generation = match.group(1).strip() or None
            return "apple watch", "apple watch series", generation, None, size_label

        return "apple watch", "apple watch", None, None, size_label

    def _extract_airpods_bundle(
        self,
        prepared: str,
    ) -> tuple[str, str, str | None, None, None]:
        if match := AIRPODS_MAX_RE.search(prepared):
            generation = match.group(1).strip() if match.group(1) else None
            return "airpods", "airpods max", generation, None, None

        if match := AIRPODS_PRO_RE.search(prepared):
            generation = match.group(1).strip() if match.group(1) else None
            generation = self._append_airpods_qualifier(prepared, generation)
            return "airpods", "airpods pro", generation, None, None

        if match := AIRPODS_STD_RE.search(prepared):
            generation = match.group(1).strip() if match.group(1) else None
            generation = self._append_airpods_qualifier(prepared, generation)
            return "airpods", "airpods", generation, None, None

        return "airpods", "airpods", None, None, None

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

    def _contains_term(self, prepared: str, term: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", prepared) is not None

    def _append_airpods_qualifier(self, prepared: str, generation: str | None) -> str | None:
        for qualifier in ("anc", "type-c", "usb-c", "lightning"):
            if self._contains_term(prepared, qualifier):
                return " ".join(part for part in (generation, qualifier) if part)
        return generation

    def _extract_watch_size(self, prepared: str) -> str | None:
        match = MM_SIZE_RE.search(prepared)
        if match:
            return f"{match.group(1)}mm"

        bare_size_match = re.search(r"\b(40|41|42|44|45|46|49)\b", prepared)
        if bare_size_match:
            return f"{bare_size_match.group(1)}mm"

        return None

    def _extract_watch_variant(self, prepared: str) -> str | None:
        prepared = re.sub(r"(?<!\w)sb(?!\w)", "sport band", prepared)
        parts: list[str] = []
        fit_token: str | None = None
        for term in WATCH_BAND_TERMS:
            if self._contains_term(prepared, term):
                parts.append(self._decorate_watch_band_term(prepared, term))
                break

        for term in ("s/m", "m/l", "small", "medium", "large"):
            if self._contains_term(prepared, term):
                fit_token = term
                break
        else:
            if self._contains_term(prepared, "s m"):
                fit_token = "s/m"
            elif self._contains_term(prepared, "m l"):
                fit_token = "m/l"

        if fit_token:
            parts.append(fit_token)

        return " ".join(parts) if parts else None

    def _apply_watch_default_band_rule(
        self,
        *,
        prepared: str,
        raw_text: str,
        generation: str | None,
        color: str | None,
        size_label: str | None,
    ) -> str | None:
        size = self._extract_watch_size(prepared)
        fit = self._extract_watch_fit_token(prepared)
        label = size_label or ""

        if self._has_explicit_watch_band_type(raw_text):
            return size_label
        if any(term in label for term in WATCH_BAND_TERMS):
            return size_label

        inferred_band = self._infer_watch_band_type(generation=generation, color=color)
        if not inferred_band and not size and not fit:
            return size_label

        parts = [size, inferred_band, fit]
        return " ".join(part for part in parts if part) or size_label

    def _has_explicit_watch_band_type(self, raw_text: str) -> bool:
        prepared = self._prepare_text(clean_text(raw_text))
        if self._contains_term(prepared, "sb"):
            return True
        return any(self._contains_term(prepared, term) for term in WATCH_BAND_TERMS)

    def _infer_watch_band_type(
        self,
        *,
        generation: str | None,
        color: str | None,
    ) -> str | None:
        normalized_color = clean_text(color or "").lower()
        if generation == "11":
            if normalized_color in SERIES_11_MILANESE_COLORS:
                return "milanese loop"
            if normalized_color in SERIES_11_SPORT_BAND_COLORS:
                return "sport band"
        return "sport band" if generation else None

    def _extract_watch_fit_token(self, prepared: str) -> str | None:
        for term in ("s/m", "m/l", "small", "medium", "large"):
            if self._contains_term(prepared, term):
                return term
        if self._contains_term(prepared, "s m"):
            return "s/m"
        if self._contains_term(prepared, "m l"):
            return "m/l"
        return None

    def _extract_watch_case_color(self, prepared: str) -> str | None:
        descriptor = self._extract_watch_descriptor(prepared)
        return self._extract_first_alias_by_position(descriptor or prepared, COLOR_ALIASES)

    def _extract_watch_descriptor(self, prepared: str) -> str:
        prepared = re.sub(r"(?<!\w)sb(?!\w)", "sport band", prepared)
        matches = list(
            re.finditer(
                r"\b(?:se\d{0,2}|s\d{1,2}|ultra\s*\d{0,2})\b(?:\s+20\d{2})?(?:\s+(?:40|41|42|44|45|46|49)(?:mm)?)?",
                prepared,
            )
        )
        if not matches:
            return prepared
        return prepared[matches[-1].end() :].strip()

    def _extract_first_alias_by_position(
        self,
        prepared: str,
        aliases: dict[str, list[str]],
    ) -> str | None:
        best_match: tuple[int, int, str] | None = None
        for canonical, values in aliases.items():
            for alias in values:
                match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", prepared)
                if not match:
                    continue
                candidate = (match.start(), -len(alias), canonical)
                if best_match is None or candidate < best_match:
                    best_match = candidate
        return best_match[2] if best_match else None

    def _decorate_watch_band_term(self, prepared: str, term: str) -> str:
        base = self._prepend_variant_color(prepared, term)
        trailing_color = self._extract_watch_trailing_band_color(prepared, term)
        if trailing_color and trailing_color not in base:
            return f"{base} {trailing_color}".strip()
        return base

    def _extract_watch_trailing_band_color(self, prepared: str, term: str) -> str | None:
        tokens = prepared.split()
        term_tokens = term.split()
        stop_tokens = {"s", "m", "l", "small", "medium", "large"}

        for index in range(len(tokens) - len(term_tokens) + 1):
            if tokens[index : index + len(term_tokens)] != term_tokens:
                continue

            trailing: list[str] = []
            pointer = index + len(term_tokens)
            while pointer < len(tokens) and len(trailing) < 2:
                token = tokens[pointer]
                if token in stop_tokens or token.isdigit() or token.endswith("mm"):
                    break
                trailing.append(token)
                pointer += 1

            if not trailing:
                return None

            phrase = " ".join(trailing)
            canonical = self._extract_first_alias_by_position(phrase, COLOR_ALIASES)
            if canonical:
                return canonical
            return phrase

        return None

    def _extract_accessory_variant(self, prepared: str, keyword: str) -> str | None:
        residual = prepared
        residual = re.sub(rf"(?<!\w){re.escape(keyword)}(?!\w)", " ", residual, count=1)
        residual = STORAGE_RE.sub(" ", residual)
        residual = YEAR_RE.sub(" ", residual)
        residual = MM_SIZE_RE.sub(" ", residual)
        residual = re.sub(r"\b\d{1,2}(?:\.\d)?\s*(?:inch|in)\b", " ", residual)

        for alias_group in (COLOR_ALIASES, CONNECTIVITY_ALIASES):
            for aliases in alias_group.values():
                for alias in aliases:
                    residual = re.sub(
                        rf"(?<!\w){re.escape(alias)}(?!\w)",
                        " ",
                        residual,
                    )

        residual = re.sub(r"(?<!\w)apple(?!\w)", " ", residual)
        residual = re.sub(r"(?<!\w)with(?!\w)", " ", residual)
        residual = re.sub(r"\s+", " ", residual).strip()
        if not residual:
            return None

        tokens = []
        seen: set[str] = set()
        for token in residual.split():
            if self._is_noise_accessory_token(keyword, token):
                continue
            if token in {"band", "loop"} and tokens:
                phrase = f"{tokens[-1]} {token}"
                if phrase in {
                    "sport band",
                    "sport loop",
                    "milanese loop",
                    "ocean band",
                    "alpine loop",
                    "trail loop",
                }:
                    tokens[-1] = phrase
                    continue
            if token not in seen:
                tokens.append(token)
                seen.add(token)

        return " ".join(tokens) if tokens else None

    def _is_noise_accessory_token(self, keyword: str, token: str) -> bool:
        if token != "3":
            return False
        return keyword in {"magic mouse", "mouse"}

    def _extract_bare_storage_gb(self, prepared: str, category: str) -> int | None:
        if category not in {"iPad", "iPhone", "MacBook", "Mac", "iMac"}:
            return None

        match = re.search(r"\b(64|128|256|512|1024|2048)\b", prepared)
        return int(match.group(1)) if match else None

    def _prepend_variant_color(self, prepared: str, term: str) -> str:
        tokens = prepared.split()
        term_tokens = term.split()
        for index in range(len(tokens) - len(term_tokens) + 1):
            if tokens[index : index + len(term_tokens)] != term_tokens:
                continue

            band_color_prefixes = {
                "blue",
                "olive",
                "tan",
            }

            if index >= 1 and tokens[index - 1] in band_color_prefixes:
                return f"{tokens[index - 1]} {term}"

            return term

        return term

    def _dedupe_identity_parts(
        self,
        *,
        product_line: str | None,
        generation: str | None,
        year: int | None,
        model_code: str | None,
    ) -> tuple[str | None, int | None, str | None]:
        normalized_line = clean_text(product_line).lower() if product_line else ""
        normalized_generation = clean_text(generation).lower() if generation else ""

        if generation and normalized_line and self._contains_term(normalized_line, normalized_generation):
            generation = None
            normalized_generation = ""

        year_text = str(year) if year else ""
        if year and (
            (normalized_line and self._contains_term(normalized_line, year_text))
            or (normalized_generation and self._contains_term(normalized_generation, year_text))
        ):
            year = None
            year_text = ""

        normalized_model_code = clean_text(model_code).lower() if model_code else ""
        if normalized_model_code and (
            (normalized_line and self._contains_term(normalized_line, normalized_model_code))
            or (
                normalized_generation
                and self._contains_term(normalized_generation, normalized_model_code)
            )
            or (year_text and normalized_model_code == year_text)
        ):
            model_code = None

        return generation, year, model_code
