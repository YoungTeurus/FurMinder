from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE, relativedelta


class RecurrenceType(StrEnum):
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    MONTHLY_WEEKDAY = "monthly_weekday"


WEEKDAY_TO_REL: dict[int, relativedelta] = {
    0: MO,
    1: TU,
    2: WE,
    3: TH,
    4: FR,
    5: SA,
    6: SU,
}


def _monthly_weekday_occurrence(
    year: int,
    month: int,
    weekday: int,
    week_of_month: int,
) -> date | None:
    weekday_rel = WEEKDAY_TO_REL[weekday]
    if week_of_month == -1:
        anchor = date(year, month, 1) + relativedelta(months=1, days=-1)
        candidate = anchor + relativedelta(weekday=weekday_rel(-1))
        return candidate if candidate.month == month else None

    candidate = date(year, month, 1) + relativedelta(weekday=weekday_rel(week_of_month))
    return candidate if candidate.month == month else None


def compute_occurrences_between(
    *,
    anchor_start: date,
    anchor_end: date | None,
    recurrence: dict[str, Any] | None,
    range_start: date,
    range_end: date,
) -> list[tuple[date, date | None]]:
    if not recurrence or not recurrence.get("enabled"):
        if range_start <= anchor_start <= range_end:
            return [(anchor_start, anchor_end)]
        return []

    recurrence_type = recurrence.get("type")
    interval = max(int(recurrence.get("interval", 1)), 1)
    duration = (anchor_end or anchor_start) - anchor_start
    occurrences: list[tuple[date, date | None]] = []

    if recurrence_type == RecurrenceType.YEARLY:
        year = anchor_start.year
        while year <= range_end.year + 1:
            try:
                start = date(year, anchor_start.month, anchor_start.day)
            except ValueError:
                start = date(year, anchor_start.month, 1) + relativedelta(day=31)
            end = start + duration if duration.days else None
            if range_start <= start <= range_end:
                occurrences.append((start, end))
            year += interval

    elif recurrence_type == RecurrenceType.MONTHLY:
        cursor = date(anchor_start.year, anchor_start.month, 1)
        limit = range_end + relativedelta(months=1)
        while cursor <= limit:
            last_day = (date(cursor.year, cursor.month, 1) + relativedelta(months=1, days=-1)).day
            day = min(anchor_start.day, last_day)
            start = date(cursor.year, cursor.month, day)
            end = start + duration if duration.days else None
            if range_start <= start <= range_end:
                occurrences.append((start, end))
            cursor += relativedelta(months=interval)

    elif recurrence_type == RecurrenceType.WEEKLY:
        cursor = anchor_start
        while cursor <= range_end:
            if cursor >= range_start:
                end = cursor + duration if duration.days else None
                occurrences.append((cursor, end))
            cursor += timedelta(weeks=interval)

    elif recurrence_type == RecurrenceType.MONTHLY_WEEKDAY:
        weekday = int(recurrence.get("weekday", anchor_start.weekday()))
        week_of_month = int(recurrence.get("week_of_month", 1))
        cursor = date(range_start.year, range_start.month, 1)
        limit = range_end + relativedelta(months=1)
        while cursor <= limit:
            start = _monthly_weekday_occurrence(cursor.year, cursor.month, weekday, week_of_month)
            if start and range_start <= start <= range_end:
                end = start + duration if duration.days else None
                occurrences.append((start, end))
            cursor += relativedelta(months=interval)

    return occurrences


def recurrence_label(recurrence: dict[str, Any] | None, locale: str = "ru") -> str:
    from furminder.i18n import t

    if not recurrence or not recurrence.get("enabled"):
        return "—"

    recurrence_type = recurrence.get("type")
    if recurrence_type == RecurrenceType.YEARLY:
        return t("recurrence_label_yearly", locale)
    if recurrence_type == RecurrenceType.MONTHLY:
        return t("recurrence_label_monthly", locale)
    if recurrence_type == RecurrenceType.WEEKLY:
        return t("recurrence_label_weekly", locale)
    if recurrence_type == RecurrenceType.MONTHLY_WEEKDAY:
        weekday = int(recurrence.get("weekday", 0))
        week_of_month = int(recurrence.get("week_of_month", 1))
        weekday_names = [
            t("weekday_mon", locale),
            t("weekday_tue", locale),
            t("weekday_wed", locale),
            t("weekday_thu", locale),
            t("weekday_fri", locale),
            t("weekday_sat", locale),
            t("weekday_sun", locale),
        ]
        week_names = {
            1: t("week_first", locale),
            2: t("week_second", locale),
            3: t("week_third", locale),
            4: t("week_fourth", locale),
            -1: t("week_last", locale),
        }
        return t(
            "recurrence_label_monthly_weekday",
            locale,
            week=week_names.get(week_of_month, str(week_of_month)),
            weekday=weekday_names[weekday],
        )
    return "—"


def chat_now(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))
