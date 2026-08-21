# Contract: declaration file schema

**Date**: 2026-08-21

The TOML shapes this feature loads, and the rules the loader enforces. This is the
contract between the owner maintaining data by hand and the engine reading it — spec §7
makes the data-entry experience part of the product, so these files are meant to be
readable and editable by a person, not just parseable.

Validated by pydantic v2 in `terezy.data.declarations.schema` with
`ConfigDict(extra="forbid", strict=True, frozen=True)` and **no field defaults**.

---

## Provenance grouping

Provenance sits **per table**, not per scalar. Values that share a source are grouped
into one table carrying `source`, `retrieved_on` and `verified_on` once.

This matches `scripts/check_provenance.py`, which already treats any table containing a
non-structural numeric value as needing a citation. Facts from different sources go in
different tables — a yield and a minimum ticket are separate observations and get
separate provenance.

`verified_on = ""` means unverified. It is **permitted and expected**; the key being
absent is an error (FR-014).

## `data/instruments/<id>.toml`

```toml
[instrument]
id             = "ovdp_synthetic_a"
name           = "Synthetic OVDP issue A — TEST FIXTURE, terms invented"
class          = "fixed_income"
currency       = "UAH"
is_synthetic   = true          # required; no default

[instrument.terms]
face_value          = 1000.0
coupon_rate_pct     = 15.5
issue_date          = "2026-01-15"
maturity_date       = "2028-01-15"
periodicity         = "semiannual"
day_count           = "act/365"
business_day_rule   = "following"
source              = "Synthetic fixture — terms chosen for a hand-checkable example, not observed"
retrieved_on        = "2026-08-21"
verified_on         = ""

[instrument.constraints]
min_ticket   = 1000.0
min_unit     = 1.0
source       = "https://www.inzhur.reit/ — minimum ticket approximately one bond"
retrieved_on = "2026-08-21"
verified_on  = ""

[instrument.tax_classes]
coupon        = "ua_government_bond"
disposal_gain = "ua_government_bond"
```

Notes:

- `coupon_rate_pct` is **percent in the file, fraction in the core.** The suffix is part
  of the field name so the unit is unmissable at the point of editing; the loader divides
  by 100 exactly once, at the boundary. The same applies to every `_pct` field.
- `is_synthetic` is required rather than defaulting to `false`, so a real issue cannot be
  mistaken for a fixture by omission. `true` also makes the fixture obvious in the
  hand-computed test, satisfying the spec's assumption that synthetic terms be marked
  plainly.
- `tax_classes` is a **table, not a scalar** — the same instrument is taxed differently on
  distribution and on disposal (spec §4.1). It carries no provenance because it holds
  references, not observations.

## `data/tax/<jurisdiction>.toml`

```toml
[jurisdiction]
id            = "ua"
name          = "Ukraine (tax resident)"
base_currency = "UAH"

[[jurisdiction.tax_class]]
id            = "ua_government_bond"
applies_to    = ["coupon", "disposal_gain"]
pit_rate_pct  = 0.0
levy_rate_pct = 0.0
note          = "Interest on certain Ukrainian state securities is PIT-exempt; the military levy is not charged on income not subject to PIT."
source        = "https://taxsummaries.pwc.com/ukraine/individual/income-determination"
retrieved_on  = "2026-08-21"
verified_on   = ""
```

The **zero rates carry a citation like any other value.** This is not ceremony: the
exemption is the single most decision-relevant number in the whole model, and an uncited
zero is exactly the sort of figure that gets believed without checking.
`scripts/check_provenance.py` enforces it — `0.0` is numeric, so the table needs a source.

## Enforced rules

Each maps to a spec requirement and to a case in
`tests/contract/test_declaration_loading.py`.

| Rule | On violation | Requirement |
|---|---|---|
| Unrecognised field | Error naming file and field | FR-016 |
| Missing required field | Error naming file and field; **no default substituted** | FR-016 |
| Wrong type — `"15.5"` where a number is expected | Error; `strict=True` means no coercion | FR-016 |
| `verified_on` key absent | Error. Empty string is fine; absence is not | FR-014 |
| Table with numeric values but no `source`/`retrieved_on` | Error | FR-014 |
| Duplicate `id` across files | Error naming both files | FR-016 |
| `tax_classes` referencing an undeclared class | Error naming the missing id and the referring instrument | FR-016, spec edge case |
| Unknown `day_count` / `periodicity` / `business_day_rule` | Error naming file and the unrecognised value | FR-021 |
| `maturity_date` on or before `issue_date` | Typed `InconsistentTerms` failure | Spec edge case |
| Non-positive `face_value`, `min_ticket` or `min_unit` | Error | Spec edge case |
| Malformed TOML | Error naming the file | FR-016 |

Duplicate ids and unresolved tax-class references are **cross-file** and therefore cannot
be pydantic validators. They run in a separate resolution pass in
`terezy.data.declarations.resolver`, after every file has been parsed individually.

## Error shape

The loader never lets a `pydantic.ValidationError` escape. It is adapted to:

```
DeclarationError(
    file:      Path,          # which file
    field_path: str,          # e.g. "instrument.terms.coupon_rate_pct"
    problem:   str,           # what was wrong, in plain language
    remedy:    str | None,    # what to write instead, where that is knowable
)
```

A raw `ValidationError` crossing the boundary would be a pydantic concept leaking into
the caller, and its default rendering does not name the file at all — which is half of
what FR-016 asks for.
