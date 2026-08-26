from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, TypeDecorator,
    UniqueConstraint, inspect, text,
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


class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[int] = mapped_column(UtcOffsetHours, default=0)
    reminder_minutes: Mapped[str] = mapped_column(String(100), default="1440,30")
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
    custom_reminder_minutes: Mapped[str | None] = mapped_column(String(100), nullable=True)


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
            await connection.run_sync(_migrate_flat_events_to_occurrences)
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(_ensure_user_locale_column)
            await connection.run_sync(_ensure_event_recurrence_column)
            await connection.run_sync(_migrate_timezone_columns_to_int)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()


def _ensure_user_locale_column(sync_conn) -> None:
    tables = inspect(sync_conn).get_table_names()
    if "users" not in tables:
        return
    columns = {column["name"] for column in inspect(sync_conn).get_columns("users")}
    if "locale" not in columns:
        sync_conn.execute(text(f"ALTER TABLE users ADD COLUMN locale VARCHAR(8) DEFAULT '{DEFAULT_LOCALE}'"))


def _ensure_event_recurrence_column(sync_conn) -> None:
    tables = inspect(sync_conn).get_table_names()
    if "events" not in tables:
        return
    columns = {column["name"] for column in inspect(sync_conn).get_columns("events")}
    if "recurrence_json" not in columns:
        sync_conn.execute(text("ALTER TABLE events ADD COLUMN recurrence_json TEXT"))


def _migrate_timezone_columns_to_int(sync_conn) -> None:
    from .config import parse_timezone_offset

    tables = inspect(sync_conn).get_table_names()
    for table in ("users", "calendars"):
        if table not in tables:
            continue
        rows = sync_conn.execute(text(f"SELECT id, timezone FROM {table}")).mappings().all()
        for row in rows:
            raw = row["timezone"]
            try:
                hours = parse_timezone_offset(raw if isinstance(raw, int) else str(raw))
            except ValueError:
                hours = 0
            sync_conn.execute(
                text(f"UPDATE {table} SET timezone = :hours WHERE id = :id"),
                {"hours": hours, "id": row["id"]},
            )
        if sync_conn.dialect.name == "sqlite":
            sync_conn.execute(text(f"UPDATE {table} SET timezone = CAST(timezone AS INTEGER)"))
    if sync_conn.dialect.name == "postgresql":
        for table in ("users", "calendars"):
            if table not in tables:
                continue
            col_type = sync_conn.execute(text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = 'timezone'"
            ), {"table": table}).scalar()
            if col_type and col_type != "integer":
                sync_conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN timezone TYPE INTEGER USING timezone::integer"
                ))


def _table_columns(sync_conn, table: str) -> set[str]:
    if table not in inspect(sync_conn).get_table_names():
        return set()
    return {column["name"] for column in inspect(sync_conn).get_columns(table)}


