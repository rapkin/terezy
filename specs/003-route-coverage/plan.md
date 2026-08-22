# Implementation Plan: The coverage report

**Feature**: `003-route-coverage` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-route-coverage/spec.md`

**Branch**: `feat/003-route-coverage` in `.claude/worktrees/003-route-coverage`, landing on
`main` by a `--no-ff` merge (`specs/README.md` §5)

## Summary

Turn feature 002's per-route refusals into a first-class audit of the whole registry: for
every `(destination × stream × regime)`, is this comparable — and if not, exactly which
single declaration is missing, and how many comparisons that one observation would unblock.

The technical shape, decided in [research.md](./research.md): the report is a **pure fold
over declarations** in `core/routes/coverage.py`, with frozen records in
`core/results/coverage.py`, on exactly the split `cost.py` / `results/ramp.py` already use.
It adds **no plugin interface** and **no code branch per venue or corridor** — every
question it asks is a query over data. It adds **exactly one declaration**: a per-owner
spendable-endpoint list at `data/spendable/owner-001.toml`, beside `data/streams/` because
where the owner spends is a fact about him, not about the world.

Three things the design makes structural rather than conventional. **No cost figure can
appear**, because no field in the report can hold a `Money`, a `Provenance`, a
`StalenessVerdict` or a `float`, and a recursive type walk asserts it across the whole
output rather than sampling. **A missing declaration carries no regime**, so the same hole
in two regimes is one value-equal record with two counts, never a sum. **A pair can carry
two deficits**, so an inbound and an exit that are both missing are both listed and both
marked not alone sufficient.

The one thing this feature must not do is the next feature's job: no chaining, no reversing,
no composed path. A two-hop way out is a hole here, and FR-018's forward note is written
into the contract so the 004 author finds it.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`); CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new. `pydantic` validates the one new declaration file at the
`data` boundary, as every other file. Hypothesis for the two property suites.

**Storage**: version-controlled TOML. One new directory, `data/spendable/`, holding one
per-owner file. No database, no cache, no network.

**Testing**: pytest. A hand-enumerated coverage table as the worked example (SC-001); a
Hypothesis property over generated registries for coverage-vs-costing agreement (SC-009),
reusing `tests/invariants/route_graphs.py`; contract tests for the no-cost-figure walk and
for data-only extensibility. Markers `worked_example`, `invariant`, `contract`.

**Target Platform**: library only. No API, no CLI, no UI — unchanged since feature 001. The
report is produced and asserted by the test suite (spec Assumptions: "no delivery surface").

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. The universe is venues × currencies × streams × regimes — tens
of pairs, not thousands. Correctness and traceability are the only goals.

**Constraints**: core pure and deterministic and **without a clock — this feature does not
even take an as-of date**, because coverage is a claim about declarations, not about today.
Exactly four plugin interfaces project-wide and this feature adds none. Functional style per
owner decision D-E. No money and no float anywhere in the output.

**Scale/Scope**: 2 new core modules, 3 touched data-layer modules, 1 new declaration file,
~8 test modules. No lettered row of `docs/REQUIRED_TESTS.md` is closed by this feature —
stated in the spec rather than stretched — and B10, B12, H2 and G6 are reinforced.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; refusals are typed and carry their reason | **PASS, and this feature is Principle I as a product.** It exists to make an absence a fact the owner acts on. Every not-ready verdict names what is missing; an empty registry dimension is a typed outcome, never an empty report (FR-020, defect B10); and the report states in its own output that its verdicts are advisory (FR-019), so the gap between the owner's rule and today's enforcement is on the face of the artifact, not only in the spec. |
| **II — Framework, not script** | Data-only extensibility; exactly four plugin interfaces | **PASS, and this is the load-bearing check.** No fifth interface, no new registry, no branch per venue or corridor. The spendable list — the one thing that could plausibly have been a constant — is a data file, and SC-019 tests exactly that: adding a venue to it flips a verdict with zero lines of source changed. SC-014 tests the same for a new venue. |
| **III — Pure deterministic core** | No I/O, no clock, no randomness; every figure traceable | **PASS, more strictly than 002.** 002 took an as-of date to measure staleness; coverage takes no date at all, because declaration is not availability (FR-022 ⚙). Every collection is a tuple in a stated order, so the same declarations produce the identical report (FR-016). `audited` records the id set the report was computed from (FR-021). |
| **IV — Reliability through contracts** | Property-based invariants; one tolerance; explicit failure | **PASS.** Two properties: coverage-vs-costing agreement over generated registries (SC-009), and totality — every pair in the declared universe appears exactly once (SC-001/FR-001). **No tolerance is imported and none is defined**: this feature produces no float, so there is nothing to compare within a tolerance. That absence is itself the check — a tolerance appearing in this feature's code would mean a number leaked into the report. Failures are tagged-union members; nothing raises. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** SC-001's hand-enumerated coverage table is the worked example, its enumeration checked in beside the assertion. SC-009 is the property. Every test builds its registry in-process; no fixture reaches the network. |
| **VI — Model the whole tuple** | Access cost never per instrument; round-trip not one-way; currency roles distinct | **PASS.** The feature is the tuple's *funding route in* and *exit route out* terms audited together: FR-002 is precisely the refusal to call a destination comparable on the strength of a way in alone. Base and tax currency stay distinct and untouched; FR-004 pins spendable to base currency only, which is the display/base conflation refused before it can happen. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; tagged unions; no ABCs | **PASS.** `coverage` is a function; every record is a frozen dataclass with no behaviour; `Ready | NotReady` and `CoverageReport | RegistryDimensionEmpty | ReservedRegimeId` are tagged unions matched on, not flags. |
| **VII — Owner-scoped and private** | `owner_id` from day one; curated vs per-user separated; no telemetry | **PASS, and the new file is where it is tested.** `data/spendable/owner-001.toml` carries `owner_id` and sits in a per-owner directory beside `data/streams/`, not at the root beside curated `venues.toml` (research.md D3). No new dependency, no network. |

