from __future__ import annotations

import asyncio
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select

from .db import Calendar, Database, Event, NotificationJob, Subscription, User, utcnow
from .config import Settings
from .google_sync import sync_all_google_calendars
from .keyboards import event_confirm_keyboard
from .service import display_time


async def process_due_jobs(db: Database, bot: Bot) -> int:
    processed = 0
    async with db.sessions() as session:
        jobs = (await session.scalars(select(NotificationJob).where(
            NotificationJob.state == "pending", NotificationJob.scheduled_at <= utcnow())
            .order_by(NotificationJob.scheduled_at).limit(100))).all()
        for job in jobs:
            event = await session.get(Event, job.event_id)
            user = await session.get(User, job.user_id)
            calendar = await session.get(Calendar, event.calendar_id) if event else None
            sub = await session.scalar(select(Subscription).where(
                Subscription.user_id == job.user_id, Subscription.calendar_id == event.calendar_id)) if event else None
            if not event or event.status != "active" or event.version != job.event_version or not sub or not sub.active or sub.muted:
                job.state = "obsolete"; continue
            try:
                minutes = job.kind.split(":", 1)[1]
                await bot.send_message(user.telegram_id, f"Reminder ({minutes} min): {event.title}\n{display_time(event.start_utc, user.timezone)}\nCalendar: {calendar.name}",
                                       reply_markup=event_confirm_keyboard(event.id))
                job.state, job.sent_at = "sent", utcnow()
            except Exception as exc:
                job.attempts += 1
                job.last_error = str(exc)[:2000]
                if job.attempts >= 5: job.state = "failed"
                else: job.scheduled_at = utcnow() + timedelta(minutes=2 ** job.attempts)
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
                telegram_ids = list((await session.scalars(select(User.telegram_id).join(Subscription).where(
                    Subscription.calendar_id == result.calendar_id,
                    Subscription.active.is_(True),
                    Subscription.muted.is_(False),
                ))).all())
                for change in result.changes:
                    event = await session.get(Event, change.event_id)
                    if not event or not calendar:
                        continue
                    heading = {
                        "created": "New event",
                        "updated": "Event updated",
                        "cancelled": "Event cancelled",
                    }[change.action]
                    for telegram_id in telegram_ids:
                        try:
                            await participant_bot.send_message(
                                telegram_id,
                                f"{heading}: {event.title}\n{display_time(event.start_utc, calendar.timezone)}\n"
                                f"Calendar: {calendar.name}",
                                reply_markup=event_confirm_keyboard(event.id) if change.action != "cancelled" else None,
                            )
                        except Exception:
                            pass
        await asyncio.sleep(settings.google_sync_interval_seconds)
