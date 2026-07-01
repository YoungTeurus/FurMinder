from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from furminder.i18n import t


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_group(update):
        await update.message.reply_text(t("help_group"))
    else:
        await update.message.reply_text(t("help_private"))


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_handler(update, context)
