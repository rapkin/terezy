# Data model: the enumerated form

**Feature**: `013-enumerated-schedule` | **Date**: 2026-08-29

Records and their validation rules. Every rule below names the requirement it comes from,
and every one of them fails **at the data boundary** naming the file and the field, except
where it is marked as an `events`-time refusal — a fact about a *purchase* rather than about
a declaration.

---

## Core records

### `PaymentKind` — `core/instruments/interface.py`

An `Enum`. Closed, and the closure is the point: FR-007 says a payment kind determines both
what the ledger records and which income kind the tax layer assesses, and FR-008 says nothing
infers one.

| Member | Ledger movement | Taxable kind |
|---|---|---|
| `coupon` | `EventKind.COUPON` | `TaxableEventKind.COUPON` |
| `principal_repayment` | `EventKind.PRINCIPAL_REPAYMENT` | `TaxableEventKind.DISPOSAL_GAIN` |

One mapping, `PAYMENT_KINDS`, holds both columns. Two mappings could disagree about one
label, and the disagreement would be invisible under the ОВДП exemption, which is the
condition FR-010 names as the one under which a defect ships.

### `ScheduledPayment` — `core/instruments/interface.py`

| Field | Type | Rule |
|---|---|---|
| `on` | `date` | Not before the schedule's `covers_from` (FR-006). |
| `amount` | `Money` | **Per unit**, in the declared currency, in its major units. Strictly positive (FR-006). No unit scaling is ever performed by the engine (FR-004). |
| `pays` | `PaymentKind` | Declared. Missing or unrecognised is a load failure naming the payment (FR-006, FR-008). |

Provenance rides on `amount`, as it does everywhere else in this engine: `Money` carries it,
`money.scale_sourced` propagates it, and a figure derived from a payment therefore inherits
the payment's mark without a second mechanism.

### `EnumeratedTerms` — `core/instruments/interface.py`

| Field | Type | Rule |
|---|---|---|
| `face_value` | `Money` | Per unit, positive. A redemption amount and **nothing else** — not a price (FR-015). |
| `covers_from` | `date` | The date from which the list is complete to the end of the instrument's life. **One-ended by construction** (FR-005): there is no closing field, so a two-ended window is unrepresentable rather than checked for. |
| `payments` | `tuple[ScheduledPayment, ...]` | Non-empty; strictly ascending by `(on, pays)` allowing two kinds on one date; at least one `principal_repayment` (FR-006). Never sorted, merged or deduplicated by the loader. |
| `day_count` | `str` | A key of `conventions.DAY_COUNT_FNS`. **Required** (FR-003a) and an input to annualisation only (FR-003b). |
| `published_in_order` | `tuple[date, ...] \| None` | Present only where the source published the payments in an order other than ascending (FR-020a). A permutation of the payment dates that is not already the ascending one; equal-to-ascending is a load failure, which is what makes SC-018's second half mechanical rather than a matter of habit. |
| `provenance` | `Provenance` | The schedule table's own citation. |

**Absent by construction, not by omission** (FR-003): `issue_date`, `coupon_rate`,
`periodicity`, `business_day_rule`, `maturity_date`. Nothing declares them, nothing defaults
them, and a file that supplies one fails on the unrecognised field (SC-019).

### `InstrumentDeclaration.terms` — the union

```python
terms: BondTerms | EnumeratedTerms
```

This one line is FR-002's mechanism for the terms **only one form declares**. Every existing
`declaration.terms.issue_date`, `.coupon_rate`, `.periodicity`, `.business_day_rule` and
`.maturity_date` stops type-checking, and `mypy --strict` enumerates those sites — the type
checker, not a reviewer.

⚙ **It reaches five of `BondTerms`' seven fields, and the two it does not are the exceptions
that matter.** `day_count` and `face_value` are declared by **both** forms, so a sealed
module reading either directly type-checks and silently stops asking the declaration, and
nothing in the toolchain objects. `face_value` is not hypothetical: reading it in
`core/results/project.py` **was** the F2 defect, a premium measured against the nominal face
of a partly-repaid issue. Both gaps are closed by assertion instead —
`tests/contract/test_no_layer_knows_the_form.py` forbids either read inside the seal, and
`core/instruments/terms.py` offers `day_count_of`, `face_value_of` and `principal_returned`
to ask instead. Recorded here because the union's promise reads as total and is not.

(`provenance` is shared too and is deliberately unsealed: it is the citation rather than a
term, and a results module reading it is what makes a figure traceable.)

### `AmountsAsDeclared` — `core/primitives/conventions.py`

The sibling of `ConventionsApplied`, which moves here from `core/results/schedule.py` (see
research D3).

| Field | Type | Meaning |
|---|---|---|
| `day_count` | `str` | The declared convention. **Its only effect is to annualise.** |
| `reason` | `str` | What the row states in its own words: no periodicity generated this date, no business-day rule moved it, no day count sized this amount — the amount is declared. |

`CashFlowRow.conventions` is typed `ConventionsApplied | AmountsAsDeclared`. FR-016's two
halves are separated deliberately and the record's shape is what keeps them separated: a row
that said *"no day count was applied"* would be false the moment a yield is emitted from the
same projection, and a row that named all three would claim two conventions that never ran.

