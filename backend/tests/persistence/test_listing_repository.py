import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from sherlock.marketplaces.vinted import VintedAdapter
from sherlock.persistence import ListingRepository

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "vinted" / "listing.json"


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def test_upsert_reports_new_then_updates_without_losing_first_seen(
    database_engine,
) -> None:
    first_seen = datetime(2026, 9, 2, 18, 0, tzinfo=UTC)
    last_seen = datetime(2026, 9, 2, 19, 0, tzinfo=UTC)
    initial_payload = load_fixture()
    adapter = VintedAdapter()

    with Session(database_engine) as session, session.begin():
        was_inserted = ListingRepository(session).upsert(
            adapter.normalize(initial_payload),
            initial_payload,
            seen_at=first_seen,
        )

    changed_payload = deepcopy(initial_payload)
    changed_payload["title"] = "Updated Omega Seamaster"
    changed_payload["price"] = {"amount": "1200.00", "currency_code": "EUR"}
    with Session(database_engine) as session, session.begin():
        was_inserted_again = ListingRepository(session).upsert(
            adapter.normalize(changed_payload),
            changed_payload,
            seen_at=last_seen,
        )

    with Session(database_engine) as session:
        record = ListingRepository(session).get("vinted", "9867705286")

        assert was_inserted is True
        assert was_inserted_again is False
        assert record is not None
        assert record.title == "Updated Omega Seamaster"
        assert record.price_amount == Decimal("1200.00")
        assert record.seller_name == "example-seller"
        assert record.first_seen_at == first_seen
        assert record.last_seen_at == last_seen
        assert record.raw_payload == changed_payload
