from sherlock.application import (
    CycleResult,
    watcher_heartbeat_is_fresh,
    write_watcher_heartbeat,
)


def test_heartbeat_records_successful_cycle_and_expires(tmp_path, monkeypatch) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    monkeypatch.setattr("sherlock.application.status.time.time", lambda: 1000.0)

    write_watcher_heartbeat(
        heartbeat,
        CycleResult(
            cycle=2,
            queries=3,
            succeeded=2,
            failed=1,
            fetched=8,
            new=1,
            already_known=7,
            elapsed_seconds=4.2,
        ),
    )

    assert watcher_heartbeat_is_fresh(heartbeat, max_age_seconds=60, now=lambda: 1059.0)
    assert not watcher_heartbeat_is_fresh(
        heartbeat, max_age_seconds=60, now=lambda: 1061.0
    )


def test_missing_or_invalid_heartbeat_is_unhealthy(tmp_path) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    assert not watcher_heartbeat_is_fresh(heartbeat, max_age_seconds=60)

    heartbeat.write_text("not-json", encoding="utf-8")
    assert not watcher_heartbeat_is_fresh(heartbeat, max_age_seconds=60)
