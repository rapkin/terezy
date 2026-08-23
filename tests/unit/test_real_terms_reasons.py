"""Every refusal names what is missing, and 001's generic reason survives nowhere.

FR-012 and G11. Feature 001's real slot carried one sentence -- *"inflation is not modelled
in this feature, so no real figure can be computed"* -- which was true then and stops being
true the moment this feature lands. Replacing it with a reason that names the *specific*
absence is the point: a refusal that names the missing month is an instruction, and one that
says "not modelled" is a shrug.

Five absences, five reasons:

| Missing | The reason names |
|---|---|
| The series | that no CPI series was declared |
| A month inside the window | **the uncovered months**, listed |
| The nominal figure | that there is nothing to deflate |
| The assumption | that no future-inflation assumption was declared for this run |
| Any elapsed month in the window | the window, and that it spans none |

And the structural claim underneath them: ``RealTerms`` is **never itself unavailable**. When
neither figure can be computed it holds two unavailable values, each with its own reason,
because *"which of the two is missing"* is exactly what FR-012 requires answering and a
single unavailable value cannot answer it (research.md D2).
"""

from __future__ import annotations

from pathlib import Path

from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.results import hurdle
from tests import cpi_fixtures

SRC = Path(__file__).resolve().parents[2] / "src"

NOMINAL = NominalRate(0.155)
COVERED_SERIES = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 12, 101.0))
FULL_WINDOW = cpi_fixtures.window("2026-01", "2026-12")


def _real_terms(
    *,
    nominal: NominalRate | None = NOMINAL,
    series: object = COVERED_SERIES,
    window: object = FULL_WINDOW,
    assumption: object = None,
) -> hurdle.RealTerms:
    """``real_terms`` with the covered defaults, so each test states only what it removes."""
    return hurdle.real_terms(
        nominal=nominal,
        nominal_provenance=prov.EMPTY,
        nominal_staleness=staleness.UNASSESSED,
        deflation=cpi_fixtures.deflation(
            window=window,  # type: ignore[arg-type]
            series=series,  # type: ignore[arg-type]
            assumption=assumption,  # type: ignore[arg-type]
        ),
    )


def test_the_slot_always_holds_a_real_terms_record_never_a_bare_unavailable() -> None:
    """Both halves missing is still two answers, not one (research.md D2)."""
    result = _real_terms(series=None, assumption=None)

    assert isinstance(result, hurdle.RealTerms)
    assert isinstance(result.realized, RealTermsUnavailable)
    assert isinstance(result.assumed, RealTermsUnavailable)
    assert result.realized.reason != result.assumed.reason


def test_an_absent_series_is_named_as_an_absent_series() -> None:
    result = _real_terms(series=None)

    assert isinstance(result.realized, RealTermsUnavailable)
    assert "no CPI series" in result.realized.reason


def test_an_uncovered_window_lists_the_months_that_are_missing() -> None:
    """The gap is named, month by month, so the reason is an instruction."""
    gapped = cpi_fixtures.series(
        [("2026-01", 101.0), ("2026-02", 101.0), ("2026-05", 101.0), ("2026-06", 101.0)]
    )
    result = _real_terms(series=gapped, window=cpi_fixtures.window("2026-01", "2026-06"))

    assert isinstance(result.realized, RealTermsUnavailable)
    assert "2026-03" in result.realized.reason
    assert "2026-04" in result.realized.reason
    assert gapped.id in result.realized.reason


def test_the_uncovered_reason_says_the_window_was_not_shortened() -> None:
    """The reader has to be told the tempting repair was refused, not merely that it failed."""
    short = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 4, 101.0))
    result = _real_terms(series=short, window=cpi_fixtures.window("2026-01", "2026-06"))

    assert isinstance(result.realized, RealTermsUnavailable)
    assert "shorten" in result.realized.reason.lower()


def test_an_absent_nominal_figure_is_distinct_from_an_absent_series() -> None:
    """*"Nothing to deflate"* and *"nothing to deflate by"* are different facts."""
    result = _real_terms(nominal=None, assumption=cpi_fixtures.owner_assumption(0.10))

    assert isinstance(result.realized, RealTermsUnavailable)
    assert isinstance(result.assumed, RealTermsUnavailable)
    assert "nominal" in result.realized.reason
    assert "nominal" in result.assumed.reason
    assert "no CPI series" not in result.realized.reason


def test_an_absent_assumption_is_named_on_the_assumed_figure_only() -> None:
    """And only on it: the realized figure is available and must not be dragged down with it."""
    result = _real_terms(assumption=None)

    assert isinstance(result.realized, RealRate)
    assert isinstance(result.assumed, RealTermsUnavailable)
    assert "assumption" in result.assumed.reason


def test_a_window_spanning_no_elapsed_month_is_refused_by_name() -> None:
    """A holding bought and matured inside one month has no price change to be deflated by.

    Refused rather than answered with "zero inflation", which would come back as a real rate
    equal to the nominal one -- a confident wrong answer that looks entirely reasonable.
    """
    result = _real_terms(window=cpi_fixtures.window("2026-05", "2026-04"))

    assert isinstance(result.realized, RealTermsUnavailable)
    assert "2026-05" in result.realized.reason
    assert "2026-04" in result.realized.reason


def test_the_five_reasons_are_all_different_from_one_another() -> None:
    """A reason that is specific in wording but identical in content is not specific."""
    gapped = cpi_fixtures.series([("2026-01", 101.0)])
    reasons = {
        _real_terms(series=None).realized,
        _real_terms(series=gapped, window=cpi_fixtures.window("2026-01", "2026-03")).realized,
        _real_terms(nominal=None).realized,
        _real_terms(assumption=None).assumed,
        _real_terms(window=cpi_fixtures.window("2026-05", "2026-04")).realized,
    }
    texts = {reason.reason for reason in reasons if isinstance(reason, RealTermsUnavailable)}

    assert len(texts) == 5


def test_no_reason_anywhere_still_says_inflation_is_not_modelled() -> None:
    """The repository-wide check. 001's sentence was true then and is false now.

    Grepping the whole of ``src/`` rather than the two modules that used to hold it, because
    the sentence is exactly the sort of text that gets copied into a neighbouring docstring
    and left behind.
    """
    offenders = [
        path
        for path in SRC.rglob("*.py")
        if "inflation is not modelled" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, (
        f"{[str(path) for path in offenders]} still say inflation is not modelled. It was "
        "feature 001's honest statement and this feature makes it false; every refusal now "
        "names the specific missing month, series, figure or assumption (FR-012)."
    )
