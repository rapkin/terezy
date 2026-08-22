---
description: "Task list for 002-ramp-cost"
---

# Tasks: The ramp

**Input**: Design documents from `specs/002-ramp-cost/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: **Mandatory, written first.** Constitution Principle V. Interleaved below, never
a trailing phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **[Story]**: US1–US5
- Every task names its files and the requirement or required-test row it closes

## Binding constraints for every task

Read before starting. Not suggestions.

- **Functional style** (constitution 1.1.0, D-E): free functions over frozen dataclasses. No
  classes with behaviour, no inheritance, no ABCs, no `Protocol` with methods, **no operator
  dunders**. `abc`, `hashlib`, `pydantic`, `pathlib` blocked in `core`.
- **No fifth plugin interface.** Routes, legs, streams, channels are data. Leg kinds are a
  `Mapping[str, LegCostFn]` registry on the day-count precedent. If you find yourself
  writing an interface, re-read research.md D1.
- **`Money(` only in `core/primitives/money.py` and `data/declarations/`** — a test enforces
  it. Use `money.*`, and `money.scale_sourced` whenever the factor came from declared data.
- **One tolerance**, imported from `core/primitives/tolerance.py`. A looser bound needs its
  reason stated at the assertion site.
- **No clock in `core`.** `as_of` and `on_date` are parameters. A month comes from an
  event's `occurred_on`.
- **Domain failures are tagged unions**, matched with `match` plus an unreachable
  `case _:`. `raise` only for programmer errors.
- **Nothing is clamped.** Fees over the amount are reported; `fraction` may exceed 1.0.

**On test-first**: a test written before its module fails with `ImportError`. That counts.
Do not stub a module to make an import succeed.

---

## Phase 1: Setup

- [x] T001 [P] Create `src/terezy/core/streams/__init__.py` with a charter docstring noting streams are per-owner data while routes are curated (Principle VII)
- [x] T002 [P] Add a charter docstring to `src/terezy/core/routes/__init__.py` (the package exists but is empty)
- [x] T003 Add the new modules to `tests/unit/test_package_layout.py` and confirm `uv run lint-imports` still passes

**Checkpoint**: packages importable, boundaries intact.

---

## Phase 2: Foundational (BLOCKING — strictly sequential)

**Purpose**: staleness, the route graph, the funding key, the result types, and the single
costing function. Everything else depends on these.

**⚠️ Sequential. Do NOT split across parallel agents.** `cost_one` is the one function
FR-029 hangs on; two agents writing it concurrently would produce the second code path the
requirement exists to forbid.

- [x] T004 Write `tests/contract/test_staleness.py` — two values with the same retrieval date and different kinds go stale at different ages; a kind with no `staleness_days` fails; staleness is evaluated against a passed-in `as_of` and never a clock. Closes **FR-025**, **FR-028**. Must fail first
- [x] T005 Implement `src/terezy/core/primitives/staleness.py` — `ObservationKind`, `StalenessVerdict`, free functions `is_stale(retrieved_on, kind, *, as_of)` and `staleness_of(provenance, kinds, *, as_of)`
- [x] T006 Write `tests/worked_examples/test_channel_rates.py` — hand-computed: a premium of +3 UAH against a reference of 42 gives `3/42`; a 150 bps markup gives 0.015; a **negative** premium is legal; a **zero** premium means at-reference. Closes part of **FR-004**, **FR-010**
- [x] T007 Implement `src/terezy/core/routes/venues.py` — `Venue` record with the currencies it can hold
- [x] T008 Implement `src/terezy/core/routes/channels.py` — `FxChannel`, `ChannelSide` (exactly one of `markup_bps` / `premium_per_unit`), and `effective_rate(side, reference)`. **Both sides required, neither derived from the other** — a system computing the sell side from the buy side is using a mid-rate with extra steps
- [x] T009 Write `tests/unit/test_leg_costs.py` — one hand-checked case per leg kind, plus an unknown kind failing loudly and naming the known ones
- [x] T010 Implement `src/terezy/core/routes/legs.py` — `Leg` record and `LEG_COST_FNS: Mapping[str, LegCostFn]` for `transfer`, `fx`, `trade`, `withdrawal`. An `fx` leg requires a channel; the others forbid one
- [x] T011 Write `tests/contract/test_per_destination_cost_unrepresentable.py` — scan `core.routes` public signatures and fail on any that accepts a destination without a stream and a route. Closes **FR-008**. **This is the most important test in the feature**: a per-destination cost hides the entire §4.3.1 finding and reads as perfectly reasonable code
- [x] T012 Implement `src/terezy/core/routes/path.py` — `FundingPath(destination_id, stream_id, route_id)`, all three required, no defaults, no optional variant, and **no amount** (research.md D2, and the post-Phase-1 note in plan.md)
- [x] T013 [P] Write `tests/unit/test_round_trip_types.py` — a `OneWayCost` cannot occupy the round-trip slot (a mypy error, asserted structurally); `ExitCostUnknown` names the route whose partner is missing. Closes **FR-030**, part of **G6**
- [x] T014 Implement `src/terezy/core/results/ramp.py` — `CostComponent` (a **closed** enumeration, not a free-form mapping), `OneWayCost`, `RoundTripCost` as unrelated records, `ExitCostUnknown`, `RampCost`, `RouteUnusable`
- [x] T015 Write `tests/invariants/test_cost_attribution.py` — over generated routes and amounts, the components sum to `sent − arrived`. Closes part of **FR-003**. Must fail first
- [x] T016 Implement `src/terezy/core/routes/cost.py` — `cost_one`, the **only** costing function. Attributed by component, `as_of` and `on_date` as separate parameters, provenance merged through `money.scale_sourced` wherever a declared rate is applied. Closes **FR-001**–**FR-005**, **FR-011**, **FR-026**

**Checkpoint**: `pytest -m "invariant or contract"` green. **Commit.** Parallel work may begin.

---

## Phase 3: User Story 1 — Know what the ramp costs (P1) 🎯 MVP

**Goal**: every route that can carry an amount, each with its one-way cost, round-trip cost,
ceiling, latency and status, and which is cheapest.

**Independent test**: state an amount and a declared premium; check both cost percentages
against hand arithmetic.

- [x] T017 [US1] Write `tests/worked_examples/test_ramp_p2p_premium.py` — the **G2** example: +3 UAH at a stated reference reproduces the §4.3.1 percentage exactly, one way and round trip, with the arithmetic checked in beside the assertion. Closes **G2**, **SC-001**, **SC-002**. Must fail first
- [x] T018 [US1] Write `tests/contract/test_same_code_path.py` — `recommended_cost(r) is r.costed[r.recommended]`, asserted with **`is`**, not `==`. Closes **SC-016**, **FR-029**
- [x] T019 [US1] Implement `src/terezy/core/routes/ranking.py` — `rank` costing every candidate with `cost_one`, ordering **lexicographically** on `(round-trip cost, ceiling desc, latency)` with ties on **cost alone**, and returning `Ranking(costed, recommended: int, excluded, ties, not_comparable)`. **No composite score** — B12 forbids one (research.md D11). Closes **FR-016**, **FR-018**, **FR-029**
- [x] T020 [P] [US1] Write `tests/unit/test_ranking_ties_and_exclusions.py` — a tie is reported as a tie, never broken arbitrarily; an excluded route carries its reason; a destination whose round trip is `ExitCostUnknown` lands in `not_comparable` and out of the ranking. Closes **FR-018**, **FR-014**, **SC-014**
- [x] T021 [P] [US1] Write `tests/contract/test_cost_labels.py` — every cost figure in every result type is reachable only through a one-way or round-trip named field; no figure is unlabelled. Verified across every field, not sampled. Closes **G6**, **FR-002**, **SC-005**
- [x] T022 [P] [US1] Write `tests/unit/test_zero_cost_domestic_route.py` — a route whose every leg declares zero fees and no conversion costs **exactly** zero and delivers exactly what was sent. This is the bar the others are measured against. Closes **SC-004**

**Checkpoint**: the §4.3.1 finding is computed. **MVP. Commit.**

---

## Phase 4: User Story 2 — Fund it from the right stream (P1)

**Goal**: the same acquisition costs almost nothing from one stream and several percent from
the other, and no cost is attributable to a destination alone.

- [x] T023 [US2] Write `tests/worked_examples/test_two_streams.py` — the **G1** example: the same USD acquisition funded from the UAH salary and from the USD contract income differs by exactly the hand-computed ramp cost. Arithmetic checked in. Closes **G1**, **SC-003**. Must fail first
- [x] T024 [US2] Implement `src/terezy/core/streams/streams.py` — `IncomeStream`, `Indexation`, and `deployable(stream)` returning the amount net of any declared income tax. Closes **FR-006**, **FR-007**
- [x] T025 [P] [US2] Write `tests/unit/test_deployable_capacity.py` — an undeclared `income_tax_rate` is **`None`, not zero**, and the output says "no rate declared" rather than showing a net figure that quietly equals the gross. Closes part of **FR-007**
- [x] T026 [P] [US2] Write `tests/unit/test_usd_stream_converts_nothing.py` — a route from the USD stream with no `fx` leg reports a conversion component of **exactly** zero, not a small residual. Closes **FR-009**, **SC-006**
- [x] T027 [P] [US2] Write `tests/unit/test_stream_venue_mismatch.py` — a route whose `origin` differs from the stream's `arrives_at` is reported, never assumed away. Closes a spec edge case

**Checkpoint**: commit.

---

## Phase 5: User Story 3 — Respect what the route will allow (P2)

**Goal**: caps, minimums, latency and status enforced; every fallback reported.

- [x] T028 [US3] Write `tests/invariants/test_capacity_accumulator.py` — over generated event streams, consumed capacity per `(route, year, month)` never exceeds the cap, and capacity consumed earlier in the same month reduces the headroom. Closes **FR-015**. Must fail first
- [x] T029 [US3] Implement `src/terezy/core/routes/capacity.py` and add the accumulator to `LedgerState` — keyed by `(capacity_pool, year, month)` taken from each event's `occurred_on`, **never a clock**, and **never by route**: two routes through one Monobank card consume one limit (research.md D10). Confirm C1–C6 still pass: this is new state in the fold. Closes **FR-012**
- [x] T030 [US3] Write `tests/invariants/test_cost_execute_agreement.py` — `execute`'s fee events sum to exactly `cost_one`'s figure and the ledger's arriving amount equals the `RampCost`'s. **This invariant is what allows the comparison to be pure while execution is recorded** (research.md D5). Must fail first
- [x] T031 [US3] Implement `src/terezy/core/routes/execute.py` — events **derived from** a `RampCost`'s per-leg attribution, never recomputed beside it. One fee event per fee-bearing component. Closes **FR-005**
- [x] T032 [US3] Write `tests/worked_examples/test_monthly_cap.py` — the **G3** example: a contribution over the cap deploys exactly the cap, the excess is handled by the declared fallback, and **every occurrence** appears with date, amount and reason. Closes **G3**, **FR-013**, **SC-007**
- [x] T033 [P] [US3] Write `tests/invariants/test_no_silent_clamping.py` — fees exceeding the amount are reported, `arrived` is not floored at zero, `fraction` may exceed 1.0, and total fees recorded equal total fees applied. Closes **B13**, **FR-005**, **SC-013**
- [x] T034 [P] [US3] Write `tests/unit/test_route_unusable.py` — below a minimum, over a maximum, or closed on the date: each reported with the binding constraint named and the shortfall, never silently rounded or dropped. Closes **FR-014**

**Checkpoint**: commit.

---

## Phase 6: User Story 4 — See what changes when the war ends (P2)

**Goal**: two regimes, a transition date stated as an assumption, and the cost difference.

- [ ] T035 [US4] Write `tests/worked_examples/test_regime_transition.py` — the **G4** example: contributions before and after the date use different route sets, and round-trip cost drops by exactly the hand-computed difference. Closes **G4**, **SC-009**. Must fail first
- [ ] T036 [US4] Implement regime selection — `Regime`, `RegimeTransition` with `is_assumption: Literal[True]` (a `bool` could be set false; the type admits one value), and the free function selecting a route set by date. Closes **FR-019**
- [ ] T037 [P] [US4] Write `tests/unit/test_transition_is_an_assumption.py` — the transition date is reported as a stated assumption with its rationale, never as a known fact, and a regime cannot be expressed as a leg availability window (research.md D8 — a fact and an assumption must stay distinguishable). Closes **FR-020**

**Checkpoint**: commit.

---

## Phase 7: User Story 5 — Add a venue or corridor without touching the engine (P3)

**Goal**: declarations, loud failure, and data-only extensibility.

- [ ] T038 [US5] Extend `src/terezy/data/declarations/schema.py` — pydantic models for routes, legs, channels, streams and observation kinds per `contracts/declaration-schema.md`. `extra="forbid"`, `strict=True`, **zero defaults**
- [ ] T039 [US5] Extend `src/terezy/data/declarations/loader.py` — `_pct` fields divided by 100 **exactly once** here; dates parsed here; `SourceRef` ids on the established `directory/file#table` scheme
- [ ] T040 [US5] Extend `src/terezy/data/declarations/resolver.py` — the cross-file pass pydantic cannot do: **leg chaining** by venue and currency, first leg at `origin` and last at `destination`, duplicate `(provider × currency path × venue)` triples, `partner_route` resolution (dangling id refused, an inbound route as a partner refused, **exit `origin` must be the inbound `destination`**, **exit must end holding the base currency**), **`capacity_pool` cap agreement across legs**, kind resolution, venue and channel references. Closes **FR-021**, **FR-023**, **FR-024**, **FR-027**
- [ ] T041 [P] [US5] Create `data/observation_kinds.toml` — `p2p_premium`, `bank_fee_schedule`, `regulatory_limit`, `bond_terms`, `tax_rule`, each with `staleness_days` and a required `note`
- [ ] T042 [P] [US5] Create `data/channels/uah_usd.toml` — a `p2p` channel in premium form and a `card` channel in bps form, both sides declared, all values marked **SYNTHETIC FIXTURE** with empty `verified_on`
- [ ] T043 [US5] Create `data/routes/inzhur_direct.toml`, `monobank_to_binance_p2p.toml`, `binance_p2p_to_monobank.toml`, `coinbase_to_ibkr.toml` — inbound and exit **in pairs** (FR-027): the zero-cost domestic path, a P2P path both ways, and one route deliberately left with `partner_route = null` so `ExitCostUnknown` has a fixture. Also a second P2P variant differing **only** in conversion count, which is what closes **G5**
- [ ] T044 [P] [US5] Create `data/streams/owner-001.toml` — the UAH salary and the USD contract income, amounts `0.0` (the honest placeholder; §11 item 3 records that the real figures are unstated)
- [ ] T045 [US5] **MIGRATION, atomic**: every existing declaration from feature 001 gains a `kind`; `scripts/check_provenance.py` gains `channels` to `SOURCED_DIRS`, requires a declared `kind` on every sourced table, and gains the new structural keys. One commit — a half-applied `kind` requirement makes the whole gate red. Closes **FR-022**, **FR-028**
- [ ] T046 [US5] Write `tests/contract/test_route_declaration_loading.py` — one case per row of the enforced-rules table in `contracts/declaration-schema.md`, including every cross-file case. **No case may substitute a default.** Closes **FR-024**, **SC-011**
- [ ] T047 [US5] Write `tests/contract/test_route_data_only.py` — a new provider, venue and corridor rank with **zero** source lines changed; and the four plugin interfaces are **still four**, so a leg kind cannot have drifted into a fifth. Closes **SC-010**
- [ ] T048 [P] [US5] Confirm `uv run python scripts/check_provenance.py` reports **zero errors** on all new and migrated files, with empty-`verified_on` warnings expected

**Checkpoint**: commit.

---

## Phase 8: Polish and cross-cutting

- [ ] T049 Write `tests/golden/test_ramp_comparison.py` with a checked-in artefact — the full ramp comparison from declarations, digest plus readable rendering, same update procedure as feature 001's golden. Extends **K3**
- [ ] T050 [P] Extend `docs/METHODOLOGY.md` — the premium-to-percentage formula, round-trip composition from a declared exit route, the two-sided channel convention and why no mid-rate is used, the staleness rule and its as-of date, and the capacity accumulator
- [ ] T051 [P] Flip the eight rows in `docs/REQUIRED_TESTS.md` with test paths: **G1, G2, G3, G4, G5, G6, F5, B13**
- [ ] T052 **REVIEW (manual, no gate can do this)**: walk every site producing a figure and confirm provenance **and** the staleness verdict survive. Every route number here is unverified at first run, so this feature leans on the marks harder than any so far. Check especially `money.scale_sourced` at each declared-rate application
- [ ] T053 **REVIEW (manual, no gate can do this)**: grep the diff for `pytest.approx`, `math.isclose`, and numeric literals used as bounds. Every tolerance must be the imported one
- [ ] T054 Run the full gate set: `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `check_provenance.py`, `pytest --cov` at the 90% floor. All blocking

---

## Dependencies

```
Phase 1 (setup)
   ↓
Phase 2 (foundational) — STRICTLY SEQUENTIAL, one agent, T004→T016
   ↓
   ├───────────────┬───────────────┬───────────────┐
   ↓               ↓               ↓               ↓
Phase 3 (US1)   Phase 4 (US2)   Phase 5 (US3)   Phase 7 (US5)
   │               │               │               │
   │  needs T019 ──┤  needs T016   │  needs T019   │  independent of US1–US4
   ↓               ↓               ↓               ↓
   └───────────────┴──── Phase 6 (US4), needs T019 ┘
                        ↓
                  Phase 8 (polish)
```

**Honestly stated:**

- **US1** depends only on Phase 2.
- **US2** needs `cost_one` (T016) — a stream comparison is two costings.
- **US3** needs `rank` (T019) only for its fallback reporting; the capacity accumulator
  itself depends on Phase 2 alone.
- **US4** needs `rank` (T019) to show the cost difference across a transition.
- **US5** is **independent of US1–US4** and can run concurrently with all of them. The loader
  builds the same records the tests construct by hand — same pattern as feature 001.

## Parallel opportunities

**Within Phase 2**: none by design.

**After Phase 2**, three agents:

| Agent | Tasks |
|---|---|
| A | Phase 3 (US1) → Phase 4 (US2) → Phase 6 (US4) |
| B | Phase 5 (US3) — capacity, execute, caps, clamping |
| C | Phase 7 (US5) — the whole declaration layer, T038–T048 |

**Caution on agent B and C overlap**: T045 is a migration touching
`scripts/check_provenance.py` and feature 001's data files. It must land atomically and
nothing else should be mid-edit in `data/` when it does.

## MVP scope

**Phases 1 + 2 + 3** — 22 tasks. That computes the §4.3.1 finding, which is the entire point
of the feature and the number that makes 15.5% a hurdle rather than a fact.

Phase 4 is P1 alongside it: a per-destination cost is not merely less useful than a
per-stream one, it is **wrong**, and shipping Story 1 without Story 2 would invite exactly
the blended figure FR-008 exists to forbid.

## Task count

| Phase | Tasks | Closes |
|---|---|---|
| 1 — Setup | 3 | — |
| 2 — Foundational | 13 | FR-001–005, FR-008, FR-010, FR-011, FR-025, FR-026, FR-028, FR-030 |
| 3 — US1 (MVP) | 6 | G2, G6, SC-001–005, SC-014, SC-016, FR-016, FR-018, FR-029 |
| 4 — US2 | 5 | G1, SC-003, SC-006, FR-006, FR-007, FR-009 |
| 5 — US3 | 7 | G3, B13, FR-012–015, SC-007, SC-013 |
| 6 — US4 | 3 | G4, SC-009, FR-019, FR-020 |
| 7 — US5 | 11 | SC-010, SC-011, FR-021–024, FR-027 |
| 8 — Polish | 6 | the eight rows, methodology, manual reviews |
| **Total** | **54** | |

**G5** (two route variants differing only in conversion count) and **F5** (channel selection
visible in attribution) are closed by fixtures in T043 exercised through T019 and T021 —
they need declared data rather than their own code, which is why they have no dedicated
implementation task.
