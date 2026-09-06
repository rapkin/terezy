# Tasks: Cash as a declared instrument

**Feature**: `023-cash-instrument` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before its
module — failing with `ImportError` — counts. Every phase opens with its checks.

`[P]` marks a task touching files no incomplete task touches.

---

## Phase 1: The class (foundational — blocks everything)

**Goal**: `cash_balance` is a declaration kind that loads, refuses by name, can carry a run plan,
and reaches nothing else yet.

- [ ] T001 Write `tests/worked_examples/test_cash_reaches_the_amount.py` with the spec's arithmetic hand-computed: 50 000.00 UAH in, 50 000.00 UAH reached on 2026-10-01, 2026-12-01 and 2027-09-01, implied rate 0.00 %, round trip 0.00 UAH both legs. Fails with `ImportError`. **This is the first task and it stays red until Phase 5.**
- [ ] T002 [P] Write `tests/unit/test_cash_declaration_loading.py`: a rate that is not exactly zero, a missing rate, an `[access.price]` and an `[access.resale_price]` each fail at load naming the file and the field, and the rate refusal says a balance that pays something is a deposit (FR-003, FR-005).
- [ ] T003 [P] Write `tests/invariants/test_cash_invariants.py`: over generated amounts, horizons and **every** convention in `conventions.DAY_COUNT_FNS`, `reaches == outlay` and the implied rate is zero, both within the imported project tolerance — the rate is bisected to a root, so an exact-zero assertion would fail for a reason unrelated to the claim (SC-006, FR-010, FR-019). Fails with `ImportError`.
- [ ] T004 Add `core/instruments/cash.py`: `CashDeclaration` (id, name, class, currency, synthetic flag, groups, the rate and its provenance), `CashAssumptions` carrying no fields, and the class's day-count constant (FR-002, FR-010, FR-011).
- [ ] T005 Add `CASH_BALANCE` to `core/instruments/registry.py` and to `DECLARATION_KINDS`; leave `REGISTRY` at two members and state, once, that a balance produces no event stream (FR-001).
- [ ] T006 Widen the plan vocabulary so a cash subject can carry one (FR-002a): the declared plan kind and its refusal message in the question loader, the question schema's plan table, `InstrumentPlan` in `core/results/tuple.py`, and the canonical rendering that matches over it with `assert_never`. Without this `CashAssumptions` has no producer and the question file cannot load.
- [ ] T007 Add the schema model and loader in `src/terezy/data/declarations/`, the `LOADERS_BY_KIND` entry, the `resolve()` branch, the third mapping on the resolved declarations, the `_check_access_price` third answer and the `declared_class_of` remedy text (FR-003, FR-005, FR-006, FR-008a).
- [ ] T008 [P] Declare the observation kind the rate ages under in `data/observation_kinds.toml`, with its `staleness_days` and the reason for it, separated from `bank_fee_schedule` on the same ground `venue_terms` is (FR-004).
- [ ] T009 [P] Widen `tests/contract/test_data_only_extensibility.py`: `DECLARATION_KINDS` gains a member and `REGISTRY` does not.

**Checkpoint**: gates green; T002 passes, T001 and T003 still fail on the missing projection. Commit.

---

## Phase 2: The identity way in

**Goal**: a tuple whose way in is *there is nothing to do* is representable and is checked.

