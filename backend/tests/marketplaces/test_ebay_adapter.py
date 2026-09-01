import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sherlock.domain import ListingStatus, Marketplace, Money
from sherlock.marketplaces.base import MarketplaceAdapter
from sherlock.marketplaces.ebay import EbayAdapter

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "ebay" / "listing.json"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def test_normalizes_ebay_listing_fixture() -> None:
    adapter: MarketplaceAdapter = EbayAdapter()

    listing = adapter.normalize(load_fixture())

    assert listing.marketplace is Marketplace.EBAY
    assert listing.external_id == "v1|266912345678|0"
    assert listing.title == "NOMOS Glashütte Tangente 38 Ref. 165 Manual Wind Watch"
    assert listing.url == "https://www.ebay.de/itm/266912345678"
    assert listing.price == Money(amount=Decimal("1499.99"), currency="EUR")
    assert listing.description == (
        "A well-preserved NOMOS Tangente 38 with original box and papers."
    )
    assert listing.location == "Berlin, Germany"
    assert listing.condition == "Pre-owned - Good"
    assert listing.image_urls == (
        "https://i.ebayimg.com/images/g/nomos-main/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/nomos-back/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/nomos-dial/s-l1600.jpg",
    )
    assert listing.published_at == datetime(2026, 8, 30, 14, 25, 36, tzinfo=UTC)
    assert listing.published_at.utcoffset() is not None
    assert listing.status is ListingStatus.ACTIVE


def test_missing_optional_fields_are_normalized_as_absent() -> None:
    raw_listing = load_fixture()
    raw_listing.pop("shortDescription")
    raw_listing.pop("itemLocation")
    raw_listing.pop("itemCreationDate")

    listing = EbayAdapter().normalize(raw_listing)

    assert listing.description is None
    assert listing.location is None
    assert listing.published_at is None
