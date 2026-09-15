import pytest
from cryptography.fernet import Fernet

from meetifier.config import Settings, validate_google_configuration


def settings(**overrides) -> Settings:
    values = {
        "organizer_bot_token": "a",
        "participant_bot_token": "b",
        "participant_bot_username": "c",
    }
    values.update(overrides)
    return Settings(**values)


def test_google_configuration_accepts_disabled_local_and_public_https():
    validate_google_configuration(settings())
    validate_google_configuration(settings(
        google_client_id="id",
        google_client_secret="secret",
        google_redirect_uri="http://127.0.0.1:8080/oauth/google/callback",
    ))
    validate_google_configuration(settings(
        google_client_id="id",
        google_client_secret="secret",
        google_redirect_uri="https://calendar.example.com/oauth/google/callback",
        google_token_encryption_key=Fernet.generate_key().decode("ascii"),
    ))


@pytest.mark.parametrize("redirect_uri", [
    "http://calendar.example.com/oauth/google/callback",
    "https://203.0.113.10/oauth/google/callback",
    "https://calendar.example.com/wrong-path",
    "https://calendar.example.com/oauth/google/callback?next=elsewhere",
])
def test_google_configuration_rejects_unsafe_public_redirects(redirect_uri):
    with pytest.raises(ValueError):
        validate_google_configuration(settings(
            google_client_id="id",
            google_client_secret="secret",
            google_redirect_uri=redirect_uri,
        ))


def test_google_configuration_rejects_partial_settings_and_invalid_ttl():
    with pytest.raises(ValueError, match="GOOGLE_CLIENT_SECRET"):
        validate_google_configuration(settings(
            google_client_id="id",
            google_redirect_uri="https://calendar.example.com/oauth/google/callback",
        ))
    with pytest.raises(ValueError, match="OAUTH_STATE_TTL_SECONDS"):
        validate_google_configuration(settings(
            google_client_id="id",
            google_client_secret="secret",
            google_redirect_uri="https://calendar.example.com/oauth/google/callback",
            oauth_state_ttl_seconds=0,
        ))


def test_public_google_configuration_requires_token_encryption():
    with pytest.raises(ValueError, match="GOOGLE_TOKEN_ENCRYPTION_KEY"):
        validate_google_configuration(settings(
            google_client_id="id",
            google_client_secret="secret",
            google_redirect_uri="https://calendar.example.com/oauth/google/callback",
        ))


def test_google_configuration_rejects_invalid_encryption_key():
    with pytest.raises(ValueError, match="GOOGLE_TOKEN_ENCRYPTION_KEY"):
        validate_google_configuration(settings(
            google_client_id="id",
            google_client_secret="secret",
            google_redirect_uri="https://calendar.example.com/oauth/google/callback",
            google_token_encryption_key="not-a-fernet-key",
        ))
