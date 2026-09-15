from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from meetifier.db import Calendar, Database, Event, EventConfirmation, EventOccurrence, NotificationJob, Subscription, utcnow
from meetifier.recurrence import RecurrenceRule, generate_starts_utc
from meetifier.service import (PAYMENT_PAID, PAYMENT_UNPAID, abo_cycle_occurrences, abo_occurrence_symbol,
                               calendar_event_series, calendar_events, change_event, compute_abo_stats, confirm_event,
                               confirmations_for_event, create_calendar, create_events, current_abo_cycle_index,
                               display_time, event_all_occurrences, event_occurrences, local_to_utc, make_invitation,
                               mark_abo_cycle_paid, month_bounds_utc, next_week_bounds_utc, owned_abo_events,
                               owned_future_events, parse_minutes, render_confirmation_request,
                               set_confirmation_template, set_occurrence_payment, set_subscription_state,
                               subscribe, week_bounds_utc)
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
    with pytest.raises(ValueError):
        parse_minutes("later")


async def prepared(db):
    async with db.sessions() as session:
        return await create_calendar(session, 100, "Math", 3, 0)


async def subscribe_participant(session, owner_id: int, participant_id: int, event_id: int) -> None:
    invite = await make_invitation(session, owner_id, event_id)
    await subscribe(session, participant_id, invite.token, 0)


async def test_weekly_events_and_durable_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Algebra", "2030-01-01 18:00", 60, 3)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        jobs = (await session.scalars(select(NotificationJob))).all()
        events = (await session.scalars(select(Event))).all()
    assert len(occurrences) == 3
    assert len(events) == 1
    assert events[0].recurrence_json
    assert len({occ.event_id for occ in occurrences}) == 1
    assert occurrences[1].start_utc - occurrences[0].start_utc == timedelta(weeks=1)
    # 3 occurrences × (confirm:24 + reminder:60)
    assert len(jobs) == 6
    kinds = {job.kind for job in jobs}
    assert kinds == {"confirm:24", "reminder:60"}


async def test_participant_notification_override(db):
    from meetifier.service import set_reminders

    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        await set_reminders(session, 200, occurrences[0].event_id, "30")
        jobs = (await session.scalars(select(NotificationJob).where(
            NotificationJob.state == "pending"))).all()
    kinds = sorted(job.kind for job in jobs)
    assert kinds == ["confirm:24", "reminder:30"]


async def test_organizer_confirmation_timing(db):
    from meetifier.service import set_confirmation_hours

    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        await set_confirmation_hours(session, 100, calendar.id, "2")
        jobs = (await session.scalars(select(NotificationJob).where(
            NotificationJob.state == "pending"))).all()
        calendar = await session.get(Calendar, calendar.id)
    kinds = sorted(job.kind for job in jobs)
    assert calendar.confirmation_hours == "2"
    assert kinds == ["confirm:2", "reminder:60"]


