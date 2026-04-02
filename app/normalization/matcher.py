from __future__ import annotations

from collections.abc import Iterable
import re

from app.config import MatchingConfig
from app.normalization.normalizer import ItemNormalizer
from app.storage.models import (
    MatchResult,
    MergedItem,
    MergeResult,
    NormalizedItem,
    RebuildStats,
    SnapshotFreshness,
)


class MatchingEngine:
    def __init__(self, config: MatchingConfig) -> None:
        self.config = config
        self._identity_normalizer = ItemNormalizer()

    def match(self, sonic_item: NormalizedItem, best_items: Iterable[NormalizedItem]) -> MatchResult:
        best_list = list(best_items)

        for candidate in best_list:
            if sonic_item.canonical_key == candidate.canonical_key:
                return MatchResult(
                    matched=True,
                    score=1.0,
                    strategy="exact_canonical_key",
                    best_key=candidate.canonical_key,
                )

        strict_candidates: list[tuple[float, NormalizedItem]] = []
        for candidate in best_list:
            if not self._passes_hard_constraints(sonic_item, candidate):
                continue
            score = self._strict_score(sonic_item, candidate)
            if score >= self.config.strong_match_threshold:
                strict_candidates.append((score, candidate))

        if strict_candidates:
            strict_candidates.sort(key=lambda pair: (-pair[0], pair[1].canonical_key))
            best_score, best_candidate = strict_candidates[0]
            return MatchResult(
                matched=True,
                score=best_score,
                strategy="strict_attributes",
                best_key=best_candidate.canonical_key,
            )

        fuzzy_candidates: list[tuple[float, NormalizedItem]] = []
        for candidate in best_list:
            if not self._passes_hard_constraints(sonic_item, candidate):
                continue
            score = self._weighted_score(sonic_item, candidate)
            if score >= self.config.similarity_threshold:
                fuzzy_candidates.append((score, candidate))

        if fuzzy_candidates:
            fuzzy_candidates.sort(key=lambda pair: (-pair[0], pair[1].canonical_key))
            best_score, best_candidate = fuzzy_candidates[0]
            return MatchResult(
                matched=True,
                score=best_score,
                strategy="weighted_similarity",
                best_key=best_candidate.canonical_key,
            )

        return MatchResult(matched=False, score=0.0, strategy="new", best_key=None)

    def merge(
        self,
        best_items: list[NormalizedItem],
        sonic_items: list[NormalizedItem],
        stats: RebuildStats,
    ) -> MergeResult:
        merged_index: dict[str, MergedItem] = {}
        best_index: dict[str, NormalizedItem] = {item.canonical_key: item for item in best_items}

        for item in best_items:
            merged_index[item.canonical_key] = MergedItem(
                category=item.category,
                product_line=item.product_line,
                family=item.family,
                canonical_name=item.canonical_name,
                canonical_key=item.canonical_key,
                price=item.price,
                currency=item.currency,
                price_source="BEST",
                source_priority=1,
                best_price=item.price,
                sonic_price=None,
                country_flag=item.country_flag,
                best_country_flag=item.country_flag,
                sonic_country_flag=None,
                model_code=item.model_code,
                color=item.color,
                storage_gb=item.storage_gb,
                ram_gb=item.ram_gb,
                connectivity=item.connectivity,
                year=item.year,
                chip=item.chip,
                screen_size=item.screen_size,
                size_label=item.size_label,
                raw_best_name=item.full_name,
                raw_sonic_name=None,
                parsed_from_best=True,
                parsed_from_sonic=False,
                match_score=None,
            )

        for sonic_item in sonic_items:
            match = self.match(sonic_item, best_items)
            if match.matched and match.best_key:
                base_item = best_index[match.best_key]
                if not self._sonic_should_override_best(sonic_item, base_item):
                    stats.best_overrode_stale_sonic += 1
                    continue
                merged_product_line = self._prefer_richer_text(
                    base_item.product_line,
                    sonic_item.product_line,
                )
                merged_family = self._prefer_richer_text(base_item.family, sonic_item.family)
                merged_generation = self._prefer_richer_text(
                    base_item.generation,
                    sonic_item.generation,
                )
                merged_year = base_item.year or sonic_item.year
                merged_chip = self._prefer_richer_text(base_item.chip, sonic_item.chip)
                merged_screen_size = self._prefer_richer_text(
                    base_item.screen_size,
                    sonic_item.screen_size,
                )
                merged_storage_gb = base_item.storage_gb or sonic_item.storage_gb
                merged_ram_gb = base_item.ram_gb or sonic_item.ram_gb
                merged_connectivity = self._prefer_richer_text(
                    base_item.connectivity,
                    sonic_item.connectivity,
                )
                merged_color = self._prefer_richer_text(base_item.color, sonic_item.color)
                merged_size_label = self._prefer_richer_text(
                    base_item.size_label,
                    sonic_item.size_label,
                )
                merged_model_code = self._prefer_richer_text(
                    base_item.model_code,
                    sonic_item.model_code,
                )
                merged_canonical_name, merged_canonical_key = (
                    self._identity_normalizer.build_identity(
                        category=base_item.category,
                        product_line=merged_product_line,
                        family=merged_family,
                        generation=merged_generation,
                        year=merged_year,
                        chip=merged_chip,
                        screen_size=merged_screen_size,
                        storage_gb=merged_storage_gb,
                        ram_gb=merged_ram_gb,
                        connectivity=merged_connectivity,
                        color=merged_color,
                        size_label=merged_size_label,
                        model_code=merged_model_code,
                    )
                )
                merged_index[match.best_key] = MergedItem(
                    category=base_item.category,
                    product_line=merged_product_line,
                    family=merged_family,
                    canonical_name=merged_canonical_name,
                    canonical_key=merged_canonical_key,
                    price=sonic_item.price if sonic_item.price is not None else base_item.price,
                    currency=sonic_item.currency or base_item.currency,
                    price_source="SONIC",
                    source_priority=2,
                    best_price=base_item.price,
                    sonic_price=sonic_item.price,
                    country_flag=sonic_item.country_flag or base_item.country_flag,
                    best_country_flag=base_item.country_flag,
                    sonic_country_flag=sonic_item.country_flag,
                    model_code=merged_model_code,
                    color=merged_color,
                    storage_gb=merged_storage_gb,
                    ram_gb=merged_ram_gb,
                    connectivity=merged_connectivity,
                    year=merged_year,
                    chip=merged_chip,
                    screen_size=merged_screen_size,
                    size_label=merged_size_label,
                    raw_best_name=base_item.full_name,
                    raw_sonic_name=sonic_item.full_name,
                    parsed_from_best=True,
                    parsed_from_sonic=True,
                    match_score=round(match.score, 4),
                )
                stats.overridden_by_sonic += 1
                continue

            merged_index[sonic_item.canonical_key] = MergedItem(
                category=sonic_item.category,
                product_line=sonic_item.product_line,
                family=sonic_item.family,
                canonical_name=sonic_item.canonical_name,
                canonical_key=sonic_item.canonical_key,
                price=sonic_item.price,
                currency=sonic_item.currency,
                price_source="SONIC",
                source_priority=2,
                best_price=None,
                sonic_price=sonic_item.price,
                country_flag=sonic_item.country_flag,
                best_country_flag=None,
                sonic_country_flag=sonic_item.country_flag,
                model_code=sonic_item.model_code,
                color=sonic_item.color,
                storage_gb=sonic_item.storage_gb,
                ram_gb=sonic_item.ram_gb,
                connectivity=sonic_item.connectivity,
                year=sonic_item.year,
                chip=sonic_item.chip,
                screen_size=sonic_item.screen_size,
                size_label=sonic_item.size_label,
                raw_best_name=None,
                raw_sonic_name=sonic_item.full_name,
                parsed_from_best=False,
                parsed_from_sonic=True,
                match_score=0.0,
            )
            stats.appended_new_from_sonic += 1

        items = sorted(
            merged_index.values(),
            key=lambda item: (
                item.category,
                item.canonical_name,
                item.model_code or "",
            ),
        )
        stats.merged_count = len(items)
        return MergeResult(items=items, stats=stats)

    def _sonic_should_override_best(
        self,
        sonic_item: NormalizedItem,
        best_item: NormalizedItem,
    ) -> bool:
        return not (
            sonic_item.snapshot_freshness == SnapshotFreshness.STALE
            and best_item.snapshot_freshness == SnapshotFreshness.FRESH
        )

    def _passes_hard_constraints(self, left: NormalizedItem, right: NormalizedItem) -> bool:
        if left.category != right.category:
            return False
        if self._hard_conflict(left.family, right.family):
            return False
        if self._hard_conflict(left.product_line, right.product_line):
            return False
        if self._hard_conflict(self._effective_storage_gb(left), self._effective_storage_gb(right)):
            return False
        if self._hard_conflict(self._effective_ram_gb(left), self._effective_ram_gb(right)):
            return False
        if self._hard_conflict(left.connectivity, right.connectivity):
            return False
        if self._hard_conflict(left.color, right.color):
            return False
        if self._hard_conflict(left.generation, right.generation):
            return False
        if self._hard_conflict(left.year, right.year):
            return False
        if self._hard_conflict(left.chip, right.chip):
            return False
        if self._hard_conflict(self._effective_screen_size(left), self._effective_screen_size(right)):
            return False
        if self._hard_conflict(
            self._primary_size_token(left.size_label),
            self._primary_size_token(right.size_label),
        ):
            return False
        if self._hard_conflict(
            self._fit_size_token(left.size_label),
            self._fit_size_token(right.size_label),
        ):
            return False
        if self._hard_conflict(
            self._variant_type_token(left.size_label),
            self._variant_type_token(right.size_label),
        ):
            return False
        if self._hard_conflict(
            self._variant_detail_token(left.size_label),
            self._variant_detail_token(right.size_label),
        ):
            return False
        return True

    def _strict_score(self, left: NormalizedItem, right: NormalizedItem) -> float:
        score = 0.0
        if left.model_code and right.model_code and left.model_code == right.model_code:
            score += 0.5
        score += self._shared_field_score(left.product_line, right.product_line, 0.2)
        score += self._shared_field_score(left.family, right.family, 0.15)
        score += self._shared_field_score(left.generation, right.generation, 0.12)
        score += self._shared_field_score(
            self._effective_storage_gb(left),
            self._effective_storage_gb(right),
            0.1,
        )
        score += self._shared_field_score(left.connectivity, right.connectivity, 0.1)
        score += self._shared_field_score(left.color, right.color, 0.08)
        score += self._size_label_score(left.size_label, right.size_label, 0.1)
        score += self._shared_field_score(left.year, right.year, 0.06)
        score += self._shared_field_score(left.chip, right.chip, 0.06)
        return max(score - self._model_code_penalty(left, right), 0.0)

    def _weighted_score(self, left: NormalizedItem, right: NormalizedItem) -> float:
        score = 0.0
        score += self._shared_field_score(left.product_line, right.product_line, 0.2)
        score += self._shared_field_score(left.family, right.family, 0.15)
        score += self._shared_field_score(left.generation, right.generation, 0.08)
        score += self._shared_field_score(
            self._effective_storage_gb(left),
            self._effective_storage_gb(right),
            0.1,
        )
        score += self._shared_field_score(left.connectivity, right.connectivity, 0.1)
        score += self._shared_field_score(left.color, right.color, 0.08)
        score += self._size_label_score(left.size_label, right.size_label, 0.08)
        score += self._shared_field_score(left.year, right.year, 0.05)
        score += self._shared_field_score(left.chip, right.chip, 0.05)
        score += self._shared_field_score(
            self._effective_screen_size(left),
            self._effective_screen_size(right),
            0.05,
        )
        score += self._token_similarity(left.tokens, right.tokens) * 0.22
        return max(score - self._model_code_penalty(left, right), 0.0)

    def _hard_conflict(self, left: object, right: object) -> bool:
        return left is not None and right is not None and left != right

    def _model_code_penalty(self, left: NormalizedItem, right: NormalizedItem) -> float:
        if left.model_code and right.model_code and left.model_code != right.model_code:
            return 0.35
        return 0.0

    def _shared_field_score(self, left: object, right: object, weight: float) -> float:
        if left and right and left == right:
            return weight
        if left is None or right is None:
            return weight * 0.4
        return 0.0

    def _token_similarity(self, left: list[str], right: list[str]) -> float:
        left_set = set(left)
        right_set = set(right)
        if not left_set or not right_set:
            return 0.0
        intersection = len(left_set & right_set)
        union = len(left_set | right_set)
        return intersection / union

    def _size_label_score(self, left: str | None, right: str | None, weight: float) -> float:
        if left and right and left == right:
            return weight

        score = 0.0
        left_primary = self._primary_size_token(left)
        right_primary = self._primary_size_token(right)
        if left_primary and right_primary and left_primary == right_primary:
            score += weight * 0.45
        elif not left_primary or not right_primary:
            score += weight * 0.08

        left_fit = self._fit_size_token(left)
        right_fit = self._fit_size_token(right)
        if left_fit and right_fit and left_fit == right_fit:
            score += weight * 0.35
        elif not left_fit or not right_fit:
            score += weight * 0.05

        left_variant = self._variant_type_token(left)
        right_variant = self._variant_type_token(right)
        if left_variant and right_variant and left_variant == right_variant:
            score += weight * 0.2
        elif not left_variant or not right_variant:
            score += weight * 0.03

        left_detail = self._variant_detail_token(left)
        right_detail = self._variant_detail_token(right)
        if left_detail and right_detail and left_detail == right_detail:
            score += weight * 0.12
        elif not left_detail or not right_detail:
            score += weight * 0.03

        return min(score, weight)

    def _prefer_richer_text(self, left: str | None, right: str | None) -> str | None:
        if not left:
            return right
        if not right:
            return left

        left_clean = left.strip()
        right_clean = right.strip()
        if left_clean.lower() == right_clean.lower():
            return left

        left_tokens = set(left_clean.lower().split())
        right_tokens = set(right_clean.lower().split())

        if left_tokens and right_tokens:
            if left_tokens < right_tokens:
                return right
            if right_tokens < left_tokens:
                return left

        if left_clean.lower() in right_clean.lower() and len(right_clean) > len(left_clean):
            return right
        if right_clean.lower() in left_clean.lower() and len(left_clean) > len(right_clean):
            return left

        return left if len(left_clean) >= len(right_clean) else right

    def _primary_size_token(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"\b\d{2}(?:mm|in)\b", value.lower())
        return match.group(0) if match else None

    def _fit_size_token(self, value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"\b(s/m|m/l|small|medium|large)\b", value.lower())
        return match.group(1) if match else None

    def _variant_type_token(self, value: str | None) -> str | None:
        if not value:
            return None
        lowered = value.lower()
        for term in (
            "sport band",
            "sport loop",
            "milanese loop",
            "ocean band",
            "alpine loop",
            "trail loop",
        ):
            if term in lowered:
                return term
        return None

    def _variant_detail_token(self, value: str | None) -> str | None:
        if not value:
            return None

        lowered = value.lower()
        primary = self._primary_size_token(lowered)
        fit = self._fit_size_token(lowered)
        variant = self._variant_type_token(lowered)

        if primary:
            lowered = re.sub(rf"\b{re.escape(primary)}\b", " ", lowered)
        if fit:
            lowered = re.sub(rf"\b{re.escape(fit)}\b", " ", lowered)
        if variant:
            lowered = lowered.replace(variant, " ")

        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered or None

    def _effective_storage_gb(self, item: NormalizedItem) -> int | None:
        if item.storage_gb is not None:
            return item.storage_gb

        text = f"{item.raw_name} {item.full_name}".lower()
        if match := re.search(r"\b(1|2)\s*tb\b", text):
            return int(match.group(1)) * 1024
        if match := re.search(r"\b(64|128|256|512|1024|2048)\s*gb\b", text):
            return int(match.group(1))
        if match := re.search(r"\b(64|128|256|512)\b", text):
            return int(match.group(1))
        return None

    def _effective_screen_size(self, item: NormalizedItem) -> str | None:
        if item.screen_size:
            return item.screen_size

        text = f"{item.raw_name} {item.full_name}".lower()
        if item.category == "iPad":
            if match := re.search(r"\bipad(?:\s+(?:pro|air|mini))?\s+(11|13)\b", text):
                return match.group(1)
        if item.category == "MacBook":
            if match := re.search(r"\b(?:macbook(?:\s+(?:air|pro))?|air|pro)\s+(13|14|15|16)\b", text):
                return match.group(1)
        if item.category == "iMac":
            if match := re.search(r"\bimac\s+(24|27)\b", text):
                return match.group(1)
        return None

    def _effective_ram_gb(self, item: NormalizedItem) -> int | None:
        if item.ram_gb is not None:
            return item.ram_gb

        text = f"{item.raw_name} {item.full_name}".lower()
        if match := re.search(r"\b(\d{1,2})\s*/\s*(?:64|128|256|512|1024|2048)\s*(?:tb|gb)?\b", text):
            return int(match.group(1))
        if match := re.search(r"\b(\d{1,2})\s*gb\s*ram\b", text):
            return int(match.group(1))
        return None
