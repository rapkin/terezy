"""A route that does not start where the stream's money lands is **reported**.

spec.md, Edge Cases: *a route whose start does not match the stream's arrival venue -- a
mismatch, reported rather than assumed away.*

**What "assumed away" would look like, and why it is worse than a crash.** The tempting
reading of a mismatched pair is that it does not matter much: the money is the owner's either
way, and a route from Coinbase costs what it costs. But the whole subject of this feature is
that *getting money to where the instrument is* has a price, and a cost that begins at a venue
the money is not in has silently skipped its own first step -- which is usually the expensive
one. The figure would look perfectly reasonable and be missing the largest term. That is the
defect class Principle VI puts at the top: a per-``(destination x stream x route)`` cost whose
stream term is decorative.

So the pair is refused, as a typed :class:`RouteUnusable` naming **both** ends, and the owner's
remedy -- declare a route from where the money actually arrives -- is readable from the output
alone.

## Two dimensions, because a venue is not the whole story

* **The venue.** ``route.origin`` is not ``stream.arrives_at``.
* **The currency.** The stream lands at the right venue in the wrong currency. A
  multi-currency account is the ordinary case -- it is what Monobank is -- so matching venues
  prove nothing about the money being in the currency the route's first leg moves. Without
  this check the costing would fail several legs later inside ``money.sub`` with a currency
  mismatch naming two currencies and neither the stream nor the route: a true message about
  the wrong thing.

## And the same refusal survives a ranking

The last class is the reason ``streams`` had to land in ``cost_one`` and ``rank`` in one
change (``contracts/route-costing.md``). If ranking costed its candidates through a signature
that did not know about streams, the winner and the alternatives would be priced by two
different functions -- the second code path FR-029 exists to forbid. Here the mismatched
candidate is *excluded with its reason* rather than dropped, and the reason it carries is the
one ``cost_one`` gives for the same path.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import NothingComparable, RampCost, Ranking, RouteUnusable
from terezy.core.routes import cost, ranking
from terezy.core.routes.legs import Route
from terezy.core.routes.path import FundingPath
from terezy.core.streams.streams import IncomeStream
from tests.invariants import route_graphs

ELSEWHERE = "privatbank_uah"
"""A second hryvnia account, so a stream can arrive somewhere no fixture route starts."""

SALARY_ELSEWHERE = dataclasses.replace(
    route_graphs.SALARY_UAH, id="salary_elsewhere", arrives_at=ELSEWHERE
)
"""The same hryvnia salary, landing in an account no declared route leaves from.

Same currency as the route it is paired with below, so the *venue* is the only thing that
disagrees and the refusal cannot be passing for the wrong reason.
"""

STREAMS: Mapping[str, IncomeStream] = {
    **route_graphs.STREAMS,
    SALARY_ELSEWHERE.id: SALARY_ELSEWHERE,
}


def _cost(
    path: FundingPath, amount: Money, *, routes: Mapping[str, Route] | None = None
) -> RampCost | RouteUnusable:
    """Cost one path against the domestic fixture's routes, whatever comes back."""
    graph = route_graphs.zero_cost_graph()
    return cost.cost_one(
        path,
        amount,
        routes=graph.routes if routes is None else routes,
        channels=graph.channels,
        streams=STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
        spendable=graph.spendable,
    )


def _mismatched_path() -> FundingPath:
    """The domestic route, funded from a stream whose money is in another account."""
    return dataclasses.replace(route_graphs.zero_cost_graph().path, stream_id=SALARY_ELSEWHERE.id)


def _refused(path: FundingPath, amount: Money) -> RouteUnusable:
    outcome = _cost(path, amount)
    assert isinstance(outcome, RouteUnusable), outcome
    return outcome


