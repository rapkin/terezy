# Tasks: An instrument declared as the payments it will make

**Feature**: `013-enumerated-schedule` | **Input**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/the-enumerated-form.md](./contracts/the-enumerated-form.md)

**Tests are not optional here.** Constitution Principle V is NON-NEGOTIABLE: no financial
behaviour is implemented before a test that would fail without it, and a test written before
its module — failing with `ImportError` — counts. Every phase below therefore opens with its
tests.

`[P]` marks a task that touches files no incomplete task touches.

---

## Phase 1: The vocabulary (foundational — blocks everything)

**Goal**: the two forms exist as types, and `mypy --strict` enumerates every site that reads
a generative field. Nothing is projectable yet.

- [x] T001 [P] Write `tests/unit/test_terms_vocabulary.py` asserting `PaymentKind` is closed, that `PAYMENT_KINDS` maps each member to exactly one `(EventKind, TaxableEventKind)` pair, and that the two vocabularies cannot disagree because there is one mapping — fails with `ImportError` until T003
- [x] T002 [P] Write `tests/unit/test_conventions_statement.py` asserting `AmountsAsDeclared` states that no periodicity generated the date, no business-day rule moved it and no day count sized the amount, while naming the day count that annualises (FR-016) — fails with `ImportError` until T004
- [x] T003 Add `PaymentKind`, `PAYMENT_KINDS`, `ScheduledPayment` and `EnumeratedTerms` to `src/terezy/core/instruments/interface.py`, and widen `InstrumentDeclaration.terms` to `BondTerms | EnumeratedTerms`
- [x] T004 Move `ConventionsApplied` from `src/terezy/core/results/schedule.py` to `src/terezy/core/primitives/conventions.py`, **correcting its `day_count` docstring** (FR-016: it does not fix a coupon's size in the enumerated case), and add `AmountsAsDeclared` beside it
- [x] T005 Re-point `src/terezy/core/results/schedule.py`, `src/terezy/core/results/canonical.py`, `src/terezy/core/results/project.py` and `tests/unit/test_schedule_from_ledger.py` at the moved record; type `CashFlowRow.conventions` on the union
- [x] T006 Run `uv run mypy` and record the list of sites that stopped type-checking in the commit body — that list is FR-002's promise, verified rather than asserted

**Checkpoint**: gates green with the generative suite unchanged. Commit.

---

## Phase 2: The delegation (foundational — blocks US1, US3)

**Goal**: the three sites that read a generative field ask the terms a question both forms
answer. No module outside `core/instruments/` learns that a second form exists.

- [x] T007 [P] Write `tests/unit/test_terms_answer_both_forms.py`: `known_from`, `day_count_of`, `conventions_of` and `excludes_of` each answer for a hand-built `BondTerms` and a hand-built `EnumeratedTerms`, and `known_from` carries the field path a refusal will name (SC-022) — fails with `ImportError` until T008
- [x] T008 Create `src/terezy/core/instruments/terms.py`: `TermsKnownFrom` and the four free functions, with the only `match` on the form in `src/`
- [x] T009 `src/terezy/core/ledger/seeds.py` asks `known_from` instead of reading `terms.issue_date`; the refusal keeps its type and names the term the declaration states
- [x] T010 `src/terezy/core/decision/tuple_outcome.py` asks `day_count_of` and gains `_excludes_of` beside it; **correct `_day_count_of`'s docstring** — the convention did not size an enumerated instrument's flows (FR-016)
- [x] T011 `src/terezy/core/results/project.py` asks `conventions_of`, `day_count_of` and `excludes_of`; it constructs no `ConventionsApplied` of its own and tests no form
- [x] T012 [P] Correct `of_conventions`'s docstring in `src/terezy/core/results/canonical.py` — it renders whichever statement it is handed, not "the three declared conventions" (FR-016)
- [x] T013 [P] Fix the pre-existing stale count in `src/terezy/core/results/hurdle.py`: "Three items" over a frozenset of four (FR-023)
- [x] T014 `hurdle.of_flows` takes `excludes` as a keyword defaulting to `EXCLUDES`, so the exclusions a figure states can differ by declaration (FR-023)

**Checkpoint**: gates green; every existing worked example and golden unchanged (SC-017's
first half). Commit.

---

## Phase 3: User Story 1 — a bond declared as the payments it will make (P1)

**Goal**: an enumerated declaration projects, and the schedule and totals match arithmetic
worked out by hand.

**Independent test**: `uv run pytest tests/worked_examples/test_enumerated_schedule.py`

- [x] T015 [P] [US1] Write `tests/worked_examples/test_enumerated_schedule.py`: four per-unit payments, a stated quantity and cost, every row and every total checked against arithmetic written out beside the assertion at the imported tolerance (SC-001)
- [x] T016 [P] [US1] Write `tests/unit/test_enumerated_refusals.py`: purchase one day before `covers_from` refuses naming both dates and on `covers_from` succeeds; `reinvest` refuses naming the missing price while `hold_cash` projects; a horizon short of the last payment refuses; every refusal's reason survives into the result (SC-008, SC-009, SC-024)
- [x] T017 [US1] Create `src/terezy/core/instruments/enumerated.py`: `events`, `tax_classes`, `constraints`; payments after the purchase date scaled by units held; principal repayments retiring their share of the repayments declared (research D6); every refusal an existing `InstrumentFailure` member (FR-013)
- [x] T018 [US1] Register `enumerated_schedule` in `src/terezy/core/instruments/registry.py` and add it to `DECLARATION_KINDS`
- [x] T019 [P] [US1] Write `tests/contract/test_enumerated_declaration_loading.py`: SC-006's whole battery, plus SC-019 (a forbidden generative term, and a missing day count) and SC-021 (a second coverage bound) — fails until T020–T022
- [x] T020 [US1] Add `EnumeratedScheduleTable`, `ScheduledPaymentTable`, `EnumeratedInstrumentTable` and `EnumeratedInstrumentFile` to `src/terezy/data/declarations/schema.py`
- [x] T021 [US1] Add `enumerated_instrument_from_file` to `src/terezy/data/declarations/loader.py` with every validation in data-model.md's battery, each naming file and entry
- [x] T022 [US1] Dispatch on the declared class in `src/terezy/data/declarations/resolver.py` (`LOADERS_BY_KIND`), keeping the one shared id space so a duplicate id collides across forms
- [x] T023 [P] [US1] Declare `data/instruments/ovdp_enumerated_a.toml` — the hand-sized fixture, synthetic and saying so, with its four inferences and their verification tasks
- [x] T024 [P] [US1] Add its `[[access]]` entry to `data/access/instruments.toml`
- [x] T025 [US1] Extend `scripts/check_provenance.py` with the inference checks (FR-022) and extend `tests/contract/test_provenance_gate.py` for SC-013

**Checkpoint**: SC-001, SC-006, SC-008, SC-009, SC-013, SC-019, SC-021, SC-024 green. Commit.

---

## Phase 4: User Story 2 — every payment says what it is (P1)

**Goal**: the declared label is load-bearing, proved by a figure that moves.

**Independent test**: `uv run pytest tests/unit/test_payment_label_is_load_bearing.py`

- [x] T026 [P] [US2] Declare `data/tax/synthetic_fixture.toml`'s two new classes — a coupon class and a disposal class at **different** invented rates (FR-010)
- [x] T027 [P] [US2] Declare `data/tax/timing/synthetic_fixture.toml`: the disposal class in a category with `treatment = "nets"`, `carryforward = "unlimited"`; the coupon class per-event. Update `tests/contract/test_tax_declaration_loading.py`'s pinned jurisdiction list (research D10)
- [x] T028 [US2] Declare `data/instruments/enumerated_taxable_x.toml` — the two-rate fixture, bought at a premium, with a same-category gain in the same tax year (FR-026)
- [x] T029 [US2] Write `tests/unit/test_payment_label_is_load_bearing.py`: relabelling one payment moves the tax total by exactly the hand-computed difference, and the same relabelling on the exempt-on-both-sides fixture moves nothing — the second half proving the first was necessary (SC-005)
- [x] T030 [US2] Add the two load failures this story needs to `loader.py` if T021 left them open: a payment with no kind, and an income kind the schedule produces with no declared tax class (FR-009). ⚙ Both were already closed by T021 and asserted in T019's battery

**Checkpoint**: SC-005 green. Commit.

---

## Phase 5: User Story 3 — nothing downstream knows which form was used (P1)

**Goal**: the headline test. Two tuples, one figure set.

**Independent test**: `uv run pytest tests/golden/test_enumerated_matches_generative.py`

- [x] T031 [P] [US3] Declare `data/instruments/ovdp_enumerated_mirror.toml`: `ovdp_synthetic_a`'s own computed schedule, every amount transcribed at **full float64 precision** from `face x rate x year_fraction`, same day count, same tax classes (SC-002)
- [x] T032 [P] [US3] Add its `[[access]]` entry to `data/access/instruments.toml` at the same par price
- [x] T033 [US3] Write `tests/golden/test_enumerated_matches_generative.py`: one tuple on each, same holding, route in, tax classes, route out and horizon; field by field; the only permitted differences are identity, provenance, the stated exclusions, the conventions statement and the causation **detail prose**; tolerance rather than bit-equality, stated at the assertion site with its reason (SC-002)
- [x] T034 [US3] Write `tests/contract/test_no_layer_knows_the_form.py` on the house pattern in `tests/source_scan.py`: the scan, a falsifiability test that plants a violation, and a coverage test proving the scan reaches `core/results/project.py` (SC-003)
- [x] T035 [US3] Write `tests/unit/test_seed_lot_before_coverage.py`: an opening lot before an enumerated instrument's coverage start refuses with the same typed failure as one before a generative issue date, and neither site gained a test of which form it was given (SC-022)
- [x] T036 [US3] Write `tests/contract/test_enumerated_data_only.py`: a third enumerated instrument in a scratch data root runs the full pipeline with no source change (SC-004)

**Checkpoint**: SC-002, SC-003, SC-004, SC-022 green. Commit.

---

## Phase 6: User Story 4 — what the form cannot answer, said out loud (P2)

**Goal**: the yield is produced, the conventions statement is honest, and nothing splits a
purchase price.

**Independent test**: `uv run pytest tests/unit/test_enumerated_yield.py`

- [x] T037 [P] [US4] Write `tests/unit/test_enumerated_yield.py`: the contractual yield is produced rather than refused and equals the generative equivalent's within the imported tolerance; a pair differing only in the declared day count produces two different yields, and that is correct (SC-011); the enumerated figure states the dirty-price exclusion and the generative one does not (SC-015)
- [x] T038 [P] [US4] Assert SC-010 — every row states that no periodicity generated its date, no business-day rule moved it and no day count sized its amount, while naming the day count; no row names a periodicity or a business-day rule; the canonical encoding distinguishes it from a generative row's three. ⚙ Landed inside `tests/unit/test_enumerated_yield.py` rather than in a file of its own: what a row says and what the projection still computes are the two halves FR-016 separates, and separating them into two files would have put the halves where a reader could read one without the other
- [x] T039 [US4] `results.canonical.of_conventions` renders `("declared", day_count)` for `AmountsAsDeclared` and leaves the generative arm byte-for-byte as it is (research D4)
- [x] T040 [P] [US4] Write `tests/contract/test_no_accrued_interest.py`: a walk over every field of every result record of an enumerated projection finds no accrued-interest figure, no clean price and no field splitting the purchase cost (SC-023)
- [x] T041 [P] [US4] Write `tests/contract/test_day_count_reaches_no_amount.py`: changing the declared day count in a copy moves the yield and leaves every cash-flow amount bit-identical through `float.hex()`; plus the scan half of SC-020

**Checkpoint**: SC-010, SC-011, SC-015, SC-020, SC-023 green. Commit.

---

## Phase 7: User Story 5 — what is inferred is written down as an inference (P2)

**Goal**: no inference is derived in code, and the marks reach every figure.

**Independent test**: `uv run pytest tests/contract/test_nothing_is_inferred.py`

- [x] T042 [P] [US5] Write `tests/contract/test_nothing_is_inferred.py` on the house scan pattern: no source-code site reads a last payment as principal, reads the largest payment as one, divides a declared amount by 100 outside `loader._as_fraction`, derives a coupon rate from an amount and an interval, or infers a coverage window — with its falsifiability and coverage tests (SC-014, FR-003c)
- [x] T043 [P] [US5] Write `tests/unit/test_enumerated_marks_propagate.py`: with every inference unverified, 100% of figures derived from an enumerated declaration carry the mark and no derived figure appears unmarked (SC-012)
- [x] T044 [P] [US5] Declare `data/instruments/enumerated_out_of_order.toml` — modelled on `UA4000235865`, principal a day before the final coupon — and write `tests/unit/test_transcription_records_the_source_order.py`: the record is carried, and rewriting the declared order to the ascending one removes it (SC-018)

**Checkpoint**: SC-012, SC-014, SC-018 green. Commit.

---

## Phase 8: The premium, and the figures that state it

**Goal**: FR-024 to FR-026. This is the phase that moves two goldens.

- [x] T045 [P] Write `tests/worked_examples/test_enumerated_premium.py`: a purchase above face reports the premium as its own figure, names the category treatment, and records the full cost as the lot's basis; under the exempt category the year's liability is zero, the carryforward is absent and no other category's base moves; under the netting category the same premium reduces that category's netted base by exactly the hand-computed amount and carries forward when the year is negative — the two runs differing only in the declared category (SC-016)
- [x] T046 Add `PurchasePremium` to `src/terezy/core/results/project.py` and the `at_purchase` field to `Projection`; it names the treatment of the category the disposal class belongs to and nothing else decides it (FR-025, FR-026)
- [x] T047 Add it to `results.canonical.of_projection`, and to `tests/golden/test_end_to_end_ovdp.py`'s rendering
- [x] T048 Regenerate the two goldens with `TEREZY_UPDATE_GOLDEN=1`, read the diff, and quote the changed lines in the commit message (constitution 1.2.0, Principle V)

**Checkpoint**: SC-016 green, goldens regenerated deliberately. Commit.

---

## Phase 9: Polish and cross-cutting

- [x] T049 [P] Update `docs/METHODOLOGY.md` in the same change as the formulas: the enumerated form's yield, the premium figure, and what a row's conventions statement means
- [x] T050 [P] Record in `docs/REQUIRED_TESTS.md` that **H1 and D1 are touched and not claimed** — H1 gains a second instrument shape (SC-004) and D1 is unchanged by design (SC-017). Flip nothing
- [x] T051 [P] Flip `specs/features.toml`'s `013-enumerated-schedule` status to `in-progress` at the first implementation commit
- [ ] T052 Run `/condense` over the branch diff — one fact, one place — then `/code-review` until clean. Both are blocking gates before anything lands

---

## Dependencies

```
Phase 1 (vocabulary) ──► Phase 2 (delegation) ──┬─► Phase 3 (US1) ──┬─► Phase 4 (US2)
                                                 │                   ├─► Phase 5 (US3)
                                                 │                   ├─► Phase 6 (US4)
                                                 │                   └─► Phase 7 (US5)
                                                 └──────────────────────► Phase 8 needs US1 + US2
Phase 9 last.
```

Phases 4–7 are independent of one another once Phase 3 lands. Phase 8 needs Phase 4's netting
fixture.

## Parallel opportunities

- T001 ∥ T002; T012 ∥ T013; T023 ∥ T024; T026 ∥ T027; T031 ∥ T032
- The four scan tests (T034, T040, T041, T042) touch four files and share only
  `tests/source_scan.py`, which they read
- The five data declarations (T023, T028, T031, T044, and the scratch fixture inside T036)
  are five files

## MVP scope

Phases 1–3. At that point the 32 real issues are declarable, which is the whole reason the
feature exists; Phases 4–8 are what stop the form being quietly wrong.
