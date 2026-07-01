from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from furminder.db.repository import Database, parse_time_str
from furminder.i18n import t
from furminder.services.date_parser import format_date, format_date_range, format_time
from furminder.services.recurrence import compute_occurrences_between, recurrence_label


def build_event_card(event: dict, *, locale: str = "ru") -> str:
    start = date.fromisoformat(event["start_date"])
    end = date.fromisoformat(event["end_date"]) if event.get("end_date") else None
    start_time = event.get("start_time")
    end_time = event.get("end_time")

    lines = [
        f"#{event['local_id']} — {event['title']}",
        f"{t('field_dates', locale)}: {format_date_range(start, end)}",
    ]
    if start_time or end_time:
        lines.append(
            f"{t('field_times', locale)}: {format_time(parse_time_str(start_time) if start_time else None)}"
            f" — {format_time(parse_time_str(end_time) if end_time else None)}"
        )
    if event.get("description"):
        lines.append(f"{t('field_description', locale)}: {event['description']}")
    if event.get("website_url"):
        lines.append(f"{t('field_website', locale)}: {event['website_url']}")
    recurrence = event.get("recurrence")
    if recurrence and recurrence.get("enabled"):
        lines.append(f"{t('field_recurrence', locale)}: {recurrence_label(recurrence, locale)}")
    return "\n".join(lines)


def build_reminder_text(
    event: dict,
    *,
    offset_days: int,
    occurrence_start: date,
    occurrence_end: date | None,
    locale: str = "ru",
) -> str:
    if offset_days == 0:
        header = t("reminder_today", locale, title=event["title"])
    elif offset_days == 1:
        header = t("reminder_tomorrow", locale, title=event["title"])
    else:
        header = t("reminder_in_days", locale, days=offset_days, title=event["title"])

    lines = [header, format_date_range(occurrence_start, occurrence_end)]
    if event.get("start_time") or event.get("end_time"):
        lines.append(
            f"{format_time(parse_time_str(event['start_time']) if event.get('start_time') else None)}"
            f" — {format_time(parse_time_str(event['end_time']) if event.get('end_time') else None)}"
        )
    if event.get("description"):
        lines.append(event["description"])
    if event.get("website_url"):
        lines.append(event["website_url"])
    return "\n".join(lines)


async def process_due_reminders(db: Database, bot) -> None:
    chats = await db.list_active_chats()
    for chat in chats:
        chat_id = chat["_id"]
        timezone_name = chat.get("timezone", "Europe/Moscow")
        now = datetime.now(ZoneInfo(timezone_name))
        current_time = now.time().replace(second=0, microsecond=0)
        today = now.date()

        rules = await db.list_reminder_rules(chat_id)
        enabled_rules = [rule for rule in rules if rule.get("enabled", True)]
        if not enabled_rules:
            continue

        events = await db.list_events_for_chat(chat_id)
        for event in events:
            anchor_start = date.fromisoformat(event["start_date"])
            anchor_end = date.fromisoformat(event["end_date"]) if event.get("end_date") else None
            for rule in enabled_rules:
                send_time = parse_time_str(rule["send_time"]).replace(second=0, microsecond=0)
                if current_time != send_time:
                    continue

                offset_days = int(rule["offset_days"])
                remind_on = today + timedelta(days=offset_days)
                range_start = remind_on
                range_end = remind_on
                occurrences = compute_occurrences_between(
                    anchor_start=anchor_start,
                    anchor_end=anchor_end,
                    recurrence=event.get("recurrence"),
                    range_start=range_start,
                    range_end=range_end,
                )
                for occurrence_start, occurrence_end in occurrences:
                    if await db.was_reminder_sent(
                        event_id=event["_id"],
                        rule_id=rule["_id"],
                        occurrence_start=occurrence_start.isoformat(),
                    ):
                        continue

                    silent = rule.get("silent", False) or chat.get("default_silent", False)
                    text = build_reminder_text(
                        event,
                        offset_days=offset_days,
                        occurrence_start=occurrence_start,
                        occurrence_end=occurrence_end,
                    )
                    try:
                        if event.get("image_file_id"):
                            await bot.send_photo(
                                chat_id=chat_id,
                                photo=event["image_file_id"],
                                caption=text,
                                disable_notification=silent,
                            )
                        else:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                disable_web_page_preview=False,
                                disable_notification=silent,
                            )
                        await db.mark_reminder_sent(
                            event_id=event["_id"],
                            rule_id=rule["_id"],
                            occurrence_start=occurrence_start.isoformat(),
                        )
                    except Exception:
                        continue
