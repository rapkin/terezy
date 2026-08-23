"""FR-009, SC-006: a route that converts nothing reports **exactly** zero, not a residual.

*A route that performs no conversion MUST report a conversion cost of exactly zero, not a
small residual.*

The dollar stream is why this requirement exists. ``SIMULATOR_SPEC.md`` §4.2: money that
arrives in dollars needs no hryvnia-to-dollar conversion, so the 5-10% ramp of §4.3.1 applies
to the hryvnia salary and not to the contract income. A route funded from that stream with no
``fx`` leg has no rate to apply, so its conversion cost is not *small* -- it does not exist,
and the number reported for it must say so exactly.

**Why "small" would be a real defect and not a rounding quibble.** A residual would mean a
rate was applied to money that never changed currency: the route would look slightly
expensive for a reason no declaration could explain, and the §4.3.1 comparison -- nearly free
from one stream, several percent from the other -- would lose its sharp edge for no cause. A
tolerance check would pass either way, which is exactly why the assertions below use ``==``
against ``0.0`` and, where the point is strongest, ``float.hex()``.

## The zero cites its own declaration

The zero is **not** an unmarked ``money.zero``. ``legs._fee_only_cost`` builds it as
``money.scale_sourced(amount, 0.0, leg.provenance)``, so it carries the provenance of the leg
that declared this movement converts nothing. That is the precedent set for a zero tax charge
in feature 001, for the same reason: a zero that cannot cite its own declaration is
indistinguishable from a conversion nobody costed, and the two are very different claims. It
is asserted below rather than left to the reader, because a later refactor reaching for
``money.zero`` here would be invisible in every number.

This module is the other half of ``tests/worked_examples/test_two_streams.py``, which pins
the same route's arriving amount against the hand arithmetic of the whole G1 comparison.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import CostComponent, ExitCostUnknown, RampCost
from terezy.core.routes import cost
from tests.invariants import route_graphs

CONVERSION = CostComponent.CONVERSION_SPREAD
"""The component under test: what a channel's spread cost. Zero here, and exactly."""


def _costed(amount: float) -> RampCost:
    """Cost dollars from the dollar stream along the route with no ``fx`` leg."""
    graph = route_graphs.usd_direct_graph()
    outcome = cost.cost_one(
        graph.path,
        Money(amount, Currency.USD, prov.EMPTY),
        routes=graph.routes,
        channels=graph.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
        spendable=graph.spendable,
    )
    assert isinstance(outcome, RampCost), outcome
    return outcome


class TestTheConversionComponentIsExactlyZero:
    """FR-009 at face value, and at several magnitudes."""

    @pytest.mark.parametrize(
        "amount",
        [
            0.0,  # nothing moved: nothing converted, and no division to go wrong
            0.01,  # one cent, where a residual would be largest as a fraction
            1e-08,  # far below any real ticket, so a fixed residual would show up
            238.0952380952381,  # the G1 amount: ten thousand hryvnia at the reference
            12_345.678,  # nothing round, so no accidental exactness
            1e09,  # a billion, where a relative residual would be largest absolutely
        ],
    )
    def test_no_amount_produces_a_residual(self, amount: float) -> None:
        # ``==``, not the project tolerance. A tolerance check would pass for a residual, and
        # a residual is precisely the thing FR-009 forbids: this route applies no rate, so
        # there is no arithmetic here that could legitimately land near zero rather than on
        # it.
        component = _costed(amount).one_way.components[CONVERSION]
        assert component.amount == 0.0
        assert component.amount.hex() == (0.0).hex()

    def test_the_cost_fraction_is_exactly_zero_too(self) -> None:
        # The headline figure, and the one a comparison sorts on. Zero fees and zero
        # conversion, so the whole cost is zero -- the bar SC-004 sets for the domestic
        # route, met here by the dollar stream on an offshore one.
        costed = _costed(238.0952380952381)
        assert costed.one_way.fraction == 0.0
        assert all(part.amount == 0.0 for part in costed.one_way.components.values())

    def test_what_was_sent_arrives_bit_for_bit_in_the_same_currency(self) -> None:
        # No conversion means no restatement: the same float, and the same currency tag.
        # ``money.convert`` refuses a same-currency conversion outright, so an arriving
        # amount that had been "converted" to dollars would have raised rather than rounded.
        costed = _costed(12_345.678)
        assert costed.one_way.arrived.currency is Currency.USD
        assert costed.one_way.arrived.amount.hex() == (12_345.678).hex()
        assert costed.one_way.sent.amount.hex() == (12_345.678).hex()


