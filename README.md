# Sherlock

Sherlock is an open-source, self-hosted watch marketplace monitoring project.

Sherlock is pre-alpha. Marketplace source viability is currently being evaluated,
and there is no production marketplace integration yet. The backend is deliberately
small: it contains only marketplace-neutral listing domain types and the boundary
future marketplace adapters can use to normalize listings.

The repository also includes a dependency-free static landing page in `frontend/`.

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
