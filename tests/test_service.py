from datetime import timedelta

import pytest
from sqlalchemy import select

from meetifier.db import Database, Event, EventConfirmation, NotificationJob, Subscription, utcnow
from meetifier.service import (calendar_events, change_event, confirm_event, confirmations_for_event, create_calendar,
                               create_events, display_time, local_to_utc, make_invitation, parse_minutes,
                               set_subscription_state, subscribe, week_bounds_utc)
from meetifier.worker import process_due_jobs


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.init()
    yield database
    await database.close()


def test_timezone_offset_parsing():
    from meetifier.config import format_timezone_offset, parse_timezone_offset

    assert parse_timezone_offset(3) == 3
    assert parse_timezone_offset("+3") == 3
    assert parse_timezone_offset("UTC-5") == -5
    assert parse_timezone_offset("UTC") == 0
    assert format_timezone_offset(3) == "UTC+3"
    with pytest.raises(ValueError):
        parse_timezone_offset(99)


def test_timezone_conversion_and_display():
    utc = local_to_utc("2026-01-15 12:00", 3)
    assert utc.hour == 9
    assert "12:00" in display_time(utc, 3)
    assert "UTC+3" in display_time(utc, 3)


def test_parse_minutes():
    assert parse_minutes("30,1440,30") == [1440, 30]
    with pytest.raises(ValueError): parse_minutes("later")


async def prepared(db):
    async with db.sessions() as session:
        calendar = await create_calendar(session, 100, "Math", 3, 0)
        invite = await make_invitation(session, 100, calendar.id)
        await subscribe(session, 200, invite.token, 0)
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


async def test_confirm_event_notifies_organizer_data(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        event = (await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60))[0]
        event_id = event.id
        confirmed, _, owner, created = await confirm_event(session, 200, event_id, "Alice", 0)
        again, _, _, created_again = await confirm_event(session, 200, event_id, "Alice", 0)
        rows = await confirmations_for_event(session, 100, event_id)
    assert created
    assert not created_again
    assert confirmed.title == "Class"
    assert owner.telegram_id == 100
    assert len(rows) == 1
    assert rows[0].display_name == "Alice"


async def test_confirmations_cleared_on_reschedule(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        event = (await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60))[0]
        await confirm_event(session, 200, event.id, "Alice", 0)
        await change_event(session, 100, event.id, "2030-01-02 19:00")
        rows = await confirmations_for_event(session, 100, event.id)
    assert rows == []


def test_week_bounds_utc():
    start, end = week_bounds_utc(0)
    assert end > start
    assert (end - start).days == 7


async def test_calendar_events_next(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        near = (await create_events(session, 100, calendar.id, "Soon", "2030-01-01 18:00", 60))[0]
        await create_events(session, 100, calendar.id, "Later", "2030-01-08 18:00", 60)
        next_only = await calendar_events(session, calendar.id, "next", calendar.timezone)
    assert len(next_only) == 1
    assert next_only[0].id == near.id


async def test_calendar_events_week(db):
    from unittest.mock import patch

    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "A", "2030-01-01 18:00", 60)
        await create_events(session, 100, calendar.id, "B", "2030-01-03 18:00", 60)
        await create_events(session, 100, calendar.id, "C", "2030-01-08 18:00", 60)
        bounds = (local_to_utc("2030-01-01 00:00", calendar.timezone), local_to_utc("2030-01-07 00:00", calendar.timezone))
        with patch("meetifier.service.week_bounds_utc", return_value=bounds):
            week_all = await calendar_events(session, calendar.id, "week", calendar.timezone)
    assert len(week_all) == 2


async def test_worker_sends_and_records_delivery(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        job = await session.scalar(select(NotificationJob))
        job.scheduled_at = utcnow() - timedelta(seconds=1)
        await session.commit()

    class FakeBot:
        sent = []
        async def send_message(self, telegram_id, text, **kwargs):
            self.sent.append((telegram_id, text))

    bot = FakeBot()
    assert await process_due_jobs(db, bot) == 1
    async with db.sessions() as session:
        job = await session.scalar(select(NotificationJob))
    assert job.state == "sent"
    assert job.sent_at is not None
    assert bot.sent[0][0] == 200
