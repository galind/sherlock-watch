"""Disposable probe for public Ricardo search-result pages."""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://www.ricardo.ch"
USER_AGENT = "Mozilla/5.0 (compatible; SherlockRicardoResearch/0.1)"


class StructureChanged(RuntimeError):
    """Raised when Ricardo no longer exposes the expected page structure."""


class PageParts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.listing_urls: dict[str, str] = {}
        self.scripts: list[str] = []
        self._in_script = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and (href := attributes.get("href")):
            if href.startswith("/de/a/"):
                listing_id = href.rstrip("/").rsplit("-", 1)[-1]
                if listing_id.isdigit():
                    self.listing_urls.setdefault(listing_id, BASE_URL + href)
        elif tag == "script" and not attributes.get("src"):
            self._in_script = True
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self.scripts.append("".join(self._script_parts))
            self._in_script = False


def fetch_page(query: str, page: int) -> tuple[str, str]:
    path = f"/de/s/{quote(query)}/"
    url = BASE_URL + path
    if page > 1:
        url += f"?page={page}"

    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            if response.status != 200 or content_type != "text/html":
                raise RuntimeError(
                    f"unexpected response: HTTP {response.status}, {content_type}"
                )
            return response.read().decode("utf-8"), response.url
    except HTTPError as error:
        detail = " (Cloudflare challenge)" if error.headers.get("cf-mitigated") else ""
        raise RuntimeError(f"request failed: HTTP {error.code}{detail}") from error
    except URLError as error:
        raise RuntimeError(f"request failed: {error.reason}") from error


def extract_search_data(html: str) -> tuple[dict[str, object], dict[str, str]]:
    page = PageParts()
    page.feed(html)

    prefix = "self.__next_f.push("
    for script in page.scripts:
        if not script.startswith(prefix) or not script.endswith(")"):
            continue
        try:
            flight_arguments = json.loads(script[len(prefix) : -1])
        except json.JSONDecodeError:
            continue
        if (
            not isinstance(flight_arguments, list)
            or len(flight_arguments) != 2
            or flight_arguments[0] != 1
            or not isinstance(flight_arguments[1], str)
        ):
            continue

        _, separator, payload = flight_arguments[1].partition(":")
        if not separator or not payload.startswith("["):
            continue
        try:
            react_node = json.loads(payload)
            state = react_node[3]["state"]
            queries = state["queries"]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError):
            continue

        for query in queries:
            data = query.get("state", {}).get("data", {})
            if isinstance(data, dict) and {"articles", "config"} <= data.keys():
                return data, page.listing_urls

    raise StructureChanged(
        "Ricardo's expected Next.js search hydration data was not found; "
        "the page structure may have changed"
    )


def price_summary(article: dict[str, object]) -> str:
    parts = []
    if article.get("hasAuction"):
        parts.append(
            f"CHF {article['bidPrice']:.2f} auction/{article['bidsCount']} bids"
        )
    if article.get("hasBuyNow"):
        parts.append(f"CHF {article['buyNowPrice']:.2f} buy-now")
    return ", ".join(parts) or "no public price"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="omega seamaster")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.page < 1 or args.limit < 1:
        parser.error("--page and --limit must be positive")

    try:
        html, url = fetch_page(args.query, args.page)
        data, listing_urls = extract_search_data(html)
        articles = data["articles"]
        if not isinstance(articles, list) or not articles:
            raise StructureChanged("expected at least one listing in search data")

        print(f"Search: {url}")
        print(
            f"Results: {len(articles)} on page / "
            f"{data['totalArticlesCount']} total; config={data['config']}"
        )
        for article in articles[: args.limit]:
            listing_id = str(article["id"])
            try:
                listing_url = listing_urls[listing_id]
            except KeyError as error:
                raise StructureChanged(
                    f"server-rendered URL missing for listing {listing_id}"
                ) from error
            print(
                f"{listing_id} | {article['title']} | "
                f"{price_summary(article)} | {listing_url}"
            )
    except (RuntimeError, KeyError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
