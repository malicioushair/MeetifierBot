from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot
from sqlalchemy import select

from .config import Settings
from .db import Database, User
from .google_sync import complete_oauth, consume_oauth_state, google_enabled, save_google_account
from .i18n import normalize_locale, t

logger = logging.getLogger(__name__)

SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Meetifier</title></head>
<body><h1>Google account linked</h1><p>You can close this page and return to the Organizer Bot.</p></body></html>"""

ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Meetifier</title></head>
<body><h1>Link failed</h1><p>{message}</p><p>Return to Telegram and try again.</p></body></html>"""


async def google_callback(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    db: Database = request.app["db"]
    bot: Bot = request.app["bot"]
    error = request.query.get("error")
    if error:
        return web.Response(text=ERROR_HTML.format(message=error), content_type="text/html", status=400)
    code = request.query.get("code")
    state = request.query.get("state")
    if not code or not state:
        return web.Response(text=ERROR_HTML.format(message="Missing code or state."), content_type="text/html", status=400)
    async with db.sessions() as session:
        telegram_id = await consume_oauth_state(session, state)
    if telegram_id is None:
        return web.Response(text=ERROR_HTML.format(message="Invalid or expired link."), content_type="text/html", status=400)
    try:
        refresh_token, access_token, expiry, email = await complete_oauth(settings, code)
        if not refresh_token:
            return web.Response(text=ERROR_HTML.format(message="Google did not return a refresh token."), content_type="text/html", status=400)
        async with db.sessions() as session:
            await save_google_account(session, telegram_id, settings.default_timezone, refresh_token, access_token, expiry, email)
        try:
            async with db.sessions() as session:
                user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
                locale = normalize_locale(user.locale if user else None)
            await bot.send_message(
                telegram_id,
                t(locale, "google_linked", email=email or t(locale, "google_connected")),
            )
        except Exception as exc:
            logger.warning("Could not notify organizer %s: %s", telegram_id, exc)
        return web.Response(text=SUCCESS_HTML, content_type="text/html")
    except Exception as exc:
        logger.exception("OAuth callback failed")
        return web.Response(text=ERROR_HTML.format(message=str(exc)), content_type="text/html", status=500)


async def run_oauth_server(settings: Settings, db: Database, bot: Bot) -> None:
    if not google_enabled(settings):
        return
    app = web.Application()
    app["settings"] = settings
    app["db"] = db
    app["bot"] = bot
    app.router.add_get("/oauth/google/callback", google_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.oauth_host, settings.oauth_port)
    await site.start()
    logger.info("Google OAuth server listening on %s:%s", settings.oauth_host, settings.oauth_port)
    try:
        await asyncio.Future()
    finally:
        await runner.cleanup()
