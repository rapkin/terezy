# Implementation Plan: Seeds and goals

**Feature**: `008-seed-and-goals` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-seed-and-goals/spec.md`

**Branch**: `feat/008-seed-and-goals` in `.claude/worktrees/008-seed-and-goals`, landing on
`main` by a `--no-ff` merge after a clean review pass (`specs/README.md` §4–5)

## Summary

Add both ends of a projection that currently starts at zero and stops when told: what the
owner already holds, and what the money is for.

The technical shape, decided in [research.md](./research.md), is two ideas.

**A seed is an ordinary ledger citizen.** It opens the ledger through the same path a purchase
takes, so every conservation invariant counts it from day one without being taught it exists —
and the one nobody taught would have been the defect.

**There is one marking system, not two.** FR-007 says an estimated basis must mark downstream
figures *exactly as* an unverified value does, and the only reading of that which stays true is
to use the system that already does it: a `SourceRef` in the lot's provenance, flowing through
`merge` into the disposal gain and therefore into the **tax**. A guessed cost becomes a guessed
tax with nobody having to remember to make it so. That is Principle I turned on the owner's own
declarations rather than only on market data, and it is the feature's spine.

The solver is closed-form arithmetic over a **stated** convention, not a root finder — because
FR-014's "reproduces hand-computed arithmetic" is only checkable when the engine and the hand
are evaluating the same model, and an iterative solver would let the tolerance absorb the
difference between two. Its conventions travel in the result for the same reason.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new, and **no solver library**. Three closed forms over a
monthly schedule; importing `scipy.optimize` here would replace a checkable formula with a
converged number.

**Storage**: version-controlled TOML. Two new per-owner directories, `data/seeds/` and
`data/goals/`, each holding one **synthetic, labelled** file. No database, no network.

**Testing**: pytest. Hand-computed arithmetic for the disposal of a seeded lot and for each
solved figure; Hypothesis for the three-mode consistency over generated pairs and for
conservation over randomly seeded ledgers; contract tests for the refusal battery and for mark
propagation.

**Target Platform**: library only. No API, no CLI, no UI.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. Three formulas and a monthly loop.

**Constraints**: core pure and deterministic, no clock; exactly four plugin interfaces and
**this feature adds none**; functional style per D-E; **one imported tolerance and no mode may
define its own** (FR-013 says so explicitly, which is unusual and worth honouring literally).

**Scale/Scope**: 3 new core modules, 2 touched, 3 touched data-layer modules, 2 new declaration
files and directories, ~10 test modules. Closes required tests **J1** and **J2**.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; refusals typed and carrying their reason | **PASS, and the feature extends the principle's reach.** Until now "unverified" described the world; here it describes the owner's own memory. An estimated basis marks the gain and therefore the tax, and a goal that cannot be met reports the binding shortfall rather than a nearest answer. The date mode returns two answers rather than rounding one into the other, and the feasibility verdict says out loud that it is not a probability. |
| **II — Framework, not script** | Data-only extensibility; exactly four plugin interfaces | **PASS.** No fifth interface. A seed names any curated instrument and the ledger holds it; adding a holding is a data change. The goal solver knows nothing about which instrument the money sits in. |
| **III — Pure deterministic core** | No I/O, no clock; traceable | **PASS.** Every date is an argument or a declaration; `date.today()` appears nowhere. The solved date is computed from declared inputs, which is what makes it reproducible a year from now. |
| **IV — Reliability through contracts** | Property-based invariants; **one** tolerance; explicit failure | **PASS, and FR-013 states the tolerance rule itself.** The three-mode agreement is a property over generated pairs with the imported tolerance, and "no mode may define its own" is in the requirement rather than only in the constitution. Six typed refusals; no exceptions for business outcomes. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** The disposal of a seeded estimated-basis lot and each solved figure are hand-computed with the arithmetic checked in. Conservation over randomly seeded ledgers is the property that proves D1's claim that seeds need no special handling. |
| **VI — Model the whole tuple** | Currency roles distinct; costs never per instrument | **PASS.** A seed's cost is base currency by declaration (FR-010), and a goal's target is base currency with the non-base case refused as *not yet modelled* rather than invalid — the multi-currency seam named, not closed. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; tagged unions; no ABCs | **PASS.** `basis` is a two-member union rather than a boolean with a nullable reason; feasibility is `Met \| Missed \| Unreachable`; every refusal is a union member matched with `match`. |
| **VII — Owner-scoped and private** | `owner_id` from day one; curated vs per-user separated | **PASS, and this feature is the first thing that lives wholly on the private side.** Seeds and goals sit in per-owner directories beside `data/streams/`, every record carries `owner_id`, and declaring or deleting them touches no curated file. No dependency added, no telemetry. |

**No violations requiring justification.** Two design costs are recorded in Complexity Tracking.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced:

- **The estimated-basis mark had to reuse the provenance machinery, not imitate it.** "Marks
  exactly as an unverified value does" can be satisfied by building a parallel system that
  behaves the same — and that system would need its own `merge`, its own propagation through
  every transform, and its own coverage in the provenance contract test. The constitution calls
  a transform that drops a mark top-severity; one system already tested end to end cannot drop
  a mark where the other remembered.
- **Emptiness is not always a refusal, and the rule needed stating.** Feature 003 makes an
  empty registry dimension a typed outcome because an empty venue list and a mistyped path are
  indistinguishable downstream. Here they are distinguishable and neither is a mistake. The
  general rule — refuse emptiness where it cannot be told from an error, accept it where it can
  — is now written down, because the two features would otherwise look inconsistent.
- **The date mode has two correct answers and needed both.** The exact real-valued solution is
  what makes FR-013's round trip close; the calendar date is what the owner can act on.
  Reporting only one breaks either the consistency property or the usefulness, and rounding
  silently is the nearest answer the spec forbids twice.

## Project Structure

### Documentation (this feature)

```text
specs/008-seed-and-goals/
├── spec.md              # Feature specification (25 FRs, 10 SCs, all clarifications resolved)
├── plan.md              # This file
├── research.md          # Phase 0 — eleven decisions with rationale
├── data-model.md        # Phase 1 — records, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── goal-solver.md         # solve / opening_events, guarantees G1–G16
│   └── owner-declarations.md  # the two TOML shapes, and their refusals
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── ledger/
│   └── seeds.py                        NEW — declared seed lots to opening events
├── goals/                              NEW package
│   └── solve.py                        NEW — three modes, feasibility, conventions
└── results/
    └── goal.py                         NEW — GoalOutcome, SolvedDate, six refusals

