# Tasks: the full tuple

**Feature**: `010-full-tuple` | **Date**: 2026-08-23 | **Plan**: [plan.md](./plan.md)

Order follows plan.md's Phase 2 note: **the chaining rule and its refusals first**, because
that is the part that can be silently wrong; then the outcome record; then the comparison;
then **H1 last**, because it is the test of everything before it. Tests before implementation
in every group.

Two findings from Phase 0 reading are recorded here because they change the task list:

- **F1 — nothing declares where an instrument is bought.** `InstrumentDeclaration` and
  `FundDeclaration` carry a currency and no venue; `IncomeStream.arrives_at` is the only
  non-route declaration in the repository that names one. So FR-004's seam has no venue to
  anchor against, and the join would be able to check only the currency — which is feature
  004's unanchored-chain defect, at two more seams. Closing it is a new declaration
  (Phase 1), not a new branch in the join.
- **F2 — a bond declares no purchase price.** `BondTerms` gives a face value; `Holding.cost`
  is *stated* by the caller. A join buying with an arriving amount needs a price per unit,
  and a fund has one (`nav_per_unit` × the declared entry markup) while a bond does not. The
  price is a venue quote, so it lands in the same access declaration.

Both are declared in a **new** `data/access/` directory rather than by widening
`data/instruments/*.toml`, for a reason that is not taste: the golden result file records the
sha256 of every instrument declaration, so a key added to a shipped instrument file moves a
golden this feature must not move. The long-term home is recorded in METHODOLOGY.

---

## Phase 1 — the access declaration (F1, F2)

- [x] **T001** `tests/contract/test_access_declaration_loading.py` — FR-022 for the new
      declaration kind: unknown instrument id, unknown venue, a venue that cannot hold the
      instrument's currency, a price on a fund (which declares its own), no price on a bond,
      a duplicate entry across two files, an unknown field, malformed TOML. Each names file
      and field; nothing defaults.
- [x] **T002** `src/terezy/core/instruments/access.py` — `InstrumentAccess`, a frozen record:
      `instrument_id`, `bought_at`, `proceeds_to`, `quote: VenueQuote | None`
      (the price and the observation kind it ages under, together), `risk_class`. No behaviour.
- [x] **T003** `data/declarations/{schema,loader,resolver}.py` — a `010-full-tuple` section
      appended to each, matching the 006 banner shape. `AccessTable`/`AccessFile`,
      `access_from_file`, `_check_access`, `AccessDeclarations`, `Registries`,
      `tuple_from_data_root`.
- [x] **T004** `data/access/instruments.toml` — the five shipped instruments.
- [x] **T005** `scripts/check_provenance.py` — `access` joins `SOURCED_DIRS` (the gate is
      fail-closed; an unlisted directory is an error). `data/README.md` gains the directory.

## Phase 2 — costing the way out from an amount that is not the inbound arrival

- [x] **T010** `tests/unit/test_way_out_cost.py` — `cost_exit` hand-checked on a fee-bearing
      chain; the head anchor refuses a chain that does not depart from where the money is;
      a closed exit segment; a chain that will not carry the amount.
- [x] **T011** `core/results/ramp.py` — `WayOutCost` under a `010-full-tuple` banner.
      Unrelated to `OneWayCost` and `RoundTripCost` by design.
- [x] **T012** `core/routes/cost.py` — `cost_exit` under a `010-full-tuple` banner. One fold,
      002's, over the exit chain, from a stated junction. No new arithmetic.

## Phase 3 — the records

- [x] **T020** `core/results/tuple.py` — `Tuple`, `TupleOutcome`, `PartContribution`,
      `Arrival`, `UndeployedCash`, `Comparison`, `BenchmarkUnavailable`, `Continuation`, and
      the typed refusals.

## Phase 4 — the chaining rule and its refusals (the part that can be silently wrong)

- [x] **T030** `tests/unit/test_chaining_refusals.py` — a deliberate mismatch at each seam,
      in each of its two halves: route-in venue, route-in currency, proceeds venue, proceeds
      currency. Every refusal names **both** sides.
- [x] **T031** `core/decision/tuple_outcome.py` — `evaluate`.

## Phase 5 — the number the feature exists for

- [x] **T040** `tests/worked_examples/test_full_round_trip.py` — SC-001: ramp in, purchase,
      lifecycle, tax, instrument exit, ramp out, hand-computed end to end.

## Phase 6 — the comparison, the benchmark, the ties

- [x] **T050** `tests/contract/test_the_hurdle_is_a_tuple.py` — SC-002, SC-003: the benchmark
      is the same object the ranking holds, asserted with `is`; and the tuple rate reproduces
      001's figure exactly over routes that cost and delay nothing.
- [x] **T051** `tests/unit/test_ties_and_ranking.py` — SC-008.
- [x] **T052** `core/decision/compare.py` — `compare`.

## Phase 7 — keying, feasibility, marks, scope

- [x] **T060** `tests/unit/test_two_streams_two_outcomes.py` — SC-004.
- [x] **T061** `tests/unit/test_infeasible_tuples.py` — SC-010.
- [x] **T061a** `tests/unit/test_rate_and_horizon_boundaries.py` — the four typed absences:
      no rate across two currencies (FR-024), no span (FR-025), no tax base this engine can
      strike (research.md D10), no conventional series. Added after Phase 4: the refusal
      battery covers the *missing declaration* half of FR-006 and these are the *computed and
      still unavailable* half, which is a different claim and a different type.
- [x] **T062** `tests/contract/test_marks_survive_the_join.py` — SC-007.
- [x] **T063** `tests/contract/test_every_figure_states_its_scope.py` — SC-009.
- [x] **T064** `tests/unit/test_tuple_refusals.py` — SC-005, the battery over all four parts.

## Phase 8 — H1

- [x] **T070** `tests/contract/test_h1_data_only.py` — SC-006. A new instrument, route, tax
      class and jurisdiction in data only, through the full pipeline, into the comparison,
      with a scan proving no shipped module names any of them.

## Phase 9 — documentation and the ledger of what is covered

- [x] **T080** `docs/METHODOLOGY.md` §28, `data/README.md`'s directory table, and §28
      "Where to look next" renumbered to §29.
- [x] **T081** `docs/REQUIRED_TESTS.md` — H1 flipped with its path, plus the reinforcement
      table for the rows this feature strengthens without closing.
- [x] **T082** `specs/features.toml` — `010-full-tuple` to `in-progress` (the landing change
      flips it to `done`; that is the owner's).
