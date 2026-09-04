"""Application service for retrying durable listing notifications."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sherlock.domain import Listing
from sherlock.persistence import DiscordNotificationRepository


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Counts from one bounded pending-notification delivery pass."""

    attempted: int
    delivered: int
    failed: int


def deliver_pending_discord_notifications(
    repository: DiscordNotificationRepository,
    send: Callable[[str, Listing], None],
    *,
    limit: int = 100,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DeliveryResult:
    """Try each pending alert once, retaining failures for a later cycle."""
    attempted = delivered = failed = 0
    for notification in repository.pending(limit=limit):
        attempted += 1
        attempted_at = now()
        try:
            send(notification.query, notification.listing)
        # Delivery adapters are an external boundary; all ordinary failures must
        # remain retryable, while BaseException still permits clean shutdown.
        except Exception as error:  # noqa: BLE001
            repository.mark_failed(
                notification,
                attempted_at=attempted_at,
                category=_delivery_failure_category(error),
            )
            failed += 1
        else:
            repository.mark_delivered(notification, attempted_at=attempted_at)
            delivered += 1
    return DeliveryResult(attempted=attempted, delivered=delivered, failed=failed)


def _delivery_failure_category(error: Exception) -> str:
    name = type(error).__name__
    if name == "DiscordWebhookError":
        return "discord-webhook"
    if isinstance(error, (TimeoutError, ConnectionError)):
        return "network"
    return "unexpected"
