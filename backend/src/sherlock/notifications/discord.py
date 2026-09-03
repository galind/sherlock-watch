"""Simple Discord webhook delivery."""

import json
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, Request, build_opener

from sherlock.domain import Listing

DISCORD_CONTENT_LIMIT = 2000
DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 10
_MAX_QUERY_LENGTH = 160
_MAX_LISTING_DETAILS = 10
_MAX_TITLE_LENGTH = 180
_MAX_URL_LENGTH = 500


class DiscordWebhookError(RuntimeError):
    """A safe description of a Discord webhook delivery failure."""


class DiscordWebhookNotifier:
    """Send aggregated listing notifications to a Discord webhook."""

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
        """Send one message describing newly discovered listings."""
        if not listings:
            return

        payload = json.dumps(
            {"content": format_discord_message(query, listings)},
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


def format_discord_message(query: str, listings: Sequence[Listing]) -> str:
    """Build a bounded Discord message with as many listing details as fit."""
    listing_noun = "listing" if len(listings) == 1 else "listings"
    header = (
        f'Vinted query "{_truncate(query.strip(), _MAX_QUERY_LENGTH)}": '
        f"{len(listings)} new {listing_noun}"
    )
    details: list[str] = []

    for listing in listings[:_MAX_LISTING_DETAILS]:
        detail = (
            f"- {_truncate(listing.title, _MAX_TITLE_LENGTH)} — "
            f"{listing.price.amount} {listing.price.currency}\n"
            f"  {_truncate(listing.url, _MAX_URL_LENGTH)}"
        )
        omitted_count = len(listings) - len(details) - 1
        parts = [header, *details, detail]
        if omitted_count:
            parts.append(_omitted_message(omitted_count))
        if len("\n\n".join(parts)) > DISCORD_CONTENT_LIMIT:
            break
        details.append(detail)

    omitted_count = len(listings) - len(details)
    parts = [header, *details]
    if omitted_count:
        parts.append(_omitted_message(omitted_count))
    return "\n\n".join(parts)


def _truncate(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"


def _omitted_message(count: int) -> str:
    noun = "listing" if count == 1 else "listings"
    return f"… {count} more {noun} omitted."
