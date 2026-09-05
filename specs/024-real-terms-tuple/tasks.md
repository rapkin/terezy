# Tasks: Real terms on a tuple

**Feature**: `024-real-terms-tuple` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before its
field — failing with `AttributeError` or `TypeError` — counts. Every phase opens with its checks.

`[P]` marks a task touching files no incomplete task touches.

---

## Phase 1: One window rule (foundational — blocks the figure)

**Goal**: the span a real figure is deflated over is derived in one place, and the projection's
existing goldens prove the move changed nothing.

- [ ] T001 Write `tests/unit/test_deflation_window.py` by hand: money leaving on the last day of a month and on the first, each with a final flow mid-month, pin both boundaries — the first month is the one *after* the money left, the last is the final flow's. Fails with `ImportError`.
- [ ] T002 Add `deflation_window(money_left_on, last_flow_on) -> Window` to `src/terezy/core/inflation/series.py`, carrying the two boundary decisions and their reasons (FR-005). The parameter is *the date the money left*, not the purchase date: a tuple's outlay precedes its purchase by the way in's declared latency, and naming the purchase would start a tuple's window a month early on an outlay made at a month end.
- [ ] T003 Collapse `src/terezy/core/results/project.py::_deflation_window` into a call to it, passing `(holding.purchased_on, last contractual flow)`, and move its docstring's reasoning with it in the widened wording, leaving no second statement of the rule.

**Checkpoint**: gates green; `tests/golden/ovdp_synthetic_a.golden.txt` byte-identical — the move is a refactor and must prove it. Commit.

---

## Phase 2: The deflators reach the evaluation (foundational)

**Goal**: the declared series and the declared belief are readable where a tuple is evaluated,
and the manifest records which of each was in force.

- [ ] T004 Write `tests/unit/test_answer_manifest.py`'s new case: an answered question's manifest names `data/cpi/ua.toml` under `cpi_series` and `data/scenarios/inflation/owner-001.toml` under `inflation_assumption` (FR-012). Fails.
- [ ] T005 Add `cpi: Mapping[str, CpiSeries]` and `inflation: InflationAssumption | None` to `Registries` in `src/terezy/core/decision/tuple_outcome.py`, both without a default — an absent deflator is a reported reason and a caller must say so (FR-013). The mapping, not one series: `InflationDeclarations.series` is keyed by declared id and nothing yet decides which one a figure is real against.
- [ ] T005a Widen `Deflation.series` in `src/terezy/core/results/hurdle.py` from `CpiSeries | None` to `Mapping[str, CpiSeries]`, and add the named builder `deflating_series(series) -> CpiSeries | RealTermsUnavailable` beside the other reason functions: exactly one is that one, none reuses `no_series_declared()`, more than one refuses naming the ids it could not choose between (FR-013a). Call it from `_realized`, so the ambiguity is decided *after* `real_terms` has hoisted the refusals that apply to both halves (FR-013b). No new record type, so no new wire tag.
- [ ] T005b Update the projection's caller in `src/terezy/core/results/project.py` and `tests/golden/test_end_to_end_ovdp.py` to pass the mapping instead of indexing it by the hard-coded `CPI_SERIES_ID`; `ovdp_synthetic_a.golden.txt` must stay byte-identical, which is what proves the widening changed no figure.
- [ ] T006 Fill both at the single `Registries(...)` construction in `src/terezy/data/declarations/resolver.py` from `inflation_from_data_root`, and carry the whole `InflationDeclarations` record on `AnswerDeclarations` beside `question_files` — `manifest.inflation_input_refs` takes that record and reads all four of its fields, so loose paths would neither satisfy it nor be one fact in one place.
- [ ] T007 Read it there from `manifest.answer_input_refs` in `src/terezy/data/manifest.py`, which already receives the `AnswerDeclarations`, through the existing `inflation_input_refs`. `src/terezy/api/answer.py` is **not** edited: `of_answer` already takes the record, and a second route for one fact is the duplication T006 exists to avoid. No new `InputKind` member — both already exist.

