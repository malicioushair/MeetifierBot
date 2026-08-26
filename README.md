# Meetifier MVP

Meetifier runs two Telegram bots in one Python application with one durable database:

- **Organizer Bot** creates calendars, one-time/weekly events, invitation links, reschedules and cancellations.
- **Participant Bot** confirms deep-link subscriptions, shows upcoming events, handles timezones, reminder preferences, mute and unsubscribe.
- A database-backed worker sends reminders with retry/backoff and invalidates obsolete jobs after event changes.

Times are stored in UTC. SQLite is the zero-setup development default; Docker Compose uses PostgreSQL as the production-style source of truth.

## 1. Create the Telegram bots

In Telegram, message **@BotFather**:

1. Run `/newbot` twice, for example `Meetifier Organizer` and `Meetifier Participant`.
2. Save both tokens.
3. Note the participant bot username without `@`.
4. Optional: use `/setdescription` and `/setuserpic` for each bot.

A participant must open/start the Participant Bot before Telegram allows it to send reminders. The generated invitation link performs this onboarding.

## 2. Run locally (SQLite, no Docker)

Python 3.11+ is required. In PowerShell:

```powershell
cd C:\Users\Dima\repos\mine\MeetifierBot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` and set both BotFather tokens plus the participant username. Leave the SQLite `DATABASE_URL` unchanged, then run:

```powershell
python -m meetifier
```

The schema and `meetifier.db` are created automatically. Stop with Ctrl+C and start the same command again; pending reminders remain in the database.

To verify the database and both BotFather credentials without starting polling:

```powershell
python -m meetifier.smoke
```

## 3. Run with PostgreSQL and Docker

Install Docker Desktop, copy/edit `.env` as above, then:

```powershell
docker compose up --build
```

The compose file overrides `DATABASE_URL` so the app uses PostgreSQL. Stop with `docker compose down`; data remains in the named volume. `docker compose down -v` also deletes the database and is destructive.

## 4. Manual end-to-end test

Use two Telegram accounts if possible (one works too).

1. Open Organizer Bot and send `/start`.
2. Create a calendar:
   `/newcalendar Math class | Europe/Moscow`
3. Note its ID from the reply or `/calendars`.
4. Create an event 10+ minutes in the future (replace `1` with the calendar ID):
   `/newevent 1 | Algebra | 2026-09-01 18:30 | 60 | 1`
5. For a four-week class, use `4` as the last field.
6. Generate `/invite 1`, open the returned link, and tap **Subscribe** in Participant Bot.
7. In Participant Bot, run `/upcoming`, `/subscriptions`, and `/timezone Europe/Moscow`.
8. To test a reminder quickly, create another event several minutes ahead and set the calendar's participant preference before creating it: `/reminders 1 2,1`.
9. In Organizer Bot use `/events 1`, then `/reschedule EVENT_ID | 2026-09-02 19:00`; the participant receives an immediate update and reminder jobs are rebuilt.
10. Run `/cancel EVENT_ID`; the participant receives a cancellation and pending jobs become obsolete.
11. Verify `/mute 1`, `/unmute 1`, and `/unsubscribe 1` in Participant Bot.

Important: reminder preference changes apply to newly generated jobs. Reschedule an event after changing preferences to rebuild that event's jobs.

## Automated tests

```powershell
python -m pytest -q
```

The tests cover timezone conversion, weekly recurrence, job creation, reschedule invalidation, and unsubscribe cleanup. No Telegram tokens or network are needed.

## Google Calendar (optional, one-way export)

Organizers can mirror Meetifier events to Google Calendar. Participants still use Telegram only.

1. Create a Google Cloud project, enable **Google Calendar API**, and create an **OAuth 2.0 Web client**.
2. Add redirect URI: `http://127.0.0.1:8080/oauth/google/callback` (or your public URL in production).
3. Set in `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://127.0.0.1:8080/oauth/google/callback
OAUTH_HOST=127.0.0.1
OAUTH_PORT=8080
```

4. Restart the app. In **Organizer Bot**: tap **🔗 Link Google**, complete OAuth in the browser, then **📎 Map to Google** to link a Meetifier calendar to a Google calendar.
5. New, rescheduled, and cancelled events in that Meetifier calendar are pushed to Google automatically.

For Docker, expose port `8080` and set `GOOGLE_REDIRECT_URI` to your public HTTPS callback URL.

## MVP boundaries

- Weekly recurrence is materialized up to 52 occurrences; editing a whole series is not yet included.
- Immediate update messages are best-effort. Durable scheduled reminders are retried up to five times.
- Database tables are auto-created; add Alembic migrations before evolving a production deployment.
- Telegram long polling is used, so HTTPS/domain setup is unnecessary for the bots themselves.
- Google sync is one-way (Meetifier → Google). Two-way sync, Outlook, webhooks, and a web dashboard are later phases.
