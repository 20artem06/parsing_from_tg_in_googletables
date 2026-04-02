from __future__ import annotations

from app.config import MatchingConfig
from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.storage.models import RawBestItem, RawSonicItem, RebuildStats

US_FLAG = "\U0001F1FA\U0001F1F8"


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


def test_watch_matching_uses_size_and_fit_from_size_label() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="S11 42mm Silver (S/M)",
                full_name="Apple Watch S11 (2025) S11 42mm Silver (S/M)",
                price=27300,
                country_flag="🇺🇸",
            ),
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=2,
                raw_name="S11 46mm Silver (M/L)",
                full_name="Apple Watch S11 (2025) S11 46mm Silver (M/L)",
                price=28800,
                country_flag="🇺🇸",
            ),
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=3,
                raw_name="S11 46mm Natural Milanese Loop (M/L)",
                full_name="Apple Watch S11 (2025) S11 46mm Natural Milanese Loop (M/L)",
                price=68500,
                country_flag="🇺🇸",
            ),
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="S11 42 Silver SB Purple Fog S/M",
                full_name="Apple Watch S11 S11 42 Silver SB Purple Fog S/M",
                price=27500,
                country_flag="🇺🇸",
            ),
            RawSonicItem(
                batch_message_ids=[60],
                line_number=2,
                raw_name="S11 42 Natural Ti Milanese Loop",
                full_name="Apple Watch S11 S11 42 Natural Ti Milanese Loop",
                price=63500,
                country_flag="🇺🇸",
            ),
        ]
    )

    matcher = MatchingEngine(MatchingConfig())

    silver_match = matcher.match(sonic[0], best)
    natural_match = matcher.match(sonic[1], best)

    assert silver_match.matched is True
    assert silver_match.best_key == best[0].canonical_key

    assert natural_match.matched is False


def test_watch_matching_does_not_cross_generation() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="S10 46mm Rose Gold Sport Band (M/L)",
                full_name="Apple Watch S10 (2024) S10 46mm Rose Gold Sport Band (M/L)",
                price=28500,
                country_flag="🇺🇸",
            ),
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=2,
                raw_name="S11 46mm Rose Gold (M/L)",
                full_name="Apple Watch S11 (2025) S11 46mm Rose Gold (M/L)",
                price=28500,
                country_flag="🇺🇸",
            ),
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="S11 46 Rose Gold SB M/L",
                full_name="Apple Watch S11 S11 46 Rose Gold SB M/L",
                price=28200,
                country_flag="🇺🇸",
            ),
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is True
    assert result.best_key == best[1].canonical_key


def test_merge_prefers_richer_sonic_watch_details_over_sparse_best_details() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="S11 42mm Jet Black (S/M)",
                full_name="Apple Watch S11 (2025) S11 42mm Jet Black (S/M)",
                price=26300,
                country_flag="🇺🇸",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="S11 42 Jet Black SB S/M",
                full_name="Apple Watch S11 S11 42 Jet Black SB S/M",
                price=25800,
                country_flag="🇺🇸",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    stats = RebuildStats(trigger="test")
    merged = matcher.merge(best, sonic, stats)

    item = merged.items[0]
    assert item.price_source == "SONIC"
    assert item.size_label == "42mm sport band s/m"
    assert item.canonical_name == "apple watch series 11 2025 black 42mm sport band s/m"


def test_ipad_storage_mismatch_does_not_fuzzy_match() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="iPad",
                row_number=1,
                raw_name="iPad 11 128GB LTE Blue",
                full_name="iPad 11 A16 (2025) iPad 11 128GB LTE Blue",
                price=70300,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="iPad 11 256 Blue LTE",
                full_name="iPad 11 (A16) 2025 iPad 11 256 Blue LTE",
                price=51500,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False


def test_ipad_pro_storage_mismatch_does_not_fuzzy_match() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="iPad",
                row_number=1,
                raw_name="iPad Pro 11 M5 256GB Wi-Fi Space Black",
                full_name="iPad Pro 11 M5 (2025) iPad Pro 11 M5 256GB Wi-Fi Space Black",
                price=75500,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="iPad Pro 11 M5 512 Space Black Wi-Fi",
                full_name="iPad Pro M5 2025 iPad Pro 11 M5 512 Space Black Wi-Fi",
                price=98500,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False


def test_ipad_pro_chip_mismatch_does_not_fuzzy_match_even_when_other_fields_align() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="iPad",
                row_number=1,
                raw_name="iPad Pro 11 M4 512GB Wi-Fi Space Black",
                full_name="iPad Pro 11 M4 512GB Wi-Fi Space Black",
                price=95500,
                country_flag=US_FLAG,
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="iPad Pro 11 M5 512 Space Black Wi-Fi",
                full_name="iPad Pro M5 2025 iPad Pro 11 M5 512 Space Black Wi-Fi",
                price=98500,
                country_flag=US_FLAG,
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False


def test_macbook_ram_mismatch_does_not_fuzzy_match() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="MacBook",
                row_number=1,
                raw_name="Pro 14 M5 2025 16/1TB Space Black MDE14",
                full_name="Pro 14 M5 2025 16/1TB Space Black MDE14",
                price=145400,
                country_flag=US_FLAG,
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="MacBook Pro 14 M5 24/1TB Space Black",
                full_name="MacBook Pro M5 MacBook Pro 14 M5 24/1TB Space Black",
                price=152000,
                country_flag=US_FLAG,
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False


def test_watch_color_mismatch_does_not_fuzzy_match() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="SE3 2025 40mm Midnight (M/L)",
                full_name="Apple Watch SE3 (2025) SE3 2025 40mm Midnight (M/L)",
                price=19600,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="SE3 40 Starlight SB M/L",
                full_name="Apple Watch SE3 SE3 40 Starlight SB M/L",
                price=20200,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False


def test_series_11_color_inferred_band_type_allows_match_when_types_align() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="S11 42mm Silver (S/M)",
                full_name="Apple Watch S11 (2025) S11 42mm Silver (S/M)",
                price=27300,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="S11 42 Silver SB S/M",
                full_name="Apple Watch S11 S11 42 Silver SB S/M",
                price=27500,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is True
    assert result.best_key == best[0].canonical_key


def test_series_11_color_inferred_band_type_blocks_conflicting_match() -> None:
    normalizer = ItemNormalizer()
    best = normalizer.normalize_best(
        [
            RawBestItem(
                sheet_name="Apple Watch",
                row_number=1,
                raw_name="S11 46mm Gold (M/L)",
                full_name="Apple Watch S11 (2025) S11 46mm Gold (M/L)",
                price=68500,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )
    sonic = normalizer.normalize_sonic(
        [
            RawSonicItem(
                batch_message_ids=[60],
                line_number=1,
                raw_name="S11 46 Gold SB M/L",
                full_name="Apple Watch S11 S11 46 Gold SB M/L",
                price=28200,
                country_flag="рџ‡єрџ‡ё",
            )
        ]
    )

    matcher = MatchingEngine(MatchingConfig())
    result = matcher.match(sonic[0], best)

    assert result.matched is False
