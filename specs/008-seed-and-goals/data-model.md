# Phase 1 data model: seeds and goals

**Feature**: `008-seed-and-goals` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Frozen dataclasses, free functions, tagged unions matched with `match` (owner decision D-E).
Money is `float64` in a currency-tagged wrapper; the single project tolerance is imported and
**no mode defines its own** (FR-013).

One rule governs the whole file: **there is one marking system, not two** (research.md D3).
An estimated basis is a `SourceRef` in the lot's `Provenance`, so it propagates through the
transforms that already exist and cannot be dropped by one that forgot about it.

---

## Seeds

### `SeedLot` — `core/ledger/seeds.py`

| Field | Type | Meaning |
|---|---|---|
| `owner_id` | `str` | FR-022, FR-007 of the constitution's Principle VII |
| `instrument_id` | `str` | Must name a curated declaration; unknown fails at load (FR-005) |
| `is_synthetic` | `bool` | Whether the holding is invented (FR-025) — required, never defaulted, and machine-readable because `data/README.md` rule 5 rests on it |
| `quantity` | `float` | |
| `acquired_on` | `date` | |
| `lot_id` | `str` | Identity, from the entry's position in the file — two purchases of one instrument on one date are two lots |
| `declared_at` | `str` | Where it was declared (`seeds/owner-001.toml#seed[0]`), for the `SEED_DECLARATION` cause and the estimate's mark |
| `cost` | `Money` | The declared amount, in the **base currency** (FR-010), *as written* — read `seeds.seed_cost`, which joins it to the basis mark |
| `basis` | `BasisKnown \| BasisEstimated` | Explicit — never inferred (FR-006) |

`basis` is a two-member union rather than a `is_estimated: bool`, because the estimated case
carries a reason and the known case carries nothing: a boolean plus a nullable reason is the
same information with one more way to be inconsistent.

### `BasisEstimated`

| Field | Type | Meaning |
|---|---|---|
| `reason` | `str` | Why the owner does not know it (FR-008) |
| `mark` | `SourceRef` | Kind `basis_estimated`; the reason is its `source` text |

The `SourceRef` is what makes FR-007 true without a second propagation path: it enters the
lot's `Provenance`, and `merge` carries it into every figure derived from the lot — including
the disposal gain, and therefore the **tax** on it (research.md D3).

**A single point value, not a range** (FR-009). A range would need a distribution to be
useful and this feature has none; a point the owner states, marked as an estimate, is the
honest shape.

## Goals

### `Goal` — declared, `core/results/goal.py`

| Field | Type | Meaning |
|---|---|---|
| `owner_id` | `str` | |
| `is_synthetic` | `bool` | Whether the target is invented (FR-025) |
| `monthly_contribution` | `Money \| None` | Any **two** of these three are declared (FR-011) |
| `target_sum` | `Money \| None` | |
| `target_date` | `date \| None` | |
| `currency` | `Currency` | Kept explicitly, **not** assumed hryvnia (FR-016, research.md D7) |

Fewer than two declared is refused naming what is missing. All three declared is not a
solve — it is the feasibility question of FR-018.

### `GoalInputs`

| Field | Type | Meaning |
|---|---|---|
| `as_of` | `date` | The date the starting amount is measured at and the schedule begins from |
| `base_currency` | `Currency` | The run's base currency, stated rather than read off the amount |
| `starting_amount` | `Money \| None` | Explicit; **no assumed opening balance** (FR-012) |
| `growth` | `GrowthAssumption \| None` | Explicit; **no default rate** |

⚙ **Amended during implementation (2026-08-23).** Three changes, each forced by the
requirements rather than chosen:

- `as_of` exists because the core has no clock and every mode needs an origin for the monthly
  schedule; without it a solved date could not be reproduced a year later.
- `base_currency` is stated rather than inferred from `starting_amount.currency`, because
  Principle VI calls conflating two currency roles a defect: inferring would mean a goal in the
  wrong currency checked against an amount in the wrong currency, and both passing.
- The last two are `| None`. Non-optional, FR-012's `StartingAmountMissing` and
  `GrowthAssumptionMissing` could never fire, and a guard that cannot fire is worse than none.

### `GrowthAssumption`

| Field | Type | Meaning |
|---|---|---|
| `annual_rate` | `float` | |
| `provenance` | `Provenance` | Marks here — unverified, estimated — propagate to every solved figure (FR-012) |

### `Conventions`

