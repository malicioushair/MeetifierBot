from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import validate_timezone
from .db import Calendar, Event, Invitation, NotificationJob, Subscription, User, utcnow


def parse_minutes(value: str) -> list[int]:
    try:
        result = sorted({int(x.strip()) for x in value.split(",") if x.strip()}, reverse=True)
    except ValueError as exc:
        raise ValueError("Reminders must be comma-separated minutes, e.g. 1440,30") from exc
    if not result or any(x < 0 or x > 525600 for x in result):
        raise ValueError("Reminder minutes must be between 0 and 525600")
    return result


def local_to_utc(value: str, timezone_name: str) -> datetime:
    try:
        local = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(timezone_name))
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD HH:MM") from exc
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def display_time(value: datetime, timezone_name: str) -> str:
    aware = value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(timezone_name))
    return aware.strftime("%Y-%m-%d %H:%M") + f" ({timezone_name})"


async def get_or_create_user(session: AsyncSession, telegram_id: int, default_timezone: str) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(telegram_id=telegram_id, timezone=default_timezone)
        session.add(user)
        await session.flush()
    return user


async def create_calendar(session: AsyncSession, telegram_id: int, name: str, timezone_name: str, default_tz: str) -> Calendar:
    validate_timezone(timezone_name)
    user = await get_or_create_user(session, telegram_id, default_tz)
    calendar = Calendar(owner_user_id=user.id, name=name.strip(), timezone=timezone_name)
    session.add(calendar)
    await session.commit()
    return calendar


async def owned_calendar(session: AsyncSession, telegram_id: int, calendar_id: int) -> Calendar | None:
    return await session.scalar(select(Calendar).join(User, User.id == Calendar.owner_user_id).where(
        Calendar.id == calendar_id, User.telegram_id == telegram_id))


async def create_events(session: AsyncSession, owner_telegram_id: int, calendar_id: int, title: str,
                        local_start: str, duration_minutes: int, weeks: int = 1) -> list[Event]:
    calendar = await owned_calendar(session, owner_telegram_id, calendar_id)
    if not calendar:
        raise PermissionError("Calendar not found or not owned by you")
    if not 1 <= duration_minutes <= 10080 or not 1 <= weeks <= 52:
        raise ValueError("Duration must be 1..10080 minutes and weeks must be 1..52")
    start = local_to_utc(local_start, calendar.timezone)
    group = str(uuid.uuid4()) if weeks > 1 else None
    events = []
    for week in range(weeks):
        occurrence_start = start + timedelta(weeks=week)
        event = Event(calendar_id=calendar.id, title=title.strip(), start_utc=occurrence_start,
                      end_utc=occurrence_start + timedelta(minutes=duration_minutes), recurrence_group=group)
        session.add(event)
        events.append(event)
    await session.flush()
    for event in events:
        await create_jobs_for_event(session, event, calendar)
    await session.commit()
    return events


async def create_jobs_for_event(session: AsyncSession, event: Event, calendar: Calendar) -> None:
    subscriptions = (await session.scalars(select(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True)))).all()
    now = utcnow()
    for sub in subscriptions:
        minutes = parse_minutes(sub.custom_reminder_minutes or calendar.reminder_minutes)
        for minute in minutes:
            scheduled = event.start_utc - timedelta(minutes=minute)
            if scheduled >= now:
                session.add(NotificationJob(event_id=event.id, user_id=sub.user_id, kind=f"reminder:{minute}",
                                            event_version=event.version, scheduled_at=scheduled))


async def make_invitation(session: AsyncSession, owner_id: int, calendar_id: int) -> Invitation:
    if not await owned_calendar(session, owner_id, calendar_id):
        raise PermissionError("Calendar not found or not owned by you")
    invite = Invitation(token=secrets.token_urlsafe(24), calendar_id=calendar_id)
    session.add(invite)
    await session.commit()
    return invite


async def invitation_calendar(session: AsyncSession, token: str) -> Calendar | None:
    return await session.scalar(select(Calendar).join(Invitation).where(
        Invitation.token == token,
        (Invitation.expires_at.is_(None)) | (Invitation.expires_at > utcnow())))