**Checkpoint**: gates green; no figure moved, no golden moved. Commit.

---

## Phase 3: The figure (US1 — the worked example)

**Goal**: every evaluated candidate carries the hurdle's real record, filled by the hurdle's
function.

- [ ] T008 [US1] Write `tests/worked_examples/test_real_terms_on_a_tuple.py` with the spec's arithmetic hand-computed: UA4000236228 over the twelve-month horizon, span 2026-09-01..2027-03-13, window 2026-10..2027-03, nominal `0.14949567241454964`, assumed real `0.044996065831408805`, and the multiplication back to `1.1494956724145498` (SC-001). Fails on a missing field.
- [ ] T009 [US1] Add to the same module the realized half's refusal: it names all six months of *its own* window, and a candidate running to 2027-09 names a different set (SC-002). Read the spans off the answer rather than retyping them.
- [ ] T010 [US1] Add `real: RealTerms` to `TupleOutcome` in `src/terezy/core/results/tuple.py`, keyword-only and with no default (FR-001).
- [ ] T011 [US1] Fill it at the single `TupleOutcome(...)` construction in `src/terezy/core/decision/tuple_outcome.py` by calling `hurdle.real_terms` with the outcome's own provenance and staleness, the window from `span`, and `nominal=` the `implied_rate` where it is a `NominalRate` and `None` where it is not (FR-002, FR-003, FR-006). Build the `Deflation` from `span` and the registries' two deflators and the `Ageing` from `registries.kinds` and the run's `as_of` — and **decide no refusal here**: every one of them belongs inside `real_terms`, which stays the only place a slot is filled (FR-013b).
- [ ] T012 [US1] Write `tests/unit/test_real_terms_refusals.py`: no belief declared, no series declared, two series and neither named, a `RateNotComparable` rate, and a span with no elapsed month — five refusals, each asserted by its reason naming what is missing, and none of them a new record type (FR-008, FR-009, FR-013a, SC-004). UA4000235865 over the owner's one-month horizon is the shipped instance of the last.

**Checkpoint**: gates green. No golden moves here — `test_the_answer.py::_render` prints `reaches` and not the rate, and `canonical.of_outcome` does not yet carry the slot. Commit.

---

## Phase 4: Nothing moved that should not (US2)

**Goal**: the field is added and no order, amount or ranking input changes.

- [ ] T013 [US2] Write `tests/contract/test_the_real_figure_moves_no_order.py`: two answers differing only in the declared belief agree field by field on every ranking, `reaches`, `implied_rate` and refusal, and differ only in their real slots (SC-003, US2 scenario 1).
- [ ] T014 [US2] Add to it the assertion that `tests/golden/candidate_set.golden.txt` is byte-identical and its recorded digest unchanged — the digest covers the key, the amount and the nominal rate, and this feature moves none of the three (FR-018, US2 scenario 2).
- [ ] T015 [US2] Confirm by reading the call graph that no module under `src/terezy/core/decision/` other than the construction site names the new field; `compare.py` and `candidates.py` must not learn it exists (FR-017).

**Checkpoint**: gates green. Commit.

---

## Phase 5: The exclusion the figure retires (US3)

**Goal**: the answer stops claiming every rate it reports is nominal, and states instead the
narrower thing that stayed true.

- [ ] T016 [US3] In `tests/contract/test_the_answer_says_only_what_it_computed.py`: invert `test_no_real_terms_figure_appears_anywhere_in_the_result` — the same walk, asserting that every evaluated outcome carries a real slot — shrink `ANSWER_WIDE` to one member and rename it and `test_the_two_answer_wide_exclusions_are_always_stated` so neither says *two* about one, and drop `verb.REAL_TERMS_SUPPLIED_BY` from `_vocabulary`, which reads it by name and breaks with an `AttributeError` the moment T017 lands (SC-006). Fails.
- [ ] T017 [US3] Delete `Exclusion.NO_REAL_TERMS_FIGURE` with its docstring from `src/terezy/core/results/answer.py`, and `REAL_TERMS_SUPPLIED_BY` with its entry in `_answer_wide_excludes` from `src/terezy/core/decision/answer.py` (FR-014).
- [ ] T018 [US3] Replace `EXCLUDES`'s *inflation (every figure here is nominal)* in `src/terezy/core/results/tuple.py` with the claim that survives — the outlay and what reaches a spendable endpoint stay nominal, and only the rate has a real counterpart — and leave `ACCOUNTS_FOR` alone (FR-015, FR-016).
- [ ] T019 [US3] Delete the sentence in `TupleOutcome.implied_rate`'s docstring that leaves inflation to `EXCLUDES`, and any neighbouring claim the field falsifies. Deleted, not rewritten.

