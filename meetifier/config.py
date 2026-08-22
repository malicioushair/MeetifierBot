from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    organizer_bot_token: str
    participant_bot_token: str
    participant_bot_username: str
    database_url: str = "sqlite+aiosqlite:///./meetifier.db"
    default_timezone: str = "UTC"
    poll_timeout_seconds: int = 20
    worker_interval_seconds: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        settings = cls(
            organizer_bot_token=os.getenv("ORGANIZER_BOT_TOKEN", ""),
            participant_bot_token=os.getenv("PARTICIPANT_BOT_TOKEN", ""),
            participant_bot_username=os.getenv("PARTICIPANT_BOT_USERNAME", "").lstrip("@"),
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./meetifier.db"),
            default_timezone=os.getenv("DEFAULT_TIMEZONE", "UTC"),
            poll_timeout_seconds=int(os.getenv("POLL_TIMEOUT_SECONDS", "20")),
            worker_interval_seconds=int(os.getenv("WORKER_INTERVAL_SECONDS", "5")),
        )
        missing = [name for name, value in (
            ("ORGANIZER_BOT_TOKEN", settings.organizer_bot_token),
            ("PARTICIPANT_BOT_TOKEN", settings.participant_bot_token),
            ("PARTICIPANT_BOT_USERNAME", settings.participant_bot_username),
        ) if not value]
        if missing:
            raise ValueError("Missing settings: " + ", ".join(missing))
        validate_timezone(settings.default_timezone)
        return settings


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {value}") from exc
    return value

