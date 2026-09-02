from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .i18n import DEFAULT_LOCALE


class UtcOffsetHours(TypeDecorator):
    """Store UTC hour offsets; coerce SQLite TEXT-affinity values back to int."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        from .config import parse_timezone_offset
        return parse_timezone_offset(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        from .config import parse_timezone_offset
        return parse_timezone_offset(value)


def utcnow() -> datetime:
    # Database timestamps intentionally use naive UTC for cross-dialect consistency.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    timezone: Mapped[int] = mapped_column(UtcOffsetHours, default=0)
    locale: Mapped[str] = mapped_column(String(8), default=DEFAULT_LOCALE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


DEFAULT_CONFIRMATION_HOURS = "24"  # organizer attendance ask
DEFAULT_NOTIFICATION_MINUTES = "60"  # 1h — participant-only reminder


class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[int] = mapped_column(UtcOffsetHours, default=0)
    confirmation_hours: Mapped[str] = mapped_column(String(100), default=DEFAULT_CONFIRMATION_HOURS)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    events: Mapped[list["Event"]] = relationship(back_populates="calendar")


class Event(Base):
    """Named event series inside a calendar (title/identity)."""

    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    recurrence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    calendar: Mapped["Calendar"] = relationship(back_populates="events")
    occurrences: Mapped[list["EventOccurrence"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="EventOccurrence.start_utc")


class EventOccurrence(Base):
    """Single date/instance of an event series."""

    __tablename__ = "event_occurrences"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    start_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    event: Mapped["Event"] = relationship(back_populates="occurrences")


class Invitation(Base):
    __tablename__ = "invitations"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "calendar_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Participant-only pre-event notifications; None → DEFAULT_NOTIFICATION_MINUTES
    notification_minutes: Mapped[str | None] = mapped_column(String(100), nullable=True)


class EventConfirmation(Base):
    __tablename__ = "event_confirmations"
    __table_args__ = (UniqueConstraint("occurrence_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("event_occurrences.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (UniqueConstraint("occurrence_id", "user_id", "kind", "occurrence_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("event_occurrences.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    occurrence_version: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    state: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GoogleAccount(Base):
    __tablename__ = "google_accounts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), default="")
    refresh_token: Mapped[str] = mapped_column(Text)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GoogleCalendarLink(Base):
    __tablename__ = "google_calendar_links"
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), primary_key=True)
    google_calendar_id: Mapped[str] = mapped_column(String(256))
    google_calendar_name: Mapped[str] = mapped_column(String(200), default="")


class GoogleEventLink(Base):
    __tablename__ = "google_event_links"
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("event_occurrences.id"), primary_key=True)
    google_event_id: Mapped[str] = mapped_column(String(256))
    google_calendar_id: Mapped[str] = mapped_column(String(256))


class GoogleCalendarSync(Base):
    __tablename__ = "google_calendar_syncs"
    calendar_id: Mapped[int] = mapped_column(ForeignKey("calendars.id"), primary_key=True)
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoogleEventState(Base):
    __tablename__ = "google_event_states"
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("event_occurrences.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), default="google")
    etag: Mapped[str] = mapped_column(String(256), default="")
    recurring_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    original_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    html_link: Mapped[str] = mapped_column(Text, default="")


class GoogleEventAttendee(Base):
    __tablename__ = "google_event_attendees"
    __table_args__ = (UniqueConstraint("occurrence_id", "email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("event_occurrences.id"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    response_status: Mapped[str] = mapped_column(String(30), default="needsAction")


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Database:
    def __init__(self, url: str):
        self.engine: AsyncEngine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
