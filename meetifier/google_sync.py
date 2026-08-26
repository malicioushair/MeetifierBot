from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .db import Calendar, Database, Event, GoogleAccount, GoogleCalendarLink, GoogleEventLink, OAuthState, User, utcnow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

T = TypeVar("T")


def google_enabled(settings: Settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)


def build_oauth_flow(settings: Settings) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=settings.google_redirect_uri)


def authorization_url(settings: Settings, state: str) -> str:
    flow = build_oauth_flow(settings)
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return url


def event_to_google_body(event: Event, calendar: Calendar) -> dict:
    tz = ZoneInfo(calendar.timezone)
    start = event.start_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    end = event.end_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    return {
        "summary": event.title,
        "start": {"dateTime": start.isoformat(), "timeZone": calendar.timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": calendar.timezone},
    }


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _credentials(settings: Settings, account: GoogleAccount) -> Credentials:
    # google-auth compares expiry to naive utcnow(); keep expiry naive UTC.
    expiry = _naive_utc(account.token_expiry)
    return Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
        expiry=expiry,
    )


def _calendar_service(settings: Settings, account: GoogleAccount):
    creds = _credentials(settings, account)
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False), creds


def _with_calendar_service(
    settings: Settings,
    account: GoogleAccount,
    fn: Callable[..., T],
    *args,
    **kwargs,
) -> tuple[T, Credentials]:
    service, creds = _calendar_service(settings, account)
    return fn(service, *args, **kwargs), creds


def _exchange_code_sync(settings: Settings, code: str) -> tuple[str, str | None, datetime | None, str]:
    flow = build_oauth_flow(settings)
    flow.fetch_token(code=code)
    creds = flow.credentials
    email = ""
    try:
        profile = build("oauth2", "v2", credentials=creds, cache_discovery=False).userinfo().get().execute()
        email = profile.get("email", "")
    except Exception:
        pass
    expiry = _naive_utc(creds.expiry)
    return creds.refresh_token or "", creds.token, expiry, email


def _list_calendars_sync(settings: Settings, account: GoogleAccount) -> tuple[list[dict[str, str]], Credentials]:
    def list_calendars(service):
        items = service.calendarList().list().execute().get("items", [])
        return [{"id": x["id"], "name": x.get("summary", x["id"])} for x in items]

    return _with_calendar_service(settings, account, list_calendars)


def _insert_event_sync(
    settings: Settings, account: GoogleAccount, google_calendar_id: str, body: dict,
) -> tuple[str, Credentials]:
    def insert_event(service):
        created = service.events().insert(calendarId=google_calendar_id, body=body).execute()
        return created["id"]

    return _with_calendar_service(settings, account, insert_event)


def _update_event_sync(
    settings: Settings, account: GoogleAccount, google_calendar_id: str, google_event_id: str, body: dict,
) -> Credentials:
    def update_event(service):
        service.events().update(calendarId=google_calendar_id, eventId=google_event_id, body=body).execute()

    _, creds = _with_calendar_service(settings, account, update_event)
    return creds


def _delete_event_sync(
    settings: Settings, account: GoogleAccount, google_calendar_id: str, google_event_id: str,
) -> Credentials:
    def delete_event(service):
        service.events().delete(calendarId=google_calendar_id, eventId=google_event_id).execute()

    _, creds = _with_calendar_service(settings, account, delete_event)
    return creds


async def create_oauth_state(session: AsyncSession, telegram_id: int) -> str:
    import secrets

    state = secrets.token_urlsafe(32)
    session.add(OAuthState(state=state, telegram_id=telegram_id))
    await session.commit()
    return state


async def consume_oauth_state(session: AsyncSession, state: str) -> int | None:
    row = await session.scalar(select(OAuthState).where(OAuthState.state == state))
    if not row:
        return None
    telegram_id = row.telegram_id
    await session.delete(row)
    await session.commit()
    return telegram_id


async def save_google_account(session: AsyncSession, telegram_id: int, default_tz: str,
                              refresh_token: str, access_token: str | None, expiry: datetime | None, email: str) -> None:
    from .service import get_or_create_user

    user = await get_or_create_user(session, telegram_id, default_tz)
    account = await session.get(GoogleAccount, user.id)
    if account:
        account.refresh_token = refresh_token
        account.access_token = access_token
        account.token_expiry = expiry
        account.email = email
    else:
        session.add(GoogleAccount(
            user_id=user.id, refresh_token=refresh_token, access_token=access_token,
            token_expiry=expiry, email=email))
    await session.commit()


async def get_google_account(session: AsyncSession, telegram_id: int) -> GoogleAccount | None:
    return await session.scalar(
        select(GoogleAccount).join(User).where(User.telegram_id == telegram_id))


