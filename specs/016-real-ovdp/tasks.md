# Tasks: The first instruments that are not fixtures

**Feature**: `016-real-ovdp` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before
its data — failing because the file is absent or the ISIN is undeclared — counts. Every phase
opens with its checks.

`[P]` marks a task touching files no incomplete task touches.

---

## Phase 1: The issuer's record, retrieved (foundational — blocks everything)

**Goal**: the register is a dated observation file with a citation on every table, and the
retrieval's own surprises are recorded rather than smoothed.

- [ ] T001 Write `scripts/fetch_nbu_depository.py`: whole register, loud on a shape change, atomic write, `--dry-run`. Its header records that `date=` selects nothing (research D1) and that a fetcher may not declare.
- [ ] T002 Run it and commit `data/observations/nbu_depository.toml`.
- [ ] T003 [P] Write `tests/contract/test_the_register_the_terms_rest_on.py`: the observation's shape, **derived rather than written** — one `emit_name`, `pay_type` a closed two-member set, the 24 declared ISINs all present, the coupon identity `auk_proc × nominal ÷ 200` exact on the 24, and the seven completed issues absent. `tests/contract/test_the_observation_the_form_rests_on.py` is the precedent (FR-025).
- [ ] T004 Add `data/observations/nbu_depository.toml` to `data/README.md`'s account of `observations/` only where that account is now wrong; do not restate the file's own header.

**Checkpoint**: gates green, no declaration yet. Commit.

---

## Phase 2: What the two sources disagree about (US2 — blocks nothing, and lands first because it is evidence)

**Goal**: the three disagreements are a check over two observation files, per issue, by ISIN.

- [ ] T005 [P] Write `tests/worked_examples/test_two_sources_disagree.py` (SC-007, FR-009): the fifteen one-day-early ISINs are exactly the named fifteen, the nine agreeing are exactly its complement, `UA4000235782` differs by the single date `2027-06-03` against `2027-06-02`, `UA4000235865` publishes its principal `2026-09-15` against `2026-09-16` and out of order, and `matures_on` equals `pgs_date` on all 24. Both ISIN sets are asserted as sets, never as counts.
- [ ] T006 Add to the same module the mutation control: moving a date in a scratch copy of either file fails the check.

**Checkpoint**: gates green. Commit.

---

## Phase 3: The declarations (US1, US3 — the feature)

**Goal**: 24 real government bonds load, project and appear in the comparison.

- [ ] T007 [P] Write `tests/contract/test_the_declared_ovdp_set.py` (SC-001): **(i)** every seller-active ISIN the register does not list is reported as a refusal naming it — empty today and the only half that can fail; **(ii)** the declared set equals the seller's active ISINs minus those refusals, its size derived. Fails naming 24 undeclared ISINs.
- [ ] T008 [P] Write `tests/worked_examples/test_ovdp_transcription.py` (SC-002 to SC-005): for all 24, every payment date, amount and kind equals the depository's and the counts are equal; currency and face value equal `val_code` and `nominal`; principal repayments are exactly the `pay_type = 2` rows; `covers_from` is at or before the earliest payment and the last payment is `pgs_date`. Asserted over the whole schedule of all 24, not a sample.
- [ ] T009 [P] Write `tests/worked_examples/test_ovdp_reconciliation.py` (SC-014, FR-017): internal rate of return over each buy quotation and the declaration's remaining payments against the seller's stated buy yield — 19 issues within 0.09 pp, the five single-coupon issues named individually with their measured residuals and the convention reason. Fails on a scratch copy of either observation in which a figure has moved.
- [ ] T010 Generate the 24 files under `data/instruments/`, one per ISIN, by hand-driven transcription from the observation (never by a script — FR-019). Each carries the shared header stating it is not a fixture, naming both sources with their retrieval dates and what each supplied.
- [ ] T011 Add the 24 `[[access]]` entries with `[access.price]` at the buy quotation and `[access.resale_price]` at the sell quotation, both citing the seller alone (FR-012, FR-020, research D7).
- [ ] T012 [P] Write `tests/contract/test_ovdp_sources_stay_apart.py` (SC-010, SC-016): no source note in any of the 24 files or their access entries names both sources; every depository citation carries the endpoint URL; no citation asserts a hyperlink is a statutory obligation; and a full tuple outcome for a declared issue carries the unverified mark with the quotation's source among those named unverified (FR-022).
- [ ] T013 [P] Write `tests/contract/test_ovdp_dealing_terms.py` (SC-015, FR-017a, FR-018): every declared minimum cites the venue's dealing-terms page with its own retrieval date; no declared minimum equals its access price; no declaration anywhere carries an available quantity. Plus research D5's stated consequence: one unit of `UA4000207518` is 10.53 UAH below the declared floor, asserted rather than left in prose.
- [ ] T014 [P] Write `tests/unit/test_ovdp_early_exit.py` (SC-013, and 015 FR-031): a declared issue whose terms run past the horizon is sold at `horizon.end` at the declared resale price rather than refusing; one with no resale price still refuses through `DeclarationMissing(part="access")`; `TupleRefused` still has seventeen members.
- [ ] T015 [P] Write `tests/contract/test_scratch_declaration_refusals.py` (SC-008, SC-011): a battery of scratch declarations carrying a maturity date, coupon rate, placement date, periodicity, stated yield, availability or status fails at load naming file and field; a scratch register with one issue removed produces the refusal naming that ISIN and the retrieval date.

