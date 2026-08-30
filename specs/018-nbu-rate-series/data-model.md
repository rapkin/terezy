# Phase 1 data model: 018-nbu-rate-series

Every domain record this feature touches already exists. What follows is what changes shape,
and — as loudly — what does not.

## Unchanged, and asserted to be unchanged

`OfficialRateObservation`, `OfficialRateSeries`, `NonPublicationRule`, `NonPublicationDay`,
`TaxCurrencyConversion`, `OfficialRateSeriesUnavailable`, `OfficialRateUndeclaredOnDate`, and the
`OfficialRateFile` schema — **no field added, removed or retyped**. FR-009 records the
publisher's `units` and `calcdate` in the citation *text* for exactly this reason: the
observation schema is `extra="forbid"`, and adding a field for either would be a schema change
this feature does not need, on the path it claims not to touch.

`data/channels/uah_usd.toml` — untouched, `reference_rate = 42.0`, still marked synthetic
(FR-018, SC-010).

## Changed

### `InputKind` (`src/terezy/data/manifest.py`)

A closed `Literal` gains one member: `"official_rate"`. It stays alphabetical, because
`input_refs` sorts by `(kind, id)` and the declaration's order is the order a manifest reads in.

### `official_rate_input_refs(rates: OfficialRateDeclarations) -> tuple[InputRef, ...]`

New, beside `inflation_input_refs` and for the same reason: `OfficialRateDeclarations` is
resolved separately from `Declarations`, so it gets its own function rather than more branches
inside one. `unverified_sources` is the union over every observation's provenance — which for the
landed file is every one of them, which is the correct and uncomfortable answer.

### `of_run(..., official_rates: OfficialRateDeclarations | None = None)`

Defaulting to `None`, like `inflation`: a run given no rates is a legitimate run whose manifest
lists none.

### `observation_for` (`src/terezy/core/tax/official_rate.py`)

Same signature, same return, same precedence (a declared observation beats any rule). The dict
rebuild becomes a bisection over the observations' dates. No field is added to carry an index:
see [research D5](./research.md).

## New: the fetched shape, inside the script only

Nothing here is a domain record and nothing here is imported by `src/`.

```text
Row          exchangedate: date   rate: float   units: int   calcdate: str
Fetched      rows: tuple[Row, ...]   retrieved_on: date   url: str   dropped: tuple[date, ...]
Verified     Mapping[date, tuple[float, str]]     # on_date -> (value, verified_on)
```

`Fetched.dropped` carries the day-ahead rows FR-010 declines, so `main` can name them instead of
them being silently absent.

## The file's shape on disk

Per row, the shipped form `data/cpi/ua.toml` already uses:

```toml
[[observation]]
on_date      = "2026-08-31"
value        = 44.5505
kind         = "official_rate"
source       = "…НБУ…; retrieved from <range URL>; units = 1; calcdate = 28.08.2026; …licence…"
retrieved_on = "2026-08-31"
verified_on  = ""
```

`source` is the whole of FR-001, FR-009 and FR-025 in one string: the endpoint and its query, the
publisher's stated unit **for that row**, the establishment date, and the two provisions the
reuse is conditional on. Per row rather than inherited, because a self-citing row is a row whose
provenance is true on its own — see spec.md, "Two alternatives, and why neither is taken".

## Invariants the landed file must satisfy

Each is a test, not a sentence here:

1. Strictly ascending `on_date`, no duplicates, one row per calendar day, zero missing.
2. First `on_date` is `2019-12-28`; no row is dated after its own `retrieved_on`.
3. `value > 0` on every row; every `source` non-empty and carrying the retrieval URL;
   every `verified_on` present and empty.
4. `[series].quotation_unit == 1.0`, and no `non_publication_rule` table.
5. The file loads through `loader.official_rate_from_file` without error.
