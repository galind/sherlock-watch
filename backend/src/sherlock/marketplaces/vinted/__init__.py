"""Vinted marketplace integration."""

from sherlock.marketplaces.vinted.adapter import VintedAdapter
from sherlock.marketplaces.vinted.client import (
    VINTED_WATCH_CATALOG_IDS,
    VintedApiError,
    VintedClient,
    VintedSearchPage,
)

__all__ = [
    "VINTED_WATCH_CATALOG_IDS",
    "VintedAdapter",
    "VintedApiError",
    "VintedClient",
    "VintedSearchPage",
]