- [ ] T010 Write `tests/unit/test_entry_by_identity.py`: the entry is legal exactly where the stream's arrival venue and currency equal the instrument's buying venue and currency; asserted for a pair that does not satisfy it and refused with the seam named (FR-013, SC-009).
- [ ] T011 [P] Write `tests/unit/test_identity_entry_costs_nothing.py`: zero cost, zero latency, purchase on the horizon's first day, and a **recorded zero** `ramp_in` contribution rather than a missing part (FR-014).
- [ ] T012 Add `EntryByIdentity` and its sentinel to `core/routes/path.py`, beside `ExitByIdentity` and with the same argument against `None` and against an empty chain (FR-012).
- [ ] T013 Widen `Tuple.route_in` in `core/results/tuple.py` to admit it (FR-012).
- [ ] T014 Handle the sentinel at every site `mypy` then names — the segment lists in `tuple_outcome`, the funding-stream guard, the destination-id read, the monthly-cap check, `_route_ids_of` and `_undeclared_routes` in `candidates.py`, `core/results/ramp.py`, and the CLI's candidate-id read. Each is a decision about what *no route at all* means there, not a cast.
- [ ] T015 Give the entry its own rendered name in `core/results/canonical.py`, used by both the ordering key and the record the answer digest is taken over; never a route id, on that module's own rule (FR-017).
- [ ] T016 Build the zero-cost inbound walk in `core/routes/cost.py`, on the pattern `_IDENTITY_ROUTE` sets for the far end (FR-014, FR-020).
- [ ] T017 Check the claim at the join in `core/decision/tuple_outcome.py`, refusing with the seam named where it does not hold (FR-013).
- [ ] T018 Construct it in `core/decision/candidates.py::_walk` for such a pair instead of calling `compose` (FR-015). The short-circuit MUST NOT bypass the composition bound: `compose` checks `max_segments < 1` **before** the arrival comparison, so a bound admitting nothing must still refuse the whole question — a registry whose pairs are all identity, which is the shape SC-004 builds, would otherwise yield candidates from a bound that admits none.

**Checkpoint**: gates green. Commit.

---

## Phase 3: The retirement

**Goal**: the column member that existed to make the gap visible goes with the gap — in one
commit, because two of its consumers are `contract` tests.

- [ ] T019 Delete `NothingNeedsToConnect` from `core/results/candidates.py`, narrow `NoCandidateReason`, and move every consumer in the same change: the match arm and import in `src/terezy/cli/main.py`, the closed-set assertions in `tests/unit/test_candidate_records.py` and `tests/contract/test_tags_and_unions.py`, the renderer in `tests/golden/test_candidate_set.py`, and the whole `TestMoneyAlreadyWhereItWasWantedIsNotAGapInTheRegistry` class in `tests/unit/test_no_candidate_column.py`, whose docstring is the other live claim that the gap is open (FR-016).
- [ ] T020 Turn `candidates._about_the_question`'s *already arrived* arm into a `raise` naming the invariant that makes it unreachable — enumeration short-circuits on the same venue and currency `compose` compares. The match stays exhaustive over the closed enum; the arm is not deleted (FR-016a).
- [ ] T021 Confirm `core/routes/compose.py::_refusal` is unchanged, and that the remaining half of `test_no_candidate_column.py` still catches a rewritten `NothingConnects` reason (FR-015).

**Checkpoint**: gates green, `pytest -m "contract or invariant"` included. Commit.

---

## Phase 4: The projection and the outcome arm

**Goal**: cash produces a purchase, a release and a rate, and nothing skips it silently.

- [ ] T022 Add `core/results/cash.py::project_cash`: a purchase event on the horizon's first day and a release of the same amount on its last, so the span is the horizon and `reaches` is not summed from an empty arrival list (FR-018).
- [ ] T023 Add the third mapping to `Registries` and the third lookup to `_considered` and `_declaration` — an id in neither existing map is skipped with no refusal, so without this the declaration disappears from enumeration silently (FR-008a).
- [ ] T024 Add the third arm to `core/decision/tuple_outcome.py::_project` and to `_plan_for`, on `(CashDeclaration, CashAssumptions)` (FR-002).
- [ ] T025 Widen the seven matches over `Declared` that T024 did not — `currency_of`, `_price_for`, `_minimum_ticket`, `_min_unit`, `_declaration_provenance`, `_day_count_of` and `_excludes_of`. `_price_for` returns the identity price; `_excludes_of` returns the shared floor **unchanged**, dropping no member of it (FR-005, FR-021).
- [ ] T025a Widen every function taking the **projection** union that a third projection type makes non-exhaustive; `mypy` names them, and `_projection_provenance` among them carries the rate's mark, which is where a bond's terms already arrive.
- [ ] T026 Charge zero tax with the reason in `accounts_for` — proceeds equal basis — and name no tax class anywhere (FR-009).
- [ ] T027 Make *no increment* representable in `_min_unit`, which returns a bare `float` today and so cannot express it, and size the holding as the whole arrived amount with **no** undeployed-cash record. Without this the cash arm is given an increment of 1.0 to silence the match, and a non-integral amount strands its fractional part — which T003's generated amounts would find as `reaches != outlay` (FR-011).
- [ ] T028 Add the fourth arm to the manifest's input references and its provenance reader, so the cash declaration's file is named by every run that reads it (FR-022).
- [ ] T029 Confirm `_standing` does not degrade on a journey whose way out is `ExitByIdentity` and whose way in now is too (FR-020).

