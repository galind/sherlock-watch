"""Normalize eBay listing payloads into Sherlock domain listings."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sherlock.domain import Listing, ListingStatus, Marketplace, Money


class EbayAdapter:
    """Normalize individual eBay Browse API-style item payloads."""

    def normalize(self, raw_listing: Mapping[str, Any]) -> Listing:
        price = raw_listing["price"]

        return Listing(
            marketplace=Marketplace.EBAY,
            external_id=raw_listing["itemId"],
            url=raw_listing["itemWebUrl"],
            title=raw_listing["title"].strip(),
            description=raw_listing.get("shortDescription"),
            price=Money(
                amount=Decimal(price["value"]),
                currency=price["currency"],
            ),
            location=self._location(raw_listing.get("itemLocation")),
            condition=raw_listing.get("condition"),
            image_urls=self._image_urls(raw_listing),
            published_at=self._timestamp(raw_listing.get("itemCreationDate")),
            status=self._status(raw_listing.get("estimatedAvailabilities")),
        )

    @staticmethod
    def _image_urls(raw_listing: Mapping[str, Any]) -> tuple[str, ...]:
        images: list[str] = []

        if primary_image := raw_listing.get("image"):
            images.append(primary_image["imageUrl"])
        images.extend(
            image["imageUrl"] for image in raw_listing.get("additionalImages", [])
        )

        return tuple(images)

    @staticmethod
    def _location(item_location: Mapping[str, Any] | None) -> str | None:
        if item_location is None:
            return None

        parts = [item_location.get("city"), item_location.get("country")]
        location = ", ".join(part for part in parts if part)
        return location or None

    @staticmethod
    def _timestamp(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _status(
        estimated_availabilities: list[Mapping[str, Any]] | None,
    ) -> ListingStatus:
        if not estimated_availabilities:
            return ListingStatus.UNKNOWN

        ebay_status = estimated_availabilities[0].get("estimatedAvailabilityStatus")
        if ebay_status == "IN_STOCK":
            return ListingStatus.ACTIVE
        return ListingStatus.UNKNOWN
