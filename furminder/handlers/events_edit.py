from __future__ import annotations

from datetime import date, datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from furminder.db.repository import Database
from furminder.i18n import t
from furminder.keyboards.inline import edit_field_keyboard, recurrence_keyboard
from furminder.services.date_parser import is_skip, is_valid_url, parse_date, parse_time
from furminder.services.permissions import can_manage_event
from furminder.services.recurrence import RecurrenceType

EDIT_FIELD = 1
EDIT_VALUE = 2

EDIT_DRAFT_KEY = "edit_draft"


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


def _week_of_month(value: date) -> int:
    return (value.day - 1) // 7 + 1


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return ConversationHandler.END
    if not context.args:
        await update.message.reply_text("/edit <номер>")
        return ConversationHandler.END

    local_id = int(context.args[0])
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    event = await db.get_event(chat_id, local_id)
    if not event:
        await update.message.reply_text(t("event_not_found", local_id=local_id))
        return ConversationHandler.END

    if not await can_manage_event(update, context, created_by=event["created_by"]):
        await update.message.reply_text(t("cannot_edit"))
        return ConversationHandler.END

    context.chat_data[EDIT_DRAFT_KEY] = {"local_id": local_id, "field": None}
    await update.message.reply_text(t("edit_choose_field"), reply_markup=edit_field_keyboard())
    return EDIT_FIELD


async def edit_field_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":", 1)[1]
    draft = context.chat_data.get(EDIT_DRAFT_KEY, {})
    draft["field"] = field

    prompts = {
        "title": t("ask_title"),
        "start_date": t("ask_start_date"),
        "end_date": t("ask_end_date"),
        "start_time": t("ask_start_time"),
        "end_time": t("ask_end_time"),
        "description": t("ask_description"),
        "image": t("ask_image"),
        "website": t("ask_website"),
    }
    if field == "recurrence":
        await query.edit_message_text(t("ask_recurrence"), reply_markup=recurrence_keyboard())
        return EDIT_VALUE

    await query.edit_message_text(prompts[field])
    return EDIT_VALUE


async def edit_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    draft = context.chat_data.get(EDIT_DRAFT_KEY)
    if not draft:
        return ConversationHandler.END

    local_id = draft["local_id"]
    field = draft["field"]
    updates: dict = {}

    if field == "title":
        updates["title"] = update.message.text.strip()
    elif field == "start_date":
        parsed = parse_date(update.message.text)
        if not parsed:
            await update.message.reply_text(t("invalid_date"))
            return EDIT_VALUE
        updates["start_date"] = parsed.isoformat()
    elif field == "end_date":
        if is_skip(update.message.text):
            updates["end_date"] = None
        else:
            parsed = parse_date(update.message.text)
            if not parsed:
                await update.message.reply_text(t("invalid_date"))
                return EDIT_VALUE
            updates["end_date"] = parsed.isoformat()
    elif field == "start_time":
        if is_skip(update.message.text):
            updates["start_time"] = None
        else:
            parsed = parse_time(update.message.text)
            if not parsed:
                await update.message.reply_text(t("invalid_time"))
                return EDIT_VALUE
            updates["start_time"] = parsed.strftime("%H:%M")
    elif field == "end_time":
        if is_skip(update.message.text):
            updates["end_time"] = None
        else:
            parsed = parse_time(update.message.text)
            if not parsed:
                await update.message.reply_text(t("invalid_time"))
                return EDIT_VALUE
            updates["end_time"] = parsed.strftime("%H:%M")
    elif field == "description":
        updates["description"] = None if is_skip(update.message.text) else update.message.text.strip()
    elif field == "image":
        if update.message.photo:
            updates["image_file_id"] = update.message.photo[-1].file_id
        elif is_skip(update.message.text or ""):
            updates["image_file_id"] = None
        else:
            await update.message.reply_text(t("ask_image"))
            return EDIT_VALUE
    elif field == "website":
        text = update.message.text.strip()
        if is_skip(text):
            updates["website_url"] = None
        elif is_valid_url(text):
            updates["website_url"] = text
        else:
            await update.message.reply_text(t("invalid_url"))
            return EDIT_VALUE

    await db.update_event(chat_id, local_id, updates)
    context.chat_data.pop(EDIT_DRAFT_KEY, None)
    await update.message.reply_text(t("edit_updated", local_id=local_id))
    return ConversationHandler.END


async def edit_recurrence_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.chat_data.get(EDIT_DRAFT_KEY)
    if not draft:
        return ConversationHandler.END

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    local_id = draft["local_id"]
    rec_type = query.data.split(":", 1)[1]

    if rec_type == "none":
        updates = {"recurrence": None}
    else:
        event = await db.get_event(chat_id, local_id)
        start = date.fromisoformat(event["start_date"])
        recurrence = {"enabled": True, "type": rec_type, "interval": 1}
        if rec_type == RecurrenceType.MONTHLY_WEEKDAY:
            recurrence["weekday"] = start.weekday()
            recurrence["week_of_month"] = _week_of_month(start)
        updates = {"recurrence": recurrence}

    await db.update_event(chat_id, local_id, updates)
    context.chat_data.pop(EDIT_DRAFT_KEY, None)
    await query.edit_message_text(t("edit_updated", local_id=local_id))
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.chat_data.pop(EDIT_DRAFT_KEY, None)
    await update.message.reply_text(t("cancelled"))
    return ConversationHandler.END
