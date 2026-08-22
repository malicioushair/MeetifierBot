from __future__ import annotations

import asyncio
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select

from .db import Calendar, Database, Event, NotificationJob, Subscription, User, utcnow
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
                await bot.send_message(user.telegram_id, f"Reminder ({minutes} min): {event.title}\n{display_time(event.start_utc, user.timezone)}\nCalendar: {calendar.name}")
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
