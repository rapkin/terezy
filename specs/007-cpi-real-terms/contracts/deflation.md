# Contract: deflation and the real-terms slot

**Feature**: `007-cpi-real-terms` | **Modules**: `terezy.core.inflation`, `terezy.core.results.hurdle`

## Signatures

```python
def coverage(series: CpiSeries, window: Window) -> Covered | NotCovered
def cumulative_inflation(observations: Sequence[CpiObservation]) -> float
def deflate(*, nominal: float, inflation: float) -> float

def real_terms(
    *,
    nominal: NominalRate,
    series: CpiSeries | None,
    window: Window,
    assumption: InflationAssumption | None,
) -> RealTerms
```

Pure throughout. No clock, no I/O. `series` and `assumption` are `None`-able because their
absence is a *reported reason*, not an error.

## Guarantees

**G1 — The nominal figure is untouched.** No nominal computation changes, and no realised
amount, tax figure or ranking moves. Filling the slot is additive. (FR-014)

**G2 — One slot, two figures, never mixed.** `HurdleRate.real` is a single field holding
`RealTerms`, whose `realized` and `assumed` are computed independently; neither stands in for
the other and no reported number blends them. (FR-006, FR-009, FR-010)

**G3 — The exact Fisher relation.** `(1 + nominal) / (1 + inflation) - 1`. The subtraction
approximation exists nowhere in the feature. (FR-008)

**G4 — Cumulative inflation is a product.** Month-on-month observations chain by
multiplication, never by addition. (research.md D1)

**G5 — Coverage is all-or-nothing, and a gap is named.** One missing month makes the realized
figure unavailable with that month listed. Nothing is interpolated, carried forward, or the
window shortened. (FR-004, FR-012)

**G6 — Deflation is a valid observation.** A window in which prices fell yields a real rate
**above** the nominal one. Not clamped, not treated as an error. (SC, User Story 1 §4)

**G7 — Every real figure says what it is.** Labelled real, naming its series, its window and
its `basis` — `realized_cpi` or `declared_assumption`. Never confusable with the nominal
figure. (FR-011)

**G8 — A cited forecast is still an assumption.** An external forecast carries its citation
and its retrieval date and is labelled an assumption on every figure it touches. (FR-010,
FR-015)

**G9 — No default rate, no default series.** A missing assumption or a missing series makes
that figure unavailable naming the absence. (FR-015, FR-012)

**G10 — Provenance is the union of both sides.** The nominal figure's marks and every CPI
observation's marks appear on the real figure and on everything derived from it. An
unverified observation marks the figure; a stale one reports staleness. A transform that
drops a mark is a top-severity defect. (FR-013)

**G11 — Reasons are specific.** Every `RealTermsUnavailable` names the uncovered period, the
absent series, the absent nominal figure, or the absent assumption. 001's generic
*"inflation is not modelled in this feature"* survives nowhere. (FR-012)

**G12 — CPI is its own staleness kind**, `cpi_index`, with a declared threshold, measured
from the later of verification and retrieval. A kind with no declared threshold fails at
load. (FR-005)

**G13 — Nothing treats the CPI as a singleton.** A second series with a different identity
loads and is addressable as data only. (FR-002)

## The obligation this feature carries out of its own scope

When this lands, **001's spec gains a ⚙ cross-reference at FR-022** recording that the
prohibition was refined rather than repealed: a real figure from an *implicit or invented*
rate stays forbidden; a *declared, dated, labelled* assumption entered as scenario data is a
different thing and is permitted because it is visible as an assumption everywhere it
appears. FR-009 records this obligation explicitly; the landing change discharges it.
