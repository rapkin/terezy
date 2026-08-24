# Phase 1 data model: tax depth

**Feature**: `009-tax-depth` | **Date**: 2026-08-23

Frozen records, free functions, tagged unions matched with `match`. One imported tolerance.

**The rule that governs the file: no field anywhere holds a liability without the method
that produced it** (FR-024, research.md D5).

---

## The tax year

### `AnnualStatement` — `core/tax/year.py`

⚙ **Built in `core/tax/year.py`, not in `core/results/`.** Putting it under `results/` would
be an import cycle rather than a preference: `core.results.fund` and `core.results.project`
both import `core.tax.year` for the charge memo, so the module that *produces* statements
cannot also import them from `results/`. Nothing mechanical would have caught it —
`.importlinter` declares no layer contract inside `terezy.core` — which is why it is recorded
here. `core/results/tax_year.py` keeps the half that spends money: `settle`, the payment
record, and the settlement refusals.

| Field | Type | Meaning |
|---|---|---|
| `tax_year` | `int` | |
| `category` | `str` | Declared income category; one statement per category per year (FR-001) |
| `treatment` | `Treatment` | How the year was assembled — nets, per event, or outside |
| `charges` | `tuple[ChargeRef, ...]` | Each traceable to its event and its rule (FR-002) |
| `netted_base` | `Money` | Gains less losses within the year (FR-013) |
| `carryforward` | `CarryforwardState \| None` | `None` for a category that carries no losses |
| `liability` | `AssessedLiability` | Never a bare `Money` — see below |
| `zero_because` | `ZeroReason \| None` | Exemption, netting, or nothing happened (FR-006) |
| `settlement`, `due_on` | | The declared behaviour and the date it is payable |
| `unsettled` | `tuple[UnsettledSwitch, ...]` | Every declared switch this figure rests on |

**No `method` field on the statement.** The method is reachable only through `liability`,
which also carries the standing behind it — so there is no field a reader can take the method
from while leaving the citation behind, and no second copy to drift from the first.

### `AssessedLiability`

| Field | Type | Meaning |
|---|---|---|
| `pit` | `Money` | |
| `levy` | `Money` | Assessed on the **same netted base** as the PIT (FR-017) |
| `base` | `Money` | The netted, carryforward-reduced figure both rates were applied to |
| `method` | `LotMethod` | The method the ledger's disposals were consumed by, **read from** `LedgerState.consumption_method` rather than taken as an argument |
| `standing` | `MethodStanding` | What the law is found to say about that method |
| `rests_on` | `Provenance` | The rate entries, the timing rule, the category, the standing |

**There is no field named `total` alone** and no constructor that produces a liability
without a method. FR-024's "no figure may be labelled the tax you would owe" is enforced by
the type, not by review.

### `LotMethod`

A closed enum: `FIFO`, `LIFO`, `AVERAGE_COST`, `SPECIFIC_LOT`. **No default anywhere.** A
caller states one.

Each carries its legal standing as declared data, not as a code attribute: the ПКУ
prescribes none (settled by absence), ДПС guidance points at proportional/average-cost for a
self-declarant, Методика МФУ № 1484 п. 3.3 prescribes FIFO for the agent case, and the
taxpayer's freedom to choose is unsettled.

## Payment

### `TaxPayment` — a ledger event

| Field | Type | Meaning |
|---|---|---|
| `due_on` | `date` | From the declared rule, never computed by the engine |
| `settles` | `CausationRef` | Names the `AnnualStatement` |
| `amount` | `Money` | Tax currency |

Goes through `engine.fold` like every other event (research.md D2). **If a conservation
property fails only for ledgers containing a payment, the event is wrong — not the
invariant.**

### `DueDateRule` — declared, `data/tax/`

| Field | Type | Meaning |
|---|---|---|
| `declare_by`, `pay_by` | month-day | Researched starting values: 1 May and 1 August |
| `weekend_convention` | declared | FR-008; not engine logic |
| `provenance` | `Provenance` | `verified_on` may be empty, never absent |

## Carryforward

### `CarryforwardState`

| Field | Type | Meaning |
|---|---|---|
| `filed` | `bool` | **Declared per run, no default** (FR-014, research.md D4) |
| `open_balance` | `Money` | Still unused at the horizon — reported, never dropped (FR-019) |
| `forfeited` | `Money` | In the unfiled branch, named so the cost of not filing is visible (SC-010) |

## Refusals

Named as designed; the implementation's own names are in the two `year.py` modules, and
where they differ they are wider rather than different (`TimingRuleUndeclared` covers the
whole timing rule, not only the due date).

| Record | When |
|---|---|
| `DueDateRuleUndeclared` | A taxable event with no declared rule (FR-005) |
| `FilingStatusUndeclared` | The loss-year branch not stated (FR-014) |
| `MethodUndeclared` | A disposal with no method named (FR-024) |
| `MethodDisagreesWithStatements` | A settlement folds under a method the statements it is paying were not assessed under (FR-024). There is no counterpart on the assessment: `statements` reads the ledger's own method rather than taking one, so the disagreement is unrepresentable there |
| `LotNotNamed` | Specific-lot without a named lot (FR-021) |
| `LotNamedUnderWrongMethod` | A lot named under any other method (FR-022) |
| `InsufficientCashForTax` | Shortfall, date and statement named; nothing sold (FR-009, D7) |
| `TaxCurrencyConversionUnavailable` | A foreign-currency taxable event, naming the missing official-rate machinery — see the plan's boundary |

## What is deliberately absent

- **No unlabelled liability.** No type reaches a figure without its method.
- **No default method, no default filing status, no default due date.**
- **No forced sale.** `forced-sale-policy` is the owner's recorded deferral.
- **No penalty or interest modelling** (FR-010, FR-011 — stated deferrals).
- **No withheld-at-source class implemented**, though the property is declarable (FR-003).
