# Data model: the ФОП group 3 regime

**Feature**: `012-fop-group-3` | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)

Every record is `@dataclass(frozen=True, slots=True, kw_only=True)` unless it is an `Enum`.
Free functions beside them, no methods, tagged unions matched with `match` (owner decision
D-E). New core code lives in two modules: `src/terezy/core/tax/scheme.py` for the scheme and
its destinations, and `src/terezy/core/streams/capacity.py` for the deployable figure and its
two records. `src/terezy/core/streams/streams.py` keeps the declaration itself, and the split
is mandatory rather than tidy — [research D14](./research.md) and `capacity.py`'s own
docstring say which contract makes it so.

---

## 1. The scheme

```
Verdict(Enum)                 INTERPRETED = "interpreted" | UNSETTLED = "unsettled"
DeclaredFor                   Literal["stream", "reading"]
Period                        Literal["month"]
```

| Record | Fields |
|---|---|
| `ComponentRate` | `effective_from: date`, `rate: float`, `provenance: Provenance` |
| `ComponentAmount` | `effective_from: date`, `amount: Money`, `provenance: Provenance` |
| `DeclaredContext` | `id: str`, `statement: str`, `not_applied_because: str`, `provenance: Provenance` |
| `RateComponent` | `id: str`, `name: str`, `schedule: tuple[ComponentRate, ...]`, `context: tuple[DeclaredContext, ...]` |
| `PeriodicComponent` | `id: str`, `name: str`, `period: Period`, `schedule: tuple[ComponentAmount, ...]`, `context: tuple[DeclaredContext, ...]` |
| `TaxationScheme` | `id`, `name`, `jurisdiction_id`, `tax_currency: Currency`, `variant: str`, `reporting_cadence: str`, `declared_for: DeclaredFor`, `rate_components: tuple[RateComponent, ...]`, `periodic_components: tuple[PeriodicComponent, ...]` |

`name` on a component is **the name the law uses** (FR-006). `id` is the handle a declaration
refers to. Nothing in the engine compares either against a literal.

`DeclaredContext` is FR-008a's shape and the reason it is a record rather than a note: a
cited fact recorded **on the component it belongs to** and deliberately **not applied**. It
carries why it is not applied, so a reader is never left to infer that the omission was an
oversight. Two are declared today — the ФОП levy's event-conditioned termination, and the
ordinary-personal-income levy's event-conditioned reversion — and neither moves a figure.

**Validation, all at the data boundary where the file can be named:**

- a scheme declares at least one component of either kind; a scheme charging nothing is a
  declaration nobody meant to write
- component ids unique within a scheme; scheme ids unique across the data root
- every schedule non-empty, strictly ascending by `effective_from`, never sorted for the file
- `rate_pct` and `amount` non-negative — a negative charge is a refund, and no source here
  declares one
- `tax_currency` a declared currency; `period` and `declared_for` closed sets resolved
  through `loader._closed_value`
- every rate entry, amount entry and context entry carries `kind`, `source`, `retrieved_on`
  and a present (possibly empty) `verified_on`

## 2. What a scheme charges

| Record | Fields |
|---|---|
| `ComponentCharge` | `component_id`, `name`, `rate: float`, `charged: Money`, `effective_from: date`, `provenance` |
| `SchemeCharge` | `scheme_id`, `base: Money`, `on_date: date`, `conversion: TaxCurrencyConversion \| None`, `lines: tuple[ComponentCharge, ...]`, `total: Money`, `provenance` |
| `PeriodicCharge` | `scheme_id`, `component_id`, `name`, `period: str`, `charged: Money`, `effective_from: date`, `provenance` |

`SchemeCharge.total` is `money.total` over the component lines — a **sum of two amounts**, and
never a blended percentage. There is no combined-rate field anywhere in this model, which is
FR-005 made unrepresentable rather than promised.

`conversion` is `None` exactly when the arrival was already in the tax currency (011 FR-009),
and otherwise is 011's own `TaxCurrencyConversion`, consumed unchanged: it carries the
foreign amount, the credit date, the observation's date, the rate, the quotation unit and any
applied non-publication rule. **The foreign arrival is not copied into a second field** — it
is `conversion.amount`.

### Refusals

