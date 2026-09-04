"""Simple Discord webhook delivery."""

import json
import unicodedata
from collections.abc import Sequence
from datetime import UTC
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import OpenerDirector, Request, build_opener

from sherlock.domain import Listing

DEFAULT_WEBHOOK_TIMEOUT_SECONDS = 10
_VINTED_COLOR = 0x007782
_MAX_DESCRIPTION_LENGTH = 500
_MAX_QUERY_LENGTH = 200
_MAX_TITLE_LENGTH = 256
_MAX_URL_LENGTH = 2048
_MAX_METADATA_LENGTH = 256
_MAX_FIELD_VALUE_LENGTH = 1024
_MARKDOWN_CHARACTERS = frozenset("\\`*_~|>[]")


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
                self.notify_listing(query, listing)
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

    def notify_listing(self, query: str, listing: Listing) -> None:
        """Send one listing, allowing callers to track delivery separately."""
        payload = json.dumps(
            {
                "allowed_mentions": {"parse": []},
                "embeds": [format_discord_embed(query, listing)],
            },
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
    title = _format_text(listing.title, _MAX_TITLE_LENGTH)
    fields: list[dict[str, object]] = [
        {
            "name": "Price",
            "value": _format_price(listing),
            "inline": True,
        }
    ]
    _append_optional_field(fields, "Condition", listing.condition)
    _append_optional_field(fields, "Seller", listing.seller_name)
    _append_optional_field(fields, "Location", listing.location)
    fields.append(
        {
            "name": "Matched search",
            "value": _format_text(query, _MAX_QUERY_LENGTH) or "Unknown search",
            "inline": False,
        }
    )

    embed: dict[str, object] = {
        "title": title or "Untitled listing",
        "color": _VINTED_COLOR,
        "fields": fields,
    }

    if _is_safe_url(listing.url, marketplace=listing.marketplace):
        embed["url"] = listing.url

    if listing.description:
        description = _format_text(
            listing.description,
            _MAX_DESCRIPTION_LENGTH,
            preserve_newlines=True,
            word_boundary=True,
        )
        if description:
            embed["description"] = description

    image_urls = _valid_image_urls(listing)
    if image_urls:
        embed["image"] = {"url": image_urls[0]}

    footer_parts = [_marketplace_label(listing.marketplace)]
    if len(image_urls) > 1:
        footer_parts.append(f"{len(image_urls)} photos")
    if listing.published_at is not None:
        footer_parts.append("Published")
        embed["timestamp"] = (
            listing.published_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
    embed["footer"] = {"text": " • ".join(footer_parts)}

    return embed


def _append_optional_field(
    fields: list[dict[str, object]], name: str, value: str | None
) -> None:
    if value is None:
        return
    formatted_value = _format_text(value, _MAX_METADATA_LENGTH)
    if formatted_value:
        fields.append({"name": name, "value": formatted_value, "inline": True})


def _format_price(listing: Listing) -> str:
    return _truncate(
        f"{listing.price.amount:,f} {listing.price.currency}",
        _MAX_FIELD_VALUE_LENGTH,
    )


def _format_text(
    value: str,
    limit: int,
    *,
    preserve_newlines: bool = False,
    word_boundary: bool = False,
) -> str:
    without_controls = "".join(
        character
        for character in value
        if character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cf"}
    )
    if preserve_newlines:
        lines = (" ".join(line.split()) for line in without_controls.splitlines())
        normalized = "\n".join(line for line in lines if line)
    else:
        normalized = " ".join(without_controls.split())

    escaped = "".join(
        f"\\{character}" if character in _MARKDOWN_CHARACTERS else character
        for character in normalized
    )
    return _truncate(escaped, limit, word_boundary=word_boundary)


def _truncate(value: str, limit: int, *, word_boundary: bool = False) -> str:
    if len(value) <= limit:
        return value

    truncated = value[: limit - 1]
    if word_boundary and " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    truncated = truncated.rstrip("\\")
    return f"{truncated}…"


def _valid_image_urls(listing: Listing) -> tuple[str, ...]:
    urls: list[str] = []
    for url in listing.image_urls:
        if url not in urls and _is_safe_url(
            url, marketplace=listing.marketplace, image=True
        ):
            urls.append(url)
    return tuple(urls)


def _is_safe_url(url: str, *, marketplace: str, image: bool = False) -> bool:
    if len(url) > _MAX_URL_LENGTH or any(character.isspace() for character in url):
        return False

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return False

    if marketplace != "vinted":
        return True

    labels = hostname.lower().rstrip(".").split(".")
    uses_country_code_suffix = labels[-3:] == ["vinted", "co", "uk"]
    if not uses_country_code_suffix and (len(labels) < 2 or labels[-2] != "vinted"):
        return False
    if image:
        expected_length = 4 if uses_country_code_suffix else 3
        return len(labels) == expected_length and labels[0].startswith("images")
    expected_length = 3 if uses_country_code_suffix else 2
    return len(labels) == expected_length or (
        len(labels) == expected_length + 1 and labels[0] == "www"
    )


def _marketplace_label(marketplace: str) -> str:
    if marketplace.lower() == "vinted":
        return "Vinted"
    return _format_text(marketplace, _MAX_METADATA_LENGTH) or "Marketplace"
