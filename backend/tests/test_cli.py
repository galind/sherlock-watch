import pytest

from sherlock import cli
from sherlock.application import PollResult


@pytest.mark.parametrize(
    "arguments",
    [
        ["watch-vinted", "movado", "--interval-seconds", "0"],
        ["watch-vinted", "   ", "--once"],
        ["watch-vinted"],
        ["watch-vinted", "movado", "--pages", "0"],
        ["watch-vinted", "movado", "--per-page", "97"],
    ],
)
def test_cli_rejects_invalid_watcher_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)

    assert error.value.code == 2


def test_cli_handles_watcher_interruption_cleanly(monkeypatch, capsys) -> None:
    def interrupt(*args, **kwargs) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_watch_vinted", interrupt)

    cli.main(["watch-vinted", "movado"])

    assert capsys.readouterr().out == "\nVinted polling stopped.\n"


def test_cli_passes_watcher_options(monkeypatch) -> None:
    received: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        cli,
        "_watch_vinted",
        lambda *args: received.append(args),
    )

    cli.main(
        [
            "watch-vinted",
            "movado",
            "juvenia",
            "--interval-seconds",
            "60",
            "--pages",
            "2",
            "--per-page",
            "24",
            "--once",
        ]
    )

    assert received == [(["movado", "juvenia"], 60, 2, 24, True)]


def test_cli_uses_one_hour_default_interval(monkeypatch) -> None:
    received: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        cli,
        "_watch_vinted",
        lambda *args: received.append(args),
    )

    cli.main(["watch-vinted", "movado"])

    assert received == [(["movado"], 3600, 3, 48, False)]


def test_cli_reads_queries_file(monkeypatch, tmp_path) -> None:
    queries_file = tmp_path / "queries.txt"
    queries_file.write_text("movado\n\n juvenia \n", encoding="utf-8")
    received: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        cli,
        "_watch_vinted",
        lambda *args: received.append(args),
    )

    cli.main(["watch-vinted", "--queries-file", str(queries_file), "--once"])

    assert received == [(["movado", "juvenia"], 3600, 3, 48, True)]


def test_cli_rejects_positional_queries_with_queries_file(
    monkeypatch, tmp_path
) -> None:
    queries_file = tmp_path / "queries.txt"
    queries_file.write_text("movado\n", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        cli.main(["watch-vinted", "juvenia", "--queries-file", str(queries_file)])

    assert error.value.code == 2


def test_cli_rejects_empty_queries_file(tmp_path) -> None:
    queries_file = tmp_path / "queries.txt"
    queries_file.write_text("\n  \n", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        cli.main(["watch-vinted", "--queries-file", str(queries_file)])

    assert error.value.code == 2


def test_watcher_result_output_is_concise(capsys) -> None:
    cli._report_watch_result(
        3,
        "omega seamaster",
        PollResult(fetched=12, new=2, already_known=10),
    )

    assert capsys.readouterr().out == (
        'Cycle 3 | query="omega seamaster" | fetched=12 | new=2 | already-known=10\n'
    )


def test_watcher_does_not_notify_when_no_new_listings(capsys) -> None:
    class UnexpectedNotifier:
        def notify(self, query, listings) -> None:
            pytest.fail(f"unexpected notification for {query}: {listings}")

    cli._report_watch_result(
        1,
        "movado",
        PollResult(fetched=4, new=0, already_known=4),
        notifier=UnexpectedNotifier(),
    )

    assert capsys.readouterr().err == ""


def test_watcher_logs_safe_warning_and_continues_after_notification_failure(
    capsys,
) -> None:
    class FailingNotifier:
        def notify(self, query, listings) -> None:
            raise cli.DiscordWebhookError("Discord webhook delivery failed")

    cli._report_watch_result(
        2,
        "movado",
        PollResult(fetched=1, new=1, already_known=0),
        notifier=FailingNotifier(),
    )

    captured = capsys.readouterr()
    assert "Discord webhook delivery failed" in captured.err
    assert "polling will continue" in captured.err


def test_watcher_without_webhook_configuration_keeps_reporting(
    monkeypatch,
    capsys,
) -> None:
    class StubSettings:
        database_url = "postgresql+psycopg://localhost/sherlock"
        vinted_base_url = "https://www.vinted.es"
        discord_webhook_url = None

    class StubEngine:
        def dispose(self) -> None:
            pass

    class StubClient:
        def __init__(self, *, base_url: str) -> None:
            self.base_url = base_url

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            pass

    def run_one_cycle(queries, poll, **options) -> None:
        options["report"](
            1,
            queries[0],
            PollResult(fetched=3, new=1, already_known=2),
        )

    monkeypatch.setattr(cli.Settings, "from_environment", lambda: StubSettings())
    monkeypatch.setattr(cli, "create_database_engine", lambda url: StubEngine())
    monkeypatch.setattr(cli, "VintedClient", StubClient)
    monkeypatch.setattr(cli, "watch_vinted_searches", run_one_cycle)
    monkeypatch.setattr(
        cli,
        "DiscordWebhookNotifier",
        lambda url: pytest.fail("notifier should not be configured"),
    )

    cli._watch_vinted(["movado"], 3600, 3, 48, True)

    assert 'query="movado"' in capsys.readouterr().out