| Record | Fields | Fires when |
|---|---|---|
| `ComponentRateUndeclaredBefore` | `scheme_id`, `component_id`, `component_name`, `on_date`, `earliest_declared: date`, `reason` | income dated before a rate component's earliest entry (FR-008, 006 FR-012) |
| `TaxBaseUnavailable` | `scheme_id`, `on_date`, `amount: Money`, `unavailable: OfficialRateUnavailable`, `reason` | no declared official rate covers the credit date (FR-011, US1 scenario 3) |
| `PeriodicAmountNotInForce` | `scheme_id`, `component_id`, `name`, `period: str`, `earliest_declared: date`, `reason` | a declared periodic component has no amount in force for the period (FR-021) |
| `ComponentNotDeclared` | `scheme_id`, `component_id`, `reason` | a component this scheme does not declare at all (FR-020) |

```
type SchemeChargeRefused = ComponentRateUndeclaredBefore | TaxBaseUnavailable
```

`TaxBaseUnavailable.unavailable` is 011's union, carried **whole**: `OfficialRateUndeclaredOnDate`
already names the series, the pair, the date, the covered window and the two remedies, and
restating any of those would be a second place for one fact. `TaxBaseUnavailable.reason` adds
only what 011 cannot know — which scheme was charging, and into which currency.

**The three nils** (FR-020, SC-011) are three return types of one function:

```
component_standing(scheme, component_id, *, on_date, period) ->
      ComponentNotDeclared            "this scheme charges no such component"
    | ComponentRate  (rate 0.0)       "declared, and it comes to nothing"  <- carries provenance
    | ComponentAmount (amount 0)      idem, for a periodic component
    | ComponentRateUndeclaredBefore   "declared, nothing in force"
    | PeriodicAmountNotInForce        idem
```

`component_standing` answers *what is declared and in force*; the charge functions answer
*what was charged*. Keeping the two questions apart is what lets the first be asked about a
component the scheme never mentions — the state that has no charge to look at.

A zero carries the citation of the entry that produced it exactly as a non-zero value does.
The ЄСВ nil the owner declares is the second row, and its citation is his own statement.

## 3. Where the income is credited

| Record | Fields |
|---|---|
| `Reading` | `id`, `label`, `scheme_id: str \| None`, `uncomputable_because: str \| None`, `recognised_on: str \| None`, `departs_from_source: str \| None`, `provenance` |
| `CreditingDestination` | `scheme_id`, `venue_id`, `verdict: Verdict`, `grounds: str`, `resolution_path: str`, `readings: tuple[Reading, ...]`, `provenance` |

A `Reading` declares **exactly one** of `scheme_id` or `uncomputable_because`, checked at
load (research D11). `recognised_on` is a **declared date name** — a string the engine never
compares against a literal — and is present exactly when `scheme_id` is.

`departs_from_source` is SC-017a's field: where this system deliberately computes something
other than what the cited source computes, the divergence is declared beside the reading and
rendered on the figure. Exactly one reading declares one today, and a contract test pins that
the figure carries it.

`grounds` is the row's recorded judgement — the spec's normative table, one cell per row, in
the file rather than in prose. `resolution_path` is what closes the question, which for every
UNSETTLED row here is an індивідуальна податкова консультація of the owner's own (ст. 52 ПКУ).

**Validation:**

- a row is keyed `(scheme_id, venue_id)`; a second row for the same pair is a load failure
  naming both files
- `scheme_id` and every reading's `scheme_id` must resolve to a declared scheme
- `venue_id` must resolve to a declared venue
- `verdict = "interpreted"` ⇒ exactly one reading, and it must be computable. An INTERPRETED
  row is a charge, and a charge with no candidate is a contradiction
- `verdict = "unsettled"` ⇒ at least one reading, and `resolution_path` non-empty
- `grounds` non-empty on every row: a verdict with no recorded reasoning is the row the
  spec's own register exists to prevent

## 4. What applying a destination produces

| Record | Fields |
|---|---|
| `ChargedUnderTheScheme` | `venue_id`, `declared_treatment`, `reading_id`, `charge: SchemeCharge`, `grounds`, `provenance` |
| `ReadingFigure` | `reading_id`, `label`, `scheme_id`, `recognised_on: str`, `charge: SchemeCharge`, `departs_from_source: str \| None`, `not_the_tax_owed: str`, `provenance` |
| `UncomputableCandidate` | `reading_id`, `label`, `because: str` |
| `UnsettledDestination` | `venue_id`, `declared_treatment`, `grounds`, `resolution_path`, `figures: tuple[ReadingFigure, ...]`, `uncomputable: tuple[UncomputableCandidate, ...]` |

