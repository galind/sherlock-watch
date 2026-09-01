"""Manual marketplace ingestion use cases."""

from collections.abc import Callable
from datetime import UTC, datetime

from sherlock.marketplaces.ebay import EbayAdapter, EbayClient
from sherlock.persistence import ListingRepository


def ingest_ebay_search(
    client: EbayClient,
    adapter: EbayAdapter,
    repository: ListingRepository,
    query: str,
    *,
    limit: int = 50,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Search one eBay page, normalize it, and upsert every result."""
    page = client.search(query, limit=limit)
    seen_at = now()
    for raw_listing in page.items:
        listing = adapter.normalize(raw_listing)
        repository.upsert(listing, raw_listing, seen_at=seen_at)
    return len(page.items)
