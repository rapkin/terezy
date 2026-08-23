# Implementation Plan: Composed paths

**Feature**: `004-composed-paths` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-composed-paths/spec.md`

**Branch**: `feat/004-composed-paths` in `.claude/worktrees/004-composed-paths`, landing on
`main` by a `--no-ff` merge after a clean review pass (`specs/README.md` §4–5)

## Summary

Let the engine reach a destination through intermediate venues when no single declared
route goes end to end — by chaining declared routes, costing every chain in full through
the one costing function, and ranking the results in one league with declared routes.

The technical shape, decided in [research.md](./research.md), is built around a single
idea: **a composed candidate is not costed differently, it is costed as its concatenated
legs.** `legs_of(candidate, routes)` turns either kind of candidate into one leg sequence
and `cost_one` walks it unchanged, so SC-002's "same costing function, asserted by
construction" is a fact about the code rather than a comparison of numbers that agree.
Capacity pools, provenance, staleness and latency then compose for free, because 002's fold
never knew what a route was.

Three shapes are fixed here and are expensive to get wrong later. **The path type widens**
into `Candidate = FundingPath | ComposedPath`, matched on — FR-013's distinction is
structural, not a boolean. **The exit chain joins the ranked unit's identity**, so two exit
chains from one destination are two ranked candidates rather than one record holding two
figures a ranking could not order. And **the search is enumeration, not routing**: an
adjacency index per `(regime, direction)`, depth-first, sorted buckets, a visited-venue set,
and a declared bound — nothing pruned by cost, because pruning by cost is the heuristic this
spec exists to keep out.

This feature also closes a recorded tension. `EXIT_BY_IDENTITY` makes costing agree with
feature 003's identity decision, so `identity-exit-vs-partner-requirement` comes off the
future list instead of being deferred a second time.

## Technical Context

**Language/Version**: Python 3.13 (`.python-version`); CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new. `pydantic` validates the one new declaration at the
`data` boundary. No graph library — the search is a depth-first walk over a few dozen edges
and importing one would put a third party between a declaration and a figure.

**Storage**: version-controlled TOML. One new per-owner directory, `data/composition/`. No
database, no cache, no network, nothing persisted between runs (FR-021).

**Testing**: pytest. Hand-computed leg-by-leg arithmetic for SC-001 and SC-015; Hypothesis
properties for the cycle rule, exhaustiveness, determinism-under-reordering and
direction discipline; the existing golden `ramp_comparison.golden.txt` as the check that
002's registries produce byte-identical results after the shape widens.

**Target Platform**: library only. No API, no CLI, no UI. Results are produced and asserted
by the test suite, as in 001–003.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none, and this is a stated position rather than an omission.
Enumeration within the declared bound is costed in full; if that is slow, the honest levers
are the bound and the registry, both data. A faster answer produced by costing less than
every candidate is 002 FR-029 undone.

**Constraints**: core pure and deterministic; exactly four plugin interfaces and this
feature adds none; functional style per D-E; one imported tolerance; money is `float64` in a
currency-tagged wrapper.

**Scale/Scope**: 2 new core modules, 4 touched core modules, 3 touched data-layer modules,
1 new declaration file and directory, ~10 test modules across all five suites.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; refusals typed and carrying their reason | **PASS, and this is the principle the whole spec is organised around.** Composition is a routing problem, and routing attracts estimates, pruning and tie-breaks by visit order — every one a number more confident than its inputs. The design refuses each structurally: every candidate is costed in full, ties are 002's ties, and there is no field for a path score. The one place a number could have been invented — a junction between two segments — is defined to convert nothing, charge nothing and wait for nothing. |
| **II — Framework, not script** | Data-only extensibility; exactly four plugin interfaces | **PASS.** No fifth interface. Reach is a function of the declarations: SC-010 adds one route file and gets new fully-costed candidates with zero source changes. The one knob — the segment bound — is data with no default, on 002 FR-028's precedent. |
| **III — Pure deterministic core** | No I/O, no clock, no randomness; traceable | **PASS, and determinism is load-bearing here rather than incidental.** A search is where iteration order leaks into output, so the adjacency buckets are sorted by route id and SC-003 runs the registry in both orders and compares everything. No clock: the as-of date stays a parameter. |
| **IV — Reliability through contracts** | Property-based invariants; one tolerance; explicit failure | **PASS.** Four properties: no venue twice over the whole emitted set, exhaustiveness within the bound, order-independence, and direction discipline. 002's cost-attribution invariant gains a second axis (segments sum to the total) rather than being replaced. Tolerance is imported, never redefined — and ties are computed with it, which is exactly where a local epsilon would have been tempting. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** SC-001 and SC-015 are hand-computed leg-by-leg; the pool case (SC-007) is hand-computed because it is a claim about 002's design surviving composition. 002's golden file is the regression that the shape widening changed no number. |
| **VI — Model the whole tuple** | Access cost never per instrument; round-trip not one-way; currency roles distinct | **PASS, and the feature sharpens two terms of the tuple at once.** Keying widens to `(destination × stream × path × exit chain)` and a per-destination cost stays unrepresentable. FR-012 makes the *exit route out* term composable while FR-030's refusal stands where nothing chains — the round trip is never a promoted one-way figure. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; tagged unions; no ABCs | **PASS.** `Candidate` and `ExitChain` are unions matched with `match`; `compose` and `legs_of` are free functions; `EXIT_BY_IDENTITY` is a single-member `Enum` rather than `None`. |
| **VII — Owner-scoped and private** | `owner_id` from day one; curated vs per-user separated; no telemetry | **PASS.** The segment bound is per-owner policy in its own directory beside `data/streams/` and `data/spendable/`, carrying `owner_id`, with the one-owner refusal feature 003 established. No new dependency, no network. |

**No violations requiring justification.** Two items of genuine added complexity are in
Complexity Tracking.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced
that the pre-check had not:

- **The exit chain had to join the ranked unit's identity, or FR-012 and FR-010 could not
  both hold.** A `RampCost` holding several round-trip figures has no defined position in a
  ranking ordered by round-trip cost, and the first thing an implementer would do is pick
  one — arriving at the blend FR-012 forbids by accident rather than by decision. Making it
  part of the key is the only shape where "two exit chains are two figures" and "one
  ranking" are compatible.
- **Duplicate suppression is a trap with a specific shape.** `Leg.index` is per-route, so a
  concatenation yields `0,1,0` where the declared equivalent has `0,1,2`, and naive tuple
  equality never matches — the ranking would hold the same real-world movement twice, which
  is precisely what SC-013 checks. Normalising the index before comparison is a two-line
  detail that the spec cannot be expected to state and the implementation cannot afford to
  miss.
- **This feature had to take a position on a tension it did not create.** Feature 003's
  identity decision and 002's partner requirement disagree exactly when composition lands —
  `features.toml` says so. Deferring again would ship a known FR-018 violation; the sentinel
  resolves it, and it must be a *distinct value* rather than a zero-length chain, because a
  round trip that costs nothing because there is nothing to do is a different claim from one
  whose fees cancelled.

## Project Structure

### Documentation (this feature)

```text
specs/004-composed-paths/
├── spec.md              # Feature specification (22 FRs, 18 SCs, 3 clarifications + 1 review finding)
├── plan.md              # This file
├── research.md          # Phase 0 — thirteen decisions with rationale
├── data-model.md        # Phase 1 — records, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── composition.md               # compose / legs_of, and guarantees G1–G17
│   └── composition-declaration.md   # the segment-bound TOML, and its refusals
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── routes/
│   ├── compose.py                      NEW — adjacency index, depth-first enumeration, bound
│   ├── path.py                         TOUCHED — ComposedPath, ExitChain, Segment, Candidate
│   ├── cost.py                         TOUCHED — legs_of; cost_one takes a Candidate
│   ├── ranking.py                      TOUCHED — one league over both kinds
│   └── execute.py                      TOUCHED — derive events from a composed figure
└── results/
    ├── composed.py                     NEW — Enumeration, CompositionRefused
    └── ramp.py                         TOUCHED — SegmentAttribution, exit_path, binding_segment

