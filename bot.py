from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import get_settings
from furminder.db.repository import Database
from furminder.handlers.chat_member import my_chat_member_handler
from furminder.handlers.events_add import (
    CONFIRM,
    DESCRIPTION,
    END_DATE,
    END_TIME,
    IMAGE,
    PRESET,
    RECURRENCE,
    START_DATE,
    START_TIME,
    TITLE,
    WEBSITE,
    add_start,
    cancel_handler,
    confirm_chosen,
    description_received,
    end_date_received,
    end_time_received,
    image_received,
    preset_chosen,
    recurrence_chosen,
    start_date_received,
    start_time_received,
    title_received,
    website_received,
)
from furminder.handlers.events_edit import (
    EDIT_FIELD,
    EDIT_VALUE,
    edit_cancel,
    edit_field_chosen,
    edit_recurrence_chosen,
    edit_start,
    edit_value_received,
)
from furminder.handlers.events_list import delete_handler, event_handler, events_handler
from furminder.handlers.settings import (
    ADD_RULE_DAYS,
    ADD_RULE_SILENT,
    ADD_RULE_TIME,
    SETTINGS_MENU,
    add_rule_days,
    add_rule_silent,
    add_rule_time,
    reminders_handler,
    settings_callback,
    settings_handler,
)
from furminder.handlers.start import help_handler, start_handler
from furminder.services.reminders import process_due_reminders

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def reminder_job(context) -> None:
    db: Database = context.application.bot_data["db"]
    await process_due_reminders(db, context.application.bot)


def build_application() -> Application:
    settings = get_settings()
    db = Database.from_settings(settings)

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )
    application.bot_data["db"] = db

    add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            PRESET: [CallbackQueryHandler(preset_chosen, pattern=r"^preset:")],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_received)],
            START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_date_received)],
            END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_date_received)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time_received)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time_received)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)],
            IMAGE: [
                MessageHandler(filters.PHOTO, image_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_received),
            ],
            WEBSITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, website_received)],
            RECURRENCE: [CallbackQueryHandler(recurrence_chosen, pattern=r"^rec:")],
            CONFIRM: [CallbackQueryHandler(confirm_chosen, pattern=r"^confirm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
        name="add_event",
        persistent=False,
    )

    edit_conversation = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_FIELD: [CallbackQueryHandler(edit_field_chosen, pattern=r"^edit:")],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_received),
                MessageHandler(filters.PHOTO, edit_value_received),
                CallbackQueryHandler(edit_recurrence_chosen, pattern=r"^rec:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
        allow_reentry=True,
        name="edit_event",
        persistent=False,
    )

    settings_conversation = ConversationHandler(
        entry_points=[CommandHandler("settings", settings_handler)],
        states={
            SETTINGS_MENU: [CallbackQueryHandler(settings_callback, pattern=r"^settings:")],
            ADD_RULE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rule_days)],
            ADD_RULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rule_time)],
            ADD_RULE_SILENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_rule_silent)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
        name="settings",
        persistent=False,
    )

    application.add_handler(add_conversation)
    application.add_handler(edit_conversation)
    application.add_handler(settings_conversation)
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("events", events_handler))
    application.add_handler(CommandHandler("event", event_handler))
    application.add_handler(CommandHandler("delete", delete_handler))
    application.add_handler(CommandHandler("reminders", reminders_handler))
    application.add_handler(
        ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    application.job_queue.run_repeating(reminder_job, interval=60, first=10)

    async def post_init(app: Application) -> None:
        await db.ensure_indexes()
        logger.info("FurMinder started")

    application.post_init = post_init
    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    main()
