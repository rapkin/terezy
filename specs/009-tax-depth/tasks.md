# Tasks: Tax depth

**Input**: Design documents from `/specs/009-tax-depth/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/tax-year.md](./contracts/tax-year.md)

**Tests**: **Mandatory**, and written first. Constitution Principle V is non-negotiable and
`docs/REQUIRED_TESTS.md` rows **E2**, **E6** and **E7** are the definition of done for this
feature. Every task marked *(test)* must fail before the implementation task beneath it.

**Organization**: by user story, in the order plan.md's Phase 2 note fixes — the annual
statement and the payment event first with 001's golden green, then the declarations and
their refusals, then netting and carryforward, then the four methods.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **[Story]**: US1–US5 from spec.md; setup, foundational and polish tasks carry none

## Path conventions

Single Python library: `src/terezy/`, `tests/`, `data/`, `docs/`. Layer order
`cli → api → data → core` (`.importlinter`).

---

## Phase 1: Setup

**Purpose**: know the ground before moving it.

- [X] T001 Record the baseline gate numbers (test count, coverage, lint/mypy/import-linter/provenance/methodology) in the working notes by running the six gate commands from `CLAUDE.md` in `/Users/rapkin/dev/terezy/.claude/worktrees/009-tax-depth`
- [X] T002 Flip `009-tax-depth` to `status = "in-progress"` in `specs/features.toml` (lands in the first implementation commit, never later)

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: cure defect B5 structurally, give the ledger a payment event, and give the data
layer the two new declaration kinds. Nothing in Phases 3–7 can be written honestly until a
tax charge stops moving cash.

**⚠️ CRITICAL**: no user-story work begins until this phase is green, **including 001's
golden**.

### The B5 cure — a charge records, it does not settle

- [X] T003 (test) Assert a `TAX_CHARGE` event whose amount is non-zero is refused by `events.check_shape`, in `tests/unit/test_ledger_failures.py` — the structural form of FR-001: tax deducted at event time becomes unrepresentable, not merely discouraged
- [X] T004 Add the zero-cash shape rule for `EventKind.TAX_CHARGE` to `_check_cash_only` in `src/terezy/core/ledger/events.py`, and state in the kind's docstring that a charge is an assessment memo whose settlement is a separate dated payment
- [X] T005 Add `EventKind.TAX_PAYMENT` to `src/terezy/core/ledger/events.py` with its shape rule (cash-only, negative or zero, touches no holding) and its place in `CASH_ONLY_KINDS`
- [X] T006 Turn the charge event into a memo in `src/terezy/core/results/project.py::_tax_event` — the amount becomes the charge at zero cash effect, with the reasoning and the signed-zero note in the docstring
- [X] T007 Turn the charge event into a memo in `src/terezy/core/results/fund.py::_tax_event`, the sibling path reaching the same claim (006's fund projection), and correct `CARRYFORWARD_NOT_MODELLED` so it no longer claims what 009 now models
- [X] T008 Take the schedule's tax column off the event's cash amount and onto the charge in `src/terezy/core/results/schedule.py` and its two callers, so a row's `tax` still reports what was charged now that no cash moves for it
- [X] T009 (test) Assert 001's golden is **bit-identical** — `uv run pytest tests/golden/test_end_to_end_ovdp.py` — and that no `TAX_PAYMENT` event appears in the exempt run, in `tests/golden/test_end_to_end_ovdp.py`

### The payment as an ordinary ledger citizen (008's seed precedent)

- [X] T010 [P] Extend `tests/invariants/event_streams.py` to generate `TAX_CHARGE` memos at zero cash and a new `TAX_PAYMENT` operation drawing real cash out
- [X] T011 (test) Draw the extended streams into the existing conservation properties in `tests/invariants/test_ledger_conservation.py` **without changing one property** (SC-006), and record in the module docstring that a failure here is a defect in the event, never in the invariant
- [X] T012 (test) Extend `tests/invariants/test_traceability.py` so a payment event resolves to the declaration that caused it (C6)

### The records

- [X] T013 [P] Create `src/terezy/core/tax/year.py` with the frozen records: `IncomeCategory`, `Treatment`, `CarryforwardRule`, `TimingRule`, `Settlement behaviour`, `LotMethod`, `MethodStanding`, `UnsettledSwitch`, `FilingDecisions`, `AssessmentRules`, `ChargeRef`, `CarryforwardState`, `AssessedLiability`, `AnnualStatement`, and the `TaxYearRefusal` union — **no constructor produces a liability without its method** (data-model.md)
- [X] T014 [P] Create `src/terezy/core/results/tax_year.py` with the settlement-side records: `TaxPayment`, `OpenObligation`, `Settlement`, `InsufficientCashForTax`, `WithholdingNotModelled`
- [ ] T015 (test) Assert `AssessedLiability` cannot be constructed without a `LotMethod` and that no field on any record in either module is a bare unlabelled liability, in `tests/contract/test_method_is_never_implicit.py`

### The declarations

- [ ] T016 [P] Append the `009-tax-depth` banner and the timing/category/method schema models to `src/terezy/data/declarations/schema.py` (`extra="forbid"`, `strict=True`, no defaults)
- [ ] T017 [P] Append the `009-tax-depth` banner and the tax-scenario schema models (filing decisions, unsettled positions) to `src/terezy/data/declarations/schema.py`
- [ ] T018 Append `timing_from_file` and `tax_positions_from_file` to `src/terezy/data/declarations/loader.py` under a `009-tax-depth` banner, every failure naming the file and the field
- [ ] T019 Append `tax_rules_from_data_root` and `tax_positions_from_data_root` to `src/terezy/data/declarations/resolver.py` under a `009-tax-depth` banner, resolving class → category references across files
- [ ] T020 [P] Write `data/tax/timing/ua.toml`: the declaration and payment deadlines, the non-business-day convention, the income categories with their netting treatment and carryforward rule, the settlement behaviour per class, and the four lot methods' legal standing — every table cited, `verified_on` empty
- [ ] T021 [P] Write `data/scenarios/tax/owner-001.toml`: the owner's per-year filing decisions and the two unsettled positions, labelled as beliefs with the ІПК (ст. 52 ПКУ) recorded as the resolution path

**Checkpoint**: the ledger has a payment kind, a charge moves no cash, 001's golden has not
moved, and both new declarations load.

---

## Phase 3: User Story 1 — Tax is money leaving on a date (Priority: P1) 🎯 MVP

**Goal**: charges assessed to a year, a statement per year and category, and a single dated
payment that debits cash in the following year.

**Independent Test**: one taxable gain; the position and proceeds are gross at trade time,
the liability equals the hand-computed charge for the gain's year, and exactly one cash
outflow settles it on the declared due date of the following year.

- [X] T022 (test) [US1] Hand-compute a one-gain scenario end to end in `tests/worked_examples/test_tax_payment.py`: gross in the ledger at trade time, the year's liability, the payment on the declared due date, arithmetic checked in beside the assertion (SC-003)
- [X] T023 (test) [P] [US1] Assert the annual statement's shape in `tests/unit/test_annual_statement.py` — charges enumerated and traceable to event and rule (FR-002), one statement per year × category, zero years present with their reason (FR-006)
- [X] T024 (test) [P] [US1] Assert an assessed-but-not-yet-due liability at the horizon is reported as an open obligation in `tests/unit/test_annual_statement.py` (FR-007)
- [X] T025 [US1] Implement `statements(...)` in `src/terezy/core/tax/year.py`: the fold from charges to statements, per year and declared category, with the netted base, the zero reason, and the method on every figure
- [X] T026 [US1] Implement `settle(...)` in `src/terezy/core/results/tax_year.py`: due date from the declared rule, the payment woven into the stream and renumbered, the statement named on the event, open obligations reported rather than dropped
- [ ] T027 (test) [US1] Assert a withheld-at-source class refuses rather than being silently self-assessed, in `tests/unit/test_annual_statement.py` (FR-003)

**Checkpoint**: US1 is testable on its own; every later story extends this fold.

---

## Phase 4: User Story 2 — A loss is worth something, if you file (Priority: P1)

**Goal**: netting within the year, carryforward between years, both filing branches, and the
levy on the same netted base.

**Independent Test**: one fixture, two runs differing only in the filing flag; each year's
tax hand-checked in both branches, and the two differing by exactly the hand-computed value
of the carryforward.

- [ ] T028 (test) [US2] Hand-compute the loss-year-then-gain-year fixture in both branches in `tests/worked_examples/test_loss_carryforward.py`, with the arithmetic checked in and the difference asserted against the carryforward's own value (SC-001, SC-010)
- [ ] T029 (test) [P] [US2] Assert PIT and the levy are both computed from the **same netted, carryforward-reduced base** and reported as separate lines, and that a negative year yields two zeros citing the netting, in `tests/worked_examples/test_loss_carryforward.py` (SC-011)
- [ ] T030 (test) [P] [US2] Assert an exempt-security (OVDP) loss beside taxable gains changes neither the taxable result nor the tax, and appears nowhere in the netting, in `tests/worked_examples/test_loss_carryforward.py` (SC-005)
- [ ] T031 (test) [P] [US2] Assert a scenario reaching a year with investment operations and no declared filing decision refuses, naming the year, in `tests/contract/test_tax_declaration_loading.py` (FR-014)
- [ ] T032 (test) [P] [US2] Assert both chain-continuity branches produce their own hand-computed figure and that each figure carries the unsettled label, in `tests/contract/test_unsettled_is_labelled.py` (FR-015, SC-012)
- [ ] T033 [US2] Implement netting, the carryforward ledger and the forfeiture figure in `src/terezy/core/tax/year.py`, per declared category treatment and declared carryforward rule
- [ ] T034 [US2] Implement the chain-continuity switch's two branches in `src/terezy/core/tax/year.py`, labelling every statement whose figures rest on it
- [ ] T035 (test) [P] [US2] Assert a carryforward still open at the horizon is reported with its origin year in `tests/unit/test_annual_statement.py` (FR-019)

**Checkpoint**: E2 closes — both branches, both hand-computed.

---

## Phase 5: User Story 3 — Choose the lots you sell (Priority: P2)

**Goal**: four methods, four figures, none of them "the tax you would owe".

**Independent Test**: a three-lot position with a partial sale run once under each method;
each run's tax checked against its own hand-computed arithmetic, and the four pairwise
distinct by construction.

- [ ] T036 (test) [US3] Hand-compute the three-lot partial-sale fixture under FIFO, LIFO, average-cost and specific-lot in `tests/worked_examples/test_four_lot_methods.py`, with each method's arithmetic checked in and the four results asserted pairwise distinct (FR-025, SC-002)
- [ ] T037 (test) [P] [US3] Assert the specific-lot refusals — an unknown lot, an exhausted lot, a lot holding too few units — each naming the lot and the shortfall, and never falling back to another method, in `tests/unit/test_ledger_failures.py` (FR-021)
- [ ] T038 (test) [P] [US3] Assert a disposal naming a lot under any method other than specific-lot is a conflict, never a silently ignored hint, in `tests/unit/test_ledger_failures.py` (FR-022)
- [ ] T039 (test) [P] [US3] Assert an unknown or absent method fails naming the four known methods, in `tests/contract/test_tax_declaration_loading.py` (FR-020)
- [ ] T040 [US3] Implement `basis_consumed` and the four selection functions in `src/terezy/core/ledger/lots.py` — all four together, where the existing two live (research.md D10) — with average cost consuming pro rata over the packet and specific lot consuming exactly the named lot
- [ ] T041 [US3] Widen `_check_closing` in `src/terezy/core/ledger/events.py` so a named lot is a specific-lot request rather than a refusal, and move the method conflict to where the method is known
- [ ] T042 (test) [P] [US3] Draw all four methods into the conservation properties in `tests/invariants/test_ledger_conservation.py` (SC-006, FR-023)
- [ ] T043 (test) [P] [US3] Assert every emitted tax figure states the method that produced it, and that the two source-backed candidates carry their citations, in `tests/contract/test_method_is_never_implicit.py` (FR-024, SC-012)

**Checkpoint**: E6 closes.

---

## Phase 6: User Story 4 — When the cash is not there (Priority: P2)

**Goal**: a typed shortfall report, and nothing sold.

**Independent Test**: a scenario whose year-Y liability exceeds the cash held on the due
date stops on that date with the hand-computed liability, cash and shortfall; no date shows
negative cash and no disposal the scenario did not declare appears.

- [ ] T044 (test) [US4] Assert the typed shortfall outcome carries the hand-computed liability, cash available and shortfall, and that the projection up to the failure date is still traceable, in `tests/unit/test_insufficient_cash.py` (SC-004, FR-009, FR-012)
- [ ] T045 (test) [P] [US4] Assert over generated scenarios that no shortfall run ends with a negative balance, a partial payment, or an engine-generated disposal, in `tests/invariants/test_no_silent_clamping.py` (SC-004)
- [ ] T046 [US4] Implement the shortfall path in `src/terezy/core/results/tax_year.py::settle` — stop, name it, touch nothing

**Checkpoint**: E7's first half closes; its forced-sale half stays the owner's recorded
deferral.

---

## Phase 7: User Story 5 — The law changes as data (Priority: P3)

**Goal**: prove, rather than build, that every legal value this feature added is data.

**Independent Test**: change a declared due date or carryforward term in data only; payment
events and netting move with it, with no source change.

- [ ] T047 (test) [P] [US5] Assert a changed due date in a scratch data root moves the payment event with no source change, in `tests/contract/test_tax_declaration_loading.py` (US5 scenario 1)
- [ ] T048 (test) [P] [US5] Assert the whole misdeclaration battery fails naming file, field or declaration — missing method, unknown method, missing filing decision, missing due-date rule, malformed carryforward declaration, unknown non-business-day convention — in `tests/contract/test_tax_declaration_loading.py` (SC-007, FR-008, FR-018)
- [ ] T049 (test) [P] [US5] Assert an unverified legal value marks 100% of the figures derived from it — annual liabilities, payment amounts, forfeitures — in `tests/contract/test_provenance_propagation.py` (SC-008, FR-027)
- [ ] T050 (test) [P] [US5] Assert a foreign-currency taxable event refuses, naming the missing official-rate machinery rather than converting at a channel rate, in `tests/contract/test_tax_declaration_loading.py` (plan.md's boundary)

**Checkpoint**: Principle II holds for everything this feature declared.

---

## Phase 8: Polish & cross-cutting

- [ ] T051 [P] Add `docs/METHODOLOGY.md` §29: how a year is assessed, why no tax is deducted at event time, the four methods with their legal standing, why none is labelled the liability, and the worked arithmetic of the carryforward
- [ ] T052 [P] Add the new questions to `docs/METHODOLOGY.md` §28's "where to look next" table
- [ ] T053 Flip **E2** and **E6** in `docs/REQUIRED_TESTS.md` with their test paths, and annotate **E7** as partially closed with the forced-sale deferral stated
- [ ] T054 Record the forced-sale and late-payment-interest deferrals as `[[future]]` entries in `specs/features.toml`
- [ ] T055 Run every gate — ruff, mypy, lint-imports, check_provenance, check_methodology_refs, `pytest --cov`, `pytest -m "contract or invariant"` — and record the delta from T001's baseline
- [ ] T056 Run `specs/009-tax-depth/quickstart.md` end to end and confirm each of its five sections says what it claims

---

## Dependencies & execution order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: blocks every user story. T003–T009 (the B5 cure) block T010–T012; T013–T014 block every implementation task; T016–T021 block Phases 3, 6 and 7
- **US1 (Phase 3)**: the fold every later story extends — not independent of Phase 2
- **US2 (Phase 4)**: needs US1's fold (T025)
- **US3 (Phase 5)**: independent of US2; needs Phase 2 only
- **US4 (Phase 6)**: needs US1's `settle` (T026)
- **US5 (Phase 7)**: needs the declarations (T016–T021) and something to move — run last
- **Polish (Phase 8)**: after all of the above

### Within each story

Tests first, and they must fail before the implementation task beneath them exists.

### Parallel opportunities

- T010, T013, T014, T016, T017, T020, T021 are different files with no shared state
- Phase 5 (US3) can run alongside Phase 4 (US2): different modules, different tests
- Every task marked [P] within a phase touches a file no other [P] task in that phase touches

---

## Implementation strategy

**Order fixed by plan.md's Phase 2 note**, and it is not negotiable: the annual statement
and the payment event first **with 001's golden green** — that proves the fold gained a year
without moving a figure. Then the declarations and their refusals; then netting and
carryforward with both branches; then the four methods.

Commit at every green checkpoint through `/commit`, ticking the tasks in the same commit as
the work.

---

## Notes

- **If a conservation property fails only for ledgers containing a payment, fix the event —
  never the invariant.** 008 did exactly this for seeds (research.md D2).
- **No default method, no default filing status, no default due date.** Each absence is a
  refusal naming what is missing.
- **The levy's base is the netted base.** A levy whose base exceeds the PIT's is invisible in
  a total (SC-011).
- **State the expected diff before regenerating any golden.** If 001's golden moves, the
  exempt path grew a behaviour it should not have (research.md D9).
