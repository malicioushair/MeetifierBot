from datetime import timedelta

import pytest
from sqlalchemy import select

from meetifier.db import Database, Event, NotificationJob, Subscription, utcnow
from meetifier.service import (change_event, create_calendar, create_events, display_time, local_to_utc,
                               make_invitation, parse_minutes, set_subscription_state, subscribe)
from meetifier.worker import process_due_jobs


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.init()
    yield database
    await database.close()


def test_timezone_conversion_and_display():
    utc = local_to_utc("2026-01-15 12:00", "Europe/Moscow")
    assert utc.hour == 9
    assert "12:00" in display_time(utc, "Europe/Moscow")


def test_parse_minutes():
    assert parse_minutes("30,1440,30") == [1440, 30]
    with pytest.raises(ValueError): parse_minutes("later")


async def prepared(db):
    async with db.sessions() as session:
        calendar = await create_calendar(session, 100, "Math", "Europe/Moscow", "UTC")
        invite = await make_invitation(session, 100, calendar.id)
        await subscribe(session, 200, invite.token, "UTC")
        return calendar


async def test_weekly_events_and_durable_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        events = await create_events(session, 100, calendar.id, "Algebra", "2030-01-01 18:00", 60, 3)
        jobs = (await session.scalars(select(NotificationJob))).all()
    assert len(events) == 3
    assert events[1].start_utc - events[0].start_utc == timedelta(weeks=1)
    assert len(jobs) == 6
    assert len({e.recurrence_group for e in events}) == 1


async def test_reschedule_invalidates_old_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        event = (await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60))[0]
        event_id = event.id
        await change_event(session, 100, event_id, "2030-01-02 19:00")
        jobs = (await session.scalars(select(NotificationJob).where(NotificationJob.event_id == event_id))).all()
        changed = await session.get(Event, event_id)
    assert changed.version == 2
    assert {j.state for j in jobs} == {"obsolete", "pending"}


async def test_unsubscribe_obsoletes_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        assert await set_subscription_state(session, 200, calendar.id, "unsubscribe")
        sub = await session.scalar(select(Subscription).where(Subscription.calendar_id == calendar.id))
        jobs = (await session.scalars(select(NotificationJob))).all()
    assert not sub.active
    assert all(job.state == "obsolete" for job in jobs)


async def test_worker_sends_and_records_delivery(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        job = await session.scalar(select(NotificationJob))
        job.scheduled_at = utcnow() - timedelta(seconds=1)
        await session.commit()

    class FakeBot:
        sent = []
        async def send_message(self, telegram_id, text):
            self.sent.append((telegram_id, text))

    bot = FakeBot()
    assert await process_due_jobs(db, bot) == 1
    async with db.sessions() as session:
        job = await session.scalar(select(NotificationJob))
    assert job.state == "sent"
    assert job.sent_at is not None
    assert bot.sent[0][0] == 200
