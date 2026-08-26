from datetime import datetime, timezone

import pytest
from google.oauth2.credentials import Credentials

from meetifier.config import Settings
from meetifier.db import Calendar, Database, Event, GoogleAccount
from meetifier.google_sync import (
    _credentials,
    _naive_utc,
    _persist_refreshed_tokens,
    event_to_google_body,
    google_enabled,
)
from meetifier.service import get_or_create_user


def test_event_to_google_body():
    calendar = Calendar(id=1, owner_user_id=1, name="Math", timezone="Europe/Moscow")
    start = datetime(2030, 1, 1, 15, 0)
    end = datetime(2030, 1, 1, 16, 0)
    event = Event(id=1, calendar_id=1, title="Algebra", start_utc=start, end_utc=end)
    body = event_to_google_body(event, calendar)
    assert body["summary"] == "Algebra"
    assert body["start"]["timeZone"] == "Europe/Moscow"
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
        user = await get_or_create_user(session, 1, "UTC")
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
