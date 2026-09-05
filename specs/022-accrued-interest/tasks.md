# Tasks: Accrued interest on a carried quotation

**Feature**: `022-accrued-interest` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before
its module — failing with `ImportError` — counts. Every phase opens with its checks.

`[P]` marks a task touching files no incomplete task touches.

---

## Phase 1: The accrual (foundational — blocks everything)

**Goal**: one module turns a quotation and a date into a clean price and an accrual, and
refuses by name where it cannot.

- [ ] T001 Write `tests/worked_examples/test_accrued_interest.py` with the spec's arithmetic hand-computed: 77.98 / 82.21 / 10.34, clean 1011.34 and 1009.91, purchase 1093.55, sale 1020.24. Fails with `ImportError`.
- [ ] T002 [P] Write `tests/invariants/test_accrual_invariants.py`: `price(clean(q, d), d) == q`; `accrued` non-decreasing inside a period; `accrued(c_i) == 0`; `0 <= accrued(t) < C`. Fails with `ImportError`.
- [ ] T003 [P] Write `tests/unit/test_accrual_refuses.py`: a date before the first declared coupon and one on or after the last each refuse by name; a zero-coupon schedule returns zero and no refusal (FR-008, FR-009).
- [ ] T003a [P] Write `tests/worked_examples/test_a_newly_placed_issue_refuses.py`: UA4000239040, UA4000239107 and UA4000239081 refuse under the 2026-08-24 quotation, and the reason names their first declared coupon; read the first-period lengths (155, 183, 29 days against a full 182-day amount) off the declarations rather than retyping them (SC-007).
- [ ] T004 Add `core/instruments/accrual.py`: the period lookup, `accrued`, `clean`, `price`, and the typed refusal record (FR-001 to FR-004, FR-008, FR-011). `Money` throughout; the imported project tolerance in the tests, never a local one.
- [ ] T005 Extend `accrual.py` to read the generative form's periods through `terms_of.accrual_periods` and its declared business-day rule, one rule for both forms (FR-007); extend T001–T003 to run over a generative fixture.

**Checkpoint**: gates green, no caller changed, no golden moved. Commit.

---

## Phase 2: The purchase leg (US2 — the hold-to-maturity overstatement)

**Goal**: the buy quotation is carried to the purchase date for every bond, and the belief is
named wherever it was leaned on.

- [ ] T006 [US2] Write `tests/worked_examples/test_the_buy_quotation_is_carried.py`: UA4000231195 over the twelve-month horizon, whose coupon of 2026-08-26 sits between the 2026-08-24 quotation and the 2026-09-02 purchase, is bought at the clean price plus the new period's accrual, below the declared 1110.24 (FR-005, US2 scenario 1).
- [ ] T007 [US2] Add to the same module the check that a hold-to-maturity candidate reads **no** resale quotation and is paid the declared payments (US2 scenario 2), asserted against `enumerated.events` rather than against a price.
- [ ] T008 [US2] Carry the buy quotation in `core/decision/tuple_outcome.py::_price_for` (FR-005); delete the two docstring paragraphs it falsifies.
- [ ] T009 [US2] Widen `core/decision/tuple_outcome.py::_rests_on` so every candidate whose price was carried names the belief, and one struck on the quotation's own day does not (FR-018).

**Checkpoint**: `candidate_set.golden.txt` moves. Regenerate deliberately, quote the changed lines in the commit message.

---

## Phase 3: The sale leg, and the deletions (US1 — the worked example)

**Goal**: the sale is struck by the same formula, and every trace of the coupon subtraction is
gone rather than adjusted.

- [ ] T010 [US1] Extend `tests/worked_examples/test_accrued_interest.py` to the whole owner answer: 45 units, 49 209.66 deployed, 3 847.50 coupon, 45 910.87 proceeds, 49 758.37 reached (US1 scenario 1, SC-001).
- [ ] T011 [US1] Add to it the check that a three-month hold reaches strictly more than a one-month and a twelve-month more than either (US1 scenario 2, SC-002).
- [ ] T012 [US1] Strike the sale at `price(clean, sold_on)` in `core/instruments/acquire.py::early_sale`; restate its "quotation worth less than the coupons inside it" refusal as a non-positive struck price.
- [ ] T013 [US1] Rebuild `SoldEarly` in `core/scenarios/early_exit.py`: `clean_per_unit` and `accrued_per_unit` in, `detached_per_unit` and `skipped_before_purchase` out (FR-022); update `core/results/project.py::_sold_early`.
- [ ] T014 [US1] Delete `early_exit.detached_since` and every call site; delete the module docstring paragraphs and `enumerated.coupons_per_unit`'s closing paragraph that describe it (FR-006).
- [ ] T015 [US1] Restate `enumerated.events`'s repayment-and-quotation refusal in the accrual's terms: a repayment inside the window rebases a unit, so one quotation cannot price both sides of it (FR-012).
- [ ] T016 [US1] Remove 013 FR-023's dirty-price clause from the enumerated projection's `HurdleRate.excludes` (FR-013); re-measure `tests/worked_examples/test_enumerated_premium.py` and 013's absence-proof walk.

**Checkpoint**: gates green. Commit.

---

## Phase 4: The belief and the exclusions (US3 — what the answer states)

