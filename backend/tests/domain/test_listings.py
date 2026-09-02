from datetime import UTC, datetime
from decimal import Decimal

import pytest

from sherlock.domain import Listing, Money


def test_money_normalizes_currency_code() -> None:
    money = Money(amount=Decimal("1499.99"), currency="eur")

    assert money.currency == "EUR"


@pytest.mark.parametrize("currency", ["EU", "EURO", "12A"])
def test_money_rejects_invalid_currency_code(currency: str) -> None:
    with pytest.raises(ValueError, match="three-letter code"):
        Money(amount=Decimal(1), currency=currency)


def test_listing_accepts_a_marketplace_identifier() -> None:
    listing = Listing(
        marketplace="example-marketplace",
        external_id="listing-123",
        url="https://example.com/listing-123",
        title="Example watch",
        price=Money(amount=Decimal(1000), currency="EUR"),
        published_at=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert listing.marketplace == "example-marketplace"


def test_listing_rejects_naive_publication_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Listing(
            marketplace="example-marketplace",
            external_id="listing-123",
            url="https://example.com/listing-123",
            title="Example watch",
            price=Money(amount=Decimal(1000), currency="EUR"),
            published_at=datetime(2026, 9, 2, tzinfo=UTC).replace(tzinfo=None),
        )