class TestTheZeroSaysWhyItIsZero:
    """Principle I: a figure that cannot cite its own declaration is not a figure."""

    def test_the_zero_carries_the_provenance_of_the_leg_that_declared_it(self) -> None:
        # The declared zero, not the additive identity. ``money.zero`` would be unmarked,
        # and an unmarked zero cannot be told apart from a conversion nobody costed.
        component = _costed(238.0952380952381).one_way.components[CONVERSION]
        assert component.provenance != prov.EMPTY
        assert route_graphs.FEE_SOURCE in component.provenance.sources

    def test_the_component_is_present_as_a_key_rather_than_absent(self) -> None:
        # "No conversion happened" and "the conversion cost is unknown" are different
        # claims, and a missing key would read as the second while meaning the first.
        costed = _costed(238.0952380952381)
        assert set(costed.one_way.components) == set(CostComponent)

    def test_the_zero_is_still_marked_unverified_because_its_declaration_is(self) -> None:
        # Every route number in this feature rests on an unverified declaration, and a zero
        # is not exempt: it is zero *according to* a leg nobody has checked against a
        # primary source, and the mark says so (FR-022).
        component = _costed(238.0952380952381).one_way.components[CONVERSION]
        assert prov.is_unverified(component.provenance)


class TestNoChannelWasConsultedAtAll:
    """FR-011 from the negative side: nothing was applied, so nothing is named."""

    def test_no_channel_is_reported_as_applied(self) -> None:
        costed = _costed(238.0952380952381)
        assert costed.one_way.channels_applied == ()

    def test_no_rate_space_spread_is_reported_either(self) -> None:
        # ``None`` rather than ``0.0`` at the leg, and therefore an empty tuple here: a zero
        # would read as "at the reference", which is a claim about a conversion that never
        # happened. This route has no reference rate to have a spread over.
        costed = _costed(238.0952380952381)
        assert costed.one_way.spreads_over_reference == ()

    def test_a_declared_channel_does_not_make_a_conversion_happen(self) -> None:
        # The stronger statement, and the one worth protecting: the fixture declares the
        # same P2P channel the hryvnia path crosses, and this route still converts nothing.
        # A conversion happens because a leg declares kind ``fx``, never because a rate
        # was available.
        graph = route_graphs.usd_direct_graph()
        assert route_graphs.CHANNEL_ID in graph.channels
        assert all(leg.channel is None for leg in graph.route.legs)
        assert all(leg.kind != "fx" for leg in graph.route.legs)


class TestTheContrastWithTheHryvniaPathIsTheWholeFinding:
    """A zero that is only ever zero proves nothing; this is the control."""

    def test_the_same_component_is_far_from_zero_when_a_conversion_does_happen(self) -> None:
        # Ten thousand hryvnia through the P2P route pays 666.67 UAH of spread on the same
        # component that is exactly zero above. The component is not inert -- it is zero
        # because nothing converted.
        graph = route_graphs.p2p_graph()
        outcome = cost.cost_one(
            graph.path,
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=graph.spendable,
        )
        assert isinstance(outcome, RampCost)
        assert outcome.one_way.components[CONVERSION].amount > 0.0
        assert outcome.one_way.channels_applied == (route_graphs.CHANNEL_ID,)


class TestCostingNothingIsNotTheSameAsBeingComparable:
    """FR-030 still applies to a free route, and that is not a contradiction."""

    def test_the_route_with_no_declared_exit_has_no_round_trip_figure(self) -> None:
        # Free to get in is not the same as free to get out, and nobody has declared how
        # dollars at an exchange become spendable hryvnia -- §4.2 notes that converting the
        # dollar stream *to* hryvnia is the expensive direction. So the round-trip slot holds
        # a statement rather than a zero, and this route is not comparison-ready.
        costed = _costed(238.0952380952381)
        assert isinstance(costed.round_trip, ExitCostUnknown)
        assert costed.round_trip.missing_partner_for == "usd_direct_to_binance"
        assert not hasattr(costed.round_trip, "fraction")
