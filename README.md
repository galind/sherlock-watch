# Sherlock

Sherlock is an open-source, self-hosted watch marketplace monitoring project.

Sherlock is pre-alpha. The backend can manually poll Vinted searches, normalize
their listings, and persist current state in PostgreSQL. It does not yet schedule
searches or send alerts.

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