async def test_mute_skips_only_participant_notifications(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        await set_subscription_state(session, 200, occurrences[0].event_id, "mute")
        for job in (await session.scalars(select(NotificationJob))).all():
            job.scheduled_at = utcnow()
        await session.commit()
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    processed = await process_due_jobs(db, bot)
    async with db.sessions() as session:
        jobs = list((await session.scalars(select(NotificationJob))).all())
    by_kind = {job.kind: job.state for job in jobs}
    assert by_kind["reminder:60"] == "obsolete"
    assert by_kind["confirm:24"] == "sent"
    assert processed == 1
    bot.send_message.assert_awaited()
    sent_text = bot.send_message.await_args.args[1]
    assert "Please confirm attendance" in sent_text
    assert bot.send_message.await_args.kwargs.get("reply_markup") is not None


def test_weekly_multi_day_and_interval():
    rule = RecurrenceRule.weekly(weekdays=[0, 2], interval=1, count=4)  # Mon+Wed
    starts = generate_starts_utc(rule, "2030-01-07 18:00", 0, 60)  # Monday
    assert [s[0].date().isoformat() for s in starts] == [
        "2030-01-07", "2030-01-09", "2030-01-14", "2030-01-16",
    ]
    biweekly = RecurrenceRule.weekly(weekdays=[0], interval=2, count=3)
    starts = generate_starts_utc(biweekly, "2030-01-07 18:00", 0, 60)
    assert [s[0].date().isoformat() for s in starts] == [
        "2030-01-07", "2030-01-21", "2030-02-04",
    ]


def test_first_tuesday_monthly():
    rule = RecurrenceRule.monthly_nth(weekday=1, bysetpos=1, count=3)  # first Tuesday
    starts = generate_starts_utc(rule, "2030-01-01 18:00", 0, 60)
    assert [s[0].date().isoformat() for s in starts] == [
        "2030-01-01", "2030-02-05", "2030-03-05",
    ]


async def test_create_with_recurrence_rule(db):
    calendar = await prepared(db)
    rule = RecurrenceRule.weekly(weekdays=[2], interval=1, count=2)  # Wed
    async with db.sessions() as session:
        occurrences = await create_events(
            session, 100, calendar.id, "Lab", "2030-01-01 18:00", 60, rule=rule)
    # 2030-01-01 local is Tuesday; first Wed is 2030-01-02 (UTC+3 -> 15:00 UTC)
    assert len(occurrences) == 2
    assert occurrences[0].start_utc == datetime(2030, 1, 2, 15, 0)
    assert occurrences[1].start_utc == datetime(2030, 1, 9, 15, 0)


async def test_reschedule_invalidates_old_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        occurrence = occurrences[0]
        occurrence_id = occurrence.id
        changed = await change_event(session, 100, occurrence_id, "2030-01-02 19:00")
        jobs = (await session.scalars(select(NotificationJob).where(
            NotificationJob.occurrence_id == occurrence_id))).all()
        changed_occ = await session.get(EventOccurrence, occurrence_id)
    assert len(changed) == 1
    assert changed_occ.version == 2
    assert {j.state for j in jobs} == {"obsolete", "pending"}


async def test_change_following_shifts_series(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60, 3)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        first_id = occurrences[0].id
        original_seconds = [o.start_utc for o in occurrences]
        changed = await change_event(session, 100, first_id, "2030-01-01 19:00", scope="following")
        assert len(changed) == 3
        refreshed = list((await session.scalars(
            select(EventOccurrence).where(EventOccurrence.event_id == occurrences[0].event_id)
            .order_by(EventOccurrence.start_utc)
        )).all())
    delta = timedelta(hours=1)
    assert [o.start_utc for o in refreshed] == [t + delta for t in original_seconds]


async def test_cancel_following(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60, 3)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        changed = await change_event(session, 100, occurrences[1].id, cancel=True, scope="following")
        assert len(changed) == 2
        rows = list((await session.scalars(
            select(EventOccurrence).where(EventOccurrence.event_id == occurrences[0].event_id)
            .order_by(EventOccurrence.start_utc)
        )).all())
    assert rows[0].status == "active"
    assert rows[1].status == "cancelled"
    assert rows[2].status == "cancelled"


async def test_unsubscribe_obsoletes_jobs(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        assert await set_subscription_state(session, 200, occurrences[0].event_id, "unsubscribe")
        sub = await session.scalar(select(Subscription).where(Subscription.event_id == occurrences[0].event_id))
        jobs = (await session.scalars(select(NotificationJob))).all()
    assert not sub.active
    assert all(job.state == "obsolete" for job in jobs)


async def test_confirm_event_notifies_organizer_data(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        occurrence = occurrences[0]
        occurrence_id = occurrence.id
        confirmed, _, owner, created = await confirm_event(session, 200, occurrence_id, "Alice", 0)
        again, _, _, created_again = await confirm_event(session, 200, occurrence_id, "Alice", 0)
    assert created and not created_again
    assert owner.telegram_id == 100
    assert confirmed.event.title == "Class"


async def test_confirmations_cleared_on_reschedule(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        occurrence = occurrences[0]
        await confirm_event(session, 200, occurrence.id, "Alice", 0)
        await change_event(session, 100, occurrence.id, "2030-01-02 19:00")
        rows = await confirmations_for_event(session, 100, occurrence.id)
    assert rows == []


def test_week_bounds_utc():
    start, end = week_bounds_utc(0)
    assert end - start == timedelta(days=7)


def test_next_week_bounds_utc():
    week_start, week_end = week_bounds_utc(0)
    next_start, next_end = next_week_bounds_utc(0)
    assert next_start == week_end
    assert next_end - next_start == timedelta(days=7)


def test_month_bounds_utc():
    start, end = month_bounds_utc(0)
    assert start.day == 1
    assert (end - start).days in {28, 29, 30, 31}


async def test_owned_future_events(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        algebra = (await create_events(session, 100, calendar.id, "Algebra", "2030-01-01 18:00", 60, 3))[0]
        await create_events(session, 100, calendar.id, "Past", "2020-01-01 18:00", 60)
        rows = await owned_future_events(session, 100)
    assert [event.title for event, _ in rows] == ["Algebra"]
    assert rows[0][0].id == algebra.event_id


async def test_calendar_event_series_and_occurrences(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "Algebra", "2030-01-01 18:00", 60, 3)
        await create_events(session, 100, calendar.id, "Geometry", "2030-01-02 18:00", 60, 1)
        series = await calendar_event_series(session, calendar.id, "future", calendar.timezone)
        assert [e.title for e in series] == ["Algebra", "Geometry"]
        algebra = series[0]
        occs = await event_occurrences(session, algebra.id, "future", calendar.timezone)
        assert len(occs) == 3
        assert all(o.event_id == algebra.id for o in occs)


async def test_calendar_events_next(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        near = (await create_events(session, 100, calendar.id, "Soon", "2030-01-01 18:00", 60))[0]
        await create_events(session, 100, calendar.id, "Later", "2030-01-08 18:00", 60)
        next_only = await calendar_events(session, calendar.id, "next", calendar.timezone)
    assert len(next_only) == 1
    assert next_only[0].id == near.id


async def test_calendar_events_week(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "A", "2030-01-01 18:00", 60)
        await create_events(session, 100, calendar.id, "B", "2030-01-03 18:00", 60)
        await create_events(session, 100, calendar.id, "C", "2030-01-08 18:00", 60)
        bounds = (local_to_utc("2030-01-01 00:00", calendar.timezone), local_to_utc("2030-01-07 00:00", calendar.timezone))
        with patch("meetifier.service.week_bounds_utc", return_value=bounds):
            week_all = await calendar_events(session, calendar.id, "week", calendar.timezone)
    assert len(week_all) == 2


async def test_calendar_events_next_week(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        await create_events(session, 100, calendar.id, "This week", "2030-01-03 18:00", 60)
        upcoming = (await create_events(session, 100, calendar.id, "Next week", "2030-01-08 18:00", 60))[0]
        await create_events(session, 100, calendar.id, "Later", "2030-01-15 18:00", 60)
        week_bounds = (
            local_to_utc("2030-01-01 00:00", calendar.timezone),
            local_to_utc("2030-01-07 00:00", calendar.timezone),
        )
        next_bounds = (
            local_to_utc("2030-01-07 00:00", calendar.timezone),
            local_to_utc("2030-01-14 00:00", calendar.timezone),
        )
        with patch("meetifier.service.week_bounds_utc", return_value=week_bounds), patch(
            "meetifier.service.next_week_bounds_utc", return_value=next_bounds,
        ):
            rows = await calendar_events(session, calendar.id, "next_week", calendar.timezone)
    assert [o.id for o in rows] == [upcoming.id]


async def test_calendar_events_month(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        past = (await create_events(session, 100, calendar.id, "Past", "2030-01-01 10:00", 60))[0]
        upcoming = (await create_events(session, 100, calendar.id, "Upcoming", "2030-01-20 18:00", 60))[0]
        await create_events(session, 100, calendar.id, "Next month", "2030-02-01 18:00", 60)
        month_bounds = (
            local_to_utc("2030-01-01 00:00", calendar.timezone),
            local_to_utc("2030-02-01 00:00", calendar.timezone),
        )
        now = local_to_utc("2030-01-02 12:00", calendar.timezone)
        with patch("meetifier.service.month_bounds_utc", return_value=month_bounds), patch(
            "meetifier.service.utcnow", return_value=now,
        ):
            rows = await calendar_events(session, calendar.id, "month", calendar.timezone)
    assert [o.id for o in rows] == [upcoming.id]
    assert past.id not in {o.id for o in rows}


async def test_calendar_events_week_excludes_past(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        past = (await create_events(session, 100, calendar.id, "Past", "2030-01-01 10:00", 60))[0]
        upcoming = (await create_events(session, 100, calendar.id, "Upcoming", "2030-01-03 18:00", 60))[0]
        await create_events(session, 100, calendar.id, "Next week", "2030-01-08 18:00", 60)
        bounds = (local_to_utc("2030-01-01 00:00", calendar.timezone), local_to_utc("2030-01-07 00:00", calendar.timezone))
        now = local_to_utc("2030-01-02 12:00", calendar.timezone)
        with patch("meetifier.service.week_bounds_utc", return_value=bounds), patch(
            "meetifier.service.utcnow", return_value=now,
        ):
            week_upcoming = await calendar_events(session, calendar.id, "week", calendar.timezone)
    assert [o.id for o in week_upcoming] == [upcoming.id]
    assert past.id not in {o.id for o in week_upcoming}


async def test_worker_sends_and_records_delivery(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        job = await session.scalar(select(NotificationJob).where(NotificationJob.kind == "confirm:24"))
        job_id = job.id
        job.scheduled_at = utcnow()
        await session.commit()
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    processed = await process_due_jobs(db, bot)
    async with db.sessions() as session:
        job = await session.get(NotificationJob, job_id)
    assert processed == 1
    assert job.state == "sent"
    bot.send_message.assert_awaited()
    assert bot.send_message.await_args.kwargs.get("reply_markup") is not None


async def test_worker_sends_participant_notification_without_confirm_button(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(session, 100, calendar.id, "Class", "2030-01-01 18:00", 60)
        await subscribe_participant(session, 100, 200, occurrences[0].event_id)
        job = await session.scalar(select(NotificationJob).where(NotificationJob.kind == "reminder:60"))
        job_id = job.id
        job.scheduled_at = utcnow()
        await session.commit()
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    processed = await process_due_jobs(db, bot)
    async with db.sessions() as session:
        job = await session.get(NotificationJob, job_id)
    assert processed == 1
    assert job.state == "sent"
    assert bot.send_message.await_args.kwargs.get("reply_markup") is None
    assert "Notification" in bot.send_message.await_args.args[1]


async def test_create_abo_with_cycles(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(
            session, 100, calendar.id, "Anna", "2030-01-01 18:00", 60, 12,
            is_abo=True, abo_lesson_count=5,
        )
        event = await session.get(Event, occurrences[0].event_id)
        assert event.is_abo is True
        assert event.abo_lesson_count == 5
        assert len(occurrences) == 12
        await subscribe_participant(session, 100, 200, event.id)
        all_occ = await event_all_occurrences(session, event.id)
        stats = compute_abo_stats(event, all_occ)
        assert stats.total == 5
        assert stats.cycle_count == 3
        assert stats.unset == 5
        assert abo_occurrence_symbol(event, all_occ[0]) == ""
        await mark_abo_cycle_paid(session, 100, event.id, 0)
        cycle = abo_cycle_occurrences(event, all_occ, 0)
        assert all(occ.payment_status == PAYMENT_PAID for occ in cycle)
        stats = compute_abo_stats(event, all_occ, 0)
        assert stats.paid_left == 5
        assert abo_occurrence_symbol(event, all_occ[0]) == "💰"
        await set_occurrence_payment(session, 100, all_occ[5].id, PAYMENT_UNPAID)
        stats = compute_abo_stats(event, all_occ, 1)
        assert stats.unpaid == 1
        assert stats.unset == 4
        abos = await owned_abo_events(session, 100)
        assert len(abos) == 1


async def test_abo_rejects_second_student(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(
            session, 100, calendar.id, "Anna", "2030-01-01 18:00", 60, 3,
            is_abo=True, abo_lesson_count=3,
        )
        event_id = occurrences[0].event_id
        await subscribe_participant(session, 100, 200, event_id)
        invite = await make_invitation(session, 100, event_id)
    async with db.sessions() as session:
        with pytest.raises(ValueError, match="abo"):
            await subscribe(session, 300, invite.token, 0)


async def test_abo_passed_lessons(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        occurrences = await create_events(
            session, 100, calendar.id, "Anna", "2020-01-01 18:00", 60, 8,
            is_abo=True, abo_lesson_count=5,
        )
        event = await session.get(Event, occurrences[0].event_id)
        all_occ = await event_all_occurrences(session, event.id)
        cycle_index = current_abo_cycle_index(event, all_occ)
        assert cycle_index == 1
        stats = compute_abo_stats(event, all_occ, cycle_index)
        assert stats.passed == 3
        assert abo_occurrence_symbol(event, all_occ[5]) == "✓"
        await set_occurrence_payment(session, 100, all_occ[5].id, PAYMENT_PAID)
        assert abo_occurrence_symbol(event, all_occ[5]) == "💰✓"


async def test_confirmation_template(db):
    calendar = await prepared(db)
    async with db.sessions() as session:
        default = render_confirmation_request(
            calendar, "en",
            title="Class", time="10:00", calendar="Math", hours="24",
        )
        assert "Please confirm attendance" in default
        await set_confirmation_template(
            session, 100, calendar.id, "Hi {title}! Confirm by {time} ({calendar}), {hours}h before.",
        )
        calendar = await session.get(Calendar, calendar.id)
        custom = render_confirmation_request(
            calendar, "en",
            title="Class", time="10:00", calendar="Math", hours="24",
        )
        assert custom == "Hi Class! Confirm by 10:00 (Math), 24h before."
        await set_confirmation_template(session, 100, calendar.id, None)
        calendar = await session.get(Calendar, calendar.id)
        assert calendar.confirmation_template is None