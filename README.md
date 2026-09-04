# Sherlock

Sherlock is an open-source, self-hosted watch marketplace monitoring project.

Sherlock is pre-alpha. The backend can poll Vinted searches, normalize their
listings, and persist current state in PostgreSQL. It can run those polls on a
simple foreground schedule and optionally send new-listing alerts to a Discord
webhook.

The repository also includes a dependency-free static landing page in `frontend/`.

## Vinted access constraints

The Vinted client uses the anonymous JSON catalog endpoint exposed by the web
experience. It first loads the configured regional Vinted homepage to receive
anonymous session cookies, then requests newest-first pages from
`GET /api/v2/catalog/items`. It does not log in, execute JavaScript, use browser
automation, or attempt to bypass access controls.

This is an undocumented web endpoint rather than a supported public API. Vinted
may change its response, authentication flow, availability, or permitted usage
without notice. Page-number pagination also shifts while new listings arrive, so
consumers must deduplicate overlapping pages and cannot assume a broad,
high-volume search captures every listing.

## Docker setup

Docker Engine with the Compose plugin is the only prerequisite for the
recommended deployment. The default stack contains PostgreSQL, a one-shot
migration job, and the long-running Vinted watcher. The test database and test
runner are in a separate profile and do not start with the normal stack.

For first-time setup, copy both examples:

```bash
cp .env.example .env
cp queries.example.txt queries.txt
```

Edit `.env` before deployment. In particular, replace the development-only
`POSTGRES_PASSWORD`, choose the regional `VINTED_BASE_URL`, and add a
`DISCORD_WEBHOOK_URL` if alerts are wanted. The watcher settings are:

```dotenv
VINTED_BASE_URL=https://www.vinted.es
DISCORD_WEBHOOK_URL=
WATCH_INTERVAL_SECONDS=3600
WATCH_PAGES=3
WATCH_PER_PAGE=48
WATCH_WATCHES_ONLY=true
```

The interval and page count must be positive integers, `WATCH_PER_PAGE` must be
between 1 and 96, and `WATCH_WATCHES_ONLY` must be `true` or `false`. Invalid
values fail before polling begins. The webhook is secret and is never printed;
startup logs report only whether database and Discord configuration is present.

Replace the fictional searches in `queries.txt` with one search per line. Blank
lines are ignored. An absent, unreadable, or empty file stops the watcher with an
actionable error.

Start everything with one command:

```bash
docker compose up -d
```

Compose waits for PostgreSQL's health check, runs `alembic upgrade head`, and
starts the watcher only after the migration job exits successfully. A failed
migration therefore prevents the watcher from starting. PostgreSQL data lives in
the named `postgres-data` volume, and the watcher restarts after unexpected
exits while continuing to write to normal Docker logs.

Follow progress and inspect service state with:

```bash
docker compose ps
docker compose logs -f watcher
docker compose logs --since 30m watcher
```

The watcher logs its redacted startup configuration, every cycle start and
completion, per-query results, elapsed time, fetched/new/already-known counts,
safe failure categories, and whether a failed query will retry immediately or
in the next cycle. A healthy idle watcher has a `healthy` status in
`docker compose ps`, continues to complete cycles, and may legitimately report
zero new listings. A watcher that has not completed any successful query for
roughly two configured intervals becomes `unhealthy`; repeated `status=failed`
lines or no cycle completion indicate a failing or stuck poll.

Useful lifecycle commands are:

```bash
docker compose restart watcher
docker compose down
```

`docker compose down` removes containers and the Compose network but preserves
the database volume. Only use `docker compose down --volumes` when permanently
discarding all stored listing and notification state is intended.

### One-shot and maintenance commands

The existing CLI remains available through the opt-in `backend` tools service.
Run one targeted poll with explicit options:

```bash
docker compose run --rm backend poll-vinted "omega seamaster" \
  --pages 3 --per-page 48 --watches-only
```

Run every query from the deployment file exactly once, without sleeping:

```bash
docker compose run --rm -v "$PWD/queries.txt:/app/queries.txt:ro" backend \
  watch-vinted --queries-file /app/queries.txt --once
```

Command-line values override the matching watcher environment values, so manual
runs can also use positional queries or options such as `--pages`, `--per-page`,
`--interval-seconds`, `--watches-only`, and `--no-watches-only`.

