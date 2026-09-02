"""Normalize Vinted catalog payloads into Sherlock domain listings."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sherlock.domain import Listing, ListingStatus, Money


class VintedAdapter:
    """Normalize individual Vinted web catalog item payloads."""

    def normalize(self, raw_listing: Mapping[str, Any]) -> Listing:
        price = raw_listing["price"]

        return Listing(
            marketplace="vinted",
            external_id=str(raw_listing["id"]),
            url=raw_listing["url"],
            title=raw_listing["title"].strip(),
            price=Money(
                amount=Decimal(str(price["amount"])),
                currency=price["currency_code"],
            ),
            condition=raw_listing.get("status"),
            image_urls=self._image_urls(raw_listing),
            status=(
                ListingStatus.ACTIVE
                if raw_listing.get("is_visible") is not False
                else ListingStatus.UNKNOWN
            ),
        )

    @staticmethod
    def _image_urls(raw_listing: Mapping[str, Any]) -> tuple[str, ...]:
        images: list[str] = []
        raw_photos = [raw_listing.get("photo")]
        additional_photos = raw_listing.get("photos")
        if isinstance(additional_photos, list):
            raw_photos.extend(additional_photos)

        for photo in raw_photos:
            if not isinstance(photo, Mapping):
                continue
            image_url = photo.get("full_size_url") or photo.get("url")
            if isinstance(image_url, str) and image_url not in images:
                images.append(image_url)

        return tuple(images)
