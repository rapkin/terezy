# Phase 1 data model: 001-ovdp-hurdle-rate

**Date**: 2026-08-21

Entities, their fields, and the validation rules each one enforces. Core types are plain
frozen dataclasses; nothing here imports a validation framework. Field types are given in
Python notation for precision, but the *rules* are the point — they trace back to spec
requirements, which are cited throughout.

---

## Primitives

### `Currency`

A closed enumeration. `UAH` and `USD` exist; only `UAH` is used by this feature.

Enumerated rather than a free string so that a typo is a load-time failure instead of a
silently distinct currency that never matches anything (FR-016).

### `SourceRef`

One cited origin for one or more observed values.

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Stable, unique within a run. Derived from the declaring file and table so a figure can be traced back to where it was declared. |
| `citation` | `str` | Non-empty. A URL or document reference. |
| `retrieved_on` | `date` | Required. |
| `verified_on` | `date \| None` | `None` means not verified against a primary source. **Permitted and expected**; the key may not be absent from the declaration (FR-014). |

`is_verified` is `verified_on is not None`.

### `Provenance`

A frozenset of `SourceRef`, with union as its combining operation — a commutative monoid
with the empty set as identity. This is the mechanism by which FR-015 becomes structural
rather than remembered.

| Member | Behaviour |
|---|---|
| `sources` | `frozenset[SourceRef]` |
| `\|` (union) | Combines two provenances. Associative and commutative, so evaluation order cannot change the mark. |
| `is_unverified` | `True` if **any** source has `verified_on is None`. One unverified input taints the result — that is the intended asymmetry. |
| `unverified_sources` | The specific sources responsible, so the mark can name *why*. |

`Provenance.EMPTY` is the identity, used for literals that came from no source (a zero, a
count).

### `Money`

| Field | Type | Rule |
|---|---|---|
| `amount` | `float` | float64, per owner decision D-A. |
| `currency` | `Currency` | Always present. |
| `provenance` | `Provenance` | Excluded from equality — `field(compare=False)`. |

Rules:

- **Currency safety (FR-007, C5).** `+`, `-` and ordering comparisons between different
  currencies raise `CurrencyMismatchError`. There is no implicit conversion anywhere, and
  no operator that performs one.
- **Provenance union (FR-015, E5).** Every arithmetic operation returns money whose
  provenance is the union of its operands'. Multiplication by a scalar preserves
  provenance; multiplication by money is not defined (money × money is not money).
- **Equality ignores provenance.** Two amounts equal in value are equal regardless of the
  path that produced them. Without this, the conservation invariants would fail for
  reasons unrelated to conservation.
- **Equality is exact, and is not the financial comparison.** Because money is float,
  tests compare through the tolerance helpers, never `==`.
- Frozen and hashable.

### `TOLERANCE` — the single tolerance

Lives in `core/primitives/tolerance.py` and is the **only** tolerance in the project
(FR-002). Exports the constant plus `is_close(a, b)` and `assert_money_close(a, b)`,
which also assert currency equality so a tolerance check cannot accidentally compare
across currencies.

A comparison needing a looser bound states why at the assertion site. A comparison that
defines its own constant is a defect.

### `NominalRate` / `RealRate` / `RealTermsUnavailable`

Three distinct types, so that assigning a nominal figure into a real slot is a **mypy
strict error** rather than a runtime mistake (FR-022, SC-011, decision D4).

`RealTermsUnavailable` carries `reason: str` — populated with the fact that inflation is
not modelled in this feature — satisfying FR-017's requirement that a degraded outcome
carry its reason.

### Conventions

Three named registries, mapping a declared name to an implemented algorithm.

| Registry | Values this feature implements |
|---|---|
| `DayCount` | `act/365`, `act/act`, `30/360` |
| `Periodicity` | `annual`, `semiannual`, `quarterly` |
| `BusinessDayRule` | `following`, `modified_following`, `none` |

An unrecognised name is a load-time failure naming the file and the value (FR-021). The
*choice* is data; the *algorithm* is code — see research.md for why that is not a
Principle II violation.

---

## Declared knowledge

### `TaxClass`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique across all tax files. A duplicate is a load-time failure. |
| `applies_to` | `frozenset[TaxableEventKind]` | Non-empty. `coupon`, `disposal_gain`, `distribution`, `interest`. |
| `pit_rate` | `float` | Fraction, not percent, once loaded. `0.0` for the exempt class. |
| `levy_rate` | `float` | Fraction. `0.0` for the exempt class. |
| `provenance` | `Provenance` | Required. A rate without a citation cannot be loaded — including a **zero** rate. |

The zero rate needing a citation as much as a non-zero one is deliberate: the exemption
is the single most decision-relevant number in the model (spec §4.5), and an uncited
zero is exactly the kind of value that gets believed without checking.

### `BondTerms`

The contractual terms from which the schedule is computed in closed form.

| Field | Type | Rule |
|---|---|---|
| `face_value` | `Money` | Positive. |
| `coupon_rate` | `float` | Fraction of face per annum. Non-negative; zero is a valid zero-coupon bond. |
| `issue_date` | `date` | |
| `maturity_date` | `date` | **Strictly after** `issue_date` and after any purchase date, else a typed failure (spec edge case). |
| `periodicity` | `Periodicity` | |
| `day_count` | `DayCount` | |
| `business_day_rule` | `BusinessDayRule` | |
| `provenance` | `Provenance` | Required. |

