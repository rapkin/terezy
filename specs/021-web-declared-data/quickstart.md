# Quickstart: run it, and check one citation by hand

**Feature**: `021-web-declared-data` | **Plan**: [plan.md](./plan.md)

Written for the day after the feature lands. Nothing here works before `020-http-api` is `done` on
`main`, because there is no API and no OpenAPI document to generate from.

## Run the two halves

```bash
uv sync --all-extras --dev
pnpm -C web install --frozen-lockfile

# terminal 1 — the API, on loopback, through terezy's OWN entry point (020 FR-026b).
# Never a bare server command: `uvicorn terezy.api.http:app --host 0.0.0.0` never
# reaches the bind guard, which is the case 020 FR-026a exists for.
uv run python -m terezy.api.http --host 127.0.0.1 --port 8000

# terminal 2 — the client. Its dev server proxies /api to the above (FR-033),
# so the browser is same-origin here exactly as it is in production.
pnpm -C web dev
```

Open the printed `127.0.0.1` URL. The app **redirects once**, writing `as_of` into the URL from the
one clock read (FR-021), and renders nothing until it is there. That redirect is the only place in
the client a clock is read, and a lint rule fails any other (FR-021a).

## The validation that matters: a citation, checked against the file

This is the feature's *Independent Test* for User Story 1, and it is the one thing a screenshot
cannot fake.

1. From the overview, open any category, then any record. Two clicks and three (SC-001).
2. On the card, read a field's **citation**, its `retrieved_on`, and its `verified_on`.
3. Read the **declaring file path** off the same card (FR-018), open that file in the repository,
   and find the same three values.

They match, or the feature is broken. That is the whole claim: **a mark survives from a TOML file
to a pixel**, and the only way to ask it is against the real stack.

An empty `verified_on` renders as the **unverified mark, in text** (FR-017, FR-009). If you can
select it with the mouse it is text; if you cannot, styling is carrying it alone, which FR-009
forbids and which the unit assertion catches by stripping every style declaration first.

## The refusal that is easiest to reach

Open `/series/cpi` and edit the window in the URL so its end runs past the last observation.

**Expected:** the in-coverage observations are **plotted**, and the refusal for the rest is on
screen **with its reason** — the two in one view (US3 scenario 4). No line continues past the last
observation, and the chart is not replaced by the refusal.

**If instead the whole chart is replaced by a refusal**, the OB-7 conflict was resolved 020's way
and this scenario was cut rather than built ([research D1](./research.md)). Check the spec before
filing a defect.

## The gates, as CI runs them

```bash
# Each script below regenerates the types first, which is why each needs `uv` on the path:
# `gen:types` runs 020's scripts/generate_openapi.py into openapi-typescript. The output is
# gitignored, so what proves the types are current is that tsc then passes over them —
# FR-003 and SC-013 in the form the owner's decision of 2026-09-05 gives them.
pnpm -C web typecheck                  # FR-004, FR-005, and the type-sync gate
pnpm -C web lint                       # the no-default-arm rule and the one-clock rule
pnpm -C web test                       # Vitest + RTL over MSW handlers typed from the document
pnpm -C web build && pnpm -C web check-bundle-urls   # FR-036 — absolute URLs against the allowlist

# end-to-end — FR-045 to FR-048, plus the a11y pass and the category-id scan inside it. The
# config starts both halves itself, on loopback, over the shipped data/.
pnpm -C web e2e
```

The Python gates are unchanged and must stay green on a tree that has grown a `web/` directory:

```bash
uv run pytest --cov && uv run mypy && uv run lint-imports
uv run python scripts/check_prose_budget.py && uv run python scripts/check_enumerations.py
```

Neither prose script is extended to `web/` — both walk `*.py` under `src`, `tests` and `scripts`,
and the spec argues why they stay that way ([research D12](./research.md)).

## The production shape, in one command

```bash
docker compose up            # no profile: the `web` service does not start (FR-051)
```

**One** container comes up, publishing on `127.0.0.1` only, serving the API and the built client
from **one origin** (FR-049, SC-014). It contains no Node toolchain and no `web/` source
(FR-053, SC-015). The development stack is the same file behind its profile:

```bash
docker compose --profile dev up
```
