# Implementation Plan: Inzhur instruments and dated tax schedules

**Feature**: `006-inzhur-instruments` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-inzhur-instruments/spec.md`

**Branch**: `feat/006-inzhur-instruments` in `.claude/worktrees/006-inzhur-instruments`,
landing on `main` by a `--no-ff` merge after a clean review pass (`specs/README.md` §4–5)

## Summary

Declare the two Inzhur funds as data, and pay feature 001's recorded debt: tax rates become
**dated schedules** instead of scalars, so a legislated change is one entry in a file rather
than a rebuild. Ukrainian law moved the military levy from 1.5% to 5% in December 2024 —
this is the shape the domain already has, not future-proofing.

The technical shape, decided in [research.md](./research.md): the schedule **replaces** the
scalar rather than sitting beside it (a half-paid debt is a second debt), and every entry
carries its own provenance because two rates cited by two sources are two observations. Two
tax classes on one instrument exercises machinery 001 already built plural; the new work is
reporting per-class subtotals, without which the split is invisible even when the ledger is
right.

The rest of the feature is Principle I applied to instruments whose numbers come from a
fund's own documents. Both funds are **assumption-driven**: asking either for a Sharpe ratio
returns a typed refusal, and no result record has a field one could sit in. Fund-internal
profitability is **not modelled** — the declared net yield is what the fund states, marked
fund-stated and unverified, and the access cost modelled carefully is the entry/exit spread
the owner actually pays. Values the primary documents did not answer enter as
`VerificationTask` records that carry **no value field**, and a projection needing one refuses
by naming the task.

**The sharpest trap in the feature is a date.** See D2, and the paragraph below.

## The one thing that must not be guessed

`RateEntry.effective_from` is a **legal fact** and must be exactly what its citation attests.
The migration invites one catastrophic shortcut: back-dating the exempt class to
`1900-01-01` so that "everything just works". Every test would pass, and a data file would
carry an invented legal fact — the single thing `CLAUDE.md` and the constitution forbid in
those words.

FR-012 exists so the honest schedule is also the working one: declare what the citation
supports, and an event dated earlier produces a typed error rather than a defaulted rate. A
schedule that never refuses is a schedule someone back-dated.

**Verify before writing the migration**: feature 001's golden run is dated 2026-01-15 onward.
If the attested effective date for the exempt class is later than that, the answer is a
citation for the earlier entry — never a widened date. If no citation can be found, **stop
and report it as an owner question**.

## Technical Context

**Language/Version**: Python 3.13; CI matrix 3.12 / 3.13 / 3.14

**Primary Dependencies**: none new. `pydantic` validates the declarations at the `data`
boundary.

**Storage**: version-controlled TOML. Three new instrument files, one migrated tax file. No
database, no cache, **no network** — the fund documents were read by a human on 2026-08-22
and their values are in the spec; nothing is fetched at build or test time.

**Testing**: pytest. Hand-computed arithmetic for the two-class split (SC-001), the three
liquidity cases (SC-007) and the pegged sizing (SC-011); 001's golden as the migration proof;
contract tests for data-only extensibility (SC-010) and for the metric refusal (SC-009).

**Target Platform**: library only. No API, no CLI, no UI.

**Project Type**: single Python library, src layout, layered `cli → api → data → core`.

**Performance Goals**: none. A monthly schedule over a few years.

**Constraints**: core pure and deterministic; exactly four plugin interfaces and **this
feature adds none, and no amendment is required**; the schedule lives behind the existing
`TaxRule`; a fund is a second **declaration kind** rather than an implementation of
`Instrument` (see *The interface question* below); functional style per D-E; one imported
tolerance; money is `float64` in a currency-tagged wrapper and a USD-equivalent term is
never money.

**Scale/Scope**: 3 new core modules, 3 touched, 3 touched data-layer modules, 4 declaration
files (3 new, 1 migrated), ~12 test modules. Closes required tests **E1**, **E10** and
**J3**, and annotates J3's wording (see below).

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Gate | Verdict |
|---|---|---|
| **I — Honesty over precision** | No figure more confident than its inputs; refusals typed and carrying their reason | **PASS, and this feature is the principle's hardest test so far.** Every number here comes from a fund describing itself. The design answers with four structural refusals rather than four caveats: no statistical metric for an assumption-driven instrument and no field for one; a range that stays a range with no midpoint helper; a `VerificationTask` that carries no value; and a rate schedule that refuses an event before its earliest cited entry. |
| **II — Framework, not script** | Data-only extensibility; exactly four plugin interfaces | **PASS, and no amendment — ruled on by the owner 2026-08-23.** No fifth plugin interface: no `FundOps`, no second mapping of functions, no new dispatch mechanism. SC-010 is the executable claim and it holds — a third fund with different liquidity terms, spread, peg and tax classes projects with zero source lines changed, and a fourth is added in a scratch directory by `tests/contract/test_fund_data_only.py`. FR-013 is the same claim for tax law, and the schedule sits behind the existing `TaxRule` unchanged. What this row must **not** say, and said until this correction, is that *a fund implements `Instrument`*. It does not: it is a second declaration **kind** under the same concept, projected by its own function because its result shape differs. See *The interface question* below. |
| **III — Pure deterministic core** | No I/O, no clock; traceable | **PASS.** `rate_on` takes the date as an argument. The fund documents were read by a human; nothing is fetched. Every projection is a fold over declared terms. |
| **IV — Reliability through contracts** | Property-based invariants; one tolerance; explicit failure | **PASS.** The tolerance is imported. Failure is a tagged union throughout — six typed refusals, none an exception. The boundary case that matters (in force *from* the effective date, inclusive) is tested at the boundary rather than inferred at each call site. |
| **V — Test-first** | Worked example, invariant or golden per behaviour; no network | **PASS.** The two-class split, the three liquidity cases and the pegged sizing are hand-computed with their arithmetic checked in. 001's golden is the migration's proof. |
| **VI — Model the whole tuple** | Cost never per instrument; currency roles distinct | **PASS, and FR-025 keeps it honest.** The fund's after-spread, after-tax outcome is reported beside 001's hurdle rate **with an explicit statement that it excludes funding and exit route costs** — the tuple's other terms are named as missing rather than quietly omitted. Base and tax currency stay hryvnia; the peg is a declared term and never a conversion licence. |
| **Engineering Standards — functional style (D-E)** | Free functions over frozen records; tagged unions; no ABCs | **PASS.** `rate_on` is a function; every declaration and result is a frozen record; refusals are union members matched with `match`; `is_assumption_driven` is `Literal[True]` rather than a bool, because this feature has no `False` case. |
| **VII — Owner-scoped and private** | Curated vs per-user separated; no telemetry | **PASS.** Fund terms and tax rates are curated public facts and live in the shared directories. The owner's exchange-rate assumption and chosen point within a range are per-run inputs, not curated data. No dependency added. |

**No violations requiring justification.** Two items of genuine added complexity are recorded
in Complexity Tracking.

### The interface question, and the ruling on it

*Added during implementation and settled by the owner on 2026-08-23, replacing a claim this
plan made that the code does not support.*

**The ruling, first, because it is what a reader needs:**

- **Not a fifth plugin interface, and no constitution amendment.** There is no `FundOps`,
  no second mapping of functions and no new dispatch mechanism; adding a third fund is a
  data-only change.
- **Nor does a fund implement `Instrument`.** The sentence this plan used to carry was
  false and the code contradicted it. A fund is a second declaration *kind* under the same
  concept, projected by its own function because its **result shape differs**.
- **`InstrumentOps` and `REGISTRY` are the dispatch for declaration kinds whose projection
  is an event stream** — not "the instrument interface" full stop, and `REGISTRY` is not
  exhaustive of instruments. Their docstrings now say so, because reading `REGISTRY` as the
  list of everything the engine calls an instrument is exactly the mistake this plan made.

**A fund does not implement `Instrument`, and it cannot without making the type system
lie.** `InstrumentOps` is the `Instrument` interface of Principle II — `events`,
`tax_classes`, `constraints`, dispatched from `core.instruments.registry.REGISTRY`. A fund
is not in that registry, and three mismatches are why:

1. **Different inputs.** `EventsFn` takes `Assumptions`: a consumption method and a coupon
   policy. A fund run also needs a liquidity mode, whether the discretionary buyback is on
   offer, an exit date, a chosen point inside a stated range, and an exchange-rate
   assumption. Nothing in this project has a default, so widening `Assumptions` would force
   every bond run to state a liquidity mode it has no use for.
2. **Different failures.** `PurchaseAfterCutoff`, `RedemptionRefused`, `PegUnsizable` and
   `AwaitingVerification` are none of them `InstrumentFailure`, and each is a fact about the
   money that has to reach the caller.
3. **A different arity of answer.** A fund stating a range with no chosen point yields
   **two** projections. No `EventsFn` signature expresses that, and collapsing it to one is
   precisely the midpoint the feature exists to refuse.

Making `InstrumentOps` generic over both was considered and rejected: it puts `Any` in the
registry and forces every call site to narrow before it can call, which is a registry that
type-checks nothing while advertising uniformity it cannot deliver. Two records that are
honestly different beat one that is uniform in name only.

**What the code therefore does.** `core.instruments.registry` declares the *vocabulary* —
`DECLARATION_KINDS`, naming both `fixed_income` and `collective_investment_fund` — and
`data.declarations.resolver.LOADERS_BY_KIND` maps each to its loader, so dispatch is a
mapping over a declared name rather than an `if` naming one class. `REGISTRY` still holds
only what genuinely implements `InstrumentOps`. The dead `fund.tax_classes()` this plan's
original claim had left behind is deleted.

**Why mismatch 3 is the decisive one.** The fund does not fit `EventsFn` because its
**output genuinely differs**, not because of a typing accident. `events` returns
`tuple[Event, ...] | InstrumentFailure`; a fund-stated 25–29% with no chosen point produces
two complete projections. There are exactly two ways to force that through the signature,
and both are worse than the split:

- **pick a point inside the range** — which FR-023 forbids by name, and which is the
  midpoint this whole feature exists to refuse; or
- **widen `EventsFn`'s return type for bonds too** — which makes every existing caller
  handle a case that cannot arise for a bond.

Neither is an improvement. Both are the interface bending to a shape it was not built for,
which is how an abstraction stops meaning anything.

**The recorded seam for feature 010**, because 010 will look for it. What it needs in order
to rank a bond against a fund in one candidate set is a common **result** — an after-tax,
after-cost figure carrying its provenance and its exclusions — not a common instrument
interface. `core.results.fund.BesideTheHurdle` is the first of those: it already takes a
fund projection and 001's `HurdleRate` and produces one comparable record with its
`excludes` and `rests_on` attached. That is where the unification belongs, and widening the
instrument interface would not have advanced it by a line.

### Post-Phase-1 re-evaluation

Re-checked after the design artifacts. No verdict changed. Three things the design surfaced:

- **The migration's risk is a date, not a schema.** Replacing a scalar with a tuple is
  mechanical; choosing what `effective_from` to give the entry that already exists is a legal
  question wearing an engineering disguise. It is now the plan's most prominent paragraph and
  a contract clause, because it is the one mistake that leaves every gate green.
- **`VerificationTask` had to carry no value field at all.** A field marked "unknown" is a
  field someone fills in. The record exists so a projection can *name* what to go and read,
  which turns "I cannot compute this" into "go read this document" — the same move feature
  003 makes with a missing route declaration.
- **The liquidity mode could not have a default.** The practice mode is a *revocable company
  practice* with an empty verification date; defaulting to it would quietly promise same-day
  NAV liquidity the регламент does not owe, and the more optimistic reading would be the
  silent one. Required parameter, on feature 005's `as_of` precedent.

## Project Structure

### Documentation (this feature)

```text
specs/006-inzhur-instruments/
├── spec.md              # Feature specification (28 FRs, 14 SCs, all clarifications resolved)
├── plan.md              # This file
├── research.md          # Phase 0 — thirteen decisions with rationale
├── data-model.md        # Phase 1 — records, fields, validation rules
├── quickstart.md        # Phase 1 — how to verify the feature works
├── contracts/
│   ├── tax-schedule.md      # rate_on, guarantees, and the cited-date rule
│   └── fund-declaration.md  # the fund TOML, guarantees, and its refusals
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code

