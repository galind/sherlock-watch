# Sherlock

Sherlock is a self-hosted watch marketplace monitoring and alerting project.

It will periodically monitor supported watch marketplaces, normalize listings, filter and classify them according to user-defined criteria, and notify users about relevant listings.

> Sherlock is currently pre-alpha. It is intended to be self-hosted and open source.

## Architecture

Sherlock is intended to use a modular-monolith architecture: clear internal module boundaries within one codebase, with separate processes where useful.

The broad stack is:

- Python and FastAPI backend
- PostgreSQL
- Marketplace-specific adapters
- Python worker and scheduler
- Next.js and TypeScript frontend
- Discord integration
- Docker Compose and Caddy

The currently implemented backend foundation provides a marketplace-independent
listing model and an eBay adapter that normalizes representative listing payloads.
It does not make marketplace network requests or persist listings yet.

## Development

The backend requires Python 3.13 or newer and
[uv](https://docs.astral.sh/uv/). From `backend/`, install the locked development
dependencies and run the checks with:

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
