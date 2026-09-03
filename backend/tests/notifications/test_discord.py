import io
import json
from decimal import Decimal
from typing import Self
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from sherlock.domain import Listing, Money
from sherlock.notifications import (
    DiscordWebhookError,
    DiscordWebhookNotifier,
    format_discord_message,
)
from sherlock.notifications.discord import DISCORD_CONTENT_LIMIT

WEBHOOK_URL = "https://discord.example/api/webhooks/id/secret-token"


class StubResponse(io.BytesIO):
    def __init__(self, status: int) -> None:
        super().__init__(b"")
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class RecordingOpener:
    def __init__(self, *, status: int = 204, error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.requests: list[tuple[Request, int]] = []

    def open(self, request: Request, *, timeout: int) -> StubResponse:
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return StubResponse(self.status)


def listing(number: int, *, title: str | None = None) -> Listing:
    return Listing(
        marketplace="vinted",
        external_id=str(number),
        url=f"https://www.vinted.es/items/{number}-watch",
        title=title or f"Vintage watch {number}",
        price=Money(Decimal("125.50"), "EUR"),
    )


def test_webhook_posts_query_count_and_listing_details() -> None:
    opener = RecordingOpener()
    notifier = DiscordWebhookNotifier(WEBHOOK_URL, opener=opener)

    notifier.notify("omega seamaster", [listing(1), listing(2)])

    assert len(opener.requests) == 1
    request, timeout = opener.requests[0]
    payload = json.loads(request.data)
    assert request.full_url == WEBHOOK_URL
    assert request.method == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == 10
    assert 'Vinted query "omega seamaster": 2 new listings' in payload["content"]
    assert "Vintage watch 1 — 125.50 EUR" in payload["content"]
    assert "https://www.vinted.es/items/1-watch" in payload["content"]


def test_webhook_message_stays_within_discord_limit_and_reports_omissions() -> None:
    listings = [
        listing(number, title="Very desirable vintage watch " * 20)
        for number in range(50)
    ]

    message = format_discord_message("collectible watches", listings)

    assert len(message) <= DISCORD_CONTENT_LIMIT
    assert "more listings omitted" in message
    assert "50 new listings" in message


def test_webhook_message_caps_listing_details_even_when_they_are_short() -> None:
    listings = [listing(number, title=f"Watch {number}") for number in range(20)]

    message = format_discord_message("watches", listings)

    assert "Watch 9 —" in message
    assert "Watch 10 —" not in message
    assert "10 more listings omitted" in message


def test_notifier_skips_empty_listing_collection() -> None:
    opener = RecordingOpener()

    DiscordWebhookNotifier(WEBHOOK_URL, opener=opener).notify("movado", [])

    assert opener.requests == []


@pytest.mark.parametrize("failure", [URLError("offline"), TimeoutError()])
def test_network_failures_raise_safe_error_without_webhook_url(failure) -> None:
    opener = RecordingOpener(error=failure)
    notifier = DiscordWebhookNotifier(WEBHOOK_URL, opener=opener)

    with pytest.raises(DiscordWebhookError) as error:
        notifier.notify("movado", [listing(1)])

    assert str(error.value) == "Discord webhook delivery failed"
    assert WEBHOOK_URL not in str(error.value)
    assert error.value.__cause__ is None


def test_http_failure_raises_safe_error_without_webhook_url() -> None:
    failure = HTTPError(WEBHOOK_URL, 429, "rate limited", {}, None)
    notifier = DiscordWebhookNotifier(
        WEBHOOK_URL,
        opener=RecordingOpener(error=failure),
    )

    with pytest.raises(DiscordWebhookError) as error:
        notifier.notify("movado", [listing(1)])

    assert str(error.value) == "Discord webhook delivery failed with HTTP 429"
    assert WEBHOOK_URL not in str(error.value)
    assert error.value.__cause__ is None
