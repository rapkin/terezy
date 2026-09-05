# Implementation Plan: The declared data, on a screen that can refuse

**Feature**: `021-web-declared-data` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

**Branch**: this plan is written on `plan/021-web-declared-data` and lands **squashed** — it is
spec-directory work, not an implementation. The implementation branch is `feat/021-web-declared-data`
and lands by `--no-ff`, and **may not start until `020-http-api` is `done` on `main`** (its `needs`).

## Summary

A read-only TypeScript client at `web/`, generated from feature 020's checked-in OpenAPI document
and reading nothing else, that browses what `data/` declares: a category overview, a record card
carrying every field with its citation and its mark, and the two declared series as charts with
their tables. It computes nothing.

The plan's own contribution, over restating the spec, is three findings and a build order.

**Finding one — three obligations 020 does not yet promise, and one it leaves ambiguous.** OB-2 (a
self-describing record), OB-3 (the declaring file path) and OB-6 (the citation exemption with its
reason) have no field in 020's draft. OB-7 is the ambiguous one: 020 FR-046 requires a window past
coverage to *refuse by name* and forbids returning a truncated result **silently** — and a body
carrying the in-coverage rows beside a named refusal is not silent, so the two specs probably agree
and 020 owes a sentence saying which body it means. The audit is [research D1](./research.md); the
resolution belongs to 020 or to this spec's scope, never to the client, and the tasks that depend
on each are marked.

**Finding one-and-a-half — the two specs have never agreed where the API is mounted.** FR-033 puts
the client's requests under `/api`; 020's endpoints are root-relative and its FR-007a requires flat
single segments, so the document a client is generated from has no `/api` in it. Development hides
it behind a proxy and production has none. The sharp edge is that FR-033's SPA fallback answers the
miss with `200 text/html`, so the failure presents as a parse error against a healthy API rather
than as FR-006's named state. [research D3a](./research.md).

**Finding two — 020's origin reasoning rests on a false premise about this feature.** 020 FR-032a
declares a CORS allowance and argues for it partly on the ground that serving the client from the
API's origin *"would break 021's development loop, where the client runs on its own port against
this service"*. It does not: FR-033 puts a **proxy** in that loop, so the browser is same-origin in
development too. [research D3](./research.md) states the proposed resolution and its blast radius,
which is the packaging tasks and nothing else.

**Finding three — the display switch is deferred, and it costs this feature almost nothing.**
The spec's three clarifications are answered (`specs/decisions/2026-09-03-clarify-021.toml`):
English only, the owner's own declarations shown and labelled as his statements, and the
display-currency selector question **moot** — the owner deferred the switch as a subject, so 020
ships no `display` parameter and there is no selector, no `display` search parameter and no display
scenario here. [research D0](./research.md) lists what is struck, what survives, and the
`[[future]]` entry that keeps the deferral visible; [research D11](./research.md) is the other two
answers. `as_of` becomes the only global search parameter; the two series routes keep their window.

**The build order** is the part that matters most for a feature blocked on another: everything that
does not need a live API is first — scaffold, tooling, four of the seven CI jobs, the mark and
refusal components against MSW fixtures, the router — and the two things that need the real document or the
real server are last. See *Ordering*.

## Technical Context

**Language/Version**: TypeScript, `strict`, on Node for tooling. No version is pinned in this plan
and none is asserted as a fact ([research, *Versions*](./research.md)); the lockfile is the record.

**Primary dependencies**: the owner's stack, decided on 2026-09-03 and not reopened here — pnpm,
Vite, React, Tailwind + shadcn/ui (copied in), TanStack Router, TanStack Query, Recharts,
`openapi-typescript` + `openapi-fetch`, Vitest + React Testing Library + MSW, Playwright, ESLint.
The concrete package list and where each sits is [`contracts/dependencies.md`](./contracts/dependencies.md);
the network-behaviour argument for each is the spec's own table and is not copied.

**Storage**: none. The client holds no state that outlives a page load. Everything on screen is a
function of the URL and a response.

**Testing**: Vitest + React Testing Library over MSW handlers typed from the document (FR-044);
Playwright against a real `uvicorn` on loopback over the shipped `data/`, offline (FR-045–FR-048).

**Target platform**: a browser on the owner's machine, reaching an API on `127.0.0.1`.

**Project type**: a TypeScript client outside the Python package. `web/` is a sibling of `src/`,
not a subdirectory of it — which is what makes *the UI may not import the core* a fact the build
cannot cross rather than a convention (constitution 1.4.0, *Architecture Constraints*).

**Constraints**: no request to any origin but its own, at run time, ever (FR-035, checked over the
built output by FR-036 and over the shipped image by FR-054); one production container (FR-049);
every published host port on `127.0.0.1` (FR-034, FR-052); one clock read in the whole client
(FR-021a); no hand-written response type and no cast over one (FR-005).

