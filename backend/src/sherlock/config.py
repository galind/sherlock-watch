"""Minimal environment-based runtime configuration."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Settings required by the manual Vinted polling command."""

    database_url: str
    vinted_base_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings with actionable errors."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        return cls(
            database_url=database_url,
            vinted_base_url=os.getenv("VINTED_BASE_URL", "https://www.vinted.es"),
        )
