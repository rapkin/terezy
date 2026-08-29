# Phase 1 data model: the official rate

**Feature**: `011-official-rate` | **Spec**: [spec.md](./spec.md) | **Decisions**: [research.md](./research.md)

Every record is a frozen dataclass carrying only data; every operation is a free function in
the module beside it (owner decision D-E). New core module: `terezy.core.tax.official_rate`.

## Records

### `OfficialRateObservation`

| Field | Type | Notes |
|---|---|---|
| `on_date` | `date` | The date this rate is the official rate *for*. |
| `value` | `float` | Strictly positive. Units of the pair's price currency per `quotation_unit` units of its unit currency. |
| `provenance` | `Provenance` | One `SourceRef`, with `kind` stamped by the loader (research D5). No `kind` field on this record. |

### `NonPublicationDay` and `NonPublicationRule`

| Field | Type | Notes |
|---|---|---|
| `NonPublicationDay.applies_to` | `date` | A date the publisher does not publish for. |
| `NonPublicationDay.governed_by` | `date` | The declared observation whose rate governs it. |
| `NonPublicationRule.id` | `str` | Named so the output can say which rule applied. |
| `NonPublicationRule.days` | `tuple[NonPublicationDay, ...]` | An explicitly enumerated mapping. No calendar (research D8). |
| `NonPublicationRule.provenance` | `Provenance` | Its own citation, required and non-empty (FR-011). |

### `OfficialRateSeries`

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Unique across the data root; a collision names both files. |
| `authority` | `str` | Who publishes it. |
| `pair` | `tuple[Currency, Currency]` | `(price, unit)`, `FxChannel.pair`'s convention. Converts `unit → price` only (research D10). |
| `quotation_unit` | `float` | Strictly positive. Declared, never defaulted (FR-002). |
| `rule` | `NonPublicationRule \| None` | `None` is the Ukrainian series and means FR-010's refusal stands. |
| `observations` | `tuple[OfficialRateObservation, ...]` | Strictly ascending by date, gaps permitted, **empty permitted** (research D6). |

### `TaxCurrencyConversion` — the record of one base being struck

| Field | Type | Notes |
|---|---|---|
| `amount` | `Money` | What was converted. |
| `base` | `Money` | The struck base, in the tax currency. |
| `series_id` | `str` | FR-016. |
| `pair` | `tuple[Currency, Currency]` | |
| `event_date` | `date` | The date the taxable event carries (FR-008). |
| `rate_date` | `date` | The observation's own date. Differs from `event_date` only when a rule applied. |
| `applied_rule` | `str \| None` | The rule id, or `None` when the event's own date is declared. |
| `rate` | `float` | The declared value. |
| `quotation_unit` | `float` | So the base is re-derivable on paper: `base = amount * rate / quotation_unit`. |

Provenance is not a field: it lives on `base`, where `money.convert` put it, unioned from the
amount's own sources and the rate observation's. A second copy would be a second place for
one fact and the one that drifts.

## Refusals

`OfficialRateUnavailable = OfficialRateSeriesUnavailable | OfficialRateUndeclaredOnDate`

| Record | Fields |
|---|---|
| `OfficialRateSeriesUnavailable` | `wanted: tuple[Currency, Currency]`, `series_id: str \| None`, `quotes: tuple[Currency, Currency] \| None`, `reason: str` |
| `OfficialRateUndeclaredOnDate` | `series_id`, `pair`, `on_date`, `covers: tuple[date, date] \| None`, `reason` |

`covers` is the declared window, `None` for a series with no observations, so a refusal can
say *before the first*, *after the last*, *inside a gap* or *nothing is declared at all*
without the reader opening a file.

The two do not carry the same list, and the difference is the point: only
`OfficialRateUndeclaredOnDate` can name a series and a date. A jurisdiction that declared no
series has neither, and says so.

## Functions

```python
def strike_base(
    amount: Money,
    series: OfficialRateSeries,
    *,
    tax_currency: Currency,
    on_date: date,
) -> TaxCurrencyConversion | OfficialRateUnavailable
```

Raises `ValueError` when `amount.currency is tax_currency`: an event already in the tax
currency must not consult a rate at all (FR-009), so the caller checks first and this
function makes the mistake unrepresentable rather than answering it.

```python
def observation_for(series, on_date) -> tuple[OfficialRateObservation, str | None] | None
def covered_window(series) -> tuple[date, date] | None
def provenance_of(series) -> Provenance          # every observation's citation, and the rule's
```

## Changes to existing records

| Record | Change | Why |
|---|---|---|
| `tax.year.AssessmentRules` | `+ official_rate: OfficialRateSeries \| None` | The jurisdiction that declares its tax currency declares the series that serves it (FR-007). `None` is a declared absence and refuses by name. |
| `tax.year.ChargeRef` | `+ conversion: TaxCurrencyConversion \| None` | FR-016: the struck base names its series, date, rate and unit where a reader of the statement meets it. `None` for a result already in the tax currency (FR-009, SC-010). |
| `tax.year.TaxCurrencyConversionUnavailable` | `+ unavailable: OfficialRateUnavailable` | The refusal carries the typed reason rather than only the two currencies. What that reason can name differs by variant — see above. |
| `tax.year.ForeignGainNotStruckPerDate` | new member of `TaxYearRefused` | research D3. |

Feature 001's `TaxCharge` and `TaxClass`, `Money`, `Provenance`, `SourceRef` and 002's
`FxChannel` and `Leg` are **unchanged**.

## Declaration shape

`data/official_rates/<authority>_<pair>.toml`:

```toml
[series]
id             = "ua_nbu_usd"
authority      = "Національний банк України"
pair           = ["UAH", "USD"]
quotation_unit = 1.0

# [non_publication_rule] is optional and is absent for Ukraine (FR-017).
# [[non_publication_rule.day]] rows are applies_to / governed_by pairs.

[[observation]]
on_date      = "2026-08-24"
value        = 41.1234
kind         = "official_rate"
source       = "..."
retrieved_on = "2026-08-24"
verified_on  = ""
```

`data/tax/timing/<jurisdiction>.toml` gains one optional key beside `tax_currency`:

```toml
[timing]
jurisdiction        = "ua"
tax_currency        = "UAH"
official_rate_series = "ua_nbu_usd"
```

`data/observation_kinds.toml` gains `official_rate`, 7 days (research D9).

## Load-time failures (FR-004, SC-004)

Named field or date in every message, no default substituted for anything:

malformed value · unrecognised field · missing required field · duplicate `on_date` ·
observations out of order · non-positive `value` · missing or non-positive `quotation_unit` ·
an `on_date` later than its own `retrieved_on` · a two-sided observation (`buy_side` /
`sell_side` are unrecognised fields, so `extra="forbid"` is the mechanism) · duplicated series
id across files · a rule whose `governed_by` names no declared observation · a rule whose
`applies_to` names a date the series does publish for · a rule with no citation ·
`official_rate_series` naming a series no file declares · a series whose price currency is not
the jurisdiction's tax currency.
