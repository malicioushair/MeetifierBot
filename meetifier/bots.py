from __future__ import annotations

from datetime import timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from .config import Settings
from .db import Calendar, Database, Event, Subscription, User, utcnow
from .service import (change_event, create_calendar, create_events, display_time, invitation_calendar,
                      make_invitation, set_reminders, set_subscription_state, set_timezone, subscribe,
                      upcoming_for_user)

ORGANIZER_HELP = """Organizer commands:
/newcalendar Name | Europe/Moscow
/calendars
/newevent CALENDAR_ID | Title | 2026-09-01 18:30 | DURATION_MINUTES | WEEKS
/events CALENDAR_ID
/invite CALENDAR_ID
/reschedule EVENT_ID | 2026-09-02 19:00
/cancel EVENT_ID
Use WEEKS=1 for one-time events or 2..52 for weekly recurrence."""

PARTICIPANT_HELP = """Participant commands:
/upcoming - next events
/timezone Europe/Moscow
/reminders CALENDAR_ID 1440,30
/mute CALENDAR_ID
/unmute CALENDAR_ID
/unsubscribe CALENDAR_ID
/subscriptions"""


def split_args(command: CommandObject, count_min: int, count_max: int | None = None) -> list[str]:
    parts = [x.strip() for x in (command.args or "").split("|")]
    maximum = count_max or count_min
    if len(parts) < count_min or len(parts) > maximum or any(not x for x in parts):
        raise ValueError("Wrong command format. Send /help for examples.")
    return parts


def build_organizer_router(db: Database, settings: Settings, participant_bot: Bot) -> Router:
    router = Router(name="organizer")

    @router.message(CommandStart())
    @router.message(Command("help"))
    async def help_handler(message: Message) -> None: await message.answer(ORGANIZER_HELP)

    @router.message(Command("newcalendar"))
    async def new_calendar(message: Message, command: CommandObject) -> None:
        try:
            name, tz = split_args(command, 2)
            async with db.sessions() as session:
                calendar = await create_calendar(session, message.from_user.id, name, tz, settings.default_timezone)
            await message.answer(f"Calendar created: {calendar.name} (ID {calendar.id})")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("calendars"))
    async def calendars(message: Message) -> None:
        async with db.sessions() as session:
            rows = (await session.scalars(select(Calendar).join(User).where(User.telegram_id == message.from_user.id))).all()
        await message.answer("\n".join(f"{x.id}: {x.name} [{x.timezone}]" for x in rows) or "No calendars yet.")

    @router.message(Command("newevent"))
    async def new_event(message: Message, command: CommandObject) -> None:
        try:
            parts = split_args(command, 4, 5)
            calendar_id, title, start, duration = parts[:4]
            weeks = int(parts[4]) if len(parts) == 5 else 1
            async with db.sessions() as session:
                events = await create_events(session, message.from_user.id, int(calendar_id), title, start, int(duration), weeks)
                calendar = await session.get(Calendar, int(calendar_id))
                await notify_subscribers(session, participant_bot, calendar, events, "New event")
            await message.answer(f"Created {len(events)} event(s). IDs: {', '.join(str(e.id) for e in events)}")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("events"))
    async def events(message: Message, command: CommandObject) -> None:
        try:
            calendar_id = int((command.args or "").strip())
            async with db.sessions() as session:
                calendar = await session.scalar(select(Calendar).join(User).where(
                    Calendar.id == calendar_id, User.telegram_id == message.from_user.id))
                if not calendar: raise PermissionError("Calendar not found or not owned by you")
                rows = (await session.scalars(select(Event).where(Event.calendar_id == calendar.id,
                    Event.start_utc > utcnow()).order_by(Event.start_utc).limit(20))).all()
            await message.answer("\n".join(f"{e.id}: {e.title} — {display_time(e.start_utc, calendar.timezone)} [{e.status}]" for e in rows) or "No future events.")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("invite"))
    async def invite(message: Message, command: CommandObject) -> None:
        try:
            async with db.sessions() as session:
                invitation = await make_invitation(session, message.from_user.id, int((command.args or "").strip()))
            await message.answer(f"Share this link:\nhttps://t.me/{settings.participant_bot_username}?start={invitation.token}")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("reschedule"))
    async def reschedule(message: Message, command: CommandObject) -> None:
        try:
            event_id, new_start = split_args(command, 2)
            async with db.sessions() as session:
                event = await change_event(session, message.from_user.id, int(event_id), new_start)
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "Event rescheduled")
            await message.answer("Event rescheduled and subscribers notified.")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("cancel"))
    async def cancel(message: Message, command: CommandObject) -> None:
        try:
            async with db.sessions() as session:
                event = await change_event(session, message.from_user.id, int((command.args or "").strip()), cancel=True)
                calendar = await session.get(Calendar, event.calendar_id)
                await notify_subscribers(session, participant_bot, calendar, [event], "Event cancelled")
            await message.answer("Event cancelled and subscribers notified.")
        except (ValueError, PermissionError) as exc: await message.answer(f"Error: {exc}")
    return router