### `InstrumentDeclaration`

| Field | Type | Rule |
|---|---|---|
| `id` | `str` | Unique across all instrument files. |
| `name` | `str` | Non-empty. |
| `instrument_class` | `str` | `fixed_income` for this feature. |
| `currency` | `Currency` | |
| `is_synthetic` | `bool` | **Required, no default.** `True` marks a test fixture whose terms are invented rather than observed. Making it required rather than defaulting to `False` means a real issue cannot be mistaken for a fixture through omission. |
| `terms` | `BondTerms` | |
| `constraints` | `InstrumentConstraints` | |
| `tax_classes` | `dict[TaxableEventKind, str]` | Maps event kind to tax-class id. **Plural by design** — the same instrument is taxed differently on distribution and on disposal (spec §4.1). Every referenced id must resolve, else a load-time failure. |

### `InstrumentConstraints`

| Field | Type | Rule |
|---|---|---|
| `min_ticket` | `Money` | Positive. A purchase below it is infeasible, reported with the shortfall, never rounded (FR-018). |
| `min_unit` | `float` | Smallest buyable increment. Governs the unreinvestable coupon remainder (FR-020). |
| `provenance` | `Provenance` | Required — separate from `terms`, because a minimum ticket and a yield are different facts from different sources. |

---

## Ledger

### `Event`

One dated, typed thing that moved money or changed a holding. The audit trail behind
every figure (FR-008).

| Field | Type | Rule |
|---|---|---|
| `sequence` | `int` | Monotonic, assigned on append. Makes the fold order explicit rather than dependent on sort stability. |
| `occurred_on` | `date` | |
| `kind` | `EventKind` | `purchase`, `coupon`, `principal_repayment`, `tax_charge`, `reinvestment`, `cash_deposit`. |
| `amount` | `Money` | Carries its own provenance. |
| `owner_id` | `str` | Present from day one per Principle VII, though there is one owner and no auth. |
| `caused_by` | `CausationRef` | The instrument term or tax rule that produced this event. **This field is what makes C6 satisfiable** — traceability is a stored fact, not a reconstruction. |
| `lot_ref` | `LotRef \| None` | Set where the event touches a specific lot. |

### `Lot` / `Position`

| Field | Type | Rule |
|---|---|---|
| `Lot.quantity` | `float` | Strictly positive. A lot may not exist at zero. |
| `Lot.acquired_on` | `date` | |
| `Lot.cost_trade_ccy` | `Money` | Cost in the instrument's own currency. |
| `Lot.cost_base_ccy` | `Money` | Cost in the base currency. Equal in this feature — both are UAH — but stored separately because the field's whole purpose is the case where they differ. |
| `Lot.fx_rate_used` | `float \| None` | `None` when trade and base currency coincide. |

`Position` invariants, asserted as properties over generated event streams:

- **C2** — `sum(lot.quantity) == position.quantity`; no lot ever goes negative; a
  disposal consumes lots by the configured method.
- **C3** — `sum(lot.cost) == position.basis`; on disposal,
  `realised_gain == proceeds − consumed_basis − allocated_fees`, computed in **both**
  currencies.

### `CashAccount`

Per-currency balances. **C1**: for each currency, on every date,
`Σ inflows − Σ outflows == balance`. Asserted daily across the whole projection, not only
at the end — an error that cancels out by the final date is still an error.

### `canonical_tuple()`

A structural representation for the determinism check: nested tuples of primitives, with
amounts as `float.hex()`. No serialisation, no hashing — those live in `data`.

**Provenance is deliberately excluded.** It identifies sources, so filling in a
`verified_on` later would change the digest even though no computed amount moved, and C4
would fail on a documentation update. The unverified mark is asserted separately by E5.

---

## Results

### `CashFlowSchedule`

The dated sequence a holding will pay: for each row, the date, the gross amount, the tax
charged, the net amount, and the convention that placed the date (FR-021). Derived from
ledger events, never computed alongside them.

### `HurdleRate`

| Field | Type | Rule |
|---|---|---|
| `nominal_ytm` | `NominalRate` | Contractual yield to maturity. |
| `nominal_cash_flow_return` | `NominalRate` | Cash-flow-weighted. Kept separate from the yield and separately labelled; neither substitutes for the other (FR-005). |
| `real` | `RealRate \| RealTermsUnavailable` | Always `RealTermsUnavailable` in this feature, carrying its reason. Present and explicitly empty — never absent (SC-011). |
| `total_tax` | `Money` | Exactly zero for the exempt class (SC-002). |
| `excludes` | `frozenset[str]` | What this figure does **not** account for: route costs, exit costs, inflation. Principle VI forbids presenting a per-instrument access cost, so the figure states its own boundaries rather than leaving a later reader to assume it is comparison-ready. |
| `provenance` | `Provenance` | Unioned from everything upstream. `is_unverified` is `True` while the yield is unverified. |

### Failure results

Every degraded outcome is one of these, never an exception swallowed or a zero (FR-017):

| Type | Carries |
|---|---|
| `InfeasiblePurchase` | The constraint violated, the required value, the actual value, the shortfall |
| `InconsistentTerms` | Which two terms conflict and how |
| `UnresolvedTaxClass` | The missing class id and the instrument that referenced it |
| `RealTermsUnavailable` | Why the real figure is absent |
| `DeclarationError` | File path, field path, and what was wrong (`data` layer) |
