"""Manual command-line entry points for Sherlock."""

import argparse

from sqlalchemy.orm import Session

from sherlock.application import poll_vinted_search
from sherlock.config import Settings
from sherlock.marketplaces.vinted import VintedAdapter, VintedClient
from sherlock.persistence import ListingRepository, create_database_engine


def main() -> None:
    """Run the selected Sherlock command."""
    parser = argparse.ArgumentParser(prog="python -m sherlock")
    subparsers = parser.add_subparsers(dest="command", required=True)
    poll_parser = subparsers.add_parser(
        "poll-vinted",
        help="search Vinted and persist newly seen listings",
    )
    poll_parser.add_argument("query", help="Vinted keyword search")
    poll_parser.add_argument("--pages", type=int, default=3)
    poll_parser.add_argument("--per-page", type=int, default=48)
    args = parser.parse_args()

    if args.command == "poll-vinted":
        _poll_vinted(args.query, args.pages, args.per_page)


def _poll_vinted(query: str, pages: int, per_page: int) -> None:
    settings = Settings.from_environment()
    engine = create_database_engine(settings.database_url)
    try:
        with (
            VintedClient(base_url=settings.vinted_base_url) as client,
            Session(engine) as session,
            session.begin(),
        ):
            result = poll_vinted_search(
                client,
                VintedAdapter(),
                ListingRepository(session),
                query,
                pages=pages,
                per_page=per_page,
            )
    finally:
        engine.dispose()

    print(
        f"Fetched {result.fetched} Vinted listings: "
        f"{result.new} new, {result.already_known} already known."
    )
