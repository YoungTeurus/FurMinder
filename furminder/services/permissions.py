from __future__ import annotations

from telegram import ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.ext import ContextTypes


async def is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return isinstance(member, (ChatMemberOwner, ChatMemberAdministrator))


async def can_manage_event(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    created_by: int,
) -> bool:
    user = update.effective_user
    if not user:
        return False
    if user.id == created_by:
        return True
    return await is_chat_admin(update, context)


async def can_add_event(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_doc: dict) -> bool:
    if chat_doc.get("allow_non_admin_add", True):
        return True
    return await is_chat_admin(update, context)