class TestAStreamArrivingSomewhereElseIsRefusedByName:
    """The venue dimension. Reported, never costed as though the money were already there."""

    def test_the_route_is_reported_unusable_rather_than_costed(self) -> None:
        refused = _refused(_mismatched_path(), Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert refused.binding_constraint == "stream.arrives_at"
        assert refused.path.stream_id == SALARY_ELSEWHERE.id

    def test_the_reason_names_both_venues(self) -> None:
        # Both, because either one alone leaves the reader guessing what to change. The
        # remedy is a route from the venue the money lands in, and the output says which
        # venue that is.
        refused = _refused(_mismatched_path(), Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert ELSEWHERE in refused.reason
        assert route_graphs.ORIGIN_VENUE in refused.reason
        assert SALARY_ELSEWHERE.id in refused.reason

    def test_no_amount_is_invented_for_a_constraint_that_is_not_an_amount(self) -> None:
        # Nothing about this refusal is a quantity: the money is in the wrong place at any
        # size. A zero in these slots would put a number where there is none, and a
        # ``shortfall`` of zero reads as "it very nearly fitted".
        refused = _refused(_mismatched_path(), Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert refused.required is None
        assert refused.actual is None
        assert refused.shortfall is None

    def test_it_is_a_refusal_and_not_a_cost_of_zero(self) -> None:
        # The failure mode this exists to prevent: the domestic fixture costs exactly zero,
        # so a mismatch that fell through to the arithmetic would come back as a free route
        # -- the answer a reader would least question.
        outcome = _cost(_mismatched_path(), Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert not isinstance(outcome, RampCost)

    def test_the_matching_pair_is_not_refused(self) -> None:
        # The control. A test that only ever sees refusals proves nothing about the check
        # being about the venue at all.
        graph = route_graphs.zero_cost_graph()
        outcome = _cost(graph.path, Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert isinstance(outcome, RampCost)
        assert graph.route.origin == route_graphs.SALARY_UAH.arrives_at


class TestTheRightVenueInTheWrongCurrencyIsAlsoAMismatch:
    """The currency dimension. A multi-currency account is the ordinary case."""

    def test_a_dollar_stream_cannot_start_down_a_hryvnia_route(self) -> None:
        # Both arrive at ``venue_0``; the route's first leg moves hryvnia and the stream
        # delivers dollars. The venues agreeing is not enough, which is the whole point of
        # checking the currency separately.
        path = dataclasses.replace(
            route_graphs.zero_cost_graph().path, stream_id=route_graphs.CONTRACT_USD.id
        )
        refused = _refused(path, Money(238.0952380952381, Currency.USD, prov.EMPTY))
        assert refused.binding_constraint == "stream.amount.currency"
        assert route_graphs.CONTRACT_USD.arrives_at == route_graphs.ORIGIN_VENUE

    def test_the_reason_names_both_currencies_and_the_leg(self) -> None:
        path = dataclasses.replace(
            route_graphs.zero_cost_graph().path, stream_id=route_graphs.CONTRACT_USD.id
        )
        refused = _refused(path, Money(238.0952380952381, Currency.USD, prov.EMPTY))
        assert "USD" in refused.reason
        assert "UAH" in refused.reason
        assert "leg 0" in refused.reason

    def test_no_conversion_is_invented_to_bridge_it(self) -> None:
        # The alternative nobody should reach for: converting the stream's dollars into the
        # leg's hryvnia at *some* rate to make the arithmetic proceed. Every conversion in
        # this system is a declared leg with a declared two-sided channel (FR-010), and this
        # route declares none -- so the answer is a refusal, not a rate.
        path = dataclasses.replace(
            route_graphs.zero_cost_graph().path, stream_id=route_graphs.CONTRACT_USD.id
        )
        refused = _refused(path, Money(238.0952380952381, Currency.USD, prov.EMPTY))
        assert "no conversion is invented" in refused.reason


class TestTheMismatchIsReportedBeforeConstraintsThatDependOnTheDate:
    """Two refusals can be true at once, so the order they are checked in is a decision."""

    def test_a_mismatched_stream_on_a_closed_route_reports_the_mismatch(self) -> None:
        # Deliberate, and documented at ``cost_one``: the checks run from the least
        # dependent on circumstance to the most. A stream that does not reach its route is
        # wrong on every date and at every amount, while a closed route is a fact about this
        # date -- and declaring a route from where the money lands is the owner's next move
        # either way.
        graph = route_graphs.zero_cost_graph()
        closed = dataclasses.replace(graph.route, status="closed")
        outcome = _cost(
            _mismatched_path(),
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes={closed.id: closed},
        )
        assert isinstance(outcome, RouteUnusable)
        assert outcome.binding_constraint == "stream.arrives_at"


class TestAnIncoherentQuestionRaisesRatherThanReturningAFigure:
    """The line between a fact about the money and an error in the caller."""

    def test_a_path_naming_an_undeclared_stream_fails_naming_the_known_ones(self) -> None:
        # A path is built *from* the owner's declared streams, so a ``stream_id`` that does
        # not resolve means the caller assembled a path for a stream nobody declared. The
        # same reasoning -- and the same treatment -- as an undeclared ``route_id``.
        path = dataclasses.replace(
            route_graphs.zero_cost_graph().path, stream_id="stream_nobody_declared"
        )
        with pytest.raises(KeyError, match="unknown income stream") as raised:
            _cost(path, Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert route_graphs.SALARY_UAH.id in str(raised.value)

    def test_an_amount_not_in_the_streams_currency_raises(self) -> None:
        # The stream is part of what a cost *is*, so costing hryvnia "from" the dollar
        # contract income would attribute a real figure to income that never delivered it.
        # A caller's error rather than a fact about the money -- exactly as a currency
        # mismatch is in ``money`` -- so it raises rather than returning a refusal.
        path = dataclasses.replace(
            route_graphs.zero_cost_graph().path, stream_id=route_graphs.CONTRACT_USD.id
        )
        with pytest.raises(ValueError, match="cannot be funded from"):
            _cost(path, Money(10_000.0, Currency.UAH, prov.EMPTY))


class TestARankingExcludesTheMismatchWithItsReasonRatherThanDroppingIt:
    """FR-014 and FR-029 together: the same refusal, from the same costing function."""

    def _ranked(self) -> Ranking:
        graph = route_graphs.zero_cost_graph(with_exit=True)
        outcome = ranking.rank(
            [graph.path, dataclasses.replace(graph.path, stream_id=SALARY_ELSEWHERE.id)],
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=graph.spendable,
        )
        assert isinstance(outcome, Ranking), outcome
        return outcome

    def test_the_mismatched_candidate_is_excluded_and_the_other_is_ranked(self) -> None:
        ranked = self._ranked()
        assert len(ranked.costed) == 1
        assert len(ranked.excluded) == 1
        assert ranked.costed[0].path.stream_id == route_graphs.SALARY_UAH.id
        assert ranked.excluded[0].path.stream_id == SALARY_ELSEWHERE.id

    def test_nothing_was_silently_dropped(self) -> None:
        # Every candidate lands in exactly one of the three groups. A silent exclusion is
        # how a comparison comes to recommend the only route left standing.
        ranked = self._ranked()
        assert len(ranked.costed) + len(ranked.excluded) + len(ranked.not_comparable) == 2

    def test_the_exclusion_carries_the_same_reason_cost_one_gives(self) -> None:
        # The FR-029 half, and the reason ``streams`` had to reach both functions in one
        # change: the ranking's reasons are not written by the ranking. They are the ones
        # the single costing function produced for the very same path.
        ranked = self._ranked()
        graph = route_graphs.zero_cost_graph(with_exit=True)
        directly = cost.cost_one(
            dataclasses.replace(graph.path, stream_id=SALARY_ELSEWHERE.id),
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=graph.spendable,
        )
        assert ranked.excluded[0] == directly

    def test_a_ranking_of_nothing_but_mismatches_is_not_a_ranking(self) -> None:
        # No comparable candidate, so :class:`NothingComparable` rather than a ranking with
        # an empty ``costed`` and an index pointing at nothing -- and the reasons survive.
        graph = route_graphs.zero_cost_graph(with_exit=True)
        outcome = ranking.rank(
            [dataclasses.replace(graph.path, stream_id=SALARY_ELSEWHERE.id)],
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=graph.spendable,
        )
        assert isinstance(outcome, NothingComparable)
        assert len(outcome.excluded) == 1
        assert outcome.excluded[0].binding_constraint == "stream.arrives_at"
