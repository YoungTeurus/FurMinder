from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from dateutil import parser as date_parser

SKIP_WORDS = {"пропустить", "skip", "-", "нет", "no"}
MONTHS_RU = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}


def is_skip(value: str) -> bool:
    return value.strip().lower() in SKIP_WORDS


def parse_date(text: str, *, base: date | None = None) -> date | None:
    raw = text.strip().lower()
    if not raw or is_skip(raw):
        return None

    today = base or date.today()
    if raw in {"сегодня", "today"}:
        return today
    if raw in {"завтра", "tomorrow"}:
        return today + timedelta(days=1)
    if raw in {"послезавтра"}:
        return today + timedelta(days=2)
    if raw.startswith("через недел"):
        return today + timedelta(days=7)

    for prefix, month in MONTHS_RU.items():
        match = re.search(rf"(\d{{1,2}})\s+{prefix}", raw)
        if match:
            day = int(match.group(1))
            year_match = re.search(r"(20\d{2})", raw)
            year = int(year_match.group(1)) if year_match else today.year
            try:
                return date(year, month, day)
            except ValueError:
                return None

    normalized = raw.replace(",", ".")
    try:
        parsed = date_parser.parse(normalized, dayfirst=True, default=datetime.combine(today, time.min))
        return parsed.date()
    except (ValueError, OverflowError):
        return None


def parse_time(text: str) -> time | None:
    raw = text.strip().lower()
    if not raw or is_skip(raw):
        return None

    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})", raw)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    try:
        parsed = date_parser.parse(raw, default=datetime.combine(date.today(), time.min))
        return parsed.time().replace(second=0, microsecond=0)
    except (ValueError, OverflowError):
        return None


def parse_int_days(text: str) -> int | None:
    raw = text.strip()
    if not raw.isdigit():
        return None
    return int(raw)


def parse_yes_no(text: str) -> bool | None:
    raw = text.strip().lower()
    if raw in {"да", "yes", "y", "1"}:
        return True
    if raw in {"нет", "no", "n", "0"}:
        return False
    return None


def is_valid_url(text: str) -> bool:
    return bool(re.match(r"^https?://\S+$", text.strip(), re.IGNORECASE))


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_time(value: time | None) -> str:
    if not value:
        return "—"
    return value.strftime("%H:%M")


def format_date_range(start: date, end: date | None) -> str:
    if not end or end == start:
        return format_date(start)
    return f"{format_date(start)} — {format_date(end)}"