Migrations can be rerun explicitly and are safe when the database is already at
the current revision:

```bash
docker compose run --rm migrate
```

After editing `.env` or `queries.txt`, restart the watcher so it reloads the
configuration:

```bash
docker compose restart watcher
```

The local `.env` and `queries.txt` files are ignored by Git because they are
deployment-specific.

### Polling and notification reliability

Each cycle polls all queries. A failed query is retried with bounded backoff; if
it still fails, the remaining queries run and the watcher sleeps normally before
trying it again next cycle. A cycle with no successful queries does not terminate
the process or refresh its health heartbeat. `KeyboardInterrupt` and container
shutdown signals are not swallowed.

Polling deduplicates IDs repeated across shifting pages, inserts newly seen
listings, and refreshes known listings. PostgreSQL preserves `first_seen_at`,
updates `last_seen_at`, and stores the current normalized fields plus the latest
raw Vinted payload.

When Discord is configured, each newly inserted listing is atomically added to a
PostgreSQL-backed pending-delivery table in the same transaction. After polling,
the watcher sends pending alerts one at a time and marks successful deliveries.
Failures remain pending and are retried on the next cycle; delivered rows are not
selected again, and the listing identity prevents the same alert from being
enqueued by multiple matching queries. When Discord is disabled, polling behaves
as before and does not create alert history.

Each alert is a Discord embed with the listing title, image, price, matched
search, and available metadata. One-shot `poll-vinted` commands do not send
alerts; `watch-vinted --once` does process its durable pending alerts.

### Troubleshooting

- If `db` is unhealthy, inspect `docker compose logs db`; port conflicts affect
  host access but containers use the internal `db:5432` address.
- If `migrate` exits non-zero, inspect `docker compose logs migrate`. The watcher
  intentionally remains stopped until `docker compose run --rm migrate`
  succeeds.
- Vinted is an undocumented anonymous endpoint. `category=vinted-api` can mean a
  transient outage, regional block, rate limit, or upstream response change.
  Sherlock backs off and retries without exposing response or session secrets.
- `Discord delivery ... failed` means the listing remains pending in PostgreSQL.
  Confirm the webhook URL and outbound network access, then watch a later cycle
  for `delivered=` to increase. Do not paste webhook URLs into issue reports.
- If the watcher is unhealthy but logs show successful recent cycles, inspect
  `docker compose exec watcher python -m sherlock watcher-health`; exit status 1
  means the heartbeat is missing, invalid, or stale.

The default Dockerfile target is the production-oriented `runtime` image. It
contains Python 3.13, the application, migrations, and only the production
dependencies resolved by `backend/uv.lock`; it runs as an unprivileged user.
The image entrypoint is `python -m sherlock` and its default argument is
`--help`, so normal CLI arguments can be appended directly:

```bash
docker build --target runtime -t sherlock-backend .
docker run --rm sherlock-backend --help
```

Published GitHub Releases also provide a multi-platform image for AMD64 and
ARM64 through GitHub Container Registry. Pull a specific release tag and pass
CLI arguments directly to the container:

```bash
docker pull ghcr.io/galind/sherlock-watch:v0.1.0
docker run --rm ghcr.io/galind/sherlock-watch:v0.1.0 --help
```

Stable releases also update the `latest` image tag. Prereleases are published
only under their exact release tag.

## Development

Compose uses the `development` image target, which adds the locked development
dependencies and test sources. Run formatting and lint checks in that image:

```bash
docker compose run --rm --no-deps --entrypoint ruff backend format --check .
docker compose run --rm --no-deps --entrypoint ruff backend check .
```

Run the full test suite against a dedicated, ephemeral PostgreSQL service. This
keeps test table cleanup away from the persistent development database:

```bash
docker compose --profile test run --rm test
```

Validate that the models match the migrated development database:

```bash
docker compose run --rm --entrypoint alembic backend check
```

The same checks can be run directly when Python 3.13, PostgreSQL, and
[uv](https://docs.astral.sh/uv/) are installed. From `backend/`:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run alembic check
```

`DATABASE_URL` is used by the CLI and Alembic. Set `TEST_DATABASE_URL` to a
separate PostgreSQL database to include the persistence integration test in a
host-run test suite.

Preview the static landing page from the repository root with:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
