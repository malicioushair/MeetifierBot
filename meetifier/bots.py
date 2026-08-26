from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .config import Settings
from .db import Calendar, Database, Event, GoogleCalendarLink, Subscription, User, utcnow
from .i18n import LOCALES, normalize_locale, t
from .keyboards import (ORGANIZER_BUTTONS, PARTICIPANT_BUTTONS, calendars_keyboard, confirm_cancel_keyboard,
                        confirm_google_adoption_keyboard, event_confirm_keyboard, event_range_keyboard,
                        events_keyboard, google_calendars_keyboard, locale_keyboard, org_texts,
                        organizer_main_menu, par_texts, participant_main_menu, upcoming_confirm_keyboard)
from .google_sync import (adopt_google_calendar, authorization_url, create_oauth_state, get_google_account,
                          google_enabled, import_google_calendar, link_google_calendar, list_google_calendars,
                          sync_changed_event, sync_created_events, sync_google_calendar)
from .service import (calendar_events, change_event, confirm_event, confirmations_for_event, create_calendar,
                      create_events, display_time, get_user_locale, invitation_calendar, make_invitation,
                      set_locale, set_reminders, set_subscription_state, set_timezone, subscribe,
                      upcoming_for_user_with_status)
from .states import (OrganizerNewCalendar, OrganizerNewEvent, OrganizerReschedule, ParticipantReminders,
                     ParticipantTimezone)


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


async def fetch_future_events(session, calendar_id: int, limit: int = 20) -> list[Event]:
    return list((await session.scalars(
        select(Event).where(Event.calendar_id == calendar_id, Event.start_utc > utcnow())
        .order_by(Event.start_utc).limit(limit)
    )).all())


async def fetch_subscribed_calendars(session, telegram_id: int) -> list[tuple[Calendar, Subscription]]:
    rows = await session.execute(
        select(Calendar, Subscription).join(Subscription).join(User).where(
            User.telegram_id == telegram_id, Subscription.active.is_(True))
    )
    return list(rows.tuples().all())


def format_organizer_events(events: list[Event], calendar: Calendar, range_mode: str, locale: str) -> str:
    if not events:
        return t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming")
    return "\n".join(
        f"{e.id}: {e.title} — {display_time(e.start_utc, calendar.timezone)} [{e.status}]" for e in events
    )


def format_participant_events(rows: list[tuple[Event, Calendar, bool]], timezone_name: str, range_mode: str,
                              locale: str) -> str:
    if not rows:
        return t(locale, "no_events_week" if range_mode == "week" else "no_events_upcoming")
    lines = []
    for event, calendar, confirmed in rows:
        status = " ✅" if confirmed else ""
        lines.append(f"{event.title} — {display_time(event.start_utc, timezone_name)} ({calendar.name}){status}")
    return "\n".join(lines)


async def mirror_created_events(db: Database, settings: Settings, calendar_id: int, events: list[Event]) -> None:
    async with db.sessions() as session:
        calendar = await session.get(Calendar, calendar_id)
    if calendar:
        await sync_created_events(db, settings, calendar, events)


