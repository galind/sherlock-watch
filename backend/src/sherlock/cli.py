"""Command-line entry points for Sherlock."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from sherlock.application import (
    DEFAULT_HEARTBEAT_FILE,
    DEFAULT_VINTED_INTERVAL_SECONDS,
    CycleResult,
    PollResult,
    deliver_pending_discord_notifications,
    poll_vinted_search,
    watch_vinted_searches,
    watcher_heartbeat_is_fresh,
    write_watcher_heartbeat,
)
from sherlock.config import Settings
from sherlock.marketplaces.vinted import (
    VINTED_WATCH_CATALOG_IDS,
    VintedAdapter,
    VintedClient,
)
from sherlock.notifications import DiscordWebhookNotifier
from sherlock.persistence import (
    DiscordNotificationRepository,
    ListingRepository,
    create_database_engine,
)


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
        nargs="*",
        type=_non_empty_query,
        metavar="QUERY",
        help="Vinted keyword searches (or use --queries-file)",
    )
    watch_parser.add_argument(
        "--queries-file",
        type=Path,
        metavar="PATH",
        help="UTF-8 file containing one Vinted query per line",
    )
    watch_parser.add_argument(
        "--interval-seconds",
        type=_positive_int,
        default=None,
        help=(
            "seconds between cycles "
            f"(default: WATCH_INTERVAL_SECONDS or {DEFAULT_VINTED_INTERVAL_SECONDS})"
        ),
    )
    watch_parser.add_argument(
        "--once",
        action="store_true",
        help="run one cycle and exit without sleeping",
    )
    _add_polling_arguments(watch_parser, environment_defaults=True)

    health_parser = subparsers.add_parser(
        "watcher-health",
        help="check that the watcher has completed a recent successful poll",
    )
    health_parser.add_argument(
        "--heartbeat-file",
        type=Path,
        default=DEFAULT_HEARTBEAT_FILE,
    )
    health_parser.add_argument("--max-age-seconds", type=_positive_int)

    args = parser.parse_args(argv)

    try:
        if args.command == "poll-vinted":
            _poll_vinted(args.query, args.pages, args.per_page, args.watches_only)
        elif args.command == "watch-vinted":
            try:
                queries = _resolve_watch_queries(args.queries, args.queries_file)
            except ValueError as error:
                parser.error(str(error))
            _watch_vinted(
                queries,
                args.interval_seconds,
                args.pages,
                args.per_page,
                args.once,
                args.watches_only,
            )
        elif args.command == "watcher-health":
            _watcher_health(args.heartbeat_file, args.max_age_seconds)
    except KeyboardInterrupt:
        print("\nVinted polling stopped.")
    except ValueError as error:
        parser.error(str(error))


def _add_polling_arguments(
    parser: argparse.ArgumentParser, *, environment_defaults: bool = False
) -> None:
    parser.add_argument(
        "--pages",
        type=_positive_int,
        default=None if environment_defaults else 3,
        help="pages per query (default: WATCH_PAGES or 3)",
    )
    parser.add_argument(
        "--per-page",
        type=_vinted_per_page,
        default=None if environment_defaults else 48,
        help="listings per page (default: WATCH_PER_PAGE or 48)",
    )
    parser.add_argument(
        "--watches-only",
        action=argparse.BooleanOptionalAction,
        default=None if environment_defaults else False,
        help=(
            "limit results to Vinted watch categories "
            "(default: WATCH_WATCHES_ONLY for watch-vinted)"
        ),
    )


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


def _resolve_watch_queries(
    positional_queries: Sequence[str], queries_file: Path | None
) -> list[str]:
    if positional_queries and queries_file is not None:
        raise ValueError("use positional queries or --queries-file, not both")
    if queries_file is None:
        if not positional_queries:
            raise ValueError("provide at least one query or --queries-file")
        return list(positional_queries)

    try:
        queries = [
            line.strip()
            for line in queries_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as error:
        raise ValueError(
            f"could not read queries file {queries_file}: {error}"
        ) from error

    if not queries:
        raise ValueError(f"queries file {queries_file} does not contain any queries")
    return queries


def _poll_vinted(
    query: str, pages: int, per_page: int, watches_only: bool = False
) -> None:
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
                catalog_ids=VINTED_WATCH_CATALOG_IDS if watches_only else (),
            )
    finally:
        engine.dispose()

    print(
        f"Fetched {result.fetched} Vinted listings: "
        f"{result.new} new, {result.already_known} already known."
    )


def _watch_vinted(
    queries: Sequence[str],
    interval_seconds: int | None,
    pages: int | None,
    per_page: int | None,
    once: bool,
    watches_only: bool | None = None,
) -> None:
    settings = Settings.from_environment()
    if interval_seconds is None:
        interval_seconds = settings.watch_interval_seconds
    if pages is None:
        pages = settings.watch_pages
    if per_page is None:
        per_page = settings.watch_per_page
    if watches_only is None:
        watches_only = settings.watch_watches_only
    notifier = (
        DiscordWebhookNotifier(settings.discord_webhook_url)
        if settings.discord_webhook_url is not None
        else None
    )
    engine = create_database_engine(settings.database_url)
    adapter = VintedAdapter()

    print(
        "Watcher starting | "
        f"queries={len(queries)} | interval-seconds={interval_seconds} | "
        f"pages={pages} | per-page={per_page} | watches-only={watches_only} | "
        f"vinted-region={_safe_vinted_region(settings.vinted_base_url)} | "
        f"database=configured | discord={'configured' if notifier else 'disabled'}",
        flush=True,
    )

    try:
        with VintedClient(base_url=settings.vinted_base_url) as client:

            def poll(query: str) -> PollResult:
                with Session(engine) as session, session.begin():
                    notification_repository = (
                        DiscordNotificationRepository(session)
                        if notifier is not None
                        else None
                    )
                    return poll_vinted_search(
                        client,
                        adapter,
                        ListingRepository(session),
                        query,
                        pages=pages,
                        per_page=per_page,
                        catalog_ids=(VINTED_WATCH_CATALOG_IDS if watches_only else ()),
                        on_new_listing=(
                            notification_repository.enqueue
                            if notification_repository is not None
                            else None
                        ),
                    )

            watch_vinted_searches(
                queries,
                poll,
                interval_seconds=interval_seconds,
                once=once,
                report=lambda cycle, query, result, elapsed: _report_watch_result(
                    cycle,
                    query,
                    result,
                    elapsed_seconds=elapsed,
                ),
                report_failure=_report_watch_failure,
                report_cycle_start=lambda cycle: print(
                    f"Cycle {cycle} starting | queries={len(queries)}", flush=True
                ),
                report_cycle_complete=lambda result: _finish_watch_cycle(
                    result,
                    engine=engine,
                    notifier=notifier,
                ),
            )
    finally:
        engine.dispose()


def _report_watch_result(
    cycle: int,
    query: str,
    result: PollResult,
    *,
    elapsed_seconds: float = 0,
) -> None:
    print(
        f'Cycle {cycle} | query="{query}" | fetched={result.fetched} | '
        f"new={result.new} | already-known={result.already_known} | "
        f"elapsed-seconds={elapsed_seconds:.2f} | status=success",
        flush=True,
    )


def _report_watch_failure(
    cycle: int,
    query: str,
    category: str,
    attempt: int,
    retry_in_seconds: float | None,
) -> None:
    behavior = (
        f"retry-in-seconds={retry_in_seconds:g}"
        if retry_in_seconds is not None
        else "retry=next-cycle"
    )
    print(
        f'Cycle {cycle} | query="{query}" | status=failed | '
        f"category={category} | attempt={attempt} | {behavior}",
        file=sys.stderr,
        flush=True,
    )


def _finish_watch_cycle(
    result: CycleResult,
    *,
    engine,
    notifier: DiscordWebhookNotifier | None,
) -> None:
    print(
        f"Cycle {result.cycle} complete | succeeded={result.succeeded} | "
        f"failed={result.failed} | fetched={result.fetched} | new={result.new} | "
        f"already-known={result.already_known} | "
        f"elapsed-seconds={result.elapsed_seconds:.2f}",
        flush=True,
    )
    if notifier is not None:
        try:
            with Session(engine) as session, session.begin():
                delivery = deliver_pending_discord_notifications(
                    DiscordNotificationRepository(session),
                    notifier.notify_listing,
                )
            if delivery.attempted:
                print(
                    "Discord delivery | "
                    f"attempted={delivery.attempted} | "
                    f"delivered={delivery.delivered} | failed={delivery.failed} | "
                    "failed-retry=next-cycle",
                    flush=True,
                )
        except SQLAlchemyError as error:
            print(
                "Discord delivery | status=failed | "
                f"category={_safe_failure_category(error)} | retry=next-cycle",
                file=sys.stderr,
                flush=True,
            )

    if result.succeeded:
        try:
            write_watcher_heartbeat(DEFAULT_HEARTBEAT_FILE, result)
        except OSError:
            print(
                "Watcher heartbeat | status=failed | category=filesystem",
                file=sys.stderr,
                flush=True,
            )


def _watcher_health(heartbeat_file: Path, max_age_seconds: int | None) -> None:
    if max_age_seconds is None:
        interval = _environment_positive_int(
            "WATCH_INTERVAL_SECONDS", DEFAULT_VINTED_INTERVAL_SECONDS
        )
        max_age_seconds = max(300, interval * 2 + 60)
    if not watcher_heartbeat_is_fresh(heartbeat_file, max_age_seconds=max_age_seconds):
        raise SystemExit(1)


def _environment_positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return _positive_int(value)
    except (ValueError, argparse.ArgumentTypeError):
        raise ValueError(f"{name} must be a positive integer") from None


def _safe_failure_category(error: Exception) -> str:
    name = type(error).__name__
    if name in {"OperationalError", "InterfaceError", "DatabaseError"}:
        return "database"
    return "unexpected"


def _safe_vinted_region(url: str) -> str:
    """Return only the non-secret host portion of a configured Vinted URL."""
    try:
        return urlsplit(url).hostname or "configured"
    except ValueError:
        return "configured"
