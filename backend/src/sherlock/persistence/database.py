"""Database primitives shared by Sherlock persistence modules."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for Sherlock's SQLAlchemy table mappings."""


def create_database_engine(database_url: str) -> Engine:
    """Create a PostgreSQL engine."""
    if not database_url:
        raise ValueError("database URL is required")
    return create_engine(database_url, pool_pre_ping=True)
