"""Resilient foreground scheduling helpers for marketplace polling."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sherlock.application.polling import PollResult

DEFAULT_VINTED_INTERVAL_SECONDS = 3600

VintedPoll = Callable[[str], PollResult]
PollReporter = Callable[[int, str, PollResult, float], None]
FailureReporter = Callable[[int, str, str, int, float | None], None]
CycleStartReporter = Callable[[int], None]
Sleeper = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class CycleResult:
    """Progress and timing from one complete watcher cycle."""

    cycle: int
    queries: int
    succeeded: int
    failed: int
    fetched: int
    new: int
    already_known: int
    elapsed_seconds: float


CycleCompleteReporter = Callable[[CycleResult], None]


def watch_vinted_searches(
    queries: Sequence[str],
    poll: VintedPoll,
    *,
    interval_seconds: int = DEFAULT_VINTED_INTERVAL_SECONDS,
    once: bool = False,
    sleep: Sleeper = time.sleep,
    retry_sleep: Sleeper = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    max_attempts: int = 3,
    retry_backoff_seconds: Sequence[float] = (2, 5),
    report: PollReporter = lambda cycle, query, result, elapsed: None,
    report_failure: FailureReporter = (
        lambda cycle, query, category, attempt, retry_in: None
    ),
    report_cycle_start: CycleStartReporter = lambda cycle: None,
    report_cycle_complete: CycleCompleteReporter = lambda result: None,
) -> None:
    """Poll every query, isolating transient failures and repeating safely."""
    normalized_queries = tuple(query.strip() for query in queries)
    if not normalized_queries or any(not query for query in normalized_queries):
        raise ValueError("at least one non-empty Vinted search query is required")
    if interval_seconds < 1:
        raise ValueError("Vinted polling interval must be positive")
    if max_attempts < 1:
        raise ValueError("Vinted polling attempts must be positive")

    cycle = 1
    while True:
        cycle_started_at = clock()
        report_cycle_start(cycle)
        succeeded = failed = fetched = new = already_known = 0
        for query in normalized_queries:
            query_started_at = clock()
            for attempt in range(1, max_attempts + 1):
                try:
                    result = poll(query)
                # A query adapter must not be able to terminate the whole watcher.
                # BaseException is intentionally not caught so shutdown propagates.
                except Exception as error:  # noqa: BLE001
                    retry_in = _retry_delay(
                        attempt,
                        max_attempts=max_attempts,
                        retry_backoff_seconds=retry_backoff_seconds,
                    )
                    report_failure(
                        cycle,
                        query,
                        _failure_category(error),
                        attempt,
                        retry_in,
                    )
                    if retry_in is None:
                        failed += 1
                        break
                    retry_sleep(retry_in)
                else:
                    succeeded += 1
                    fetched += result.fetched
                    new += result.new
                    already_known += result.already_known
                    report(cycle, query, result, clock() - query_started_at)
                    break

        report_cycle_complete(
            CycleResult(
                cycle=cycle,
                queries=len(normalized_queries),
                succeeded=succeeded,
                failed=failed,
                fetched=fetched,
                new=new,
                already_known=already_known,
                elapsed_seconds=clock() - cycle_started_at,
            )
        )

        if once:
            return

        sleep(interval_seconds)
        cycle += 1


def _retry_delay(
    attempt: int,
    *,
    max_attempts: int,
    retry_backoff_seconds: Sequence[float],
) -> float | None:
    if attempt >= max_attempts:
        return None
    if not retry_backoff_seconds:
        return 0
    index = min(attempt - 1, len(retry_backoff_seconds) - 1)
    return max(0, retry_backoff_seconds[index])


def _failure_category(error: Exception) -> str:
    """Return a safe, stable category without including exception details."""
    name = type(error).__name__
    if name == "VintedApiError":
        return "vinted-api"
    if name in {"OperationalError", "InterfaceError", "DatabaseError"}:
        return "database"
    if isinstance(error, (TimeoutError, ConnectionError)):
        return "network"
    if isinstance(error, ValueError):
        return "invalid-data"
    return "unexpected"
