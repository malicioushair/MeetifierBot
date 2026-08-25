from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .db import Calendar, Event

# Organizer reply keyboard labels
ORG_CALENDARS = "📅 Calendars"
ORG_NEW_CALENDAR = "➕ New calendar"
ORG_NEW_EVENT = "➕ New event"
ORG_EVENTS = "📋 Events"
ORG_INVITE = "🔗 Invite"
ORG_RESCHEDULE = "✏️ Reschedule"
ORG_CANCEL = "❌ Cancel event"
ORG_CONFIRMATIONS = "✅ Confirmations"
ORG_HELP = "❓ Help"

ORGANIZER_BUTTONS = {
    ORG_CALENDARS, ORG_NEW_CALENDAR, ORG_NEW_EVENT, ORG_EVENTS,
    ORG_INVITE, ORG_RESCHEDULE, ORG_CANCEL, ORG_CONFIRMATIONS, ORG_HELP,
}

# Participant reply keyboard labels
PAR_UPCOMING = "📅 Upcoming"
PAR_CONFIRM = "✅ Confirm"
PAR_SUBSCRIPTIONS = "📋 Subscriptions"
PAR_TIMEZONE = "🌍 Timezone"
PAR_REMINDERS = "⏰ Reminders"
PAR_MUTE = "🔇 Mute"
PAR_UNMUTE = "🔊 Unmute"
PAR_UNSUBSCRIBE = "🚫 Unsubscribe"
PAR_HELP = "❓ Help"

PARTICIPANT_BUTTONS = {
    PAR_UPCOMING, PAR_CONFIRM, PAR_SUBSCRIPTIONS, PAR_TIMEZONE, PAR_REMINDERS,
    PAR_MUTE, PAR_UNMUTE, PAR_UNSUBSCRIBE, PAR_HELP,
}


def organizer_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ORG_CALENDARS), KeyboardButton(text=ORG_NEW_CALENDAR)],
            [KeyboardButton(text=ORG_NEW_EVENT), KeyboardButton(text=ORG_EVENTS)],
            [KeyboardButton(text=ORG_INVITE), KeyboardButton(text=ORG_RESCHEDULE)],
            [KeyboardButton(text=ORG_CANCEL), KeyboardButton(text=ORG_CONFIRMATIONS)],
            [KeyboardButton(text=ORG_HELP)],
        ],
        resize_keyboard=True,
    )


def participant_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PAR_UPCOMING), KeyboardButton(text=PAR_CONFIRM)],
            [KeyboardButton(text=PAR_SUBSCRIPTIONS), KeyboardButton(text=PAR_TIMEZONE)],
            [KeyboardButton(text=PAR_REMINDERS), KeyboardButton(text=PAR_MUTE)],
            [KeyboardButton(text=PAR_UNMUTE), KeyboardButton(text=PAR_UNSUBSCRIBE)],
            [KeyboardButton(text=PAR_HELP)],
        ],
        resize_keyboard=True,
    )


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


def event_confirm_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Confirm attendance", callback_data=f"p_confirm:{event_id}")]]
    )


def upcoming_confirm_keyboard(events: list[Event], confirmed_ids: set[int]) -> InlineKeyboardMarkup:
    buttons = []
    for event in events:
        if event.id in confirmed_ids:
            continue
        buttons.append([InlineKeyboardButton(text=f"✅ {event.title}", callback_data=f"p_confirm:{event.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else InlineKeyboardMarkup(inline_keyboard=[])


def confirm_cancel_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Yes, cancel", callback_data=f"o_cancel_yes:{event_id}"),
            InlineKeyboardButton(text="No", callback_data="o_cancel_no"),
        ]]
    )
