from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .config import Settings, format_timezone_offset
from .db import Calendar, Database, Event, EventOccurrence, GoogleCalendarLink, Subscription, User
from .i18n import LOCALES, normalize_locale, t
from .keyboards import (FLOW_BACK_DATA, FLOW_CANCEL_DATA, ORG_INPUT_BLOCKLIST, PAR_INPUT_BLOCKLIST,
                        calendars_keyboard, confirm_cancel_keyboard, confirm_google_adoption_keyboard,
                        edit_scope_keyboard, event_confirm_keyboard, event_range_keyboard, event_series_keyboard,
                        flow_nav_keyboard, google_calendars_keyboard, locale_keyboard, monthly_pos_keyboard,
                        nav_texts, occurrences_keyboard, org_texts, organizer_main_menu, par_texts,
                        participant_main_menu, recurrence_pattern_keyboard, weekday_pick_keyboard,
                        weekdays_keyboard)
from .flow import discard_flow
from .google_sync import (adopt_google_calendar, authorization_url, create_oauth_state, get_google_account,
                          google_enabled, import_google_calendar, link_google_calendar, list_google_calendars,
                          sync_changed_event, sync_created_events, sync_google_calendar)
from .recurrence import RecurrenceRule, parse_local_naive
from .service import (calendar_event_series, calendar_events, change_event, confirm_event, confirmations_for_event,
                      confirmed_occurrence_ids, create_calendar, create_events, display_time, event_occurrences,
                      get_user_locale, invitation_calendar, make_invitation, set_locale, set_reminders,
                      set_subscription_state, set_timezone, subscribe, upcoming_for_user_with_status)
from .states import (OrganizerCancelEvent, OrganizerConfirmations, OrganizerEvents, OrganizerGoogleAdopt,
                     OrganizerGoogleImport, OrganizerGoogleMap, OrganizerGoogleSync, OrganizerInvite,
                     OrganizerNewCalendar, OrganizerNewEvent, OrganizerReschedule, ParticipantConfirmPick,
                     ParticipantMute, ParticipantReminders, ParticipantTimezone, ParticipantUnmute,
                     ParticipantUnsubscribe, ParticipantUpcoming)


def participant_display_name(user) -> str:
    name = (user.full_name or "").strip()
    if user.username:
        return f"{name} (@{user.username})".strip() if name else f"@{user.username}"
    return name or f"User {user.id}"


def split_args(command: CommandObject, count_min: int, count_max: int | None = None, locale: str | None = None) -> list[str]:
    parts = [x.strip() for x in (command.args or "").split("|")]
    maximum = count_max or count_min
    if len(parts) < count_min or len(parts) > maximum or any(not x for x in parts):
        raise ValueError(t(locale, "wrong_command"))
    return parts


async def fetch_owned_calendars(session, telegram_id: int) -> list[Calendar]:
    return list((await session.scalars(
        select(Calendar).join(User).where(User.telegram_id == telegram_id)
    )).all())


async def fetch_future_series(session, calendar_id: int, range_mode: str = "future",
                              tz_offset_hours: int | str = 0) -> list[Event]:
    return await calendar_event_series(session, calendar_id, range_mode, tz_offset_hours)


async def fetch_subscribed_calendars(session, telegram_id: int) -> list[tuple[Calendar, Subscription]]:
    rows = await session.execute(
        select(Calendar, Subscription).join(Subscription).join(User).where(
            User.telegram_id == telegram_id, Subscription.active.is_(True))
    )
    return list(rows.tuples().all())


async def subscribed_calendars_with_series(session, telegram_id: int, range_mode: str,
                                           tz_offset_hours: int | str) -> list[Calendar]:
    calendars = []
    for calendar, _ in await fetch_subscribed_calendars(session, telegram_id):
        series = await calendar_event_series(session, calendar.id, range_mode, tz_offset_hours)
        if series:
            calendars.append(calendar)
    return calendars


async def subscribed_calendars_with_pending(session, telegram_id: int, default_tz: int | str) -> list[Calendar]:
    rows = await upcoming_for_user_with_status(session, telegram_id, "future", default_tz)
    pending_cal_ids = {c.id for occ, c, confirmed in rows if not confirmed}
    return [c for c, _ in await fetch_subscribed_calendars(session, telegram_id) if c.id in pending_cal_ids]


async def pending_series_for_calendar(session, telegram_id: int, calendar_id: int,
                                      default_tz: int | str) -> list[Event]:
    rows = await upcoming_for_user_with_status(session, telegram_id, "future", default_tz)
    seen: dict[int, Event] = {}
    for occ, calendar, confirmed in rows:
        if confirmed or calendar.id != calendar_id:
            continue
        if occ.event_id not in seen:
            seen[occ.event_id] = occ.event
    return list(seen.values())


def occurrence_button_items(occurrences: list[EventOccurrence], timezone_offset: int | str,
                            *, confirmed_ids: set[int] | None = None, mark_confirm: bool = False,
                            ) -> list[tuple[str, int]]:
    confirmed_ids = confirmed_ids or set()
    items = []
    for occurrence in occurrences:
        label = display_time(occurrence.start_utc, timezone_offset)
        if mark_confirm and occurrence.id not in confirmed_ids:
            label = f"✅ {label}"
        elif occurrence.id in confirmed_ids:
            label = f"{label} ✓"
        items.append((label, occurrence.id))
    return items


def format_organizer_events(occurrences: list[EventOccurrence], calendar: Calendar, range_mode: str, locale: str) -> str:
    if not occurrences:
        return t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming")
    return "\n".join(
        f"{occ.id}: {occ.event.title} — {display_time(occ.start_utc, calendar.timezone)} [{occ.status}]"
        for occ in occurrences
    )


def format_series_occurrences(event: Event, occurrences: list[EventOccurrence], calendar: Calendar,
                              range_mode: str, locale: str, *, with_confirm: bool = False,
                              confirmed_ids: set[int] | None = None) -> str:
    if not occurrences:
        return t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming")
    confirmed_ids = confirmed_ids or set()
    lines = [t(locale, "event_dates_header", title=event.title)]
    for occ in occurrences:
        status = ""
        if with_confirm:
            status = " ✅" if occ.id in confirmed_ids else ""
        lines.append(f"{occ.id}: {display_time(occ.start_utc, calendar.timezone)} [{occ.status}]{status}")
    return "\n".join(lines)


def format_participant_events(rows: list[tuple[EventOccurrence, Calendar, bool]], timezone_name: str, range_mode: str,
                              locale: str) -> str:
    if not rows:
        return t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming")
    lines = []
    for occurrence, calendar, confirmed in rows:
        status = " ✅" if confirmed else ""
        lines.append(
            f"{occurrence.event.title} — {display_time(occurrence.start_utc, timezone_name)} ({calendar.name}){status}"
        )
    return "\n".join(lines)


async def mirror_created_events(db: Database, settings: Settings, calendar_id: int,
                                occurrences: list[EventOccurrence]) -> None:
    async with db.sessions() as session:
        calendar = await session.get(Calendar, calendar_id)
    if calendar:
        await sync_created_events(db, settings, calendar, occurrences)


async def mirror_changed_event(db: Database, settings: Settings, occurrence: EventOccurrence,
                               *, cancelled: bool = False) -> None:
    async with db.sessions() as session:
        calendar = await session.get(Calendar, occurrence.event.calendar_id)
    if calendar:
        await sync_changed_event(db, settings, occurrence, calendar, cancelled=cancelled)


async def mirror_changed_events(db: Database, settings: Settings, occurrences: list[EventOccurrence],
                                *, cancelled: bool = False) -> None:
    for occurrence in occurrences:
        await mirror_changed_event(db, settings, occurrence, cancelled=cancelled)


async def send_organizer_onboarding(message: Message, locale: str, *, with_language_picker: bool = False) -> None:
    await message.answer(t(locale, "org.welcome"), reply_markup=organizer_main_menu(locale))
    await message.answer(t(locale, "org.onboarding"))
    if with_language_picker:
        await message.answer(t(locale, "choose_language"), reply_markup=locale_keyboard("o_locale"))


async def send_participant_onboarding(message: Message, locale: str, *, with_language_picker: bool = False) -> None:
    await message.answer(t(locale, "par.welcome"), reply_markup=participant_main_menu(locale))
    await message.answer(t(locale, "par.onboarding"))
    if with_language_picker:
        await message.answer(t(locale, "choose_language"), reply_markup=locale_keyboard("p_locale"))


