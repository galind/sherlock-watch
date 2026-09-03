import pytest

from sherlock.config import Settings


def test_missing_discord_webhook_configuration_is_optional(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/sherlock")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    settings = Settings.from_environment()

    assert settings.discord_webhook_url is None


def test_https_discord_webhook_configuration_is_loaded(monkeypatch) -> None:
    webhook_url = "https://discord.com/api/webhooks/example-id/example-token"
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/sherlock")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", webhook_url)

    settings = Settings.from_environment()

    assert settings.discord_webhook_url == webhook_url


@pytest.mark.parametrize(
    "webhook_url",
    [
        "http://discord.com/api/webhooks/id/token",
        "https:///api/webhooks/id/token",
        "https://not a host/api/webhooks/id/token",
        "https://bad_host.example/api/webhooks/id/token",
        "not-a-url",
    ],
)
def test_invalid_discord_webhook_url_is_rejected(webhook_url: str) -> None:
    with pytest.raises(
        ValueError,
        match="DISCORD_WEBHOOK_URL must be a valid HTTPS URL with a host",
    ):
        Settings(
            database_url="postgresql+psycopg://localhost/sherlock",
            vinted_base_url="https://www.vinted.es",
            discord_webhook_url=webhook_url,
        )


def test_discord_webhook_validation_does_not_expose_url() -> None:
    webhook_url = "http://discord.example/api/webhooks/id/secret-token"

    with pytest.raises(ValueError) as error:
        Settings(
            database_url="postgresql+psycopg://localhost/sherlock",
            vinted_base_url="https://www.vinted.es",
            discord_webhook_url=webhook_url,
        )

    assert webhook_url not in str(error.value)
