from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_flag(text: str) -> str | None:
    match = FLAG_RE.search(text)
    return match.group(0) if match else None


def extract_model_code(text: str) -> str | None:
    match = re.search(r"\(([A-Z0-9]{4,12})\)", text)
    if match:
        return match.group(1)
    match = re.search(r"\b([A-Z]{2,5}\d[A-Z0-9]{1,8})\b", text)
    return match.group(1) if match else None


def parse_price(raw: object) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)

    text = clean_text(raw)
    if not text:
        return None

    text = (
        text.lower()
        .replace("руб.", "")
        .replace("руб", "")
        .replace("р.", "")
        .replace("р", "")
    )
    text = text.replace(",", ".")
    text = re.sub(r"[^\d.]", "", text)
    if not text:
        return None

    if text.count(".") > 1:
        text = text.replace(".", "")
    elif "." in text:
        left, right = text.split(".", maxsplit=1)
        if len(right) == 3:
            text = left + right

    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return None