src/terezy/data/declarations/
├── schema.py                           TOUCHED — SeedFile, GoalFile
├── loader.py                           TOUCHED — seeds_from_file, goals_from_file
└── resolver.py                         TOUCHED — seeds and goals join the resolved set

scripts/check_provenance.py             TOUCHED — EXEMPT_DIRS gains seeds and goals, with reasons

data/
├── seeds/owner-001.toml                NEW — SYNTHETIC FIXTURE
└── goals/owner-001.toml                NEW — SYNTHETIC FIXTURE
```

### Tests

```text
tests/worked_examples/
├── test_seeded_disposal.py             SC-002 — hand-computed gain from a known basis
└── test_goal_arithmetic.py             FR-014 — each solved figure, by hand

tests/invariants/
├── test_goal_mode_consistency.py       SC-001 — three modes agree over generated pairs
└── test_ledger_conservation.py         TOUCHED — SC-005, now over randomly seeded ledgers

tests/unit/
├── test_goal_feasibility.py            SC-006 — met, missed, unreachable, no-contribution-needed
└── test_solved_date_two_answers.py     FR-015 — exact and first-reached, both, neither rounded

tests/contract/
├── test_seed_declaration_loading.py    SC-004 — the whole refusal battery
├── test_estimated_basis_propagates.py  SC-003 — 100% of tax figures marked
├── test_owner_scoping.py               SC-007 — every record carries owner_id
└── test_empty_seeds_and_goals.py       SC-008 — an ordinary run, not a refusal
```

**Structure Decision**: one new small package (`core/goals/`), two new core modules in packages
that already exist, two new per-owner data directories. No new layer, no change to
`.importlinter`.

## Complexity Tracking

| Design cost | Why accepted | Simpler alternative rejected because |
|---|---|---|
| The date mode returns two answers | The exact solution is what makes the three modes consistent; the calendar date is what the owner can act on | Returning one forces either a broken consistency property or a useless answer, and rounding between them silently is the nearest answer FR-015 forbids by name |
| `basis` is a two-member union rather than a flag plus a nullable reason | The estimated case carries a reason and the known case carries nothing | A boolean with an optional reason is the same information with one more way to be inconsistent — and the loader would have to check the combination that the type can simply not express |

## Required tests this feature closes

**J1** (a target is a sum, a date and a contribution; fix any two, solve the third) and **J2**
(existing holdings as opening lots with a known or estimated basis). Both boxes flip in the
landing change with their test paths recorded.

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: **seeds first, with the
existing conservation invariants green over seeded ledgers** — that is the proof of D1's claim
that a seed needs no special handling, and it should be established before anything depends on
it. Then the estimated-basis mark and its propagation, then the declarations and their
refusals, then the solver, then feasibility. Tests before implementation in each group.