### `TermsKnownFrom` — `core/instruments/terms.py`

| Field | Type | Meaning |
|---|---|---|
| `on` | `date` | The earliest date this instrument's terms are known from. |
| `term` | `str` | The declared field that states it — what a refusal names as the second of two facts that cannot both hold. |
| `as_declared` | `str` | How to say it in a sentence, so a refusal reads in the form's own words. |

### `PurchasePremium` — `core/results/project.py`

FR-025, FR-026. Always present on a `Projection`, carrying a possibly-zero difference.

| Field | Type | Meaning |
|---|---|---|
| `paid` | `Money` | What was paid, in full, exactly as stated. Nothing is amortised or reclassified (FR-024). Named `paid` rather than `cost`, which `tests/contract/test_cost_labels.py` forbids on a result record. |
| `principal_returned` | `Money` | The repayments this holding will receive, times quantity. **Not `face_value × quantity`** — FR-025 amended 2026-08-30; the two coincide for a bond that repays its face once. |
| `difference` | `Money` | `paid − principal_returned`. Positive is a premium, negative a discount, zero is par and says so. |
| `tax_class_id` | `str \| None` | The class the disposal is taxed under, or `None` where the declaration names none — a different fault from the rules mapping no category to it, and reported as one. |
| `governed_by` | `GovernedBy \| TreatmentUnstated` | The declared category and its treatment — `outside`, `nets`, `per_event` — with what it means for this difference; or a typed statement that the run was given no assessment rules, because those three are different claims and none is assumed. |

## Declaration files

```toml
[instrument]
id           = "ovdp_enumerated_a"
name         = "Synthetic enumerated issue A — TEST FIXTURE, terms invented"
class        = "enumerated_schedule"
currency     = "UAH"
is_synthetic = true

[instrument.schedule]
face_value   = 1000.0
covers_from  = "2026-02-01"
day_count    = "act/365"
kind         = "bond_terms"
source       = "INFERENCE: ..."
retrieved_on = "2026-08-29"
verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2026-07-15"
  amount       = 78.5
  pays         = "coupon"
  kind         = "bond_terms"
  source       = "INFERENCE: ..."
  retrieved_on = "2026-08-29"
  verified_on  = ""

[instrument.constraints]     # unchanged from the generative form
[instrument.tax_classes]     # unchanged from the generative form

[[instrument.verification_task]]
settles     = "face_value"
question    = "..."
searched    = "..."
searched_on = "2026-08-29"
```

**`pays`, not `kind`.** The provenance gate reads `kind` as the *observation* kind a table
ages under, so a payment declaring `kind = "coupon"` would be reported as naming an
undeclared observation kind — a true statement about the wrong field. This is the same trap
`LEG_KIND_KEY` exists for, and the fix follows its precedent: the field is named for what it
is.

### Load-time failures — SC-006's battery

Every one names the file and the offending entry, and none substitutes a default.

| Condition | Requirement |
|---|---|
| Both `[instrument.terms]` and `[instrument.schedule]`, or neither | FR-002 |
| An empty payment list | FR-006 |
| A payment list not in ascending date order | FR-006 (the loader never sorts — FR-020a) |
| A payment dated before `covers_from` | FR-006 |
| A non-positive amount | FR-006 |
| A missing or unrecognised `pays` | FR-006, FR-008 |
| No `principal_repayment` anywhere in the list | FR-006 |
| A declared `maturity_date` (or `issue_date`, `coupon_rate_pct`, `periodicity`, `business_day_rule`) | FR-003, SC-019 |
| A missing `day_count` | FR-003a, SC-019 |
| A `covers_until` — or any second coverage bound | FR-005, SC-021 |
| An income kind the schedule produces with no declared tax class | FR-009 |
| A duplicate instrument id, in either form | FR-006 |
| `published_in_order` equal to the ascending order, or not a permutation of the payment dates | FR-020a, SC-018 |
| An inferred value whose source lacks the inference statement, or with no matching verification task | FR-020, FR-022 (the gate, not the loader) |

### `events`-time refusals — typed, in the existing union

These are facts about a *purchase*, not about a declaration, so they cannot be load
failures.

| Condition | Value | Requirement |
|---|---|---|
| Purchase, or declared opening lot, dated before `covers_from` | `InconsistentTerms`, naming both dates | FR-014, SC-008 |
| Coupon policy `reinvest` | `InconsistentTerms`, naming the missing price and refusing to substitute face | FR-015, SC-009 |
| Horizon ending before the last enumerated payment | `InconsistentTerms` | Edge Cases |
| A purchase dated on or after every payment the schedule declares | `InconsistentTerms` — it receives nothing, so there is no holding to project and no series to yield on | research D6 |
| A purchase after every repayment of principal | `InconsistentTerms` — coupons on a position nothing closes | research D6 |
| A horizon opening after the purchase, or running backwards | `InconsistentTerms` | as the generative form |
| Quantity ≤ 0, cost ≤ 0, cost below the minimum ticket | as the generative form | unchanged |
