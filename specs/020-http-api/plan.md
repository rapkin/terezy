# Implementation Plan: The HTTP API — the schema the UI is a client of

**Feature**: `020-http-api` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Branch**: `feat/020-http-api`, landing on `main` by a `--no-ff` merge after a clean review.

**Clarifications**: answered 2026-09-03, [`specs/decisions/2026-09-03-clarify-020.toml`](../decisions/2026-09-03-clarify-020.toml).
The display switch is **deferred entirely**, so FR-021 to FR-025 are out of this plan; `as_of` is
required with no clock read; `reason` is optional in the schema and the absences are discovered by a
walk.

## Summary

One new module tree, `src/terezy/api/http/`, that serves what `data/` declares and the answer verb
already produces — and nothing else. It computes no figure: FR-003 has no exception now that the
display conversion is deferred, so no module under it constructs money at all.

The whole feature rests on one mechanism. A **shape** is derived once per annotated type — a tagged
description of what that type is made of — and two folds run over it: one builds the Pydantic model
the OpenAPI document is generated from, the other encodes an instance into the body. Both are
driven by the same shape, so the document and the bytes cannot disagree about a field; and FastAPI
validates the encoder's output against the model with `extra="forbid"`, which turns any drift into a
failed request rather than a wrong body.

Measured on the shipped tree while planning, and reproducible by `tests/contract/`:

| Measurement | Value |
|---|---|
| Records reachable from the response roots | **155**, of the core's 314 |
| Distinct `<leaf>.<ClassName>` tags over those 155 | **155** — injective, no override needed |
| Cycles in the reachable record graph | **none**, so no forward references and no `model_rebuild` |
| Callable-typed fields in the reachable graph | **none** |
| `Mapping` fields whose key is not `str` | **4** — two `TaxableEventKind`, one `LotMethod`, one `int` |
| `frozenset`-typed fields in the core | **11**, one of them provenance |
| Records whose annotations need a fallback namespace to resolve | **15**, all naming a `TYPE_CHECKING` import |

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`; `requires-python >= 3.12`).

**Primary Dependencies**: `fastapi`, `starlette`, `uvicorn[standard]`, `pydantic` — all four pinned to
exact versions (FR-037) because the gated OpenAPI bytes are a function of three of them. `pyyaml`
arrives in the closure through `uvicorn[standard]` and is what the compose-file tests parse with, so
the packaging tests add no dependency of their own.

**Storage**: none. Read-only over the version-controlled TOML under `data/`, resolved per request.
No cache: the declarations are small and a cache is where a stale value hides (Principle IV).

**Testing**: pytest with Starlette's in-process `TestClient` (FR-050). No test starts a server and no
test opens a socket; the suite's existing guard covers outbound connections and a scan covers the
listening half (SC-017).

**Target Platform**: loopback only. A host process under the default bind context, or a container
whose ports the host publishes to `127.0.0.1`.

**Project Type**: single Python library with two clients over `api/` — the CLI, unchanged, and now
HTTP.

**Constraints**: the core is untouched (SC-023a); no module under `terezy.api.http` constructs a
`Money`, calls a staleness function, or imports `core.results.canonical`; every set is serialised in a
declared total order; the committed OpenAPI document is byte-gated.

**Scale/Scope**: 25 categories, 3 fixed endpoints, 2 windowed series reads, and a 352 KB OpenAPI
document. Every endpoint sits under one `/api` prefix, declared in `document.py` and carried by
that document, so a generated client is correct by construction.

## Constitution Check

| Principle | Verdict |
|---|---|
| **I — Honesty over precision** | **PASS.** Every figure carries its provenance and the derived `is_unverified` verdict beside it (FR-018), swept off the response types rather than sampled. Nothing is converted, nothing is aged, nothing is summarised. A refusal arrives as itself, tagged, with its own fields and no synthesised message. |
| **II — Framework, not script** | **PASS.** The category set is a mapping from id to entry point and shape (FR-005), fail-closed against `data/` in both directions (FR-006, FR-007). A new declaration directory is a row plus its response type — and until it is one, the suite is red. |
| **III — Pure deterministic core** | **PASS.** The core gains nothing: the tag is derived by the HTTP layer from the record's identity (FR-011) and no core file is in the diff. Two runs of one request produce identical bytes across processes with different `PYTHONHASHSEED` (SC-009). No clock is read anywhere: `as_of` is required. |
| **IV — Reliability through contracts** | **PASS.** A refusal is a typed body, never a bare status. A missing id is a refusal and not a load error — the trap FR-008 names. `extra="forbid"` on every generated model makes an encoder that invents a field fail loudly. No tolerance is defined here; this feature compares no floats. |
| **V — Test-first** | **PASS.** Every module lands after a test that fails without it. The OpenAPI document is a gated artefact with a mutation check, and the refusal-union scan is a walk with no hand list. |
| **VI — The whole tuple** | **PASS, and this is the feature that carries it across the socket.** `OneWayCost` and `RoundTripCost` have the same nine fields; tagged, they serialise to different bodies (SC-006). Currency's display role is deferred by the owner, so nothing here can conflate it with the base or tax roles. |
| **VII — Owner-scoped and private** | **PASS.** The release gate is untouched and no supported path reaches its condition: a per-request client check under the default context, a startup refusal on the address, a verified container claim, a gated compose file. The documentation UI is off, so no page fetches from a CDN. |

No violation to justify, so **Complexity Tracking is empty**.

## Project Structure

### Documentation (this feature)

```text
specs/020-http-api/
├── spec.md
├── plan.md            # this file
├── research.md        # the six decisions that were open, and what settled them
├── data-model.md      # the shape algebra, the envelopes, the category table
├── contracts/
│   └── endpoints.md   # the route table as it will be registered
├── quickstart.md
└── tasks.md           # /speckit-tasks
```

### Source (repository root)

```text
src/terezy/api/http/
├── __init__.py        # re-exports the app, and states what this layer may not do
├── service.py         # the routed application, built from the category registry
├── shapes.py          # annotation -> Shape; the hint resolution and its fallback namespace
├── tags.py            # <leaf>.<ClassName>, the override table, injectivity
├── models.py          # Shape -> pydantic model (memoised), discriminated unions
├── encode.py          # Shape + value -> JSON-able body, in a declared total order
├── categories.py      # the registry: id -> (constant, shape, entry point, record type)
├── envelopes.py       # the response containers, their refusals, and the field descriptors
├── summary.py         # the registry summary (FR-009, FR-010, FR-054)
├── series.py          # windowed reads and the out-of-coverage refusal
├── answers.py         # the answer endpoint over declared questions
├── bind.py            # bind context, the loopback rule, the container marker
├── middleware.py      # the per-request client check and the Host allowlist
├── serve.py           # the process entry point that applies the guard, then serves
├── __main__.py        # `python -m terezy.api.http`
├── document.py        # info.version, the /api prefix, the canonical dump
└── openapi.json       # the gated artefact