**Goal**: one assumption, declared where it belongs, stated without a sign it cannot warrant.

- [ ] T017 [US3] Write the failing check in `tests/contract/test_the_answer_says_only_what_it_computed.py`: no result record carries a detached-coupon figure and no answer states an accrued-interest exclusion (SC-004).
- [ ] T018 [US3] Move `data/scenarios/early_exit/owner-001.toml` to `data/scenarios/quotation/owner-001.toml`; new `id`, and a `rationale` stating the constant clean price, the linear intra-period accrual and that neither is observable (FR-016, FR-003).
- [ ] T019 [US3] Rename `resolver.EARLY_EXIT_DIR` and the HTTP category id `early-exit-belief` **together** — `api/http/categories.py::directory_of` reaches the constant by `getattr` on its name, so renaming one alone raises at request time and no type checker sees it (FR-017); keep the no-default load-time refusal and its test.
- [ ] T019a [US3] Rename `manifest.InputKind`'s `early_exit_assumption` member and `declarations.tuples.early_exit_file`, and re-measure `tests/unit/test_answer_manifest.py`, which pins the literal `scenarios/early_exit/owner-001.toml` (FR-017).
- [ ] T020 [US3] Move `QuotationHolds` and `rests_on` out of `core/scenarios/early_exit.py` into a module not named for the exit (FR-017).
- [ ] T021 [US3] Remove `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST`, `Direction.SALE_STRUCK_TOO_LOW` and `core/decision/answer.py::ACCRUED_INTEREST_SUPPLIED_BY`; add the unsigned constant-clean-price exclusion in `core/results/answer.py` and `core/decision/answer.py::_early_exit_exclusions` (FR-019, FR-020, FR-021).
- [ ] T022 [US3] Re-measure the exclusion and direction sets in `tests/contract/test_the_answer_says_only_what_it_computed.py`, and assert the replacement claim carries no direction (SC-005, SC-006).

**Checkpoint**: gates green; `the_answer.golden.txt` moves. Regenerate deliberately. Commit.

---

## Phase 5: The counts and the prose

- [ ] T023 Replace `tests/worked_examples/test_a_coupon_inside_the_window.py` with the Phase 1/3 worked example; keep `BEFORE_THE_PURCHASE` as the purchase-carried-across-a-coupon case and delete `DETACHED_PER_HORIZON` and `MULTI_COUPON`, whose subject is gone.
- [ ] T024 [P] Re-run `tests/golden/test_enumerated_matches_generative.py` unchanged — the check that FR-007's one rule is one rule.
- [ ] T025 Regenerate `tests/golden/the_answer.golden.txt` and `tests/golden/candidate_set.golden.txt`, reading the diff and quoting the changed figures in the commit message (FR-025). Expect the three newly placed issues to leave — 17 lines each in the first, 4 each in the second — and check that each leaves as a **named refusal**, not as an absence.
- [ ] T026 Rewrite `docs/METHODOLOGY.md` §34.1–§34.2 and delete §31.5; add the accrual formula with the worked arithmetic (FR-024).
- [ ] T027 [P] Delete the docstrings the change falsified, listed in [plan.md](./plan.md) — `VenueQuote.observed_on`, `_price_for`, `coupons_per_unit`, `SoldEarly`'s removed fields, `early_exit.py`'s module docstring, and the `Direction` class docstring, which argues its naming convention entirely through the member FR-019 removes.
- [ ] T028 Regenerate `src/terezy/api/http/openapi.json` under its existing gate. It moves three ways — two `SoldEarly` required properties out and two in, the `InputKind` enum member renamed, the category path segment renamed — and 021's generated types regenerate from it. No request parameter changes.
- [ ] T029 Add this feature's section to `docs/REQUIRED_TESTS.md` saying which rows it presses and which box moves — no row names accrued interest today (measured 2026-09-05), and D1 is the nearest; flip `022-accrued-interest` to `done` in `specs/features.toml`.
- [ ] T030 Run the full gate list — `ruff`, `mypy`, `lint-imports`, `pytest --cov`, `check_provenance.py`, `check_prose_budget.py`, `check_enumerations.py`, `check_methodology_refs.py`.

---

## Dependencies

Phase 1 blocks everything: no leg can be carried before the accrual exists. Phase 2 (US2) and
Phase 3 (US1) touch different call sites and could run in parallel, but Phase 2 lands first
because it moves the candidate golden alone and Phase 3 moves both — a smaller diff to read.
Phase 4 (US3) needs Phase 3's deletions before the exclusion can go. Phase 5 is last by
construction: it measures what the other four changed.

## Independent test criteria

- **US1** — the spec's worked example reproduces to the project tolerance, and a longer hold
  reaches more than a shorter one.
- **US2** — a hold-to-maturity candidate's purchase price is below its declared buy quotation
  where a coupon detached in between, and its exit reads no quotation.
- **US3** — no answer states an accrued-interest exclusion, and the replacement claim carries
  no direction.

## MVP scope

Phases 1 and 3: the accrual and the sale leg. That alone makes an early exit return a real
holding period's interest, which is the owner's decision of 2026-09-05. Phase 2 is the second
half of the same defect and is not optional, only separable.