**No violations requiring justification.** Two deliberate widenings of the spec's letter are
recorded in Complexity Tracking; both are widenings toward honesty, and both are written
down rather than absorbed silently.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced
that the pre-check had not:

- **"No cost figures" is a type-level property, not a review item.** SC-004 and SC-008 both
  say *verified across the whole output, not sampled*. The only reading of that which stays
  true when someone adds a field in six months is a recursive walk over
  `dataclasses.fields` banning `Money`, `Provenance`, `StalenessVerdict` and `float`
  (research.md D12). Discovering that also settled Principle IV's tolerance question: this
  feature has no tolerance because it has no float.
- **FR-018's agreement property had to be scoped before it was written, not after it
  failed.** `cost_one` refuses for two different reasons — no such way, and not feasible
  today — and only the first is what coverage claims. An unscoped property fails the first
  time Hypothesis picks a small amount, and the fix under pressure would have been to weaken
  coverage rather than the property. Scoped in research.md D11 and stated at the assertion
  site.
- **Deficit kind 2's name does not survive contact with FR-011.** "Inbound exists but no
  exit partner" cannot be conditioned on the inbound existing, or a pair missing both halves
  could not list both. The kinds classify the exit side; the inbound side is reported
  independently (research.md D7). The three deficits stay distinguished, which is what
  FR-003 is actually protecting.

## Project Structure

### Documentation (this feature)

```text
specs/003-route-coverage/
├── spec.md              # Feature specification (24 FRs, 20 SCs, both clarifications resolved)
├── plan.md              # This file
├── research.md          # Phase 0 — sixteen decisions with rationale
├── data-model.md        # Phase 1 — records, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── coverage-report.md     # `coverage` and its sixteen guarantees
│   └── spendable-schema.md    # the one new TOML shape, and its refusals
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── routes/
│   ├── coverage.py                     NEW — the fold: destinations, matching, deficits, to-do
│   └── (existing: venues, legs, cost, path, ranking, channels, capacity, execute)
└── results/
    ├── coverage.py                     NEW — CoverageReport and every record it holds
    └── (existing: ramp, hurdle, schedule, project, canonical)

src/terezy/data/declarations/
├── schema.py                           TOUCHED — SpendableFile, OwnerTable, SpendableTable
├── loader.py                           TOUCHED — spendable_from_file, SPENDABLE_TABLE
└── resolver.py                         TOUCHED — CoverageDeclarations, coverage_from_data_root

data/
└── spendable/
    └── owner-001.toml                  NEW — the one declaration this feature adds
```

### Tests

```text
tests/worked_examples/
└── test_coverage_table.py              SC-001, SC-002, SC-012 — hand-enumerated table checked in

tests/invariants/
├── test_coverage_costing_agreement.py  SC-009 — the scoped property over route_graphs.py
└── test_coverage_totality.py           FR-001 — every pair exactly once, over generated registries

tests/unit/
├── test_coverage_deficits.py           SC-003, SC-005, SC-006, SC-010, SC-011, SC-017
├── test_coverage_regimes.py            SC-007, SC-018 — per regime, implicit regime, one shared item
└── test_coverage_empty.py              SC-013 — every empty dimension, typed

tests/contract/
├── test_coverage_no_figures.py         SC-004, SC-008, SC-016, SC-020 — the recursive walk, determinism, advisory
├── test_coverage_data_only.py          SC-014, SC-019, SC-015 — data-only extensibility, closed-route visibility
└── test_spendable_declaration_loading.py  every refusal in contracts/spendable-schema.md
```

**Structure Decision**: the existing single-library layout, unchanged. Two new core modules
in packages that already exist, three touched data-layer modules, one new data directory.
No new package, no new layer, no change to `.importlinter`.

## Complexity Tracking

> Two widenings of the spec's letter. Neither is added machinery; both are recorded because
> a reader comparing spec to code would otherwise find a discrepancy and have to guess.

| Widening | Why needed | Narrower reading rejected because |
|---|---|---|
| `RegistryDimensionEmpty` names a fourth dimension, `spendable`, which FR-020 does not list | An empty spendable list makes every exit deficit 3 — a report full of confident wrong verdicts | Leaving it out produces exactly the confident-but-empty output FR-020 exists to forbid; the loader refuses it too, so the typed outcome only fires for direct core calls (which the tests make) |
| Deficit kinds classify the exit side independently of the inbound side, widening FR-003's phrase "inbound exists but no exit partner" | FR-011 and the spec's own "missing both" edge case require both missing declarations to be listed for one pair | Conditioning the exit deficit on inbound presence makes a pair missing both halves report only one, and the second observation the owner needs would be invisible until he had made the first |

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: the **declaration and
its refusals** first (the report cannot be tested without a spendable list), then the
**records**, then the **fold**, then the **properties**. Tests before implementation in each
group — a test failing with `ImportError` counts, per `specs/README.md` §2.
