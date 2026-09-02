import pytest

from sherlock import cli
from sherlock.application import PollResult


@pytest.mark.parametrize(
    "arguments",
    [
        ["watch-vinted", "movado", "--interval-seconds", "0"],
        ["watch-vinted", "   ", "--once"],
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


def test_watcher_result_output_is_concise(capsys) -> None:
    cli._report_watch_result(
        3,
        "omega seamaster",
        PollResult(fetched=12, new=2, already_known=10),
    )

    assert capsys.readouterr().out == (
        'Cycle 3 | query="omega seamaster" | fetched=12 | new=2 | already-known=10\n'
    )
