"""Minimal environment-based configuration for manual ingestion."""

import os
from dataclasses import dataclass
from typing import Literal, cast


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings required by the eBay ingestion command."""

    database_url: str
    ebay_client_id: str
    ebay_client_secret: str
    ebay_environment: Literal["production", "sandbox"]
    ebay_marketplace_id: str

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings from environment variables with actionable errors."""
        environment = os.getenv("EBAY_ENVIRONMENT", "production")
        if environment not in {"production", "sandbox"}:
            raise ValueError("EBAY_ENVIRONMENT must be 'production' or 'sandbox'")

        return cls(
            database_url=_required("DATABASE_URL"),
            ebay_client_id=_required("EBAY_CLIENT_ID"),
            ebay_client_secret=_required("EBAY_CLIENT_SECRET"),
            ebay_environment=cast(Literal["production", "sandbox"], environment),
            ebay_marketplace_id=os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US"),
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} environment variable is required")
    return value
