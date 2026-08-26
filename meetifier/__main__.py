from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .bots import build_organizer_router, build_participant_router, configure_commands
from .config import Settings
from .db import Database
from .oauth_server import run_oauth_server
from .worker import run_google_sync_worker, run_worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    db = Database(settings.database_url)
    await db.init()
    organizer, participant = Bot(settings.organizer_bot_token), Bot(settings.participant_bot_token)
    organizer_dp, participant_dp = Dispatcher(storage=MemoryStorage()), Dispatcher(storage=MemoryStorage())
    organizer_dp.include_router(build_organizer_router(db, settings, participant))
    participant_dp.include_router(build_participant_router(db, settings, organizer))
    await configure_commands(organizer, participant)
    tasks = [
        organizer_dp.start_polling(organizer, polling_timeout=settings.poll_timeout_seconds),
        participant_dp.start_polling(participant, polling_timeout=settings.poll_timeout_seconds),
        run_worker(db, participant, settings.worker_interval_seconds),
    ]
    if settings.google_client_id:
        tasks.append(run_oauth_server(settings, db, organizer))
        tasks.append(run_google_sync_worker(db, settings, participant))
    try:
        await asyncio.gather(*tasks)
    finally:
        await organizer.session.close(); await participant.session.close(); await db.close()


if __name__ == "__main__":
    asyncio.run(main())
