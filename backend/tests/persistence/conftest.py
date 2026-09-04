import os

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from sherlock.persistence import (
    Base,
    DiscordNotificationRecord,
    ListingRecord,
    create_database_engine,
)


@pytest.fixture(scope="session")
def database_engine():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clear_listings(database_engine) -> None:
    with Session(database_engine) as session, session.begin():
        session.execute(delete(DiscordNotificationRecord))
        session.execute(delete(ListingRecord))
