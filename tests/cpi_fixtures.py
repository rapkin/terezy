"""Clearly-labelled synthetic CPI observations, and nothing that describes Ukraine.

Not a test module -- ``pytest`` collects only ``test_*.py``. It exists so that every
deflation example in the suite is built the same way, and so that the values under test are
**stated in the test that uses them** rather than read out of ``data/cpi/ua.toml``.

**The examples test the arithmetic, not the economy** (spec.md, Assumptions). A worked
example that deflated by the real Ukrainian series would be checking a published statistic
into a test file, where nobody would ever re-verify it, and would fail the day the series
was re-fetched. Every value here is invented and says so in its own citation.

**One ``SourceRef`` per observation**, exactly as ``loader.cpi_from_file`` builds them. A
real figure over a long window therefore carries hundreds of sources, which is the honest
answer (research.md D6) and the thing ``tests/contract/test_provenance_propagation.py``
asserts by count. A fixture that shared one ref across every month would make that
assertion pass for the wrong reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from terezy.core.inflation.series import CpiObservation, CpiSeries, InflationAssumption
from terezy.core.primitives import periods
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance, SourceRef

CPI_KIND = "cpi_index"
"""The declared kind every CPI observation ages under (``data/observation_kinds.toml``)."""

CITATION = "SYNTHETIC FIXTURE -- invented price-index values. Not observed from any publisher."
"""Said in the citation itself, so a value that escaped into an output would announce itself."""

RETRIEVED_ON = date(2026, 8, 23)
"""The fixture's retrieval date. An argument everywhere it is aged against, never a clock."""


def observation(
    period: str,
    value: float,
    *,
    verified_on: date | None = None,
    retrieved_on: date = RETRIEVED_ON,
) -> CpiObservation:
    """One synthetic month, with its own source ref.

    ``verified_on`` defaults to ``None`` -- unverified, like every real observation in
    ``data/cpi/ua.toml`` -- so a test that wants the mark absent has to say so, which is the
    direction that keeps the propagation tests falsifiable.
    """
    return CpiObservation(
        period=period,
        value=value,
        kind=CPI_KIND,
        provenance=prov.of(
            [
                SourceRef(
                    id=f"synthetic:cpi:{period}",
                    citation=CITATION,
                    retrieved_on=retrieved_on,
                    verified_on=verified_on,
                )
            ]
        ),
    )


def series(
    values: Sequence[tuple[str, float]],
    *,
    series_id: str = "synthetic_cpi_monthly",
    country: str = "XX",
    verified_on: date | None = None,
    retrieved_on: date = RETRIEVED_ON,
) -> CpiSeries:
    """A monthly series over the stated ``(period, value)`` pairs, in the order given.

    ``country`` defaults to ``XX`` -- the ISO reserved code for "no country" -- so that
    nothing here can be mistaken for a statement about a real economy.
    """
    return CpiSeries(
        id=series_id,
        country=country,
        index="SYNTHETIC FIXTURE -- invented price index",
        periodicity="monthly",
        base="previous month = 100",
        observations=tuple(
            observation(period, value, verified_on=verified_on, retrieved_on=retrieved_on)
            for period, value in values
        ),
    )


def run_of(first: str, count: int, value: float) -> list[tuple[str, float]]:
    """``count`` consecutive months from ``first``, every one at ``value``.

    A flat run rather than a varied one wherever the example is about the *chaining*: with
    every month equal, the product is a power and the reader can check it by squaring twice.
    """
    period = first
    months: list[tuple[str, float]] = []
    for _ in range(count):
        months.append((period, value))
        period = periods.next_month(period)
    return months


def window(first: str, last: str) -> Window:
    """A window, written the way the tests read."""
    return Window(first=first, last=last)


def owner_assumption(
    annual_rate: float,
    *,
    assumption_id: str = "synthetic_owner_inflation",
    provenance: Provenance | None = None,
    kind: str | None = None,
) -> InflationAssumption:
    """A declared future-inflation assumption: the owner's own figure by default.

    ``provenance`` is ``None`` for the owner's own belief -- there is nothing to cite -- and
    is a real citation for an external published forecast, which remains **an assumption**
    either way (FR-010).
    """
    return InflationAssumption(
        id=assumption_id,
        annual_rate=annual_rate,
        is_assumption=True,
        rationale="SYNTHETIC FIXTURE -- an invented belief about future inflation.",
        provenance=provenance,
        kind=kind,
    )


def forecast_assumption(
    annual_rate: float,
    *,
    assumption_id: str = "synthetic_published_forecast",
    verified_on: date | None = None,
) -> InflationAssumption:
    """An external published forecast: cited, dated, ageing under a kind -- and still an assumption.

    The distinction this fixture exists to make testable. It carries everything an
    observation carries and is *not* one: a forecast is a statement about a year that has
    not happened, so no verification against a primary source can make it observed.
    """
    return InflationAssumption(
        id=assumption_id,
        annual_rate=annual_rate,
        is_assumption=True,
        rationale=(
            "SYNTHETIC FIXTURE -- stands in for an external published forecast. Invented; "
            "not the National Bank's figure or anybody else's."
        ),
        provenance=prov.of(
            [
                SourceRef(
                    id=f"synthetic:forecast:{assumption_id}",
                    citation=(
                        "SYNTHETIC FIXTURE -- an invented forecast, cited so that the "
                        "'a cited forecast is still an assumption' rule can be tested."
                    ),
                    retrieved_on=RETRIEVED_ON,
                    verified_on=verified_on,
                )
            ]
        ),
        kind=CPI_KIND,
    )
