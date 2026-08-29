# Quickstart: the official rate and the tax-currency role

## Declare a series

`data/official_rates/<series>.toml`. The `observation` key sits **above** `[series]` because
TOML binds a bare key to the table it follows.

```toml
observation = []          # or omit this line and write [[observation]] rows below

[series]
id             = "xx_official_usd"
authority      = "Who publishes it"
pair           = ["UAH", "USD"]     # price currency, then unit currency
quotation_unit = 1.0                # never defaulted: 100.0 is normal for some currencies
```

Each `[[observation]]` is one date's published rate with its own citation:

```toml
[[observation]]
on_date      = "2026-03-02"
value        = 41.50
kind         = "official_rate"
source       = "https://..."
retrieved_on = "2026-03-02"
verified_on  = ""            # present and empty: nobody has checked it yet
```

Name it from the jurisdiction whose tax currency it serves, in
`data/tax/timing/<jurisdiction>.toml`:

```toml
[timing]
jurisdiction         = "ua"
tax_currency         = "UAH"
official_rate_series = "xx_official_usd"
```

## Strike a base

```python
from terezy.core.tax import official_rate

struck = official_rate.strike_base(
    amount, series, tax_currency=Currency.UAH, on_date=event.occurred_on
)
```

`TaxCurrencyConversion` on success — carrying the series, the rate, **the observation's own
date beside the event's**, and the quotation unit — or `OfficialRateSeriesUnavailable` /
`OfficialRateUndeclaredOnDate`. An amount already in the tax currency raises: it must not
consult a rate at all.

## Declare a non-publication-day rule

Only as an **explicitly enumerated per-date mapping**, and only with a citation of a text
somebody read. A paraphrase is not a citation.

```toml
[non_publication_rule]
id           = "xx_rule"
kind         = "tax_rule"
source       = "..."
retrieved_on = "2026-08-24"
verified_on  = ""

[[non_publication_rule.day]]
applies_to  = "2026-03-07"
governed_by = "2026-03-06"
```

Every `governed_by` must be a declared observation and every `applies_to` must not be; both
are load failures naming the row.

**Do not try to declare the Ukrainian rule.** It is written in working days and public
holidays, which needs a declared, cited calendar this feature does not build — see
`docs/METHODOLOGY.md` §30.5 and `specs/features.toml`'s `declared-working-day-calendar`.

## What refuses, and where to read why

| Question | File |
| --- | --- |
| What is a dollar income worth for tax? | `tests/worked_examples/test_official_rate_base.py` |
| What happens on a date the publisher skipped? | `tests/unit/test_official_rate_refusals.py` |
| Why is a realised gain not converted? | `tests/unit/test_tax_base_in_the_tax_currency.py` |
| Is the tax rate kept apart from the trading rate? | `tests/contract/test_the_rate_you_are_taxed_at.py` |
| Is a second series really data-only? | `tests/contract/test_official_rate_data_only.py` |
