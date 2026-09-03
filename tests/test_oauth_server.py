from aiohttp.test_utils import make_mocked_request

from meetifier.config import Settings
from meetifier.oauth_server import (
    create_http_app,
    error_response,
    google_callback,
    google_success,
    healthcheck,
)


def test_error_response_escapes_html_and_prevents_caching():
    response = error_response('<script>alert("x")</script>')

    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")


async def test_http_health_and_public_pages():
    settings = Settings(
        organizer_bot_token="a", participant_bot_token="b", participant_bot_username="c",
    )
    app = create_http_app(settings, None, None)

    health = await healthcheck(make_mocked_request("GET", "/healthz", app=app))
    assert health.status == 200
    assert health.text == '{"status": "ok"}'

    success = await google_success(make_mocked_request("GET", "/oauth/google/success", app=app))
    assert success.status == 200
    assert "Google account linked" in success.text
    assert "no-store" == success.headers["Cache-Control"]

    disabled_callback = await google_callback(
        make_mocked_request("GET", "/oauth/google/callback", app=app)
    )
    assert disabled_callback.status == 503
    assert "not configured" in disabled_callback.text
