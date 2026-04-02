from __future__ import annotations

from app.normalization.normalizer import ItemNormalizer
from app.storage.models import RawBestItem, RawSonicItem
from app.utils.parsing import extract_model_code


US_FLAG = "\U0001F1FA\U0001F1F8"


def test_normalization_extracts_expected_ipad_fields() -> None:
    normalizer = ItemNormalizer()
    item = RawBestItem(
        sheet_name="iPad",
        row_number=10,
        raw_name="Silver Wi-Fi",
        full_name="iPad 11 (A16) 2025 128GB Silver Wi-Fi",
        price=27900,
        country_flag=US_FLAG,
    )

    normalized = normalizer.normalize_best([item])[0]

    assert normalized.category == "iPad"
    assert normalized.family == "ipad 11"
    assert normalized.product_line == "ipad 11"
    assert normalized.storage_gb == 128
    assert normalized.color == "silver"
    assert normalized.connectivity == "wifi"
    assert normalized.year == 2025
    assert normalized.chip == "A16"


def test_normalization_extracts_accessory_model_code() -> None:
    normalizer = ItemNormalizer()
    item = RawSonicItem(
        batch_message_ids=[1],
        line_number=2,
        raw_name="Magic Keyboard Air 11 Black (MGYX4)",
        full_name="Magic Keyboard (iPad Air) Magic Keyboard Air 11 Black (MGYX4)",
        price=25500,
        country_flag=US_FLAG,
        model_code="MGYX4",
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.category == "Accessory"
    assert normalized.product_line == "Magic Keyboard"
    assert normalized.model_code == "MGYX4"
    assert normalized.color == "black"


def test_normalization_does_not_detect_cellular_inside_64gb() -> None:
    normalizer = ItemNormalizer()
    item = RawBestItem(
        sheet_name="Аксессуары Apple",
        row_number=12,
        raw_name="Magic Mouse 3 White USB-C",
        full_name="Аксессуары Apple 64GB 128GB Magic Mouse 3 White USB-C",
        price=8100,
    )

    normalized = normalizer.normalize_best([item])[0]

    assert normalized.category == "Accessory"
    assert normalized.product_line == "Magic Mouse"
    assert normalized.storage_gb == 64
    assert normalized.connectivity is None


def test_extract_model_code_ignores_year_in_parentheses() -> None:
    assert extract_model_code("AirPods Max 2 (2024) AirPods Max 2 Midnight") is None
    assert extract_model_code("Magic Keyboard Air 11 Black (MGYX4)") == "MGYX4"


def test_airpods_generation_and_qualifier_are_not_duplicated() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="AirPods",
            row_number=1,
            raw_name="AirPods 4",
            full_name="AirPods 4",
            price=9100,
        ),
        RawBestItem(
            sheet_name="AirPods",
            row_number=2,
            raw_name="AirPods 4 ANC",
            full_name="AirPods 4 ANC",
            price=11600,
        ),
        RawBestItem(
            sheet_name="AirPods",
            row_number=3,
            raw_name="AirPods Pro 2 Type-C",
            full_name="AirPods Pro 2 Type-C",
            price=14500,
        ),
        RawBestItem(
            sheet_name="AirPods",
            row_number=4,
            raw_name="AirPods Max 2 Midnight",
            full_name="AirPods Max 2 (2024) AirPods Max 2 Midnight",
            price=39500,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].canonical_name == "airpods 4"
    assert normalized[1].canonical_name == "airpods 4 anc"
    assert normalized[1].canonical_key != normalized[0].canonical_key
    assert normalized[2].canonical_name == "airpods pro 2 type-c"
    assert normalized[3].canonical_name == "airpods max 2 2024 midnight"


def test_watch_generation_and_year_are_not_duplicated() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=1,
            raw_name="SE2 2024 44mm Midnight Sport Loop",
            full_name="Apple Watch SE2 (2024) SE2 2024 44mm Midnight Sport Loop",
            price=16800,
        ),
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=2,
            raw_name="S10 42mm Jet Black Sport Loop",
            full_name="Apple Watch S10 (2024) S10 42mm Jet Black Sport Loop",
            price=19900,
        ),
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=3,
            raw_name="Ultra 2 49mm Natural Ti Tan Alpine Loop Large",
            full_name="Apple Watch Ultra 2 (2024) Ultra 2 49mm Natural Ti Tan Alpine Loop Large",
            price=59900,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].product_line == "apple watch se"
    assert normalized[0].generation == "2"
    assert normalized[0].canonical_name == "apple watch se 2 2024 midnight 44mm sport loop"

    assert normalized[1].product_line == "apple watch series"
    assert normalized[1].generation == "10"
    assert normalized[1].canonical_name == "apple watch series 10 2024 black 42mm sport loop"

    assert normalized[2].product_line == "apple watch ultra"
    assert normalized[2].generation == "2"
    assert normalized[2].canonical_name == "apple watch ultra 2 2024 natural titanium 49mm tan alpine loop large"