`declared_treatment` is the scheme the income was **asked about**; what actually charged is
`charge.scheme_id` on the figure. They are two names because an interpreted row may answer
that income under one scheme, credited somewhere, is charged under another — and a charge
labelled with a scheme that did not produce it is the shape a reader cannot detect.

**`UnsettledDestination` has no `Money` field, no `total`, no `mean` and no `range`.** There
is nowhere for a blended number to live, and the test that says so enumerates
`dataclasses.fields` rather than trusting this sentence.

**`ChargedUnderTheScheme` and `ReadingFigure` are unrelated records.** Neither can be assigned
into the other's slot without a mypy strict error. The type that means *the tax owed* is the
first, and only an INTERPRETED destination produces one; a switch holds only the second, and
every one of them carries `not_the_tax_owed` in its own words.

### Refusals

| Record | Fields |
|---|---|
| `RefusedState(Enum)` | `NO_DECLARED_JUDGEMENT = "no_declared_judgement"`, `NO_CANDIDATE_IS_COMPUTABLE = "no_candidate_is_computable"` |
| `CreditingDestinationRefused` | `venue_id`, `declared_treatment`, `state: RefusedState`, `uncomputable: tuple[UncomputableCandidate, ...]`, `reason` |
| `ReadingDateUndeclared` | `scheme_id`, `reading_id`, `recognised_on`, `declared: tuple[str, ...]`, `reason` |
| `ReadingRefused` | `venue_id`, `scheme_id`, `reading_id`, `label`, `because: SchemeChargeRefused \| ReadingDateUndeclared`, `reason` |

```
type DestinationRefused = CreditingDestinationRefused | ReadingRefused
```

**Two states, where FR-027 names three, and it is deliberate** (research D16). The engine can
see *the table has no row for this destination* and *the row's every candidate is
uncomputable*. It cannot see the difference between *no source reaches it* and *a source
reaches it and the table has not caught it* — that difference is about the world, not about
the data, and SC-013's own note says it is a reader's reclassification. So
`NO_DECLARED_JUDGEMENT` covers FR-027's states 1 and 2, and its `reason` names **both**
closures — find a source, and add the row with its reasoning — rather than asserting which of
the two obtains.

`ReadingRefused` is not `UncomputableCandidate`. A candidate is uncomputable **as a matter of
law-not-declared** and is named on a switch that still stands; a reading refuses because a
rate schedule does not reach the date, or no official rate covers it, or the caller supplied
no date under the name it asked for — and then the whole application refuses. A switch that
quietly dropped a reading would be the defect FR-026's *named on the switch* clause exists to
prevent, wearing the other clause's clothes.

## 5. Functions

```python
# core/tax/scheme.py  -- `apply`'s destination argument is named `credited_to`, and the
# charge's component lines are `lines`, so that
# `tests/contract/test_per_destination_cost_unrepresentable.py`'s access-cost scan does not
# read a tax charge as a corridor's price. That module records the boundary from its side.
rate_in_force(component: RateComponent, on_date: date)      -> ComponentRate | None
amount_in_force(component: PeriodicComponent, period: str)  -> ComponentAmount | None

charge_income(scheme, amount: Money, *, on_date: date,
              series: OfficialRateSeries | None)            -> SchemeCharge | SchemeChargeRefused

charge_period(scheme, component: PeriodicComponent, period: str)
                                                            -> PeriodicCharge | PeriodicAmountNotInForce
charge_periods(scheme, window: Window)
       -> tuple[PeriodicCharge | PeriodicAmountNotInForce, ...]

component_standing(scheme, component_id: str, *, on_date: date | None, period: str | None)
       -> ComponentRate | ComponentAmount | ComponentNotDeclared
        | ComponentRateUndeclaredBefore | PeriodicAmountNotInForce

apply(*, scheme_id: str, credited_to: str, amount: Money,
      on_dates: Mapping[str, date],
      schemes: Mapping[str, TaxationScheme],
      destinations: Mapping[tuple[str, str], CreditingDestination],
      series: OfficialRateSeries | None)
       -> ChargedUnderTheScheme | UnsettledDestination | DestinationRefused

base_versus_received(base: Money, received: Money)          -> BaseVersusReceived
```

`BaseVersusReceived(base, received, difference, outside_the_base: str)` — `difference` is
`base − received`, **signed**, because FR-013's exposure points either way and an absolute
value would hide which. `outside_the_base` is the label on the figure's own face.

`charge_income` checks `amount.currency is scheme.tax_currency` **before** touching a series,
because `strike_base` raises on an amount that needs no rate (011 FR-009). That check is the
Edge Case *a stream in the tax currency naming this regime*, and it is why a hryvnia stream
never sees a rate-unavailable reason.