```text
src/terezy/core/
├── tax/
│   ├── schedule.py                     NEW — RateEntry, rate_on, RateUndeclaredBefore
│   ├── flat_rate.py                    TOUCHED — reads the schedule; TaxRule unchanged
│   └── registry.py                     TOUCHED — class lookup over schedules
├── instruments/
│   └── fund.py                         NEW — the collective-investment fund
└── results/
    └── fund.py                         NEW — FundProjection and six typed refusals

src/terezy/data/declarations/
├── schema.py                           TOUCHED — RateEntryTable, FundTable, VerificationTaskTable
├── loader.py                           TOUCHED — fund_from_file; tax classes as schedules
└── resolver.py                         TOUCHED — funds join the resolved declarations

data/
├── tax/ua.toml                         MIGRATED — schedules, plus the two new classes
└── instruments/
    ├── inzhur_reit.toml                NEW
    ├── inzhur_miltech.toml             NEW
    └── synthetic_fund_c.toml           NEW — SC-010's data-only proof
```

### Tests

```text
tests/worked_examples/
├── test_two_tax_classes.py             SC-001 — distribution and redemption, per-class subtotals
├── test_rate_schedule_straddle.py      SC-003, SC-004 — a run across an effective date
├── test_fund_liquidity.py              SC-007 — practice, legal-with-discount, refused
└── test_pegged_distribution.py         SC-011, SC-012 — sizing, the cap binding, spread erosion

tests/unit/
├── test_rate_lookup_boundary.py        FR-011 — inclusive at the effective date, exactly
└── test_schedule_refusals.py           SC-005 — before the earliest entry, typed

tests/contract/
├── test_fund_data_only.py              SC-010 — a third fund, zero source lines
├── test_assumption_driven_refusal.py   SC-009 — no metric, and no field for one
├── test_fund_declaration_loading.py    every refusal in the two contracts
└── test_provenance_propagation.py      TOUCHED — SC-008, fund terms join the walk

tests/golden/
└── test_end_to_end_ovdp.py             UNCHANGED FILE — 001's golden must not move (SC-006)
```

