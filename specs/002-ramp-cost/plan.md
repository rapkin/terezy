# Implementation Plan: The ramp

**Feature**: `002-ramp-cost` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-ramp-cost/spec.md`

**Branch**: none — this repo works on `main` by design

## Summary

Compute what it costs to move money from where it arrives to where an instrument lives,
per income stream and per route — the largest term in the owner's real decision, and the
one the predecessor left out entirely.

The technical shape, decided in [research.md](./research.md): routes, legs, streams and
channels are **pure declared data** and need no new plugin interface; leg *kinds* are an
algorithm registry, the same boundary already set for day-count conventions. Costing is a
pure calculation run for every candidate; **execution** derives ledger events from the
costed figure so the two cannot disagree. A cost is keyed by a `FundingPath` triple with no
partial form, so a per-destination cost has no type to live in. One-way and round-trip are
distinct types, so a missing exit route cannot be papered over with the figure that is
available.

Nothing in `core` gains a clock: staleness is measured against an as-of date passed in, and
a monthly cap is an accumulator in the fold.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`); CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new. `pydantic` continues to validate declarations in `data`
only. No array library — the arithmetic is a handful of legs per route.

**Storage**: version-controlled TOML under `data/routes/`, `data/streams/`,
`data/channels/`, `data/scenarios/`, plus a new `data/observation_kinds.toml`. No database,
no cache, no network.

**Testing**: pytest; Hypothesis for the cost-attribution and no-clamping invariants;
hand-computed worked examples for G1, G2 and G4. Markers `worked_example`, `invariant`,
`contract`, `golden`.

**Target Platform**: library only. No API, no CLI, no UI — unchanged from feature 001.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. Ranking a handful of routes over a handful of legs.
Correctness and traceability are the only goals.

**Constraints**: core pure and deterministic, no clock; money is float64 with one imported
tolerance; exactly four plugin interfaces project-wide and **this feature adds none**;
functional style per D-E.

**Scale/Scope**: ~8 new core modules under `core/routes/` and `core/streams/`, ~3 data-layer
modules, ~6 declaration files, ~11 test modules covering 8 rows of
`docs/REQUIRED_TESTS.md`.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; unverified marks propagate; staleness surfaces | **PASS.** Every route number here is an unobserved figure at first run (§11 item 1), so the marks matter more than anywhere else. A missing exit route yields no round-trip figure rather than a promoted one-way figure (FR-030). Staleness is reported per value kind. |
| **II — Framework, not script** | Data-only extensibility; exactly four plugin interfaces | **PASS, and this is the load-bearing check.** No fifth interface: routes/legs/streams/channels are data, leg kinds are an algorithm registry on the day-count precedent (research.md D1). `Provider` stays unimplemented with its seam named. SC-010 is the executable test. |
| **III — Pure deterministic core** | No I/O, no clock; every figure traceable; manifest | **PASS.** Staleness takes an as-of date as input (D9); a monthly cap is a fold accumulator (D7). Both are the alternative to a clock, not a workaround for one. The as-of date lands in the manifest. |
| **IV — Reliability through contracts** | Property-based invariants; one tolerance; explicit failure | **PASS.** Two new invariant suites: cost attribution sums to total, and cost-then-execute agreement (D5). Failures are tagged-union members; `raise` reserved for a broken chain reaching core, which is a programmer error. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** G1/G2/G4 are hand-computed; the §4.3.1 percentage is the headline arithmetic. Network already blocked. |
| **VI — Model the whole tuple** | Access cost never per instrument; round-trip not one-way; currency roles distinct | **PASS, and this feature is where the principle is actually enforced.** FR-008's per-destination cost is made unrepresentable by type (D2), not discouraged by convention. One-way and round-trip are distinct types (D4). Base and tax currency stay distinct; display remains out of scope. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; registries of functions; tagged unions | **PASS.** `abc` blocked in core; leg-kind and channel dispatch are `Mapping[str, Callable]` on the established pattern. |
| **VII — Owner-scoped and private** | `owner_id` from day one; curated vs per-user separated; no telemetry | **PASS.** Streams are per-owner data and carry `owner_id`; routes and channels are curated and shared. That boundary is sharper here than anywhere so far, and the plan keeps them in separate directories to make it structural. |

