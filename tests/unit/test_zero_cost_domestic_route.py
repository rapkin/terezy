"""SC-004: a route whose every leg declares zero costs **exactly** zero. The bar.

*A fully domestic route with zero declared fees costs exactly zero and delivers exactly what was
sent.*

**Why this is worth its own module.** Every other figure in this feature is measured against
this one. §4.3.1's finding is a *comparison* -- the P2P route costs 13.33% round trip and the
domestic route costs nothing -- so a domestic route that leaked a small residual would make
every such comparison slightly flattering to the expensive alternative, and it would do so
invisibly. A residual of a hundredth of a percent is indistinguishable from rounding to anyone
reading the output and it moves the hurdle rate the whole project exists to compute.

**"Exactly" is meant literally, and that is why nothing here uses the tolerance.** The project
tolerance exists because hand arithmetic and float arithmetic differ in the last bits; it is not
slack for a modelling disagreement. Zero times an amount is zero in float64 with no error at
all, and a subtraction of an exact zero returns the operand unchanged. So the assertions below
are ``== 0.0`` and ``== SENT``, and if one of them ever needs a tolerance the right response is
to find out what introduced the error rather than to widen the bound.

**Every component is a present key, not an absent one** (FR-009). "No conversion happened" and
"the conversion cost is unknown" are different claims, and an absent key would read as the second
while meaning the first -- the same reason a zero tax charge has to cite its exemption.

``tests/invariants/test_cost_attribution.py`` asserts the one-way half of this over the generated
graphs. What this module adds is the parts a property test cannot reach: the **round trip**
through a declared zero-cost exit, the channel list being empty rather than merely harmless, the
ranking treating this route as the cheapest thing available, and the arithmetic staying exact for
amounts across several orders of magnitude.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import (
    CostComponent,
    ExitCostUnknown,
    RampCost,
    Ranking,
    RoundTripCost,
    recommended_cost,
)
from terezy.core.routes import cost, ranking
from terezy.core.routes.path import candidate_id
from tests.invariants import route_graphs

SENT = 10_000.0
"""Ten thousand hryvnia, the amount used throughout this feature's examples."""


def _costed(*, amount: float = SENT, with_exit: bool = False) -> RampCost:
    graph = route_graphs.zero_cost_graph(with_exit=with_exit)
    costed = cost.cost_one(
        graph.path,
        Money(amount, Currency.UAH, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )
    assert isinstance(costed, RampCost), costed
    return costed


class TestTheOneWayCostIsExactlyZero:
    """Not within tolerance of zero. Zero."""

    def test_exactly_what_was_sent_arrives(self) -> None:
        # Two transfer legs, each declaring a zero percentage and a zero fixed fee. Ten
        # thousand in, ten thousand out, in the same currency, with no arithmetic in between
        # that could round anything.
        one_way = _costed().one_way
        assert one_way.arrived.amount == SENT
        assert one_way.arrived.currency is Currency.UAH
        assert one_way.sent.amount == SENT

    def test_the_cost_fraction_is_exactly_zero(self) -> None:
        assert _costed().one_way.fraction == 0.0

    def test_every_component_is_present_and_every_one_is_exactly_zero(self) -> None:
        # The closed enumeration, in full. A missing key would be the honest-looking bug:
        # the sum would still come to zero, and "we did not charge for a conversion" would
        # have become "nobody costed the conversion" with nothing in the output to say so.
        components = _costed().one_way.components
        assert set(components) == set(CostComponent)
        for component, charge in components.items():
            assert charge.amount == 0.0, component
            assert charge.currency is Currency.UAH, component

    def test_no_channel_was_applied_because_nothing_was_converted(self) -> None:
        # Empty rather than a channel that happened to charge nothing (FR-009). A domestic
        # route consults no rate at all, and a channel appearing here would mean a
        # conversion had been priced -- at zero this time, and at something else next time.
        assert _costed().one_way.channels_applied == ()


class TestTheRoundTripIsExactlyZeroToo:
    """FR-002: the figure that belongs in a comparison, and it is also zero."""

    def test_the_declared_zero_cost_exit_returns_exactly_what_it_was_given(self) -> None:
        costed = _costed(with_exit=True)
        assert isinstance(costed.round_trip, RoundTripCost)
        assert costed.round_trip.arrived.amount == SENT
        assert costed.round_trip.fraction == 0.0
        assert costed.round_trip.channels_applied == ()

    def test_the_round_trip_components_are_all_exactly_zero(self) -> None:
        costed = _costed(with_exit=True)
        assert isinstance(costed.round_trip, RoundTripCost)
        assert set(costed.round_trip.components) == set(CostComponent)
        assert all(charge.amount == 0.0 for charge in costed.round_trip.components.values())

    def test_a_zero_cost_route_with_no_declared_exit_still_has_no_round_trip_figure(
        self,
    ) -> None:
        # Zero cost does not excuse a missing exit (FR-030). It is tempting here above all --
        # the way in cost nothing, so surely the way out does too -- and that inference is
        # exactly the confident number for a path nobody has looked at. The default fixture
        # declares no partner, and the slot holds a statement rather than a zero.
        costed = _costed()
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.round_trip.missing_partner_for == "inzhur_direct"


class TestTheExactnessSurvivesTheAmount:
    """A residual would show up at some scale, so several are checked."""

    @pytest.mark.parametrize("amount", [0.0, 1.0, 0.01, 12_345.67, 1_000_000.0, 1e12])
    def test_zero_declared_costs_stay_zero_at_every_scale(self, amount: float) -> None:
        # Including zero itself: a route that charges nothing on nothing costs nothing, and
        # the fraction is zero rather than the infinity a flat fee would produce. And
        # including a twelve-figure sum, where an error of one part in 1e15 would be visible
        # as a fraction of a kopiyka.
        costed = _costed(amount=amount)
        assert costed.one_way.arrived.amount == amount
        assert costed.one_way.fraction == 0.0
        assert all(charge.amount == 0.0 for charge in costed.one_way.components.values())

    def test_the_arriving_amount_is_the_same_float_and_not_merely_a_close_one(self) -> None:
        # Bit identity, stated through the hex form the canonical result form uses. Stricter
        # than the tolerance, deliberately: the claim is that no arithmetic happened, and a
        # value that had been through a multiplication by 1.0 would still pass a tolerance
        # check while proving the arithmetic ran.
        costed = _costed(amount=12_345.67)
        assert costed.one_way.arrived.amount.hex() == (12_345.67).hex()


class TestTheBarIsWhatARankingMeasuresAgainst:
    """The reason SC-004 is worth asserting: it anchors every comparison."""

    def _ranked(self) -> Ranking:
        domestic = route_graphs.zero_cost_graph(with_exit=True)
        offshore = route_graphs.p2p_graph()
        ranked = ranking.rank(
            [domestic.path, offshore.path],
            Money(SENT, Currency.UAH, prov.EMPTY),
            routes={**domestic.routes, **offshore.routes},
            channels=offshore.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(ranked, Ranking), ranked
        return ranked

    def test_the_free_route_is_the_recommendation_and_its_cost_is_zero(self) -> None:
        recommended = recommended_cost(self._ranked())
        assert candidate_id(recommended.path) == "inzhur_direct"
        assert isinstance(recommended.round_trip, RoundTripCost)
        assert recommended.round_trip.fraction == 0.0

    def test_a_free_route_is_not_reported_as_tied_with_an_expensive_one(self) -> None:
        # The other direction of the tolerance question. Zero and 13.33% are not the same
        # answer, and a tolerance loose enough to call them one would have absorbed the
        # entire finding.
        assert self._ranked().ties == ()
