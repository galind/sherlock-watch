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
- Dependency-free static landing page; Next.js and TypeScript product frontend planned
- Discord integration
- Docker Compose and Caddy

## Development

The public landing page is a dependency-free HTML and CSS site in `frontend/`.
To preview it locally, run:

```bash
python3 -m http.server 8000 --directory frontend
```

Then visit [http://localhost:8000](http://localhost:8000).

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