**No violations requiring justification.** Two items of genuine added complexity are
recorded in Complexity Tracking.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced
that the pre-check had not:

- **The stream/route split is a Principle VII boundary, not just tidiness.** A stream is the
  owner's salary; a route is a public fact about a corridor. Putting them in one directory
  would make per-user and curated data indistinguishable at the filesystem level, which is
  the boundary the constitution says makes multi-user cheap later.
- **`FundingPath` must not carry the amount.** A path is *which way*, an amount is *how
  much*. Folding the amount in would make the key of a cost include the cost's input, so two
  amounts through one route would look like two paths — and the cap accumulator keyed by
  route would stop working.
- **Cost attribution needs a closed set of components, not a free-form mapping.** FR-003
  wants the reader to see which term dominates. A `dict[str, Money]` would let a leg invent
  a component name and break the "components sum to total" invariant silently. A closed
  enumeration makes the sum checkable.

## Project Structure

### Documentation (this feature)

```text
specs/002-ramp-cost/
├── spec.md              # Feature specification (complete, 30 FRs, 16 SCs)
├── plan.md              # This file
├── research.md          # Phase 0 — nine decisions with rationale
├── data-model.md        # Phase 1 — entities, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── route-costing.md          # cost_one / execute / rank, and their guarantees
│   └── declaration-schema.md     # the TOML shapes for routes, streams, channels, kinds
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16 passing)
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── primitives/
│   ├── staleness.py                    NEW — Observed kinds, as-of evaluation, no clock
│   └── (existing: money, provenance, tolerance, rates, currency, conventions)
├── routes/                             NEW (package exists, empty)
│   ├── venues.py                       Venue record
│   ├── channels.py                     FX channel: two-sided rates, premium form
│   ├── legs.py                         Leg record + LEG_COST_FNS registry
│   ├── path.py                         FundingPath — the triple with no partial form
│   ├── cost.py                         cost_one — the ONLY costing function
│   ├── execute.py                      events derived from a RampCost
│   ├── ranking.py                      rank — recommendation as an index
│   └── capacity.py                     monthly cap accumulator
├── streams/                            NEW
│   └── streams.py                      IncomeStream record, deployable capacity net of tax
├── ledger/
│   └── (existing; capacity accumulator added to LedgerState)
└── results/
    └── ramp.py                          NEW — RampCost, OneWayCost, RoundTripCost, ExitCostUnknown

src/terezy/data/
├── declarations/
│   ├── schema.py                       extended: routes, streams, channels, kinds
│   ├── loader.py                       extended
│   └── resolver.py                      extended: leg chaining, kind resolution
└── manifest.py                          extended: the as-of date is a recorded input

data/
├── routes/            inbound and exit routes, declared in pairs (FR-027)
├── channels/          NEW — two-sided rates per channel
├── streams/           NEW — per-owner; the Principle VII boundary
├── scenarios/         regimes: transition date as a stated assumption
└── observation_kinds.toml  NEW — staleness threshold per kind, no default

tests/
├── worked_examples/   test_ramp_p2p_premium.py (G2), test_two_streams.py (G1),
│                      test_regime_transition.py (G4)
├── invariants/        test_cost_attribution.py, test_cost_execute_agreement.py,
│                      test_no_silent_clamping.py (B13)
├── contract/          test_route_declaration_loading.py, test_route_data_only.py (SC-010),
│                      test_per_destination_cost_unrepresentable.py (FR-008),
│                      test_same_code_path.py (SC-016), test_staleness.py (FR-028)
└── golden/            extended: the ramp comparison artefact
```

