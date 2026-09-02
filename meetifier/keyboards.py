from __future__ import annotations

import calendar as cal_mod
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .db import Calendar, Event
from .i18n import LOCALES, LOCALE_LABELS, NAV_BTN, ORG_BTN, PAR_BTN, all_btn_texts, btn, t

ORGANIZER_BUTTONS = all_btn_texts(ORG_BTN)
PARTICIPANT_BUTTONS = all_btn_texts(PAR_BTN)
NAV_BUTTONS = all_btn_texts(NAV_BTN)
ORG_INPUT_BLOCKLIST = ORGANIZER_BUTTONS | NAV_BUTTONS
PAR_INPUT_BLOCKLIST = PARTICIPANT_BUTTONS | NAV_BUTTONS

FLOW_CANCEL_DATA = "flow:cancel"
FLOW_BACK_DATA = "flow:back"
DT_PREFIX = "o_dt"
DT_IGNORE = f"{DT_PREFIX}:ign"


def org_texts(*actions: str) -> set[str]:
    return all_btn_texts(ORG_BTN, *actions)


def par_texts(*actions: str) -> set[str]:
    return all_btn_texts(PAR_BTN, *actions)


def nav_texts(*actions: str) -> set[str]:
    return all_btn_texts(NAV_BTN, *actions)


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


def flow_nav_keyboard(locale: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text=btn(NAV_BTN, "back", locale)),
            KeyboardButton(text=btn(NAV_BTN, "cancel", locale)),
        ]],
        resize_keyboard=True,
    )


def attach_flow_nav(
    markup: InlineKeyboardMarkup,
    locale: str | None = None,
    *,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if show_back:
        row.append(InlineKeyboardButton(text=t(locale, "btn_back"), callback_data=FLOW_BACK_DATA))
    row.append(InlineKeyboardButton(text=t(locale, "btn_flow_cancel"), callback_data=FLOW_CANCEL_DATA))
    rows = list(markup.inline_keyboard) + [row]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def locale_keyboard(prefix: str = "set_locale") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LOCALE_LABELS[code], callback_data=f"{prefix}:{code}")]
            for code in LOCALES
        ]
    )


def event_range_keyboard(prefix: str, locale: str | None = None, *, with_nav: bool = True) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(locale, "btn_next_event"), callback_data=f"{prefix}:next"),
            InlineKeyboardButton(text=t(locale, "btn_this_week"), callback_data=f"{prefix}:week"),
        ]]
    )
    return attach_flow_nav(markup, locale, show_back=False) if with_nav else markup


def google_calendars_keyboard(
    count: int,
    locale: str | None = None,
    prefix: str = "o_gcal_pick",
    *,
    with_nav: bool = True,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=t(locale, "btn_google_cal", n=i + 1),
                callback_data=f"{prefix}:{i}",
            )]
            for i in range(min(count, 10))
        ]
    )
    return attach_flow_nav(markup, locale, show_back=show_back) if with_nav else markup


def confirm_google_adoption_keyboard(calendar_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(locale, "btn_notify_attendees"),
            callback_data=f"o_gadopt_yes:{calendar_id}",
        ),
    ]])
    return attach_flow_nav(markup, locale, show_back=True)


def calendars_keyboard(
    calendars: list[Calendar],
    prefix: str,
    locale: str | None = None,
    *,
    with_nav: bool = True,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.name, callback_data=f"{prefix}:{c.id}")] for c in calendars
        ]
    )
    return attach_flow_nav(markup, locale, show_back=show_back) if with_nav else markup


def event_series_keyboard(
    events: list[Event],
    prefix: str,
    locale: str | None = None,
    *,
    with_nav: bool = True,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=event.title, callback_data=f"{prefix}:{event.id}")]
            for event in events
        ]
    )
    return attach_flow_nav(markup, locale, show_back=show_back) if with_nav else markup


def occurrences_keyboard(
    items: list[tuple[str, int]],
    prefix: str,
    locale: str | None = None,
    *,
    with_nav: bool = True,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    """items: (button label, occurrence_id)."""
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"{prefix}:{occurrence_id}")]
            for label, occurrence_id in items
        ]
    )
    return attach_flow_nav(markup, locale, show_back=show_back) if with_nav else markup


def event_confirm_keyboard(occurrence_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text=t(locale, "btn_confirm_attendance"),
            callback_data=f"p_confirm:{occurrence_id}",
        )]]
    )


def recurrence_pattern_keyboard(locale: str | None = None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "btn_pattern_once"), callback_data="o_pat:once")],
        [InlineKeyboardButton(text=t(locale, "btn_pattern_weekly"), callback_data="o_pat:weekly")],
        [InlineKeyboardButton(text=t(locale, "btn_pattern_monthly"), callback_data="o_pat:monthly_nth")],
    ])
    return attach_flow_nav(markup, locale, show_back=True)


