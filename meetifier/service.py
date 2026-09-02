from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import format_timezone_offset, parse_timezone_offset, tzinfo_from_offset, validate_timezone
from .db import (
    DEFAULT_CONFIRMATION_HOURS,
    DEFAULT_NOTIFICATION_MINUTES,
    Calendar,
    Event,
    EventConfirmation,
    EventOccurrence,
    Invitation,
    NotificationJob,
    Subscription,
    User,
    utcnow,
)
from .i18n import DEFAULT_LOCALE, normalize_locale
from .recurrence import RecurrenceRule

JOB_KIND_CONFIRM = "confirm"
JOB_KIND_REMINDER = "reminder"


def parse_minutes(value: str) -> list[int]:
    try:
        result = sorted({int(x.strip()) for x in value.split(",") if x.strip()}, reverse=True)
    except ValueError as exc:
        raise ValueError("Minutes must be comma-separated integers, e.g. 60 or 120,30") from exc
    if not result or any(x < 0 or x > 525600 for x in result):
        raise ValueError("Minutes must be between 0 and 525600")
    return result


def parse_hours(value: str) -> list[int]:
    try:
        result = sorted({int(x.strip()) for x in value.split(",") if x.strip()}, reverse=True)
    except ValueError as exc:
        raise ValueError("Hours must be comma-separated integers, e.g. 24 or 48,24") from exc
    if not result or any(x < 0 or x > 8760 for x in result):
        raise ValueError("Hours must be between 0 and 8760")
    return result


def confirmation_offsets(calendar: Calendar) -> list[int]:
    """Lead times in hours before the event for attendance confirmation asks."""
    return parse_hours(calendar.confirmation_hours or DEFAULT_CONFIRMATION_HOURS)


def notification_offsets(sub: Subscription) -> list[int]:
    return parse_minutes(sub.notification_minutes or DEFAULT_NOTIFICATION_MINUTES)


def job_kind(kind: str, offset: int) -> str:
    return f"{kind}:{offset}"


def local_to_utc(value: str, tz_offset_hours: int | str) -> datetime:
    try:
        local = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo_from_offset(tz_offset_hours))
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD HH:MM") from exc
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def display_time(value: datetime, tz_offset_hours: int | str) -> str:
    hours = parse_timezone_offset(tz_offset_hours)
    aware = value.replace(tzinfo=timezone.utc).astimezone(tzinfo_from_offset(hours))
    return aware.strftime("%Y-%m-%d %H:%M") + f" ({format_timezone_offset(hours)})"


