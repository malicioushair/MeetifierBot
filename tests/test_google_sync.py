from datetime import datetime, timezone

import pytest
from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from meetifier.config import Settings
from meetifier.db import (Calendar, Database, Event, EventOccurrence, GoogleAccount, GoogleCalendarLink,
                          GoogleEventAttendee, GoogleEventLink, GoogleEventState, NotificationJob)
from meetifier.google_sync import (
    _credentials,
    _naive_utc,
    _persist_refreshed_tokens,
    _upsert_google_event,
    event_to_google_body,
    google_enabled,
)
from meetifier.service import create_calendar, get_or_create_user


def test_event_to_google_body():
    calendar = Calendar(id=1, owner_user_id=1, name="Math", timezone=3)
    start = datetime(2030, 1, 1, 15, 0)
    end = datetime(2030, 1, 1, 16, 0)
    event = Event(id=1, calendar_id=1, title="Algebra")
    occurrence = EventOccurrence(id=1, event_id=1, start_utc=start, end_utc=end)
    occurrence.event = event
    body = event_to_google_body(occurrence, calendar)
    assert body["summary"] == "Algebra"
    assert body["start"]["timeZone"] == "Etc/GMT-3"
    assert "18:00" in body["start"]["dateTime"]


def test_google_enabled_requires_all_settings():
    assert not google_enabled(Settings(
        organizer_bot_token="a", participant_bot_token="b", participant_bot_username="c",
        google_client_id="", google_client_secret="x", google_redirect_uri="http://localhost/cb"))
    assert google_enabled(Settings(
        organizer_bot_token="a", participant_bot_token="b", participant_bot_username="c",
        google_client_id="id", google_client_secret="secret", google_redirect_uri="http://localhost/cb"))


def test_credentials_use_naive_utc_expiry():
    settings = Settings(
        organizer_bot_token="a", participant_bot_token="b", participant_bot_username="c",
        google_client_id="id", google_client_secret="secret", google_redirect_uri="http://localhost/cb",
    )
    aware = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    account = GoogleAccount(user_id=1, refresh_token="rt", access_token="at", token_expiry=aware)
    creds = _credentials(settings, account)
    assert creds.expiry is not None
    assert creds.expiry.tzinfo is None
    assert creds.expired in (True, False)  # must not raise on compare


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.init()
    yield database
    await database.close()


async def test_persist_refreshed_tokens_updates_account(db):
    async with db.sessions() as session:
        user = await get_or_create_user(session, 1, 0)
        account = GoogleAccount(
            user_id=user.id,
            refresh_token="old_rt",
            access_token="old_at",
            token_expiry=datetime(2020, 1, 1),
        )
        session.add(account)
        await session.commit()

        creds = Credentials(
            token="new_at",
            refresh_token="new_rt",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="id",
            client_secret="secret",
        )
        creds.expiry = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)

        await _persist_refreshed_tokens(session, account, creds)

        stored = await session.get(GoogleAccount, user.id)
        assert stored is not None
        assert stored.access_token == "new_at"
        assert stored.refresh_token == "new_rt"
        assert stored.token_expiry == datetime(2030, 1, 1, 12, 0)


async def test_google_event_import_update_cancel_and_attendees(db):
    async with db.sessions() as session:
        calendar = await create_calendar(session, 1, "Work", 3, 0)
        link = GoogleCalendarLink(
            calendar_id=calendar.id,
            google_calendar_id="primary",
            google_calendar_name="Work",
        )
        session.add(link)
        await session.commit()
        item = {
            "id": "google-1",
            "etag": "v1",
            "summary": "Planning",
            "description": "Agenda",
            "status": "confirmed",
            "start": {"dateTime": "2030-01-01T18:00:00+03:00"},
            "end": {"dateTime": "2030-01-01T19:00:00+03:00"},
            "recurringEventId": "series-1",
            "originalStartTime": {"dateTime": "2030-01-01T18:00:00+03:00"},
            "attendees": [{"email": "guest@example.com", "displayName": "Guest", "responseStatus": "accepted"}],
        }
        change = await _upsert_google_event(session, calendar, link, item)
        await session.commit()
        occurrence = await session.scalar(
            select(EventOccurrence).options(selectinload(EventOccurrence.event)))
        mapping = await session.get(GoogleEventLink, occurrence.id)
        state = await session.get(GoogleEventState, occurrence.id)
        attendee = await session.scalar(select(GoogleEventAttendee))

        assert change.action == "created"
        assert occurrence.event.title == "Planning"
        assert occurrence.start_utc == datetime(2030, 1, 1, 15, 0)
        assert mapping.google_event_id == "google-1"
        assert state.recurring_event_id == "series-1"
        assert attendee.email == "guest@example.com"

        item["etag"] = "v2"
        item["start"] = {"dateTime": "2030-01-02T19:00:00+03:00"}
        item["end"] = {"dateTime": "2030-01-02T20:00:00+03:00"}
        change = await _upsert_google_event(session, calendar, link, item)
        await session.commit()
        await session.refresh(occurrence)
        assert change.action == "updated"
        assert occurrence.version == 2
        assert occurrence.start_utc == datetime(2030, 1, 2, 16, 0)

        item = {"id": "google-1", "status": "cancelled"}
        change = await _upsert_google_event(session, calendar, link, item)
        await session.commit()
        await session.refresh(occurrence)
        assert change.action == "cancelled"
        assert occurrence.status == "cancelled"


async def test_google_event_import_is_idempotent(db):
    async with db.sessions() as session:
        calendar = await create_calendar(session, 1, "Work", 0, 0)
        link = GoogleCalendarLink(calendar_id=calendar.id, google_calendar_id="primary", google_calendar_name="Work")
        session.add(link)
        await session.commit()
        item = {
            "id": "google-1",
            "etag": "v1",
            "summary": "Planning",
            "status": "confirmed",
            "start": {"dateTime": "2030-01-01T18:00:00Z"},
            "end": {"dateTime": "2030-01-01T19:00:00Z"},
        }
        first = await _upsert_google_event(session, calendar, link, item)
        second = await _upsert_google_event(session, calendar, link, item)
        await session.commit()
        events = list((await session.scalars(select(Event))).all())
        occurrences = list((await session.scalars(select(EventOccurrence))).all())
        jobs = list((await session.scalars(select(NotificationJob))).all())

    assert first.action == "created"
    assert second.action == "unchanged"
    assert len(events) == 1
    assert len(occurrences) == 1
    assert jobs == []
