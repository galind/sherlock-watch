"""File-backed watcher heartbeat used by container health checks."""

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from sherlock.application.scheduling import CycleResult

DEFAULT_HEARTBEAT_FILE = Path("/tmp/sherlock-watcher-heartbeat.json")


def write_watcher_heartbeat(path: Path, result: CycleResult) -> None:
    """Atomically record the most recent cycle with at least one success."""
    payload = {
        "cycle": result.cycle,
        "queries": result.queries,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "fetched": result.fetched,
        "new": result.new,
        "already_known": result.already_known,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "written_at_unix": time.time(),
    }
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary_path, path)


def watcher_heartbeat_is_fresh(
    path: Path,
    *,
    max_age_seconds: int,
    now: Callable[[], float] = time.time,
) -> bool:
    """Return whether a readable successful-cycle heartbeat is recent enough."""
    if max_age_seconds < 1:
        raise ValueError("heartbeat maximum age must be positive")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        written_at = payload["written_at_unix"]
        succeeded = payload["succeeded"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return False
    return (
        isinstance(written_at, (int, float))
        and isinstance(succeeded, int)
        and succeeded > 0
        and 0 <= now() - written_at <= max_age_seconds
    )
