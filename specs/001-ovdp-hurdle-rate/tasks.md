---
description: "Task list for 001-ovdp-hurdle-rate"
---

# Tasks: The OVDP hurdle rate

**Input**: Design documents from `specs/001-ovdp-hurdle-rate/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: **Mandatory, and written first.** Constitution Principle V: no financial
behaviour is implemented before a test that would fail without it. Tests are interleaved
below, never a trailing phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1–US4)
- Every task names its files and the requirement or required-test row it closes

## Binding constraints for every task

Read before starting any task. These are not suggestions.

- **Functional style** (constitution 1.1.0, decision D-E): free functions over frozen
  dataclasses. No classes with behaviour, no inheritance, no ABCs, no `Protocol` classes
  with methods, **no operator dunders**. `abc` is blocked in `core` by `.importlinter`.
- **Interfaces are function signatures** gathered into frozen records, dispatched from a
  `dict`. Never subclass dispatch.
- **Domain failures are a tagged union**, matched with `match` plus a `case _:` mypy
  proves unreachable. `raise` only for programmer errors (currency mismatch, violated
  invariant).
- **Core is pure**: no I/O, network, logging, formatting, `random`, `datetime.now`,
  `hashlib`, `pydantic`.
- **One tolerance**, imported from `core/primitives/tolerance.py`. A task that writes its
  own tolerance constant is wrong.
- **Provenance propagates.** Money is combined only through `money.*` functions, which
  merge provenance. Never construct `Money(...)` with `Provenance.EMPTY` from a declared
  value.

**On test-first ordering**: a test written before its module fails with `ImportError`.
That counts — it is a red test proving the behaviour is absent. Do not stub a module to
make the import succeed.

---

## Phase 1: Setup

**Purpose**: package skeletons. The layered tree already exists from the foundation
commit; this adds the new leaves.

- [ ] T001 [P] Create `src/terezy/core/primitives/__init__.py` with a charter docstring stating it imports nothing but the standard library
- [ ] T002 [P] Create `src/terezy/core/results/__init__.py` with a charter docstring
- [ ] T003 [P] Create `src/terezy/data/declarations/__init__.py` with a charter docstring stating validation lives here, never in core
- [ ] T004 Verify `uv run lint-imports` still passes with the new packages, and add the new modules to `tests/unit/test_package_layout.py`

**Checkpoint**: packages importable, boundaries intact.

---

## Phase 2: Foundational (BLOCKING — strictly sequential)

**Purpose**: money, provenance, conventions and the ledger. Everything else imports these.

**⚠️ This phase is a single sequential block and must NOT be split across parallel
agents.** `Money`-with-provenance is the foundation; two agents writing it concurrently
will diverge on the provenance contract, which is the one thing the gates cannot check.
No task within this phase is marked `[P]`.

### Primitives (plan step 1)

- [ ] T005 Write `tests/invariants/test_currency_safety.py` — property test that combining UAH and USD always raises `CurrencyMismatchError`; no implicit conversion exists. Closes **C5**, FR-007. Must fail first.
- [ ] T006 Implement `src/terezy/core/primitives/currency.py` — closed `Currency` enum, `UAH` and `USD`
- [ ] T007 Implement `src/terezy/core/primitives/provenance.py` — frozen `SourceRef` and `Provenance` records plus free functions `merge`, `merge_all`, `is_unverified`, `unverified_sources`, `EMPTY`. Closes part of FR-014
- [ ] T008 Write `tests/unit/test_provenance_monoid.py` — property tests that `merge` is associative and commutative and that `EMPTY` is its identity, so evaluation order can never change a mark. Closes part of **E5**
- [ ] T009 Implement `src/terezy/core/primitives/money.py` — frozen `Money(amount: float, currency: Currency, provenance: Provenance)` with `provenance` excluded from equality (`field(compare=False)`), plus free functions `add`, `sub`, `scale`, `total`, `compare`. Every combining function merges provenance; cross-currency raises. **No dunders.** Closes FR-006, FR-007, part of FR-015
- [ ] T010 Implement `src/terezy/core/primitives/tolerance.py` — the single `TOLERANCE` constant plus `is_close` and `assert_money_close`, the latter also asserting currency equality. Closes FR-002
- [ ] T011 Implement `src/terezy/core/primitives/rates.py` — three unrelated frozen records `NominalRate`, `RealRate`, `RealTermsUnavailable(reason: str)`. Not a hierarchy: assigning nominal into a real slot must be a mypy error. Closes part of FR-022
- [ ] T012 Implement `src/terezy/core/errors.py` — the tagged union of domain failures (`InfeasiblePurchase`, `InconsistentTerms`, `UnresolvedTaxClass`, `InstrumentFailure`, `TaxFailure`), each a frozen record carrying its reason, plus `CurrencyMismatchError` as the one exception. Closes FR-017
- [ ] T013 Write `tests/contract/test_money_construction_guard.py` — scan the source tree for direct `Money(` construction outside `core/primitives/money.py` and `data/declarations/`, and fail on any other site. This closes the one hole the functional style leaves open (research.md D2)

### Conventions (plan step 2)

- [ ] T014 Write `tests/worked_examples/test_day_count.py` — hand-computed day-count fractions for `act/365`, `act/act` and `30/360` over stated date pairs, arithmetic checked in beside each assertion
- [ ] T015 Implement `src/terezy/core/primitives/conventions.py` — `DAY_COUNT_FNS`, `PERIODICITY_FNS`, `BUSINESS_DAY_FNS` as `Mapping[str, Callable]`. Closes part of FR-021
- [ ] T016 Write `tests/contract/test_unknown_convention.py` — an unrecognised convention name fails loudly naming the value; there is no fallback convention. Closes part of **FR-021**

### Ledger (plan step 3)

- [ ] T017 Write `tests/invariants/test_ledger_conservation.py` with three property suites: cash conservation per currency **on every date** (**C1**), lot conservation with no negative quantity (**C2**), and basis conservation with realised gain equal to proceeds minus consumed basis minus allocated fees in **both** currencies (**C3**). Must fail first. Closes FR-009, FR-010, FR-011
- [ ] T018 Implement `src/terezy/core/ledger/events.py` — frozen `Event` record with `sequence`, `occurred_on`, `kind`, `amount`, `owner_id`, `caused_by: CausationRef`, `lot_ref`. `owner_id` is present from day one per Principle VII
- [ ] T019 Implement `src/terezy/core/ledger/lots.py` — frozen `Lot` and `Position` records, plus free functions `rebuild(events)` and `consume(position, qty, method)`. Lots carry cost in trade **and** base currency plus the FX rate used
- [ ] T020 Implement `src/terezy/core/ledger/accounts.py` — frozen per-currency balance record plus `apply(account, event)`
- [ ] T021 Implement `src/terezy/core/ledger/engine.py` — pure fold of an event sequence into ledger state. Deterministic in `sequence` order, never dependent on sort stability
- [ ] T022 Implement `src/terezy/core/ledger/canonical.py` — free functions `of_event`, `of_position`, `of_result` returning nested tuples of primitives with amounts as `float.hex()`. **Provenance is deliberately excluded** — see plan's post-Phase-1 note
- [ ] T023 Write `tests/invariants/test_traceability.py` — every figure resolves to the events behind it, and every event names the term or rule that caused it. Closes **C6**, FR-008

**Checkpoint**: `uv run pytest -m invariant` green for C1, C2, C3, C5, C6. Parallel work
may now begin. **Commit here** — this is the natural green checkpoint.

---

## Phase 3: User Story 1 — Know the hurdle rate (P1) 🎯 MVP

**Goal**: state a purchase, hold to maturity, get the schedule and the after-tax return
labelled as the hurdle rate.

**Independent test**: construct bond terms directly in code — no file on disk — project to
maturity, and check every cash flow against arithmetic worked out by hand. This is why the
loader is not in this phase (research.md D1).

- [ ] T024 [US1] Write `tests/worked_examples/test_ovdp_schedule.py` — the D1 example: a stated purchase of a synthetic issue held to maturity, with the full coupon and principal schedule computed by hand and checked in beside the assertion, and **total tax exactly zero**. Closes **D1**, SC-001, SC-002. Must fail first
- [ ] T025 [US1] Implement `src/terezy/core/instruments/interface.py` — `EventsFn`, `TaxClassesFn`, `ConstraintsFn` type aliases, frozen `InstrumentOps` record, and `REGISTRY: Mapping[str, InstrumentOps]`. Unknown `instrument_class` is a failure, never a fallback
- [ ] T026 [US1] Implement `src/terezy/core/instruments/fixed_income.py` — free functions computing the closed-form coupon and principal schedule from `BondTerms` via the declared conventions, exported as `OPS`. Returns `InconsistentTerms` when maturity ≤ issue and `InfeasiblePurchase` below `min_ticket`. Closes FR-001, FR-018
- [ ] T027 [P] [US1] Implement `src/terezy/core/tax/interface.py` — `ChargeFn` alias, frozen `TaxRuleOps`, `REGISTRY`. The rule takes `TaxClass` as an argument rather than closing over it
- [ ] T028 [P] [US1] Implement `src/terezy/core/tax/flat_rate.py` — applies whatever `pit_rate` and `levy_rate` the declared class carries, PIT and levy on **separate bases** and reported as separate lines. A zero charge is still a charge, carrying the class's provenance. **No exempt-specific branch exists.** Closes FR-003
- [ ] T029 [US1] Implement `src/terezy/core/results/schedule.py` — `CashFlowSchedule` derived from ledger events, each row carrying date, gross, tax, net and the convention that placed the date
- [ ] T030 [US1] Implement `src/terezy/core/results/hurdle.py` — `HurdleRate` with `nominal_ytm`, `nominal_cash_flow_return`, `real: RealRate | RealTermsUnavailable`, `total_tax`, `excludes`, `provenance`. Closes FR-004, FR-005, FR-022
- [ ] T031 [P] [US1] Write `tests/unit/test_hurdle_real_slot.py` — the real slot is present and explicitly `RealTermsUnavailable` with a reason, never absent and never holding a nominal value. Closes **SC-011**
- [ ] T032 [P] [US1] Write `tests/unit/test_infeasible_and_inconsistent.py` — purchase below minimum ticket reports the shortfall and is not rounded; maturity on or before issue produces no schedule; non-positive quantity is rejected. Closes FR-018 and the spec's edge cases
- [ ] T033 [US1] Add `src/terezy/core/results/project.py` wiring schedule → events → ledger → `HurdleRate`, and take T024 green. Every figure derives from the ledger, never from the schedule directly (research.md D3)

**Checkpoint**: the project's benchmark number exists and is hand-verified. **MVP
reached** — commit.

---

## Phase 4: User Story 2 — Trust the number (P1)

**Goal**: every figure traceable to its events and its rule; every input showing its
source and verification state; an unverified input marking everything downstream.

**Independent test**: leave the yield unverified and confirm no derived figure appears
unmarked.

- [ ] T034 [US2] Write `tests/contract/test_provenance_propagation.py` — with the yield's `verified_on` empty, the schedule, every tax figure, `total_tax` and both return figures all report unverified, and **no derived figure is unmarked**. Closes **E5**, FR-015. Must fail first
- [ ] T035 [P] [US2] Write `tests/invariants/test_determinism.py` — two runs on identical inputs produce an identical digest; the digest is unaffected by filling in a `verified_on`. Closes **C4**, SC-006
- [ ] T036 [US2] Implement `src/terezy/data/manifest.py` — run manifest recording inputs, their versions and the SHA-256 digest over the canonical form. `hashlib` lives here, not in core. Closes FR-012
- [ ] T037 [P] [US2] Write `tests/unit/test_manifest_records_inputs.py` — a result without a manifest is not a result; the manifest names every declaration and version that fed the run

**Checkpoint**: `pytest -m "contract or invariant"` green. Commit.

---

## Phase 5: User Story 3 — Reinvest the coupons (P2)

**Goal**: coupons either held as cash or reinvested at the yield available on the coupon
date, with the difference visible.

**Independent test**: same purchase run under both policies, two-period arithmetic checked
by hand.

- [ ] T038 [US3] Write `tests/worked_examples/test_coupon_reinvestment.py` — the D2 example: two coupon periods reinvested, arithmetic checked in beside the assertion. Closes **D2**. Must fail first
- [ ] T039 [US3] Extend `src/terezy/core/instruments/fixed_income.py` with the declared coupon policy — `hold_cash` and `reinvest` — emitting `reinvestment` events for whole units only. Closes FR-019
- [ ] T040 [P] [US3] Write `tests/unit/test_reinvestment_remainder.py` — a coupon too small to buy a whole unit reports the remainder and retains it as cash, never discarding it and never buying a fraction. Closes **FR-020**
- [ ] T041 [P] [US3] Write `tests/unit/test_policies_differ.py` — reinvesting and cash-holding produce different terminal amounts on the same purchase, and the cash sits in a UAH balance. Closes **SC-010**

**Checkpoint**: commit.

---

## Phase 6: User Story 4 — Add another issue without touching the engine (P3)

**Goal**: a second issue with different conventions works as a data-only change, and every
malformed declaration fails loudly naming file and field.

**Independent test**: add a declaration file and run the full projection with no source
edit.

- [ ] T042 [P] [US4] Implement `src/terezy/data/declarations/errors.py` — `DeclarationError(file, field_path, problem, remedy)`. No `pydantic.ValidationError` may cross this boundary
- [ ] T043 [US4] Implement `src/terezy/data/declarations/schema.py` — pydantic v2 models with `ConfigDict(extra="forbid", strict=True, frozen=True)` and **zero field defaults**, per `contracts/declaration-schema.md`. `is_synthetic` is required
- [ ] T044 [US4] Implement `src/terezy/data/declarations/loader.py` — `tomllib` read → validate → construct core records, adapting `ValidationError` into `DeclarationError`. Divides `_pct` fields by 100 exactly once, at this boundary. Builds `SourceRef` ids from file and table so figures trace back
- [ ] T045 [US4] Implement `src/terezy/data/declarations/resolver.py` — the cross-file pass pydantic cannot do: duplicate ids across files, and `tax_classes` referencing an undeclared class. Closes part of FR-016
- [ ] T046 [P] [US4] Create `data/tax/ua.toml` — the `ua_government_bond` exempt class with its cited source per `contracts/declaration-schema.md`. **Zero rates carry a citation.** `verified_on` empty
- [ ] T047 [P] [US4] Create `data/instruments/ovdp_synthetic_a.toml` — the D1/D2 fixture, `is_synthetic = true`, name stating plainly that terms are invented
- [ ] T048 [P] [US4] Create `data/instruments/ovdp_synthetic_b.toml` — a second issue with **different** periodicity and day-count, to prove SC-012
- [ ] T049 [US4] Write `tests/contract/test_declaration_loading.py` — a battery of deliberately broken files, one per row of the enforced-rules table in `contracts/declaration-schema.md`: unknown field, missing field, wrong type, absent `verified_on`, table with numerics but no source, duplicate id, undeclared tax class, unknown convention name, malformed TOML, non-positive face value. Every case names file and field; **no case substitutes a default**. Closes **H2**, FR-014, FR-016, SC-004
- [ ] T050 [US4] Write `tests/contract/test_data_only_extensibility.py` — the second issue produces a complete result with zero source-code changes, and each schedule reports the convention it applied. Closes **SC-003**, **SC-012**
- [ ] T051 [P] [US4] Confirm `uv run python scripts/check_provenance.py` passes on the three new data files, with empty-`verified_on` warnings expected and no errors

**Checkpoint**: `pytest -m contract` green. Commit.

---

## Phase 7: Polish and cross-cutting

- [ ] T052 Write `tests/golden/test_end_to_end_ovdp.py` — the full path from `data/instruments/ovdp_synthetic_a.toml` through the loader to `HurdleRate`, asserting it agrees with the directly-constructed path of T033 within the project tolerance
- [ ] T053 [P] Create `docs/METHODOLOGY.md` documenting the coupon-schedule formula, each day-count fraction, the yield-to-maturity and cash-flow-weighted return definitions, and the tolerance policy. An undocumented formula is an incomplete feature
- [ ] T054 [P] Flip the ten rows in `docs/REQUIRED_TESTS.md` and record each test path: **C1, C2, C3, C4, C5, C6, D1, D2, E5, H2**
- [ ] T055 **REVIEW (manual, no gate can do this)**: read every site that produces a figure and confirm the provenance mark survives. The gates cannot see a dropped mark; FR-015 calls it top-severity. Check especially aggregations and any place a raw `float` is turned back into `Money`
- [ ] T056 **REVIEW (manual, no gate can do this)**: grep the diff for `pytest.approx`, `abs(... ) <`, `math.isclose` and any numeric literal used as a bound. Every tolerance must be the imported one; FR-002 admits no local constant
- [ ] T057 Run the full gate set: `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `check_provenance.py`, `pytest --cov` with the 90% floor. All blocking

---

## Dependencies

```
Phase 1 (setup)
   ↓
Phase 2 (foundational) — STRICTLY SEQUENTIAL, one agent, T005→T023
   ↓
   ├──────────────┬──────────────┬──────────────┐
   ↓              ↓              ↓              ↓
Phase 3 (US1)  Phase 4 (US2)  Phase 5 (US3)  Phase 6 (US4)
   │              │              │              │
   │              └── needs T033 │              │  (independent of US1)
   │                             └── needs T026 │
   ↓              ↓              ↓              ↓
   └──────────────┴──────────────┴──────────────┘
                        ↓
                  Phase 7 (polish)
```

**Story dependencies, honestly stated:**

- **US1** depends only on Phase 2.
- **US2** needs T033 from US1 — there must be figures before their provenance can be
  traced.
- **US3** needs T026 from US1 — reinvestment extends the schedule generator.
- **US4** is **independent of US1–US3** and can run concurrently with all of them. The
  loader constructs the same core records the tests build by hand.

## Parallel opportunities

**Within Phase 2**: none by design. This is the deliberate serialisation.

**After Phase 2**, three agents can work concurrently:

| Agent | Tasks |
|---|---|
| A | Phase 3 (US1) → then Phase 4 (US2) → then Phase 5 (US3) |
| B | Phase 6 (US4) — the whole data layer, T042–T051 |
| C | T053 (`METHODOLOGY.md`) once the formulas are settled by T026 |

**Within phases**, tasks marked `[P]` touch different files: T027+T028 (tax alongside
instruments), T031+T032, T035+T037, T040+T041, T046+T047+T048, T053+T054.

## MVP scope

**Phase 1 + Phase 2 + Phase 3** — 33 tasks. That delivers the hand-verified hurdle rate,
which is the entire point of the slice, and is worth committing on its own.

Phase 4 is not optional in spirit even though it is a separate phase: the spec marks US2
as P1 alongside US1, because the first figure this tool ever produces rests on an
unverified yield. Shipping the number without the mark would be the exact dishonesty
Principle I exists to prevent.

## Task count

| Phase | Tasks | Closes |
|---|---|---|
| 1 — Setup | 4 | — |
| 2 — Foundational | 19 | C1, C2, C3, C5, C6, FR-002, FR-006–011, FR-017, FR-021 |
| 3 — US1 (MVP) | 10 | D1, SC-001, SC-002, SC-011, FR-001, FR-003–005, FR-018, FR-022 |
| 4 — US2 | 4 | C4, E5, SC-006, FR-012, FR-015 |
| 5 — US3 | 4 | D2, SC-010, FR-019, FR-020 |
| 6 — US4 | 10 | H2, SC-003, SC-004, SC-012, FR-013, FR-014, FR-016 |
| 7 — Polish | 6 | the ten required-test rows, methodology, manual reviews |
| **Total** | **57** | |
