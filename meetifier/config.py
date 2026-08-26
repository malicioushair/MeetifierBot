from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# Fixed UTC hour offset. Valid civil-time range used by the bots.
MIN_UTC_OFFSET_HOURS = -12
MAX_UTC_OFFSET_HOURS = 14
DEFAULT_UTC_OFFSET_HOURS = 0


@dataclass(frozen=True)
class Settings:
    organizer_bot_token: str
    participant_bot_token: str
    participant_bot_username: str
    database_url: str = "sqlite+aiosqlite:///./meetifier.db"
    default_timezone: int = DEFAULT_UTC_OFFSET_HOURS
    poll_timeout_seconds: int = 20
    worker_interval_seconds: int = 5
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    oauth_host: str = "127.0.0.1"
    oauth_port: int = 8080
    google_sync_interval_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        settings = cls(
            organizer_bot_token=os.getenv("ORGANIZER_BOT_TOKEN", ""),
            participant_bot_token=os.getenv("PARTICIPANT_BOT_TOKEN", ""),
            participant_bot_username=os.getenv("PARTICIPANT_BOT_USERNAME", "").lstrip("@"),
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./meetifier.db"),
            default_timezone=parse_timezone_offset(os.getenv("DEFAULT_TIMEZONE", str(DEFAULT_UTC_OFFSET_HOURS))),
            poll_timeout_seconds=int(os.getenv("POLL_TIMEOUT_SECONDS", "20")),
            worker_interval_seconds=int(os.getenv("WORKER_INTERVAL_SECONDS", "5")),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
            oauth_host=os.getenv("OAUTH_HOST", "127.0.0.1"),
            oauth_port=int(os.getenv("OAUTH_PORT", "8080")),
            google_sync_interval_seconds=int(os.getenv("GOOGLE_SYNC_INTERVAL_SECONDS", "60")),
        )
        missing = [name for name, value in (
            ("ORGANIZER_BOT_TOKEN", settings.organizer_bot_token),
            ("PARTICIPANT_BOT_TOKEN", settings.participant_bot_token),
            ("PARTICIPANT_BOT_USERNAME", settings.participant_bot_username),
        ) if not value]
        if missing:
            raise ValueError("Missing settings: " + ", ".join(missing))
        return settings


def validate_timezone(value: int | str) -> int:
    return parse_timezone_offset(value)


def parse_timezone_offset(value: int | str) -> int:
    """Parse a UTC hour offset. Accepts int, '3', '+3', '-5', 'UTC+3', 'UTC-5', 'UTC'."""
    if isinstance(value, bool):
        raise ValueError(
            f"Timezone must be an integer UTC offset from {MIN_UTC_OFFSET_HOURS} to {MAX_UTC_OFFSET_HOURS}"
        )
    if isinstance(value, int):
        hours = value
    else:
        raw = str(value).strip()
        if not raw:
            raise ValueError(
                f"Timezone must be an integer UTC offset from {MIN_UTC_OFFSET_HOURS} to {MAX_UTC_OFFSET_HOURS}"
            )
        normalized = raw.upper().replace(" ", "")
        if normalized in {"UTC", "GMT", "Z"}:
            hours = 0
        elif normalized.startswith(("UTC", "GMT")):
            rest = normalized[3:] or "0"
            hours = int(rest)
        else:
            # Legacy IANA names (migration / Google import)
            if re.fullmatch(r"[A-Za-z_]+/[A-Za-z0-9_\-+]+", raw) or raw in {"UTC", "GMT"}:
                hours = iana_to_offset_hours(raw)
            else:
                try:
                    hours = int(normalized)
                except ValueError as exc:
                    raise ValueError(
                        f"Timezone must be an integer UTC offset from {MIN_UTC_OFFSET_HOURS} to "
                        f"{MAX_UTC_OFFSET_HOURS}, e.g. 3 or -5"
                    ) from exc
    if not MIN_UTC_OFFSET_HOURS <= hours <= MAX_UTC_OFFSET_HOURS:
        raise ValueError(
            f"Timezone must be an integer UTC offset from {MIN_UTC_OFFSET_HOURS} to {MAX_UTC_OFFSET_HOURS}"
        )
    return hours


def format_timezone_offset(hours: int | str) -> str:
    value = parse_timezone_offset(hours)
    return f"UTC{value:+d}"


def tzinfo_from_offset(hours: int | str) -> timezone:
    return timezone(timedelta(hours=parse_timezone_offset(hours)))


def iana_to_offset_hours(name: str) -> int:
    try:
        offset = datetime.now(ZoneInfo(name)).utcoffset()
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc
    if offset is None:
        return 0
    total_seconds = int(offset.total_seconds())
    # Round to nearest hour for storage as int.
    hours = int(round(total_seconds / 3600))
    return max(MIN_UTC_OFFSET_HOURS, min(MAX_UTC_OFFSET_HOURS, hours))


def google_timezone_id(hours: int | str) -> str:
    """Map UTC offset hours to an Etc/GMT zone id (sign is inverted in Etc/GMT)."""
    value = parse_timezone_offset(hours)
    if value == 0:
        return "UTC"
    return f"Etc/GMT{-value:+d}"
