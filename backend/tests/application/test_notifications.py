from datetime import UTC, datetime
from decimal import Decimal

from sherlock.application import deliver_pending_discord_notifications
from sherlock.domain import Listing, Money
from sherlock.persistence import PendingDiscordNotification


def listing() -> Listing:
    return Listing(
        marketplace="vinted",
        external_id="example-1",
        url="https://www.vinted.es/items/example-1",
        title="Example watch",
        price=Money(Decimal(10), "EUR"),
    )


class RecordingRepository:
    def __init__(self) -> None:
        self.items = [
            PendingDiscordNotification(
                marketplace="vinted",
                external_id="example-1",
                query="example query",
                attempts=0,
                listing=listing(),
            )
        ]
        self.delivered = []
        self.failed = []

    def pending(self, *, limit: int = 100):
        return tuple(self.items[:limit])

    def mark_delivered(self, notification, *, attempted_at) -> None:
        self.delivered.append(notification)
        self.items.remove(notification)

    def mark_failed(self, notification, *, attempted_at, category) -> None:
        self.failed.append((notification, category))


def test_failed_delivery_remains_pending_and_can_succeed_later() -> None:
    repository = RecordingRepository()

    failed = deliver_pending_discord_notifications(
        repository,
        lambda query, item: (_ for _ in ()).throw(TimeoutError()),
        now=lambda: datetime(2026, 9, 4, tzinfo=UTC),
    )
    delivered = deliver_pending_discord_notifications(
        repository,
        lambda query, item: None,
        now=lambda: datetime(2026, 9, 4, 1, tzinfo=UTC),
    )
    empty = deliver_pending_discord_notifications(
        repository,
        lambda query, item: None,
    )

    assert failed == type(failed)(attempted=1, delivered=0, failed=1)
    assert repository.failed[0][1] == "network"
    assert delivered == type(delivered)(attempted=1, delivered=1, failed=0)
    assert empty == type(empty)(attempted=0, delivered=0, failed=0)
