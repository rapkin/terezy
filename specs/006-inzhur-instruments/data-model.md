# Phase 1 data model: Inzhur instruments and dated tax schedules

**Feature**: `006-inzhur-instruments` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Frozen dataclasses, free functions, tagged unions matched with `match` (owner decision D-E).
Money is `float64` in a currency-tagged wrapper; the single project tolerance is imported,
never redefined.

Two rules govern everything below. **A number that was not found does not become a field**
(research.md D8) — it becomes a declared question. And **a number the fund states about
itself is marked fund-stated and unverified**, and every figure derived from it inherits the
mark.

---

## Dated tax schedules

### `RateEntry` — `core/tax/schedule.py`

| Field | Type | Meaning |
|---|---|---|
| `effective_from` | `date` | Exactly the date this entry's citation attests (research.md D2) |
| `pit_rate` | `float` | Fraction, not percent — converted once at the loader boundary |
| `levy_rate` | `float` | Fraction |
| `provenance` | `Provenance` | **Per entry**, not per class: two rates cited by two sources are two observations |

### `TaxClass` — changed

| Field | Change |
|---|---|
| `rates` | **new** — `tuple[RateEntry, ...]`, sorted by `effective_from`, non-empty |
| `pit_rate_pct`, `levy_rate_pct` | **removed** — not deprecated (research.md D1) |
| `id`, `applies_to`, `note` | unchanged |

Validated at load: at least one entry; strictly increasing effective dates; no duplicates.
Sorting and overlap belong at the loader because that is where the file can be named.

### `RateUndeclaredBefore` — `core/tax/schedule.py`

| Field | Type | Meaning |
|---|---|---|
| `tax_class_id` | `str` | |
| `event_date` | `date` | |
| `earliest_declared` | `date` | What the schedule does start at, so the reader knows what to go and cite |
| `reason` | `str` | |

Returned instead of a rate. No default, no zero silently charged (FR-012).

## The fund instrument

### `FundDeclaration` — `core/instruments/fund.py`

| Field | Type | Meaning |
|---|---|---|
| `id`, `name` | `str` | |
| `unit_currency` | `Currency` | The currency units and NAV are denominated in |
| `is_assumption_driven` | `Literal[True]` | Both funds. Not a bool — there is no `False` case in this feature, and a `Literal` says so (FR-004) |
| `declared_yield` | `DeclaredYield` | The fund-stated rate, marked |
| `distribution` | `DistributionTerms \| None` | `None` for an accumulation fund — MilTech has no dividend obligation, and that is a declared fact, not a missing field |
| `spread` | `SpreadTerms` | Entry markup and exit discount around NAV (FR-024) |
| `liquidity` | `LiquidityTerms` | Both modes, kept distinguishable |
| `minimum_units` | `float` | |
| `subscription_cutoff` | `date \| None` | |
| `terminates_on` | `date` | |
| `tax_classes` | `Mapping[str, str]` | Event kind to class id — 001's mapping, now with two distinct values (FR-006) |
| `fee_context` | `tuple[FeeFact, ...]` | Researched fee facts as **provenance context** for the declared yield, never modelled flows (research.md D9) |
| `verification_tasks` | `tuple[VerificationTask, ...]` | What the documents did not answer (research.md D8) |

### `DeclaredYield`

| Field | Type | Meaning |
|---|---|---|
| `low`, `high` | `float` | Equal for a point rate; different for MilTech's 25–29% |
| `basis` | `Literal["simple_annual", "usd_equivalent_annual"]` | |
| `provenance` | `Provenance` | Fund-stated, `verified_on` empty |

A projection over a range either reports a range or takes an explicitly declared point
labelled the owner's assumption. **There is no midpoint helper** — that absence is the
requirement (research.md D11).

### `DistributionTerms`

| Field | Type | Meaning |
|---|---|---|
| `frequency` | `Literal["monthly"]` | |
| `basis_note` | `str` | "at least 90% of net rental profit" — declared, not computed |
| `record_day`, `payment_day` | `int` | Last day of month; by the 10th following |
| `paid_in` | `Currency` | UAH |
| `peg` | `Peg \| None` | |

### `Peg`

| Field | Type | Meaning |
|---|---|---|
| `sized_in` | `Currency` | USD — the currency the amount is *sized* in |
| `cap` | `tuple[CapEntry, ...]` | The leases' «граничний курс», dated, declared-but-unverified |

