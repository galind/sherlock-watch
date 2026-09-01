# Sherlock

Sherlock is an open-source, self-hosted watch marketplace monitoring project.

> Sherlock is pre-alpha. The current vertical slice can search one page of live
> eBay listings, normalize the results, and upsert their latest state into
> PostgreSQL. It does not yet schedule searches or send alerts.

## What is implemented

- A marketplace-independent `Listing` domain model.
- An eBay Browse API adapter and OAuth-authenticated keyword search client.
- PostgreSQL storage for normalized listings and their original eBay payload.
- Idempotent upserts keyed by `(marketplace, external_id)`.
- A manual command that runs one configured eBay search.
- A dependency-free static landing page in `frontend/`.

Sherlock remains a modular monolith. eBay HTTP behavior, marketplace payload
normalization, application orchestration, and PostgreSQL persistence are kept in
separate modules inside the backend.

## eBay API constraints

Sherlock uses the official [eBay Browse API keyword search](https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search),
not website scraping. The client obtains an application access token through
eBay's [OAuth client credentials grant](https://developer.ebay.com/api-docs/static/oauth-client-credentials-grant.html)
and sends it to `GET /buy/browse/v1/item_summary/search`. A marketplace is selected
with `X-EBAY-C-MARKETPLACE-ID`.

The command currently fetches one page. eBay permits a `limit` of up to 200 items
and returns a `next` URL when another page is available. The client exposes that
URL so later pagination can be added without changing normalization or storage.

The Browse API is available in eBay's sandbox, but sandbox search data is limited
and does not represent the live catalog. More importantly, eBay documents its Buy
APIs as a limited release: [production access requires approval](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html)
and is not guaranteed. Valid production keys alone may therefore be insufficient
until eBay grants the application access.

## Local setup

The backend requires:

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- An eBay developer application with Browse API access

Create a PostgreSQL database and user, then copy the example environment file:

```bash
cp .env.example .env
```

Set `DATABASE_URL`, `EBAY_CLIENT_ID`, and `EBAY_CLIENT_SECRET` in `.env`.
`EBAY_ENVIRONMENT` selects matching production or sandbox credentials, and
`EBAY_MARKETPLACE_ID` selects the eBay site (for example, `EBAY_US`, `EBAY_ES`,
or `EBAY_DE`). The example values are deliberately non-secret.

Load the environment, sync locked dependencies, and create the schema:

```bash
set -a
source .env
set +a
cd backend
uv sync --locked
uv run alembic upgrade head
```

Run one search and persist up to 50 results:

```bash
uv run python -m sherlock ingest-ebay "omega seamaster" --limit 50
```

Repeating the command updates current fields, `last_seen_at`, and the raw JSONB
payload. It preserves `first_seen_at` and does not create a duplicate row.

## Development checks

From `backend/`:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

PostgreSQL integration tests run when `TEST_DATABASE_URL` is set. They are skipped
without it; CI always supplies a real PostgreSQL service. To verify migrations
against a disposable development or test database configured by `DATABASE_URL`:

```bash
uv run alembic upgrade head
uv run alembic check
```

### Landing page

Preview the static landing page with:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