src/terezy/data/declarations/
├── schema.py                           TOUCHED — CompositionFile, CompositionTable
├── loader.py                           TOUCHED — composition_from_file
└── resolver.py                         TOUCHED — the bound joins the resolved declarations

scripts/check_provenance.py             TOUCHED — EXEMPT_DIRS gains composition, with its reason

data/composition/owner-001.toml         NEW — the one declaration this feature adds
```

### Tests

```text
tests/worked_examples/
├── test_composed_arithmetic.py         SC-001 — leg-by-leg by hand, chain vs declared
├── test_composed_exit_chain.py         SC-015 — round trip over a chained exit, both ways
└── test_composed_pool.py               SC-007 — shared headroom across two segments

tests/invariants/
├── test_composition_search.py          SC-004, SC-005, SC-016 — cycles, bound, directions
└── test_composition_order.py           SC-003 — reversed declaration order changes nothing

tests/unit/
├── test_composed_feasibility.py        SC-008, SC-012 — closed segment, regime discipline
└── test_composed_duplicates.py         SC-013 — leg-chain identity with index normalised

tests/contract/
├── test_composed_same_costing.py       SC-002, SC-009, SC-011 — by construction
├── test_composed_distinct.py           SC-017, SC-018 — visibly composed, per-chain figures
└── test_composition_declaration.py     FR-006 — every refusal in the declaration contract

tests/golden/
└── test_ramp_comparison.py             UNCHANGED FILE — 002's golden must not move
```

**Structure Decision**: the existing single-library layout. Two new core modules in
packages that already exist, one new per-owner data directory, no new layer and no change
to `.importlinter`.

## Complexity Tracking

| Added complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| `RampCost` keyed by exit chain as well as inbound path | FR-012: two exit chains are two round-trip figures, never blended, and FR-010 puts them in one ranking | A record holding several round-trip figures cannot be ordered by round-trip cost, so ranking would have to pick one — the blend FR-012 forbids, reached by accident |
| `ExitChain` is a three-member union rather than a route id | 002's single partner, FR-012's chain, and 003's identity case are three different claims about how money gets out | Collapsing identity into a zero-length chain erases the difference between "nothing to do" and "fees cancelled", which is a Principle I distinction |

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: the **declaration and
its refusals** first, then the **widened types** (nothing costs until `Candidate` exists),
then **`legs_of` with 002's golden file green** — that is the checkpoint proving the shape
widened without moving a number — then **enumeration**, then the **properties**. Tests
before implementation in each group.