**Structure Decision**: the existing single-library layout. Three new core modules in
packages that already exist, one migrated data file, no new layer, no change to
`.importlinter`.

## Complexity Tracking

| Added complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Provenance per `RateEntry` rather than per `TaxClass` | Two rates cited by two sources are two observations with two verification dates | One mark per class would attach a single `verified_on` to two independent facts, and the December 2024 change is exactly that case |
| `LiquidityTerms` holds two records rather than one with a mode flag | The регламент's obligations and the company's current practice are two different kinds of claim, one revocable | A flag makes them one claim read two ways, and the revocability — the thing that matters — has nowhere to live |

## Required tests this feature closes

**E1** (two tax classes on one instrument), **E10** (rates as dated schedules) and **J3**.

J3's row speaks of "redemption windows"; the funds' primary documents show **no windows
exist**. The row's substance — an exit outside the declared terms is refused, or executed at
the declared haircut, taxed correctly either way — is preserved over these declared liquidity
terms, and the landing change annotates the row's wording rather than silently reinterpreting
it (FR-015 ⚙).

## Phase 2 note

`/speckit-tasks` generates `tasks.md` next. The order that matters: **the schedule migration
first, with 001's golden green**, because everything else in the tax path depends on it and a
migration that moved a number should be found before any fund exists. Then the fund
declaration and its refusals; then the projection; then the liquidity modes; then the peg.
Tests before implementation in each group.
