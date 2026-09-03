# syntax=docker/dockerfile:1

FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --locked --no-dev --no-editable


FROM builder AS development-builder

RUN uv sync --locked --no-editable


FROM python:3.13-slim-bookworm AS image-base

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 sherlock \
    && useradd --system --uid 10001 --gid sherlock \
        --create-home --home-dir /home/sherlock sherlock

WORKDIR /app

COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations

USER sherlock

ENTRYPOINT ["python", "-m", "sherlock"]
CMD ["--help"]


FROM image-base AS development

ENV RUFF_CACHE_DIR=/tmp/ruff-cache

COPY --from=development-builder /opt/venv /opt/venv
COPY backend/src ./src
COPY backend/tests ./tests
COPY backend/pyproject.toml ./pyproject.toml


FROM image-base AS runtime

COPY --from=builder /opt/venv /opt/venv
