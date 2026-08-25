from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .config import Settings
from .db import Calendar, Database, Event, Subscription, User, utcnow
from .keyboards import (ORGANIZER_BUTTONS, ORG_CALENDARS, ORG_CANCEL, ORG_CONFIRMATIONS, ORG_EVENTS, ORG_HELP,
                        ORG_INVITE, ORG_NEW_CALENDAR, ORG_NEW_EVENT, ORG_RESCHEDULE, PARTICIPANT_BUTTONS, PAR_CONFIRM,
                        PAR_HELP, PAR_MUTE, PAR_REMINDERS, PAR_SUBSCRIPTIONS, PAR_TIMEZONE, PAR_UNMUTE, PAR_UNSUBSCRIBE,
                        PAR_UPCOMING, calendars_keyboard, confirm_cancel_keyboard, event_confirm_keyboard,
                        events_keyboard, organizer_main_menu, participant_main_menu, upcoming_confirm_keyboard)
from .service import (change_event, confirm_event, confirmations_for_event, create_calendar, create_events, display_time,
                      invitation_calendar, make_invitation, set_reminders, set_subscription_state, set_timezone,
                      subscribe, upcoming_for_user_with_status)
from .states import (OrganizerNewCalendar, OrganizerNewEvent, OrganizerReschedule, ParticipantReminders,
                     ParticipantTimezone)

ORGANIZER_HELP = """Use the menu buttons below, or type commands directly:

/newcalendar Name | Europe/Moscow
/calendars
/newevent CALENDAR_ID | Title | 2026-09-01 18:30 | DURATION_MINUTES | WEEKS
/events CALENDAR_ID
/invite CALENDAR_ID
/reschedule EVENT_ID | 2026-09-02 19:00
/cancel EVENT_ID
/confirmations CALENDAR_ID

Use WEEKS=1 for one-time events or 2..52 for weekly recurrence."""

PARTICIPANT_HELP = """Use the menu buttons below, or type commands directly:

/upcoming - next events
/confirm EVENT_ID - confirm attendance
/timezone Europe/Moscow
/reminders CALENDAR_ID 1440,30
/mute CALENDAR_ID
/unmute CALENDAR_ID
/unsubscribe CALENDAR_ID
/subscriptions"""


def participant_display_name(user) -> str:
    name = (user.full_name or "").strip()
    if user.username:
        return f"{name} (@{user.username})".strip() if name else f"@{user.username}"
    return name or f"User {user.id}"


def split_args(command: CommandObject, count_min: int, count_max: int | None = None) -> list[str]:
    parts = [x.strip() for x in (command.args or "").split("|")]
    maximum = count_max or count_min
    if len(parts) < count_min or len(parts) > maximum or any(not x for x in parts):
        raise ValueError("Wrong command format. Send /help for examples.")
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


