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


def test_watcher_environment_configuration_is_parsed(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/sherlock")
    monkeypatch.setenv("WATCH_INTERVAL_SECONDS", "120")
    monkeypatch.setenv("WATCH_PAGES", "2")
    monkeypatch.setenv("WATCH_PER_PAGE", "24")
    monkeypatch.setenv("WATCH_WATCHES_ONLY", "false")

    settings = Settings.from_environment()

    assert settings.watch_interval_seconds == 120
    assert settings.watch_pages == 2
    assert settings.watch_per_page == 24
    assert settings.watch_watches_only is False


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("WATCH_INTERVAL_SECONDS", "0", "positive integer"),
        ("WATCH_PAGES", "many", "must be an integer"),
        ("WATCH_PER_PAGE", "97", "between 1 and 96"),
        ("WATCH_WATCHES_ONLY", "sometimes", "true or false"),
    ],
)
def test_invalid_watcher_environment_is_rejected_before_start(
    monkeypatch, name: str, value: str, message: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/sherlock")
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        Settings.from_environment()