| Field | Type | Meaning |
|---|---|---|
| `contribution_timing` | `Literal["end_of_period"]` | When in the period a contribution lands |
| `compounding` | `Literal["monthly"]` | How growth compounds between contributions |
| `monthly_rate` | `Literal["twelfth_root_of_annual"]` | `i = (1+g)^(1/12) - 1`, the effective reading |
| `month_count` | `Literal["anniversary_actual_days"]` | Monthly anniversaries plus the elapsed fraction of the month in progress |

⚙ **The last two were added during implementation (2026-08-23)**, and they are not decoration:
each changes the answer materially. A nominal annual rate over twelve gives 12.68% where the
effective reading gives 12%, and a fixed 30.44-day month puts a target date on a fractional
month it does not fall on. FR-014 requires the conventions the arithmetic depends on to be
stated, and these two are among them.

**Carried in the result, not implicit in the code** (FR-014). This is what lets a hand
computation and the engine check the same model instead of two models that agree to three
decimals.

## Results

### `GoalOutcome` — `core/results/goal.py`

| Field | Type | Meaning |
|---|---|---|
| `solved_for` | `Literal["contribution", "sum", "date", "feasibility"]` | Which of the three was unknown, or `"feasibility"` when all three were declared |
| `contribution`, `sum`, `date` | the three, all populated after solving | |
| `exact_date` | `SolvedDate \| None` | Date mode only — see below |
| `conventions` | `Conventions` | |
| `feasibility` | `Met \| Missed \| Unreachable` | FR-018, FR-019 |
| `terms` | `Literal["nominal"]` | Labelled on its face (FR-017) |
| `real` | `RealTargetSum \| RealTermsUnavailable` | The reserved slot, in the shape 001's `HurdleRate.real` set (research.md D8) — a **typed** empty occupant carrying its reason, not a bare `None`, so a nominal `Money` cannot be assigned into it |
| `determinism_note` | `str` | States the verdict is one path under a stated assumption, **not** a probability (FR-021, research.md D10) |
| `provenance` | `Provenance` | The growth assumption's marks, propagated |

### `SolvedDate` — the date mode's two answers

| Field | Type | Meaning |
|---|---|---|
| `exact` | `float` | Months, real-valued — the point at which FR-013's round trip closes |
| `first_reached_on` | `date` | The first calendar date the target is actually reached |

**Both, always, each labelled** (FR-015, research.md D5). Neither is rounded into the other.

### Feasibility

| Member | Fields |
|---|---|
| `Met` | `margin: Money` |
| `Missed` | `shortfall_at_target: Money`, `reached_on: date` — both, per FR-018 |
| `Unreachable` | `reason: str` — never a capped horizon or a distant date (FR-019) |

### Typed refusals

⚙ **Eight, not six, and one of them is not in this module** (amended 2026-08-23). The two
additions each close a case the spec's own edge-case list names and the contract's signature
did not enumerate; `SeedInstrumentUndeclared` moved because a seed refusal in a results module
would make `core.ledger` import `core.results`, which is backwards.

| Record | Where | When |
|---|---|---|
| `GoalUnderdetermined` | `core/results/goal.py` | Fewer than two variables — names which (FR-011) |
| `StartingAmountMissing` | `core/results/goal.py` | No opening balance declared; none is assumed (FR-012) |
| `GrowthAssumptionMissing` | `core/results/goal.py` | No rate declared; none is defaulted (FR-012) |
| `CurrencyNotYetModelled` | `core/results/goal.py` | A non-base target — the reason names the **missing FX modelling**, never the currency as invalid (FR-016) |
| `NoContributionNeeded` | `core/results/goal.py` | The solved contribution is at or below zero, **or** the date mode is asked about a target already met — carries the margin, not a negative instruction (FR-020) |
| `TargetDateNotInFuture` | `core/results/goal.py` | A target date on or before the evaluation date — never solved backwards (spec, Edge Cases). Uncatchable at load: "past" is relative to a date no declaration file carries |
| `Unreachable` | `core/results/goal.py` | Returned by `solve` in the date mode, where there is no other answer to give; the same record the feasibility verdict uses (FR-019) |
| `SeedInstrumentUndeclared` | `core/errors.py` | A seed naming an instrument no curated declaration defines (FR-005) |

None is an exception. `raise` stays for programmer errors.

## What is deliberately absent

- **No probability field anywhere** (FR-021, research.md D10).
- **No second marking system** for estimated bases (research.md D3).
- **No default growth rate and no assumed opening balance** — there is no field either could
  hide in, and their absence is a refusal rather than a substitution.
- **No range-valued basis** (FR-009).
- **No real-terms figure** — the slot exists and stays `None` until feature 007, and the owner
  did not opt into real becoming the default when it lands.
- **No empty-dimension refusal.** No seeds and no goals is an ordinary run (FR-024,
  research.md D9).
