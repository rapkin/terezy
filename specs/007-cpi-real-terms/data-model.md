# Phase 1 data model: CPI and real terms

**Feature**: `007-cpi-real-terms` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Frozen dataclasses, free functions, tagged unions matched with `match` (owner decision D-E).
One imported tolerance. No clock — every date is an argument or a declaration.

The rule that shapes everything: **a realized figure and an assumed figure are two figures,
and no reported number blends them** (FR-009, FR-010).

---

## The declared series

### `CpiSeries` — `core/inflation/series.py`

| Field | Type | Meaning |
|---|---|---|
| `id` | `str` | `ua_cpi_monthly` |
| `country` | `str` | FR-002: the series declares what it measures |
| `index` | `str` | "consumer price index, all goods and services" |
| `periodicity` | `Literal["monthly"]` | Declared per series, **never fixed in the engine** (FR-002) |
| `base` | `str` | "previous month = 100" — the form, stated |
| `observations` | `tuple[CpiObservation, ...]` | Sorted by period, no duplicates, no overlaps |

**Nothing treats "the CPI" as a singleton** (FR-002). A second series with a different
identity is a data-only addition that loads and is addressable, even though this feature
consumes one.

### `CpiObservation`

| Field | Type | Meaning |
|---|---|---|
| `period` | `str` | `YYYY-MM`, conforming to the declared periodicity |
| `value` | `float` | The published index **against the previous month**: 100.9 is +0.9% |
| `provenance` | `Provenance` | Source, retrieval date, verification date — `verified_on` may be empty but never absent (FR-001) |

The shipped file has 411 of these, 1991-08 to 2025-10, every one unverified.

## Deflation

### `Window`

| Field | Type | Meaning |
|---|---|---|
| `first`, `last` | `str` | `YYYY-MM`, inclusive |

### `Coverage` — `core/inflation/series.py`

A tagged union, returned before any arithmetic runs:

| Member | Fields |
|---|---|
| `Covered` | `observations: tuple[CpiObservation, ...]` — every month of the window, in order |
| `NotCovered` | `missing: tuple[str, ...]` — the periods with no declared observation, **named** |

All-or-nothing (research.md D4). A window is never silently shortened to the covered part:
that produces a real number for a window nobody asked about.

### `cumulative_inflation(observations) -> float`

The product of every `value / 100`, minus one. **Not a sum** — over Ukrainian magnitudes the
difference is material, which is the same reason FR-008 forbids the subtraction
approximation one level up (research.md D1).

### `deflate(nominal, inflation) -> float` — `core/inflation/deflate.py`

`(1 + nominal) / (1 + inflation) - 1`. The exact Fisher relation.

**There is no function in this feature that subtracts an inflation rate from a nominal one**
(FR-008). The approximation is not discouraged; it is absent.

## Results

### `RealTerms` — `core/results/hurdle.py`

| Field | Type | Meaning |
|---|---|---|
| `realized` | `RealRate \| RealTermsUnavailable` | Deflated by declared observations |
| `assumed` | `RealRate \| RealTermsUnavailable` | Deflated by the declared assumption |

`HurdleRate.real` becomes `RealTerms` — still **one** field, so FR-006's invariance holds
(research.md D2). `RealTerms` is never itself unavailable: when neither figure can be
computed it holds two unavailable values, each with its own reason, because "which one is
missing" is exactly what FR-012 requires answering.

### `RealRate` — extended

| Field | Type | Meaning |
|---|---|---|
| `value` | `float` | |
| `basis` | `Literal["realized_cpi", "declared_assumption"]` | The epistemic source, on the figure itself (FR-010) |
| `series_id` | `str` | Which series it is real *against* (FR-011) |
| `window` | `Window` | What the observations cover (FR-011) |
| `provenance` | `Provenance` | The union of the nominal figure's and every observation's (FR-013) |

`basis` is on the record rather than inferred from which field holds it, so a figure lifted
out of `RealTerms` and passed alone still says what it rests on.

### `RealTermsUnavailable` — reason, made specific

001's single generic reason is replaced by one that names what is missing (FR-012):

| Case | The reason names |
|---|---|
| No series declared | the absent series |
| A gap in the window | **the uncovered months**, listed |
| No nominal figure | the absent nominal figure |
| No declared assumption | that no future-inflation assumption was declared for this run |

001's *"inflation is not modelled in this feature"* stops being true the moment this lands
and must not survive anywhere.

## The assumption

### `InflationAssumption` — `core/inflation/series.py`

| Field | Type | Meaning |
|---|---|---|
| `annual_rate` | `float` | |
| `is_assumption` | `Literal[True]` | Carried where an observation carries a source, on `RegimeTransition`'s precedent |
| `rationale` | `str` | |
| `provenance` | `Provenance \| None` | An external forecast carries its citation; the owner's own figure carries none |

**A cited forecast is still an assumption** (FR-010, research.md D5). The National Bank's
number has a source and a retrieval date and is a *forecast*; `is_assumption` is `Literal[True]`
because this record has no other case.

## What is deliberately absent

- **No level index.** The published form is month-on-month and no base-100 series is
  synthesised (research.md D1).
- **No subtraction approximation**, anywhere (FR-008).
- **No interpolation, extrapolation or carry-forward** across a gap (FR-004).
- **No default inflation rate**, and no field one could hide in (FR-015).
- **No blended figure.** There is no single number combining observed and assumed inflation,
  and no field that could hold one (FR-009, FR-010).
- **No network, no cache.** The loader reads a committed file; `scripts/fetch_cpi.py` is
  tooling this feature does not know about (research.md D10).
