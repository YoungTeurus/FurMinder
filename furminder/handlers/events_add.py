from __future__ import annotations

from datetime import date, datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from furminder.db.repository import Database
from furminder.i18n import t
from furminder.keyboards.inline import confirm_keyboard, preset_keyboard, recurrence_keyboard
from furminder.services.date_parser import (
    is_skip,
    is_valid_url,
    parse_date,
    parse_time,
)
from furminder.services.permissions import can_add_event
from furminder.services.recurrence import RecurrenceType
from furminder.services.reminders import build_event_card

(
    PRESET,
    TITLE,
    START_DATE,
    END_DATE,
    START_TIME,
    END_TIME,
    DESCRIPTION,
    IMAGE,
    WEBSITE,
    RECURRENCE,
    CONFIRM,
) = range(11)

DRAFT_KEY = "event_draft"


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


def _get_draft(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.chat_data.setdefault(DRAFT_KEY, {})


def _clear_draft(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data.pop(DRAFT_KEY, None)


def _week_of_month(value: date) -> int:
    return (value.day - 1) // 7 + 1


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return ConversationHandler.END

    db: Database = context.application.bot_data["db"]
    chat = update.effective_chat
    chat_doc = await db.ensure_chat(chat.id, chat.title)
    if not await can_add_event(update, context, chat_doc):
        await update.message.reply_text(t("cannot_add_events"))
        return ConversationHandler.END

    _clear_draft(context)
    await update.message.reply_text(t("choose_preset"), reply_markup=preset_keyboard())
    return PRESET


async def preset_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    preset = query.data.split(":", 1)[1]
    draft = _get_draft(context)
    draft["preset"] = None if preset == "custom" else preset

    if preset == "birthday":
        draft["recurrence"] = {"enabled": True, "type": RecurrenceType.YEARLY, "interval": 1}
    elif preset == "festival":
        draft["single_day"] = True
    elif preset == "con":
        draft["multi_day"] = True

    await query.edit_message_text(t("ask_title"))
    return TITLE


async def title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text(t("ask_title"))
        return TITLE

    _get_draft(context)["title"] = title
    await update.message.reply_text(t("ask_start_date"))
    return START_DATE


async def start_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parsed = parse_date(update.message.text)
    if not parsed:
        await update.message.reply_text(t("invalid_date"))
        return START_DATE

    draft = _get_draft(context)
    draft["start_date"] = parsed.isoformat()

    if draft.get("single_day"):
        draft["end_date"] = None
        await update.message.reply_text(t("ask_start_time"))
        return START_TIME

    if draft.get("multi_day"):
        await update.message.reply_text(t("ask_end_date"))
        return END_DATE

    await update.message.reply_text(t("ask_end_date"))
    return END_DATE


async def end_date_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    if is_skip(update.message.text):
        draft["end_date"] = None
    else:
        parsed = parse_date(update.message.text)
        if not parsed:
            await update.message.reply_text(t("invalid_date"))
            return END_DATE
        if parsed < date.fromisoformat(draft["start_date"]):
            await update.message.reply_text(t("end_before_start"))
            return END_DATE
        draft["end_date"] = parsed.isoformat()

    await update.message.reply_text(t("ask_start_time"))
    return START_TIME


async def start_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    if is_skip(update.message.text):
        draft["start_time"] = None
    else:
        parsed = parse_time(update.message.text)
        if not parsed:
            await update.message.reply_text(t("invalid_time"))
            return START_TIME
        draft["start_time"] = parsed.strftime("%H:%M")

    await update.message.reply_text(t("ask_end_time"))
    return END_TIME


async def end_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    if is_skip(update.message.text):
        draft["end_time"] = None
    else:
        if not draft.get("start_time"):
            await update.message.reply_text(t("end_time_without_start"))
            return END_TIME
        parsed = parse_time(update.message.text)
        if not parsed:
            await update.message.reply_text(t("invalid_time"))
            return END_TIME
        draft["end_time"] = parsed.strftime("%H:%M")

    await update.message.reply_text(t("ask_description"))
    return DESCRIPTION


async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    draft["description"] = None if is_skip(update.message.text) else update.message.text.strip()
    await update.message.reply_text(t("ask_image"))
    return IMAGE


async def image_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    if update.message.photo:
        draft["image_file_id"] = update.message.photo[-1].file_id
    elif is_skip(update.message.text or ""):
        draft["image_file_id"] = None
    else:
        await update.message.reply_text(t("ask_image"))
        return IMAGE

    await update.message.reply_text(t("ask_website"))
    return WEBSITE


async def website_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = _get_draft(context)
    text = (update.message.text or "").strip()
    if is_skip(text):
        draft["website_url"] = None
    elif is_valid_url(text):
        draft["website_url"] = text
    else:
        await update.message.reply_text(t("invalid_url"))
        return WEBSITE

    if draft.get("recurrence"):
        return await _show_confirm(update, context)

    await update.message.reply_text(t("ask_recurrence"), reply_markup=recurrence_keyboard())
    return RECURRENCE


async def recurrence_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = _get_draft(context)
    rec_type = query.data.split(":", 1)[1]

    if rec_type == "none":
        draft["recurrence"] = None
    else:
        start = date.fromisoformat(draft["start_date"])
        recurrence = {"enabled": True, "type": rec_type, "interval": 1}
        if rec_type == RecurrenceType.MONTHLY_WEEKDAY:
            recurrence["weekday"] = start.weekday()
            recurrence["week_of_month"] = _week_of_month(start)
        draft["recurrence"] = recurrence

    await query.edit_message_text(t("confirm_event"))
    return await _show_confirm(update, context, from_callback=True)


async def _show_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    from_callback: bool = False,
) -> int:
    draft = _get_draft(context)
    preview = build_event_card(
        {
            "local_id": 0,
            "title": draft["title"],
            "start_date": draft["start_date"],
            "end_date": draft.get("end_date"),
            "start_time": draft.get("start_time"),
            "end_time": draft.get("end_time"),
            "description": draft.get("description"),
            "website_url": draft.get("website_url"),
            "recurrence": draft.get("recurrence"),
        }
    )
    text = f"{t('confirm_event')}\n\n{preview}"
    if from_callback:
        await update.callback_query.message.reply_text(text, reply_markup=confirm_keyboard())
    elif update.message:
        await update.message.reply_text(text, reply_markup=confirm_keyboard())
    return CONFIRM


async def confirm_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm:cancel":
        _clear_draft(context)
        await query.edit_message_text(t("cancelled"))
        return ConversationHandler.END

    draft = _get_draft(context)
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    local_id = await db.next_local_id(chat_id)

    event_doc = {
        "chat_id": chat_id,
        "local_id": local_id,
        "preset": draft.get("preset"),
        "title": draft["title"],
        "start_date": draft["start_date"],
        "end_date": draft.get("end_date"),
        "start_time": draft.get("start_time"),
        "end_time": draft.get("end_time"),
        "description": draft.get("description"),
        "image_file_id": draft.get("image_file_id"),
        "website_url": draft.get("website_url"),
        "recurrence": draft.get("recurrence"),
        "created_by": update.effective_user.id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await db.create_event(event_doc)
    _clear_draft(context)
    await query.edit_message_text(t("event_saved", local_id=local_id, title=draft["title"]))
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear_draft(context)
    await update.message.reply_text(t("cancelled"))
    return ConversationHandler.END
