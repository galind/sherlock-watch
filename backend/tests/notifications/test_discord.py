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
    format_discord_embed,
)

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
        image_urls=(f"https://images.vinted.es/{number}.jpg",),
    )


def test_webhook_posts_query_count_and_listing_details() -> None:
    opener = RecordingOpener()
    notifier = DiscordWebhookNotifier(WEBHOOK_URL, opener=opener)

    notifier.notify("omega seamaster", [listing(1), listing(2)])

    assert len(opener.requests) == 2
    for request, timeout in opener.requests:
        payload = json.loads(request.data)
        assert request.full_url == WEBHOOK_URL
        assert request.method == "POST"
        assert request.get_header("Content-type") == "application/json"
        assert timeout == 10
        assert "content" not in payload
        assert len(payload["embeds"]) == 1

    first_embed = json.loads(opener.requests[0][0].data)["embeds"][0]
    assert first_embed["title"] == "Vintage watch 1"
    assert first_embed["url"] == "https://www.vinted.es/items/1-watch"
    assert first_embed["fields"] == [
        {"name": "Price", "value": "125.50 EUR", "inline": True},
        {"name": "Search", "value": "omega seamaster", "inline": True},
    ]
    assert first_embed["thumbnail"] == {
        "url": "https://images.vinted.es/1.jpg",
    }


def test_discord_embed_truncates_long_title_and_query() -> None:
    embed = format_discord_embed("search " * 100, listing(1, title="watch " * 100))

    assert len(embed["title"]) <= 256
    assert len(embed["fields"][1]["value"]) <= 200


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
