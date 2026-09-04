"""Manual marketplace polling use cases."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sherlock.domain import Listing
from sherlock.marketplaces.vinted import VintedAdapter, VintedClient
from sherlock.persistence import ListingRepository


@dataclass(frozen=True, slots=True)
class PollResult:
    """Counts from one marketplace polling run."""

    fetched: int
    new: int
    already_known: int
    new_listings: tuple[Listing, ...] = ()


def poll_vinted_search(
    client: VintedClient,
    adapter: VintedAdapter,
    repository: ListingRepository,
    query: str,
    *,
    pages: int = 3,
    per_page: int = 48,
    catalog_ids: Sequence[int] = (),
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    on_new_listing: Callable[[str, Listing, datetime], None] | None = None,
) -> PollResult:
    """Fetch Vinted pages, deduplicate them, and persist current state."""
    if pages < 1:
        raise ValueError("Vinted page count must be positive")

    seen_at = now()
    fetched_ids: set[str] = set()
    new_listings: list[Listing] = []

    for page_number in range(1, pages + 1):
        page = client.search(
            query,
            page=page_number,
            per_page=per_page,
            catalog_ids=catalog_ids,
        )
        for raw_listing in page.items:
            listing = adapter.normalize(raw_listing)
            if listing.external_id in fetched_ids:
                continue

            fetched_ids.add(listing.external_id)
            if repository.upsert(listing, raw_listing, seen_at=seen_at):
                new_listings.append(listing)
                if on_new_listing is not None:
                    on_new_listing(query, listing, seen_at)

        if page.current_page >= page.total_pages:
            break

    fetched_count = len(fetched_ids)
    new_count = len(new_listings)
    return PollResult(
        fetched=fetched_count,
        new=new_count,
        already_known=fetched_count - new_count,
        new_listings=tuple(new_listings),
    )
