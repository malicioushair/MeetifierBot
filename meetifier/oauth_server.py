from __future__ import annotations

import asyncio
import html
import logging

from aiohttp import web
from aiogram import Bot
from sqlalchemy import select

from .config import Settings
from .db import Database, User
from .google_sync import complete_oauth, consume_oauth_state, google_enabled, save_google_account
from .i18n import normalize_locale, t

logger = logging.getLogger(__name__)

SETTINGS_KEY = web.AppKey("settings", Settings)
DATABASE_KEY = web.AppKey("db", Database)
BOT_KEY = web.AppKey("bot", Bot)

SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Meetifier</title></head>
<body><h1>Google account linked</h1><p>You can close this page and return to the Organizer Bot.</p></body></html>"""

ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Meetifier</title></head>
<body><h1>Link failed</h1><p>{message}</p><p>Return to Telegram and try again.</p></body></html>"""

HTML_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def html_response(body: str, *, status: int = 200) -> web.Response:
    return web.Response(text=body, content_type="text/html", status=status, headers=HTML_HEADERS)


def error_response(message: str, *, status: int = 400) -> web.Response:
    return html_response(ERROR_HTML.format(message=html.escape(message)), status=status)


async def healthcheck(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"}, headers={"Cache-Control": "no-store"})


async def google_success(_: web.Request) -> web.Response:
    return html_response(SUCCESS_HTML)


async def google_callback(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS_KEY]
    db = request.app[DATABASE_KEY]
    bot = request.app[BOT_KEY]
    if not google_enabled(settings):
        return error_response("Google Calendar integration is not configured.", status=503)
    error = request.query.get("error")
    if error:
        logger.info("Google authorization returned an error: %r", error[:100])
        return error_response("Google authorization was denied or failed.")
    code = request.query.get("code")
    state = request.query.get("state")
    if not code or not state:
        return error_response("Missing code or state.")
    async with db.sessions() as session:
        telegram_id = await consume_oauth_state(session, state, settings.oauth_state_ttl_seconds)
    if telegram_id is None:
        return error_response("Invalid or expired link.")
    try:
        refresh_token, access_token, expiry, email = await complete_oauth(settings, code)
        if not refresh_token:
            return error_response("Google did not return a refresh token. Please start the link flow again.")
        async with db.sessions() as session:
            await save_google_account(
                session, settings, telegram_id, settings.default_timezone,
                refresh_token, access_token, expiry, email,
            )
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
        raise web.HTTPFound("/oauth/google/success", headers=HTML_HEADERS)
    except web.HTTPException:
        raise
    except Exception:
        logger.exception("OAuth callback failed")
        return error_response("Unable to link the Google account. Please try again.", status=500)


def create_http_app(settings: Settings, db: Database, bot: Bot) -> web.Application:
    app = web.Application()
    app[SETTINGS_KEY] = settings
    app[DATABASE_KEY] = db
    app[BOT_KEY] = bot
    app.router.add_get("/healthz", healthcheck)
    app.router.add_get("/oauth/google/callback", google_callback)
    app.router.add_get("/oauth/google/success", google_success)
    return app


async def run_oauth_server(settings: Settings, db: Database, bot: Bot) -> None:
    app = create_http_app(settings, db, bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.oauth_host, settings.oauth_port)
    await site.start()
    logger.info("Meetifier HTTP server listening on %s:%s", settings.oauth_host, settings.oauth_port)
    try:
        await asyncio.Future()
    finally:
        await runner.cleanup()