**Scale**: 25 categories over 69 files (020's endpoint table, measured 2026-09-03), and two series —
the larger of them `data/official_rates/ua_nbu_usd.toml` at 2,439 daily observations and growing by
one a day ([research D8](./research.md)). Five routes.

## Constitution Check

Against `.specify/memory/constitution.md` **v1.4.0**, whose D-B discharge and `web/` layer line this
feature is the reason for.

| Principle | How this feature meets it |
|---|---|
| **I — honesty over precision** | The whole feature. FR-007's three states, FR-008's prohibition on a blank cell where a refusal belongs, FR-009's mark carried in text, FR-011's per-figure rule. The client emits no number of its own, so it cannot emit one more confident than its inputs — it can only fail to carry the confidence the API stated, which is what every one of those requirements is about. |
| **II — framework not script** | FR-015: no category id, label or per-category branch in `web/src`, enforced by a scan against the **running API's own index** rather than against a hard-coded list — which would be the second copy it exists to forbid. The two series routes are the one declared exception (FR-015a) and a third is a decision taken in review. |
| **III — pure deterministic core** | `web/` cannot import the core: it is a TypeScript tree and its types come from one generated file. The client's own determinism is FR-021a's single clock read, and FR-048 makes the end-to-end suite deterministic by putting `as_of` in every URL an assertion reads a figure from. |
| **IV — stated contracts** | FR-004 is the mechanical form: a member added to a closed union fails the typecheck at every site that does not handle it, with no `default` arm to absorb it ([research D4](./research.md)). FR-006 makes a transport failure and a non-2xx response each a **named** state, so no failure presents as an empty list. |
| **V — test-first** | Every component task below is preceded by its test, and the test fails before the component exists. The feature adds no financial behaviour and therefore no worked example or golden; what it adds is a rendering contract, and the tests are the enumerating kind (SC-002 counts the figure-bearing components; SC-003 adds a union member to a copy of the document and asserts the build goes red). |
| **VI — the whole tuple** | Currency's three roles: base and tax render as the API returned them, and the **display role has no client at all** under the deferral ([research D0](./research.md)) — which is *the client converts nothing* holding by construction. FR-023 and FR-023a are the `as_of` half: staleness changes iff a threshold is crossed, and beyond that `as_of` changes exactly what the API says is a function of it. |
| **VII — owner-scoped and private** | FR-035's no-third-party-origin rule, checked over the built output and over the artefact inside the image; fonts vendored; no analytics, no telemetry, no error reporting, no source-map upload. FR-034 and FR-052 keep every published port on `127.0.0.1`, which is what stops the constitution's authentication release gate being reached **by accident** through a blank host field. Authentication itself is out of scope and unweakened. |

**Functional style (D-E)** applies here as it does in Python: components are functions, state is the
URL and a query result, and there is no client store (the spec's decision table, taken against
Redux and against MobX-from-the-start). MobX is the owner's standing preference for the day one is
needed; that day is not this feature.

**Prose discipline (1.3.0).** `scripts/check_prose_budget.py` and `scripts/check_enumerations.py`
measure `*.py` under `src`, `tests` and `scripts`. Neither sees `web/`, neither is extended by this
feature, and the spec argues why — in `web/` the enumeration rule is enforced by FR-004 instead, and
a ceiling recorded for a tree on its first day has no history behind it. A task confirms both stay
green on a tree that has grown a `web/` directory rather than assuming they will
([research D12](./research.md)).

**No violations to justify.** The Complexity Tracking table is empty.

## The `web/` layout

Only the parts that carry a requirement are annotated; the rest is a shape.

```text
web/
├── package.json  pnpm-lock.yaml  tsconfig.json  vite.config.ts  eslint.config.js
├── components.json                        shadcn/ui: components are copied in, not depended on
├── index.html
├── public/fonts/                          vendored (FR-035) — no runtime font fetch
├── src/
│   ├── main.tsx
│   ├── api/
│   │   ├── schema.d.ts                    GENERATED from src/terezy/api/http/openapi.json, COMMITTED (FR-003)
│   │   ├── client.ts                      openapi-fetch; same origin always, base path unsettled (D3a)
│   │   └── queries.ts                     TanStack Query options; one place a request is described
│   ├── search/params.ts                   as_of (global) and the series window: validators (FR-020, FR-027)
│   ├── clock.ts                           THE one clock read (FR-021, FR-021a) — the lint's sole exception
│   ├── lib/exhaustive.ts                  assertNever — FR-004's mechanism
│   ├── lib/provenance.ts                  narrowing guards over the response shapes; no cast (FR-005)
│   ├── components/
│   │   ├── ui/                            shadcn primitives, owned code, reviewed in git
│   │   ├── figure/                        FigureSlot, Mark, Refusal, Provenance, CitationExemption
│   │   ├── record/                        RecordCard, FieldRow, SyntheticFlag, DeclaringPath
│   │   ├── category/                      CategoryIndex, CategoryCard, RecordList, EmptyCategory
│   │   ├── series/                        SeriesChart, SeriesTable, CoverageRefusal
│   │   └── shell/                         AppShell, SkipLink, AsOfControl, ThemeToggle, ApiErrorState, ParameterError
│   └── routes/                            /, /data/:category, /data/:category/:id, /series/official-rate, /series/cpi
├── tests/
│   ├── msw/handlers.ts                    typed from the same document (FR-044)
│   └── unit/*.test.tsx
├── e2e/
│   ├── playwright.config.ts
│   ├── *.spec.ts                          FR-046's minimum
│   ├── a11y.spec.ts                       FR-043, every route, BOTH themes
│   └── category-id-scan.spec.ts           FR-015 — needs the running API's index
└── tools/
    ├── check-bundle-urls.mjs  bundle-url-allowlist.txt      FR-036, FR-054
    └── category-scan-exceptions.txt                        FR-015: paths, each with a one-line reason
```

**Two files this feature needs and does not own.** `docker-compose.yml` and the `Dockerfile` belong
to feature 020 (its FR-032, and this spec's *Assumptions*). This feature contributes the `web`
service stanza and the pnpm build stage; the tasks that add them say so and are last.

## The seven CI jobs, and how each is wired

The **spec's table is the requirement** — what each job fails on — and is not copied here. What
this plan adds is where each runs and what it runs, because a job with no command is a job nobody
built.

| Job | Wiring |
|---|---|
| Typecheck | `pnpm -C web exec tsc --noEmit`. Node setup + `pnpm install --frozen-lockfile`. |
| Lint | `pnpm -C web lint`. Carries R1's exhaustiveness rule and FR-021a's clock rule. |
| Unit | `pnpm -C web test` (Vitest, jsdom, MSW). |
| End-to-end | `uv sync` + Node setup; starts `uvicorn` on `127.0.0.1` through 020's own entry point (its FR-026b), then `pnpm -C web exec playwright test`. Carries the a11y pass and the category-id scan **inside it** (spec's table). |
| Type sync | Regenerate `web/src/api/schema.d.ts` from `src/terezy/api/http/openapi.json`; `git diff --exit-code` on it. |
| Bundle URLs | `pnpm -C web build`, then `node web/tools/check-bundle-urls.mjs web/dist`. Its second input — the assets extracted from the image — is produced by the smoke job ([research D9](./research.md)). |
| Compose smoke | Static parse of `docker-compose.yml` across **every service and every profile** for a published port not naming `127.0.0.1`; then build, `up`, and assert one container, one origin, no Node toolchain, and the extracted-asset URL check. |

**All seven are unconditional**, not filtered on a `web/` path. The spec gives the reason and it is
the whole point of the type-sync job: it exists to turn red when a **Python** change moves the
OpenAPI document, and a path filter would disable it on the only change it was built for.

## Ordering, and why it is shaped by the block

Implementation cannot start before 020 is `done`, so the order minimises what waits on it.

**API-independent** — everything below can be written, run and reviewed against fixtures, with no
OpenAPI document and no server: the scaffold and the toolchain; four of the seven CI jobs (type
sync waits for something to compare, and the two that need a browser or an image wait too); `assertNever` and the lint that protects it; the router with
its typed `as_of` and window validators, the redirect and the one clock read; every figure, record,
category and series component; the chart properties no route can reach (FR-031, FR-031a); the
bundle-URL check; the a11y harness. These are written against **hand-written fixtures shaped like
the spec's Key Entities**, which is the one place in this feature a hand-written type is allowed —
because it is a fixture for a component, not a response type (FR-005 governs the second).

**API-bound** — three things, and only three: generating `schema.d.ts` from the real document and
re-typing the MSW handlers and query layer onto it; the Playwright suite against the real server;
and the packaging tasks that touch 020's two files. Everything before them is a component library
with tests, which is exactly what should be waiting when 020 lands.

## Artefacts

```text
specs/021-web-declared-data/
├── spec.md
├── plan.md                          (this file)
├── research.md                      D0–D12, and the risks to verify at implementation time
├── data-model.md                    what the client renders, and the three states every figure has
├── contracts/
│   ├── api-obligations.md           OB-1..OB-9 against 020, and what the client does under each
│   ├── components.md                the component inventory, each with its requirement and its test
│   └── dependencies.md              the concrete package list, and where each sits
├── quickstart.md                    how to run it, and how to check one citation by hand
└── tasks.md                         (/speckit-tasks)
```

## Complexity Tracking

Empty. No constitutional gate is bent by this feature, and the one place it could have been — a
per-category rendering branch — is forbidden by FR-015 and checked by SC-012.
