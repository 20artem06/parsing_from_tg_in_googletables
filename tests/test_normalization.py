from __future__ import annotations

from app.normalization.normalizer import ItemNormalizer
from app.storage.models import RawBestItem, RawSonicItem


def test_normalization_extracts_expected_ipad_fields() -> None:
    normalizer = ItemNormalizer()
    item = RawBestItem(
        sheet_name="iPad",
        row_number=10,
        raw_name="Silver Wi-Fi",
        full_name="iPad 11 (A16) 2025 128GB Silver Wi-Fi",
        price=27900,
        country_flag="🇺🇸",
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
        country_flag="🇺🇸",
        model_code="MGYX4",
    )

    normalized = normalizer.normalize_sonic([item])[0]

    assert normalized.category == "Accessory"
    assert normalized.product_line == "Magic Keyboard"
    assert normalized.model_code == "MGYX4"
    assert normalized.color == "black"
