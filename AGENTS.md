# Development instructions

## Project

- Sherlock is a self-hosted watch marketplace monitoring and alerting project.
- It is currently pre-alpha.
- Prefer simple implementations and let the architecture evolve as real requirements emerge.

## Architecture

- Treat the codebase as a modular monolith.
- Keep clear internal module boundaries without prematurely creating independent services.
- Isolate marketplace-specific behavior behind adapters.
- Core and domain logic must not depend on how an individual marketplace is accessed.
- The API, worker/scheduler, frontend, and Discord bot may run as different processes while remaining part of the same application and codebase.
- PostgreSQL is the shared source of persistent state.
- Do not introduce Redis, message brokers, Elasticsearch, microservices, or similar infrastructure without a demonstrated need.

## Development workflow

- Never push directly to the default branch during normal development.
- Work on a short-lived branch and open a pull request.
- Keep pull requests focused on one coherent change.
- Do not mix unrelated refactors with feature work.
- Prefer small, understandable changes over speculative abstraction.
- During pre-alpha, do not preserve backwards compatibility for internal APIs unless an actual consumer requires it.

## Branch naming

Prefer these forms:

- feat/<short-description>
- fix/<short-description>
- refactor/<short-description>
- docs/<short-description>
- chore/<short-description>

Do not make branch naming more complicated than this.

## Commits

Use Conventional Commits. For example:

- feat: add ebay listing adapter
- fix: handle listings without prices
- refactor: extract listing normalization
- docs: document marketplace adapter contract
- chore: configure linting

Commits should be focused and understandable. Do not spend effort making intermediate branch history artificially perfect because pull requests are squash-merged.

## Pull requests

- Explain what changed and why.
- Explicitly mention architectural, schema, or dependency changes.
- Resolve review conversations before merge.
- Do not include unrelated changes.
- Repository merges are squash merges.

## Quality

- When formatting, linting, type checking, and testing tools exist, run the repository-provided commands before considering work complete.
- Prefer enforcing formatting and style mechanically rather than documenting cosmetic rules in prose.
- Add or update tests for meaningful behavior changes where appropriate.
- Do not invent tests solely to increase coverage metrics.

## Dependencies

- Avoid dependencies when the standard library or existing dependencies solve the problem cleanly.
- New infrastructure-level dependencies require a clear justification.
- Do not introduce technologies merely because they may become useful later.

## Security

- Never commit credentials, cookies, session data, API keys, Discord tokens, private marketplace data, or .env files.
- Use example environment files only with fake, documented values.
- Treat marketplace authentication and session material as sensitive.
- Do not log secrets or authentication material.

## Documentation

- Keep documentation aligned with actual behavior.
- Do not document planned functionality as if it already exists.
- Update relevant documentation when architectural decisions materially change.