def test_accessory_variants_do_not_collapse_into_same_key() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Аксессуары Apple",
            row_number=1,
            raw_name="Pencil USB-C",
            full_name="Pencil USB-C",
            price=7500,
        ),
        RawBestItem(
            sheet_name="Аксессуары Apple",
            row_number=2,
            raw_name="Pencil Pro",
            full_name="Pencil Pro",
            price=8700,
        ),
        RawBestItem(
            sheet_name="Аксессуары Apple",
            row_number=3,
            raw_name="Magic Mouse 3 White Lightning",
            full_name="Magic Mouse 3 White Lightning",
            price=6800,
        ),
        RawBestItem(
            sheet_name="Аксессуары Apple",
            row_number=4,
            raw_name="Magic Mouse 3 White USB-C",
            full_name="Magic Mouse 3 White USB-C",
            price=8100,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].canonical_name == "Apple Pencil usb-c"
    assert normalized[1].canonical_name == "Apple Pencil pro"
    assert normalized[0].canonical_key != normalized[1].canonical_key

    assert normalized[2].canonical_name == "Magic Mouse white lightning"
    assert normalized[3].canonical_name == "Magic Mouse white usb-c"
    assert normalized[2].canonical_key != normalized[3].canonical_key


def test_watch_band_size_and_precise_colors_stay_distinct() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=1,
            raw_name="S11 42mm Silver (S/M)",
            full_name="Apple Watch S11 (2025) S11 42mm Silver (S/M)",
            price=27800,
        ),
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=2,
            raw_name="S11 42mm Space Gray (M/L)",
            full_name="Apple Watch S11 (2025) S11 42mm Space Gray (M/L)",
            price=27800,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].canonical_name == "apple watch series 11 2025 silver 42mm sport band s/m"
    assert normalized[1].canonical_name == "apple watch series 11 2025 space gray 42mm sport band m/l"
    assert normalized[0].canonical_key != normalized[1].canonical_key


def test_watch_missing_band_type_defaults_to_sport_band_when_fit_is_present() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=1,
            raw_name="SE3 2025 40mm Starlight (S/M)",
            full_name="Apple Watch SE3 (2025) SE3 2025 40mm Starlight (S/M)",
            price=20400,
        ),
        RawSonicItem(
            batch_message_ids=[1],
            line_number=2,
            raw_name="S11 42 Jet Black S/M",
            full_name="Apple Watch S11 S11 42 Jet Black S/M",
            price=25800,
            country_flag=US_FLAG,
        ),
    ]

    best_normalized = normalizer.normalize_best([items[0]])[0]
    sonic_normalized = normalizer.normalize_sonic([items[1]])[0]

    assert best_normalized.size_label == "40mm sport band s/m"
    assert best_normalized.canonical_name == "apple watch se 3 2025 starlight 40mm sport band s/m"

    assert sonic_normalized.size_label == "42mm sport band s/m"
    assert sonic_normalized.canonical_name == "apple watch series 11 black 42mm sport band s/m"


def test_series_11_missing_band_type_uses_color_rule() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=1,
            raw_name="S11 46mm Gold (M/L)",
            full_name="Apple Watch S11 (2025) S11 46mm Gold (M/L)",
            price=68500,
        ),
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=2,
            raw_name="S11 46mm Silver (S/M)",
            full_name="Apple Watch S11 (2025) S11 46mm Silver (S/M)",
            price=29800,
        ),
        RawSonicItem(
            batch_message_ids=[1],
            line_number=3,
            raw_name="S11 42 Natural Ti M/L",
            full_name="Apple Watch S11 S11 42 Natural Ti M/L",
            price=63500,
            country_flag=US_FLAG,
        ),
    ]

    best_gold = normalizer.normalize_best([items[0]])[0]
    best_silver = normalizer.normalize_best([items[1]])[0]
    sonic_natural = normalizer.normalize_sonic([items[2]])[0]

    assert best_gold.size_label == "46mm milanese loop m/l"
    assert best_gold.canonical_name == "apple watch series 11 2025 gold 46mm milanese loop m/l"

    assert best_silver.size_label == "46mm sport band s/m"
    assert best_silver.canonical_name == "apple watch series 11 2025 silver 46mm sport band s/m"

    assert sonic_natural.size_label == "42mm milanese loop m/l"
    assert sonic_natural.canonical_name == "apple watch series 11 natural titanium 42mm milanese loop m/l"