def build_organizer_router(db: Database, settings: Settings, participant_bot: Bot) -> Router:
    router = Router(name="organizer")

    async def locale_for(telegram_id: int) -> str:
        async with db.sessions() as session:
            return await get_user_locale(session, telegram_id, settings.default_timezone)

    async def err(message: Message, locale: str, exc: Exception) -> None:
        await message.answer(t(locale, "error", error=exc), reply_markup=organizer_main_menu(locale))

    async def flow_err(message: Message, locale: str, exc: Exception, retry_prompt: str) -> None:
        """Show an error but keep the current FSM step so the user can retry."""
        await message.answer(t(locale, "error", error=exc))
        await message.answer(retry_prompt, reply_markup=flow_nav_keyboard(locale))

    async def restore_menu(target: Message | CallbackQuery, locale: str, text: str | None = None) -> None:
        msg = target.message if isinstance(target, CallbackQuery) else target
        await msg.answer(text or t(locale, "main_menu"), reply_markup=organizer_main_menu(locale))

    async def prompt_text(target: Message | CallbackQuery, text: str, locale: str) -> None:
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text)
            except Exception:
                await target.message.answer(text, reply_markup=flow_nav_keyboard(locale))
            else:
                await target.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
            await target.answer()
        else:
            await target.answer(text, reply_markup=flow_nav_keyboard(locale))

    async def prompt_inline(
        target: Message | CallbackQuery, text: str, markup, locale: str, *, with_reply_nav: bool = False,
    ) -> None:
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text, reply_markup=markup)
            except Exception:
                await target.message.answer(text, reply_markup=markup)
            if with_reply_nav:
                await target.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
            await target.answer()
        else:
            await target.answer(text, reply_markup=markup)
            await target.answer("\u2060", reply_markup=flow_nav_keyboard(locale))

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        locale = await locale_for(message.from_user.id)
        await send_organizer_onboarding(message, locale, with_language_picker=True)

    @router.message(Command("language"))
    @router.message(F.text.in_(org_texts("language")))
    async def language_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "choose_language"), reply_markup=locale_keyboard("o_locale"))

    @router.callback_query(F.data.startswith("o_locale:"))
    async def language_set(callback: CallbackQuery) -> None:
        code = normalize_locale(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            await set_locale(session, callback.from_user.id, code, settings.default_timezone)
        await callback.message.edit_text(t(code, "language_updated"))
        await send_organizer_onboarding(callback.message, code)
        await callback.answer()

    @router.message(Command("help"))
    @router.message(F.text.in_(org_texts("help")))
    async def help_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "org.onboarding"), reply_markup=organizer_main_menu(locale))
        await message.answer(t(locale, "org.help"))

    @router.message(Command("cancel"))
    async def cancel_command(message: Message, state: FSMContext, command: CommandObject) -> None:
        locale = await locale_for(message.from_user.id)
        if command.args:
            try:
                async with db.sessions() as session:
                    changed = await change_event(
                        session, message.from_user.id, int(command.args.strip()), cancel=True)
                    calendar = await session.get(Calendar, changed[0].event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, changed, "heading_event_cancelled")
                await mirror_changed_events(db, settings, changed, cancelled=True)
                await message.answer(
                    t(locale, "events_cancelled_count", count=len(changed)),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        if await state.get_state():
            await discard_flow(message, state, locale, role="org")
            return
        await message.answer(t(locale, "nothing_to_cancel_event"))

    @router.message(F.text.in_(nav_texts("cancel")))
    async def org_cancel_btn(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        if await state.get_state():
            await discard_flow(message, state, locale, role="org")
        else:
            await message.answer(t(locale, "nothing_to_cancel"), reply_markup=organizer_main_menu(locale))

    @router.callback_query(F.data == FLOW_CANCEL_DATA)
    async def org_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        if await state.get_state():
            await discard_flow(callback, state, locale, role="org")
        else:
            await callback.answer(t(locale, "nothing_to_cancel"), show_alert=True)

    async def org_flow_back(target: Message | CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(target.from_user.id)
        current = await state.get_state()
        data = await state.get_data()
        uid = target.from_user.id

        if not current:
            if isinstance(target, CallbackQuery):
                await target.answer(t(locale, "nothing_to_cancel"), show_alert=True)
            else:
                await target.answer(t(locale, "nothing_to_cancel"), reply_markup=organizer_main_menu(locale))
            return

        async def cancel() -> None:
            await discard_flow(target, state, locale, role="org")

        if current == OrganizerNewCalendar.name.state:
            await cancel()
        elif current == OrganizerNewCalendar.timezone.state:
            await state.set_state(OrganizerNewCalendar.name)
            await state.update_data(name=None)
            await prompt_text(target, t(locale, "enter_calendar_name"), locale)
        elif current == OrganizerNewEvent.calendar.state:
            await cancel()
        elif current == OrganizerNewEvent.title.state:
            await state.set_state(OrganizerNewEvent.calendar)
            await state.update_data(calendar_id=None, title=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar_event"),
                calendars_keyboard(rows, "o_newevent", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerNewEvent.start.state:
            await state.set_state(OrganizerNewEvent.title)
            await state.update_data(start=None)
            await prompt_text(target, t(locale, "enter_event_title"), locale)
        elif current == OrganizerNewEvent.duration.state:
            await state.set_state(OrganizerNewEvent.start)
            await state.update_data(duration=None)
            await prompt_text(target, t(locale, "enter_start_time"), locale)
        elif current == OrganizerNewEvent.pattern.state:
            await state.set_state(OrganizerNewEvent.duration)
            await state.update_data(pattern=None)
            await prompt_text(target, t(locale, "enter_duration"), locale)
        elif current == OrganizerNewEvent.weekdays.state:
            await state.set_state(OrganizerNewEvent.pattern)
            await state.update_data(weekdays=None)
            await prompt_inline(
                target, t(locale, "choose_pattern"), recurrence_pattern_keyboard(locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerNewEvent.interval.state:
            data_weekdays = set(data.get("weekdays") or [])
            await state.set_state(OrganizerNewEvent.weekdays)
            await state.update_data(interval=None)
            await prompt_inline(
                target, t(locale, "choose_weekdays"), weekdays_keyboard(data_weekdays, locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerNewEvent.monthly_pos.state:
            await state.set_state(OrganizerNewEvent.pattern)
            await state.update_data(monthly_pos=None)
            await prompt_inline(
                target, t(locale, "choose_pattern"), recurrence_pattern_keyboard(locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerNewEvent.monthly_weekday.state:
            await state.set_state(OrganizerNewEvent.monthly_pos)
            await state.update_data(monthly_weekday=None)
            await prompt_inline(
                target, t(locale, "choose_monthly_pos"), monthly_pos_keyboard(locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerNewEvent.count.state:
            if data.get("pattern") == "weekly":
                await state.set_state(OrganizerNewEvent.interval)
                await state.update_data(count=None)
                await prompt_text(target, t(locale, "enter_interval_weeks"), locale)
            else:
                await state.set_state(OrganizerNewEvent.monthly_weekday)
                await state.update_data(count=None)
                await prompt_inline(
                    target, t(locale, "choose_monthly_weekday"),
                    weekday_pick_keyboard("o_mwd", locale),
                    locale, with_reply_nav=isinstance(target, Message),
                )
        elif current == OrganizerReschedule.calendar.state:
            await cancel()
        elif current == OrganizerReschedule.series.state:
            await state.set_state(OrganizerReschedule.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar_reschedule"),
                calendars_keyboard(rows, "o_resched", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerReschedule.occurrence.state:
            calendar_id = data.get("calendar_id")
            await state.set_state(OrganizerReschedule.series)
            await state.update_data(series_id=None)
            async with db.sessions() as session:
                series = await fetch_future_series(session, int(calendar_id))
            await prompt_inline(
                target, t(locale, "choose_event"),
                event_series_keyboard(series, "o_resched_ser", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerReschedule.scope.state:
            calendar_id = data.get("calendar_id")
            series_id = data.get("series_id")
            await state.set_state(OrganizerReschedule.occurrence)
            await state.update_data(occurrence_id=None, scope=None)
            async with db.sessions() as session:
                calendar = await session.get(Calendar, int(calendar_id))
                rows = await event_occurrences(session, int(series_id))
            await prompt_inline(
                target, t(locale, "choose_occurrence"),
                occurrences_keyboard(occurrence_button_items(rows, calendar.timezone), "o_resched_occ", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerReschedule.new_start.state:
            await state.set_state(OrganizerReschedule.scope)
            await state.update_data(scope=None)
            await prompt_inline(
                target, t(locale, "choose_edit_scope"),
                edit_scope_keyboard("o_resched_scope", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerCancelEvent.calendar.state:
            await cancel()
        elif current == OrganizerCancelEvent.series.state:
            await state.set_state(OrganizerCancelEvent.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar"),
                calendars_keyboard(rows, "o_cancel", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerCancelEvent.occurrence.state:
            calendar_id = data.get("calendar_id")
            await state.set_state(OrganizerCancelEvent.series)
            await state.update_data(series_id=None)
            async with db.sessions() as session:
                series = await fetch_future_series(session, int(calendar_id))
            await prompt_inline(
                target, t(locale, "choose_event_cancel"),
                event_series_keyboard(series, "o_cancel_ser", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerCancelEvent.scope.state:
            calendar_id = data.get("calendar_id")
            series_id = data.get("series_id")
            await state.set_state(OrganizerCancelEvent.occurrence)
            await state.update_data(occurrence_id=None, scope=None)
            async with db.sessions() as session:
                calendar = await session.get(Calendar, int(calendar_id))
                rows = await event_occurrences(session, int(series_id))
            await prompt_inline(
                target, t(locale, "choose_occurrence_cancel"),
                occurrences_keyboard(occurrence_button_items(rows, calendar.timezone), "o_cancel_occ", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerCancelEvent.confirm.state:
            await state.set_state(OrganizerCancelEvent.scope)
            await prompt_inline(
                target, t(locale, "choose_edit_scope"),
                edit_scope_keyboard("o_cancel_scope", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerInvite.calendar.state:
            await cancel()
        elif current == OrganizerEvents.range_pick.state:
            await cancel()
        elif current == OrganizerEvents.calendar.state:
            await state.set_state(OrganizerEvents.range_pick)
            await state.update_data(range_mode=None)
            await prompt_inline(
                target, t(locale, "what_to_see"),
                event_range_keyboard("o_evt_rng", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerEvents.series.state:
            range_mode = data.get("range_mode") or "week"
            await state.set_state(OrganizerEvents.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar"),
                calendars_keyboard(rows, f"o_evt_cal:{range_mode}", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerConfirmations.calendar.state:
            await cancel()
        elif current == OrganizerConfirmations.series.state:
            await state.set_state(OrganizerConfirmations.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar_confirmations"),
                calendars_keyboard(rows, "o_conf_cal", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerConfirmations.occurrence.state:
            calendar_id = data.get("calendar_id")
            await state.set_state(OrganizerConfirmations.series)
            await state.update_data(series_id=None)
            async with db.sessions() as session:
                series = await fetch_future_series(session, int(calendar_id))
            await prompt_inline(
                target, t(locale, "choose_event"),
                event_series_keyboard(series, "o_conf_ser", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerGoogleMap.calendar.state:
            await cancel()
        elif current == OrganizerGoogleMap.google_cal.state:
            await state.set_state(OrganizerGoogleMap.calendar)
            await state.update_data(meetifier_calendar_id=None, google_calendars=None)
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, uid)
            await prompt_inline(
                target, t(locale, "choose_calendar_map"),
                calendars_keyboard(rows, "o_gmap_cal", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == OrganizerGoogleImport.google_cal.state:
            await cancel()
        elif current == OrganizerGoogleSync.calendar.state:
            await cancel()
        elif current == OrganizerGoogleAdopt.calendar.state:
            await cancel()
        elif current == OrganizerGoogleAdopt.confirm.state:
            calendars = await fetch_linked_calendars(uid)
            if len(calendars) > 1:
                await state.set_state(OrganizerGoogleAdopt.calendar)
                await state.update_data(calendar_id=None)
                await prompt_inline(
                    target, t(locale, "choose_calendar_adopt"),
                    calendars_keyboard(calendars, "o_gadopt", locale, show_back=False),
                    locale, with_reply_nav=isinstance(target, Message),
                )
            else:
                await cancel()
        else:
            await cancel()

    @router.message(F.text.in_(nav_texts("back")))
    async def org_back_btn(message: Message, state: FSMContext) -> None:
        await org_flow_back(message, state)

    @router.callback_query(F.data == FLOW_BACK_DATA)
    async def org_back_cb(callback: CallbackQuery, state: FSMContext) -> None:
        await org_flow_back(callback, state)

    async def reply_calendars(message: Message, locale: str) -> None:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        await message.answer(
            "\n".join(f"{x.id}: {x.name} [{format_timezone_offset(x.timezone)}]" for x in rows) or t(locale, "no_calendars"),
            reply_markup=organizer_main_menu(locale),
        )

    @router.message(Command("calendars"))
    @router.message(F.text.in_(org_texts("calendars")))
    async def calendars(message: Message, state: FSMContext) -> None:
        await state.clear()
        await reply_calendars(message, await locale_for(message.from_user.id))

    @router.message(Command("newcalendar"))
    @router.message(F.text.in_(org_texts("new_calendar")))
    async def new_calendar_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                name, tz = split_args(command, 2, locale=locale)
                async with db.sessions() as session:
                    calendar = await create_calendar(session, message.from_user.id, name, tz, settings.default_timezone)
                await message.answer(
                    t(locale, "calendar_created", name=calendar.name, id=calendar.id),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await state.set_state(OrganizerNewCalendar.name)
        await message.answer(t(locale, "enter_calendar_name"), reply_markup=flow_nav_keyboard(locale))

    @router.message(OrganizerNewCalendar.name, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_calendar_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name=message.text.strip())
        await state.set_state(OrganizerNewCalendar.timezone)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_timezone"), reply_markup=flow_nav_keyboard(locale))

    @router.message(OrganizerNewCalendar.timezone, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_calendar_timezone(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                calendar = await create_calendar(
                    session, message.from_user.id, data["name"], message.text.strip(), settings.default_timezone)
            await state.clear()
            await message.answer(
                t(locale, "calendar_created", name=calendar.name, id=calendar.id),
                reply_markup=organizer_main_menu(locale),
            )
        except (ValueError, PermissionError) as exc:
            await flow_err(message, locale, exc, t(locale, "enter_timezone"))

    async def pick_calendar(
        message: Message, prefix: str, prompt_key: str, locale: str, *, show_back: bool = False,
    ) -> bool:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        if not rows:
            await message.answer(t(locale, "no_calendars_create"), reply_markup=organizer_main_menu(locale))
            return False
        await prompt_inline(
            message, t(locale, prompt_key),
            calendars_keyboard(rows, prefix, locale, show_back=show_back),
            locale, with_reply_nav=True,
        )
        return True

    @router.message(Command("events"))
    @router.message(F.text.in_(org_texts("events")))
    async def events_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            parts = command.args.split()
            try:
                calendar_id = int(parts[0])
                range_mode = parts[1].lower() if len(parts) > 1 else "week"
                if range_mode not in {"next", "week"}:
                    raise ValueError("Range must be 'next' or 'week'")
                async with db.sessions() as session:
                    calendar = await session.scalar(select(Calendar).join(User).where(
                        Calendar.id == calendar_id, User.telegram_id == message.from_user.id))
                    if not calendar:
                        raise PermissionError(t(locale, "calendar_not_owned"))
                    rows = await calendar_events(session, calendar.id, range_mode, calendar.timezone)
                await message.answer(
                    format_organizer_events(rows, calendar, range_mode, locale),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.set_state(OrganizerEvents.range_pick)
        await prompt_inline(
            message, t(locale, "what_to_see"), event_range_keyboard("o_evt_rng", locale), locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("o_evt_rng:"))
    async def events_range_pick(callback: CallbackQuery, state: FSMContext) -> None:
        range_mode = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        await state.update_data(range_mode=range_mode)
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, callback.from_user.id)
            if not rows:
                await state.clear()
                await callback.message.edit_text(t(locale, "no_calendars_create"))
                await restore_menu(callback, locale)
                await callback.answer()
                return
            if len(rows) == 1:
                calendar = rows[0]
                await state.update_data(calendar_id=calendar.id)
                series = await fetch_future_series(session, calendar.id, range_mode, calendar.timezone)
                if not series:
                    await state.clear()
                    await callback.message.edit_text(
                        t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming"))
                    await restore_menu(callback, locale)
                    await callback.answer()
                    return
                await state.set_state(OrganizerEvents.series)
                await callback.message.edit_text(
                    t(locale, "choose_event"),
                    reply_markup=event_series_keyboard(series, f"o_evt_ser:{range_mode}", locale, show_back=False),
                )
                await callback.answer()
                return
        await state.set_state(OrganizerEvents.calendar)
        await callback.message.edit_text(
            t(locale, "choose_calendar"),
            reply_markup=calendars_keyboard(rows, f"o_evt_cal:{range_mode}", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_evt_cal:"))
    async def events_calendar_pick(callback: CallbackQuery, state: FSMContext) -> None:
        _, range_mode, calendar_id = callback.data.split(":", 2)
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(calendar_id))
            series = await fetch_future_series(session, calendar.id, range_mode, calendar.timezone)
        if not series:
            await state.clear()
            await callback.message.edit_text(
                t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(range_mode=range_mode, calendar_id=calendar.id)
        await state.set_state(OrganizerEvents.series)
        await callback.message.edit_text(
            t(locale, "choose_event"),
            reply_markup=event_series_keyboard(series, f"o_evt_ser:{range_mode}", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_evt_ser:"))
    async def events_series_pick(callback: CallbackQuery, state: FSMContext) -> None:
        _, range_mode, series_id = callback.data.split(":", 2)
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            event = await session.get(Event, int(series_id))
            calendar = await session.get(Calendar, event.calendar_id)
            rows = await event_occurrences(session, event.id, range_mode, calendar.timezone)
        await state.clear()
        await callback.message.edit_text(format_series_occurrences(event, rows, calendar, range_mode, locale))
        await restore_menu(callback, locale)
        await callback.answer()

    @router.message(F.text.in_(org_texts("google_link")))
    async def google_link_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if not google_enabled(settings):
            await message.answer(t(locale, "google_not_configured"), reply_markup=organizer_main_menu(locale))
            return
        async with db.sessions() as session:
            token = await create_oauth_state(session, message.from_user.id)
        await message.answer(
            t(locale, "google_open_link", url=authorization_url(settings, token)),
            reply_markup=organizer_main_menu(locale),
        )

    @router.message(F.text.in_(org_texts("google_map")))
    async def google_map_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if not google_enabled(settings):
            await message.answer(t(locale, "google_not_configured"), reply_markup=organizer_main_menu(locale))
            return
        async with db.sessions() as session:
            account = await get_google_account(session, message.from_user.id)
        if not account:
            await message.answer(t(locale, "google_link_first"), reply_markup=organizer_main_menu(locale))
            return
        await state.set_state(OrganizerGoogleMap.calendar)
        await pick_calendar(message, "o_gmap_cal", "choose_calendar_map", locale)

    @router.callback_query(F.data.startswith("o_gmap_cal:"))
    async def google_map_pick_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            account = await get_google_account(session, callback.from_user.id)
            if not account:
                await state.clear()
                await callback.message.edit_text(t(locale, "google_link_first"))
                await restore_menu(callback, locale)
                await callback.answer()
                return
            try:
                google_cals = await list_google_calendars(session, settings, account)
            except Exception as exc:
                await state.clear()
                await callback.message.edit_text(t(locale, "google_load_failed", error=exc))
                await restore_menu(callback, locale)
                await callback.answer()
                return
        if not google_cals:
            await state.clear()
            await callback.message.edit_text(t(locale, "google_none_found"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(meetifier_calendar_id=calendar_id, google_calendars=google_cals)
        await state.set_state(OrganizerGoogleMap.google_cal)
        await callback.message.edit_text(
            t(locale, "google_choose"),
            reply_markup=google_calendars_keyboard(len(google_cals), locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_gcal_pick:"))
    async def google_map_pick_google_cal(callback: CallbackQuery, state: FSMContext) -> None:
        index = int(callback.data.split(":", 1)[1])
        data = await state.get_data()
        locale = await locale_for(callback.from_user.id)
        calendars_list = data.get("google_calendars") or []
        calendar_id = data.get("meetifier_calendar_id")
        if calendar_id is None or index >= len(calendars_list):
            await state.clear()
            await callback.message.edit_text(t(locale, "google_map_expired"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        chosen = calendars_list[index]
        try:
            async with db.sessions() as session:
                await link_google_calendar(
                    session, callback.from_user.id, int(calendar_id),
                    chosen["id"], chosen["name"])
            result = await sync_google_calendar(db, settings, int(calendar_id), force_full=True)
            await state.clear()
            await callback.message.edit_text(
                t(locale, "google_mapped", name=chosen["name"], created=result.created, updated=result.updated))
            await restore_menu(callback, locale)
        except Exception as exc:
            await callback.message.answer(t(locale, "error", error=exc))
            await callback.message.answer(
                t(locale, "google_choose"),
                reply_markup=google_calendars_keyboard(len(calendars_list), locale),
            )
        await callback.answer()

    @router.message(Command("googleimport"))
    @router.message(F.text.in_(org_texts("google_import")))
    async def google_import_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if not google_enabled(settings):
            await message.answer(t(locale, "google_not_configured"), reply_markup=organizer_main_menu(locale))
            return
        async with db.sessions() as session:
            account = await get_google_account(session, message.from_user.id)
            if not account:
                await message.answer(t(locale, "google_link_first"), reply_markup=organizer_main_menu(locale))
                return
            try:
                google_cals = await list_google_calendars(session, settings, account)
            except Exception as exc:
                await message.answer(
                    t(locale, "google_load_failed", error=exc), reply_markup=organizer_main_menu(locale))
                return
        if not google_cals:
            await message.answer(t(locale, "google_none_writable"), reply_markup=organizer_main_menu(locale))
            return
        await state.update_data(google_import_calendars=google_cals)
        await state.set_state(OrganizerGoogleImport.google_cal)
        names = "\n".join(f"{i + 1}. {calendar['name']}" for i, calendar in enumerate(google_cals[:10]))
        await prompt_inline(
            message, t(locale, "google_choose_import", names=names),
            google_calendars_keyboard(len(google_cals), locale, "o_gimport_pick", show_back=False),
            locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("o_gimport_pick:"))
    async def google_import_pick(callback: CallbackQuery, state: FSMContext) -> None:
        index = int(callback.data.split(":", 1)[1])
        data = await state.get_data()
        locale = await locale_for(callback.from_user.id)
        google_cals = data.get("google_import_calendars") or []
        if index >= len(google_cals):
            await state.clear()
            await callback.message.edit_text(t(locale, "google_import_expired"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        chosen = google_cals[index]
        try:
            calendar, result = await import_google_calendar(
                db, settings, callback.from_user.id, chosen)
            await state.clear()
            await callback.message.edit_text(
                t(locale, "google_imported", name=chosen["name"], id=calendar.id,
                  created=result.created, updated=result.updated, cancelled=result.cancelled)
            )
            await restore_menu(callback, locale)
        except Exception as exc:
            names = "\n".join(f"{i + 1}. {calendar['name']}" for i, calendar in enumerate(google_cals[:10]))
            await callback.message.answer(t(locale, "google_import_failed", error=exc))
            await callback.message.answer(
                t(locale, "google_choose_import", names=names),
                reply_markup=google_calendars_keyboard(len(google_cals), locale, "o_gimport_pick"),
            )
        await callback.answer()

    async def fetch_linked_calendars(telegram_id: int) -> list[Calendar]:
        async with db.sessions() as session:
            return list((await session.scalars(
                select(Calendar).join(User).join(GoogleCalendarLink).where(User.telegram_id == telegram_id)
            )).all())

    @router.message(Command("googlesync"))
    @router.message(F.text.in_(org_texts("google_sync")))
    async def google_sync_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        calendars = await fetch_linked_calendars(message.from_user.id)
        if not calendars:
            await message.answer(t(locale, "google_no_linked"), reply_markup=organizer_main_menu(locale))
            return
        if len(calendars) == 1:
            try:
                result = await sync_google_calendar(db, settings, calendars[0].id)
                await message.answer(
                    t(locale, "google_sync_complete", created=result.created, updated=result.updated,
                      cancelled=result.cancelled),
                    reply_markup=organizer_main_menu(locale),
                )
            except Exception as exc:
                await message.answer(
                    t(locale, "google_sync_failed", error=exc), reply_markup=organizer_main_menu(locale))
            return
        await state.set_state(OrganizerGoogleSync.calendar)
        await prompt_inline(
            message, t(locale, "choose_calendar_sync"),
            calendars_keyboard(calendars, "o_gsync", locale, show_back=False),
            locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("o_gsync:"))
    async def google_sync_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        calendars = await fetch_linked_calendars(callback.from_user.id)
        owned = {calendar.id for calendar in calendars}
        if calendar_id not in owned:
            await callback.message.answer(t(locale, "calendar_not_owned"))
            await callback.message.answer(
                t(locale, "choose_calendar_sync"),
                reply_markup=calendars_keyboard(calendars, "o_gsync", locale),
            )
        else:
            try:
                result = await sync_google_calendar(db, settings, calendar_id)
                await state.clear()
                await callback.message.edit_text(
                    t(locale, "google_sync_complete", created=result.created, updated=result.updated,
                      cancelled=result.cancelled))
                await restore_menu(callback, locale)
            except Exception as exc:
                await callback.message.answer(t(locale, "google_sync_failed", error=exc))
                await callback.message.answer(
                    t(locale, "choose_calendar_sync"),
                    reply_markup=calendars_keyboard(calendars, "o_gsync", locale),
                )
        await callback.answer()

    @router.message(Command("googleinvite"))
    @router.message(F.text.in_(org_texts("google_adopt")))
    async def google_adopt_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        calendars = await fetch_linked_calendars(message.from_user.id)
        if not calendars:
            await message.answer(t(locale, "google_adopt_first"), reply_markup=organizer_main_menu(locale))
            return
        if len(calendars) == 1:
            calendar = calendars[0]
            await state.set_state(OrganizerGoogleAdopt.confirm)
            await state.update_data(calendar_id=calendar.id)
            await prompt_inline(
                message, t(locale, "google_adopt_confirm", name=calendar.name),
                confirm_google_adoption_keyboard(calendar.id, locale),
                locale, with_reply_nav=True,
            )
            return
        await state.set_state(OrganizerGoogleAdopt.calendar)
        await prompt_inline(
            message, t(locale, "choose_calendar_adopt"),
            calendars_keyboard(calendars, "o_gadopt", locale, show_back=False),
            locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("o_gadopt:"))
    async def google_adopt_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        owned = {calendar.id: calendar for calendar in await fetch_linked_calendars(callback.from_user.id)}
        calendar = owned.get(calendar_id)
        if not calendar:
            await state.clear()
            await callback.message.edit_text(t(locale, "calendar_not_owned"))
            await restore_menu(callback, locale)
        else:
            await state.set_state(OrganizerGoogleAdopt.confirm)
            await state.update_data(calendar_id=calendar_id)
            await callback.message.edit_text(
                t(locale, "google_adopt_confirm_short", name=calendar.name),
                reply_markup=confirm_google_adoption_keyboard(calendar_id, locale),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_gadopt_yes:"))
    async def google_adopt_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        try:
            updated, total, invitation_url = await adopt_google_calendar(
                db, settings, callback.from_user.id, calendar_id, settings.participant_bot_username)
            await state.clear()
            await callback.message.edit_text(
                t(locale, "google_adopt_done", updated=updated, total=total, url=invitation_url)
            )
            await restore_menu(callback, locale)
        except Exception as exc:
            owned = {c.id: c for c in await fetch_linked_calendars(callback.from_user.id)}
            calendar = owned.get(calendar_id)
            await callback.message.answer(t(locale, "google_adopt_failed", error=exc))
            if calendar:
                await callback.message.answer(
                    t(locale, "google_adopt_confirm_short", name=calendar.name),
                    reply_markup=confirm_google_adoption_keyboard(calendar_id, locale),
                )
        await callback.answer()

    @router.callback_query(F.data == "o_gadopt_no")
    async def google_adopt_cancel(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        await discard_flow(callback, state, locale, role="org")

    @router.message(Command("invite"))
    @router.message(F.text.in_(org_texts("invite")))
    async def invite_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                async with db.sessions() as session:
                    invitation = await make_invitation(session, message.from_user.id, int(command.args.strip()))
                url = f"https://t.me/{settings.participant_bot_username}?start={invitation.token}"
                await message.answer(t(locale, "share_invite", url=url), reply_markup=organizer_main_menu(locale))
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await state.set_state(OrganizerInvite.calendar)
        await pick_calendar(message, "o_invite", "choose_calendar_invite", locale)

    @router.callback_query(F.data.startswith("o_invite:"))
    async def invite_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        try:
            async with db.sessions() as session:
                invitation = await make_invitation(session, callback.from_user.id, calendar_id)
            url = f"https://t.me/{settings.participant_bot_username}?start={invitation.token}"
            await state.clear()
            await callback.message.edit_text(t(locale, "share_invite", url=url))
            await restore_menu(callback, locale)
        except (ValueError, PermissionError) as exc:
            async with db.sessions() as session:
                rows = await fetch_owned_calendars(session, callback.from_user.id)
            await callback.message.answer(t(locale, "error", error=exc))
            await callback.message.answer(
                t(locale, "choose_calendar_invite"),
                reply_markup=calendars_keyboard(rows, "o_invite", locale),
            )
        await callback.answer()

    @router.message(Command("newevent"))
    @router.message(F.text.in_(org_texts("new_event")))
    async def new_event_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                parts = split_args(command, 4, 5, locale=locale)
                calendar_id, title, start, duration = parts[:4]
                weeks = int(parts[4]) if len(parts) == 5 else 1
                async with db.sessions() as session:
                    occurrences = await create_events(
                        session, message.from_user.id, int(calendar_id), title, start, int(duration), weeks)
                    calendar = await session.get(Calendar, int(calendar_id))
                    await notify_subscribers(session, participant_bot, calendar, occurrences, "heading_new_event")
                await mirror_created_events(db, settings, int(calendar_id), occurrences)
                await message.answer(
                    t(locale, "events_created", count=len(occurrences), ids=", ".join(str(o.id) for o in occurrences)),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await state.set_state(OrganizerNewEvent.calendar)
        await pick_calendar(message, "o_newevent", "choose_calendar_event", locale)

    @router.callback_query(F.data.startswith("o_newevent:"))
    async def new_event_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerNewEvent.title)
        await callback.message.edit_text(t(locale, "enter_event_title"))
        await callback.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
        await callback.answer()

    @router.message(OrganizerNewEvent.title, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_event_title(message: Message, state: FSMContext) -> None:
        await state.update_data(title=message.text.strip())
        await state.set_state(OrganizerNewEvent.start)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_start_time"), reply_markup=flow_nav_keyboard(locale))

    @router.message(OrganizerNewEvent.start, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_event_start_time(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        try:
            parse_local_naive(message.text.strip())
        except ValueError as exc:
            await flow_err(message, locale, exc, t(locale, "enter_start_time"))
            return
        await state.update_data(start=message.text.strip())
        await state.set_state(OrganizerNewEvent.duration)
        await message.answer(t(locale, "enter_duration"), reply_markup=flow_nav_keyboard(locale))

    @router.message(OrganizerNewEvent.duration, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_event_duration(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        try:
            duration = int(message.text.strip())
            if not 1 <= duration <= 10080:
                raise ValueError("Duration must be 1..10080 minutes")
        except ValueError as exc:
            await flow_err(message, locale, exc, t(locale, "enter_duration"))
            return
        await state.update_data(duration=str(duration))
        await state.set_state(OrganizerNewEvent.pattern)
        await prompt_inline(
            message, t(locale, "choose_pattern"), recurrence_pattern_keyboard(locale), locale, with_reply_nav=True,
        )

    async def finish_new_event(message_or_cb, state: FSMContext, rule: RecurrenceRule, locale: str) -> None:
        data = await state.get_data()
        target_message = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
        try:
            async with db.sessions() as session:
                occurrences = await create_events(
                    session, message_or_cb.from_user.id, data["calendar_id"], data["title"],
                    data["start"], int(data["duration"]), rule=rule)
                calendar = await session.get(Calendar, data["calendar_id"])
                await notify_subscribers(session, participant_bot, calendar, occurrences, "heading_new_event")
            await mirror_created_events(db, settings, data["calendar_id"], occurrences)
            text = t(
                locale, "events_created", count=len(occurrences),
                ids=", ".join(str(o.id) for o in occurrences),
            )
            await state.clear()
            if isinstance(message_or_cb, CallbackQuery):
                await message_or_cb.message.edit_text(text)
                await restore_menu(message_or_cb, locale)
                await message_or_cb.answer()
            else:
                await target_message.answer(text, reply_markup=organizer_main_menu(locale))
        except (ValueError, PermissionError) as exc:
            current = await state.get_state()
            if current == OrganizerNewEvent.count.state:
                retry = t(locale, "enter_occurrence_count")
            elif current == OrganizerNewEvent.pattern.state or data.get("pattern") == "once":
                retry = t(locale, "choose_pattern")
            else:
                retry = t(locale, "try_again")
            if isinstance(message_or_cb, CallbackQuery):
                await message_or_cb.message.answer(t(locale, "error", error=exc))
                if data.get("pattern") == "once":
                    await message_or_cb.message.answer(
                        t(locale, "choose_pattern"), reply_markup=recurrence_pattern_keyboard(locale))
                else:
                    await message_or_cb.message.answer(retry, reply_markup=flow_nav_keyboard(locale))
                await message_or_cb.answer()
            else:
                await flow_err(target_message, locale, exc, retry)

    @router.callback_query(F.data.startswith("o_pat:"))
    async def new_event_pattern(callback: CallbackQuery, state: FSMContext) -> None:
        pattern = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        await state.update_data(pattern=pattern)
        if pattern == "once":
            await finish_new_event(callback, state, RecurrenceRule.once(), locale)
            return
        if pattern == "weekly":
            weekday = parse_local_naive(data["start"]).weekday()
            await state.update_data(weekdays=[weekday])
            await state.set_state(OrganizerNewEvent.weekdays)
            await callback.message.edit_text(
                t(locale, "choose_weekdays"),
                reply_markup=weekdays_keyboard({weekday}, locale),
            )
            await callback.answer()
            return
        await state.set_state(OrganizerNewEvent.monthly_pos)
        await callback.message.edit_text(
            t(locale, "choose_monthly_pos"), reply_markup=monthly_pos_keyboard(locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_wd_tog:"))
    async def new_event_weekday_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        day = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        selected = set(data.get("weekdays") or [])
        if day in selected:
            selected.remove(day)
        else:
            selected.add(day)
        await state.update_data(weekdays=sorted(selected))
        await callback.message.edit_reply_markup(reply_markup=weekdays_keyboard(selected, locale))
        await callback.answer()

    @router.callback_query(F.data == "o_wd_done")
    async def new_event_weekdays_done(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        if not data.get("weekdays"):
            await callback.answer(t(locale, "choose_weekdays"), show_alert=True)
            return
        await state.set_state(OrganizerNewEvent.interval)
        await callback.message.edit_text(t(locale, "enter_interval_weeks"))
        await callback.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
        await callback.answer()

    @router.message(OrganizerNewEvent.interval, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_event_interval(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        try:
            interval = int(message.text.strip())
            if not 1 <= interval <= 12:
                raise ValueError("Interval must be 1..12")
        except ValueError as exc:
            await flow_err(message, locale, exc, t(locale, "enter_interval_weeks"))
            return
        await state.update_data(interval=interval)
        await state.set_state(OrganizerNewEvent.count)
        await message.answer(t(locale, "enter_occurrence_count"), reply_markup=flow_nav_keyboard(locale))

    @router.callback_query(F.data.startswith("o_nth:"))
    async def new_event_monthly_pos(callback: CallbackQuery, state: FSMContext) -> None:
        pos = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(monthly_pos=pos)
        await state.set_state(OrganizerNewEvent.monthly_weekday)
        await callback.message.edit_text(
            t(locale, "choose_monthly_weekday"),
            reply_markup=weekday_pick_keyboard("o_mwd", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_mwd:"))
    async def new_event_monthly_weekday(callback: CallbackQuery, state: FSMContext) -> None:
        weekday = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(monthly_weekday=weekday)
        await state.set_state(OrganizerNewEvent.count)
        await callback.message.edit_text(t(locale, "enter_occurrence_count"))
        await callback.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
        await callback.answer()

    @router.message(OrganizerNewEvent.count, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def new_event_count(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            count = int(message.text.strip())
            if data.get("pattern") == "weekly":
                rule = RecurrenceRule.weekly(
                    weekdays=list(data["weekdays"]), interval=int(data["interval"]), count=count)
            else:
                rule = RecurrenceRule.monthly_nth(
                    weekday=int(data["monthly_weekday"]), bysetpos=int(data["monthly_pos"]), count=count)
            await finish_new_event(message, state, rule, locale)
        except (ValueError, PermissionError, KeyError) as exc:
            detail = exc if not isinstance(exc, KeyError) else ValueError("Incomplete recurrence data")
            await flow_err(message, locale, detail, t(locale, "enter_occurrence_count"))

    @router.message(Command("reschedule"))
    @router.message(F.text.in_(org_texts("reschedule")))
    async def reschedule_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                event_id, new_start = split_args(command, 2, locale=locale)
                async with db.sessions() as session:
                    changed = await change_event(session, message.from_user.id, int(event_id), new_start)
                    calendar = await session.get(Calendar, changed[0].event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, changed, "heading_event_rescheduled")
                await mirror_changed_events(db, settings, changed)
                await message.answer(
                    t(locale, "events_updated_count", count=len(changed)),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await state.set_state(OrganizerReschedule.calendar)
        await pick_calendar(message, "o_resched", "choose_calendar_reschedule", locale)

    @router.callback_query(F.data.startswith("o_resched:"))
    async def reschedule_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            series = await fetch_future_series(session, calendar_id)
        if not series:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerReschedule.series)
        await callback.message.edit_text(
            t(locale, "choose_event"), reply_markup=event_series_keyboard(series, "o_resched_ser", locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_resched_ser:"))
    async def reschedule_series(callback: CallbackQuery, state: FSMContext) -> None:
        series_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(data["calendar_id"]))
            rows = await event_occurrences(session, series_id)
        if not rows:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(series_id=series_id)
        await state.set_state(OrganizerReschedule.occurrence)
        await callback.message.edit_text(
            t(locale, "choose_occurrence"),
            reply_markup=occurrences_keyboard(occurrence_button_items(rows, calendar.timezone), "o_resched_occ", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_resched_occ:"))
    async def reschedule_occurrence(callback: CallbackQuery, state: FSMContext) -> None:
        occurrence_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(occurrence_id=occurrence_id)
        await state.set_state(OrganizerReschedule.scope)
        await callback.message.edit_text(
            t(locale, "choose_edit_scope"), reply_markup=edit_scope_keyboard("o_resched_scope", locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_resched_scope:"))
    async def reschedule_scope(callback: CallbackQuery, state: FSMContext) -> None:
        scope = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        await state.update_data(scope=scope)
        await state.set_state(OrganizerReschedule.new_start)
        await callback.message.edit_text(t(locale, "enter_new_start"))
        await callback.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
        await callback.answer()

    @router.message(OrganizerReschedule.new_start, ~F.text.in_(ORG_INPUT_BLOCKLIST))
    async def reschedule_time(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                changed = await change_event(
                    session, message.from_user.id, data["occurrence_id"], message.text.strip(),
                    scope=data.get("scope") or "one")
                calendar = await session.get(Calendar, changed[0].event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, changed, "heading_event_rescheduled")
            await mirror_changed_events(db, settings, changed)
            await state.clear()
            await message.answer(
                t(locale, "events_updated_count", count=len(changed)),
                reply_markup=organizer_main_menu(locale),
            )
        except (ValueError, PermissionError) as exc:
            await flow_err(message, locale, exc, t(locale, "enter_new_start"))

    @router.message(F.text.in_(org_texts("cancel_event")))
    async def cancel_event_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await state.set_state(OrganizerCancelEvent.calendar)
        await pick_calendar(message, "o_cancel", "choose_calendar", locale)

    @router.callback_query(F.data.startswith("o_cancel:"))
    async def cancel_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            series = await fetch_future_series(session, calendar_id)
        if not series:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerCancelEvent.series)
        await callback.message.edit_text(
            t(locale, "choose_event_cancel"), reply_markup=event_series_keyboard(series, "o_cancel_ser", locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_ser:"))
    async def cancel_series(callback: CallbackQuery, state: FSMContext) -> None:
        series_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(data["calendar_id"]))
            rows = await event_occurrences(session, series_id)
        if not rows:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(series_id=series_id)
        await state.set_state(OrganizerCancelEvent.occurrence)
        await callback.message.edit_text(
            t(locale, "choose_occurrence_cancel"),
            reply_markup=occurrences_keyboard(occurrence_button_items(rows, calendar.timezone), "o_cancel_occ", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_occ:"))
    async def cancel_pick_occurrence(callback: CallbackQuery, state: FSMContext) -> None:
        occurrence_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(occurrence_id=occurrence_id)
        await state.set_state(OrganizerCancelEvent.scope)
        await callback.message.edit_text(
            t(locale, "choose_edit_scope"), reply_markup=edit_scope_keyboard("o_cancel_scope", locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_scope:"))
    async def cancel_scope(callback: CallbackQuery, state: FSMContext) -> None:
        scope = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        await state.update_data(scope=scope)
        await state.set_state(OrganizerCancelEvent.confirm)
        prompt = t(locale, "cancel_following_events" if scope == "following" else "cancel_this_event")
        await callback.message.edit_text(
            prompt, reply_markup=confirm_cancel_keyboard(int(data["occurrence_id"]), locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_yes:"))
    async def cancel_event_yes(callback: CallbackQuery, state: FSMContext) -> None:
        occurrence_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        try:
            async with db.sessions() as session:
                changed = await change_event(
                    session, callback.from_user.id, occurrence_id, cancel=True,
                    scope=data.get("scope") or "one")
                calendar = await session.get(Calendar, changed[0].event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, changed, "heading_event_cancelled")
            await mirror_changed_events(db, settings, changed, cancelled=True)
            await state.clear()
            await callback.message.edit_text(t(locale, "events_cancelled_count", count=len(changed)))
            await restore_menu(callback, locale)
        except (ValueError, PermissionError) as exc:
            scope = data.get("scope") or "one"
            prompt = t(locale, "cancel_following_events" if scope == "following" else "cancel_this_event")
            await callback.message.answer(t(locale, "error", error=exc))
            await callback.message.answer(prompt, reply_markup=confirm_cancel_keyboard(occurrence_id, locale))
        await callback.answer()

    @router.callback_query(F.data == "o_cancel_no")
    async def cancel_event_no(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        await discard_flow(callback, state, locale, role="org")

    @router.message(Command("confirmations"))
    @router.message(F.text.in_(org_texts("confirmations")))
    async def confirmations_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            try:
                calendar_id = int(command.args.strip())
                async with db.sessions() as session:
                    series = await fetch_future_series(session, calendar_id)
                if not series:
                    await message.answer(t(locale, "no_future_events"), reply_markup=organizer_main_menu(locale))
                    return
                await state.set_state(OrganizerConfirmations.series)
                await state.update_data(calendar_id=calendar_id)
                await prompt_inline(
                    message, t(locale, "choose_event"),
                    event_series_keyboard(series, "o_conf_ser", locale, show_back=False),
                    locale, with_reply_nav=True,
                )
            except ValueError as exc:
                await err(message, locale, exc)
            return
        await state.set_state(OrganizerConfirmations.calendar)
        await pick_calendar(message, "o_conf_cal", "choose_calendar_confirmations", locale)

    @router.callback_query(F.data.startswith("o_conf_cal:"))
    async def confirmations_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            series = await fetch_future_series(session, calendar_id)
        if not series:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerConfirmations.series)
        await callback.message.edit_text(
            t(locale, "choose_event"), reply_markup=event_series_keyboard(series, "o_conf_ser", locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_conf_ser:"))
    async def confirmations_series(callback: CallbackQuery, state: FSMContext) -> None:
        series_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(data["calendar_id"]))
            rows = await event_occurrences(session, series_id)
        if not rows:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_future_events"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(series_id=series_id)
        await state.set_state(OrganizerConfirmations.occurrence)
        await callback.message.edit_text(
            t(locale, "choose_occurrence"),
            reply_markup=occurrences_keyboard(occurrence_button_items(rows, calendar.timezone), "o_conf_occ", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_conf_occ:"))
    async def confirmations_occurrence(callback: CallbackQuery, state: FSMContext) -> None:
        occurrence_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            from sqlalchemy.orm import selectinload
            occurrence = await session.scalar(
                select(EventOccurrence).options(selectinload(EventOccurrence.event)).where(
                    EventOccurrence.id == occurrence_id))
            calendar = await session.get(Calendar, occurrence.event.calendar_id)
            rows = await confirmations_for_event(session, callback.from_user.id, occurrence_id)
        if not rows:
            text = t(locale, "no_confirmations", title=occurrence.event.title)
        else:
            names = "\n".join(
                f"• {c.display_name or t(locale, 'participant_fallback')}" for c in rows)
            text = t(
                locale, "confirmations_for", title=occurrence.event.title,
                time=display_time(occurrence.start_utc, calendar.timezone), names=names)
        await state.clear()
        await callback.message.edit_text(text)
        await restore_menu(callback, locale)
        await callback.answer()

    return router



async def notify_subscribers(session, bot: Bot, calendar: Calendar, occurrences: list[EventOccurrence],
                             heading_key: str) -> None:
    users = list((await session.scalars(select(User).join(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True), Subscription.muted.is_(False)))).all())
    for user in users:
        locale = normalize_locale(user.locale)
        heading = t(locale, heading_key)
        for occurrence in occurrences[:10]:
            try:
                await bot.send_message(
                    user.telegram_id,
                    t(locale, "notify_event", heading=heading, title=occurrence.event.title,
                      time=display_time(occurrence.start_utc, calendar.timezone), calendar=calendar.name),
                    reply_markup=event_confirm_keyboard(occurrence.id, locale),
                )
            except Exception:
                pass


async def notify_organizer_confirmation(bot: Bot, organizer: User, participant_name: str,
                                        occurrence: EventOccurrence, calendar: Calendar) -> None:
    locale = normalize_locale(organizer.locale)
    try:
        await bot.send_message(
            organizer.telegram_id,
            t(locale, "organizer_confirmed", name=participant_name, title=occurrence.event.title,
              time=display_time(occurrence.start_utc, calendar.timezone), calendar=calendar.name),
        )
    except Exception:
        pass


def build_participant_router(db: Database, settings: Settings, organizer_bot: Bot) -> Router:
    router = Router(name="participant")

    async def locale_for(telegram_id: int) -> str:
        async with db.sessions() as session:
            return await get_user_locale(session, telegram_id, settings.default_timezone)

    async def flow_err(message: Message, locale: str, exc: Exception, retry_prompt: str) -> None:
        await message.answer(t(locale, "error", error=exc))
        await message.answer(retry_prompt, reply_markup=flow_nav_keyboard(locale))

    async def restore_menu(target: Message | CallbackQuery, locale: str, text: str | None = None) -> None:
        msg = target.message if isinstance(target, CallbackQuery) else target
        await msg.answer(text or t(locale, "main_menu"), reply_markup=participant_main_menu(locale))

    async def prompt_text(target: Message | CallbackQuery, text: str, locale: str) -> None:
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text)
            except Exception:
                await target.message.answer(text, reply_markup=flow_nav_keyboard(locale))
            else:
                await target.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
            await target.answer()
        else:
            await target.answer(text, reply_markup=flow_nav_keyboard(locale))

    async def prompt_inline(
        target: Message | CallbackQuery, text: str, markup, locale: str, *, with_reply_nav: bool = False,
    ) -> None:
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text, reply_markup=markup)
            except Exception:
                await target.message.answer(text, reply_markup=markup)
            if with_reply_nav:
                await target.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
            await target.answer()
        else:
            await target.answer(text, reply_markup=markup)
            await target.answer("\u2060", reply_markup=flow_nav_keyboard(locale))

    @router.message(CommandStart(deep_link=True))
    async def deep_start(message: Message, command: CommandObject) -> None:
        locale = await locale_for(message.from_user.id)
        token = command.args or ""
        async with db.sessions() as session:
            calendar = await invitation_calendar(session, token)
        if not calendar:
            await message.answer(t(locale, "invite_invalid"))
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text=t(locale, "btn_subscribe", name=calendar.name), callback_data=f"subscribe:{token}")]])
        await message.answer(
            t(locale, "invited_to", name=calendar.name, timezone=format_timezone_offset(calendar.timezone)),
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("subscribe:"))
    async def confirm(callback: CallbackQuery) -> None:
        locale = await locale_for(callback.from_user.id)
        try:
            async with db.sessions() as session:
                calendar = await subscribe(
                    session, callback.from_user.id, callback.data.split(":", 1)[1], settings.default_timezone)
            await callback.message.edit_text(t(locale, "subscribed", name=calendar.name))
            await callback.message.answer(t(locale, "main_menu"), reply_markup=participant_main_menu(locale))
        except ValueError as exc:
            await callback.message.edit_text(str(exc))
        await callback.answer()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        locale = await locale_for(message.from_user.id)
        await send_participant_onboarding(message, locale, with_language_picker=True)

    @router.message(Command("language"))
    @router.message(F.text.in_(par_texts("language")))
    async def language_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "choose_language"), reply_markup=locale_keyboard("p_locale"))

    @router.callback_query(F.data.startswith("p_locale:"))
    async def language_set(callback: CallbackQuery) -> None:
        code = normalize_locale(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            await set_locale(session, callback.from_user.id, code, settings.default_timezone)
        await callback.message.edit_text(t(code, "language_updated"))
        await send_participant_onboarding(callback.message, code)
        await callback.answer()

    @router.message(Command("help"))
    @router.message(F.text.in_(par_texts("help")))
    async def help_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "par.onboarding"), reply_markup=participant_main_menu(locale))
        await message.answer(t(locale, "par.help"))

    @router.message(Command("cancel"))
    async def cancel_fsm(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        if await state.get_state():
            await discard_flow(message, state, locale, role="par")
        else:
            await message.answer(t(locale, "nothing_to_cancel"), reply_markup=participant_main_menu(locale))

    @router.message(F.text.in_(nav_texts("cancel")))
    async def par_cancel_btn(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        if await state.get_state():
            await discard_flow(message, state, locale, role="par")
        else:
            await message.answer(t(locale, "nothing_to_cancel"), reply_markup=participant_main_menu(locale))

    @router.callback_query(F.data == FLOW_CANCEL_DATA)
    async def par_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        if await state.get_state():
            await discard_flow(callback, state, locale, role="par")
        else:
            await callback.answer(t(locale, "nothing_to_cancel"), show_alert=True)

    async def par_flow_back(target: Message | CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(target.from_user.id)
        current = await state.get_state()
        data = await state.get_data()
        uid = target.from_user.id

        if not current:
            if isinstance(target, CallbackQuery):
                await target.answer(t(locale, "nothing_to_cancel"), show_alert=True)
            else:
                await target.answer(t(locale, "nothing_to_cancel"), reply_markup=participant_main_menu(locale))
            return

        async def cancel() -> None:
            await discard_flow(target, state, locale, role="par")

        if current == ParticipantTimezone.timezone.state:
            await cancel()
        elif current == ParticipantReminders.calendar.state:
            await cancel()
        elif current == ParticipantReminders.minutes.state:
            await state.set_state(ParticipantReminders.calendar)
            await state.update_data(calendar_id=None)
            async with db.sessions() as session:
                data = await fetch_subscribed_calendars(session, uid)
            calendars = [c for c, _ in data]
            await prompt_inline(
                target, t(locale, "choose_reminders"),
                calendars_keyboard(calendars, "p_remind", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == ParticipantUpcoming.range_pick.state:
            await cancel()
        elif current == ParticipantUpcoming.calendar.state:
            await state.set_state(ParticipantUpcoming.range_pick)
            await state.update_data(range_mode=None, calendar_id=None)
            await prompt_inline(
                target, t(locale, "what_to_see"),
                event_range_keyboard("p_up_rng", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == ParticipantUpcoming.series.state:
            range_mode = data.get("range_mode") or "week"
            await state.set_state(ParticipantUpcoming.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                user = await session.scalar(select(User).where(User.telegram_id == uid))
                tz = user.timezone if user else settings.default_timezone
                calendars = await subscribed_calendars_with_series(session, uid, range_mode, tz)
            await prompt_inline(
                target, t(locale, "choose_calendar"),
                calendars_keyboard(calendars, f"p_up_cal:{range_mode}", locale, show_back=True),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == ParticipantConfirmPick.calendar.state:
            await cancel()
        elif current == ParticipantConfirmPick.series.state:
            await state.set_state(ParticipantConfirmPick.calendar)
            await state.update_data(calendar_id=None, series_id=None)
            async with db.sessions() as session:
                calendars = await subscribed_calendars_with_pending(session, uid, settings.default_timezone)
            await prompt_inline(
                target, t(locale, "choose_calendar_confirm"),
                calendars_keyboard(calendars, "p_conf_cal", locale, show_back=False),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == ParticipantConfirmPick.occurrence.state:
            calendar_id = data.get("calendar_id")
            await state.set_state(ParticipantConfirmPick.series)
            await state.update_data(series_id=None)
            async with db.sessions() as session:
                series = await pending_series_for_calendar(session, uid, int(calendar_id), settings.default_timezone)
            await prompt_inline(
                target, t(locale, "choose_event"),
                event_series_keyboard(series, "p_conf_ser", locale),
                locale, with_reply_nav=isinstance(target, Message),
            )
        elif current == ParticipantMute.calendar.state:
            await cancel()
        elif current == ParticipantUnmute.calendar.state:
            await cancel()
        elif current == ParticipantUnsubscribe.calendar.state:
            await cancel()
        else:
            await cancel()

    @router.message(F.text.in_(nav_texts("back")))
    async def par_back_btn(message: Message, state: FSMContext) -> None:
        await par_flow_back(message, state)

    @router.callback_query(F.data == FLOW_BACK_DATA)
    async def par_back_cb(callback: CallbackQuery, state: FSMContext) -> None:
        await par_flow_back(callback, state)

    async def reply_upcoming(message: Message, range_mode: str, locale: str) -> None:
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            rows = await upcoming_for_user_with_status(
                session, message.from_user.id, range_mode, settings.default_timezone)
        tz = user.timezone if user else settings.default_timezone
        await message.answer(
            format_participant_events(rows, tz, range_mode, locale),
            reply_markup=participant_main_menu(locale),
        )

    @router.message(Command("upcoming"))
    @router.message(F.text.in_(par_texts("upcoming")))
    async def upcoming(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            range_mode = command.args.strip().lower()
            if range_mode not in {"next", "week"}:
                await message.answer(t(locale, "usage_upcoming"), reply_markup=participant_main_menu(locale))
                return
            await reply_upcoming(message, range_mode, locale)
            return
        await state.set_state(ParticipantUpcoming.range_pick)
        await prompt_inline(
            message, t(locale, "what_to_see"), event_range_keyboard("p_up_rng", locale), locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("p_up_rng:"))
    async def upcoming_range_pick(callback: CallbackQuery, state: FSMContext) -> None:
        range_mode = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        await state.update_data(range_mode=range_mode)
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            tz = user.timezone if user else settings.default_timezone
            calendars = await subscribed_calendars_with_series(
                session, callback.from_user.id, range_mode, tz)
        if not calendars:
            await state.clear()
            await callback.message.edit_text(
                t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        if len(calendars) == 1:
            calendar = calendars[0]
            await state.update_data(calendar_id=calendar.id)
            async with db.sessions() as session:
                series = await fetch_future_series(session, calendar.id, range_mode, calendar.timezone)
            await state.set_state(ParticipantUpcoming.series)
            await callback.message.edit_text(
                t(locale, "choose_event"),
                reply_markup=event_series_keyboard(series, f"p_up_ser:{range_mode}", locale, show_back=False),
            )
            await callback.answer()
            return
        await state.set_state(ParticipantUpcoming.calendar)
        await callback.message.edit_text(
            t(locale, "choose_calendar"),
            reply_markup=calendars_keyboard(calendars, f"p_up_cal:{range_mode}", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("p_up_cal:"))
    async def upcoming_calendar_pick(callback: CallbackQuery, state: FSMContext) -> None:
        _, range_mode, calendar_id = callback.data.split(":", 2)
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(calendar_id))
            series = await fetch_future_series(session, calendar.id, range_mode, calendar.timezone)
        if not series:
            await state.clear()
            await callback.message.edit_text(
                t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(range_mode=range_mode, calendar_id=calendar.id)
        await state.set_state(ParticipantUpcoming.series)
        await callback.message.edit_text(
            t(locale, "choose_event"),
            reply_markup=event_series_keyboard(series, f"p_up_ser:{range_mode}", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("p_up_ser:"))
    async def upcoming_series_pick(callback: CallbackQuery, state: FSMContext) -> None:
        _, range_mode, series_id = callback.data.split(":", 2)
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            event = await session.get(Event, int(series_id))
            calendar = await session.get(Calendar, event.calendar_id)
            rows = await event_occurrences(session, event.id, range_mode, calendar.timezone)
            confirmed = set()
            if user:
                confirmed = await confirmed_occurrence_ids(session, user.id, [o.id for o in rows])
        await state.clear()
        await callback.message.edit_text(
            format_series_occurrences(
                event, rows, calendar, range_mode, locale, with_confirm=True, confirmed_ids=confirmed))
        await restore_menu(callback, locale)
        await callback.answer()

    @router.message(Command("confirm"))
    @router.message(F.text.in_(par_texts("confirm")))
    async def confirm_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await handle_confirm(message.from_user, int(command.args.strip()), message, locale)
            return
        async with db.sessions() as session:
            calendars = await subscribed_calendars_with_pending(
                session, message.from_user.id, settings.default_timezone)
        if not calendars:
            await message.answer(t(locale, "no_pending_confirm"), reply_markup=participant_main_menu(locale))
            return
        await state.set_state(ParticipantConfirmPick.calendar)
        await prompt_inline(
            message, t(locale, "choose_calendar_confirm"),
            calendars_keyboard(calendars, "p_conf_cal", locale, show_back=False),
            locale, with_reply_nav=True,
        )

    @router.callback_query(F.data.startswith("p_conf_cal:"))
    async def confirm_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            series = await pending_series_for_calendar(
                session, callback.from_user.id, calendar_id, settings.default_timezone)
        if not series:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_pending_confirm"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(ParticipantConfirmPick.series)
        await callback.message.edit_text(
            t(locale, "choose_event"),
            reply_markup=event_series_keyboard(series, "p_conf_ser", locale),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("p_conf_ser:"))
    async def confirm_series(callback: CallbackQuery, state: FSMContext) -> None:
        series_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(data["calendar_id"]))
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            rows = await event_occurrences(session, series_id)
            confirmed = await confirmed_occurrence_ids(session, user.id, [o.id for o in rows]) if user else set()
            pending = [o for o in rows if o.id not in confirmed]
        if not pending:
            await state.clear()
            await callback.message.edit_text(t(locale, "no_pending_confirm"))
            await restore_menu(callback, locale)
            await callback.answer()
            return
        await state.update_data(series_id=series_id)
        await state.set_state(ParticipantConfirmPick.occurrence)
        await callback.message.edit_text(
            t(locale, "choose_occurrence_confirm"),
            reply_markup=occurrences_keyboard(
                occurrence_button_items(pending, calendar.timezone, mark_confirm=True),
                "p_confirm",
                locale,
            ),
        )
        await callback.answer()

    async def handle_confirm(user, event_id: int, reply_target: Message | CallbackQuery, locale: str,
                             *, keep_flow: bool = False) -> bool:
        name = participant_display_name(user)
        try:
            async with db.sessions() as session:
                occurrence, calendar, owner, created = await confirm_event(
                    session, user.id, event_id, name, settings.default_timezone)
            if created:
                await notify_organizer_confirmation(organizer_bot, owner, name, occurrence, calendar)
                text = t(locale, "confirmed", title=occurrence.event.title,
                         time=display_time(occurrence.start_utc, calendar.timezone))
            else:
                text = t(locale, "already_confirmed", title=occurrence.event.title)
            if isinstance(reply_target, CallbackQuery):
                await reply_target.message.edit_text(text)
                await restore_menu(reply_target, locale)
                await reply_target.answer()
            else:
                await reply_target.answer(text, reply_markup=participant_main_menu(locale))
            return True
        except (ValueError, PermissionError) as exc:
            text = t(locale, "error", error=exc)
            if isinstance(reply_target, CallbackQuery):
                if keep_flow:
                    await reply_target.message.answer(text)
                else:
                    await reply_target.message.edit_text(text)
                    await restore_menu(reply_target, locale)
                await reply_target.answer()
            else:
                await reply_target.answer(text, reply_markup=participant_main_menu(locale))
            return False

    @router.callback_query(F.data.startswith("p_confirm:"))
    async def confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
        locale = await locale_for(callback.from_user.id)
        data = await state.get_data()
        in_flow = await state.get_state() == ParticipantConfirmPick.occurrence.state
        ok = await handle_confirm(
            callback.from_user, int(callback.data.split(":", 1)[1]), callback, locale, keep_flow=in_flow)
        if ok:
            await state.clear()
            return
        if in_flow and data.get("series_id") and data.get("calendar_id"):
            async with db.sessions() as session:
                calendar = await session.get(Calendar, int(data["calendar_id"]))
                user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
                rows = await event_occurrences(session, int(data["series_id"]))
                confirmed = await confirmed_occurrence_ids(session, user.id, [o.id for o in rows]) if user else set()
                pending = [o for o in rows if o.id not in confirmed]
            if pending:
                await callback.message.answer(
                    t(locale, "choose_occurrence_confirm"),
                    reply_markup=occurrences_keyboard(
                        occurrence_button_items(pending, calendar.timezone, mark_confirm=True),
                        "p_confirm",
                        locale,
                    ),
                )
            else:
                await state.clear()
                await restore_menu(callback, locale)

    async def reply_subscriptions(message: Message, locale: str) -> None:
        async with db.sessions() as session:
            data = await fetch_subscribed_calendars(session, message.from_user.id)
        await message.answer(
            "\n".join(
                f"{c.id}: {c.name} [{t(locale, 'sub_muted') if s.muted else t(locale, 'sub_active')}]"
                for c, s in data
            ) or t(locale, "no_subscriptions"),
            reply_markup=participant_main_menu(locale),
        )

    @router.message(Command("subscriptions"))
    @router.message(F.text.in_(par_texts("subscriptions")))
    async def subscriptions(message: Message, state: FSMContext) -> None:
        await state.clear()
        await reply_subscriptions(message, await locale_for(message.from_user.id))

    @router.message(Command("timezone"))
    @router.message(F.text.in_(par_texts("timezone")))
    async def timezone_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                async with db.sessions() as session:
                    await set_timezone(session, message.from_user.id, command.args.strip(), settings.default_timezone)
                await message.answer(t(locale, "timezone_updated"), reply_markup=participant_main_menu(locale))
            except ValueError as exc:
                await message.answer(t(locale, "error", error=exc), reply_markup=participant_main_menu(locale))
            return
        await state.clear()
        await state.set_state(ParticipantTimezone.timezone)
        await message.answer(t(locale, "enter_timezone"), reply_markup=flow_nav_keyboard(locale))

    @router.message(ParticipantTimezone.timezone, ~F.text.in_(PAR_INPUT_BLOCKLIST))
    async def timezone_value(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                await set_timezone(session, message.from_user.id, message.text.strip(), settings.default_timezone)
            await state.clear()
            await message.answer(t(locale, "timezone_updated"), reply_markup=participant_main_menu(locale))
        except ValueError as exc:
            await flow_err(message, locale, exc, t(locale, "enter_timezone"))

    async def pick_subscription(message: Message, prefix: str, prompt_key: str, locale: str) -> bool:
        async with db.sessions() as session:
            data = await fetch_subscribed_calendars(session, message.from_user.id)
        if not data:
            await message.answer(t(locale, "no_subscriptions"), reply_markup=participant_main_menu(locale))
            return False
        calendars = [c for c, _ in data]
        await prompt_inline(
            message, t(locale, prompt_key),
            calendars_keyboard(calendars, prefix, locale, show_back=False),
            locale, with_reply_nav=True,
        )
        return True

    async def state_action(message: Message, calendar_id: int, action: str, locale: str) -> None:
        try:
            async with db.sessions() as session:
                changed = await set_subscription_state(session, message.from_user.id, calendar_id, action)
            text = t(locale, "updated") if changed else t(locale, "subscription_not_found")
            await message.answer(text, reply_markup=participant_main_menu(locale))
        except ValueError:
            await message.answer(t(locale, "usage_action", action=action), reply_markup=participant_main_menu(locale))

    @router.message(Command("mute"))
    @router.message(F.text.in_(par_texts("mute")))
    async def mute_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state_action(message, int(command.args.strip()), "mute", locale)
            return
        await state.set_state(ParticipantMute.calendar)
        await pick_subscription(message, "p_mute", "choose_mute", locale)

    @router.message(Command("unmute"))
    @router.message(F.text.in_(par_texts("unmute")))
    async def unmute_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unmute", locale)
            return
        await state.set_state(ParticipantUnmute.calendar)
        await pick_subscription(message, "p_unmute", "choose_unmute", locale)

    @router.message(Command("unsubscribe"))
    @router.message(F.text.in_(par_texts("unsubscribe")))
    async def unsubscribe_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unsubscribe", locale)
            return
        await state.set_state(ParticipantUnsubscribe.calendar)
        await pick_subscription(message, "p_unsub", "choose_unsubscribe", locale)

    @router.callback_query(F.data.startswith("p_mute:"))
    async def mute_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "mute")
        await state.clear()
        await callback.message.edit_text(t(locale, "muted") if changed else t(locale, "subscription_not_found"))
        await restore_menu(callback, locale)
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unmute:"))
    async def unmute_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unmute")
        await state.clear()
        await callback.message.edit_text(t(locale, "unmuted") if changed else t(locale, "subscription_not_found"))
        await restore_menu(callback, locale)
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unsub:"))
    async def unsub_pick(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unsubscribe")
        await state.clear()
        await callback.message.edit_text(
            t(locale, "unsubscribed") if changed else t(locale, "subscription_not_found"))
        await restore_menu(callback, locale)
        await callback.answer()

    @router.message(Command("reminders"))
    @router.message(F.text.in_(par_texts("reminders")))
    async def reminders_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                parts = command.args.split(maxsplit=1)
                async with db.sessions() as session:
                    changed = await set_reminders(session, message.from_user.id, int(parts[0]), parts[1])
                await message.answer(
                    t(locale, "reminders_saved") if changed else t(locale, "subscription_not_found"),
                    reply_markup=participant_main_menu(locale),
                )
            except (ValueError, IndexError) as exc:
                detail = exc if str(exc) else t(locale, "usage_reminders")
                await message.answer(t(locale, "error", error=detail), reply_markup=participant_main_menu(locale))
            return
        await state.clear()
        await state.set_state(ParticipantReminders.calendar)
        await pick_subscription(message, "p_remind", "choose_reminders", locale)

    @router.callback_query(F.data.startswith("p_remind:"))
    async def reminders_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(ParticipantReminders.minutes)
        await callback.message.edit_text(t(locale, "enter_reminders"))
        await callback.message.answer("\u2060", reply_markup=flow_nav_keyboard(locale))
        await callback.answer()

    @router.message(ParticipantReminders.minutes, ~F.text.in_(PAR_INPUT_BLOCKLIST))
    async def reminders_value(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                changed = await set_reminders(session, message.from_user.id, data["calendar_id"], message.text.strip())
            await state.clear()
            await message.answer(
                t(locale, "reminders_saved") if changed else t(locale, "subscription_not_found"),
                reply_markup=participant_main_menu(locale),
            )
        except ValueError as exc:
            await flow_err(message, locale, exc, t(locale, "enter_reminders"))

    return router



async def configure_commands(organizer: Bot, participant: Bot) -> None:
    for code in LOCALES:
        await organizer.set_my_commands([
            BotCommand(command="calendars", description=t(code, "cmd.calendars")),
            BotCommand(command="newevent", description=t(code, "cmd.newevent")),
            BotCommand(command="googleimport", description=t(code, "cmd.googleimport")),
            BotCommand(command="googlesync", description=t(code, "cmd.googlesync")),
            BotCommand(command="googleinvite", description=t(code, "cmd.googleinvite")),
            BotCommand(command="language", description=t(code, "cmd.language")),
            BotCommand(command="help", description=t(code, "cmd.help")),
        ], language_code=code)
        await participant.set_my_commands([
            BotCommand(command="upcoming", description=t(code, "cmd.upcoming")),
            BotCommand(command="confirm", description=t(code, "cmd.confirm")),
            BotCommand(command="subscriptions", description=t(code, "cmd.subscriptions")),
            BotCommand(command="language", description=t(code, "cmd.language")),
            BotCommand(command="help", description=t(code, "cmd.help")),
        ], language_code=code)
    await organizer.set_my_commands([
        BotCommand(command="calendars", description=t("en", "cmd.calendars")),
        BotCommand(command="newevent", description=t("en", "cmd.newevent")),
        BotCommand(command="googleimport", description=t("en", "cmd.googleimport")),
        BotCommand(command="googlesync", description=t("en", "cmd.googlesync")),
        BotCommand(command="googleinvite", description=t("en", "cmd.googleinvite")),
        BotCommand(command="language", description=t("en", "cmd.language")),
        BotCommand(command="help", description=t("en", "cmd.help")),
    ])
    await participant.set_my_commands([
        BotCommand(command="upcoming", description=t("en", "cmd.upcoming")),
        BotCommand(command="confirm", description=t("en", "cmd.confirm")),
        BotCommand(command="subscriptions", description=t("en", "cmd.subscriptions")),
        BotCommand(command="language", description=t("en", "cmd.language")),
        BotCommand(command="help", description=t("en", "cmd.help")),
    ])