def build_organizer_router(db: Database, settings: Settings, participant_bot: Bot) -> Router:
    router = Router(name="organizer")

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer("Welcome! Use the buttons below to manage your calendars.", reply_markup=organizer_main_menu())

    @router.message(Command("help"))
    @router.message(F.text == ORG_HELP)
    async def help_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(ORGANIZER_HELP, reply_markup=organizer_main_menu())

    @router.message(Command("cancel"))
    async def cancel_command(message: Message, state: FSMContext, command: CommandObject) -> None:
        if command.args:
            try:
                async with db.sessions() as session:
                    event = await change_event(session, message.from_user.id, int(command.args.strip()), cancel=True)
                    calendar = await session.get(Calendar, event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, [event], "Event cancelled")
                await message.answer("Event cancelled and subscribers notified.", reply_markup=organizer_main_menu())
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        if await state.get_state():
            await state.clear()
            await message.answer("Cancelled.", reply_markup=organizer_main_menu())
            return
        await message.answer("Nothing to cancel. Use ❌ Cancel event to cancel an event.")

    async def reply_calendars(message: Message) -> None:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        await message.answer(
            "\n".join(f"{x.id}: {x.name} [{x.timezone}]" for x in rows) or "No calendars yet.",
            reply_markup=organizer_main_menu(),
        )

    @router.message(Command("calendars"))
    @router.message(F.text == ORG_CALENDARS)
    async def calendars(message: Message, state: FSMContext) -> None:
        await state.clear()
        await reply_calendars(message)

    @router.message(Command("newcalendar"))
    @router.message(F.text == ORG_NEW_CALENDAR)
    async def new_calendar_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                name, tz = split_args(command, 2)
                async with db.sessions() as session:
                    calendar = await create_calendar(session, message.from_user.id, name, tz, settings.default_timezone)
                await message.answer(f"Calendar created: {calendar.name} (ID {calendar.id})", reply_markup=organizer_main_menu())
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await state.clear()
        await state.set_state(OrganizerNewCalendar.name)
        await message.answer("Enter calendar name:", reply_markup=organizer_main_menu())

    @router.message(OrganizerNewCalendar.name, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_calendar_name(message: Message, state: FSMContext) -> None:
        await state.update_data(name=message.text.strip())
        await state.set_state(OrganizerNewCalendar.timezone)
        await message.answer("Enter timezone (e.g. Europe/Moscow):")

    @router.message(OrganizerNewCalendar.timezone, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_calendar_timezone(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            async with db.sessions() as session:
                calendar = await create_calendar(
                    session, message.from_user.id, data["name"], message.text.strip(), settings.default_timezone)
            await message.answer(f"Calendar created: {calendar.name} (ID {calendar.id})", reply_markup=organizer_main_menu())
        except (ValueError, PermissionError) as exc:
            await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
        await state.clear()

    async def pick_calendar(message: Message, prefix: str, prompt: str) -> None:
        async with db.sessions() as session:
            rows = await fetch_owned_calendars(session, message.from_user.id)
        if not rows:
            await message.answer("No calendars yet. Create one first.", reply_markup=organizer_main_menu())
            return
        await message.answer(prompt, reply_markup=calendars_keyboard(rows, prefix))

    @router.message(Command("events"))
    @router.message(F.text == ORG_EVENTS)
    async def events_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                calendar_id = int(command.args.strip())
                async with db.sessions() as session:
                    calendar = await session.scalar(select(Calendar).join(User).where(
                        Calendar.id == calendar_id, User.telegram_id == message.from_user.id))
                    if not calendar:
                        raise PermissionError("Calendar not found or not owned by you")
                    rows = await fetch_future_events(session, calendar.id)
                await message.answer(
                    "\n".join(f"{e.id}: {e.title} — {display_time(e.start_utc, calendar.timezone)} [{e.status}]" for e in rows)
                    or "No future events.",
                    reply_markup=organizer_main_menu(),
                )
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await state.clear()
        await pick_calendar(message, "o_events", "Choose a calendar:")

    @router.callback_query(F.data.startswith("o_events:"))
    async def events_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            calendar = await session.get(Calendar, calendar_id)
            rows = await fetch_future_events(session, calendar_id)
        text = "\n".join(
            f"{e.id}: {e.title} — {display_time(e.start_utc, calendar.timezone)} [{e.status}]" for e in rows
        ) or "No future events."
        await callback.message.edit_text(text)
        await callback.answer()

    @router.message(Command("invite"))
    @router.message(F.text == ORG_INVITE)
    async def invite_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                async with db.sessions() as session:
                    invitation = await make_invitation(session, message.from_user.id, int(command.args.strip()))
                await message.answer(
                    f"Share this link:\nhttps://t.me/{settings.participant_bot_username}?start={invitation.token}",
                    reply_markup=organizer_main_menu(),
                )
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await state.clear()
        await pick_calendar(message, "o_invite", "Choose a calendar to invite to:")

    @router.callback_query(F.data.startswith("o_invite:"))
    async def invite_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        try:
            async with db.sessions() as session:
                invitation = await make_invitation(session, callback.from_user.id, calendar_id)
            await callback.message.edit_text(
                f"Share this link:\nhttps://t.me/{settings.participant_bot_username}?start={invitation.token}")
        except (ValueError, PermissionError) as exc:
            await callback.message.edit_text(f"Error: {exc}")
        await callback.answer()

    @router.message(Command("newevent"))
    @router.message(F.text == ORG_NEW_EVENT)
    async def new_event_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                parts = split_args(command, 4, 5)
                calendar_id, title, start, duration = parts[:4]
                weeks = int(parts[4]) if len(parts) == 5 else 1
                async with db.sessions() as session:
                    events = await create_events(
                        session, message.from_user.id, int(calendar_id), title, start, int(duration), weeks)
                    calendar = await session.get(Calendar, int(calendar_id))
                    await notify_subscribers(session, participant_bot, calendar, events, "New event")
                await message.answer(
                    f"Created {len(events)} event(s). IDs: {', '.join(str(e.id) for e in events)}",
                    reply_markup=organizer_main_menu(),
                )
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await state.clear()
        await pick_calendar(message, "o_newevent", "Choose a calendar for the new event:")

    @router.callback_query(F.data.startswith("o_newevent:"))
    async def new_event_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(OrganizerNewEvent.title)
        await callback.message.edit_text("Enter event title:")
        await callback.answer()

    @router.message(OrganizerNewEvent.title, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_title(message: Message, state: FSMContext) -> None:
        await state.update_data(title=message.text.strip())
        await state.set_state(OrganizerNewEvent.start)
        await message.answer("Enter start time (YYYY-MM-DD HH:MM):")

    @router.message(OrganizerNewEvent.start, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_start_time(message: Message, state: FSMContext) -> None:
        await state.update_data(start=message.text.strip())
        await state.set_state(OrganizerNewEvent.duration)
        await message.answer("Duration in minutes:")

    @router.message(OrganizerNewEvent.duration, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_duration(message: Message, state: FSMContext) -> None:
        await state.update_data(duration=message.text.strip())
        await state.set_state(OrganizerNewEvent.weeks)
        await message.answer("Number of weeks (1 for one-time, 2..52 for weekly):")

    @router.message(OrganizerNewEvent.weeks, ~F.text.in_(ORGANIZER_BUTTONS))
    async def new_event_weeks(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            weeks = int(message.text.strip())
            async with db.sessions() as session:
                events = await create_events(
                    session, message.from_user.id, data["calendar_id"], data["title"],
                    data["start"], int(data["duration"]), weeks)
                calendar = await session.get(Calendar, data["calendar_id"])
                await notify_subscribers(session, participant_bot, calendar, events, "New event")
            await message.answer(
                f"Created {len(events)} event(s). IDs: {', '.join(str(e.id) for e in events)}",
                reply_markup=organizer_main_menu(),
            )
        except (ValueError, PermissionError) as exc:
            await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
        await state.clear()

    @router.message(Command("reschedule"))
    @router.message(F.text == ORG_RESCHEDULE)
    async def reschedule_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                event_id, new_start = split_args(command, 2)
                async with db.sessions() as session:
                    event = await change_event(session, message.from_user.id, int(event_id), new_start)
                    calendar = await session.get(Calendar, event.calendar_id)
                    await notify_subscribers(session, participant_bot, calendar, [event], "Event rescheduled")
                await message.answer("Event rescheduled and subscribers notified.", reply_markup=organizer_main_menu())
            except (ValueError, PermissionError) as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await state.clear()
        await pick_calendar(message, "o_resched", "Choose a calendar to reschedule an event in:")

    @router.callback_query(F.data.startswith("o_resched:"))
    async def reschedule_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text("No future events in this calendar.")
            await callback.answer()
            return
        await state.update_data(calendar_id=calendar_id)
        await callback.message.edit_text("Choose an event:", reply_markup=events_keyboard(rows, "o_resched_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_resched_evt:"))
    async def reschedule_event(callback: CallbackQuery, state: FSMContext) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        await state.update_data(event_id=event_id)
        await state.set_state(OrganizerReschedule.new_start)
        await callback.message.edit_text("Enter new start time (YYYY-MM-DD HH:MM):")
        await callback.answer()

    @router.message(OrganizerReschedule.new_start, ~F.text.in_(ORGANIZER_BUTTONS))
    async def reschedule_time(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            async with db.sessions() as session:
                event = await change_event(session, message.from_user.id, data["event_id"], message.text.strip())
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "Event rescheduled")
            await message.answer("Event rescheduled and subscribers notified.", reply_markup=organizer_main_menu())
        except (ValueError, PermissionError) as exc:
            await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
        await state.clear()

    @router.message(F.text == ORG_CANCEL)
    async def cancel_event_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await pick_calendar(message, "o_cancel", "Choose a calendar:")

    @router.callback_query(F.data.startswith("o_cancel:"))
    async def cancel_calendar(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text("No future events in this calendar.")
            await callback.answer()
            return
        await callback.message.edit_text("Choose an event to cancel:", reply_markup=events_keyboard(rows, "o_cancel_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_evt:"))
    async def cancel_event_confirm(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        await callback.message.edit_text("Cancel this event?", reply_markup=confirm_cancel_keyboard(event_id))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_cancel_yes:"))
    async def cancel_event_yes(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        try:
            async with db.sessions() as session:
                event = await change_event(session, callback.from_user.id, event_id, cancel=True)
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "Event cancelled")
            await callback.message.edit_text("Event cancelled and subscribers notified.")
        except (ValueError, PermissionError) as exc:
            await callback.message.edit_text(f"Error: {exc}")
        await callback.answer()

    @router.callback_query(F.data == "o_cancel_no")
    async def cancel_event_no(callback: CallbackQuery) -> None:
        await callback.message.edit_text("Cancellation aborted.")
        await callback.answer()

    @router.message(Command("confirmations"))
    @router.message(F.text == ORG_CONFIRMATIONS)
    async def confirmations_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        if command and command.args:
            try:
                calendar_id = int(command.args.strip())
                async with db.sessions() as session:
                    rows = await fetch_future_events(session, calendar_id)
                if not rows:
                    await message.answer("No future events in this calendar.", reply_markup=organizer_main_menu())
                    return
                await message.answer("Choose an event:", reply_markup=events_keyboard(rows, "o_conf_evt"))
            except ValueError as exc:
                await message.answer(f"Error: {exc}", reply_markup=organizer_main_menu())
            return
        await pick_calendar(message, "o_conf_cal", "Choose a calendar to view confirmations:")

    @router.callback_query(F.data.startswith("o_conf_cal:"))
    async def confirmations_calendar(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            rows = await fetch_future_events(session, calendar_id)
        if not rows:
            await callback.message.edit_text("No future events in this calendar.")
            await callback.answer()
            return
        await callback.message.edit_text("Choose an event:", reply_markup=events_keyboard(rows, "o_conf_evt"))
        await callback.answer()

    @router.callback_query(F.data.startswith("o_conf_evt:"))
    async def confirmations_event(callback: CallbackQuery) -> None:
        event_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            calendar = await session.scalar(select(Calendar).join(Event).where(Event.id == event_id))
            event = await session.get(Event, event_id)
            rows = await confirmations_for_event(session, callback.from_user.id, event_id)
        if not rows:
            text = f"No confirmations yet for {event.title}."
        else:
            names = "\n".join(f"• {c.display_name or 'Participant'}" for c in rows)
            text = f"Confirmations for {event.title} ({display_time(event.start_utc, calendar.timezone)}):\n{names}"
        await callback.message.edit_text(text)
        await callback.answer()

    return router


async def notify_subscribers(session, bot: Bot, calendar: Calendar, events: list[Event], heading: str) -> None:
    telegram_ids = (await session.scalars(select(User.telegram_id).join(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True), Subscription.muted.is_(False)))).all()
    for telegram_id in telegram_ids:
        for event in events[:10]:
            try:
                await bot.send_message(
                    telegram_id,
                    f"{heading}: {event.title}\n{display_time(event.start_utc, calendar.timezone)}\nCalendar: {calendar.name}",
                    reply_markup=event_confirm_keyboard(event.id),
                )
            except Exception:
                pass


async def notify_organizer_confirmation(bot: Bot, organizer_telegram_id: int, participant_name: str,
                                        event: Event, calendar: Calendar) -> None:
    try:
        await bot.send_message(
            organizer_telegram_id,
            f"✅ {participant_name} confirmed attendance:\n{event.title}\n"
            f"{display_time(event.start_utc, calendar.timezone)}\nCalendar: {calendar.name}",
        )
    except Exception:
        pass


def build_participant_router(db: Database, settings: Settings, organizer_bot: Bot) -> Router:
    router = Router(name="participant")

    @router.message(CommandStart(deep_link=True))
    async def deep_start(message: Message, command: CommandObject) -> None:
        token = command.args or ""
        async with db.sessions() as session:
            calendar = await invitation_calendar(session, token)
        if not calendar:
            await message.answer("This invitation is invalid or expired.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text=f"Subscribe to {calendar.name}", callback_data=f"subscribe:{token}")]])
        await message.answer(
            f"You were invited to {calendar.name} ({calendar.timezone}).",
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("subscribe:"))
    async def confirm(callback: CallbackQuery) -> None:
        try:
            async with db.sessions() as session:
                calendar = await subscribe(
                    session, callback.from_user.id, callback.data.split(":", 1)[1], settings.default_timezone)
            await callback.message.edit_text(
                f"Subscribed to {calendar.name}. Tap 📅 Upcoming to see events.")
            await callback.message.answer("Main menu:", reply_markup=participant_main_menu())
        except ValueError as exc:
            await callback.message.edit_text(str(exc))
        await callback.answer()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer("Welcome! Use the buttons below to manage your subscriptions.", reply_markup=participant_main_menu())

    @router.message(Command("help"))
    @router.message(F.text == PAR_HELP)
    async def help_handler(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(PARTICIPANT_HELP, reply_markup=participant_main_menu())

    @router.message(Command("cancel"))
    async def cancel_fsm(message: Message, state: FSMContext) -> None:
        if await state.get_state():
            await state.clear()
            await message.answer("Cancelled.", reply_markup=participant_main_menu())
        else:
            await message.answer("Nothing to cancel.")

    async def reply_upcoming(message: Message) -> None:
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            rows = await upcoming_for_user_with_status(session, message.from_user.id)
        tz = user.timezone if user else settings.default_timezone
        lines = []
        for event, calendar, confirmed in rows:
            status = " ✅" if confirmed else ""
            lines.append(f"{event.title} — {display_time(event.start_utc, tz)} ({calendar.name}){status}")
        await message.answer(
            "\n".join(lines) or "No upcoming events.",
            reply_markup=participant_main_menu(),
        )

    @router.message(Command("upcoming"))
    @router.message(F.text == PAR_UPCOMING)
    async def upcoming(message: Message, state: FSMContext) -> None:
        await state.clear()
        await reply_upcoming(message)

    @router.message(Command("confirm"))
    @router.message(F.text == PAR_CONFIRM)
    async def confirm_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        if command and command.args:
            await handle_confirm(message.from_user, int(command.args.strip()), message)
            return
        async with db.sessions() as session:
            rows = await upcoming_for_user_with_status(session, message.from_user.id)
        pending = [(e, c) for e, c, confirmed in rows if not confirmed]
        if not pending:
            await message.answer("No events waiting for confirmation.", reply_markup=participant_main_menu())
            return
        confirmed_ids = {e.id for e, _, confirmed in rows if confirmed}
        await message.answer(
            "Tap an event to confirm attendance:",
            reply_markup=upcoming_confirm_keyboard([e for e, _ in pending], confirmed_ids),
        )

    async def handle_confirm(user, event_id: int, reply_target: Message | CallbackQuery) -> None:
        name = participant_display_name(user)
        try:
            async with db.sessions() as session:
                event, calendar, owner, created = await confirm_event(
                    session, user.id, event_id, name, settings.default_timezone)
            if created:
                await notify_organizer_confirmation(organizer_bot, owner.telegram_id, name, event, calendar)
                text = f"Confirmed: {event.title}\n{display_time(event.start_utc, calendar.timezone)}"
            else:
                text = f"Already confirmed: {event.title}"
        except (ValueError, PermissionError) as exc:
            text = f"Error: {exc}"
        if isinstance(reply_target, CallbackQuery):
            await reply_target.message.edit_text(text)
            await reply_target.answer()
        else:
            await reply_target.answer(text, reply_markup=participant_main_menu())

    @router.callback_query(F.data.startswith("p_confirm:"))
    async def confirm_callback(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await handle_confirm(callback.from_user, int(callback.data.split(":", 1)[1]), callback)

    async def reply_subscriptions(message: Message) -> None:
        async with db.sessions() as session:
            data = await fetch_subscribed_calendars(session, message.from_user.id)
        await message.answer(
            "\n".join(f"{c.id}: {c.name} [{'muted' if s.muted else 'active'}]" for c, s in data) or "No subscriptions.",
            reply_markup=participant_main_menu(),
        )

    @router.message(Command("subscriptions"))
    @router.message(F.text == PAR_SUBSCRIPTIONS)
    async def subscriptions(message: Message, state: FSMContext) -> None:
        await state.clear()
        await reply_subscriptions(message)

    @router.message(Command("timezone"))
    @router.message(F.text == PAR_TIMEZONE)
    async def timezone_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                async with db.sessions() as session:
                    await set_timezone(session, message.from_user.id, command.args.strip(), settings.default_timezone)
                await message.answer("Timezone updated.", reply_markup=participant_main_menu())
            except ValueError as exc:
                await message.answer(f"Error: {exc}", reply_markup=participant_main_menu())
            return
        await state.clear()
        await state.set_state(ParticipantTimezone.timezone)
        await message.answer("Enter timezone (e.g. Europe/Moscow):", reply_markup=participant_main_menu())

    @router.message(ParticipantTimezone.timezone, ~F.text.in_(PARTICIPANT_BUTTONS))
    async def timezone_value(message: Message, state: FSMContext) -> None:
        try:
            async with db.sessions() as session:
                await set_timezone(session, message.from_user.id, message.text.strip(), settings.default_timezone)
            await message.answer("Timezone updated.", reply_markup=participant_main_menu())
        except ValueError as exc:
            await message.answer(f"Error: {exc}", reply_markup=participant_main_menu())
        await state.clear()

    async def pick_subscription(message: Message, prefix: str, prompt: str) -> None:
        async with db.sessions() as session:
            data = await fetch_subscribed_calendars(session, message.from_user.id)
        if not data:
            await message.answer("No subscriptions.", reply_markup=participant_main_menu())
            return
        calendars = [c for c, _ in data]
        await message.answer(prompt, reply_markup=calendars_keyboard(calendars, prefix))

    async def state_action(message: Message, calendar_id: int, action: str) -> None:
        try:
            async with db.sessions() as session:
                changed = await set_subscription_state(session, message.from_user.id, calendar_id, action)
            await message.answer("Updated." if changed else "Subscription not found.", reply_markup=participant_main_menu())
        except ValueError:
            await message.answer(f"Usage: /{action} CALENDAR_ID", reply_markup=participant_main_menu())

    @router.message(Command("mute"))
    @router.message(F.text == PAR_MUTE)
    async def mute_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        if command and command.args:
            await state_action(message, int(command.args.strip()), "mute")
            return
        await pick_subscription(message, "p_mute", "Choose a calendar to mute:")

    @router.message(Command("unmute"))
    @router.message(F.text == PAR_UNMUTE)
    async def unmute_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unmute")
            return
        await pick_subscription(message, "p_unmute", "Choose a calendar to unmute:")

    @router.message(Command("unsubscribe"))
    @router.message(F.text == PAR_UNSUBSCRIBE)
    async def unsubscribe_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        await state.clear()
        if command and command.args:
            await state_action(message, int(command.args.strip()), "unsubscribe")
            return
        await pick_subscription(message, "p_unsub", "Choose a calendar to unsubscribe from:")

    @router.callback_query(F.data.startswith("p_mute:"))
    async def mute_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "mute")
        await callback.message.edit_text("Muted." if changed else "Subscription not found.")
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unmute:"))
    async def unmute_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unmute")
        await callback.message.edit_text("Unmuted." if changed else "Subscription not found.")
        await callback.answer()

    @router.callback_query(F.data.startswith("p_unsub:"))
    async def unsub_pick(callback: CallbackQuery) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        async with db.sessions() as session:
            changed = await set_subscription_state(session, callback.from_user.id, calendar_id, "unsubscribe")
        await callback.message.edit_text("Unsubscribed." if changed else "Subscription not found.")
        await callback.answer()

    @router.message(Command("reminders"))
    @router.message(F.text == PAR_REMINDERS)
    async def reminders_start(message: Message, state: FSMContext, command: CommandObject | None = None) -> None:
        if command and command.args:
            await state.clear()
            try:
                parts = command.args.split(maxsplit=1)
                async with db.sessions() as session:
                    changed = await set_reminders(session, message.from_user.id, int(parts[0]), parts[1])
                await message.answer(
                    "Reminder preference saved for future jobs." if changed else "Subscription not found.",
                    reply_markup=participant_main_menu(),
                )
            except (ValueError, IndexError) as exc:
                await message.answer(f"Error: {exc or 'Usage: /reminders CALENDAR_ID 1440,30'}", reply_markup=participant_main_menu())
            return
        await state.clear()
        await pick_subscription(message, "p_remind", "Choose a calendar:")

    @router.callback_query(F.data.startswith("p_remind:"))
    async def reminders_calendar(callback: CallbackQuery, state: FSMContext) -> None:
        calendar_id = int(callback.data.split(":", 1)[1])
        await state.update_data(calendar_id=calendar_id)
        await state.set_state(ParticipantReminders.minutes)
        await callback.message.edit_text("Enter reminder minutes (comma-separated, e.g. 1440,30):")
        await callback.answer()

    @router.message(ParticipantReminders.minutes, ~F.text.in_(PARTICIPANT_BUTTONS))
    async def reminders_value(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        try:
            async with db.sessions() as session:
                changed = await set_reminders(session, message.from_user.id, data["calendar_id"], message.text.strip())
            await message.answer(
                "Reminder preference saved for future jobs." if changed else "Subscription not found.",
                reply_markup=participant_main_menu(),
            )
        except ValueError as exc:
            await message.answer(f"Error: {exc}", reply_markup=participant_main_menu())
        await state.clear()

    return router


async def configure_commands(organizer: Bot, participant: Bot) -> None:
    await organizer.set_my_commands([
        BotCommand(command="calendars", description="List calendars"),
        BotCommand(command="newevent", description="Create event"),
        BotCommand(command="help", description="Show help"),
    ])
    await participant.set_my_commands([
        BotCommand(command="upcoming", description="Upcoming events"),
        BotCommand(command="confirm", description="Confirm attendance"),
        BotCommand(command="subscriptions", description="My calendars"),
        BotCommand(command="help", description="Show help"),
    ])