async def link_google_calendar(session: AsyncSession, telegram_id: int, calendar_id: int,
                               google_calendar_id: str, google_calendar_name: str) -> None:
    calendar = await session.scalar(
        select(Calendar).join(User).where(Calendar.id == calendar_id, User.telegram_id == telegram_id))
    if not calendar:
        raise PermissionError("Calendar not found or not owned by you")
    account = await get_google_account(session, telegram_id)
    if not account:
        raise PermissionError("Link Google account first")
    link = await session.get(GoogleCalendarLink, calendar_id)
    if link:
        link.google_calendar_id = google_calendar_id
        link.google_calendar_name = google_calendar_name
    else:
        session.add(GoogleCalendarLink(
            calendar_id=calendar_id, google_calendar_id=google_calendar_id, google_calendar_name=google_calendar_name))
    await session.commit()


async def list_google_calendars(session: AsyncSession, settings: Settings, account: GoogleAccount) -> list[dict[str, str]]:
    loop = asyncio.get_running_loop()
    calendars, creds = await loop.run_in_executor(None, lambda: _list_calendars_sync(settings, account))
    await _persist_refreshed_tokens(session, account, creds)
    return calendars


async def complete_oauth(settings: Settings, code: str) -> tuple[str, str | None, datetime | None, str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _exchange_code_sync(settings, code))


async def _load_sync_context(session: AsyncSession, calendar: Calendar) -> tuple[GoogleAccount, GoogleCalendarLink] | None:
    link = await session.get(GoogleCalendarLink, calendar.id)
    if not link:
        return None
    account = await session.get(GoogleAccount, calendar.owner_user_id)
    if not account or not account.refresh_token:
        return None
    return account, link


async def sync_created_events(db: Database, settings: Settings, calendar: Calendar, events: list[Event]) -> None:
    if not google_enabled(settings) or not events:
        return
    async with db.sessions() as session:
        ctx = await _load_sync_context(session, calendar)
        if not ctx:
            return
        account, link = ctx
        latest_creds: Credentials | None = None
        for event in events:
            try:
                body = event_to_google_body(event, calendar)
                loop = asyncio.get_running_loop()
                google_event_id, creds = await loop.run_in_executor(
                    None, lambda b=body: _insert_event_sync(settings, account, link.google_calendar_id, b))
                latest_creds = creds
                existing = await session.get(GoogleEventLink, event.id)
                if existing:
                    existing.google_event_id = google_event_id
                    existing.google_calendar_id = link.google_calendar_id
                else:
                    session.add(GoogleEventLink(
                        event_id=event.id, google_event_id=google_event_id, google_calendar_id=link.google_calendar_id))
            except Exception as exc:
                logger.warning("Google sync create failed for event %s: %s", event.id, exc)
        await session.commit()
        if latest_creds:
            await _persist_refreshed_tokens(session, account, latest_creds)


async def sync_changed_event(db: Database, settings: Settings, event: Event, calendar: Calendar, *, cancelled: bool) -> None:
    if not google_enabled(settings):
        return
    async with db.sessions() as session:
        ctx = await _load_sync_context(session, calendar)
        if not ctx:
            return
        account, link = ctx
        mapping = await session.get(GoogleEventLink, event.id)
        if not mapping:
            return
        loop = asyncio.get_running_loop()
        latest_creds: Credentials | None = None
        try:
            if cancelled:
                latest_creds = await loop.run_in_executor(
                    None,
                    lambda: _delete_event_sync(settings, account, mapping.google_calendar_id, mapping.google_event_id))
                await session.delete(mapping)
            else:
                body = event_to_google_body(event, calendar)
                latest_creds = await loop.run_in_executor(
                    None,
                    lambda: _update_event_sync(
                        settings, account, mapping.google_calendar_id, mapping.google_event_id, body))
        except Exception as exc:
            logger.warning("Google sync change failed for event %s: %s", event.id, exc)
        await session.commit()
        if latest_creds:
            await _persist_refreshed_tokens(session, account, latest_creds)


async def _persist_refreshed_tokens(session: AsyncSession, account: GoogleAccount, creds: Credentials) -> None:
    changed = False
    if creds.token and creds.token != account.access_token:
        account.access_token = creds.token
        changed = True
    expiry = _naive_utc(creds.expiry)
    if expiry != account.token_expiry:
        account.token_expiry = expiry
        changed = True
    if creds.refresh_token and creds.refresh_token != account.refresh_token:
        account.refresh_token = creds.refresh_token
        changed = True
    if changed:
        await session.commit()
