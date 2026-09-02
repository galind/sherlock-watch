"""Persistence mapping and upsert operations for normalized listings."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Numeric, String, Text, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from sherlock.domain import Listing
from sherlock.persistence.database import Base


class ListingRecord(Base):
    """The current persisted state of one marketplace listing."""

    __tablename__ = "listings"

    marketplace: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    price_amount: Mapped[Decimal] = mapped_column(Numeric)
    price_currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list[str]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ListingRepository:
    """Store the latest state and identify first-seen listings."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self,
        listing: Listing,
        raw_payload: Mapping[str, Any],
        *,
        seen_at: datetime,
    ) -> bool:
        """Insert or refresh a listing and return whether it was newly inserted."""
        if seen_at.utcoffset() is None:
            raise ValueError("seen_at must be timezone-aware")

        values = {
            "marketplace": listing.marketplace,
            "external_id": listing.external_id,
            "url": listing.url,
            "title": listing.title,
            "price_amount": listing.price.amount,
            "price_currency": listing.price.currency,
            "description": listing.description,
            "location": listing.location,
            "condition": listing.condition,
            "image_urls": list(listing.image_urls),
            "published_at": listing.published_at,
            "status": listing.status.value,
            "first_seen_at": seen_at,
            "last_seen_at": seen_at,
            "raw_payload": dict(raw_payload),
        }
        inserted_id = self._session.scalar(
            insert(ListingRecord)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[
                    ListingRecord.marketplace,
                    ListingRecord.external_id,
                ]
            )
            .returning(ListingRecord.external_id)
        )
        if inserted_id is not None:
            return True

        update_values = {
            key: value
            for key, value in values.items()
            if key not in {"marketplace", "external_id", "first_seen_at"}
        }
        self._session.execute(
            update(ListingRecord)
            .where(
                ListingRecord.marketplace == listing.marketplace,
                ListingRecord.external_id == listing.external_id,
            )
            .values(**update_values)
        )
        return False

    def get(self, marketplace: str, external_id: str) -> ListingRecord | None:
        """Load a listing by its marketplace identity."""
        return self._session.get(ListingRecord, (marketplace, external_id))
