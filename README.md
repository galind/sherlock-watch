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

Docker Compose is the recommended local setup. Copy the example configuration;
the defaults are development-only credentials and can be used as-is:

```bash
cp .env.example .env
```

Start the persistent PostgreSQL service and wait for its health check:

```bash
docker compose up -d --wait db
```

Apply migrations explicitly. This command exits non-zero and displays the
Alembic error if a migration fails:

```bash
docker compose run --rm migrate
```

Run a targeted Vinted poll across three pages of 48 results:

```bash
docker compose run --rm backend poll-vinted "omega seamaster" --pages 3 --per-page 48
```

The command deduplicates IDs repeated across shifting pages, inserts newly seen
listings, refreshes known listings, and reports both counts. PostgreSQL preserves
`first_seen_at`, updates `last_seen_at`, and stores the latest normalized fields
plus the original Vinted payload.

Add `--watches-only` to limit results to Vinted's women's and men's watch
categories and remove most unrelated keyword matches:

```bash
docker compose run --rm backend poll-vinted "omega seamaster" --watches-only
```

Run multiple searches immediately and repeat them every hour:

```bash
docker compose run --rm backend watch-vinted "movado" "juvenia" \
  --interval-seconds 3600 \
  --pages 3 \
  --per-page 48
```

The default interval is 3600 seconds (one hour). Each cycle polls the queries sequentially
and reports fetched, new, and already-known listing counts for each query. Add
`--once` to run one complete cycle and exit without sleeping, which is useful for
manual runs and configuration checks:

```bash
docker compose run --rm backend watch-vinted "movado" "juvenia" --once
```

For a reusable local query list, put one query per line in `queries.txt` (blank
lines are ignored) and pass it with `--queries-file`:

```text
omega seamaster
movado
juvenia
```

```bash
docker compose run --rm -v "$PWD/queries.txt:/app/queries.txt:ro" backend \
  watch-vinted --queries-file /app/queries.txt \
  --watches-only --interval-seconds 3600
```

The local `queries.txt` file is ignored by Git because its contents are
deployment-specific. The watch-category filter applies to every query in the
file without changing its one-query-per-line format. Omit `--watches-only` to
retain the broader keyword search behavior.

To receive Discord notifications, add a webhook URL to the local `.env` file:

```dotenv
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/example-id/example-token
```

`DISCORD_WEBHOOK_URL` is optional, and must use HTTPS with a valid host when it
is configured. Only `watch-vinted` sends notifications, and only when a query
finds new listings; one-shot `poll-vinted` runs never send them. Each new watch
gets its own Discord embed with a clickable title, large main picture, price,
search query, and any available condition, seller, location, description, and
publication time. Additional photos are summarized by count rather than sent as
extra embeds. Sending one webhook message per listing makes the individual
watches easy to scan; embed fields are bounded to Discord's limits and mentions
from marketplace text are disabled.

Webhook delivery is currently intentionally simple: failed deliveries emit a
warning and polling continues, with no retries or alert history.

The scheduler is intentionally a simple foreground process and stops if a poll
fails. Compose keeps it attached to the terminal so logs and failures remain
visible; use your host's service manager for a long-lived homelab deployment.

The default Dockerfile target is the production-oriented `runtime` image. It
contains Python 3.13, the application, migrations, and only the production
dependencies resolved by `backend/uv.lock`; it runs as an unprivileged user.
The image entrypoint is `python -m sherlock` and its default argument is
`--help`, so normal CLI arguments can be appended directly:

```bash
docker build --target runtime -t sherlock-backend .
docker run --rm sherlock-backend --help
```

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

Stop and remove local containers and networks while preserving PostgreSQL data:

```bash
docker compose --profile test down
```

To also delete the persistent development database volume, use the following
only when its data is no longer needed:

```bash
docker compose --profile test down --volumes
```

Preview the static landing page from the repository root with:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
