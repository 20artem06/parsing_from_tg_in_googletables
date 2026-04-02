from __future__ import annotations

import re


YEAR_RE = re.compile(r"\b(20[1-3]\d)\b", re.IGNORECASE)
STORAGE_RE = re.compile(r"\b(\d{1,4})\s*(tb|gb|гб|тб)\b", re.IGNORECASE)
SPEC_PAIR_RE = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,4})\s*(tb|gb|гб|тб)\b", re.IGNORECASE)
RAM_RE = re.compile(r"\b(\d{1,2})\s*(?:gb|гб)\s*ram\b", re.IGNORECASE)
SCREEN_RE = re.compile(r'\b(\d{1,2}(?:\.\d)?)\s*(?:inch|in|"|”|″)\b', re.IGNORECASE)
MM_SIZE_RE = re.compile(r"\b(\d{2})\s*mm\b", re.IGNORECASE)
CHIP_RE = re.compile(r"\b((?:m|a)\d{1,2}(?:\s?(?:pro|max|ultra))?)\b", re.IGNORECASE)
IPHONE_RE = re.compile(
    r"\b(?:iphone\s*)?(air|\d{2})(?:\s*(pro max|pro|plus|max|mini|e))?\b",
    re.IGNORECASE,
)
IPAD_RE = re.compile(
    r"\bipad(?:\s+(pro|air|mini))?(?:\s+(\d{1,2}(?:\.\d)?))?\b",
    re.IGNORECASE,
)
MACBOOK_RE = re.compile(
    r"\b(?:macbook\s+)?(air|pro|neo)(?:\s+(\d{1,2}(?:\.\d)?))?\b",
    re.IGNORECASE,
)
IMAC_RE = re.compile(r"\bimac(?:\s+(\d{2}))?\b", re.IGNORECASE)
WATCH_SERIES_RE = re.compile(
    r"\b(?:apple\s+watch\s+)?(?:series\s*|s)(\d{1,2})\b",
    re.IGNORECASE,
)
WATCH_SE_RE = re.compile(r"\b(?:apple\s+watch\s+)?se\s*(\d{0,2})\b", re.IGNORECASE)
WATCH_ULTRA_RE = re.compile(
    r"\b(?:apple\s+watch\s+)?ultra\s*(\d{0,2})\b",
    re.IGNORECASE,
)
AIRPODS_MAX_RE = re.compile(r"\bairpods\s+max(?:\s+(\d{1,2}))?\b", re.IGNORECASE)
AIRPODS_PRO_RE = re.compile(r"\bairpods\s+pro(?:\s+(\d{1,2}))?\b", re.IGNORECASE)
AIRPODS_STD_RE = re.compile(r"\bairpods(?:\s+(\d{1,2}))?\b", re.IGNORECASE)
