from __future__ import annotations

import asyncio
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .db import Calendar, Database, EventOccurrence, NotificationJob, Subscription, User, utcnow
from .config import Settings
from .google_sync import sync_all_google_calendars
from .i18n import normalize_locale, t
from .keyboards import event_confirm_keyboard
from .service import display_time


async def process_due_jobs(db: Database, bot: Bot) -> int:
    processed = 0
    async with db.sessions() as session:
        jobs = (await session.scalars(select(NotificationJob).where(
            NotificationJob.state == "pending", NotificationJob.scheduled_at <= utcnow())
            .order_by(NotificationJob.scheduled_at).limit(100))).all()
        for job in jobs:
            occurrence = await session.scalar(
                select(EventOccurrence)
                .options(selectinload(EventOccurrence.event))
                .where(EventOccurrence.id == job.occurrence_id)
            )
            user = await session.get(User, job.user_id)
            calendar = await session.get(Calendar, occurrence.event.calendar_id) if occurrence else None
            sub = await session.scalar(select(Subscription).where(
                Subscription.user_id == job.user_id,
                Subscription.calendar_id == occurrence.event.calendar_id,
            )) if occurrence else None
            if (
                not occurrence or occurrence.status != "active" or occurrence.event.status != "active"
                or occurrence.version != job.occurrence_version or not sub or not sub.active or sub.muted
            ):
                job.state = "obsolete"
                continue
            try:
                minutes = job.kind.split(":", 1)[1]
                locale = normalize_locale(user.locale)
                await bot.send_message(
                    user.telegram_id,
                    t(locale, "reminder", minutes=minutes, title=occurrence.event.title,
                      time=display_time(occurrence.start_utc, user.timezone), calendar=calendar.name),
                    reply_markup=event_confirm_keyboard(occurrence.id, locale),
                )
                job.state, job.sent_at = "sent", utcnow()
            except Exception as exc:
                job.attempts += 1
                job.last_error = str(exc)[:2000]
                if job.attempts >= 5:
                    job.state = "failed"
                else:
                    job.scheduled_at = utcnow() + timedelta(minutes=2 ** job.attempts)
            processed += 1
        await session.commit()
    return processed


async def run_worker(db: Database, bot: Bot, interval: int) -> None:
    while True:
        await process_due_jobs(db, bot)
        await asyncio.sleep(interval)


async def run_google_sync_worker(db: Database, settings: Settings, participant_bot: Bot) -> None:
    while True:
        results = await sync_all_google_calendars(db, settings)
        for result in results:
            if not result.changes:
                continue
            async with db.sessions() as session:
                calendar = await session.get(Calendar, result.calendar_id)
                users = list((await session.scalars(select(User).join(Subscription).where(
                    Subscription.calendar_id == result.calendar_id,
                    Subscription.active.is_(True),
                    Subscription.muted.is_(False),
                ))).all())
                for change in result.changes:
                    occurrence = await session.scalar(
                        select(EventOccurrence)
                        .options(selectinload(EventOccurrence.event))
                        .where(EventOccurrence.id == change.occurrence_id)
                    )
                    if not occurrence or not calendar:
                        continue
                    heading_key = {
                        "created": "heading_new_event",
                        "updated": "heading_event_updated",
                        "cancelled": "heading_event_cancelled",
                    }[change.action]
                    for user in users:
                        locale = normalize_locale(user.locale)
                        try:
                            await participant_bot.send_message(
                                user.telegram_id,
                                t(locale, "notify_event", heading=t(locale, heading_key),
                                  title=occurrence.event.title,
                                  time=display_time(occurrence.start_utc, calendar.timezone),
                                  calendar=calendar.name),
                                reply_markup=(
                                    event_confirm_keyboard(occurrence.id, locale)
                                    if change.action != "cancelled" else None
                                ),
                            )
                        except Exception:
                            pass
        await asyncio.sleep(settings.google_sync_interval_seconds)
