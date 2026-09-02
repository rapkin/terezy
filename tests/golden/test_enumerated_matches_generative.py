"""SC-002: the two forms, the same cash flows, the same figures.

This is the feature's headline test and the property that makes the second declaration form
affordable. Two declarations describe the same payments -- one states the issue's terms and
lets the engine derive them, one states the payments themselves -- and the owner runs the
full tuple on each: same holding size, same funding route in, same tax classes, same exit
route out, same horizon. Every figure agrees and the two take the same position in the
ranking.

**If this could not pass, the right response would be to stop**, not to add a branch: two
forms the join, the tax engine or the ranking has to know about are a second instrument
concept wearing one interface, which is the situation the four-interface limit of
constitution Principle II protects against.

**The permitted differences, and why each is correct rather than tolerated** (FR-011,
SC-002):

* *identity* -- two declarations, two ids;
* *provenance* -- two files, two citations;
* *the stated exclusions* -- an enumerated purchase price is a dirty price that has not
  been separated into a clean price and accrued interest, and the figure says so (FR-023);
* *the schedule's statement of conventions* -- one row names three conventions, the other
  names the one that annualises and denies the other two (FR-016);
* *the causation detail prose* -- a generative coupon's detail names the rate, the day count
  and the business-day rule it was computed from, and an enumerated one has none of the
  three to name. That prose is inside the canonical form on every row, deliberately, because
  a digest ignoring it would call two differently-explained results identical.

**Tolerance rather than bit-equality**, and that is stated here rather than in a footnote:
the two forms reach the same amount by different arithmetic. The generative form computes
``face x rate x year_fraction x units``; the enumerated form multiplies a transcribed
per-unit amount by the units. The transcription is at full float64 precision, so what is
left is the last bit or two of a different multiplication order -- which the project
tolerance covers and rounding to kopecks would not.
"""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest

from terezy.core.decision import tuple_outcome
from terezy.core.decision.compare import compare
from terezy.core.instruments import terms as instrument_terms
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.ledger.canonical import of_causation
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.results.schedule import CashFlowSchedule
from terezy.core.results.tuple import Comparison, TupleOutcome
from terezy.data.declarations import resolver
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.golden

MIRROR = "ovdp_enumerated_mirror"
"""``ovdp_synthetic_a``'s own computed schedule, transcribed as a list of payments."""

REGISTRIES = fixtures.without_latency(fixtures.declared())
"""Latency zeroed for the reason `tuple_registries.without_latency` gives: waiting is a
cost and it is the same cost on both sides, but leaving it in would need a tolerance loose
enough to hide the thing this test is looking for."""

WITHIN_TOLERANCE = frozenset({"implied_rate", "parts", "arrivals"})
"""Fields whose *contents* are compared above at the imported tolerance rather than by
equality, because the two forms reach the same amount by different arithmetic.

Named rather than inlined so the field-by-field sweep can say what it is deferring and to
where. Each is compared field by field in its own test; what the sweep still checks here is
that the two sides have the same number of them, so a form that dropped an arrival could not
hide behind a name on this list.
"""

HORIZON = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
"""Opened on the issue date rather than the day before, as `test_the_hurdle_is_a_tuple`
does: with the latency zeroed the money arrives the day it leaves, and a purchase dated
before the generative issue's own issue date is refused by that form -- correctly."""


def _rate(outcome: TupleOutcome) -> float:
    """The outcome's money-weighted return, refusing to compare a refusal with a number."""
    assert isinstance(outcome.implied_rate, NominalRate), outcome.implied_rate
    return outcome.implied_rate.value