async def notify_subscribers(session, bot: Bot, calendar: Calendar, events: list[Event], heading: str) -> None:
    telegram_ids = (await session.scalars(select(User.telegram_id).join(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True), Subscription.muted.is_(False)))).all()
    for telegram_id in telegram_ids:
        for event in events[:10]:
            try: await bot.send_message(telegram_id, f"{heading}: {event.title}\n{display_time(event.start_utc, calendar.timezone)}\nCalendar: {calendar.name}")
            except Exception: pass


def build_participant_router(db: Database, settings: Settings) -> Router:
    router = Router(name="participant")

    @router.message(CommandStart(deep_link=True))
    async def deep_start(message: Message, command: CommandObject) -> None:
        token = command.args or ""
        async with db.sessions() as session: calendar = await invitation_calendar(session, token)
        if not calendar:
            await message.answer("This invitation is invalid or expired."); return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text=f"Subscribe to {calendar.name}", callback_data=f"subscribe:{token}")]])
        await message.answer(f"You were invited to {calendar.name} ({calendar.timezone}).", reply_markup=keyboard)

    @router.callback_query(F.data.startswith("subscribe:"))
    async def confirm(callback: CallbackQuery) -> None:
        try:
            async with db.sessions() as session:
                calendar = await subscribe(session, callback.from_user.id, callback.data.split(":", 1)[1], settings.default_timezone)
            await callback.message.edit_text(f"Subscribed to {calendar.name}. Use /upcoming to see events.")
        except ValueError as exc: await callback.message.edit_text(str(exc))
        await callback.answer()

    @router.message(CommandStart())
    @router.message(Command("help"))
    async def help_handler(message: Message) -> None: await message.answer(PARTICIPANT_HELP)

    @router.message(Command("upcoming"))
    async def upcoming(message: Message) -> None:
        async with db.sessions() as session:
            user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
            rows = await upcoming_for_user(session, message.from_user.id)
        tz = user.timezone if user else settings.default_timezone
        await message.answer("\n".join(f"{e.title} — {display_time(e.start_utc, tz)} ({c.name})" for e, c in rows) or "No upcoming events.")

    @router.message(Command("timezone"))
    async def timezone_handler(message: Message, command: CommandObject) -> None:
        try:
            async with db.sessions() as session: await set_timezone(session, message.from_user.id, (command.args or "").strip(), settings.default_timezone)
            await message.answer("Timezone updated.")
        except ValueError as exc: await message.answer(f"Error: {exc}")

    @router.message(Command("subscriptions"))
    async def subscriptions(message: Message) -> None:
        async with db.sessions() as session:
            rows = await session.execute(select(Calendar, Subscription).join(Subscription).join(User).where(
                User.telegram_id == message.from_user.id, Subscription.active.is_(True)))
            data = rows.tuples().all()
        await message.answer("\n".join(f"{c.id}: {c.name} [{'muted' if s.muted else 'active'}]" for c, s in data) or "No subscriptions.")

    async def state_command(message: Message, command: CommandObject, action: str) -> None:
        try:
            async with db.sessions() as session: changed = await set_subscription_state(session, message.from_user.id, int((command.args or "").strip()), action)
            await message.answer("Updated." if changed else "Subscription not found.")
        except ValueError: await message.answer("Usage: /" + action + " CALENDAR_ID")

    @router.message(Command("mute"))
    async def mute(message: Message, command: CommandObject) -> None: await state_command(message, command, "mute")
    @router.message(Command("unmute"))
    async def unmute(message: Message, command: CommandObject) -> None: await state_command(message, command, "unmute")
    @router.message(Command("unsubscribe"))
    async def unsubscribe_handler(message: Message, command: CommandObject) -> None: await state_command(message, command, "unsubscribe")

    @router.message(Command("reminders"))
    async def reminders(message: Message, command: CommandObject) -> None:
        try:
            parts = (command.args or "").split(maxsplit=1)
            async with db.sessions() as session: changed = await set_reminders(session, message.from_user.id, int(parts[0]), parts[1])
            await message.answer("Reminder preference saved for future jobs." if changed else "Subscription not found.")
        except (ValueError, IndexError) as exc: await message.answer(f"Error: {exc or 'Usage: /reminders CALENDAR_ID 1440,30'}")
    return router


async def configure_commands(organizer: Bot, participant: Bot) -> None:
    await organizer.set_my_commands([BotCommand(command="calendars", description="List calendars"), BotCommand(command="newevent", description="Create event"), BotCommand(command="help", description="Show help")])
    await participant.set_my_commands([BotCommand(command="upcoming", description="Upcoming events"), BotCommand(command="subscriptions", description="My calendars"), BotCommand(command="help", description="Show help")])
