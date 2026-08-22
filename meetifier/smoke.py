"""Read-only local deployment checks (database and Telegram credentials)."""

from __future__ import annotations

import asyncio

from aiogram import Bot

from .config import Settings
from .db import Database


async def main() -> None:
    settings = Settings.from_env()
    database = Database(settings.database_url)
    organizer = Bot(settings.organizer_bot_token)
    participant = Bot(settings.participant_bot_token)
    try:
        await database.init()
        print(f"database_connection=ok dialect={database.engine.dialect.name}")
        organizer_info, participant_info = await asyncio.gather(
            organizer.get_me(), participant.get_me()
        )
        print(f"organizer_bot=ok username=@{organizer_info.username}")
        print(f"participant_bot=ok username=@{participant_info.username}")
        matches = (participant_info.username or "").casefold() == settings.participant_bot_username.casefold()
        print(f"participant_username_matches={matches}")
        if not matches:
            raise RuntimeError("PARTICIPANT_BOT_USERNAME does not match the configured bot token")
    finally:
        await organizer.session.close()
        await participant.session.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
