"""Contract for marketplace listing normalization."""

from collections.abc import Mapping
from typing import Any, Protocol

from sherlock.domain import Listing


class MarketplaceAdapter(Protocol):
    """Normalize marketplace-specific listing payloads."""

    def normalize(self, raw_listing: Mapping[str, Any]) -> Listing:
        """Convert a marketplace payload to a Sherlock listing."""
        ...