def test_explicit_watch_band_type_is_not_overridden_by_series_11_color_rule() -> None:
    normalizer = ItemNormalizer()
    item = RawSonicItem(
        batch_message_ids=[1],
        line_number=1,
        raw_name="S11 42 Gold Sport Loop S/M",
        full_name="Apple Watch S11 S11 42 Gold Sport Loop S/M",
        price=25800,
        country_flag=US_FLAG,
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.size_label == "42mm sport loop s/m"
    assert normalized.canonical_name == "apple watch series 11 gold 42mm sport loop s/m"


def test_series_11_explicit_milanese_loop_in_raw_text_blocks_color_inference() -> None:
    normalizer = ItemNormalizer()
    item = RawBestItem(
        sheet_name="Apple Watch",
        row_number=1,
        raw_name="S11 46mm Slate Milanese Loop (M/L)",
        full_name="Apple Watch S11 (2025) S11 46mm Slate Milanese Loop (M/L)",
        price=68300,
    )

    normalized = normalizer.normalize_best([item])[0]

    assert normalized.size_label == "46mm milanese loop m/l"
    assert normalized.canonical_name == "apple watch series 11 2025 slate 46mm milanese loop m/l"


def test_series_11_explicit_sb_in_raw_text_blocks_color_inference() -> None:
    normalizer = ItemNormalizer()
    item = RawSonicItem(
        batch_message_ids=[1],
        line_number=1,
        raw_name="S11 42 Space Gray SB S/M",
        full_name="Apple Watch S11 S11 42 Space Gray SB S/M",
        price=25800,
        country_flag=US_FLAG,
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.size_label == "42mm sport band s/m"
    assert normalized.canonical_name == "apple watch series 11 space gray 42mm sport band s/m"


def test_watch_band_color_is_included_in_variant_when_present() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=1,
            raw_name="Ultra 2 49mm Black Ti Blue Alpine Loop Large",
            full_name="Apple Watch Ultra 2 (2024) Ultra 2 49mm Black Ti Blue Alpine Loop Large",
            price=65300,
        ),
        RawBestItem(
            sheet_name="Apple Watch",
            row_number=2,
            raw_name="Ultra 2 49mm Black Ti Olive Alpine Loop Large",
            full_name="Apple Watch Ultra 2 (2024) Ultra 2 49mm Black Ti Olive Alpine Loop Large",
            price=65300,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].canonical_name == "apple watch ultra 2 2024 black titanium 49mm blue alpine loop large"
    assert normalized[1].canonical_name == "apple watch ultra 2 2024 black titanium 49mm olive alpine loop large"
    assert normalized[0].canonical_key != normalized[1].canonical_key


def test_sonic_watch_shorthand_keeps_case_color_size_and_band_details() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawSonicItem(
            batch_message_ids=[1],
            line_number=1,
            raw_name="S11 42 Silver SB Purple Fog S/M",
            full_name="Apple Watch S11 S11 42 Silver SB Purple Fog S/M",
            price=27500,
            country_flag=US_FLAG,
        ),
        RawSonicItem(
            batch_message_ids=[1],
            line_number=2,
            raw_name="S11 42 Natural Ti Milanese Loop",
            full_name="Apple Watch S11 S11 42 Natural Ti Milanese Loop",
            price=63500,
            country_flag=US_FLAG,
        ),
    ]

    normalized = normalizer.normalize_sonic(items)

    assert normalized[0].color == "silver"
    assert normalized[0].size_label == "42mm sport band purple fog s/m"
    assert normalized[0].canonical_name == "apple watch series 11 silver 42mm sport band purple fog s/m"

    assert normalized[1].color == "natural titanium"
    assert normalized[1].size_label == "42mm milanese loop"
    assert normalized[1].canonical_name == "apple watch series 11 natural titanium 42mm milanese loop"