def weekdays_keyboard(selected: set[int], locale: str | None = None) -> InlineKeyboardMarkup:
    labels = [t(locale, f"wd_{i}") for i in range(7)]
    rows = []
    row = []
    for i, label in enumerate(labels):
        mark = "✓ " if i in selected else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"o_wd_tog:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(locale, "btn_weekdays_done"), callback_data="o_wd_done")])
    return attach_flow_nav(InlineKeyboardMarkup(inline_keyboard=rows), locale, show_back=True)


def monthly_pos_keyboard(locale: str | None = None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(locale, "btn_nth_1"), callback_data="o_nth:1"),
            InlineKeyboardButton(text=t(locale, "btn_nth_2"), callback_data="o_nth:2"),
        ],
        [
            InlineKeyboardButton(text=t(locale, "btn_nth_3"), callback_data="o_nth:3"),
            InlineKeyboardButton(text=t(locale, "btn_nth_4"), callback_data="o_nth:4"),
        ],
        [InlineKeyboardButton(text=t(locale, "btn_nth_last"), callback_data="o_nth:-1")],
    ])
    return attach_flow_nav(markup, locale, show_back=True)


def weekday_pick_keyboard(prefix: str, locale: str | None = None) -> InlineKeyboardMarkup:
    labels = [t(locale, f"wd_{i}") for i in range(7)]
    rows = []
    row = []
    for i, label in enumerate(labels):
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return attach_flow_nav(InlineKeyboardMarkup(inline_keyboard=rows), locale, show_back=True)


def edit_scope_keyboard(prefix: str, locale: str | None = None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "btn_scope_one"), callback_data=f"{prefix}:one")],
        [InlineKeyboardButton(text=t(locale, "btn_scope_following"), callback_data=f"{prefix}:following")],
    ])
    return attach_flow_nav(markup, locale, show_back=True)


def confirm_cancel_keyboard(occurrence_id: int, locale: str | None = None) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(locale, "btn_yes_cancel"), callback_data=f"o_cancel_yes:{occurrence_id}"),
        ]]
    )
    return attach_flow_nav(markup, locale, show_back=True)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def date_calendar_keyboard(
    year: int,
    month: int,
    locale: str | None = None,
    *,
    with_nav: bool = True,
) -> InlineKeyboardMarkup:
    """Month grid (Mon–Sun). Callbacks: o_dt:nav:YYYY-MM, o_dt:day:YYYY-MM-DD, o_dt:ign."""
    prev_y, prev_m = shift_month(year, month, -1)
    next_y, next_m = shift_month(year, month, 1)
    header = [
        InlineKeyboardButton(text="‹", callback_data=f"{DT_PREFIX}:nav:{prev_y:04d}-{prev_m:02d}"),
        InlineKeyboardButton(
            text=f"{t(locale, f'month_{month}')} {year}",
            callback_data=DT_IGNORE,
        ),
        InlineKeyboardButton(text="›", callback_data=f"{DT_PREFIX}:nav:{next_y:04d}-{next_m:02d}"),
    ]
    weekdays = [
        InlineKeyboardButton(text=t(locale, f"wd_{i}"), callback_data=DT_IGNORE)
        for i in range(7)
    ]
    rows: list[list[InlineKeyboardButton]] = [header, weekdays]
    # calendar.setfirstweekday(MONDAY); weeks are Mon..Sun
    weeks = cal_mod.Calendar(firstweekday=0).monthdayscalendar(year, month)
    today = date.today()
    for week in weeks:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data=DT_IGNORE))
                continue
            label = str(day)
            if date(year, month, day) == today:
                label = f"·{day}·"
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"{DT_PREFIX}:day:{year:04d}-{month:02d}-{day:02d}",
            ))
        rows.append(row)
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    return attach_flow_nav(markup, locale, show_back=True) if with_nav else markup


def hour_keyboard(locale: str | None = None, *, with_nav: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for hour in range(24):
        row.append(InlineKeyboardButton(
            text=f"{hour:02d}",
            callback_data=f"{DT_PREFIX}:hr:{hour}",
        ))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    return attach_flow_nav(markup, locale, show_back=True) if with_nav else markup


def minute_keyboard(locale: str | None = None, *, with_nav: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for minute in range(0, 60, 5):
        row.append(InlineKeyboardButton(
            text=f"{minute:02d}",
            callback_data=f"{DT_PREFIX}:mn:{minute}",
        ))
        if len(row) == 6:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    return attach_flow_nav(markup, locale, show_back=True) if with_nav else markup
