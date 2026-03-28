from __future__ import annotations

from app.config import MatchingConfig
from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.storage.models import RawBestItem, RawSonicItem, RebuildStats


def build_items():
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="iPad",
                row_number=1,
                raw_name="Silver Wi-Fi",
                full_name="iPad 11 (A16) 2025 128GB Silver Wi-Fi",
                price=30000,
                country_flag="🇺🇸",
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
                country_flag="🇺🇸",
            ),
            RawSonicItem(
                batch_message_ids=[10],
                line_number=2,
                raw_name="Magic Keyboard Air 11 Black (MGYX4)",
                full_name="Magic Keyboard (iPad Air) Magic Keyboard Air 11 Black (MGYX4)",
                price=25500,
                country_flag="🇺🇸",
                model_code="MGYX4",
            ),
        ]
    )
    return best, sonic


def test_matching_finds_existing_best_item() -> None:
    best, sonic = build_items()
    matcher = MatchingEngine(MatchingConfig())

    result = matcher.match(sonic[0], best)

    assert result.matched is True
    assert result.strategy in {"strict_attributes", "exact_canonical_key", "weighted_similarity"}
    assert result.score >= 0.74


def test_merge_overrides_best_and_appends_new_items() -> None:
    best, sonic = build_items()
    matcher = MatchingEngine(MatchingConfig())
    stats = RebuildStats(trigger="test")

    merged = matcher.merge(best, sonic, stats)

    assert len(merged.items) == 2
    ipad = next(item for item in merged.items if item.category == "iPad")
    accessory = next(item for item in merged.items if item.category == "Accessory")
    assert ipad.price == 27900
    assert ipad.price_source == "SONIC"
    assert accessory.price_source == "SONIC"
    assert merged.stats.overridden_by_sonic == 1
    assert merged.stats.appended_new_from_sonic == 1
