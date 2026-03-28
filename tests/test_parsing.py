from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.parsers.best_excel_parser import BestExcelParser
from app.parsers.sonic_text_parser import SonicTextParser
from app.storage.models import SonicBatch
from app.utils.parsing import parse_price


def test_parse_price_variants() -> None:
    assert parse_price("27.900") == 27900
    assert parse_price("43 500") == 43500
    assert parse_price("52,900") == 52900
    assert parse_price(61000) == 61000


def test_parse_sonic_line_and_model_code() -> None:
    parser = SonicTextParser()
    item = parser.parse_line(
        line="Magic Keyboard Air 11 Black (MGYX4) - 25.500 🇺🇸",
        line_number=3,
        current_section="Magic Keyboard (iPad Air)",
        batch_message_ids=[101, 102],
    )

    assert item is not None
    assert item.price == 25500
    assert item.country_flag == "🇺🇸"
    assert item.model_code == "MGYX4"
    assert item.full_name.startswith("Magic Keyboard (iPad Air)")


def test_parse_best_excel_with_sections() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "iPad"
    sheet.append(["Модель", "Стоимость", "Флаг"])
    sheet.append(["iPad 11 (A16) 2025", None, None])
    sheet.append(["128GB", None, None])
    sheet.append(["Silver Wi-Fi", "27.900", "🇺🇸"])

    buffer = BytesIO()
    workbook.save(buffer)

    parser = BestExcelParser()
    items = parser.parse_bytes(buffer.getvalue())

    assert len(items) == 1
    assert items[0].price == 27900
    assert items[0].country_flag == "🇺🇸"
    assert items[0].full_name == "iPad 11 (A16) 2025 128GB Silver Wi-Fi"


def test_parse_sonic_batch_keeps_section_context() -> None:
    batch = SonicBatch(
        message_ids=[201, 202],
        raw_text=(
            "iPad 11 (A16) 2025\n"
            "iPad 11 128 Silver Wi-Fi - 27.900 🇺🇸\n"
            "iPad 11 128 Pink LTE - 43.500 🇺🇸"
        ),
    )
    parser = SonicTextParser()
    items = parser.parse_batch(batch)

    assert len(items) == 2
    assert items[0].section_name == "iPad 11 (A16) 2025"
    assert items[1].price == 43500