def _migrate_flat_events_to_occurrences(sync_conn) -> None:
    """Upgrade legacy flat events (one row per date) to Event series + EventOccurrence."""
    tables = set(inspect(sync_conn).get_table_names())
    if "events" not in tables:
        return
    event_cols = _table_columns(sync_conn, "events")
    if "start_utc" not in event_cols:
        return

    dialect = sync_conn.dialect.name
    sync_conn.execute(text("""
        CREATE TABLE IF NOT EXISTS event_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            start_utc DATETIME NOT NULL,
            end_utc DATETIME NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            version INTEGER DEFAULT 1,
            updated_at DATETIME
        )
    """) if dialect == "sqlite" else text("""
        CREATE TABLE IF NOT EXISTS event_occurrences (
            id SERIAL PRIMARY KEY,
            event_id INTEGER NOT NULL,
            start_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            end_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            version INTEGER DEFAULT 1,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
    """))

    legacy = sync_conn.execute(text(
        "SELECT id, calendar_id, title, description, start_utc, end_utc, status, "
        "recurrence_group, version, updated_at FROM events ORDER BY id"
    )).mappings().all()
    if not legacy:
        _rebuild_events_table_without_occurrence_columns(sync_conn, dialect)
        _rename_child_event_fks_to_occurrence(sync_conn, dialect, {})
        return

    # old_event_id -> occurrence_id; group_key -> series event id
    id_map: dict[int, int] = {}
    series_ids: dict[str, int] = {}

    sync_conn.execute(text("""
        CREATE TABLE events_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendar_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at DATETIME,
            updated_at DATETIME
        )
    """) if dialect == "sqlite" else text("""
        CREATE TABLE events_series (
            id SERIAL PRIMARY KEY,
            calendar_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
    """))

    for row in legacy:
        group_key = row["recurrence_group"] or f"single:{row['id']}"
        if group_key not in series_ids:
            result = sync_conn.execute(text(
                "INSERT INTO events_series (calendar_id, title, description, status, created_at, updated_at) "
                "VALUES (:calendar_id, :title, :description, :status, :created_at, :updated_at)"
            ), {
                "calendar_id": row["calendar_id"],
                "title": row["title"],
                "description": row["description"] or "",
                "status": "active",
                "created_at": row["updated_at"],
                "updated_at": row["updated_at"],
            })
            series_ids[group_key] = int(result.lastrowid)
        series_id = series_ids[group_key]
        result = sync_conn.execute(text(
            "INSERT INTO event_occurrences (event_id, start_utc, end_utc, status, version, updated_at) "
            "VALUES (:event_id, :start_utc, :end_utc, :status, :version, :updated_at)"
        ), {
            "event_id": series_id,
            "start_utc": row["start_utc"],
            "end_utc": row["end_utc"],
            "status": row["status"] or "active",
            "version": row["version"] or 1,
            "updated_at": row["updated_at"],
        })
        id_map[int(row["id"])] = int(result.lastrowid)

    sync_conn.execute(text("DROP TABLE events"))
    sync_conn.execute(text("ALTER TABLE events_series RENAME TO events"))
    _rename_child_event_fks_to_occurrence(sync_conn, dialect, id_map)


def _rebuild_events_table_without_occurrence_columns(sync_conn, dialect: str) -> None:
    sync_conn.execute(text("""
        CREATE TABLE events_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendar_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at DATETIME,
            updated_at DATETIME
        )
    """) if dialect == "sqlite" else text("""
        CREATE TABLE events_series (
            id SERIAL PRIMARY KEY,
            calendar_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
    """))
    sync_conn.execute(text(
        "INSERT INTO events_series (id, calendar_id, title, description, status, created_at, updated_at) "
        "SELECT id, calendar_id, title, COALESCE(description, ''), COALESCE(status, 'active'), "
        "COALESCE(updated_at, CURRENT_TIMESTAMP), COALESCE(updated_at, CURRENT_TIMESTAMP) FROM events"
    ))
    sync_conn.execute(text("DROP TABLE events"))
    sync_conn.execute(text("ALTER TABLE events_series RENAME TO events"))


