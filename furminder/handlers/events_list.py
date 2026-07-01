from __future__ import annotations

from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from furminder.db.repository import Database
from furminder.i18n import t
from furminder.services.date_parser import format_date_range
from furminder.services.permissions import can_manage_event
from furminder.services.recurrence import compute_occurrences_between, recurrence_enabled
from furminder.services.reminders import build_event_card


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


def _next_occurrence_start(event: dict) -> date | None:
    anchor_start = date.fromisoformat(event["start_date"])
    anchor_end = date.fromisoformat(event["end_date"]) if event.get("end_date") else None
    today = date.today()
    occurrences = compute_occurrences_between(
        anchor_start=anchor_start,
        anchor_end=anchor_end,
        recurrence=event.get("recurrence"),
        range_start=today,
        range_end=today + timedelta(days=365 * 2),
    )
    return occurrences[0][0] if occurrences else None


async def events_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    await db.ensure_chat(chat_id, update.effective_chat.title)

    events = await db.list_upcoming_events(chat_id)
    visible = []
    for event in events:
        if recurrence_enabled(event.get("recurrence")):
            if _next_occurrence_start(event):
                visible.append(event)
        else:
            if date.fromisoformat(event["start_date"]) >= date.today():
                visible.append(event)

    if not visible:
        await update.message.reply_text(t("no_events"))
        return

    lines = [t("events_header")]
    for event in visible[:20]:
        start = date.fromisoformat(event["start_date"])
        end = date.fromisoformat(event["end_date"]) if event.get("end_date") else None
        if recurrence_enabled(event.get("recurrence")):
            next_start = _next_occurrence_start(event)
            if next_start:
                duration = (end - start).days if end and end > start else 0
                display_end = next_start + timedelta(days=duration) if duration else None
                lines.append(f"#{event['local_id']} {event['title']} — {format_date_range(next_start, display_end)}")
        else:
            lines.append(f"#{event['local_id']} {event['title']} — {format_date_range(start, end)}")
    await update.message.reply_text("\n".join(lines))


async def event_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return
    if not context.args:
        await update.message.reply_text("/event <номер>")
        return

    local_id = int(context.args[0])
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    event = await db.get_event(chat_id, local_id)
    if not event:
        await update.message.reply_text(t("event_not_found", local_id=local_id))
        return

    text = build_event_card(event)
    if event.get("image_file_id"):
        await update.message.reply_photo(event["image_file_id"], caption=text)
    else:
        await update.message.reply_text(text)


async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return
    if not context.args:
        await update.message.reply_text("/delete <номер>")
        return

    local_id = int(context.args[0])
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    event = await db.get_event(chat_id, local_id)
    if not event:
        await update.message.reply_text(t("event_not_found", local_id=local_id))
        return

    if not await can_manage_event(update, context, created_by=event["created_by"]):
        await update.message.reply_text(t("cannot_delete"))
        return

    await db.delete_event(chat_id, local_id)
    await update.message.reply_text(t("event_deleted", local_id=local_id))
