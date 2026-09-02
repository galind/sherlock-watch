"""Command-line entry points for Sherlock."""

import argparse
from collections.abc import Sequence

from sqlalchemy.orm import Session

from sherlock.application import (
    DEFAULT_VINTED_INTERVAL_SECONDS,
    PollResult,
    poll_vinted_search,
    watch_vinted_searches,
)
from sherlock.config import Settings
from sherlock.marketplaces.vinted import VintedAdapter, VintedClient
from sherlock.persistence import ListingRepository, create_database_engine


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected Sherlock command."""
    parser = argparse.ArgumentParser(prog="python -m sherlock")
    subparsers = parser.add_subparsers(dest="command", required=True)
    poll_parser = subparsers.add_parser(
        "poll-vinted",
        help="search Vinted and persist newly seen listings",
    )
    poll_parser.add_argument(
        "query", type=_non_empty_query, help="Vinted keyword search"
    )
    _add_polling_arguments(poll_parser)

    watch_parser = subparsers.add_parser(
        "watch-vinted",
        help="periodically search Vinted and persist newly seen listings",
    )
    watch_parser.add_argument(
        "queries",
        nargs="+",
        type=_non_empty_query,
        metavar="QUERY",
        help="one or more Vinted keyword searches",
    )
    watch_parser.add_argument(
        "--interval-seconds",
        type=_positive_int,
        default=DEFAULT_VINTED_INTERVAL_SECONDS,
        help=f"seconds between cycles (default: {DEFAULT_VINTED_INTERVAL_SECONDS})",
    )
    watch_parser.add_argument(
        "--once",
        action="store_true",
        help="run one cycle and exit without sleeping",
    )
    _add_polling_arguments(watch_parser)

    args = parser.parse_args(argv)

    try:
        if args.command == "poll-vinted":
            _poll_vinted(args.query, args.pages, args.per_page)
        elif args.command == "watch-vinted":
            _watch_vinted(
                args.queries,
                args.interval_seconds,
                args.pages,
                args.per_page,
                args.once,
            )
    except KeyboardInterrupt:
        print("\nVinted polling stopped.")


def _add_polling_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pages", type=_positive_int, default=3)
    parser.add_argument("--per-page", type=_vinted_per_page, default=48)


def _positive_int(value: str) -> int:
    parsed_value = int(value)
    if parsed_value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed_value


def _vinted_per_page(value: str) -> int:
    parsed_value = _positive_int(value)
    if parsed_value > 96:
        raise argparse.ArgumentTypeError("must be between 1 and 96")
    return parsed_value


def _non_empty_query(value: str) -> str:
    query = value.strip()
    if not query:
        raise argparse.ArgumentTypeError("query must not be empty")
    return query


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


def _watch_vinted(
    queries: Sequence[str],
    interval_seconds: int,
    pages: int,
    per_page: int,
    once: bool,
) -> None:
    settings = Settings.from_environment()
    engine = create_database_engine(settings.database_url)
    adapter = VintedAdapter()

    try:
        with VintedClient(base_url=settings.vinted_base_url) as client:

            def poll(query: str) -> PollResult:
                with Session(engine) as session, session.begin():
                    return poll_vinted_search(
                        client,
                        adapter,
                        ListingRepository(session),
                        query,
                        pages=pages,
                        per_page=per_page,
                    )

            watch_vinted_searches(
                queries,
                poll,
                interval_seconds=interval_seconds,
                once=once,
                report=_report_watch_result,
            )
    finally:
        engine.dispose()


def _report_watch_result(cycle: int, query: str, result: PollResult) -> None:
    print(
        f'Cycle {cycle} | query="{query}" | fetched={result.fetched} | '
        f"new={result.new} | already-known={result.already_known}",
        flush=True,
    )
