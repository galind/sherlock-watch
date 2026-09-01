"""HTTP client for eBay Browse API searches."""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

import httpx

EBAY_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayApiError(RuntimeError):
    """A safe, credential-free description of an eBay API failure."""


@dataclass(frozen=True, slots=True)
class EbaySearchPage:
    """One page of raw eBay item summaries."""

    items: tuple[Mapping[str, Any], ...]
    next_url: str | None


class EbayClient:
    """Authenticate and search eBay's Browse API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        environment: Literal["production", "sandbox"] = "production",
        marketplace_id: str = "EBAY_US",
        http_client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("eBay client ID and secret are required")
        if environment not in {"production", "sandbox"}:
            raise ValueError("eBay environment must be 'production' or 'sandbox'")
        if not marketplace_id.startswith("EBAY_"):
            raise ValueError("eBay marketplace ID must start with 'EBAY_'")

        host = "api.ebay.com" if environment == "production" else "api.sandbox.ebay.com"
        self._base_url = f"https://{host}"
        self._client_id = client_id
        self._client_secret = client_secret
        self._marketplace_id = marketplace_id
        self._http_client = http_client or httpx.Client(timeout=20.0)
        self._owns_http_client = http_client is None
        self._clock = clock
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    def close(self) -> None:
        """Close the internally created HTTP client."""
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def search(self, query: str, *, limit: int = 50, offset: int = 0) -> EbaySearchPage:
        """Return one page of active eBay item summaries for a keyword query."""
        if not query.strip():
            raise ValueError("eBay search query must not be empty")
        if not 1 <= limit <= 200:
            raise ValueError("eBay search limit must be between 1 and 200")
        if not 0 <= offset <= 9_999:
            raise ValueError("eBay search offset must be between 0 and 9999")

        payload = self._request_json(
            "GET",
            f"{self._base_url}/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {self._application_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            },
            params={"q": query.strip(), "limit": limit, "offset": offset},
            operation="search",
        )

        raw_items = payload.get("itemSummaries", [])
        if not isinstance(raw_items, list) or not all(
            isinstance(item, Mapping) for item in raw_items
        ):
            raise EbayApiError("eBay search returned an invalid itemSummaries payload")

        next_url = payload.get("next")
        if next_url is not None and not isinstance(next_url, str):
            raise EbayApiError("eBay search returned an invalid next page URL")

        return EbaySearchPage(items=tuple(raw_items), next_url=next_url)

    def _application_token(self) -> str:
        if (
            self._access_token is not None
            and self._clock() < self._access_token_expires_at
        ):
            return self._access_token

        payload = self._request_json(
            "POST",
            f"{self._base_url}/identity/v1/oauth2/token",
            auth=httpx.BasicAuth(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": EBAY_OAUTH_SCOPE},
            operation="OAuth",
        )
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(access_token, str) or not isinstance(expires_in, int):
            raise EbayApiError("eBay OAuth returned an invalid token payload")

        self._access_token = access_token
        # Refresh slightly early so a token does not expire during a request.
        self._access_token_expires_at = self._clock() + max(expires_in - 30, 0)
        return access_token

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        operation: str,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        try:
            response = self._http_client.request(method, url, **kwargs)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise EbayApiError(
                f"eBay {operation} request failed with HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise EbayApiError(f"eBay {operation} request failed") from exc

        if not isinstance(payload, Mapping):
            raise EbayApiError(f"eBay {operation} returned an invalid JSON payload")
        return payload