**Structure Decision**: `core/routes/` and `core/streams/` as separate packages, and
`data/streams/` separate from `data/routes/`. The split is the Principle VII boundary made
structural: a stream is per-owner data (the owner's salary, its amount, its arrival venue),
a route is curated data shared across owners (a public fact about a corridor). One directory
holding both would make that distinction a matter of reading field names.

`staleness.py` goes in `primitives` rather than `routes` because it applies to every observed
value in the project, not only route costs — the OVDP yield is stale-able too.

## Implementation sequence

| # | Step | Closes | Depends on |
|---|---|---|---|
| 1 | `primitives/staleness.py` + observation kinds | FR-025, FR-028 | — |
| 2 | `routes/venues.py`, `channels.py` — two-sided rates, premium form | FR-010, FR-011 | 1 |
| 3 | `routes/legs.py` + `LEG_COST_FNS` registry | FR-001 | 2 |
| 4 | `routes/path.py` — `FundingPath` | FR-008 | — |
| 5 | `results/ramp.py` — `OneWayCost`, `RoundTripCost`, `ExitCostUnknown`, `RampCost` | FR-002, FR-030 | 4 |
| 6 | `routes/cost.py` — the single costing function, attributed | FR-003, FR-004, FR-005 | 3, 5 |
| 7 | `streams/streams.py` — deployable capacity net of income tax | FR-006, FR-007, FR-009 | 1 |
| 8 | `routes/capacity.py` + `LedgerState` accumulator | FR-012, FR-015 | 6 |
| 9 | `routes/execute.py` — events derived from the costed figure | FR-005, FR-013 | 6, 8 |
| 10 | `routes/ranking.py` — recommendation as an index | FR-016, FR-017, FR-018, FR-029 | 6 |
| 11 | Regimes in scenario data | FR-019, FR-020 | 10 |
| 12 | `data.declarations` extension: schema, loader, chaining resolver | FR-021, FR-024 | 1–11 |
| 13 | Declaration files: routes in pairs, channels, streams, kinds | FR-023, SC-010 | 12 |
| 14 | `check_provenance.py`: `streams`, `channels`, kind resolution | FR-022 | 13 |
| 15 | Golden artefact for the ramp comparison; flip the eight rows | — | all |

Steps 1–6 are the spine and are worth landing as one green checkpoint. Steps 7 and 12–13 are
parallelisable against 8–11.

## Risk register

| Risk | Why it matters here | Guard |
|---|---|---|
| A per-destination cost sneaks in | Hides the entire §4.3.1 finding; reads as reasonable code | `FundingPath` has no partial form (D2); contract test asserts no public function accepts a destination alone |
| The winner and the alternatives diverge | A comparison nobody can trust; would surface as an unexplained gap | Recommendation is an **index** into the costed set; test asserts identity, not equality (D3) |
| A one-way figure promoted to round-trip | A confident number for an exit nobody costed | Distinct types; mypy strict catches the assignment (D4) |
| Fees silently clamped at zero | Predecessor defect B13; money vanishes with no diagnostic | Invariant suite plus an explicit test for fees exceeding the amount |
| Cost and execution drift apart | Ledger would disagree with the comparison that chose the route | `execute` derives from `cost_one`'s attribution; agreement is a property test (D5) |
| A stale route cost passes unnoticed | Invalidates every comparison built on it, silently | Per-kind thresholds, no permissive default; a kind without one fails at load |
| A clock creeps in for staleness | Would break C4 determinism for a convenience | `datetime.now` blocked in core; as-of date is an input recorded in the manifest |
| Leg kinds drift toward a fifth interface | Principle II amendment by accident | The registry is `Mapping[str, LegCostFn]` on the day-count precedent; contract test asserts the four interfaces are still four |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| `FundingPath` as a mandatory triple, threaded through every costing signature | FR-008 requires a per-destination cost to be *unrepresentable*. A convention cannot deliver that, and this project has already had a mislabelled figure pass review twice | A required keyword argument is still satisfiable with a constant; a naming convention is the mechanism that already failed on `nominal_ytm` |
| Two functions over one arithmetic — `cost_one` pure, `execute` deriving events from it | A comparison costs many routes and executes one, but FR-005 needs every executed fee as a recorded line | Events for all candidates would put fees in the ledger for money that never moved; two independent implementations is the divergence D3 exists to forbid |

## Deferred, with the seam named

**`Provider` stays unimplemented.** FX channels are declared data in this feature, and the
function resolving `(channel, date) → two-sided rate` is shaped so that it becomes a
`Provider` call later without changing its callers. Building `Provider` now would mean
inventing a rate source.

**Required test F1** — a position flat in USD across a devaluation posting a taxable UAH
gain, which `REWRITE_BRIEF.md` calls "the reason the rewrite exists" — is deliberately not
here. It needs a taxable foreign instrument and dated official rates for the tax base. This
feature builds the channels that make it possible and stops.