async def subscribe(session: AsyncSession, telegram_id: int, token: str, default_tz: str) -> Calendar:
    calendar = await invitation_calendar(session, token)
    if not calendar:
        raise ValueError("Invitation is invalid or expired")
    user = await get_or_create_user(session, telegram_id, default_tz)
    sub = await session.scalar(select(Subscription).where(
        Subscription.user_id == user.id, Subscription.calendar_id == calendar.id))
    if sub:
        sub.active, sub.muted = True, False
    else:
        sub = Subscription(user_id=user.id, calendar_id=calendar.id)
        session.add(sub)
    await session.flush()
    future_events = (await session.scalars(select(Event).where(
        Event.calendar_id == calendar.id, Event.status == "active", Event.start_utc > utcnow()))).all()
    for event in future_events:
        await create_jobs_for_subscriber(session, event, calendar, sub)
    await session.commit()
    return calendar


async def create_jobs_for_subscriber(session: AsyncSession, event: Event, calendar: Calendar, sub: Subscription) -> None:
    for minute in parse_minutes(sub.custom_reminder_minutes or calendar.reminder_minutes):
        scheduled = event.start_utc - timedelta(minutes=minute)
        if scheduled >= utcnow():
            existing = await session.scalar(select(NotificationJob.id).where(
                NotificationJob.event_id == event.id, NotificationJob.user_id == sub.user_id,
                NotificationJob.kind == f"reminder:{minute}", NotificationJob.event_version == event.version))
            if not existing:
                session.add(NotificationJob(event_id=event.id, user_id=sub.user_id, kind=f"reminder:{minute}",
                                            event_version=event.version, scheduled_at=scheduled))


async def change_event(session: AsyncSession, owner_id: int, event_id: int, new_local_start: str | None = None,
                       cancel: bool = False) -> Event:
    event = await session.scalar(select(Event).join(Calendar).join(User).where(
        Event.id == event_id, User.telegram_id == owner_id))
    if not event:
        raise PermissionError("Event not found or not owned by you")
    calendar = await session.get(Calendar, event.calendar_id)
    await session.execute(update(NotificationJob).where(
        NotificationJob.event_id == event.id, NotificationJob.state == "pending").values(state="obsolete"))
    event.version += 1
    if cancel:
        event.status = "cancelled"
    else:
        duration = event.end_utc - event.start_utc
        event.start_utc = local_to_utc(new_local_start or "", calendar.timezone)
        event.end_utc = event.start_utc + duration
        await create_jobs_for_event(session, event, calendar)
    await session.commit()
    return event


async def upcoming_for_user(session: AsyncSession, telegram_id: int, limit: int = 10) -> list[tuple[Event, Calendar]]:
    rows = await session.execute(select(Event, Calendar).join(Calendar).join(Subscription).join(User).where(
        User.telegram_id == telegram_id, Subscription.active.is_(True), Event.status == "active",
        Event.start_utc > utcnow()).order_by(Event.start_utc).limit(limit))
    return list(rows.tuples())


async def set_timezone(session: AsyncSession, telegram_id: int, timezone_name: str, default_tz: str) -> User:
    validate_timezone(timezone_name)
    user = await get_or_create_user(session, telegram_id, default_tz)
    user.timezone = timezone_name
    await session.commit()
    return user


async def set_subscription_state(session: AsyncSession, telegram_id: int, calendar_id: int, action: str) -> bool:
    sub = await session.scalar(select(Subscription).join(User).where(
        User.telegram_id == telegram_id, Subscription.calendar_id == calendar_id))
    if not sub:
        return False
    if action == "mute": sub.muted = True
    elif action == "unmute": sub.muted = False
    elif action == "unsubscribe": sub.active = False
    else: raise ValueError("Unknown action")
    if not sub.active:
        await session.execute(update(NotificationJob).where(
            NotificationJob.user_id == sub.user_id,
            NotificationJob.event_id.in_(select(Event.id).where(Event.calendar_id == calendar_id)),
            NotificationJob.state == "pending").values(state="obsolete"))
    await session.commit()
    return True


async def set_reminders(session: AsyncSession, telegram_id: int, calendar_id: int, value: str) -> bool:
    parse_minutes(value)
    sub = await session.scalar(select(Subscription).join(User).where(
        User.telegram_id == telegram_id, Subscription.calendar_id == calendar_id, Subscription.active.is_(True)))
    if not sub: return False
    sub.custom_reminder_minutes = value
    await session.commit()
    return True
