"""SC-013 and SC-014: incomparability is a property of a **pair**, and *not placed* of a candidate.

019 FR-008a. Where a pair cannot be decided on some objective it yields no verdict and is
recorded as incomparable, naming the objective and what made it so. It refuses no section and
removes neither candidate from any other pair's verdict -- a candidate is *not placed* only when
**every** pair involving it is incomparable.

Both cases are planted on a real section, because no declaration in this repository produces
either: the money criterion reads a field that is always present, and the shipped registry has
one spendable endpoint (research D5).
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.decision.dominance import relates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.dominance import (
    DateFigure,
    DeliveredInTwoCurrencies,
    FigureMissing,
    FigureUnavailable,
    Incomparable,
    MoneyFigure,
    MoneyWidth,
)
from terezy.core.results.objectives import Criterion, ObjectiveDirection
from tests import dominance_sections as sections
from tests.data_roots import REPO_ROOT
from tests.source_scan import executable_source

MISSING = "UA4000239016"
"""The candidate whose arrivals are emptied. Any would do; naming one keeps the assertions
readable."""


def test_a_candidate_with_no_arrivals_is_incomparable_against_every_other() -> None:
    """SC-013's first half, naming the objective and the field that carried nothing."""
    planted = sections.with_no_arrivals(sections.section(), MISSING)
    result = sections.result(planted)
    involving = [
        pair
        for pair in result.incomparable
        if MISSING in (pair.left.instrument_id, pair.right.instrument_id)
    ]
    population = len(result.non_dominated) + len(result.dominated) + len(result.not_placed)
    assert len(involving) == population - 1, "some pair involving it was still decided"
    for pair in involving:
        assert pair.criterion is Criterion.ALL_MONEY_BACK_ON
        assert isinstance(pair.why, FigureMissing)
        assert pair.why.what == "TupleOutcome.arrivals"


def test_a_candidate_every_pair_of_which_is_incomparable_is_not_placed() -> None:
    """SC-013's second half, and it is in neither of the other two populations."""
    planted = sections.with_no_arrivals(sections.section(), MISSING)
    result = sections.result(planted)
    unplaced = [item for item in result.not_placed if item.key.instrument_id == MISSING]
    assert len(unplaced) == 1
    assert unplaced[0].every_pair
    assert MISSING not in {key.instrument_id for key in result.non_dominated}
    assert MISSING not in {item.key.instrument_id for item in result.dominated}


def test_a_not_placed_candidates_figures_are_still_reported_unchanged() -> None:
    """FR-009 again, from the other side: nothing is dropped for being undecidable."""
    planted = sections.with_no_arrivals(sections.section(), MISSING)
    reported = {item.key.instrument_id: item for item in section_evaluated(planted)}
    assert MISSING in reported
    assert reported[MISSING].reaches == sections.named(sections.section(), MISSING).reaches


def test_a_cross_currency_pair_is_incomparable_naming_both_currencies() -> None:
    """SC-014's first: Principle VI, and *more money* is not a question across a rate nobody
    declared."""
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016"])
    result = sections.result(planted)
    crossing = [
        pair for pair in result.incomparable if isinstance(pair.why, DeliveredInTwoCurrencies)
    ]
    assert crossing
    for pair in crossing:
        assert pair.criterion is Criterion.MONEY_AT_THE_ENDPOINT
        assert isinstance(pair.why, DeliveredInTwoCurrencies)
        assert {pair.why.left_currency, pair.why.right_currency} == {
            Currency.UAH,
            Currency.USD,
        }


def test_every_same_currency_pair_around_it_is_still_decided() -> None:
    """SC-014's second. Refusing the section for one pair would drop 200 verdicts to report one
    absence, which is what FR-008a exists to refuse."""
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016"])
    result = sections.result(planted)
    assert result.dominated, "nothing was decided, so incomparability took the whole section"
    assert result.non_dominated


def test_a_candidate_with_one_incomparable_pair_and_one_decided_pair_is_not_unplaced() -> None:
    """SC-014's third, and the only case that exercises FR-008a's *only when every pair*.

    Two candidates deliver dollars, so each has an incomparable pair against every hryvnia
    candidate **and** a decided pair against the other dollar one. An implementation that marked
    a candidate *not placed* on any incomparable pair would put both here.
    """
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016", "UA4000238281"])
    result = sections.result(planted, amounts=sections.question_amounts(usd=200.0))
    unplaced = {item.key.instrument_id for item in result.not_placed}
    assert "UA4000239016" not in unplaced
    assert "UA4000238281" not in unplaced
    assert result.incomparable, "no pair crossed a currency, so this asserts nothing"


def test_no_exchange_rate_is_consulted_anywhere_in_the_pass() -> None:
    """SC-014's fourth, as a scan because the criterion is the **absence** of a conversion.

    ``money.convert`` is the one function that returns an amount in another currency, and it
    exists precisely so the prohibition can be checked at one name rather than audited across
    every expression. A run cannot observe a call that was never written.
    """
    for module in ("core/decision/dominance.py", "core/results/dominance.py"):
        source = executable_source(REPO_ROOT / "src" / "terezy" / module)
        assert "convert" not in source, f"{module} converts a currency"
        assert "official_rate" not in source


# ---------------------------------------------------------------------------
# The relation's own contract, reached directly rather than through the pass
# ---------------------------------------------------------------------------
#
# The pass asks `first_unreadable` before it looks up a width, so `relates`' own early exit is
# never taken from there. It is part of the public contract either way, and a caller holding
# figure vectors -- which is what the battery and the planted witness are -- reaches it.


def _uah(amount: float) -> MoneyFigure:
    return MoneyFigure(amount=Money(amount, Currency.UAH, prov.EMPTY))


def _width() -> MoneyWidth:
    return MoneyWidth(amount=Money(5.0, Currency.UAH, prov.EMPTY))


def test_relates_returns_the_first_position_it_cannot_read() -> None:
    verdict = relates(
        (_uah(10.0), FigureUnavailable(what="TupleOutcome.arrivals")),
        (_uah(20.0), _uah(30.0)),
        directions=(ObjectiveDirection.MORE_IS_BETTER,) * 2,
        widths=(_width(), _width()),
    )
    assert isinstance(verdict, Incomparable)
    assert verdict.position == 1
    assert verdict.why == FigureMissing(what="TupleOutcome.arrivals")


def test_a_missing_figure_on_the_right_is_read_the_same_way_round() -> None:
    verdict = relates(
        (_uah(10.0),),
        (FigureUnavailable(what="TupleOutcome.arrivals"),),
        directions=(ObjectiveDirection.MORE_IS_BETTER,),
        widths=(_width(),),
    )
    assert isinstance(verdict, Incomparable)
    assert verdict.position == 0


def test_two_kinds_of_figure_at_one_position_is_a_programmer_error() -> None:
    """A criterion reads one kind of figure, so a money figure against a date at one position
    means a criterion and its reader disagree about what the criterion reads. Principle IV's
    split: ``raise`` for a violated invariant, a typed value for a business outcome."""
    with pytest.raises(AssertionError, match="disagree about what it reads"):
        relates(
            (_uah(10.0),),
            (DateFigure(on=date(2027, 1, 1)),),
            directions=(ObjectiveDirection.MORE_IS_BETTER,),
            widths=(_width(),),
        )
