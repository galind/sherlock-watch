"""Environment-based runtime configuration."""

import os
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime and watcher settings with safe development defaults."""

    database_url: str
    vinted_base_url: str
    discord_webhook_url: str | None = None
    watch_interval_seconds: int = 3600
    watch_pages: int = 3
    watch_per_page: int = 48
    watch_watches_only: bool = True

    def __post_init__(self) -> None:
        if self.watch_interval_seconds < 1:
            raise ValueError("WATCH_INTERVAL_SECONDS must be a positive integer")
        if self.watch_pages < 1:
            raise ValueError("WATCH_PAGES must be a positive integer")
        if not 1 <= self.watch_per_page <= 96:
            raise ValueError("WATCH_PER_PAGE must be an integer between 1 and 96")
        if self.discord_webhook_url is not None:
            _validate_discord_webhook_url(self.discord_webhook_url)

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings with actionable errors."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        return cls(
            database_url=database_url,
            vinted_base_url=os.getenv("VINTED_BASE_URL", "https://www.vinted.es"),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
            watch_interval_seconds=_environment_int(
                "WATCH_INTERVAL_SECONDS", default=3600
            ),
            watch_pages=_environment_int("WATCH_PAGES", default=3),
            watch_per_page=_environment_int("WATCH_PER_PAGE", default=48),
            watch_watches_only=_environment_bool("WATCH_WATCHES_ONLY", default=True),
        )


def _environment_int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None


def _environment_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _validate_discord_webhook_url(url: str) -> None:
    try:
        parsed_url = urlsplit(url)
        host = parsed_url.hostname
        _ = parsed_url.port
    except ValueError:
        raise ValueError(
            "DISCORD_WEBHOOK_URL must be a valid HTTPS URL with a host"
        ) from None

    if (
        parsed_url.scheme.lower() != "https"
        or host is None
        or parsed_url.username is not None
        or parsed_url.password is not None
        or any(character.isspace() for character in url)
        or not _is_valid_host(host)
    ):
        raise ValueError("DISCORD_WEBHOOK_URL must be a valid HTTPS URL with a host")


def _is_valid_host(host: str) -> bool:
    try:
        ip_address(host)
        return True
    except ValueError:
        pass

    if len(host) > 253:
        return False
    labels = host.rstrip(".").split(".")
    return all(
        label
        and len(label) <= 63
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )
