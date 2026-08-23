# Implementation Plan: CPI and real terms

**Feature**: `007-cpi-real-terms` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-cpi-real-terms/spec.md`

**Branch**: `feat/007-cpi-real-terms` in `.claude/worktrees/007-cpi-real-terms`, landing on
`main` by a `--no-ff` merge after a clean review pass (`specs/README.md` §4–5)

## Summary

Fill the slot feature 001 reserved and left honestly empty. A nominal 15.5% against
double-digit inflation is a materially different proposition, and until now the output said
"not modelled" rather than implying otherwise.

**The data is already here.** `data/cpi/ua.toml` was fetched on 2026-08-23 by
`scripts/fetch_cpi.py` from Держстат via data.gov.ua — 411 monthly observations, 1991-08 to
2025-10, each cited, each with an **empty** verification date. This feature reads that
committed file and knows nothing about the script.

The shape, decided in [research.md](./research.md), turns on the owner's 2026-08-22
resolution of a real collision: 001's FR-022 forbids a real figure from an assumed rate, yet
a hurdle projects into the future where only assumptions exist. The answer was **both
figures, separately labelled, never mixed** — so the reserved slot holds a two-field record
rather than one number, and FR-006's invariance survives because `HurdleRate` still has
exactly one field named `real`.

Three pieces of arithmetic discipline do the rest. Inflation over a window is a **product**
of month-on-month observations, never a sum. The real rate is the **exact Fisher relation**,
and the subtraction approximation is not merely discouraged — no function in this feature
performs it. And coverage is **all-or-nothing**: one missing month makes the realized figure
unavailable naming that month, because silently shortening the window produces a real number
for a window nobody asked about.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new.

**Storage**: `data/cpi/ua.toml`, already committed and already in `SOURCED_DIRS`; plus one
inflation-assumption declaration under `data/scenarios/`. No database, **no network** — the
loader reads a file and never learns the fetcher exists.

**Testing**: pytest. Hand-computed deflation over a window long enough that summing and
multiplying differ visibly; a falling-prices case; coverage-gap refusals; provenance union
asserted by count rather than by sample.

**Target Platform**: library only.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. A product over at most a few hundred floats.

**Constraints**: core pure, no clock; exactly four plugin interfaces and **this feature adds
none**; functional style per D-E; one imported tolerance; **no nominal figure may move**.

**Scale/Scope**: 1 new core package (2 modules), 2 touched core modules, 3 touched
data-layer modules, 1 new declaration, ~8 test modules.

## Constitution Check

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs | **PASS, and this feature is 001's deferred honesty being paid off.** The slot was left empty rather than filled with a guess; it is now filled with two figures that never blend, each naming what it rests on. Every refusal names the specific missing month, series, figure or assumption — 001's generic reason stops being true the moment this lands and survives nowhere. |
| **II — Framework, not script** | Data-only extensibility; four interfaces | **PASS.** No fifth interface. Periodicity is declared per series, never fixed in the engine, and a second series with a different identity is a data-only addition that loads and is addressable — FR-002 forbidding a singleton is the executable form of this. |
| **III — Pure deterministic core** | No I/O, no clock | **PASS, and the boundary is sharper here than usual.** The data arrived over the network, and the network lives in `scripts/fetch_cpi.py`, outside the package, outside the layers, run by hand. The core reads a committed file. `.importlinter` and the socket guard both enforce it. |
| **IV — Reliability through contracts** | Invariants; one tolerance; explicit failure | **PASS.** `Coverage` is a tagged union returned *before* any arithmetic runs, so an uncovered window cannot reach the Fisher relation at all. Failure is typed throughout. One imported tolerance. |
| **V — Test-first** | Worked example, invariant or golden | **PASS.** The deflation arithmetic is hand-computed on a window chosen so the sum and the product visibly disagree — a test that a summing implementation cannot pass. |
| **VI — Model the whole tuple** | Currency roles; nothing conflated | **PASS.** Real terms are a third reading of the same hryvnia figure, and the labelling rules keep nominal and real as distinct as one-way and round-trip are in 002. |
| **Engineering Standards — D-E** | Frozen records; tagged unions; no ABCs | **PASS.** `Covered \| NotCovered` and `RealRate \| RealTermsUnavailable` are unions matched with `match`; `basis` is a closed `Literal` on the record rather than inferred from which field holds it. |
| **VII — Owner-scoped and private** | Curated vs per-owner; no telemetry | **PASS.** CPI is a curated public observation and lives in `data/cpi/`; the inflation assumption is the owner's belief and lives in `data/scenarios/`, exempt from the citation gate for the reason that directory already carries. |

**No violations requiring justification.** Two design costs in Complexity Tracking.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced:

- **The reserved slot could not simply hold a number.** FR-009's two figures and FR-006's
  unchanged shape are only compatible if the slot stays one field and its occupant carries
  both. A second field on `HurdleRate` would have broken the invariance that FR-022 existed
  to create — which would have been an odd way to honour it.
- **`RealTerms` must never itself be unavailable.** "Which of the two is missing" is the
  question FR-012 requires answering, and a single unavailable value cannot answer it. So the
  record always exists and holds two independently-typed outcomes.
- **Two different questions both look like staleness.** "Is this observation stale?" is the
  45-day threshold; "does the series reach the end of my window?" is the coverage check. Both
  can fire on one run, they mean different things, and merging them into one message would
  make a re-fetch look like a data gap or the reverse.

## Project Structure

### Documentation (this feature)

```text
specs/007-cpi-real-terms/
├── spec.md              # Feature specification (15 FRs, all clarifications resolved)
├── plan.md              # This file
├── research.md          # Phase 0 — ten decisions with rationale
├── data-model.md        # Phase 1 — records, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   └── deflation.md     # coverage / cumulative_inflation / deflate / real_terms, G1–G13
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── inflation/                          NEW package
│   ├── series.py                       CpiSeries, Coverage, cumulative_inflation, InflationAssumption
│   └── deflate.py                      the Fisher relation, and nothing else
└── results/
    └── hurdle.py                       TOUCHED — RealTerms, RealRate.basis, specific reasons

src/terezy/data/declarations/
├── schema.py                           TOUCHED — CpiFile, InflationAssumptionTable
├── loader.py                           TOUCHED — cpi_from_file, the assumption
└── resolver.py                         TOUCHED — the series joins the resolved set

data/
├── cpi/ua.toml                         ALREADY COMMITTED — read, not written
└── scenarios/inflation_owner.toml      NEW — the declared assumption, is_assumption = true
```

### Tests

```text
tests/worked_examples/
├── test_deflation_arithmetic.py        the Fisher relation and the chained product, by hand
└── test_falling_prices.py              a negative-inflation window: real above nominal

tests/unit/
├── test_cpi_coverage.py                gaps named; the window never shortened
└── test_real_terms_reasons.py          all four specific reasons; the 001 text gone

tests/contract/
├── test_cpi_declaration_loading.py     the refusal battery, including the shipped file
├── test_two_figures_never_blend.py     realized and assumed distinguishable; no blended field
├── test_provenance_propagation.py      TOUCHED — the union, asserted by count
└── test_no_subtraction_approximation.py  an AST scan: nothing subtracts inflation from nominal

tests/golden/
└── test_end_to_end_ovdp.py             001's figures unmoved; the real slot's two lines expected
```

**Structure Decision**: one new small package, two touched core modules, no new layer, no
change to `.importlinter`.

## Complexity Tracking

| Design cost | Why accepted | Simpler alternative rejected because |
|---|---|---|
| `RealTerms` wraps two independently-typed outcomes rather than the slot holding a rate | FR-009's two figures and FR-012's specific reasons both require knowing *which* is missing | One field of `RealRate \| Unavailable` cannot say that half the answer exists, and the natural repair — a second field on `HurdleRate` — breaks FR-006 |
| `Coverage` is returned before any arithmetic rather than checked inside `deflate` | An uncovered window then cannot reach the Fisher relation at all | A check inside the computation is a check someone later moves, reorders or short-circuits; a union returned first makes the uncovered case unrepresentable downstream |

## The expected golden diff, stated before it happens

`tests/golden/ovdp_synthetic_a.golden.txt` **will** move, on exactly one kind of line: the
real slot renders two entries instead of one, and its reason changes from 001's *"inflation
is not modelled in this feature"* to the specific reason FR-012 requires — today, that the
declared series ends 2025-10 and the window is uncovered.

Every nominal figure, every schedule row and every tax charge stays byte-identical. **If a
nominal figure moves, stop** — FR-014 is the whole claim of this feature's additivity.

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: **the series and its
coverage first**, because the refusal path is the one that runs today (the shipped series ends
before any hurdle window); then the Fisher relation with its worked example; then the slot;
then the assumption. Tests before implementation in each group.
