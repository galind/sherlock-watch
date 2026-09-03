"""Simple Discord webhook delivery."""

import json
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, Request, build_opener

from sherlock.domain import Listing

DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 10
_MAX_QUERY_LENGTH = 200
_MAX_TITLE_LENGTH = 256
_MAX_URL_LENGTH = 2048


class DiscordWebhookError(RuntimeError):
    """A safe description of a Discord webhook delivery failure."""


class DiscordWebhookNotifier:
    """Send one embedded listing notification per newly found watch."""

    def __init__(
        self,
        webhook_url: str,
        *,
        timeout: int = DEFAULT_WEBHOOK_TIMEOUT_SECONDS,
        opener: OpenerDirector | None = None,
    ) -> None:
        if timeout < 1:
            raise ValueError("Discord webhook timeout must be positive")

        self._webhook_url = webhook_url
        self._timeout = timeout
        self._opener = opener or build_opener()

    def notify(self, query: str, listings: Sequence[Listing]) -> None:
        """Send one embedded message for each newly discovered listing."""
        if not listings:
            return

        failures = 0
        first_failure: DiscordWebhookError | None = None
        for listing in listings:
            try:
                self._send_listing(query, listing)
            except DiscordWebhookError as error:
                failures += 1
                first_failure = first_failure or error

        if failures:
            if failures == 1 and first_failure is not None:
                raise first_failure
            noun = "listing" if failures == 1 else "listings"
            raise DiscordWebhookError(
                f"Discord webhook delivery failed for {failures} {noun}"
            )

    def _send_listing(self, query: str, listing: Listing) -> None:
        payload = json.dumps(
            {"embeds": [format_discord_embed(query, listing)]},
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self._webhook_url,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Sherlock/0.1",
            },
            method="POST",
        )

        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                status = response.status
        except HTTPError as error:
            raise DiscordWebhookError(
                f"Discord webhook delivery failed with HTTP {error.code}"
            ) from None
        except (URLError, TimeoutError, OSError):
            raise DiscordWebhookError("Discord webhook delivery failed") from None

        if not 200 <= status < 300:
            raise DiscordWebhookError(
                f"Discord webhook delivery failed with HTTP {status}"
            )


def format_discord_embed(query: str, listing: Listing) -> dict[str, object]:
    """Build one Discord embed for a newly discovered listing."""
    embed: dict[str, object] = {
        "title": _truncate(listing.title, _MAX_TITLE_LENGTH),
        "url": _truncate(listing.url, _MAX_URL_LENGTH),
        "fields": [
            {
                "name": "Price",
                "value": f"{listing.price.amount} {listing.price.currency}",
                "inline": True,
            },
            {
                "name": "Search",
                "value": _truncate(query.strip(), _MAX_QUERY_LENGTH),
                "inline": True,
            },
        ],
    }
    if listing.image_urls:
        embed["thumbnail"] = {"url": listing.image_urls[0]}
    return embed


def _truncate(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"
