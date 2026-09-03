import json
from decimal import Decimal
from pathlib import Path

from sherlock.domain import ListingStatus, Money
from sherlock.marketplaces.base import MarketplaceAdapter
from sherlock.marketplaces.vinted import VintedAdapter

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "vinted" / "listing.json"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def test_normalizes_vinted_listing_fixture() -> None:
    adapter: MarketplaceAdapter = VintedAdapter()

    listing = adapter.normalize(load_fixture())

    assert listing.marketplace == "vinted"
    assert listing.external_id == "9867705286"
    assert listing.title == "Omega Seamaster Automatic"
    assert listing.url == (
        "https://www.vinted.es/items/9867705286-omega-seamaster-automatic"
    )
    assert listing.price == Money(amount=Decimal("1250.50"), currency="EUR")
    assert listing.description is None
    assert listing.location is None
    assert listing.condition == "Muy bueno"
    assert listing.seller_name == "example-seller"
    assert listing.image_urls == (
        "https://images1.vinted.net/tc/primary/example.jpeg",
        "https://images1.vinted.net/tc/caseback/example.jpeg",
    )
    assert listing.published_at is None
    assert listing.status is ListingStatus.ACTIVE


def test_missing_optional_fields_are_normalized_as_absent() -> None:
    raw_listing = load_fixture()
    raw_listing.pop("status")
    raw_listing.pop("photo")
    raw_listing.pop("photos")
    raw_listing.pop("user")

    listing = VintedAdapter().normalize(raw_listing)

    assert listing.condition is None
    assert listing.seller_name is None
    assert listing.image_urls == ()


def test_malformed_seller_is_normalized_as_absent() -> None:
    raw_listing = load_fixture()
    raw_listing["user"] = {"login": "   "}
    raw_listing["status"] = {"unexpected": "shape"}

    listing = VintedAdapter().normalize(raw_listing)

    assert listing.seller_name is None
    assert listing.condition is None
