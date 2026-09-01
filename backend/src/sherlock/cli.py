"""Development command-line entry points for Sherlock."""

import argparse

from sqlalchemy.orm import Session

from sherlock.application import ingest_ebay_search
from sherlock.config import Settings
from sherlock.marketplaces.ebay import EbayAdapter, EbayClient
from sherlock.persistence import ListingRepository, create_database_engine


def main() -> None:
    """Run the selected Sherlock command."""
    parser = argparse.ArgumentParser(prog="python -m sherlock")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser(
        "ingest-ebay", help="search and persist one page of eBay listings"
    )
    ingest_parser.add_argument("query", help="eBay keyword search")
    ingest_parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.command == "ingest-ebay":
        _ingest_ebay(args.query, args.limit)


def _ingest_ebay(query: str, limit: int) -> None:
    settings = Settings.from_environment()
    engine = create_database_engine(settings.database_url)
    try:
        with (
            EbayClient(
                settings.ebay_client_id,
                settings.ebay_client_secret,
                environment=settings.ebay_environment,
                marketplace_id=settings.ebay_marketplace_id,
            ) as client,
            Session(engine) as session,
            session.begin(),
        ):
            count = ingest_ebay_search(
                client,
                EbayAdapter(),
                ListingRepository(session),
                query,
                limit=limit,
            )
    finally:
        engine.dispose()

    print(f"Ingested {count} eBay listings.")