**A pegged amount is never a `Money`** until an `ExchangeRateAssumption` sizes it
(research.md D7). The type refuses the conflation; a reviewer does not have to catch it.

### `ExchangeRateAssumption`

| Field | Type | Meaning |
|---|---|---|
| `rate` | `float` | UAH per USD |
| `is_assumption` | `Literal[True]` | Carried where an observation carries a source, on `RegimeTransition`'s precedent |
| `rationale` | `str` | |

### `SpreadTerms`

| Field | Type | Meaning |
|---|---|---|
| `entry_markup_max`, `exit_discount_max` | `float` | Up to 1% of NAV each |
| `live_entry_markup`, `live_exit_discount` | `float` | The settings believed live, **unverified** |
| `provenance` | `Provenance` | Including FR-024's recorded arithmetic observation |

### `LiquidityTerms`

| Field | Type | Meaning |
|---|---|---|
| `legal` | `LegalTerms` | No obligation before termination; discretionary buyback; max discount; settlement delay |
| `practice` | `ObservedPractice` | Buyback at NAV, same day, zero commission — **a revocable company practice**, own citation, empty verification date |

Two records rather than one with a mode flag, because they are two different kinds of claim:
one is what the регламент owes, the other is what the company currently does.

### `FeeFact`, `VerificationTask`

| `FeeFact` | |
|---|---|
| `what` | `str` — "management fee up to 2%/yr of NAV, accrued 1/12 monthly" |
| `provenance` | `Provenance` |

| `VerificationTask` | |
|---|---|
| `question` | `str` — what is unknown |
| `searched` | `str` — which document was read |
| `searched_on` | `date` |

`VerificationTask` carries **no value field**. That is the point: there is nowhere for a
number to be put by a later contributor in a hurry.

## Results

### `FundProjection` — `core/results/fund.py`

| Field | Type | Meaning |
|---|---|---|
| `instrument_id` | `str` | |
| `liquidity_mode` | `LiquidityMode` | Stated, always (FR-016) |
| `tax_by_class` | `tuple[ClassSubtotal, ...]` | Per-class subtotals — which class charged what (FR-007) |
| `distributions` | `tuple[DistributionLine, ...]` | Each with the rate entry applied and its date |
| `entry_spread`, `exit_spread` | `Money` | Own lines; round-trip erosion its own figure (FR-024) |
| `exit_discount` | `Money \| None` | Its own line under legal terms (FR-018) |
| `peg_statement` | `str \| None` | The peg and the cap, restated in the output (FR-020) |
| `yield_basis` | `DeclaredYield \| ChosenPoint` | A range, or a point labelled the owner's assumption |
| `excludes` | `str` | Funding and exit route costs — the comparison's stated boundary (FR-025) |
| `provenance` | `Provenance` | Every fund-stated input's mark, propagated |

**No `volatility`, no `sharpe`, no `sortino`, and no field one could live in** (research.md
D10). The refusal is structural.

**No computed fee** (research.md D9). Same reasoning.

### Typed refusals — `core/results/fund.py`

| Record | When |
|---|---|
| `RedemptionRefused` | Legal terms, buyback declared unavailable — names the termination date as the next guaranteed exit; the lot stays open (FR-017) |
| `PurchaseAfterCutoff` | Names the cutoff (FR-019) |
| `MetricRefused` | An assumption-driven instrument was asked for a statistical metric (FR-005) |
| `PegUnsizable` | No `ExchangeRateAssumption` declared — names exactly which input is missing (FR-021) |
| `AwaitingVerification` | A projection needed a value recorded only as a `VerificationTask` — names the task (research.md D8) |
| `RateUndeclaredBefore` | Above (FR-012) |

Each carries its reason, and the reason reaches the output. None is an exception: `raise` is
for programmer errors.

## What is deliberately absent

- **No modelled fund-internal profitability** — no fee accrual, no performance fee, no
  coupon reinvestment of the underlying bonds (FR-023, owner decision B).
- **No statistical metric** for either fund, and no field for one.
- **No invented rate-fixing rule and no invented cap value** — those are
  `VerificationTask`s.
- **No loss carryforward** — a disposal at a loss charges exactly zero and says
  carryforward is not modelled here (FR-008); it is feature 009's.
- **No FX attribution** — the peg is stated, not decomposed. A later feature.
