"""Marketplace-independent listing domain types."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ListingStatus(StrEnum):
    """The marketplace-reported availability of a listing."""

    ACTIVE = "active"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Money:
    """An exact monetary amount and its ISO 4217 currency code."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("money amount must be finite")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        object.__setattr__(self, "currency", self.currency.upper())


@dataclass(frozen=True, slots=True)
class Listing:
    """A marketplace listing normalized for use by Sherlock."""

    marketplace: str
    external_id: str
    url: str
    title: str
    price: Money
    description: str | None = None
    location: str | None = None
    condition: str | None = None
    image_urls: tuple[str, ...] = ()
    published_at: datetime | None = None
    status: ListingStatus = ListingStatus.UNKNOWN

    def __post_init__(self) -> None:
        if self.published_at is not None and self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
