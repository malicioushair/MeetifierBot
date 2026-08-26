from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import TypeVar

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, google_timezone_id, parse_timezone_offset, tzinfo_from_offset
from .db import (Calendar, Database, Event, EventConfirmation, GoogleAccount, GoogleCalendarLink,
                 GoogleCalendarSync, GoogleEventAttendee, GoogleEventLink, GoogleEventState,
                 Invitation, NotificationJob, OAuthState, User, utcnow)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]

T = TypeVar("T")


@dataclass(frozen=True)
class GoogleSyncChange:
    event_id: int
    action: str


@dataclass(frozen=True)
class GoogleSyncResult:
    calendar_id: int
    created: int = 0
    updated: int = 0
    cancelled: int = 0
    unchanged: int = 0
    changes: tuple[GoogleSyncChange, ...] = ()


class ExpiredSyncToken(Exception):
    pass


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
    tz = tzinfo_from_offset(calendar.timezone)
    zone_id = google_timezone_id(calendar.timezone)
    start = event.start_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    end = event.end_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    return {
        "summary": event.title,
        "start": {"dateTime": start.isoformat(), "timeZone": zone_id},
        "end": {"dateTime": end.isoformat(), "timeZone": zone_id},
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
        return [{
            "id": x["id"],
            "name": x.get("summary", x["id"]),
            "timezone": x.get("timeZone", "UTC"),
            "access_role": x.get("accessRole", "reader"),
        } for x in items if x.get("accessRole") in {"owner", "writer"}]

    return _with_calendar_service(settings, account, list_calendars)


def _list_events_sync(settings: Settings, account: GoogleAccount, google_calendar_id: str,
                      sync_token: str | None) -> tuple[list[dict], str | None, Credentials]:
    def list_events(service):
        events: list[dict] = []
        page_token = None
        next_sync_token = None
        while True:
            kwargs = {
                "calendarId": google_calendar_id,
                "singleEvents": True,
                "showDeleted": True,
                "maxResults": 2500,
                "pageToken": page_token,
            }
            if sync_token:
                kwargs["syncToken"] = sync_token
            else:
                kwargs["timeMin"] = datetime.now(timezone.utc).isoformat()
                kwargs["timeMax"] = (datetime.now(timezone.utc) + timedelta(days=366)).isoformat()
                kwargs["orderBy"] = "startTime"
            try:
                response = service.events().list(**kwargs).execute()
            except Exception as exc:
                if getattr(getattr(exc, "resp", None), "status", None) == 410:
                    raise ExpiredSyncToken from exc
                raise
            events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            next_sync_token = response.get("nextSyncToken", next_sync_token)
            if not page_token:
                return events, next_sync_token, None

    result, creds = _with_calendar_service(settings, account, list_events)
    events, next_sync_token, _ = result
    return events, next_sync_token, creds


def _patch_adoption_link_sync(settings: Settings, account: GoogleAccount, google_calendar_id: str,
                              google_event_id: str, invitation_url: str) -> tuple[bool, Credentials]:
    def patch_event(service):
        resource = service.events().get(calendarId=google_calendar_id, eventId=google_event_id).execute()
        description = resource.get("description", "")
        label = "Meetifier reminders:"
        lines = [line for line in description.splitlines() if not line.strip().startswith(label)]
        new_description = "\n".join(lines).rstrip()
        new_description = f"{new_description}\n\n{label} {invitation_url}".strip()
        if new_description == description:
            return False
        service.events().patch(
            calendarId=google_calendar_id,
            eventId=google_event_id,
            body={"description": new_description},
            sendUpdates="all",
        ).execute()
        return True

    return _with_calendar_service(settings, account, patch_event)


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
        service.events().patch(
            calendarId=google_calendar_id,
            eventId=google_event_id,
            body=body,
            sendUpdates="all",
        ).execute()

    _, creds = _with_calendar_service(settings, account, update_event)
    return creds


def _delete_event_sync(
    settings: Settings, account: GoogleAccount, google_calendar_id: str, google_event_id: str,
) -> Credentials:
    def delete_event(service):
        service.events().delete(
            calendarId=google_calendar_id,
            eventId=google_event_id,
            sendUpdates="all",
        ).execute()

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
    already_linked = await session.scalar(
        select(GoogleCalendarLink).join(Calendar).where(
            Calendar.owner_user_id == account.user_id,
            GoogleCalendarLink.google_calendar_id == google_calendar_id,
            GoogleCalendarLink.calendar_id != calendar_id,
        )
    )
    if already_linked:
        raise ValueError("That Google calendar is already linked to another Meetifier calendar")
    link = await session.get(GoogleCalendarLink, calendar_id)
    if link:
        if link.google_calendar_id != google_calendar_id:
            raise ValueError("This Meetifier calendar is already mapped to a different Google calendar")
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


def _google_datetime(value: dict, tz_offset_hours: int | str) -> datetime:
    if value.get("dateTime"):
        parsed = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    else:
        parsed = datetime.combine(
            date.fromisoformat(value["date"]), time.min, tzinfo_from_offset(tz_offset_hours))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


async def import_google_calendar(db: Database, settings: Settings, telegram_id: int,
                                 google_calendar: dict[str, str]) -> tuple[Calendar, GoogleSyncResult]:
    """Create or reuse a Meetifier calendar and immediately import its Google events."""
    from .service import create_calendar

    async with db.sessions() as session:
        existing = await session.scalar(
            select(Calendar).join(GoogleCalendarLink).join(User).where(
                User.telegram_id == telegram_id,
                GoogleCalendarLink.google_calendar_id == google_calendar["id"],
            )
        )
        if existing:
            calendar = existing
        else:
            timezone_offset = parse_timezone_offset(
                google_calendar.get("timezone") or settings.default_timezone)
            calendar = await create_calendar(
                session, telegram_id, google_calendar["name"], timezone_offset, settings.default_timezone)
            await link_google_calendar(
                session, telegram_id, calendar.id, google_calendar["id"], google_calendar["name"])
        calendar_id = calendar.id
    result = await sync_google_calendar(db, settings, calendar_id, force_full=True)
    return calendar, result


async def _replace_attendees(session: AsyncSession, event_id: int, attendees: list[dict]) -> None:
    await session.execute(delete(GoogleEventAttendee).where(GoogleEventAttendee.event_id == event_id))
    seen: set[str] = set()
    for attendee in attendees:
        email = (attendee.get("email") or "").strip().lower()
        if not email or email in seen or attendee.get("self"):
            continue
        seen.add(email)
        session.add(GoogleEventAttendee(
            event_id=event_id,
            email=email,
            display_name=(attendee.get("displayName") or "")[:200],
            response_status=(attendee.get("responseStatus") or "needsAction")[:30],
        ))


async def _upsert_google_event(session: AsyncSession, calendar: Calendar, link: GoogleCalendarLink,
                               item: dict) -> GoogleSyncChange | None:
    from .service import create_jobs_for_event

    if item.get("eventType", "default") != "default":
        return None
    organizer = item.get("organizer") or {}
    if organizer and not organizer.get("self", False):
        return None
    google_event_id = item.get("id")
    if not google_event_id:
        return None
    mapping = await session.scalar(select(GoogleEventLink).where(
        GoogleEventLink.google_calendar_id == link.google_calendar_id,
        GoogleEventLink.google_event_id == google_event_id,
    ))
    event = await session.get(Event, mapping.event_id) if mapping else None
    status = item.get("status", "confirmed")
    if status == "cancelled":
        if not event or event.status == "cancelled":
            return None
        await session.execute(update(NotificationJob).where(
            NotificationJob.event_id == event.id,
            NotificationJob.state == "pending",
        ).values(state="obsolete"))
        await session.execute(delete(EventConfirmation).where(EventConfirmation.event_id == event.id))
        event.status = "cancelled"
        event.version += 1
        return GoogleSyncChange(event.id, "cancelled")

    if not item.get("start") or not item.get("end"):
        return None
    start_utc = _google_datetime(item["start"], calendar.timezone)
    end_utc = _google_datetime(item["end"], calendar.timezone)
    title = (item.get("summary") or "(Untitled)")[:200]
    description = item.get("description") or ""
    created = event is None
    if created:
        event = Event(
            calendar_id=calendar.id,
            title=title,
            description=description,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        session.add(event)
        await session.flush()
        mapping = GoogleEventLink(
            event_id=event.id,
            google_event_id=google_event_id,
            google_calendar_id=link.google_calendar_id,
        )
        session.add(mapping)
        state = GoogleEventState(event_id=event.id, source="google")
        session.add(state)
        await create_jobs_for_event(session, event, calendar)
        action = "created"
    else:
        state = await session.get(GoogleEventState, event.id)
        if not state:
            state = GoogleEventState(event_id=event.id, source="meetifier")
            session.add(state)
        changed = (
            event.title != title or event.start_utc != start_utc or
            event.end_utc != end_utc or event.status != "active"
        )
        event.description = description
        if changed:
            await session.execute(update(NotificationJob).where(
                NotificationJob.event_id == event.id,
                NotificationJob.state == "pending",
            ).values(state="obsolete"))
            await session.execute(delete(EventConfirmation).where(EventConfirmation.event_id == event.id))
            event.title = title
            event.start_utc = start_utc
            event.end_utc = end_utc
            event.status = "active"
            event.version += 1
            await create_jobs_for_event(session, event, calendar)
            action = "updated"
        else:
            action = "unchanged"
    state.etag = (item.get("etag") or "")[:256]
    state.recurring_event_id = item.get("recurringEventId")
    original_start = item.get("originalStartTime") or {}
    state.original_start = original_start.get("dateTime") or original_start.get("date")
    state.html_link = item.get("htmlLink") or ""
    await _replace_attendees(session, event.id, item.get("attendees") or [])
    return GoogleSyncChange(event.id, action)


async def sync_google_calendar(db: Database, settings: Settings, calendar_id: int,
                               *, force_full: bool = False) -> GoogleSyncResult:
    async with db.sessions() as session:
        calendar = await session.get(Calendar, calendar_id)
        if not calendar:
            raise ValueError("Calendar not found")
        ctx = await _load_sync_context(session, calendar)
        if not ctx:
            raise ValueError("Calendar is not linked to Google")
        account, link = ctx
        sync_state = await session.get(GoogleCalendarSync, calendar_id)
        sync_token = None if force_full or not sync_state else sync_state.sync_token
        loop = asyncio.get_running_loop()
        try:
            items, next_sync_token, creds = await loop.run_in_executor(
                None,
                lambda: _list_events_sync(settings, account, link.google_calendar_id, sync_token),
            )
        except ExpiredSyncToken:
            items, next_sync_token, creds = await loop.run_in_executor(
                None,
                lambda: _list_events_sync(settings, account, link.google_calendar_id, None),
            )
        if not sync_state:
            sync_state = GoogleCalendarSync(calendar_id=calendar_id)
            session.add(sync_state)
        changes: list[GoogleSyncChange] = []
        try:
            for item in items:
                change = await _upsert_google_event(session, calendar, link, item)
                if change:
                    changes.append(change)
            sync_state.sync_token = next_sync_token or sync_state.sync_token
            sync_state.last_synced_at = utcnow()
            sync_state.last_error = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            async with db.sessions() as error_session:
                state = await error_session.get(GoogleCalendarSync, calendar_id)
                if not state:
                    state = GoogleCalendarSync(calendar_id=calendar_id)
                    error_session.add(state)
                state.last_error = str(exc)[:2000]
                await error_session.commit()
            raise
        await _persist_refreshed_tokens(session, account, creds)
        counts = {name: sum(c.action == name for c in changes) for name in ("created", "updated", "cancelled", "unchanged")}
        visible_changes = tuple(c for c in changes if c.action != "unchanged")
        return GoogleSyncResult(calendar_id=calendar_id, changes=visible_changes, **counts)


async def sync_all_google_calendars(db: Database, settings: Settings) -> list[GoogleSyncResult]:
    if not google_enabled(settings):
        return []
    async with db.sessions() as session:
        calendar_ids = list((await session.scalars(select(GoogleCalendarLink.calendar_id))).all())
    results = []
    for calendar_id in calendar_ids:
        try:
            results.append(await sync_google_calendar(db, settings, calendar_id))
        except Exception as exc:
            logger.warning("Google import sync failed for calendar %s: %s", calendar_id, exc)
    return results


async def adopt_google_calendar(db: Database, settings: Settings, telegram_id: int,
                                calendar_id: int, participant_bot_username: str) -> tuple[int, int, str]:
    """Add a stable bot onboarding link to Google events and notify their attendees."""
    async with db.sessions() as session:
        calendar = await session.scalar(select(Calendar).join(User).where(
            Calendar.id == calendar_id, User.telegram_id == telegram_id))
        if not calendar:
            raise PermissionError("Calendar not found or not owned by you")
        ctx = await _load_sync_context(session, calendar)
        if not ctx:
            raise ValueError("Calendar is not linked to Google")
        account, link = ctx
        invitation = await session.scalar(select(Invitation).where(
            Invitation.calendar_id == calendar_id,
            (Invitation.expires_at.is_(None)) | (Invitation.expires_at > utcnow()),
        ).order_by(Invitation.created_at.desc()))
        if not invitation:
            import secrets
            invitation = Invitation(token=secrets.token_urlsafe(24), calendar_id=calendar_id)
            session.add(invitation)
            await session.commit()
        invitation_url = f"https://t.me/{participant_bot_username}?start={invitation.token}"
        rows = (await session.execute(
            select(GoogleEventLink.google_event_id, GoogleEventState.recurring_event_id, Event.id)
            .join(Event, Event.id == GoogleEventLink.event_id)
            .outerjoin(GoogleEventState, GoogleEventState.event_id == Event.id)
            .where(
                Event.calendar_id == calendar_id,
                Event.status == "active",
                Event.end_utc > utcnow(),
                select(GoogleEventAttendee.id).where(
                    GoogleEventAttendee.event_id == Event.id).exists(),
            )
        )).all()
        targets = {recurring_id or google_event_id for google_event_id, recurring_id, _ in rows}
        loop = asyncio.get_running_loop()
        updated = 0
        latest_creds = None
        for google_event_id in targets:
            changed, creds = await loop.run_in_executor(
                None,
                lambda event_id=google_event_id: _patch_adoption_link_sync(
                    settings, account, link.google_calendar_id, event_id, invitation_url),
            )
            updated += int(changed)
            latest_creds = creds
        if latest_creds:
            await _persist_refreshed_tokens(session, account, latest_creds)
        return updated, len(targets), invitation_url


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