def _outcome(instrument_id: str) -> TupleOutcome:
    outcome = tuple_outcome.evaluate(
        replace(fixtures.hurdle_tuple(), instrument_id=instrument_id),
        amount=fixtures.AMOUNT,
        horizon=HORIZON,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=REGISTRIES,
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


@cache
def _generative() -> TupleOutcome:
    return _outcome(fixtures.OVDP)


@cache
def _enumerated() -> TupleOutcome:
    return _outcome(MIRROR)


# ⚙ **Cached accessors rather than module constants, and the difference is the diagnostic.**
# Evaluating the engine at import time means a 013 regression surfaces as
# ``Interrupted: 1 error during collection`` with **no test run and no test name** -- the
# whole gate reported as infrastructure, taking every unrelated result down with it. Loud
# rather than silent, so not a coverage lie; the wrong shape all the same. Cached because the
# two runs are pure and this file asks for them a dozen times.


class TestEveryFigureAgrees:
    def test_the_same_money_goes_out(self) -> None:
        assert is_close(_generative().outlay.amount, _enumerated().outlay.amount)

    def test_the_same_money_comes_back(self) -> None:
        assert is_close(_generative().reaches.amount, _enumerated().reaches.amount)

    def test_every_arrival_agrees_in_every_field(self) -> None:
        """All four, not only the date and the amount. ``released`` is the net-of-tax figure
        two other contract tests assert against, and ``released_on`` differs from
        ``arrived_on`` the moment latency is not zeroed -- so comparing the pair a test
        happens to have zeroed apart would agree by accident."""
        for one, other in zip(_generative().arrivals, _enumerated().arrivals, strict=True):
            assert (one.released_on, one.arrived_on) == (other.released_on, other.arrived_on)
            for field in ("released", "amount"):
                mine, theirs = getattr(one, field), getattr(other, field)
                assert is_close(mine.amount, theirs.amount), field
                assert mine.currency == theirs.currency, field

    def test_every_part_contributes_the_same_amount(self) -> None:
        """The join reports each term of the tuple separately so a reader can see which one
        dominates. Two forms of the same instrument must not move any of them."""
        assert [part.part for part in _generative().parts] == [
            part.part for part in _enumerated().parts
        ]
        for one, other in zip(_generative().parts, _enumerated().parts, strict=True):
            assert is_close(one.amount.amount, other.amount.amount), one.part
            assert one.amount.currency == other.amount.currency, one.part
            assert one.source == other.source, (
                "the source is the mechanical half of *the join invents nothing*: two forms "
                "of one instrument must attribute each part to the same place"
            )

    def test_the_same_implied_rate(self) -> None:
        assert is_close(_rate(_generative()), _rate(_enumerated()))

    def test_the_same_span_and_horizon(self) -> None:
        assert _generative().span == _enumerated().span
        assert _generative().horizon == _enumerated().horizon

    def test_the_same_undeployed_remainder(self) -> None:
        assert (_generative().undeployed is None) == (_enumerated().undeployed is None)

    def test_the_same_route_standing_and_risk_class(self) -> None:
        assert _generative().routes == _enumerated().routes
        assert _generative().risk_class == _enumerated().risk_class

    def test_the_same_statement_of_what_the_figure_is_net_of(self) -> None:
        assert _generative().accounts_for == _enumerated().accounts_for


class TestTheOnlyDifferencesArePermittedOnes:
    def test_the_identity_differs_and_nothing_else_in_the_key(self) -> None:
        assert _generative().key.instrument_id != _enumerated().key.instrument_id
        assert replace(_generative().key, instrument_id=MIRROR) == _enumerated().key

    def test_the_exclusions_differ_by_exactly_the_dirty_price_clause(self) -> None:
        """FR-023, SC-015. Two facts are missing and neither may be inferred: the start of
        the accrual period containing the purchase, and the basis interest accrues on."""
        assert _enumerated().excludes - _generative().excludes == frozenset(
            {instrument_terms.DIRTY_PRICE}
        )
        assert _generative().excludes - _enumerated().excludes == frozenset()

    def test_the_provenance_differs_because_the_files_do(self) -> None:
        """Different citations, and the same **mark**: both rest on unverified values, as
        every figure in this repository does today, and a form that lost the mark on one
        side would be the top-severity defect Principle I names."""
        assert _generative().provenance != _enumerated().provenance
        assert prov.is_unverified(_generative().provenance)
        assert prov.is_unverified(_enumerated().provenance)

    def test_the_staleness_verdict_names_different_sources_and_reaches_the_same_answer(
        self,
    ) -> None:
        """`staleness` is identity again: its `assessed` tuple lists the source ids behind
        the figure, which name the files. What must agree is the verdict."""
        assert _generative().staleness.stale == _enumerated().staleness.stale == ()
        assert _generative().staleness.assessed != _enumerated().staleness.assessed
        assert len(_enumerated().staleness.assessed) > len(_generative().staleness.assessed), (
            "a declared schedule cites more sources than a declared rate does, because "
            "every payment carries its own -- and all of them are aged, which is the half "
            "that matters"
        )

    def test_field_by_field_nothing_else_differs(self) -> None:
        """The assertion the rest of this class exists to make safe: every field of the
        outcome compared, with the permitted differences named and nothing else allowed.

        Each name in ``permitted`` is asserted on separately above, as is each name in
        :data:`WITHIN_TOLERANCE`; what this adds is that the two lists are **exhaustive**,
        so a field added to the outcome later cannot differ between the forms without
        somebody deciding that it may -- an added field falls to the ``else`` arm and is
        compared for equality."""
        permitted = {"key", "excludes", "provenance", "rests_on", "staleness"}
        for field in TupleOutcome.__dataclass_fields__:
            if field in permitted:
                continue
            one, other = getattr(_generative(), field), getattr(_enumerated(), field)
            if hasattr(one, "amount") and hasattr(one, "currency"):
                assert is_close(one.amount, other.amount), field
                assert one.currency == other.currency, field
            elif field in WITHIN_TOLERANCE:
                assert len(one) == len(other) if hasattr(one, "__len__") else True, field
            else:
                assert one == other, field

    def test_what_each_figure_rests_on_names_its_own_declaration(self) -> None:
        """`rests_on` is identity wearing another name: it lists the declarations behind the
        figure, and the two runs read different files."""
        assert any(MIRROR in claim for claim in _enumerated().rests_on)
        assert any(fixtures.OVDP in claim for claim in _generative().rests_on)


class TestTheScheduleSaysDifferentTrueThings:
    def test_the_generated_rows_name_three_conventions(self) -> None:
        for row in _schedule(fixtures.OVDP).rows:
            assert isinstance(row.conventions, ConventionsApplied)

    def test_the_declared_rows_name_only_the_one_that_annualises(self) -> None:
        for row in _schedule(MIRROR).rows:
            assert isinstance(row.conventions, AmountsAsDeclared)
            assert row.conventions.day_count == "act/365"

    def test_the_rows_otherwise_report_the_same_money_on_the_same_dates(self) -> None:
        generated, declared = _schedule(fixtures.OVDP).rows, _schedule(MIRROR).rows
        assert len(generated) == len(declared)
        for one, other in zip(generated, declared, strict=True):
            assert (one.occurred_on, one.kind) == (other.occurred_on, other.kind)
            assert is_close(one.gross.amount, other.gross.amount)
            assert is_close(one.tax.amount, other.tax.amount)
            assert is_close(one.net.amount, other.net.amount)

    def test_only_the_causation_detail_prose_differs_between_the_rows(self) -> None:
        """A generative coupon's detail names the rate, the day count and the business-day
        rule it was computed from; a declared one has none of the three to name. The rest of
        the causation -- what kind of thing caused the event, and which declared term -- is
        the same claim in both."""
        for one, other in zip(_schedule(fixtures.OVDP).rows, _schedule(MIRROR).rows, strict=True):
            assert one.caused_by.kind == other.caused_by.kind
            if one.caused_by.detail != other.caused_by.detail:
                assert of_causation(one.caused_by) != of_causation(other.caused_by)


class TestTheRankingPutsThemInTheSamePlace:
    def test_neither_beats_the_other(self) -> None:
        comparison = compare(
            (replace(fixtures.hurdle_tuple(), instrument_id=MIRROR),),
            benchmark=fixtures.hurdle_tuple(),
            amount=fixtures.AMOUNT,
            horizon=HORIZON,
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=REGISTRIES,
        )
        assert isinstance(comparison, Comparison), comparison
        assert comparison.ties == ((0, 1),), (
            "two declarations of one schedule that did not tie would mean the form reached "
            "a figure, which is what this whole feature exists to prevent"
        )
        assert comparison.beats_benchmark == ()

    def test_the_two_rates_agree_to_the_project_tolerance(self) -> None:
        assert abs(_rate(_generative()) - _rate(_enumerated())) < TOLERANCE


DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
PURCHASE = Holding(
    owner_id="owner-1",
    instrument_id=fixtures.OVDP,
    quantity=10.0,
    purchased_on=fixtures.ISSUE_DATE,
    cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
)
"""The purchase the tuple above makes: 10 000.00 UAH at the declared par quote of 1 000.00
per unit, on the date the generative issue starts accruing. Rebuilt here rather than read
off the tuple because the schedule is a projection's figure and the tuple keeps only the
result -- the two runs are the same purchase either way, which is what the parts assertion
above already proves."""


def _schedule(instrument_id: str) -> CashFlowSchedule:
    """The dated lines the same purchase of one declaration produces."""
    outcome = project.project(
        DECLARATIONS.instruments[instrument_id],
        replace(PURCHASE, instrument_id=instrument_id),
        DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        fixtures.HOLD_TO_MATURITY,
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome.schedule
