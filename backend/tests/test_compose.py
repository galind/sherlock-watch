"""Checks for the user-facing default Docker Compose path."""

from pathlib import Path

COMPOSE_CANDIDATES = (
    Path(__file__).parents[1] / "compose.yaml",
    Path(__file__).parents[2] / "compose.yaml",
)


def test_default_compose_stack_wires_migrations_and_watcher() -> None:
    compose_path = next(path for path in COMPOSE_CANDIDATES if path.exists())
    compose = compose_path.read_text(encoding="utf-8")

    assert "  watcher:" in compose
    assert "condition: service_healthy" in compose
    assert "condition: service_completed_successfully" in compose
    assert "./queries.txt:/app/queries.txt:ro" in compose
    assert "restart: unless-stopped" in compose
    assert "watcher-health" in compose
    assert "profiles: [test]" in compose
