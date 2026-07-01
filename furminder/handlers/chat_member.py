from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from furminder.db.repository import Database
from furminder.i18n import t


async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return

    chat = my_chat_member.chat
    if chat.type not in {"group", "supergroup"}:
        return

    db: Database = context.application.bot_data["db"]
    new_status = my_chat_member.new_chat_member.status
    if new_status in {"member", "administrator"}:
        await db.ensure_chat(chat.id, chat.title)
        if update.effective_message:
            await update.effective_message.reply_text(t("bot_added"))
    elif new_status in {"left", "kicked"}:
        await db.deactivate_chat(chat.id)
