import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sherlock.application import ingest_ebay_search
from sherlock.domain import Marketplace
from sherlock.marketplaces.ebay import EbayAdapter, EbaySearchPage
from sherlock.persistence import ListingRecord, ListingRepository

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "ebay" / "listing.json"


class StubEbayClient:
    def __init__(self, raw_listing: dict[str, object]) -> None:
        self.raw_listing = raw_listing

    def search(self, query: str, *, limit: int = 50) -> EbaySearchPage:
        assert query == "nomos tangente"
        assert limit == 1
        return EbaySearchPage(items=(self.raw_listing,), next_url=None)


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def test_reingestion_updates_listing_without_duplicate(database_engine) -> None:
    first_seen = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    last_seen = datetime(2026, 9, 1, 11, 30, tzinfo=UTC)
    initial_payload = load_fixture()

    with Session(database_engine) as session, session.begin():
        count = ingest_ebay_search(
            StubEbayClient(initial_payload),
            EbayAdapter(),
            ListingRepository(session),
            "nomos tangente",
            limit=1,
            now=lambda: first_seen,
        )

    assert count == 1

    changed_payload = deepcopy(initial_payload)
    changed_payload["title"] = "Updated NOMOS Tangente 38"
    changed_payload["price"] = {"value": "1399.00", "currency": "EUR"}
    changed_payload.pop("shortDescription")
    changed_payload.pop("itemLocation")
    changed_payload.pop("itemCreationDate")
    changed_payload.pop("additionalImages")

    with Session(database_engine) as session, session.begin():
        ingest_ebay_search(
            StubEbayClient(changed_payload),
            EbayAdapter(),
            ListingRepository(session),
            "nomos tangente",
            limit=1,
            now=lambda: last_seen,
        )

    with Session(database_engine) as session:
        listing_count = session.scalar(select(func.count()).select_from(ListingRecord))
        record = ListingRepository(session).get(Marketplace.EBAY, "v1|266912345678|0")

        assert listing_count == 1
        assert record is not None
        assert record.title == "Updated NOMOS Tangente 38"
        assert record.price_amount == Decimal("1399.00")
        assert record.description is None
        assert record.location is None
        assert record.published_at is None
        assert record.image_urls == [
            "https://i.ebayimg.com/images/g/nomos-main/s-l1600.jpg"
        ]
        assert record.first_seen_at == first_seen
        assert record.last_seen_at == last_seen
        assert record.raw_payload == changed_payload
