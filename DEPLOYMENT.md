# Meetifier VPS deployment

This deployment uses Docker Compose, PostgreSQL, and Caddy. Caddy obtains and renews the public TLS certificate. The Telegram bots use long polling, so the Google OAuth callback is the only public application endpoint.

## Prerequisites

- A Linux VM with Docker and the Compose plugin.
- A domain name whose `A`/`AAAA` record points to the VM.
- Inbound TCP ports 80 and 443 allowed. Do not expose port 8080 publicly.
- Outbound HTTPS access to Google and Telegram.

## Google Cloud configuration

1. Create or select a Google Cloud project and enable Google Calendar API.
2. Configure the OAuth consent screen. Use an Internal audience for a Workspace-only bot, or publish and verify an External app as appropriate.
3. Create an OAuth client with application type **Web application**.
4. Add exactly this authorized redirect URI, substituting your domain:

   `https://calendar.example.com/oauth/google/callback`

Do not use the VM IP address. Keep the consent screen out of Testing mode for persistent synchronization; Testing-mode refresh tokens for Calendar access expire after seven days.

## Environment

Copy `.env.example` to `.env` and set every secret value. In particular:

```dotenv
POSTGRES_PASSWORD=use-a-long-random-url-safe-password
MEETIFIER_DOMAIN=calendar.example.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://calendar.example.com/oauth/google/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=...
```

Generate the token encryption key once:

```sh
python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
```

Generate a URL-safe PostgreSQL password with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.

Keep this key stable and backed up. Losing or rotating it without a migration makes existing Google connections unreadable. On Google Cloud, store bot tokens, the OAuth client secret, database password, and encryption key in Secret Manager and inject them into the deployment environment. On another VPS, use an owner-readable environment file with mode `0600`.

Existing plaintext Google tokens are encrypted automatically after this key is configured and each account next synchronizes. If an existing PostgreSQL volume was initialized with a different password, update the `meetifier` database role password before changing `POSTGRES_PASSWORD`; changing the environment variable alone does not rewrite an initialized database.

## Start and verify

```sh
docker compose --profile production up -d --build
docker compose ps
curl --fail https://calendar.example.com/healthz
```

Then select **Link Google** in the Organizer Bot. The browser should return to a clean Meetifier success page. Restart the containers and run a manual Google sync to confirm that the persisted refresh token and PostgreSQL volume survive a restart.

Run only one `app` replica. Multiple long-polling bot or synchronization workers require leader election and shared FSM storage, which this deployment does not provide.

Back up the `postgres_data` volume regularly. Caddy certificate data is stored in `caddy_data` and is recreated automatically if lost.