def _rename_child_event_fks_to_occurrence(sync_conn, dialect: str, id_map: dict[int, int]) -> None:
    """Rebuild child tables that referenced flat event ids so they reference occurrence ids."""
    tables = set(inspect(sync_conn).get_table_names())

    def remap(table: str, old_col: str, new_col: str, extra_cols: list[str], create_sql: str) -> None:
        if table not in tables:
            return
        cols = _table_columns(sync_conn, table)
        if new_col in cols and old_col not in cols:
            return
        if old_col not in cols:
            return
        sync_conn.execute(text(create_sql))
        rows = sync_conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
        for row in rows:
            old_id = row[old_col]
            new_id = id_map.get(int(old_id), int(old_id)) if id_map else int(old_id)
            payload = {new_col: new_id}
            for col in extra_cols:
                if col in row:
                    payload[col] = row[col]
            placeholders = ", ".join(f":{k}" for k in payload)
            columns = ", ".join(payload)
            sync_conn.execute(text(f"INSERT INTO {table}_new ({columns}) VALUES ({placeholders})"), payload)
        sync_conn.execute(text(f"DROP TABLE {table}"))
        sync_conn.execute(text(f"ALTER TABLE {table}_new RENAME TO {table}"))

    if dialect == "sqlite":
        remap(
            "event_confirmations", "event_id", "occurrence_id",
            ["id", "user_id", "display_name", "confirmed_at"],
            """CREATE TABLE event_confirmations_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurrence_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                display_name VARCHAR(200) DEFAULT '',
                confirmed_at DATETIME
            )""",
        )
        # notification_jobs: event_id/event_version -> occurrence_id/occurrence_version
        if "notification_jobs" in tables:
            cols = _table_columns(sync_conn, "notification_jobs")
            if "event_id" in cols:
                sync_conn.execute(text("""
                    CREATE TABLE notification_jobs_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        occurrence_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        kind VARCHAR(30) NOT NULL,
                        occurrence_version INTEGER NOT NULL,
                        scheduled_at DATETIME NOT NULL,
                        state VARCHAR(20) DEFAULT 'pending',
                        attempts INTEGER DEFAULT 0,
                        last_error TEXT,
                        sent_at DATETIME
                    )
                """))
                rows = sync_conn.execute(text("SELECT * FROM notification_jobs")).mappings().all()
                for row in rows:
                    old_id = int(row["event_id"])
                    sync_conn.execute(text(
                        "INSERT INTO notification_jobs_new "
                        "(id, occurrence_id, user_id, kind, occurrence_version, scheduled_at, state, attempts, last_error, sent_at) "
                        "VALUES (:id, :occurrence_id, :user_id, :kind, :occurrence_version, :scheduled_at, :state, :attempts, :last_error, :sent_at)"
                    ), {
                        "id": row["id"],
                        "occurrence_id": id_map.get(old_id, old_id) if id_map else old_id,
                        "user_id": row["user_id"],
                        "kind": row["kind"],
                        "occurrence_version": row.get("event_version") or row.get("occurrence_version") or 1,
                        "scheduled_at": row["scheduled_at"],
                        "state": row["state"],
                        "attempts": row["attempts"],
                        "last_error": row["last_error"],
                        "sent_at": row["sent_at"],
                    })
                sync_conn.execute(text("DROP TABLE notification_jobs"))
                sync_conn.execute(text("ALTER TABLE notification_jobs_new RENAME TO notification_jobs"))

        for table, create_sql in (
            ("google_event_links", """CREATE TABLE google_event_links_new (
                occurrence_id INTEGER PRIMARY KEY,
                google_event_id VARCHAR(256) NOT NULL,
                google_calendar_id VARCHAR(256) NOT NULL
            )"""),
            ("google_event_states", """CREATE TABLE google_event_states_new (
                occurrence_id INTEGER PRIMARY KEY,
                source VARCHAR(20) DEFAULT 'google',
                etag VARCHAR(256) DEFAULT '',
                recurring_event_id VARCHAR(256),
                original_start VARCHAR(64),
                html_link TEXT DEFAULT ''
            )"""),
            ("google_event_attendees", """CREATE TABLE google_event_attendees_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurrence_id INTEGER NOT NULL,
                email VARCHAR(320) NOT NULL,
                display_name VARCHAR(200) DEFAULT '',
                response_status VARCHAR(30) DEFAULT 'needsAction'
            )"""),
        ):
            if table not in tables:
                continue
            cols = _table_columns(sync_conn, table)
            if "occurrence_id" in cols and "event_id" not in cols:
                continue
            if "event_id" not in cols:
                continue
            sync_conn.execute(text(create_sql))
            rows = sync_conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
            for row in rows:
                data = dict(row)
                old_id = int(data.pop("event_id"))
                data["occurrence_id"] = id_map.get(old_id, old_id) if id_map else old_id
                columns = ", ".join(data)
                placeholders = ", ".join(f":{k}" for k in data)
                sync_conn.execute(text(f"INSERT INTO {table}_new ({columns}) VALUES ({placeholders})"), data)
            sync_conn.execute(text(f"DROP TABLE {table}"))
            sync_conn.execute(text(f"ALTER TABLE {table}_new RENAME TO {table}"))
