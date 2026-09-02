"""Small foreground scheduling helpers for marketplace polling."""

import time
from collections.abc import Callable, Sequence

from sherlock.application.polling import PollResult

DEFAULT_VINTED_INTERVAL_SECONDS = 300

VintedPoll = Callable[[str], PollResult]
PollReporter = Callable[[int, str, PollResult], None]
Sleeper = Callable[[float], None]


def watch_vinted_searches(
    queries: Sequence[str],
    poll: VintedPoll,
    *,
    interval_seconds: int = DEFAULT_VINTED_INTERVAL_SECONDS,
    once: bool = False,
    sleep: Sleeper = time.sleep,
    report: PollReporter = lambda cycle, query, result: None,
) -> None:
    """Poll each Vinted query immediately, then repeat after each interval."""
    normalized_queries = tuple(query.strip() for query in queries)
    if not normalized_queries or any(not query for query in normalized_queries):
        raise ValueError("at least one non-empty Vinted search query is required")
    if interval_seconds < 1:
        raise ValueError("Vinted polling interval must be positive")

    cycle = 1
    while True:
        for query in normalized_queries:
            result = poll(query)
            report(cycle, query, result)

        if once:
            return

        sleep(interval_seconds)
        cycle += 1
