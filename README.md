# Sherlock

Sherlock is an open-source, self-hosted watch marketplace monitoring project.

Sherlock is pre-alpha. The backend contains marketplace-neutral listing domain
types, a boundary for marketplace adapters, and an initial Vinted catalog client
and normalizer. It does not yet persist listings, schedule searches, or send
alerts.

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

## Development

The backend requires Python 3.13 or newer and
[uv](https://docs.astral.sh/uv/). From `backend/`, install the locked development
dependencies and run the checks with:

```bash
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Preview the static landing page from the repository root with:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
