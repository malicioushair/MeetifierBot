from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .db import Calendar, Event
from .i18n import LOCALES, LOCALE_LABELS, ORG_BTN, PAR_BTN, all_btn_texts, btn, t

ORGANIZER_BUTTONS = all_btn_texts(ORG_BTN)
PARTICIPANT_BUTTONS = all_btn_texts(PAR_BTN)


def org_texts(*actions: str) -> set[str]:
    return all_btn_texts(ORG_BTN, *actions)


def par_texts(*actions: str) -> set[str]:
    return all_btn_texts(PAR_BTN, *actions)


def organizer_main_menu(locale: str | None = None) -> ReplyKeyboardMarkup:
    b = lambda action: KeyboardButton(text=btn(ORG_BTN, action, locale))
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("calendars"), b("new_calendar")],
            [b("new_event"), b("events")],
            [b("invite"), b("reschedule")],
            [b("cancel_event"), b("confirmations")],
            [b("google_link"), b("google_map")],
            [b("google_import"), b("google_sync")],
            [b("google_adopt")],
            [b("language"), b("help")],
        ],
        resize_keyboard=True,
    )


def participant_main_menu(locale: str | None = None) -> ReplyKeyboardMarkup:
    b = lambda action: KeyboardButton(text=btn(PAR_BTN, action, locale))
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("upcoming"), b("confirm")],
            [b("subscriptions"), b("timezone")],
            [b("reminders"), b("mute")],
            [b("unmute"), b("unsubscribe")],
            [b("language"), b("help")],
        ],
        resize_keyboard=True,
    )


def locale_keyboard(prefix: str = "set_locale") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LOCALE_LABELS[code], callback_data=f"{prefix}:{code}")]
            for code in LOCALES
        ]
    )


def event_range_keyboard(prefix: str, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(locale, "btn_next_event"), callback_data=f"{prefix}:next"),
            InlineKeyboardButton(text=t(locale, "btn_this_week"), callback_data=f"{prefix}:week"),
        ]]
    )


def google_calendars_keyboard(count: int, locale: str | None = None, prefix: str = "o_gcal_pick") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=t(locale, "btn_google_cal", n=i + 1),
                callback_data=f"{prefix}:{i}",
            )]
            for i in range(min(count, 10))
        ]
    )


def confirm_google_adoption_keyboard(calendar_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(locale, "btn_notify_attendees"),
            callback_data=f"o_gadopt_yes:{calendar_id}",
        ),
        InlineKeyboardButton(text=t(locale, "btn_cancel"), callback_data="o_gadopt_no"),
    ]])


def calendars_keyboard(calendars: list[Calendar], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.name, callback_data=f"{prefix}:{c.id}")] for c in calendars
        ]
    )


def events_keyboard(events: list[Event], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=e.title, callback_data=f"{prefix}:{e.id}")] for e in events
        ]
    )


def event_confirm_keyboard(event_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text=t(locale, "btn_confirm_attendance"),
            callback_data=f"p_confirm:{event_id}",
        )]]
    )


def upcoming_confirm_keyboard(events: list[Event], confirmed_ids: set[int]) -> InlineKeyboardMarkup:
    buttons = []
    for event in events:
        if event.id in confirmed_ids:
            continue
        buttons.append([InlineKeyboardButton(text=f"✅ {event.title}", callback_data=f"p_confirm:{event.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else InlineKeyboardMarkup(inline_keyboard=[])


def confirm_cancel_keyboard(event_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(locale, "btn_yes_cancel"), callback_data=f"o_cancel_yes:{event_id}"),
            InlineKeyboardButton(text=t(locale, "btn_no"), callback_data="o_cancel_no"),
        ]]
    )
