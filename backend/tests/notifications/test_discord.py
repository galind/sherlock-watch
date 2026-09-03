import io
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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


def listing(number: int, *, title: str | None = None, **changes: object) -> Listing:
    base_listing = Listing(
        marketplace="vinted",
        external_id=str(number),
        url=f"https://www.vinted.es/items/{number}-watch",
        title=title or f"Vintage watch {number}",
        price=Money(Decimal("125.50"), "EUR"),
        image_urls=(f"https://images.vinted.es/{number}.jpg",),
    )
    return replace(base_listing, **changes)


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
        assert payload["allowed_mentions"] == {"parse": []}
        assert len(payload["embeds"]) == 1

    first_embed = json.loads(opener.requests[0][0].data)["embeds"][0]
    assert first_embed["title"] == "Vintage watch 1"
    assert first_embed["url"] == "https://www.vinted.es/items/1-watch"
    assert first_embed == {
        "title": "Vintage watch 1",
        "color": 30594,
        "url": "https://www.vinted.es/items/1-watch",
        "fields": [
            {"name": "Price", "value": "125.50 EUR", "inline": True},
            {
                "name": "Matched search",
                "value": "omega seamaster",
                "inline": False,
            },
        ],
        "image": {"url": "https://images.vinted.es/1.jpg"},
        "footer": {"text": "Vinted"},
    }


def test_discord_embed_includes_optional_evaluation_metadata() -> None:
    published_at = datetime(2026, 9, 3, 12, 42, 17, tzinfo=timezone(timedelta(hours=2)))
    embed = format_discord_embed(
        "omega seamaster",
        listing(
            1,
            description="Recently serviced.\n\nIncludes box and papers.",
            condition="Muy bueno",
            seller_name="example-seller",
            location="Barcelona, España",
            image_urls=(
                "https://images1.vinted.net/primary.jpg",
                "https://images1.vinted.net/caseback.jpg",
            ),
            published_at=published_at,
        ),
    )

    assert embed["description"] == "Recently serviced.\nIncludes box and papers."
    assert embed["fields"] == [
        {"name": "Price", "value": "125.50 EUR", "inline": True},
        {"name": "Condition", "value": "Muy bueno", "inline": True},
        {"name": "Seller", "value": "example-seller", "inline": True},
        {"name": "Location", "value": "Barcelona, España", "inline": True},
        {
            "name": "Matched search",
            "value": "omega seamaster",
            "inline": False,
        },
    ]
    assert embed["image"] == {"url": "https://images1.vinted.net/primary.jpg"}
    assert embed["footer"] == {"text": "Vinted • 2 photos • Published"}
    assert embed["timestamp"] == "2026-09-03T10:42:17Z"


def test_discord_embed_truncates_long_title_and_query() -> None:
    embed = format_discord_embed("search " * 100, listing(1, title="watch " * 100))

    assert len(embed["title"]) <= 256
    assert len(embed["fields"][-1]["value"]) <= 200


def test_discord_embed_uses_fallbacks_and_omits_blank_optional_values() -> None:
    embed = format_discord_embed(
        "\u202e",
        listing(
            1,
            title="  ",
            description="\u202e",
            condition="  ",
            seller_name="\u202e",
            image_urls=(),
        ),
    )

    assert embed["title"] == "Untitled listing"
    assert embed["fields"] == [
        {"name": "Price", "value": "125.50 EUR", "inline": True},
        {"name": "Matched search", "value": "Unknown search", "inline": False},
    ]
    assert "description" not in embed
    assert "image" not in embed
    assert embed["footer"] == {"text": "Vinted"}


def test_discord_embed_truncates_description_and_escapes_untrusted_markdown() -> None:
    embed = format_discord_embed(
        "omega",
        listing(
            1,
            description="[click](https://example.test) " + "description " * 100,
            seller_name="@everyone_*seller*",
        ),
    )

    assert len(embed["description"]) <= 500
    assert not embed["description"].startswith("[click]")
    assert embed["fields"][1]["value"] == "@everyone\\_\\*seller\\*"


def test_discord_embed_uses_first_valid_unique_image() -> None:
    embed = format_discord_embed(
        "omega",
        listing(
            1,
            image_urls=(
                "http://images1.vinted.net/insecure.jpg",
                "https://example.test/not-vinted.jpg",
                "https://images1.vinted.net/watch.jpg",
                "https://images1.vinted.net/watch.jpg",
                "https://images1.vinted.net/caseback.jpg",
            ),
        ),
    )

    assert embed["image"] == {"url": "https://images1.vinted.net/watch.jpg"}
    assert embed["footer"] == {"text": "Vinted • 2 photos"}


@pytest.mark.parametrize(
    "url",
    [
        "http://www.vinted.es/items/1-watch",
        "https://user:password@www.vinted.es/items/1-watch",
        "https://example.test/items/1-watch",
        "https://[invalid/items/1-watch",
        f"https://www.vinted.es/{'x' * 2048}",
    ],
)
def test_discord_embed_omits_unsafe_listing_url(url: str) -> None:
    embed = format_discord_embed("omega", listing(1, url=url))

    assert "url" not in embed


def test_discord_embed_formats_price_without_losing_decimal_precision() -> None:
    embed = format_discord_embed(
        "omega",
        listing(1, price=Money(Decimal("1234567.500"), "eur")),
    )

    assert embed["fields"][0]["value"] == "1,234,567.500 EUR"


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