src/terezy/data/citation_policy.py   # the gate's lists, now imported by the gate and served
scripts/generate_openapi.py
docker-compose.yml
Dockerfile
```

**Structure Decision**: `terezy.api.http` is a subtree of the existing `terezy.api` package, so
`.importlinter`'s `layers` contract places it above `data` and `core` with no change (FR-001). A new
`frameworks-only-in-the-http-module` contract forbids the framework everywhere else, and a scan
covers the two `__init__` files a `forbidden` contract cannot reach plus a completeness check over
`src/terezy/` (FR-002).

### Tests

```text
tests/contract/    the boundary claims: the category set both ways, tags, unions, the
                   provenance sweep, the import contracts, the money and canonical scans,
                   the lock-file closure, the compose file, the bind guard's closed set
tests/unit/        the shape algebra, the encoder's ordering, the series window, the
                   refusals, the registry summary
tests/golden/      the committed OpenAPI document, and the endpoint that serves it
```

## The mechanism, in the order it has to be built

1. **`shapes.py`** — `plan_of(annotation) -> Shape`, memoised. `Shape` is a tagged union:
   `RecordShape`, `UnionShape`, `OptionalShape`, `SequenceShape`, `SetShape`, `MappingShape`,
   `EnumShape`, `ScalarShape`. Hints resolve against the record's own module globals with a small
   fallback namespace for the 15 records whose annotations name a `TYPE_CHECKING` import; a test
   asserts every reachable record resolves, so the fallback cannot silently go short.
2. **`tags.py`** — the derivation, the empty override table consulted first, and injectivity over the
   walk.
3. **`models.py`** and **`encode.py`** — the two folds. The set ordering rule is *encode, then sort by
   the canonical JSON text of the encoded element*: one rule for strings, ints, enums and records
   alike, and no per-type key table to go stale.
4. **`categories.py`** — 25 rows, each naming its resolver entry point, its shape (keyed or
   singleton), whether it takes a scenario, and the record type its reads serialise.
5. **`envelopes.py`**, **`summary.py`**, **`series.py`**, **`answers.py`** — the four response families.
6. **`bind.py`**, **`middleware.py`**, **`serve.py`** — the guard, in the order FR-029 ranks them: the
   per-request check is the load-bearing half and is built first. No cross-origin allowance is
   declared: 021 is same-origin with this service in both of its modes.
7. **`document.py`**, `scripts/generate_openapi.py`, the committed `openapi.json`.
8. `docker-compose.yml`, `Dockerfile`, and the tests that parse them as text.

## What sits outside this feature's module and is required by it

| Where | What | Requirement |
|---|---|---|
| `pyproject.toml` | exact pins for `fastapi`, `starlette`, `pydantic`; `starlette` added to the `api` extra; `httpx2` in the dev group, which is what Starlette 1.6's test client requires | FR-037, FR-050 |
| `src/terezy/data/citation_policy.py` | the provenance gate's two directory lists, moved into the package so the gate and the API read one definition | FR-054 |
| `.importlinter` | the `frameworks-only-in-the-http-module` contract | FR-002 |
| `scripts/generate_openapi.py` | the regeneration command | FR-040 |
| repository root | `docker-compose.yml`, `Dockerfile` | FR-032 to FR-035 |
| `specs/features.toml` | `status = "in-progress"`, then the landing commit's `done` | `specs/README.md` |
| `docs/REQUIRED_TESTS.md` | test paths recorded on the rows this feature reinforces; **no box flipped** | FR-051 |

## Complexity Tracking

Empty: the Constitution Check has no violation.
