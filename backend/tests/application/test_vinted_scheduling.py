import pytest

from sherlock.application import PollResult, watch_vinted_searches


def test_first_cycle_runs_immediately_for_each_query() -> None:
    calls: list[str] = []
    reports: list[tuple[int, str, PollResult]] = []
    result = PollResult(fetched=4, new=1, already_known=3)

    watch_vinted_searches(
        ["movado", "juvenia"],
        lambda query: calls.append(query) or result,
        once=True,
        sleep=lambda seconds: pytest.fail("single cycle should not sleep"),
        report=lambda cycle, query, poll_result: reports.append(
            (cycle, query, poll_result)
        ),
    )

    assert calls == ["movado", "juvenia"]
    assert reports == [(1, "movado", result), (1, "juvenia", result)]


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
