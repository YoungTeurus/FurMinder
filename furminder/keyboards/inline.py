from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from furminder.i18n import t


def preset_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("preset_custom", locale), callback_data="preset:custom")],
            [InlineKeyboardButton(t("preset_birthday", locale), callback_data="preset:birthday")],
            [InlineKeyboardButton(t("preset_festival", locale), callback_data="preset:festival")],
            [InlineKeyboardButton(t("preset_con", locale), callback_data="preset:con")],
        ]
    )


def recurrence_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("recurrence_none", locale), callback_data="rec:none")],
            [InlineKeyboardButton(t("recurrence_yearly", locale), callback_data="rec:yearly")],
            [InlineKeyboardButton(t("recurrence_monthly", locale), callback_data="rec:monthly")],
            [InlineKeyboardButton(t("recurrence_weekly", locale), callback_data="rec:weekly")],
            [
                InlineKeyboardButton(
                    t("recurrence_monthly_weekday", locale),
                    callback_data="rec:monthly_weekday",
                )
            ],
        ]
    )


def confirm_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t("confirm_save", locale), callback_data="confirm:save"),
                InlineKeyboardButton(t("confirm_cancel", locale), callback_data="confirm:cancel"),
            ]
        ]
    )


def settings_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Добавление событий", callback_data="settings:toggle_add")],
            [InlineKeyboardButton("Тихие напоминания", callback_data="settings:toggle_silent")],
            [InlineKeyboardButton("Добавить правило", callback_data="settings:add_rule")],
        ]
    )


def edit_field_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("edit_field_title", locale), callback_data="edit:title")],
            [InlineKeyboardButton(t("edit_field_start_date", locale), callback_data="edit:start_date")],
            [InlineKeyboardButton(t("edit_field_end_date", locale), callback_data="edit:end_date")],
            [InlineKeyboardButton(t("edit_field_start_time", locale), callback_data="edit:start_time")],
            [InlineKeyboardButton(t("edit_field_end_time", locale), callback_data="edit:end_time")],
            [InlineKeyboardButton(t("edit_field_description", locale), callback_data="edit:description")],
            [InlineKeyboardButton(t("edit_field_image", locale), callback_data="edit:image")],
            [InlineKeyboardButton(t("edit_field_website", locale), callback_data="edit:website")],
            [InlineKeyboardButton(t("edit_field_recurrence", locale), callback_data="edit:recurrence")],
        ]
    )
