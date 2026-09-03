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

## Local setup

The backend requires Python 3.13 or newer, PostgreSQL, and
[uv](https://docs.astral.sh/uv/). Create a PostgreSQL database, copy the example
configuration, and apply the schema:

```bash
cp .env.example .env
set -a
source .env
set +a
cd backend
uv sync --locked
uv run alembic upgrade head
```

Run a targeted Vinted poll across three pages of 48 results:

```bash
uv run python -m sherlock poll-vinted "omega seamaster" --pages 3 --per-page 48
```

The command deduplicates IDs repeated across shifting pages, inserts newly seen
listings, refreshes known listings, and reports both counts. PostgreSQL preserves
`first_seen_at`, updates `last_seen_at`, and stores the latest normalized fields
plus the original Vinted payload.

Run multiple searches immediately and repeat them every hour:

```bash
uv run python -m sherlock watch-vinted "movado" "juvenia" \
  --interval-seconds 3600 \
  --pages 3 \
  --per-page 48
```

The default interval is 3600 seconds (one hour). Each cycle polls the queries sequentially
and reports fetched, new, and already-known listing counts for each query. Add
`--once` to run one complete cycle and exit without sleeping, which is useful for
manual runs and configuration checks:

```bash
uv run python -m sherlock watch-vinted "movado" "juvenia" --once
```

For a reusable local query list, put one query per line in `queries.txt` (blank
lines are ignored) and pass it with `--queries-file`:

```text
omega seamaster
movado
juvenia
```

```bash
uv run python -m sherlock watch-vinted --queries-file queries.txt \
  --interval-seconds 3600
```

The local `queries.txt` file is ignored by Git because its contents are
deployment-specific.

To receive Discord notifications, add a webhook URL to the local `.env` file:

```dotenv
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/example-id/example-token
```

`DISCORD_WEBHOOK_URL` is optional, and must use HTTPS with a valid host when it
is configured. Only `watch-vinted` sends notifications, and only when a query
finds new listings; one-shot `poll-vinted` runs never send them. Each new watch
gets its own Discord embed with a clickable title, price, search query, URL,
and the listing's main picture as the thumbnail. Sending one webhook message
per listing makes the individual watches easy to scan; embed fields are
bounded to Discord's limits.

Webhook delivery is currently intentionally simple: failed deliveries emit a
warning and polling continues, with no retries or alert history.

This scheduler is intentionally a simple foreground process. It must currently
be kept running manually and stops if a poll fails. For a homelab, run it in a
persistent terminal multiplexer after loading the environment, for example:

```bash
cd /path/to/sherlock
set -a
source .env
set +a
cd backend
tmux new-session -s sherlock-vinted \
  'uv run python -m sherlock watch-vinted "omega seamaster" "movado" --interval-seconds 3600'
```

## Development

From `backend/`, run the checks with:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run alembic check
```

Preview the static landing page from the repository root with:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