**Checkpoint**: `the_answer.golden.txt`'s two `[excludes]` lines become one, so the golden is red until T021. Run the gates, land T020 and T021 in the same commit as this phase, and quote the changed lines.

---

## Phase 6: The digest, the schema and the prose

- [ ] T020 Add `of_real_terms(value.real)` to `canonical.of_outcome` in `src/terezy/core/results/canonical.py`, tagged so a real rate and its absence cannot digest alike (FR-019).
- [ ] T021 Regenerate `tests/golden/the_answer.golden.txt`, read the diff, and quote the changed lines in the commit message. **Expect exactly two kinds of change**: the `[digest]` line, because `of_outcome` now carries the slot, and `[excludes] no_real_terms_figure` disappearing. No `evaluated` line moves — `_render` prints the amount and not the rate — so a diff larger than that means something unplanned happened (SC-007).
- [ ] T022 [P] Re-run `tests/contract/test_tags_and_unions.py` over the three newly reachable records — `rates.RealRate`, `rates.RealTermsUnavailable`, `hurdle.RealTerms` — and add an `OVERRIDES` entry only if it goes red (FR-020).
- [ ] T023 [P] Regenerate the OpenAPI document under its existing gate (`scripts/generate_openapi.py`) and confirm zero files under `web/` change: the client's types are generated from the document and are not committed (SC-009).
- [ ] T024 Add §27.7 to `docs/METHODOLOGY.md` — which nominal figure a tuple deflates, over which window, how the series is chosen, and why nothing ranks on it — and add one cross-reference to it from §29.5. §29.5's *"two figures"* is the amount and the rate and stays true; do not rewrite it (FR-021).
- [ ] T025 Add this feature's section to `docs/REQUIRED_TESTS.md` recording that **no row flips**: F4 stays open on the display switch, and this feature adds a second consumer of its UA half. Flip `024-real-terms-tuple` to `done` in `specs/features.toml`.
- [ ] T026 Run the full gate list — `ruff check` + `ruff format --check .`, `mypy`, `lint-imports`, `pytest --cov`, `check_provenance.py`, `check_prose_budget.py`, `check_enumerations.py`, `check_methodology_refs.py`.

---

## Dependencies

Phases 1 and 2 are independent of each other and both block Phase 3 — the figure needs the window
rule and the deflators. Phase 4 needs Phase 3 (there is no field to prove inert before it exists)
and is deliberately *before* Phase 5, so the ranking is proved unmoved on a diff that has not yet
touched the exclusion set. Phase 5 needs Phase 3 for the same reason its test inverts rather than
changes, and it turns the answer golden red — so T020 and T021 land with it rather than after it,
which is the one place a phase boundary and a commit boundary do not coincide.

## Independent test criteria

- **US1** — the spec's worked example reproduces to the imported project tolerance, and the
  realized half names the months of its own window.
- **US2** — two answers differing only in the belief agree on every ranking input, and the
  candidate golden is byte-identical.
- **US3** — no answer states a real-terms exclusion, and no `TupleOutcome` claims every figure it
  carries is nominal.

## MVP scope

Phases 1–3: the window rule, the deflators and the figure. That alone answers the owner's
«по інфляції — так», with the exclusion still stated beside it — honest, if redundant. Phase 4
proves nothing else moved and Phases 5 and 6 stop the answer contradicting itself; none is
optional.
