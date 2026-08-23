---

description: "Task list for 008-seed-and-goals"
---

# Tasks: Seeds and goals

**Input**: `specs/008-seed-and-goals/` — spec.md (25 FRs, 10 SCs), plan.md, research.md (D1–D11),
data-model.md, contracts/goal-solver.md (G1–G16), contracts/owner-declarations.md, quickstart.md

**Branch**: `feat/008-seed-and-goals` in `.claude/worktrees/008-seed-and-goals`

**Tests**: required, and **written first** — constitution Principle V. A test must fail before the
implementation exists; an `ImportError` counts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelisable — different files, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1…US5)

## Order that matters (plan.md, Phase 2 note)

**Seeds first, with the existing conservation invariants green over seeded ledgers** — the proof of
D1's claim that a seed needs no special handling. Then the estimated-basis mark and its propagation,
then the declarations and their refusals, then the solver, then feasibility. Tests before
implementation in each group.

---

## Phase 1: Setup

**Purpose**: the two things every later phase needs, and nothing else.

- [x] T001 Record the baseline for the final report: `uv run pytest --cov -q` test count and coverage
      percentage, run from the worktree root
- [x] T002 Create the `core/goals` package with its charter docstring in
      `src/terezy/core/goals/__init__.py`, and register it in `LAYER_MODULES` of
      `tests/unit/test_package_layout.py` (the layout test asserts every layer is importable and
      documents its charter)

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the one shared primitive both halves of the feature need. No user story work begins
until this is done.

- [x] T003 Make the monthly-anniversary rule public: rename `_shift_months` to `shift_months` in
      `src/terezy/core/primitives/conventions.py`, updating its one internal call site, and state in
      its docstring that the goal schedule and the coupon schedule step months the same way — two
      implementations of one clamping rule would be two answers to "what is a month later"

**Checkpoint**: `uv run pytest -q` still green; nothing else has changed.

---

## Phase 3: User Story 1 — Start from what is actually held (Priority: P1) 🎯 MVP

**Goal**: declared seed lots open the ledger as ordinary opening lots, and every conservation
invariant counts them without being taught they exist.

**Independent test**: declare a synthetic seed lot with a stated cost, dispose of it, and check the
realised gain against hand arithmetic; conservation holds over randomly seeded ledgers.

### Tests for User Story 1 (write first, watch them fail)

- [x] T004 [P] [US1] SC-005: a Hypothesis strategy generating ledgers that **open from seeded lots**
      in `tests/invariants/seeded_streams.py` — seed events dated before the base stream, sequences
      and `allocated_to` shifted, the same instrument id so FIFO consumes the seeded lots first
- [x] T005 [US1] SC-005: widen **only** the `STREAMS` constant (and its docstring) in
      `tests/invariants/test_ledger_conservation.py` to draw seeded ledgers as well as unseeded ones.
      Every existing property stays byte-identical — if one fails, fix the opening, never the
      invariant
- [x] T006 [P] [US1] SC-002 / FR-004: hand-computed disposal of a known-basis seed lot in
      `tests/worked_examples/test_seeded_disposal.py`, arithmetic checked in beside the assertion —
      position quantity and basis at the opening, the realised gain after fees, several lots of one
      instrument keeping their own dates and costs
- [x] T007 [P] [US1] FR-005 / G15: `opening_events` returns `SeedInstrumentUndeclared` naming the
      instrument when no declaration defines it, and refuses an acquisition before the instrument's
      issue date and after the ledger opens — `tests/unit/test_seed_opening.py`

### Implementation for User Story 1

- [x] T008 [US1] `SeedLot`, `BasisKnown`, `BasisEstimated` and `opening_events` in
      `src/terezy/core/ledger/seeds.py`: declaration order sorted by `(acquired_on, lot_id)`,
      sequences from zero, `EventKind.PURCHASE` (the kind the engine already opens lots with), the
      cost as the event's negative amount so the existing basis invariant recomputes it
- [x] T009 [US1] Add `CausationKind.SEED_DECLARATION` in `src/terezy/core/ledger/events.py` with the
      ⚙ migration note feature 002 set for `ROUTE_TERM`: a seed declaration is a *declaration*
      resolvable to the file it was read from, which is the test the enum's docstring sets for a new
      member — not the catch-all it forbids
- [x] T010 [US1] `SeedInstrumentUndeclared` in `src/terezy/core/results/goal.py` (the feature's
      result module), reusing `errors.InconsistentTerms` for the two date inconsistencies

