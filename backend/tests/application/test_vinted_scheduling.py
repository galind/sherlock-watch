import pytest

from sherlock.application import PollResult, watch_vinted_searches


def test_first_cycle_runs_immediately_for_each_query() -> None:
    calls: list[str] = []
    reports: list[tuple[int, str, PollResult, float]] = []
    result = PollResult(fetched=4, new=1, already_known=3)

    watch_vinted_searches(
        ["movado", "juvenia"],
        lambda query: calls.append(query) or result,
        once=True,
        sleep=lambda seconds: pytest.fail("single cycle should not sleep"),
        report=lambda cycle, query, poll_result, elapsed: reports.append(
            (cycle, query, poll_result, elapsed)
        ),
    )

    assert calls == ["movado", "juvenia"]
    assert [
        (cycle, query, poll_result) for cycle, query, poll_result, _ in reports
    ] == [
        (1, "movado", result),
        (1, "juvenia", result),
    ]


def test_repeating_watcher_sleeps_between_complete_cycles() -> None:
    events: list[tuple[str, object]] = []

    def poll(query: str) -> PollResult:
        events.append(("poll", query))
        return PollResult(fetched=0, new=0, already_known=0)

    def sleep(seconds: float) -> None:
        events.append(("sleep", seconds))
        if len([event for event in events if event[0] == "sleep"]) == 2:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        watch_vinted_searches(
            ["movado", "juvenia"],
            poll,
            interval_seconds=17,
            sleep=sleep,
        )

    assert events == [
        ("poll", "movado"),
        ("poll", "juvenia"),
        ("sleep", 17),
        ("poll", "movado"),
        ("poll", "juvenia"),
        ("sleep", 17),
    ]


@pytest.mark.parametrize("queries", [[], [""], ["movado", "   "]])
def test_watcher_rejects_missing_or_empty_queries(queries: list[str]) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        watch_vinted_searches(queries, lambda query: pytest.fail(query), once=True)


def test_watcher_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError, match="positive"):
        watch_vinted_searches(
            ["movado"],
            lambda query: pytest.fail(query),
            interval_seconds=0,
            once=True,
        )


def test_failed_query_is_retried_then_does_not_block_other_queries() -> None:
    calls: list[str] = []
    failures: list[tuple[str, int, float | None]] = []
    reports: list[str] = []

    def poll(query: str) -> PollResult:
        calls.append(query)
        if query == "broken":
            raise TimeoutError
        return PollResult(fetched=2, new=1, already_known=1)

    watch_vinted_searches(
        ["broken", "working"],
        poll,
        once=True,
        max_attempts=2,
        retry_backoff_seconds=(0,),
        retry_sleep=lambda seconds: None,
        report=lambda cycle, query, result, elapsed: reports.append(query),
        report_failure=lambda cycle, query, category, attempt, retry_in: (
            failures.append((category, attempt, retry_in))
        ),
    )

    assert calls == ["broken", "broken", "working"]
    assert failures == [("network", 1, 0), ("network", 2, None)]
    assert reports == ["working"]


def test_all_failed_cycle_is_followed_by_another_cycle() -> None:
    calls = 0
    completed: list[tuple[int, int, int]] = []

    def poll(query: str) -> PollResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return PollResult(fetched=1, new=0, already_known=1)

    def complete(result) -> None:
        completed.append((result.cycle, result.succeeded, result.failed))
        if result.cycle == 2:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        watch_vinted_searches(
            ["movado"],
            poll,
            max_attempts=1,
            sleep=lambda seconds: None,
            report_cycle_complete=complete,
        )

    assert completed == [(1, 0, 1), (2, 1, 0)]


def test_keyboard_interrupt_from_poll_is_not_swallowed() -> None:
    with pytest.raises(KeyboardInterrupt):
        watch_vinted_searches(
            ["movado"],
            lambda query: (_ for _ in ()).throw(KeyboardInterrupt),
            once=True,
        )