def test_iphone_without_explicit_prefix_is_still_parsed_structurally() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="iPhone",
            row_number=1,
            raw_name="16 Pro Max 1TB Desert",
            full_name="16 Pro Max 1TB Desert",
            price=139300,
        ),
        RawBestItem(
            sheet_name="iPhone",
            row_number=2,
            raw_name="Air 1TB Light Gold",
            full_name="Air 1TB Light Gold",
            price=109500,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].product_line == "iphone 16 pro max"
    assert normalized[0].storage_gb == 1024
    assert normalized[0].color == "desert titanium"
    assert normalized[0].canonical_name == "iphone 16 pro max 1024GB desert titanium"

    assert normalized[1].product_line == "iphone air"
    assert normalized[1].storage_gb == 1024
    assert normalized[1].color == "gold"
    assert normalized[1].canonical_name == "iphone air 1024GB gold"


def test_macbook_slash_specs_extract_ram_storage_and_screen_size() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="MacBook",
            row_number=1,
            raw_name="Pro 14 M5 2025 16/1TB Silver MDE54",
            full_name="Pro 14 M5 2025 16/1TB Silver MDE54",
            price=145400,
        ),
        RawBestItem(
            sheet_name="MacBook",
            row_number=2,
            raw_name="Air 13 M4 2025 24/512GB Sky Blue MC6V4",
            full_name="Air 13 M4 2025 24/512GB Sky Blue MC6V4",
            price=112000,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].product_line == "macbook pro"
    assert normalized[0].screen_size == "14"
    assert normalized[0].ram_gb == 16
    assert normalized[0].storage_gb == 1024
    assert normalized[0].canonical_name == "macbook pro 2025 M5 14in 1024GB 16GB RAM silver MDE54"

    assert normalized[1].product_line == "macbook air"
    assert normalized[1].screen_size == "13"
    assert normalized[1].ram_gb == 24
    assert normalized[1].storage_gb == 512
    assert normalized[1].color == "blue"


def test_mac_mini_gets_dedicated_mac_category_without_affecting_macbook_or_imac() -> None:
    normalizer = ItemNormalizer()
    items = [
        RawBestItem(
            sheet_name="MacBook",
            row_number=1,
            raw_name="Mac Mini M4 16/256GB MU9D3",
            full_name="Mac Mini M4 16/256GB MU9D3",
            price=59900,
        ),
        RawBestItem(
            sheet_name="MacBook",
            row_number=2,
            raw_name="MacBook Pro 14 M5 2025 16/1TB Silver MDE54",
            full_name="MacBook Pro 14 M5 2025 16/1TB Silver MDE54",
            price=145400,
        ),
        RawBestItem(
            sheet_name="iMac",
            row_number=3,
            raw_name="iMac 24 M4 16/512GB Blue",
            full_name="iMac 24 M4 16/512GB Blue",
            price=120000,
        ),
    ]

    normalized = normalizer.normalize_best(items)

    assert normalized[0].category == "Mac"
    assert normalized[0].product_line == "mac mini"
    assert normalized[0].family == "mac mini"

    assert normalized[1].category == "MacBook"
    assert normalized[1].product_line == "macbook pro"

    assert normalized[2].category == "iMac"
    assert normalized[2].product_line == "imac"


def test_ipad_pro_sonic_line_extracts_screen_size_storage_and_chip_without_gb_suffix() -> None:
    normalizer = ItemNormalizer()
    item = RawSonicItem(
        batch_message_ids=[1],
        line_number=1,
        raw_name="iPad Pro 11 M5 512 Space Black Wi-Fi",
        full_name="iPad Pro M5 2025 iPad Pro 11 M5 512 Space Black Wi-Fi",
        price=98500,
        country_flag=US_FLAG,
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.category == "iPad"
    assert normalized.product_line == "ipad pro"
    assert normalized.chip == "M5"
    assert normalized.year == 2025
    assert normalized.screen_size == "11"
    assert normalized.storage_gb == 512
    assert normalized.canonical_name == "ipad pro 2025 M5 11in 512GB wifi space black"


def test_macbook_sonic_line_extracts_screen_size_when_section_title_repeats_model() -> None:
    normalizer = ItemNormalizer()
    item = RawSonicItem(
        batch_message_ids=[1],
        line_number=1,
        raw_name="MacBook Pro 14 M5 24/1TB Space Black",
        full_name="MacBook Pro M5 MacBook Pro 14 M5 24/1TB Space Black",
        price=152000,
        country_flag=US_FLAG,
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.category == "MacBook"
    assert normalized.product_line == "macbook pro"
    assert normalized.chip == "M5"
    assert normalized.screen_size == "14"
    assert normalized.ram_gb == 24
    assert normalized.storage_gb == 1024
    assert normalized.canonical_name == "macbook pro M5 14in 1024GB 24GB RAM space black"
