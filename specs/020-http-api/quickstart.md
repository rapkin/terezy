# Quickstart: 020-http-api

## Run the suite (no container, no daemon, no socket)

```bash
uv sync --all-extras --dev
uv run pytest -q                                  # the whole suite
uv run pytest tests/contract -q -k http           # the boundary claims
uv run lint-imports                               # includes frameworks-only-in-the-http-module
```

## Write out the OpenAPI document

The document is generated, never stored (owner decision 2026-09-05). The endpoint renders it, and
this writes the same bytes for a build that generates a client from them.

```bash
uv run python scripts/generate_openapi.py            # to standard output
uv run python scripts/generate_openapi.py --out /tmp/openapi.json
```

## Serve it locally

```bash
uv run python -m terezy.api.http --host 127.0.0.1 --port 8000
curl 'http://127.0.0.1:8000/api/routes?as_of=2026-09-03'
curl 'http://127.0.0.1:8000/api/questions/fifty-thousand-hryvnia/answer?as_of=2026-09-03'
curl 'http://127.0.0.1:8000/api/registry?as_of=2026-09-03'
```

`--host 0.0.0.0` exits non-zero naming the constitution's release gate. A bare
`uvicorn terezy.api.http:app --host 0.0.0.0` starts — and every request from a non-loopback client
is refused, which is the half FR-029 calls load-bearing.

## Run the packaged service

```bash
docker compose up api        # published at 127.0.0.1:8000 only; data/ mounted read-only
```

## What to check by eye after a change

- a figure in any response still carries its `provenance`, and `is_unverified` beside it;
- a refusal still arrives with its own fields and no message the record did not carry;
- `git diff` touches nothing under `src/terezy/core/` or `src/terezy/cli/`.