**Checkpoint**: gates green, the suite's counts red. Commit is deferred to Phase 5.

---

## Phase 4: Nothing derives a term it was not given (US4)

- [ ] T016 [P] Write `tests/contract/test_no_isin_reaches_the_core.py` (SC-017, FR-019, FR-023): no module under `src/terezy/core/` names an ISIN or reads a stated yield, an availability figure, a status, a coupon rate, a placement date or a coupon period; no script writes under `data/instruments/` or `data/access/`. Each scan carries a negative control proving it would catch the thing it forbids.
- [ ] T017 Correct `data/README.md`'s *"reviewed rather than enforced"* paragraph, which T016 closes (FR-028).

**Checkpoint**: gates green. Commit.

---

## Phase 5: The counts, and the prose that went false (US5)

- [ ] T018 Apply FR-027a: drop `ovdp` from `data/instruments/enumerated_out_of_order.toml`'s `groups`, and correct its header's claim that the real issue *"publishes the repayment of principal one day BEFORE the final coupon"* — the depository puts both on `2026-09-16` and the ordering is the seller's transcription error. Keep the fixture and the mechanism (FR-027, FR-028).
- [ ] T019 [P] Write `tests/contract/test_one_security_is_not_two_candidates.py` (SC-020): no group resolves to both `UA4000235865` and `enumerated_out_of_order`, asserted against a registry that actually declares the `ovdp` group so a green result over zero labels cannot pass for evidence.
- [ ] T020 Correct 013's account of `UA4000235865` wherever it attributes the ordering to the issuer (FR-028). The requirement and the fixture stand; the reading of the instance does not.
- [ ] T021 Re-measure and re-record every site under *Counts that move*: `tests/worked_examples/test_candidate_accounting.py`, `tests/worked_examples/test_candidate_enumeration.py`, `tests/unit/test_seventeen_refusals_through_the_loop.py`, `specs/014-candidates/spec.md`, `specs/014-candidates/plan.md`, and feature 015's note in `specs/features.toml`. Replace a count by a derivation wherever one is available (FR-025).
- [ ] T022 Regenerate `tests/golden/candidate_set.golden.txt` and `tests/golden/the_answer.golden.txt` deliberately; read both diffs and quote the changed lines in the commit body. **A result line moving where only an input digest should have is a stop-and-report** (Principle V).
- [ ] T023 Flip the rows this feature closes in `docs/REQUIRED_TESTS.md` and record the test paths. Confirm `docs/METHODOLOGY.md` is unchanged and say so (FR-028).
- [ ] T024 Run every gate by exit code: `uv run pytest --cov`, `uv run mypy`, `uv run ruff check . && uv run ruff format --check .`, `uv run lint-imports`, and all four `scripts/check_*.py`.

**Checkpoint**: everything green. Commit, then `/condense`, then `/code-review` until clean.

---

## Out of this feature's hands

Recorded rather than done: FR-011's inference marker on a primary-sourced schedule (the
`primary-sourced-schedule-may-be-verified` future entry), the inventory cap, the secondary-market
model, and owner verification tasks 2 and 3.