## 6. The stream, after the migration

```python
IncomeStream:  id, owner_id, amount, cadence, arrives_at, credited_to, indexation, tax_scheme
```

- `income_tax_rate: float | None` is **removed** (FR-015).
- `tax_scheme: str | None` — the declared treatment. `None` means the owner has named none,
  which is not a treatment charging zero.
- `credited_to: str` — **required**, a declared venue, the tax event's location. Never
  defaulted from `arrives_at` and never defaulting it (FR-024a, research D17).

```python
DeployableCapacity:      stream_id, cadence, charge: SchemeCharge, net: Money
TaxTreatmentUndeclared:  reason, stream_id, gross: Money
deployable(stream, charged: ChargedUnderTheScheme | None)
       -> DeployableCapacity | TaxTreatmentUndeclared
```

`gross` is `charge.base` and `charged` is `charge.total`; neither is copied into a field of
its own. All three of `gross`, `charged` and `net` are in the **tax currency**, and the
arrival that produced them is `charge.conversion.amount` (research D14).

`TaxTreatmentUndeclared` carries **no net field at all**, which is the guarantee rather than a
description of one — the same shape, and the same reason, as the record it replaces. Passing a
charge for a stream that names no scheme, or omitting one for a stream that does, is a
programmer error and raises.

## 7. Declaration shapes

### `data/tax/schemes/<id>.toml`

```toml
[scheme]
id = "…"; name = "…"; jurisdiction = "ua"; tax_currency = "UAH"
variant = "…"; reporting_cadence = "quarterly"; declared_for = "stream" | "reading"

  [[scheme.rate_component]]
  id = "…"; name = "…"                       # the name the law uses
    [[scheme.rate_component.rate]]
    effective_from = "YYYY-MM-DD"; rate_pct = 0.0; note = "…"
    kind = "tax_rule"; source = "…"; retrieved_on = "…"; verified_on = ""
    [[scheme.rate_component.context]]        # optional; recorded, never applied
    id = "…"; statement = "…"; not_applied_because = "…"
    kind = "tax_rule"; source = "…"; retrieved_on = "…"; verified_on = ""

  [[scheme.periodic_component]]
  id = "…"; name = "…"; period = "month"
    [[scheme.periodic_component.amount]]
    effective_from = "YYYY-MM-DD"; amount = 0.0; currency = "UAH"; note = "…"
    kind = "tax_rule"; source = "…"; retrieved_on = "…"; verified_on = ""
```

### `data/tax/destinations/<jurisdiction>.toml`

```toml
[[destination]]
scheme = "…"; venue = "…"; verdict = "interpreted" | "unsettled"
grounds = "…"; resolution_path = "…"
kind = "tax_rule"; source = "…"; retrieved_on = "…"; verified_on = ""

  [[destination.reading]]
  id = "…"; label = "…"
  scheme = "…"                 # XOR
  recognised_on = "credited"   # a declared date name; present iff `scheme` is
  # uncomputable_because = "…" # XOR
  # departs_from_source = "…"  # optional
  kind = "tax_rule"; source = "…"; retrieved_on = "…"; verified_on = ""
```

### `data/streams/owner-001.toml`

`income_tax_rate_pct` is removed from the schema entirely — `extra = "forbid"` means a file
still carrying it fails at load naming the key, which is the migration announcing itself
rather than silently ignoring a rate the owner may believe is being applied.
`credited_to` is added and required; `tax_scheme` is added and optional.

## 8. What ships

| File | Holds |
|---|---|
| `data/tax/schemes/ua_fop_group_3.toml` | єдиний податок 5% from 2016-01-01; військовий збір 1% from 2025-01-01 with its termination as recorded context; ЄСВ declared explicitly at zero, sourced to the owner |
| `data/tax/schemes/ua_personal_income.toml` | `declared_for = "reading"`: ПДФО 18% and військовий збір 5% with its reversion as recorded context. **One declaration, consumed by every personal-income reading and copied by none.** Declares no ЄСВ component at all, which is what makes FR-020's *not charged by this scheme* reachable on shipped data |
| `data/tax/destinations/ua.toml` | five rows — the normative table, one row per destination, each with its recorded judgement and its citations |
| `data/venues.toml` | `+ payoneer`, `+ foreign_bank_usd` (research D13) |
| `data/streams/owner-001.toml` | `credited_to` on both streams; `tax_scheme` on `contract_usd` |