**Checkpoint**: gates green; T003 passes. Commit.

---

## Phase 5: The data

**Goal**: the owner's first word resolves.

- [ ] T030 Add `cash` to `data/groups.toml` (FR-007).
- [ ] T031 Write `data/instruments/cash_uah_monobank.toml`: the identity table, `groups = ["cash"]`, and `[instrument.balance]` with `rate_pct = 0.0` and the four citation keys under the kind T008 declared. `verified_on` is empty and the header says why (FR-004, owner verification task 1).
- [ ] T032 Add the access row to `data/access/instruments.toml`: `bought_at` and `proceeds_to` both `monobank_uah`, a risk-class label, no price table (FR-005, FR-006).
- [ ] T033 Add the `cash` run plan to `data/questions/fifty-thousand.toml`; its header is T039's (FR-024).

**Checkpoint**: T001 passes. Both goldens now move. Commit.

---

## Phase 6: The counts and the prose

**Goal**: every figure this feature moved is re-measured rather than guessed.

- [ ] T034 Regenerate `tests/golden/the_answer.golden.txt` and `tests/golden/candidate_set.golden.txt` deliberately, read the diffs, and quote the changed lines in the commit message. Update the `"  ranked 21"` literal in `tests/golden/test_the_answer.py` to what was **measured** (FR-025).
- [ ] T035 Re-run `tests/contract/test_marks_survive_the_join.py` against the new candidate, whose route in contributes no mark, and `tests/contract/test_no_layer_knows_the_form.py` for the new class string (SC-010).
- [ ] T036 [P] Add the cash projection to §29 of `docs/METHODOLOGY.md` (FR-027).
- [ ] T037 [P] Record in `docs/REQUIRED_TESTS.md` I4 what this closes — the row's own subject now exists and is scored — and what it does not: I4 wants a strategy shortlist and that is the decision layer's.
- [ ] T038 [P] Delete the prose the plan names as falsified, including the two sentences in `candidates.py` that say a `Tuple` cannot exist without a `route_in` and that a refused pair lands in `NothingNeedsToConnect`, and drop `zero-hop-way-in` from the list of gaps in `specs/019-decision-layer/spec.md` — an unbuilt spec, so a live instruction rather than a record.
- [ ] T039 [P] Cut `data/questions/fifty-thousand.toml`'s heading and paragraph about the words that resolve to nothing down to `btc` alone. **Rewritten, not deleted**: the `btc` half stays true and SC-003 rests on it.
- [ ] T040 Flip `023-cash-instrument` to `done` in `specs/features.toml` in the landing change.
- [ ] T041 Run the full gate list: `ruff`, `mypy`, `lint-imports`, `pytest --cov`, `check_provenance.py`, `check_prose_budget.py`, `check_enumerations.py`.

**Checkpoint**: condense, then review. Land by `--no-ff` merge.

---

## Dependencies

Phase 1 blocks everything. Phase 2 is independent of Phase 1 except for T018, which needs the
access record's shape. Phase 3 needs Phase 2. Phase 4 needs Phases 1 and 2. Phase 5 needs Phases
1 and 4. Phase 6 needs all of them.

Within a phase, every task marked `[P]` touches files no incomplete task touches; the rest are
sequential because they edit the same modules. T019 is deliberately one task and not six: two of
its consumers assert the union is closed, so a half-done narrowing is a red compliance suite.

## Notes

**T001 stays red for four phases, and that is the shape.** It is the only hand-computed
arithmetic in the feature, and every term of it — the two identity legs, the zero rate, the
absent tax, the release at the horizon's end — is a separate claim that lands in a different
phase. A test that went green in Phase 1 would be asserting something smaller than the feature.

**No figure is hand-computed except the worked example's.** Every count the goldens hold is
measured by regenerating them; a figure typed in from expectation is the defect Principle V's
"a golden is evidence, never a freeze" exists to prevent, read from the other end.
