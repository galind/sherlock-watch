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

## License

Sherlock is licensed under the [GNU Affero General Public License v3.0](LICENSE).
