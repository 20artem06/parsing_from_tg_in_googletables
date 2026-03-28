from __future__ import annotations

from collections.abc import Iterable

from app.config import MatchingConfig
from app.storage.models import MatchResult, MergedItem, MergeResult, NormalizedItem, RebuildStats


class MatchingEngine:
    def __init__(self, config: MatchingConfig) -> None:
        self.config = config

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
                merged_index[match.best_key] = MergedItem(
                    category=base_item.category,
                    product_line=base_item.product_line or sonic_item.product_line,
                    family=base_item.family or sonic_item.family,
                    canonical_name=base_item.canonical_name,
                    canonical_key=base_item.canonical_key,
                    price=sonic_item.price if sonic_item.price is not None else base_item.price,
                    currency=sonic_item.currency or base_item.currency,
                    price_source="SONIC",
                    source_priority=2,
                    best_price=base_item.price,
                    sonic_price=sonic_item.price,
                    country_flag=sonic_item.country_flag or base_item.country_flag,
                    best_country_flag=base_item.country_flag,
                    sonic_country_flag=sonic_item.country_flag,
                    model_code=base_item.model_code or sonic_item.model_code,
                    color=base_item.color or sonic_item.color,
                    storage_gb=base_item.storage_gb or sonic_item.storage_gb,
                    ram_gb=base_item.ram_gb or sonic_item.ram_gb,
                    connectivity=base_item.connectivity or sonic_item.connectivity,
                    year=base_item.year or sonic_item.year,
                    chip=base_item.chip or sonic_item.chip,
                    screen_size=base_item.screen_size or sonic_item.screen_size,
                    size_label=base_item.size_label or sonic_item.size_label,
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

    def _passes_hard_constraints(self, left: NormalizedItem, right: NormalizedItem) -> bool:
        if left.category != right.category:
            return False
        if left.model_code and right.model_code and left.model_code != right.model_code:
            return False
        if left.storage_gb and right.storage_gb and left.storage_gb != right.storage_gb:
            return False
        if left.family and right.family and left.family != right.family:
            return False
        if left.product_line and right.product_line and left.product_line != right.product_line:
            return False
        if left.screen_size and right.screen_size and left.screen_size != right.screen_size:
            return False
        return True

    def _strict_score(self, left: NormalizedItem, right: NormalizedItem) -> float:
        score = 0.0
        if left.model_code and right.model_code and left.model_code == right.model_code:
            score += 0.5
        score += self._shared_field_score(left.product_line, right.product_line, 0.2)
        score += self._shared_field_score(left.family, right.family, 0.15)
        score += self._shared_field_score(left.storage_gb, right.storage_gb, 0.1)
        score += self._shared_field_score(left.connectivity, right.connectivity, 0.1)
        score += self._shared_field_score(left.color, right.color, 0.08)
        score += self._shared_field_score(left.year, right.year, 0.07)
        score += self._shared_field_score(left.chip, right.chip, 0.07)
        return score

    def _weighted_score(self, left: NormalizedItem, right: NormalizedItem) -> float:
        score = 0.0
        score += self._shared_field_score(left.product_line, right.product_line, 0.2)
        score += self._shared_field_score(left.family, right.family, 0.15)
        score += self._shared_field_score(left.storage_gb, right.storage_gb, 0.1)
        score += self._shared_field_score(left.connectivity, right.connectivity, 0.1)
        score += self._shared_field_score(left.color, right.color, 0.08)
        score += self._shared_field_score(left.year, right.year, 0.05)
        score += self._shared_field_score(left.chip, right.chip, 0.05)
        score += self._shared_field_score(left.screen_size, right.screen_size, 0.05)
        score += self._token_similarity(left.tokens, right.tokens) * 0.22
        return score

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
