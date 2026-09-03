"""HTTP client for Vinted's anonymous web catalog search."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener

DEFAULT_VINTED_BASE_URL = "https://www.vinted.es"
VINTED_WATCH_CATALOG_IDS = (22, 97)
VINTED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)


class VintedApiError(RuntimeError):
    """A safe description of a Vinted web API failure."""


@dataclass(frozen=True, slots=True)
class VintedSearchPage:
    """One page of raw Vinted catalog results."""

    items: tuple[Mapping[str, Any], ...]
    current_page: int
    total_pages: int
    total_entries: int


class VintedClient:
    """Bootstrap an anonymous Vinted session and search its web catalog API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_VINTED_BASE_URL,
        opener: OpenerDirector | None = None,
    ) -> None:
        parsed_url = urlparse(base_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ValueError("Vinted base URL must be an HTTPS origin")

        self._base_url = base_url.rstrip("/")
        self._opener = opener or build_opener(HTTPCookieProcessor(CookieJar()))
        self._bootstrapped = False

    def close(self) -> None:
        """Support the same context-manager shape as other HTTP clients."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def search(
        self,
        query: str,
        *,
        page: int = 1,
        per_page: int = 48,
        catalog_ids: Sequence[int] = (),
    ) -> VintedSearchPage:
        """Return one newest-first page for a keyword query."""
        if not query.strip():
            raise ValueError("Vinted search query must not be empty")
        if page < 1:
            raise ValueError("Vinted search page must be positive")
        if not 1 <= per_page <= 96:
            raise ValueError("Vinted per-page limit must be between 1 and 96")
        normalized_catalog_ids = tuple(catalog_ids)
        if any(
            type(catalog_id) is not int or catalog_id < 1
            for catalog_id in normalized_catalog_ids
        ):
            raise ValueError("Vinted catalog IDs must be positive integers")

        if not self._bootstrapped:
            self._bootstrap_anonymous_session()

        params: dict[str, str | int] = {
            "search_text": query.strip(),
            "order": "newest_first",
            "page": page,
            "per_page": per_page,
            "disable_search_saving": "true",
        }
        if normalized_catalog_ids:
            params["catalog_ids"] = ",".join(map(str, normalized_catalog_ids))

        encoded_params = urlencode(params)
        payload = self._request_json(
            f"{self._base_url}/api/v2/catalog/items?{encoded_params}"
        )

        raw_items = payload.get("items")
        pagination = payload.get("pagination")
        if not isinstance(raw_items, list) or not all(
            isinstance(item, Mapping) for item in raw_items
        ):
            raise VintedApiError("Vinted search returned an invalid items payload")
        if not isinstance(pagination, Mapping):
            raise VintedApiError("Vinted search returned invalid pagination")

        current_page = pagination.get("current_page")
        total_pages = pagination.get("total_pages")
        total_entries = pagination.get("total_entries")
        if not all(
            isinstance(value, int)
            for value in (current_page, total_pages, total_entries)
        ):
            raise VintedApiError("Vinted search returned invalid pagination values")

        return VintedSearchPage(
            items=tuple(raw_items),
            current_page=current_page,
            total_pages=total_pages,
            total_entries=total_entries,
        )

    def _bootstrap_anonymous_session(self) -> None:
        request = Request(
            self._base_url,
            headers={"User-Agent": VINTED_USER_AGENT},
        )
        try:
            with self._opener.open(request, timeout=20):
                pass
        except HTTPError as exc:
            raise VintedApiError(
                f"Vinted anonymous session bootstrap failed with HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise VintedApiError("Vinted anonymous session bootstrap failed") from exc
        self._bootstrapped = True

    def _request_json(self, url: str) -> Mapping[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Referer": f"{self._base_url}/catalog",
                "User-Agent": VINTED_USER_AGENT,
            },
        )
        try:
            with self._opener.open(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise VintedApiError(
                f"Vinted search request failed with HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise VintedApiError("Vinted search request failed") from exc

        if not isinstance(payload, Mapping):
            raise VintedApiError("Vinted search returned an invalid JSON payload")
        if payload.get("code") != 0:
            message_code = payload.get("message_code", "unknown error")
            raise VintedApiError(f"Vinted search was rejected: {message_code}")
        return payload
