# The api service's image. Official base images only (020 FR-034, extended by 021 FR-049 to the
# Node stage that builds the client): `uv` and `pnpm` arrive from their package indexes rather
# than from a third image, so the only registries this build reads from are the ones holding
# `python` and `node`.
#
# The index fetch is a build-time act. At runtime this service opens no outbound connection,
# which is what Principle VII is about. Nothing in the suite builds this file -- the checks in
# tests/contract/test_the_shipped_compose_file.py parse it as text, so `uv run pytest` needs no
# daemon (FR-035).

# ---------------------------------------------------------------------------
# The OpenAPI document, generated rather than read from the repository (owner decision
# 2026-09-05). The client's types come out of it, so the client stage needs Python to exist --
# and the final stage carries neither (021 FR-053).
FROM python:3.13-slim AS schema

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN pip install --no-cache-dir uv==0.9.5
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra api --no-install-project
COPY src ./src
COPY scripts/generate_openapi.py ./scripts/generate_openapi.py
RUN uv sync --locked --no-dev --extra api \
 && mkdir -p /schema \
 && uv run python scripts/generate_openapi.py --out /schema/openapi.json

# ---------------------------------------------------------------------------
# The client, built from web/ and from the document above and from nothing else (021 FR-049).
# Installed frozen from the lockfile: a build that can pick a different dependency than CI
# typechecked is a build whose gates prove nothing (FR-050).
FROM node:22-slim AS client

ENV CI=1
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
COPY --from=schema /schema/openapi.json /schema/openapi.json
ENV TEREZY_OPENAPI_JSON=/schema/openapi.json
RUN pnpm gen:types && pnpm exec tsc --noEmit && pnpm exec vite build \
 && node tools/check-bundle-urls.mjs dist

# ---------------------------------------------------------------------------
# What ships: the Python application, its runtime, and the built assets. No Node toolchain and
# no `web/` source (021 FR-053) -- the final stage copies `dist` and nothing that produced it.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN pip install --no-cache-dir uv==0.9.5

WORKDIR /app

# Dependencies before sources, from the locked file only, so a source edit does not re-resolve.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra api --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --extra api

# One origin serves the API and the client, so there is no CORS allowance to declare and no
# reverse proxy to run (021 FR-049).
COPY --from=client /web/dist /app/web/dist
ENV TEREZY_WEB_DIST=/app/web/dist

EXPOSE 8000

# terezy's own entry point, never a bare server command: it is the one that applies the bind
# guard before it binds (FR-026b). No CMD, so `docker run` with no arguments takes the entry
# point's own default of 127.0.0.1 -- reachable inside the container and nowhere else. The
# address a published container needs is named by docker-compose.yml, which is also the file
# the port-publication gate reads.
ENTRYPOINT ["python", "-m", "terezy.api.http"]