async def mirror_changed_event(db: Database, settings: Settings, event: Event, *, cancelled: bool = False) -> None:
    async with db.sessions() as session:
        calendar = await session.get(Calendar, event.calendar_id)
    if calendar:
        await sync_changed_event(db, settings, event, calendar, cancelled=cancelled)


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
                    event = await change_event(session, message.from_user.id, int(command.args.strip()), cancel=True)
                    calendar = await session.get(Calendar, event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, [event], "heading_event_cancelled")
                await mirror_changed_event(db, settings, event, cancelled=True)
                await message.answer(t(locale, "event_cancelled_notified"), reply_markup=organizer_main_menu(locale))
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        if await state.get_state():
            await state.clear()
            await message.answer(t(locale, "cancelled"), reply_markup=organizer_main_menu(locale))
            return
        await message.answer(t(locale, "nothing_to_cancel_event"))

    async def reply_calendars(message: Message, locale: str) -> None:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        await message.answer(
            "\n".join(f"{x.id}: {x.name} [{x.timezone}]" for x in rows) or t(locale, "no_calendars"),
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
        await message.answer(t(locale, "enter_calendar_name"), reply_markup=organizer_main_menu(locale))

    @router.message(OrganizerNewCalendar.name, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_calendar_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name=message.text.strip())
        await state.set_state(OrganizerNewCalendar.timezone)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_timezone"))

    @router.message(OrganizerNewCalendar.timezone, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_calendar_timezone(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                calendar = await create_calendar(
                    session, message.from_user.id, data["name"], message.text.strip(), settings.default_timezone)
            await message.answer(
                t(locale, "calendar_created", name=calendar.name, id=calendar.id),
                reply_markup=organizer_main_menu(locale),
            )
        except (ValueError, PermissionError) as exc:
            await err(message, locale, exc)
        await state.clear()

    async def pick_calendar(message: Message, prefix: str, prompt_key: str, locale: str) -> None:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        if not rows:
            await message.answer(t(locale, "no_calendars_create"), reply_markup=organizer_main_menu(locale))
            return
        await message.answer(t(locale, prompt_key), reply_markup=calendars_keyboard(rows, prefix))

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
        await message.answer(t(locale, "what_to_see"), reply_markup=event_range_keyboard("o_evt_rng", locale))

    @router.callback_query(F.data.startswith("o_evt_rng:"))
    async def events_range_pick(callback: CallbackQuery) -> None:
        range_mode = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, callback.from_user.id)
            if not rows:
                await callback.message.edit_text(t(locale, "no_calendars_create"))
                await callback.answer()
                return
            if len(rows) == 1:
                calendar = rows[0]
                events = await calendar_events(session, calendar.id, range_mode, calendar.timezone)
                await callback.message.edit_text(format_organizer_events(events, calendar, range_mode, locale))
                await callback.answer()
                return
        await callback.message.edit_text(
            t(locale, "choose_calendar"),
            reply_markup=calendars_keyboard(rows, f"o_evt_cal:{range_mode}"),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_evt_cal:"))
    async def events_calendar_pick(callback: CallbackQuery) -> None:
        _, range_mode, calendar_id = callback.data.split(":", 2)
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            calendar = await session.get(Calendar, int(calendar_id))
            rows = await calendar_events(session, calendar.id, range_mode, calendar.timezone)
        await callback.message.edit_text(format_organizer_events(rows, calendar, range_mode, locale))
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
        await pick_calendar(message, "o_gmap_cal", "choose_calendar_map", locale)

    @router.callback_query(F.data.startswith("o_gmap_cal:"))
    async def google_map_pick_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            account = await get_google_account(session, callback.from_user.id)
            if not account:
                await callback.message.edit_text(t(locale, "google_link_first"))
                await callback.answer()
                return
            try:
                google_cals = await list_google_calendars(session, settings, account)
            except Exception as exc:
                await callback.message.edit_text(t(locale, "google_load_failed", error=exc))
                await callback.answer()
                return
        if not google_cals:
            await callback.message.edit_text(t(locale, "google_none_found"))
            await callback.answer()
            return
        await state.update_data(meetifier_calendar_id=calendar_id, google_calendars=google_cals)
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
            await callback.message.edit_text(t(locale, "google_map_expired"))
            await callback.answer()
            return
        chosen = calendars_list[index]
        try:
            async with db.sessions() as session:
                await link_google_calendar(
                    session, callback.from_user.id, int(calendar_id),
                    chosen["id"], chosen["name"])
            result = await sync_google_calendar(db, settings, int(calendar_id), force_full=True)
            await callback.message.edit_text(
                t(locale, "google_mapped", name=chosen["name"], created=result.created, updated=result.updated))
        except Exception as exc:
            await callback.message.edit_text(t(locale, "error", error=exc))
        await state.clear()
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
        names = "\n".join(f"{i + 1}. {calendar['name']}" for i, calendar in enumerate(google_cals[:10]))
        await message.answer(
            t(locale, "google_choose_import", names=names),
            reply_markup=google_calendars_keyboard(len(google_cals), locale, "o_gimport_pick"),
        )

    @router.callback_query(F.data.startswith("o_gimport_pick:"))
    async def google_import_pick(callback: CallbackQuery, state: FSMContext) -> None:
        index = int(callback.data.split(":", 1)[1])
        data = await state.get_data()
        locale = await locale_for(callback.from_user.id)
        google_cals = data.get("google_import_calendars") or []
        if index >= len(google_cals):
            await callback.message.edit_text(t(locale, "google_import_expired"))
            await callback.answer()
            return
        chosen = google_cals[index]
        try:
            calendar, result = await import_google_calendar(
                db, settings, callback.from_user.id, chosen)
            await callback.message.edit_text(
                t(locale, "google_imported", name=chosen["name"], id=calendar.id,
                  created=result.created, updated=result.updated, cancelled=result.cancelled)
            )
        except Exception as exc:
            await callback.message.edit_text(t(locale, "google_import_failed", error=exc))
        await state.clear()
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
        await message.answer(
            t(locale, "choose_calendar_sync"), reply_markup=calendars_keyboard(calendars, "o_gsync"))

    @router.callback_query(F.data.startswith("o_gsync:"))
    async def google_sync_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        owned = {calendar.id for calendar in await fetch_linked_calendars(callback.from_user.id)}
        if calendar_id not in owned:
            await callback.message.edit_text(t(locale, "calendar_not_owned"))
        else:
            try:
                result = await sync_google_calendar(db, settings, calendar_id)
                await callback.message.edit_text(
                    t(locale, "google_sync_complete", created=result.created, updated=result.updated,
                      cancelled=result.cancelled))
            except Exception as exc:
                await callback.message.edit_text(t(locale, "google_sync_failed", error=exc))
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
            await message.answer(
                t(locale, "google_adopt_confirm", name=calendar.name),
                reply_markup=confirm_google_adoption_keyboard(calendar.id, locale),
            )
            return
        await message.answer(
            t(locale, "choose_calendar_adopt"),
            reply_markup=calendars_keyboard(calendars, "o_gadopt"),
        )

    @router.callback_query(F.data.startswith("o_gadopt:"))
    async def google_adopt_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        owned = {calendar.id: calendar for calendar in await fetch_linked_calendars(callback.from_user.id)}
        calendar = owned.get(calendar_id)
        if not calendar:
            await callback.message.edit_text(t(locale, "calendar_not_owned"))
        else:
            await callback.message.edit_text(
                t(locale, "google_adopt_confirm_short", name=calendar.name),
                reply_markup=confirm_google_adoption_keyboard(calendar_id, locale),
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("o_gadopt_yes:"))
    async def google_adopt_confirm(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        try:
            updated, total, invitation_url = await adopt_google_calendar(
                db, settings, callback.from_user.id, calendar_id, settings.participant_bot_username)
            await callback.message.edit_text(
                t(locale, "google_adopt_done", updated=updated, total=total, url=invitation_url)
            )
        except Exception as exc:
            await callback.message.edit_text(t(locale, "google_adopt_failed", error=exc))
        await callback.answer()

    @router.callback_query(F.data == "o_gadopt_no")
    async def google_adopt_cancel(callback: CallbackQuery) -> None:
        locale = await locale_for(callback.from_user.id)
        await callback.message.edit_text(t(locale, "google_adopt_cancelled"))
        await callback.answer()

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
        await pick_calendar(message, "o_invite", "choose_calendar_invite", locale)

    @router.callback_query(F.data.startswith("o_invite:"))
    async def invite_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        try:
            async with db.sessions() as session:
                invitation = await make_invitation(session, callback.from_user.id, calendar_id)
            url = f"https://t.me/{settings.participant_bot_username}?start={invitation.token}"
            await callback.message.edit_text(t(locale, "share_invite", url=url))
        except (ValueError, PermissionError) as exc:
            await callback.message.edit_text(t(locale, "error", error=exc))
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
                    events = await create_events(
                        session, message.from_user.id, int(calendar_id), title, start, int(duration), weeks)
                    calendar = await session.get(Calendar, int(calendar_id))
                    await notify_subscribers(session, participant_bot, calendar, events, "heading_new_event")
                await mirror_created_events(db, settings, int(calendar_id), events)
                await message.answer(
                    t(locale, "events_created", count=len(events), ids=", ".join(str(e.id) for e in events)),
                    reply_markup=organizer_main_menu(locale),
                )
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await pick_calendar(message, "o_newevent", "choose_calendar_event", locale)

    @router.callback_query(F.data.startswith("o_newevent:"))
    async def new_event_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerNewEvent.title)
        await callback.message.edit_text(t(locale, "enter_event_title"))
        await callback.answer()

    @router.message(OrganizerNewEvent.title, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_title(message: Message, state: FSMContext) -> None:
        await state.update_data(title=message.text.strip())
        await state.set_state(OrganizerNewEvent.start)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_start_time"))

    @router.message(OrganizerNewEvent.start, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_start_time(message: Message, state: FSMContext) -> None:
        await state.update_data(start=message.text.strip())
        await state.set_state(OrganizerNewEvent.duration)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_duration"))

    @router.message(OrganizerNewEvent.duration, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_duration(message: Message, state: FSMContext) -> None:
        await state.update_data(duration=message.text.strip())
        await state.set_state(OrganizerNewEvent.weeks)
        locale = await locale_for(message.from_user.id)
        await message.answer(t(locale, "enter_weeks"))

    @router.message(OrganizerNewEvent.weeks, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_weeks(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            weeks = int(message.text.strip())
            async with db.sessions() as session:
                events = await create_events(
                    session, message.from_user.id, data["calendar_id"], data["title"],
                    data["start"], int(data["duration"]), weeks)
                calendar = await session.get(Calendar, data["calendar_id"])
                await notify_subscribers(session, participant_bot, calendar, events, "heading_new_event")
            await mirror_created_events(db, settings, data["calendar_id"], events)
            await message.answer(
                t(locale, "events_created", count=len(events), ids=", ".join(str(e.id) for e in events)),
                reply_markup=organizer_main_menu(locale),
            )
        except (ValueError, PermissionError) as exc:
            await err(message, locale, exc)
        await state.clear()

    @router.message(Command("reschedule"))
    @router.message(F.text.in_(org_texts("reschedule")))
    async def reschedule_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state.clear()
            try:
                event_id, new_start = split_args(command, 2, locale=locale)
                async with db.sessions() as session:
                    event = await change_event(session, message.from_user.id, int(event_id), new_start)
                    calendar = await session.get(Calendar, event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, [event], "heading_event_rescheduled")
                await mirror_changed_event(db, settings, event)
                await message.answer(t(locale, "event_rescheduled_notified"), reply_markup=organizer_main_menu(locale))
            except (ValueError, PermissionError) as exc:
                await err(message, locale, exc)
            return
        await state.clear()
        await pick_calendar(message, "o_resched", "choose_calendar_reschedule", locale)

    @router.callback_query(F.data.startswith("o_resched:"))
    async def reschedule_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text(t(locale, "no_future_events"))
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await callback.message.edit_text(
            t(locale, "choose_event"), reply_markup=events_keyboard(rows, "o_resched_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_resched_evt:"))
    async def reschedule_event(callback: CallbackQuery, state: FSMContext) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(event_id=event_id)
        await state.set_state(OrganizerReschedule.new_start)
        await callback.message.edit_text(t(locale, "enter_new_start"))
        await callback.answer()

    @router.message(OrganizerReschedule.new_start, ~F.text.in_(ORGANIZER_BUTTONS))
    async def reschedule_time(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                event = await change_event(session, message.from_user.id, data["event_id"], message.text.strip())
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "heading_event_rescheduled")
            await mirror_changed_event(db, settings, event)
            await message.answer(t(locale, "event_rescheduled_notified"), reply_markup=organizer_main_menu(locale))
        except (ValueError, PermissionError) as exc:
            await err(message, locale, exc)
        await state.clear()

    @router.message(F.text.in_(org_texts("cancel_event")))
    async def cancel_event_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        await pick_calendar(message, "o_cancel", "choose_calendar", locale)

    @router.callback_query(F.data.startswith("o_cancel:"))
    async def cancel_calendar(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text(t(locale, "no_future_events"))
            await callback.answer()
            return
        await callback.message.edit_text(
            t(locale, "choose_event_cancel"), reply_markup=events_keyboard(rows, "o_cancel_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_evt:"))
    async def cancel_event_confirm(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await callback.message.edit_text(
            t(locale, "cancel_this_event"), reply_markup=confirm_cancel_keyboard(event_id, locale))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_yes:"))
    async def cancel_event_yes(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        try:
            async with db.sessions() as session:
                event = await change_event(session, callback.from_user.id, event_id, cancel=True)
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "heading_event_cancelled")
            await mirror_changed_event(db, settings, event, cancelled=True)
            await callback.message.edit_text(t(locale, "event_cancelled_notified"))
        except (ValueError, PermissionError) as exc:
            await callback.message.edit_text(t(locale, "error", error=exc))
        await callback.answer()

    @router.callback_query(F.data == "o_cancel_no")
    async def cancel_event_no(callback: CallbackQuery) -> None:
        locale = await locale_for(callback.from_user.id)
        await callback.message.edit_text(t(locale, "cancellation_aborted"))
        await callback.answer()

    @router.message(Command("confirmations"))
    @router.message(F.text.in_(org_texts("confirmations")))
    async def confirmations_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            try:
                calendar_id = int(command.args.strip())
                async with db.sessions() as session:
                    rows = await fetch_future_events(session, calendar_id)
                if not rows:
                    await message.answer(t(locale, "no_future_events"), reply_markup=organizer_main_menu(locale))
                    return
                await message.answer(t(locale, "choose_event"), reply_markup=events_keyboard(rows, "o_conf_evt"))
            except ValueError as exc:
                await err(message, locale, exc)
            return
        await pick_calendar(message, "o_conf_cal", "choose_calendar_confirmations", locale)

    @router.callback_query(F.data.startswith("o_conf_cal:"))
    async def confirmations_calendar(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text(t(locale, "no_future_events"))
            await callback.answer()
            return
        await callback.message.edit_text(t(locale, "choose_event"), reply_markup=events_keyboard(rows, "o_conf_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_conf_evt:"))
    async def confirmations_event(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            calendar = await session.scalar(select(Calendar).join(Event).where(Event.id == event_id))
            event = await session.get(Event, event_id)
            rows = await confirmations_for_event(session, callback.from_user.id, event_id)
        if not rows:
            text = t(locale, "no_confirmations", title=event.title)
        else:
            names = "\n".join(
                f"• {c.display_name or t(locale, 'participant_fallback')}" for c in rows)
            text = t(
                locale, "confirmations_for", title=event.title,
                time=display_time(event.start_utc, calendar.timezone), names=names)
        await callback.message.edit_text(text)
        await callback.answer()

    return router


async def notify_subscribers(session, bot: Bot, calendar: Calendar, events: list[Event], heading_key: str) -> None:
    users = list((await session.scalars(select(User).join(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True), Subscription.muted.is_(False)))).all())
    for user in users:
        locale = normalize_locale(user.locale)
        heading = t(locale, heading_key)
        for event in events[:10]:
            try:
                await bot.send_message(
                    user.telegram_id,
                    t(locale, "notify_event", heading=heading, title=event.title,
                      time=display_time(event.start_utc, calendar.timezone), calendar=calendar.name),
                    reply_markup=event_confirm_keyboard(event.id, locale),
                )
            except Exception:
                pass


async def notify_organizer_confirmation(bot: Bot, organizer: User, participant_name: str,
                                        event: Event, calendar: Calendar) -> None:
    locale = normalize_locale(organizer.locale)
    try:
        await bot.send_message(
            organizer.telegram_id,
            t(locale, "organizer_confirmed", name=participant_name, title=event.title,
              time=display_time(event.start_utc, calendar.timezone), calendar=calendar.name),
        )
    except Exception:
        pass


def build_participant_router(db: Database, settings: Settings, organizer_bot: Bot) -> Router:
    router = Router(name="participant")

    async def locale_for(telegram_id: int) -> str:
        async with db.sessions() as session:
            return await get_user_locale(session, telegram_id, settings.default_timezone)

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
            t(locale, "invited_to", name=calendar.name, timezone=calendar.timezone),
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
            await state.clear()
            await message.answer(t(locale, "cancelled"), reply_markup=participant_main_menu(locale))
        else:
            await message.answer(t(locale, "nothing_to_cancel"))

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
        await message.answer(t(locale, "what_to_see"), reply_markup=event_range_keyboard("p_up_rng", locale))

    @router.callback_query(F.data.startswith("p_up_rng:"))
    async def upcoming_range_pick(callback: CallbackQuery) -> None:
        range_mode = callback.data.split(":", 1)[1]
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
            rows = await upcoming_for_user_with_status(
                session, callback.from_user.id, range_mode, settings.default_timezone)
        tz = user.timezone if user else settings.default_timezone
        await callback.message.edit_text(format_participant_events(rows, tz, range_mode, locale))
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
            rows = await upcoming_for_user_with_status(
                session, message.from_user.id, "future", settings.default_timezone)
        pending = [(e, c) for e, c, confirmed in rows if not confirmed]
        if not pending:
            await message.answer(t(locale, "no_pending_confirm"), reply_markup=participant_main_menu(locale))
            return
        confirmed_ids = {e.id for e, _, confirmed in rows if confirmed}
        await message.answer(
            t(locale, "tap_to_confirm"),
            reply_markup=upcoming_confirm_keyboard([e for e, _ in pending], confirmed_ids),
        )

    async def handle_confirm(user, event_id: int, reply_target: Message | CallbackQuery, locale: str) -> None:
        name = participant_display_name(user)
        try:
            async with db.sessions() as session:
                event, calendar, owner, created = await confirm_event(
                    session, user.id, event_id, name, settings.default_timezone)
            if created:
                await notify_organizer_confirmation(organizer_bot, owner, name, event, calendar)
                text = t(locale, "confirmed", title=event.title,
                         time=display_time(event.start_utc, calendar.timezone))
            else:
                text = t(locale, "already_confirmed", title=event.title)
        except (ValueError, PermissionError) as exc:
            text = t(locale, "error", error=exc)
        if isinstance(reply_target, CallbackQuery):
            await reply_target.message.edit_text(text)
            await reply_target.answer()
        else:
            await reply_target.answer(text, reply_markup=participant_main_menu(locale))

    @router.callback_query(F.data.startswith("p_confirm:"))
    async def confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        locale = await locale_for(callback.from_user.id)
        await handle_confirm(callback.from_user, int(callback.data.split(":", 1)[1]), callback, locale)

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
        await message.answer(t(locale, "enter_timezone"), reply_markup=participant_main_menu(locale))

    @router.message(ParticipantTimezone.timezone, ~F.text.in_(PARTICIPANT_BUTTONS))
    async def timezone_value(message: Message, state: FSMContext) -> None:
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                await set_timezone(session, message.from_user.id, message.text.strip(), settings.default_timezone)
            await message.answer(t(locale, "timezone_updated"), reply_markup=participant_main_menu(locale))
        except ValueError as exc:
            await message.answer(t(locale, "error", error=exc), reply_markup=participant_main_menu(locale))
        await state.clear()

    async def pick_subscription(message: Message, prefix: str, prompt_key: str, locale: str) -> None:
        async with db.sessions() as session:
            data = await fetch_subscribed_calendars(session, message.from_user.id)
        if not data:
            await message.answer(t(locale, "no_subscriptions"), reply_markup=participant_main_menu(locale))
            return
        calendars = [c for c, _ in data]
        await message.answer(t(locale, prompt_key), reply_markup=calendars_keyboard(calendars, prefix))

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
        await pick_subscription(message, "p_mute", "choose_mute", locale)

    @router.message(Command("unmute"))
    @router.message(F.text.in_(par_texts("unmute")))
    async def unmute_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unmute", locale)
            return
        await pick_subscription(message, "p_unmute", "choose_unmute", locale)

    @router.message(Command("unsubscribe"))
    @router.message(F.text.in_(par_texts("unsubscribe")))
    async def unsubscribe_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        locale = await locale_for(message.from_user.id)
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unsubscribe", locale)
            return
        await pick_subscription(message, "p_unsub", "choose_unsubscribe", locale)

    @router.callback_query(F.data.startswith("p_mute:"))
    async def mute_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "mute")
        await callback.message.edit_text(t(locale, "muted") if changed else t(locale, "subscription_not_found"))
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unmute:"))
    async def unmute_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unmute")
        await callback.message.edit_text(t(locale, "unmuted") if changed else t(locale, "subscription_not_found"))
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unsub:"))
    async def unsub_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unsubscribe")
        await callback.message.edit_text(
            t(locale, "unsubscribed") if changed else t(locale, "subscription_not_found"))
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
        await pick_subscription(message, "p_remind", "choose_reminders", locale)

    @router.callback_query(F.data.startswith("p_remind:"))
    async def reminders_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        locale = await locale_for(callback.from_user.id)
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(ParticipantReminders.minutes)
        await callback.message.edit_text(t(locale, "enter_reminders"))
        await callback.answer()

    @router.message(ParticipantReminders.minutes, ~F.text.in_(PARTICIPANT_BUTTONS))
    async def reminders_value(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        locale = await locale_for(message.from_user.id)
        try:
            async with db.sessions() as session:
                changed = await set_reminders(session, message.from_user.id, data["calendar_id"], message.text.strip())
            await message.answer(
                t(locale, "reminders_saved") if changed else t(locale, "subscription_not_found"),
                reply_markup=participant_main_menu(locale),
            )
        except ValueError as exc:
            await message.answer(t(locale, "error", error=exc), reply_markup=participant_main_menu(locale))
        await state.clear()

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