def week_bounds_utc(tz_offset_hours: int | str) -> tuple[datetime, datetime]:
    tz = tzinfo_from_offset(tz_offset_hours)
    now_local = datetime.now(tz)
    week_start = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    return (
        week_start.astimezone(timezone.utc).replace(tzinfo=None),
        week_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _apply_occurrence_range(query, range_mode: str, tz_offset_hours: int | str, now: datetime):
    if range_mode == "week":
        start, end = week_bounds_utc(tz_offset_hours)
        return query.where(EventOccurrence.start_utc >= start, EventOccurrence.start_utc < end)
    if range_mode in {"next", "future"}:
        return query.where(EventOccurrence.start_utc > now)
    raise ValueError("Range must be 'next', 'week', or 'future'")


async def calendar_events(session: AsyncSession, calendar_id: int, range_mode: str,
                          tz_offset_hours: int | str) -> list[EventOccurrence]:
    if range_mode not in {"next", "week"}:
        raise ValueError("Range must be 'next' or 'week'")
    now = utcnow()
    query = (
        select(EventOccurrence)
        .join(Event)
        .options(selectinload(EventOccurrence.event))
        .where(
            Event.calendar_id == calendar_id,
            Event.status == "active",
            EventOccurrence.status == "active",
        )
    )
    query = _apply_occurrence_range(query, range_mode, tz_offset_hours, now)
    query = query.order_by(EventOccurrence.start_utc)
    if range_mode == "next":
        query = query.limit(1)
    return list((await session.scalars(query)).all())


async def calendar_event_series(session: AsyncSession, calendar_id: int, range_mode: str = "future",
                                tz_offset_hours: int | str = 0) -> list[Event]:
    """Event series in a calendar that have at least one occurrence in the given range."""
    if range_mode not in {"next", "week", "future"}:
        raise ValueError("Range must be 'next', 'week', or 'future'")
    now = utcnow()
    matching = (
        select(EventOccurrence.event_id, func.min(EventOccurrence.start_utc).label("soonest"))
        .join(Event)
        .where(
            Event.calendar_id == calendar_id,
            Event.status == "active",
            EventOccurrence.status == "active",
        )
    )
    matching = _apply_occurrence_range(matching, range_mode if range_mode != "next" else "future",
                                       tz_offset_hours, now)
    matching = matching.group_by(EventOccurrence.event_id).subquery()
    query = (
        select(Event)
        .join(matching, Event.id == matching.c.event_id)
        .order_by(matching.c.soonest, Event.title)
    )
    return list((await session.scalars(query)).all())


async def event_occurrences(session: AsyncSession, event_id: int, range_mode: str = "future",
                            tz_offset_hours: int | str = 0, limit: int = 50) -> list[EventOccurrence]:
    """Upcoming (or in-range) occurrences for one event series."""
    if range_mode not in {"next", "week", "future"}:
        raise ValueError("Range must be 'next', 'week', or 'future'")
    now = utcnow()
    query = (
        select(EventOccurrence)
        .options(selectinload(EventOccurrence.event))
        .where(EventOccurrence.event_id == event_id, EventOccurrence.status == "active")
    )
    query = _apply_occurrence_range(query, range_mode, tz_offset_hours, now)
    query = query.order_by(EventOccurrence.start_utc)
    if range_mode == "next":
        query = query.limit(1)
    else:
        query = query.limit(limit)
    return list((await session.scalars(query)).all())


async def get_or_create_user(session: AsyncSession, telegram_id: int, default_timezone: int | str,
                             locale: str | None = None) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = User(
            telegram_id=telegram_id,
            timezone=parse_timezone_offset(default_timezone),
            locale=normalize_locale(locale) if locale else DEFAULT_LOCALE,
        )
        session.add(user)
        await session.flush()
    return user


async def get_user_locale(session: AsyncSession, telegram_id: int, default_timezone: int | str = 0) -> str:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        user = await get_or_create_user(session, telegram_id, default_timezone)
        await session.commit()
    return normalize_locale(user.locale)


async def set_locale(session: AsyncSession, telegram_id: int, locale: str, default_tz: int | str) -> User:
    user = await get_or_create_user(session, telegram_id, default_tz)
    user.locale = normalize_locale(locale)
    await session.commit()
    return user


async def create_calendar(session: AsyncSession, telegram_id: int, name: str, tz_offset_hours: int | str,
                          default_tz: int | str, confirmation_hours: str | None = None) -> Calendar:
    hours = validate_timezone(tz_offset_hours)
    user = await get_or_create_user(session, telegram_id, default_tz)
    confirm = confirmation_hours if confirmation_hours is not None else DEFAULT_CONFIRMATION_HOURS
    parse_hours(confirm)
    calendar = Calendar(
        owner_user_id=user.id,
        name=name.strip(),
        timezone=hours,
        confirmation_hours=confirm,
    )
    session.add(calendar)
    await session.commit()
    return calendar


async def owned_calendar(session: AsyncSession, telegram_id: int, calendar_id: int) -> Calendar | None:
    return await session.scalar(select(Calendar).join(User, User.id == Calendar.owner_user_id).where(
        Calendar.id == calendar_id, User.telegram_id == telegram_id))


async def create_events(
    session: AsyncSession,
    owner_telegram_id: int,
    calendar_id: int,
    title: str,
    local_start: str,
    duration_minutes: int,
    weeks: int | None = None,
    rule: RecurrenceRule | None = None,
) -> list[EventOccurrence]:
    from .recurrence import generate_starts_utc, parse_local_naive, rule_from_legacy_weeks

    calendar = await owned_calendar(session, owner_telegram_id, calendar_id)
    if not calendar:
        raise PermissionError("Calendar not found or not owned by you")
    if rule is None:
        if weeks is None:
            weeks = 1
        anchor_weekday = parse_local_naive(local_start).weekday()
        rule = rule_from_legacy_weeks(weeks, anchor_weekday)
    starts = generate_starts_utc(rule, local_start, calendar.timezone, duration_minutes)
    event = Event(calendar_id=calendar.id, title=title.strip(), recurrence_json=rule.to_json())
    session.add(event)
    await session.flush()
    occurrences: list[EventOccurrence] = []
    for start_utc, end_utc in starts:
        occurrence = EventOccurrence(event_id=event.id, start_utc=start_utc, end_utc=end_utc)
        session.add(occurrence)
        occurrences.append(occurrence)
    await session.flush()
    for occurrence in occurrences:
        await session.refresh(occurrence, attribute_names=["event"])
        await create_jobs_for_occurrence(session, occurrence, calendar)
    await session.commit()
    for occurrence in occurrences:
        await session.refresh(occurrence, attribute_names=["event"])
    return occurrences


async def create_jobs_for_occurrence(session: AsyncSession, occurrence: EventOccurrence, calendar: Calendar) -> None:
    subscriptions = (await session.scalars(select(Subscription).where(
        Subscription.calendar_id == calendar.id, Subscription.active.is_(True)))).all()
    now = utcnow()
    confirm_hours = confirmation_offsets(calendar)
    for sub in subscriptions:
        for hour in confirm_hours:
            scheduled = occurrence.start_utc - timedelta(hours=hour)
            if scheduled >= now:
                session.add(NotificationJob(
                    occurrence_id=occurrence.id, user_id=sub.user_id,
                    kind=job_kind(JOB_KIND_CONFIRM, hour),
                    occurrence_version=occurrence.version, scheduled_at=scheduled,
                ))
        for minute in notification_offsets(sub):
            scheduled = occurrence.start_utc - timedelta(minutes=minute)
            if scheduled >= now:
                session.add(NotificationJob(
                    occurrence_id=occurrence.id, user_id=sub.user_id,
                    kind=job_kind(JOB_KIND_REMINDER, minute),
                    occurrence_version=occurrence.version, scheduled_at=scheduled,
                ))


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


async def subscribe(session: AsyncSession, telegram_id: int, token: str, default_tz: int | str) -> Calendar:
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
    future = (await session.scalars(
        select(EventOccurrence).join(Event).where(
            Event.calendar_id == calendar.id,
            Event.status == "active",
            EventOccurrence.status == "active",
            EventOccurrence.start_utc > utcnow(),
        )
    )).all()
    for occurrence in future:
        await create_jobs_for_subscriber(session, occurrence, calendar, sub)
    await session.commit()
    return calendar


async def create_jobs_for_subscriber(
    session: AsyncSession, occurrence: EventOccurrence, calendar: Calendar, sub: Subscription,
) -> None:
    now = utcnow()
    kinds_offsets = (
        [(JOB_KIND_CONFIRM, h, "hours") for h in confirmation_offsets(calendar)]
        + [(JOB_KIND_REMINDER, m, "minutes") for m in notification_offsets(sub)]
    )
    for kind, offset, unit in kinds_offsets:
        scheduled = (
            occurrence.start_utc - timedelta(hours=offset)
            if unit == "hours"
            else occurrence.start_utc - timedelta(minutes=offset)
        )
        if scheduled < now:
            continue
        kind_value = job_kind(kind, offset)
        existing = await session.scalar(select(NotificationJob.id).where(
            NotificationJob.occurrence_id == occurrence.id, NotificationJob.user_id == sub.user_id,
            NotificationJob.kind == kind_value,
            NotificationJob.occurrence_version == occurrence.version))
        if not existing:
            session.add(NotificationJob(
                occurrence_id=occurrence.id, user_id=sub.user_id, kind=kind_value,
                occurrence_version=occurrence.version, scheduled_at=scheduled,
            ))


async def change_event(
    session: AsyncSession,
    owner_id: int,
    occurrence_id: int,
    new_local_start: str | None = None,
    cancel: bool = False,
    scope: str = "one",
) -> list[EventOccurrence]:
    """Change one occurrence or this and all following active occurrences in the series."""
    if scope not in {"one", "following"}:
        raise ValueError("Scope must be 'one' or 'following'")
    occurrence = await session.scalar(
        select(EventOccurrence)
        .join(Event)
        .join(Calendar)
        .join(User)
        .options(selectinload(EventOccurrence.event))
        .where(EventOccurrence.id == occurrence_id, User.telegram_id == owner_id)
    )
    if not occurrence:
        raise PermissionError("Event not found or not owned by you")
    calendar = await session.get(Calendar, occurrence.event.calendar_id)
    targets = [occurrence]
    if scope == "following":
        following = list((await session.scalars(
            select(EventOccurrence)
            .options(selectinload(EventOccurrence.event))
            .where(
                EventOccurrence.event_id == occurrence.event_id,
                EventOccurrence.status == "active",
                EventOccurrence.start_utc > occurrence.start_utc,
            )
            .order_by(EventOccurrence.start_utc)
        )).all())
        targets.extend(following)

    delta: timedelta | None = None
    if not cancel:
        new_start = local_to_utc(new_local_start or "", calendar.timezone)
        delta = new_start - occurrence.start_utc

    changed: list[EventOccurrence] = []
    for target in targets:
        await session.execute(update(NotificationJob).where(
            NotificationJob.occurrence_id == target.id, NotificationJob.state == "pending",
        ).values(state="obsolete"))
        target.version += 1
        await session.execute(delete(EventConfirmation).where(EventConfirmation.occurrence_id == target.id))
        if cancel:
            target.status = "cancelled"
        else:
            assert delta is not None
            duration = target.end_utc - target.start_utc
            target.start_utc = target.start_utc + delta
            target.end_utc = target.start_utc + duration
            await create_jobs_for_occurrence(session, target, calendar)
        changed.append(target)
    await session.commit()
    for target in changed:
        await session.refresh(target, attribute_names=["event"])
    return changed


async def upcoming_for_user(session: AsyncSession, telegram_id: int, range_mode: str = "week",
                            default_tz: int | str = 0, limit: int = 50) -> list[tuple[EventOccurrence, Calendar]]:
    if range_mode not in {"next", "week", "future"}:
        raise ValueError("Range must be 'next', 'week', or 'future'")
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    tz = user.timezone if user else default_tz
    now = utcnow()
    query = (
        select(EventOccurrence, Calendar)
        .join(Event, EventOccurrence.event_id == Event.id)
        .join(Calendar, Event.calendar_id == Calendar.id)
        .join(Subscription, Subscription.calendar_id == Calendar.id)
        .join(User, User.id == Subscription.user_id)
        .options(selectinload(EventOccurrence.event))
        .where(
            User.telegram_id == telegram_id,
            Subscription.active.is_(True),
            Event.status == "active",
            EventOccurrence.status == "active",
        )
    )
    if range_mode == "next":
        query = query.where(EventOccurrence.start_utc > now).order_by(EventOccurrence.start_utc).limit(1)
    elif range_mode == "week":
        start, end = week_bounds_utc(tz)
        query = query.where(
            EventOccurrence.start_utc >= start, EventOccurrence.start_utc < end,
        ).order_by(EventOccurrence.start_utc).limit(limit)
    else:
        query = query.where(EventOccurrence.start_utc > now).order_by(EventOccurrence.start_utc).limit(limit)
    rows = await session.execute(query)
    return list(rows.tuples())


async def set_timezone(session: AsyncSession, telegram_id: int, tz_offset_hours: int | str,
                       default_tz: int | str) -> User:
    hours = validate_timezone(tz_offset_hours)
    user = await get_or_create_user(session, telegram_id, default_tz)
    user.timezone = hours
    await session.commit()
    return user


async def set_subscription_state(session: AsyncSession, telegram_id: int, calendar_id: int, action: str) -> bool:
    sub = await session.scalar(select(Subscription).join(User).where(
        User.telegram_id == telegram_id, Subscription.calendar_id == calendar_id))
    if not sub:
        return False
    if action == "mute":
        sub.muted = True
    elif action == "unmute":
        sub.muted = False
    elif action == "unsubscribe":
        sub.active = False
    else:
        raise ValueError("Unknown action")
    if not sub.active:
        occurrence_ids = select(EventOccurrence.id).join(Event).where(Event.calendar_id == calendar_id)
        await session.execute(update(NotificationJob).where(
            NotificationJob.user_id == sub.user_id,
            NotificationJob.occurrence_id.in_(occurrence_ids),
            NotificationJob.state == "pending",
        ).values(state="obsolete"))
    await session.commit()
    return True


async def confirm_event(session: AsyncSession, telegram_id: int, occurrence_id: int, display_name: str,
                        default_tz: int | str) -> tuple[EventOccurrence, Calendar, User, bool]:
    user = await get_or_create_user(session, telegram_id, default_tz)
    occurrence = await session.scalar(
        select(EventOccurrence)
        .options(selectinload(EventOccurrence.event))
        .where(
            EventOccurrence.id == occurrence_id,
            EventOccurrence.status == "active",
            EventOccurrence.start_utc > utcnow(),
        )
    )
    if not occurrence:
        raise ValueError("Event not found or no longer active")
    calendar = await session.get(Calendar, occurrence.event.calendar_id)
    sub = await session.scalar(select(Subscription).where(
        Subscription.user_id == user.id, Subscription.calendar_id == calendar.id, Subscription.active.is_(True)))
    if not sub:
        raise PermissionError("You are not subscribed to this calendar")
    existing = await session.scalar(select(EventConfirmation).where(
        EventConfirmation.occurrence_id == occurrence.id, EventConfirmation.user_id == user.id))
    if existing:
        return occurrence, calendar, await session.get(User, calendar.owner_user_id), False
    session.add(EventConfirmation(
        occurrence_id=occurrence.id, user_id=user.id,
        display_name=display_name.strip() or str(telegram_id),
    ))
    await session.commit()
    await session.refresh(occurrence, attribute_names=["event"])
    return occurrence, calendar, await session.get(User, calendar.owner_user_id), True


async def confirmations_for_event(session: AsyncSession, owner_telegram_id: int,
                                  occurrence_id: int) -> list[EventConfirmation]:
    occurrence = await session.scalar(
        select(EventOccurrence).join(Event).join(Calendar).join(User).where(
            EventOccurrence.id == occurrence_id, User.telegram_id == owner_telegram_id))
    if not occurrence:
        raise PermissionError("Event not found or not owned by you")
    return list((await session.scalars(select(EventConfirmation).where(
        EventConfirmation.occurrence_id == occurrence_id).order_by(EventConfirmation.confirmed_at))).all())


async def confirmed_occurrence_ids(session: AsyncSession, user_id: int, occurrence_ids: list[int]) -> set[int]:
    if not occurrence_ids:
        return set()
    rows = await session.scalars(select(EventConfirmation.occurrence_id).where(
        EventConfirmation.user_id == user_id, EventConfirmation.occurrence_id.in_(occurrence_ids)))
    return set(rows.all())


async def upcoming_for_user_with_status(session: AsyncSession, telegram_id: int, range_mode: str = "week",
                                        default_tz: int | str = 0) -> list[tuple[EventOccurrence, Calendar, bool]]:
    rows = await upcoming_for_user(session, telegram_id, range_mode, default_tz)
    if not rows:
        return []
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        return [(occ, calendar, False) for occ, calendar in rows]
    confirmed = await confirmed_occurrence_ids(session, user.id, [occ.id for occ, _ in rows])
    return [(occ, calendar, occ.id in confirmed) for occ, calendar in rows]


async def set_reminders(session: AsyncSession, telegram_id: int, calendar_id: int, value: str) -> bool:
    """Participant-only pre-event notification offsets for a subscription."""
    parse_minutes(value)
    sub = await session.scalar(select(Subscription).join(User).where(
        User.telegram_id == telegram_id, Subscription.calendar_id == calendar_id, Subscription.active.is_(True)))
    if not sub:
        return False
    sub.notification_minutes = value
    occurrence_ids = select(EventOccurrence.id).join(Event).where(
        Event.calendar_id == calendar_id,
        Event.status == "active",
        EventOccurrence.status == "active",
        EventOccurrence.start_utc > utcnow(),
    )
    await session.execute(update(NotificationJob).where(
        NotificationJob.user_id == sub.user_id,
        NotificationJob.occurrence_id.in_(occurrence_ids),
        NotificationJob.state == "pending",
        NotificationJob.kind.like(f"{JOB_KIND_REMINDER}:%"),
    ).values(state="obsolete"))
    future = (await session.scalars(
        select(EventOccurrence)
        .options(selectinload(EventOccurrence.event))
        .where(EventOccurrence.id.in_(occurrence_ids))
    )).all()
    for occurrence in future:
        for minute in notification_offsets(sub):
            scheduled = occurrence.start_utc - timedelta(minutes=minute)
            if scheduled >= utcnow():
                session.add(NotificationJob(
                    occurrence_id=occurrence.id, user_id=sub.user_id,
                    kind=job_kind(JOB_KIND_REMINDER, minute),
                    occurrence_version=occurrence.version, scheduled_at=scheduled,
                ))
    await session.commit()
    return True


async def set_confirmation_hours(
    session: AsyncSession, owner_telegram_id: int, calendar_id: int, value: str,
) -> Calendar | None:
    """Organizer-controlled attendance confirmation lead times (hours) for a calendar."""
    parse_hours(value)
    calendar = await owned_calendar(session, owner_telegram_id, calendar_id)
    if not calendar:
        return None
    calendar.confirmation_hours = value
    occurrence_ids = select(EventOccurrence.id).join(Event).where(
        Event.calendar_id == calendar_id,
        Event.status == "active",
        EventOccurrence.status == "active",
        EventOccurrence.start_utc > utcnow(),
    )
    await session.execute(update(NotificationJob).where(
        NotificationJob.occurrence_id.in_(occurrence_ids),
        NotificationJob.state == "pending",
        NotificationJob.kind.like(f"{JOB_KIND_CONFIRM}:%"),
    ).values(state="obsolete"))
    future = (await session.scalars(
        select(EventOccurrence)
        .options(selectinload(EventOccurrence.event))
        .where(EventOccurrence.id.in_(occurrence_ids))
    )).all()
    subs = (await session.scalars(select(Subscription).where(
        Subscription.calendar_id == calendar_id, Subscription.active.is_(True)))).all()
    now = utcnow()
    for occurrence in future:
        for sub in subs:
            for hour in confirmation_offsets(calendar):
                scheduled = occurrence.start_utc - timedelta(hours=hour)
                if scheduled >= now:
                    session.add(NotificationJob(
                        occurrence_id=occurrence.id, user_id=sub.user_id,
                        kind=job_kind(JOB_KIND_CONFIRM, hour),
                        occurrence_version=occurrence.version, scheduled_at=scheduled,
                    ))
    await session.commit()
    return calendar
