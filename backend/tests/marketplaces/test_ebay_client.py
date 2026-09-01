import base64
import json
from typing import Any

import httpx
import pytest

from sherlock.marketplaces.ebay import EbayApiError, EbayClient


def test_search_mints_application_token_and_returns_first_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/identity/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "application-token", "expires_in": 7200},
            )
        return httpx.Response(
            200,
            json={
                "itemSummaries": [{"itemId": "v1|123|0"}],
                "next": "https://api.ebay.com/next-page",
            },
        )

    client = EbayClient(
        "client-id",
        "client-secret",
        marketplace_id="EBAY_DE",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    page = client.search("  nomos tangente  ", limit=25)

    assert page.items == ({"itemId": "v1|123|0"},)
    assert page.next_url == "https://api.ebay.com/next-page"
    assert len(requests) == 2

    token_request, search_request = requests
    assert token_request.method == "POST"
    assert token_request.url.path == "/identity/v1/oauth2/token"
    assert token_request.headers["authorization"] == (
        "Basic " + base64.b64encode(b"client-id:client-secret").decode()
    )
    assert token_request.headers["content-type"].startswith(
        "application/x-www-form-urlencoded"
    )
    assert token_request.content == (
        b"grant_type=client_credentials&"
        b"scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope"
    )

    assert search_request.method == "GET"
    assert search_request.url.path == "/buy/browse/v1/item_summary/search"
    assert dict(search_request.url.params) == {
        "q": "nomos tangente",
        "limit": "25",
        "offset": "0",
    }
    assert search_request.headers["authorization"] == "Bearer application-token"
    assert search_request.headers["x-ebay-c-marketplace-id"] == "EBAY_DE"


def test_search_reuses_unexpired_application_token() -> None:
    token_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/identity/v1/oauth2/token":
            token_requests += 1
            return httpx.Response(200, json={"access_token": "token", "expires_in": 60})
        return httpx.Response(200, json={"itemSummaries": []})

    client = EbayClient(
        "client-id",
        "client-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: 100.0,
    )

    client.search("omega")
    client.search("rolex")

    assert token_requests == 1


@pytest.mark.parametrize(
    "failing_path",
    ["/identity/v1/oauth2/token", "/buy/browse/v1/item_summary/search"],
)
def test_api_http_failures_raise_safe_error(failing_path: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == failing_path:
            return httpx.Response(401, json={"error": "request rejected"})
        return httpx.Response(200, json={"access_token": "token", "expires_in": 60})

    client = EbayClient(
        "client-id",
        "client-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(EbayApiError) as error:
        client.search("omega")

    assert "HTTP 401" in str(error.value)
    assert "client-secret" not in str(error.value)


def test_invalid_search_payload_raises_api_error() -> None:
    responses: list[dict[str, Any]] = [
        {"access_token": "token", "expires_in": 60},
        {"itemSummaries": "not-a-list"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(responses.pop(0)))

    client = EbayClient(
        "client-id",
        "client-secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(EbayApiError, match="invalid itemSummaries"):
        client.search("omega")
