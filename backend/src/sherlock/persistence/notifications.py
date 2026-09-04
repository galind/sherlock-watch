"""Durable PostgreSQL state for new-listing Discord alerts."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from sherlock.domain import Listing, ListingStatus, Money
from sherlock.persistence.database import Base
from sherlock.persistence.listings import ListingRecord


class DiscordNotificationRecord(Base):
    """Delivery state for one listing's Discord notification."""

    __tablename__ = "discord_notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["marketplace", "external_id"],
            ["listings.marketplace", "listings.external_id"],
            ondelete="CASCADE",
        ),
        Index("ix_discord_notifications_pending", "status", "created_at"),
    )

    marketplace: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))


@dataclass(frozen=True, slots=True)
class PendingDiscordNotification:
    """A pending alert and the current listing data needed to deliver it."""

    marketplace: str
    external_id: str
    query: str
    attempts: int
    listing: Listing


class DiscordNotificationRepository:
    """Enqueue first-seen listings and track webhook delivery attempts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, query: str, listing: Listing, created_at: datetime) -> bool:
        """Create one pending alert per listing and return whether it was added."""
        inserted_id = self._session.scalar(
            insert(DiscordNotificationRecord)
            .values(
                marketplace=listing.marketplace,
                external_id=listing.external_id,
                query=query,
                status="pending",
                attempts=0,
                created_at=created_at,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    DiscordNotificationRecord.marketplace,
                    DiscordNotificationRecord.external_id,
                ]
            )
            .returning(DiscordNotificationRecord.external_id)
        )
        return inserted_id is not None

    def pending(self, *, limit: int = 100) -> tuple[PendingDiscordNotification, ...]:
        """Load pending alerts oldest first with their current listing state."""
        rows = self._session.execute(
            select(DiscordNotificationRecord, ListingRecord)
            .join(
                ListingRecord,
                (ListingRecord.marketplace == DiscordNotificationRecord.marketplace)
                & (ListingRecord.external_id == DiscordNotificationRecord.external_id),
            )
            .where(DiscordNotificationRecord.status == "pending")
            .order_by(
                DiscordNotificationRecord.last_attempt_at.asc().nulls_first(),
                DiscordNotificationRecord.created_at,
            )
            .limit(limit)
            .with_for_update(skip_locked=True, of=DiscordNotificationRecord)
        ).all()
        return tuple(
            PendingDiscordNotification(
                marketplace=notification.marketplace,
                external_id=notification.external_id,
                query=notification.query,
                attempts=notification.attempts,
                listing=_listing_from_record(listing),
            )
            for notification, listing in rows
        )

    def mark_delivered(
        self,
        notification: PendingDiscordNotification,
        *,
        attempted_at: datetime,
    ) -> None:
        """Mark a pending alert delivered after a successful webhook response."""
        self._session.execute(
            update(DiscordNotificationRecord)
            .where(
                DiscordNotificationRecord.marketplace == notification.marketplace,
                DiscordNotificationRecord.external_id == notification.external_id,
                DiscordNotificationRecord.status == "pending",
            )
            .values(
                status="delivered",
                attempts=DiscordNotificationRecord.attempts + 1,
                last_attempt_at=attempted_at,
                delivered_at=attempted_at,
                last_error=None,
            )
        )

    def mark_failed(
        self,
        notification: PendingDiscordNotification,
        *,
        attempted_at: datetime,
        category: str,
    ) -> None:
        """Record a safe failure category while leaving an alert retryable."""
        self._session.execute(
            update(DiscordNotificationRecord)
            .where(
                DiscordNotificationRecord.marketplace == notification.marketplace,
                DiscordNotificationRecord.external_id == notification.external_id,
                DiscordNotificationRecord.status == "pending",
            )
            .values(
                attempts=DiscordNotificationRecord.attempts + 1,
                last_attempt_at=attempted_at,
                last_error=category[:64],
            )
        )


def _listing_from_record(record: ListingRecord) -> Listing:
    return Listing(
        marketplace=record.marketplace,
        external_id=record.external_id,
        url=record.url,
        title=record.title,
        price=Money(record.price_amount, record.price_currency),
        description=record.description,
        location=record.location,
        condition=record.condition,
        seller_name=record.seller_name,
        image_urls=tuple(record.image_urls),
        published_at=record.published_at,
        status=ListingStatus(record.status),
    )
