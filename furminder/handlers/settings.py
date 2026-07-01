from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from furminder.db.repository import Database
from furminder.i18n import t
from furminder.keyboards.inline import settings_keyboard
from furminder.services.date_parser import parse_int_days, parse_time, parse_yes_no
from furminder.services.permissions import is_chat_admin

SETTINGS_MENU = 1
ADD_RULE_DAYS = 2
ADD_RULE_TIME = 3
ADD_RULE_SILENT = 4


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not _is_group(update):
        await update.message.reply_text(t("group_only"))
        return False
    if not await is_chat_admin(update, context):
        await update.message.reply_text(t("admin_only"))
        return False
    return True


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _require_admin(update, context):
        return ConversationHandler.END

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    chat_doc = await db.ensure_chat(chat_id, update.effective_chat.title)

    allow = t("settings_on") if chat_doc.get("allow_non_admin_add", True) else t("settings_off")
    silent = t("settings_silent_on") if chat_doc.get("default_silent", False) else t("settings_silent_off")
    text = "\n".join(
        [
            t("settings_header"),
            t("settings_allow_non_admin", value=allow),
            t("settings_timezone", timezone=chat_doc.get("timezone", "Europe/Moscow")),
            t("settings_default_silent", value=silent),
        ]
    )
    await update.message.reply_text(text, reply_markup=settings_keyboard())
    return SETTINGS_MENU


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not await is_chat_admin(update, context):
        await query.edit_message_text(t("admin_only"))
        return ConversationHandler.END

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    action = query.data.split(":", 1)[1]

    if action == "toggle_add":
        chat_doc = await db.get_chat(chat_id)
        new_value = not chat_doc.get("allow_non_admin_add", True)
        await db.update_chat_settings(chat_id, {"allow_non_admin_add": new_value})
        await query.edit_message_text(
            t("settings_allow_non_admin", value=t("settings_on") if new_value else t("settings_off"))
        )
        return ConversationHandler.END

    if action == "toggle_silent":
        chat_doc = await db.get_chat(chat_id)
        new_value = not chat_doc.get("default_silent", False)
        await db.update_chat_settings(chat_id, {"default_silent": new_value})
        await query.edit_message_text(
            t("settings_default_silent", value=t("settings_silent_on") if new_value else t("settings_silent_off"))
        )
        return ConversationHandler.END

    if action == "add_rule":
        context.chat_data["new_rule"] = {}
        await query.edit_message_text(t("ask_reminder_days"))
        return ADD_RULE_DAYS

    return ConversationHandler.END


async def add_rule_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    days = parse_int_days(update.message.text)
    if days is None:
        await update.message.reply_text(t("invalid_days"))
        return ADD_RULE_DAYS
    context.chat_data["new_rule"]["offset_days"] = days
    await update.message.reply_text(t("ask_reminder_time"))
    return ADD_RULE_TIME


async def add_rule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parsed = parse_time(update.message.text)
    if not parsed:
        await update.message.reply_text(t("invalid_time"))
        return ADD_RULE_TIME
    context.chat_data["new_rule"]["send_time"] = parsed.strftime("%H:%M")
    await update.message.reply_text(t("ask_reminder_silent"))
    return ADD_RULE_SILENT


async def add_rule_silent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = parse_yes_no(update.message.text)
    if value is None:
        await update.message.reply_text(t("ask_reminder_silent"))
        return ADD_RULE_SILENT

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    rule = context.chat_data.pop("new_rule", {})
    await db.add_reminder_rule(
        chat_id,
        offset_days=rule["offset_days"],
        send_time=rule["send_time"],
        silent=value,
    )
    await update.message.reply_text(
        t("reminder_added", days=rule["offset_days"], time=rule["send_time"])
    )
    return ConversationHandler.END


async def reminders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id
    rules = await db.list_reminder_rules(chat_id)
    if not rules:
        await update.message.reply_text(t("reminders_header") + "\n—")
        return

    lines = [t("reminders_header")]
    for idx, rule in enumerate(rules, start=1):
        silent = t("reminder_silent_suffix") if rule.get("silent") else ""
        disabled = t("reminder_disabled_suffix") if not rule.get("enabled", True) else ""
        lines.append(
            t(
                "reminder_rule_line",
                idx=idx,
                days=rule["offset_days"],
                time=rule["send_time"],
                silent=silent + disabled,
            )
        )
    await update.message.reply_text("\n".join(lines))
