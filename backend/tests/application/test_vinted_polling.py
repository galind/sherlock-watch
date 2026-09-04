import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from sherlock.application import poll_vinted_search
from sherlock.marketplaces.vinted import VintedAdapter, VintedSearchPage

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "vinted" / "listing.json"


class StubVintedClient:
    def __init__(self, pages: list[VintedSearchPage]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, int, int, tuple[int, ...]]] = []

    def search(
        self,
        query: str,
        *,
        page: int = 1,
        per_page: int = 48,
        catalog_ids=(),
    ) -> VintedSearchPage:
        self.calls.append((query, page, per_page, tuple(catalog_ids)))
        return self.pages.pop(0)


class RecordingRepository:
    def __init__(self, new_ids: set[str]) -> None:
        self.new_ids = new_ids
        self.upserts: list[tuple[object, object, datetime]] = []

    def upsert(self, listing, raw_payload, *, seen_at: datetime) -> bool:
        self.upserts.append((listing, raw_payload, seen_at))
        return listing.external_id in self.new_ids


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def test_poll_fetches_pages_deduplicates_and_counts_new_listings() -> None:
    first_listing = load_fixture()
    second_listing = deepcopy(first_listing)
    second_listing["id"] = 9867705287
    second_listing["url"] = "https://www.vinted.es/items/9867705287-second-watch"
    client = StubVintedClient(
        [
            VintedSearchPage(
                items=(first_listing,),
                current_page=1,
                total_pages=2,
                total_entries=2,
            ),
            VintedSearchPage(
                items=(first_listing, second_listing),
                current_page=2,
                total_pages=2,
                total_entries=2,
            ),
        ]
    )
    repository = RecordingRepository(new_ids={"9867705287"})
    seen_at = datetime(2026, 9, 2, 18, 0, tzinfo=UTC)

    result = poll_vinted_search(
        client,
        VintedAdapter(),
        repository,
        "omega seamaster",
        pages=5,
        per_page=48,
        now=lambda: seen_at,
    )

    assert result.fetched == 2
    assert result.new == 1
    assert result.already_known == 1
    assert tuple(listing.external_id for listing in result.new_listings) == (
        "9867705287",
    )
    assert client.calls == [
        ("omega seamaster", 1, 48, ()),
        ("omega seamaster", 2, 48, ()),
    ]
    assert [upsert[0].external_id for upsert in repository.upserts] == [
        "9867705286",
        "9867705287",
    ]
    assert all(upsert[2] == seen_at for upsert in repository.upserts)


def test_poll_passes_catalog_filter_to_vinted_client() -> None:
    client = StubVintedClient(
        [
            VintedSearchPage(
                items=(),
                current_page=1,
                total_pages=1,
                total_entries=0,
            )
        ]
    )

    poll_vinted_search(
        client,
        VintedAdapter(),
        RecordingRepository(new_ids=set()),
        "omega",
        catalog_ids=(22, 97),
    )

    assert client.calls == [("omega", 1, 48, (22, 97))]


def test_poll_invokes_new_listing_handler_only_for_insertions() -> None:
    raw_listing = load_fixture()
    client = StubVintedClient(
        [
            VintedSearchPage(
                items=(raw_listing,),
                current_page=1,
                total_pages=1,
                total_entries=1,
            )
        ]
    )
    seen_at = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
    enqueued = []

    poll_vinted_search(
        client,
        VintedAdapter(),
        RecordingRepository(new_ids={"9867705286"}),
        "omega",
        now=lambda: seen_at,
        on_new_listing=lambda query, item, created_at: enqueued.append(
            (query, item.external_id, created_at)
        ),
    )

    assert enqueued == [("omega", "9867705286", seen_at)]
