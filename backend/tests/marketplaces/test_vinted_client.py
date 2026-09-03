import io
import json
from typing import Any, Self
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from sherlock.marketplaces.vinted import VintedApiError, VintedClient


class StubResponse(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class StubOpener:
    def __init__(
        self,
        search_payloads: list[dict[str, Any]] | None = None,
        *,
        failing_path: str | None = None,
    ) -> None:
        self.search_payloads = search_payloads or []
        self.failing_path = failing_path
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: int) -> StubResponse:
        assert timeout == 20
        self.requests.append(request)
        path = urlparse(request.full_url).path or "/"
        if path == self.failing_path:
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)
        if path == "/":
            return StubResponse(b"<html></html>")
        return StubResponse(json.dumps(self.search_payloads.pop(0)).encode())


def search_payload(*, items: object = None) -> dict[str, Any]:
    return {
        "code": 0,
        "items": [] if items is None else items,
        "pagination": {
            "current_page": 2,
            "total_pages": 20,
            "total_entries": 960,
        },
    }


def test_search_bootstraps_anonymous_session_and_returns_page() -> None:
    opener = StubOpener([search_payload(items=[{"id": 123}])])
    client = VintedClient(opener=opener)

    page = client.search("  omega seamaster  ", page=2, per_page=48)

    assert page.items == ({"id": 123},)
    assert page.current_page == 2
    assert page.total_pages == 20
    assert page.total_entries == 960
    assert len(opener.requests) == 2

    bootstrap_request, catalog_request = opener.requests
    assert (urlparse(bootstrap_request.full_url).path or "/") == "/"
    assert "Mozilla/5.0" in bootstrap_request.get_header("User-agent")
    assert urlparse(catalog_request.full_url).path == "/api/v2/catalog/items"
    assert parse_qs(urlparse(catalog_request.full_url).query) == {
        "search_text": ["omega seamaster"],
        "order": ["newest_first"],
        "page": ["2"],
        "per_page": ["48"],
        "disable_search_saving": ["true"],
    }
    assert catalog_request.get_header("Accept") == "application/json"
    assert catalog_request.get_header("Referer") == "https://www.vinted.es/catalog"


def test_search_adds_catalog_filter_when_requested() -> None:
    opener = StubOpener([search_payload()])
    client = VintedClient(opener=opener)

    client.search("omega", catalog_ids=(22, 97))

    catalog_request = opener.requests[1]
    assert parse_qs(urlparse(catalog_request.full_url).query)["catalog_ids"] == [
        "22,97"
    ]


@pytest.mark.parametrize("catalog_ids", [(0,), (-1,), (True,), ("22",)])
def test_search_rejects_invalid_catalog_ids(catalog_ids: tuple[object, ...]) -> None:
    client = VintedClient(opener=StubOpener())

    with pytest.raises(ValueError, match="positive integers"):
        client.search("omega", catalog_ids=catalog_ids)


def test_search_reuses_bootstrapped_session() -> None:
    opener = StubOpener([search_payload(), search_payload()])
    client = VintedClient(opener=opener)

    client.search("omega")
    client.search("rolex")

    bootstrap_requests = [
        request
        for request in opener.requests
        if (urlparse(request.full_url).path or "/") == "/"
    ]
    assert len(bootstrap_requests) == 1


@pytest.mark.parametrize("failing_path", ["/", "/api/v2/catalog/items"])
def test_http_failures_raise_safe_error(failing_path: str) -> None:
    opener = StubOpener([search_payload()], failing_path=failing_path)
    client = VintedClient(opener=opener)

    with pytest.raises(VintedApiError) as error:
        client.search("omega")

    assert "HTTP 401" in str(error.value)


def test_invalid_search_payload_raises_api_error() -> None:
    opener = StubOpener([search_payload(items="not-a-list")])
    client = VintedClient(opener=opener)

    with pytest.raises(VintedApiError, match="invalid items"):
        client.search("omega")