**Checkpoint**: conservation, lot and basis invariants green over seeded ledgers with no invariant
edited. Commit.

---

## Phase 4: User Story 2 — A guessed cost is a guessed tax (Priority: P1)

**Goal**: an estimated basis is a `SourceRef` in the lot's provenance, so the disposal gain and the
tax on it carry the mark through the transforms that already exist. One marking system, not two.

**Independent test**: two seed lots identical but for the basis declaration; dispose of both; the
estimated one's gain, tax and every derived figure are marked and the known one's are not.

### Tests for User Story 2 (write first)

- [x] T011 [P] [US2] SC-003 / FR-007: `tests/contract/test_estimated_basis_propagates.py` — 100% of
      the tax figures downstream of an estimated-basis lot carry the mark (`pit`, `levy`, `total`,
      `taxable_base`, the charge's provenance), the known-basis twin carries none of it, and a lot
      resting on both an estimated basis and an unverified observation shows both
- [x] T012 [P] [US2] FR-008: the mark states its reason and is distinguishable from an
      unverified-observation mark — `is_basis_estimated` / `basis_estimated_sources` over a
      provenance carrying one of each, in `tests/unit/test_basis_mark.py`

### Implementation for User Story 2

- [x] T013 [US2] `basis_estimated`, `BASIS_ESTIMATED_PREFIX`, `is_basis_estimated` and
      `basis_estimated_sources` in `src/terezy/core/ledger/seeds.py`: one `SourceRef` with
      `verified_on=None`, the owner's reason as its citation, and an id namespaced so the mark is
      distinguishable on inspection while propagating by the existing rule

**Checkpoint**: a guessed cost produces a guessed tax with nobody having to remember. Commit.

---

## Phase 5: User Story 5a — the seed declaration (Priority: P3, needed here)

**Goal**: seeds are per-owner declared data that fails loudly, naming file and field.

### Tests for User Story 5a (write first)

- [x] T014 [P] [US5] SC-004: the whole seed refusal battery in
      `tests/contract/test_seed_declaration_loading.py` — missing cost, missing/unknown `basis`,
      `estimated` without `reason`, `known` with one, unknown instrument, unrecognised field,
      a `currency` key (FR-010 is structural: there is no field to state one in), zero and negative
      quantity, negative cost, malformed date, bad TOML, missing file
- [x] T015 [P] [US5] SC-007: every loaded seed lot carries `owner_id`, and the shipped file says
      `SYNTHETIC FIXTURE` — in `tests/contract/test_owner_scoping.py`

### Implementation for User Story 5a

- [x] T016 [US5] `SeedTable` / `SeedFile` appended under an `008-seed-and-goals` banner in
      `src/terezy/data/declarations/schema.py`
- [x] T017 [US5] `seeds_from_file` appended under the same banner in
      `src/terezy/data/declarations/loader.py`: base currency by declaration (FR-010), lot ids from
      the file position, `prov.EMPTY` for a known basis and the estimated mark for an estimated one
- [x] T018 [P] [US5] `data/seeds/owner-001.toml` — SYNTHETIC FIXTURE, one known-basis and one
      estimated-basis lot, header stating the Principle VII boundary and why there are no citations
- [x] T019 [US5] `data/seeds/` in `EXEMPT_DIRS` of `scripts/check_provenance.py` **with its reason**
      — the owner's own records, the exemption `objectives` and `strategies` already carry

**Checkpoint**: `uv run python scripts/check_provenance.py` clean with the new directory. Commit.

---

## Phase 6: User Story 3 — Fix two, solve the third (Priority: P1)

**Goal**: three closed forms over one stated convention, mutually consistent within the single
imported tolerance.

**Independent test**: a generated body of `(contribution, sum)` pairs round-trips through the date
mode and back within the imported tolerance; each mode reproduces hand arithmetic.

### Tests for User Story 3 (write first)

- [x] T020 [P] [US3] SC-001 / FR-013 / G3: `tests/invariants/test_goal_mode_consistency.py` — over
      generated pairs, date→sum and sum→date and contribution→sum round trips all close within the
      **imported** tolerance, and no float literal near a comparison anywhere in the solver
- [x] T021 [P] [US3] FR-014: `tests/worked_examples/test_goal_arithmetic.py` — one solved figure per
      mode against arithmetic worked out by hand and checked in, plus the zero-growth degenerate case
- [x] T022 [P] [US3] FR-015 / G5: `tests/unit/test_solved_date_two_answers.py` — the exact
      real-valued solution **and** the first calendar date the target is reached, each labelled,
      neither rounded into the other
- [x] T023 [P] [US3] FR-017 / SC-009 / FR-021 / SC-010: every figure labelled nominal, the real slot
      present and explicitly empty, the determinism note present, and a marked growth assumption
      reaching every solved figure — `tests/unit/test_goal_result_shape.py`

### Implementation for User Story 3

- [x] T024 [US3] The result records in `src/terezy/core/results/goal.py`: `Goal`, `GrowthAssumption`,
      `GoalInputs`, `Conventions` (+ the one implemented convention as a module constant),
      `GoalOutcome`, `SolvedDate`, `RealTargetSum`, the feasibility union and the typed refusals
- [x] T025 [US3] `solve` in `src/terezy/core/goals/solve.py`: the three closed forms over
      `V(t) = (S − L)(1 + i)^t + L`, marks propagated through `money.scale_sourced`, the conventions
      carried in the result, no solver library and no iteration to a tolerance

**Checkpoint**: J1's property green over generated pairs. Commit.

---

## Phase 7: User Story 4 — Told the truth when the goal cannot be met (Priority: P2)

**Goal**: met with the margin, missed with both faces of the shortfall, unreachable with the reason,
and "no contribution needed" instead of a negative instruction.

### Tests for User Story 4 (write first)

- [x] T026 [P] [US4] SC-006 / G8–G10: `tests/unit/test_goal_feasibility.py` — met with margin, missed
      with the amount short **and** the date it would arrive, unreachable with its reason and no
      finite date, a non-positive solved contribution as `NoContributionNeeded` with the margin, and
      no declared variable adjusted in any case
- [x] T027 [P] [US4] G1, G2, G11: `tests/unit/test_goal_refusals.py` — fewer than two variables names
      what is missing, a missing starting amount and a missing growth assumption are named and never
      defaulted, and a non-base currency is refused as **not yet modelled** naming the missing FX
      modelling, never as an invalid currency

### Implementation for User Story 4

- [x] T028 [US4] Feasibility and the refusals in `src/terezy/core/goals/solve.py`: reachability
      decided in closed form before any date is reported, and the determinism note stating the
      verdict is one path under one stated assumption rather than a probability

**Checkpoint**: every infeasible synthetic goal yields a typed report. Commit.

---

## Phase 8: User Story 5b — the goal declaration, the owner boundary, and emptiness

**Goal**: goals are per-owner declared data; a run with no seeds and no goals is an ordinary run.

⚙ **Landed with Phase 5 rather than after Phase 7.** The goal loader needs the `Goal` record,
and the resolver reads both per-owner directories in one pass -- splitting them across two
commits would have meant a resolver that knew about half the boundary. So `Goal` was defined
early in `core/results/goal.py` and the rest of that module (the outcome, the conventions, the
feasibility union and the refusals) still lands with the solver in Phase 6.

### Tests for User Story 5b (write first)

- [x] T029 [P] [US5] SC-004: the goal refusal battery in
      `tests/contract/test_goal_declaration_loading.py` — fewer than two variables, a duplicate id,
      an unrecognised field, a malformed date, a negative contribution, a non-positive target, an
      unknown currency, and a non-base currency refused as not yet modelled
- [x] T030 [P] [US5] SC-008 / FR-024 / G16 / D9: `tests/contract/test_empty_seeds_and_goals.py` — no
      seeds and no goals runs normally with empty positions and no goal section; **not** a refusal,
      deliberately unlike feature 003's empty-dimension outcome
- [x] T031 [US5] SC-007: extend `tests/contract/test_owner_scoping.py` — every goal carries
      `owner_id`, the two files' owners must agree, and resolving them modifies no curated file
      (compare the curated tree before and after)

### Implementation for User Story 5b

- [x] T032 [US5] `GoalTable` / `GoalFile` appended to the `008-seed-and-goals` banner in
      `src/terezy/data/declarations/schema.py`
- [x] T033 [US5] `goals_from_file` appended to the banner in
      `src/terezy/data/declarations/loader.py`
- [x] T034 [US5] `SeedAndGoalDeclarations`, `resolve_seeds_and_goals` and
      `seeds_and_goals_from_data_root` appended under an `008-seed-and-goals` banner in
      `src/terezy/data/declarations/resolver.py`: instrument references resolved, the base-currency
      refusal, the two owners checked against each other, at most one file per directory, and an
      empty or absent directory accepted as an ordinary run
- [x] T035 [P] [US5] `data/goals/owner-001.toml` — SYNTHETIC FIXTURE, one goal declaring exactly two
      of the three variables
- [x] T036 [US5] `data/goals/` in `EXEMPT_DIRS` of `scripts/check_provenance.py` with its reason

**Checkpoint**: all ten success criteria have a named test. Commit.

---

## Phase 9: Polish & cross-cutting

- [x] T037 [P] `docs/METHODOLOGY.md`: what a seed lot is and why it needs a cost rather than a value;
      what an estimated basis marks and how far the mark travels; the solver's three modes with their
      stated conventions and the formula; why the feasibility verdict is not a probability
- [x] T038 [P] `docs/REQUIRED_TESTS.md`: flip **J1** and **J2** with their test paths recorded, and
      note under "Rows a feature reinforced without closing" that C1–C3 now run over seeded ledgers
- [x] T039 [P] `data/README.md`: the two new per-owner directories and their exemption
- [x] T040 Flip `008-seed-and-goals` to `status = "in-progress"` in `specs/features.toml` (with the
      first implementation commit; **not** to `done`)
- [x] T041 Run every gate from the worktree and record the numbers for the final report:
      `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `check_provenance.py`,
      `pytest --cov`, `pytest -m "contract or invariant"`

---

## Dependencies & execution order

- **Phase 1 → Phase 2 → Phase 3**. T003 blocks the solver (T025) and nothing else.
- **US1 (Phase 3)** blocks US2 (Phase 4): the mark rides the seed lot that US1 defines.
- **US5a (Phase 5)** depends on US1 and US2 — the loader builds the records they define.
- **US3 (Phase 6)** depends only on Phase 2; it shares no module with US1/US2 and could be built in
  parallel with Phases 3–5 by a second pair of hands.
- **US4 (Phase 7)** depends on US3 — same module.
- **US5b (Phase 8)** depends on US3 (the `Goal` record) and on US5a (the banner sections).
- **Phase 9** depends on everything.

### Parallel opportunities

- T004, T006, T007 (US1 tests) — three separate files
- T011, T012 (US2 tests)
- T020–T023 (US3 tests) — four separate files
- T026, T027 (US4 tests)
- T037, T038, T039 (docs)

---

## Phase 10: Review follow-up (2026-08-23)

Two blockers, three fold-ins and one owner decision from the independent review.

- [x] T042 **Blocker.** A crossing before the target date is no longer reported as an arrival:
      `_missed_or_unreachable` in `src/terezy/core/goals/solve.py` refuses a crossing that is
      not strictly later than the horizon, and the verdict is unreachable carrying the
      shortfall and the falling-through month. Pinned both directions in
      `tests/unit/test_goal_feasibility.py` and as a property with the regression as a
      Hypothesis `@example` in `tests/invariants/test_goal_mode_consistency.py`
- [x] T043 **Blocker.** `seeds.seed_cost` joins the estimated-basis mark to the declared cost
      inside `src/terezy/core/ledger/seeds.py`, so a lot assembled without the loader cannot
      fold into an unmarked gain; the propagation fixtures now build unmarked costs on purpose
- [x] T044 `_unreachable_reason` gains the third shape it was folding into the second — pure
      decay with no contribution — each branch testing the expression the solver gave up on
- [x] T045 The closed forms compute `(1+i)^t - 1` with `expm1` and invert with `log1p`, and the
      consistency property's target floor of 10 000 is gone
- [x] T046 `data/README.md` rule 5 rewritten to the owner's own rule (public facts and labelled
      synthetic fixtures only), enumeration made total, and reconciled with Principle VII;
      `.claude/skills/commit/SKILL.md` amended to match
- [x] T047 `data-model.md`, `contracts/goal-solver.md` and `research.md` D7 reconciled with the
      code they describe
- [x] T048 `is_synthetic` added to the seed and goal declarations as a required field, so rule
      5's claim is machine-readable

---

## Notes

- Every commit goes through the `/commit` skill, which runs the gates.
- Tick the checkbox in the same commit as the work.
- A conservation invariant that fails only for seeded ledgers is a defect in the opening, never a
  reason to edit the invariant (research.md D1, quickstart §1).
