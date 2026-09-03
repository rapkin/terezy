# The api service's image. An official Python base and no other image pulled (020 FR-034):
# `uv` arrives from the package index rather than from a second image, so the only registry
# this build reads from is the one holding `python`.
#
# The index fetch is a build-time act. At runtime this service opens no outbound connection,
# which is what Principle VII is about. Nothing in the suite builds this file -- the checks in
# tests/contract/test_the_shipped_compose_file.py parse it as text, so `uv run pytest` needs no
# daemon (FR-035).
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

EXPOSE 8000

# terezy's own entry point, never a bare server command: it is the one that applies the bind
# guard before it binds (FR-026b). No CMD, so `docker run` with no arguments takes the entry
# point's own default of 127.0.0.1 -- reachable inside the container and nowhere else. The
# address a published container needs is named by docker-compose.yml, which is also the file
# the port-publication gate reads.
ENTRYPOINT ["python", "-m", "terezy.api.http"]
