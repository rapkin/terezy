"""Five ways a tuple's real slot has no figure, each naming what is missing.

007 already names four of them and 024 FR-013a adds the fifth. None is a new record type -- all
five are a :class:`RealTermsUnavailable`, which is what keeps the wire tags and the web client
untouched -- and none is decided at the construction site: every one is reached inside
``hurdle.real_terms``, which stays the only place a slot is filled (FR-013b).

| Missing | The reason names |
|---|---|
| The belief | that no future-inflation assumption was declared |
| The series | that no CPI series was declared |
| **Which** series, with more than one declared | both ids it could not choose between |
| The nominal figure | that there is nothing to deflate |
| Any elapsed month in the span | the window, and that it spans none |

**The last two outrank the deflator ones.** A tuple with no comparable rate says *there is
nothing to deflate* whether or not a series was declared, because a call site that resolved the
series first would report the wrong absence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import RealTermsUnavailable
from terezy.core.results.tuple import RateNotComparable, Tuple, TupleOutcome
from terezy.core.routes.path import DeclaredExit, FundingPath
from tests import answer_registries as answers
from tests import tuple_registries as fixtures
from tests.outcomes import evaluated_outcome

HORIZON: Final = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
SECOND_SERIES: Final = "pl_cpi_monthly"
"""A second declared id. Invented here rather than in `data/`: 007 FR-002 makes a second series
a data-only addition, and what this suite is about is the engine refusing to *choose*."""


def _evaluated(registries: Registries, candidate: Tuple | None = None) -> TupleOutcome:
    outcome = evaluated_outcome(
        candidate or fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT,
        horizon=HORIZON,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


def test_a_run_with_no_declared_belief_reports_the_absence_and_assumes_no_rate() -> None:
    """FR-009 and SC-004: no default belief, and none may be added."""
    figure = _evaluated(replace(fixtures.declared(), inflation=None)).real.assumed

    assert isinstance(figure, RealTermsUnavailable), figure
    assert "future-inflation assumption" in figure.reason
    assert "no default rate" in figure.reason.lower()


def test_a_run_with_no_declared_series_reports_that_there_is_nothing_to_deflate_by() -> None:
    """Distinct from having nothing to deflate: the two send a reader to different files."""
    figure = _evaluated(replace(fixtures.declared(), cpi={})).real.realized

    assert isinstance(figure, RealTermsUnavailable), figure
    assert "no CPI series" in figure.reason


@pytest.mark.parametrize("extra", [1, 2])
def test_declared_series_and_none_named_refuses_naming_every_id(extra: int) -> None:
    """FR-013a. Adding a second series stays a data-only change that loads; what it stops
    doing is silently deciding which index a figure is real against.

    Two counts, because the guard fires for **any** number above one and its sentence has to
    describe what it did at each: a message written for a collision between two files says
    something false the day a third is declared.
    """
    declared = fixtures.declared()
    one = next(iter(declared.cpi.values()))
    every = {
        **declared.cpi,
        **{
            f"{SECOND_SERIES}_{index}": replace(one, id=f"{SECOND_SERIES}_{index}")
            for index in range(extra)
        },
    }

    figure = _evaluated(replace(declared, cpi=every)).real.realized

    assert isinstance(figure, RealTermsUnavailable), figure
    assert str(len(every)) in figure.reason
    for series_id in sorted(every):
        assert series_id in figure.reason


def test_a_second_series_changes_no_other_figure_on_the_outcome() -> None:
    """SC-004's second half: the ambiguity refuses the realized half and nothing else."""
    declared = fixtures.declared()
    one = next(iter(declared.cpi.values()))
    ambiguous = _evaluated(
        replace(declared, cpi={**declared.cpi, SECOND_SERIES: replace(one, id=SECOND_SERIES)})
    )
    single = _evaluated(declared)

    assert ambiguous.implied_rate == single.implied_rate
    assert ambiguous.reaches == single.reaches
    assert ambiguous.real.assumed == single.real.assumed
    assert ambiguous.real.realized != single.real.realized


def test_a_tuple_with_no_comparable_rate_says_there_is_nothing_to_deflate_on_both_halves() -> None:
    """FR-002 and FR-013b. A dollar outlay against hryvnia inflows is not a rate of anything,
    and both halves report the missing *figure* rather than a missing deflator -- which is what
    a call site resolving the series before calling would have got wrong."""
    registries = fixtures.with_new_route(
        fixtures.declared(),
        fixtures.fx_route("test_deel_to_inzhur", origin="deel", destination="inzhur"),
    )
    outcome = evaluated_outcome(
        Tuple(
            instrument_id=fixtures.OVDP,
            stream_id="contract_usd",
            route_in=FundingPath(
                destination_id="inzhur", stream_id="contract_usd", route_id="test_deel_to_inzhur"
            ),
            exit_terms=fixtures.HOLD_TO_MATURITY,
            route_out=DeclaredExit(route_id=fixtures.DOMESTIC_OUT),
        ),
        amount=Money(1_000.0, Currency.USD, prov.EMPTY),
        horizon=HORIZON,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    assert isinstance(outcome.implied_rate, RateNotComparable)

    for figure in (outcome.real.realized, outcome.real.assumed):
        assert isinstance(figure, RealTermsUnavailable), figure
        assert "no nominal figure to deflate" in figure.reason


ONE_MONTH: Final = 0
"""Index of the owner's shortest declared horizon, 2026-09-01 .. 2026-10-01."""

PAID_INSIDE_A_MONTH: Final = "UA4000235865"
"""Its last coupon and its principal are paid 2026-09-16 and the money arrives 2026-09-19 after
the declared exit latency, so its span sits inside one month at all three of his horizons."""


def test_a_span_inside_one_month_refuses_both_halves_for_holding_no_elapsed_month() -> None:
    """The edge case the shipped root actually contains, and the refusal that outranks the
    deflator ones: the belief is declared and the series is not ambiguous, and neither half
    reports either fact, because there is no elapsed month to deflate over at all."""
    result = answers.answered(supplied=answers.shipped_inputs())
    found = [
        outcome
        for outcome in section_evaluated(result.sections[ONE_MONTH])
        if outcome.key.instrument_id == PAID_INSIDE_A_MONTH
    ]
    assert len(found) == 1
    outcome = found[0]
    assert outcome.span.end == date(2026, 9, 19)

    for figure in (outcome.real.realized, outcome.real.assumed):
        assert isinstance(figure, RealTermsUnavailable), figure
        assert "no elapsed month" in figure.reason


def test_no_refusal_here_is_a_record_type_of_its_own() -> None:
    """FR-013a's *no new record type*: five absences, one union arm, so no new wire tag.

    The web client narrows on a tag, so a sixth arm would be a schema change for a fact the
    existing arm already carries in words.
    """
    declared = fixtures.declared()
    one = next(iter(declared.cpi.values()))
    refusals = [
        _evaluated(replace(declared, inflation=None)).real.assumed,
        _evaluated(replace(declared, cpi={})).real.realized,
        _evaluated(
            replace(declared, cpi={**declared.cpi, SECOND_SERIES: replace(one, id=SECOND_SERIES)})
        ).real.realized,
    ]

    assert {type(figure) for figure in refusals} == {RealTermsUnavailable}
    reasons = {figure.reason for figure in refusals if isinstance(figure, RealTermsUnavailable)}
    assert len(reasons) == len(refusals)
