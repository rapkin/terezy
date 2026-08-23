"""**G4**, FR-019, FR-020, SC-009: the war ends, the route set changes, and the cost drops.

Required test **G4**: *a regime transition on the war-end date switches the route set;
round-trip cost drops by exactly the hand-computed difference.* SC-009 states it as a
measurement, and User Story 4's independent test as a procedure: *declare two regimes and a
transition date; confirm contributions before and after use different route sets and that the
round-trip cost drops by exactly the hand-computed difference.*

## What kind of statement this test is making

Everything below rests on **one assumption and no observations**. The transition date is a
belief about the future -- "the war ends mid-2027" -- and nobody knows it. That is the whole
reason a regime is not expressed as a leg availability window (research.md D8): a leg's
``available_from``/``available_until`` is a *fact* about a corridor with a source behind it
("this closed in March 2025"), while a regime transition is a *guess*. Written into the same
field, the two would be indistinguishable in every output, and no report could tell "this
route is closed because it closed" from "this route is closed because I picked a date".

So the last class in this module asserts the negative: **not one leg in either corridor
carries the transition date**, and no leg field mentions it. The date exists in exactly one
place -- a ``RegimeTransition`` whose ``is_assumption`` is structurally ``True`` and whose
``rationale`` says in words what is being assumed.

## The two corridors, and why they differ in exactly one thing

Both corridors start at the same venue, end at the same venue, are funded by the same hryvnia
salary, carry the same 10 000 UAH, and price their conversions against the **same reference
rate of 42 UAH per dollar** out of the **same channels mapping**. The only difference is the
spread the corridor charges:

* **wartime** -- the P2P book. A premium of ``+3`` in and ``-3`` out, so the price is 45 UAH
  per dollar going in and 39 coming back.
* **normalized** -- a bank. A premium of ``+0.5`` in and ``-0.5`` out: 42.5 in, 41.5 back.

Everything else is held fixed on purpose. Had each regime been costed against its own channels
mapping, the *rate* would have moved with the route set and the drop would have had two causes;
had the corridors ended at different venues it would have had three. One variable, one drop.

## The arithmetic, by hand, in full

Sending 10 000 UAH and bringing it all the way back, through the corridor in force:

```
wartime      in   10 000 / 45              =   222.222222... USD
             out    222.222222... x 39     = 8 666.666666... UAH
             cost 10 000 - 8 666.666666    = 1 333.333333... UAH
             fraction = 1 - 39/45 = 6/45   = 2/15 = 0.133333333...   = 13.3333%

normalized   in   10 000 / 42.5            =   235.294117... USD
             out    235.294117... x 41.5   = 9 764.705882... UAH
             cost 10 000 - 9 764.705882    =   235.294117... UAH
             fraction = 1 - 41.5/42.5      = 1/42.5 = 2/85 = 0.023529411... = 2.3529%
```

and therefore the drop, which is the figure **G4** names:

```
in rate space   2/15 - 2/85 = 34/255 - 6/255 = 28/255 = 0.10980392156862745
in money        1 333.333333... - 235.294117... = 1 098.039215686274... UAH
                which is 10 000 x 28/255 = 280 000/255, the same number
```

A round trip needs no reference rate **as an input**: it is what you get back over what you
put in, so each fraction above is a pure ratio of the two prices and is hand-checkable without
knowing what the reference was. ``28/255`` is therefore exact -- not rounded, not approximated.

**It is not, however, independent of the reference**, and that distinction is worth keeping
straight because the first version of this docstring blurred it. The prices themselves are
``r + p`` and ``r - p``, so a different reference with the same premia gives a different drop:
at 42 it is 10.98%, at 30 it is 14.90%, at 55 it is 8.54%. What the formula does not *take* is
not the same as what the answer does not *depend on*. The figure is exact for the declared
reference, which is the claim the assertions make.

**1 098 UAH on 10 000.** Worth stating in money as well as in percent: this is the number the
owner is being asked to wait for, and the break-even §8 question 2 asks about -- fund now at
wartime cost, or wait -- is a comparison between that 1 098 and whatever the delay costs.

## What is *not* claimed

The drop is conditional on the assumption. Nothing here says the war ends in mid-2027, and
nothing here says the bank corridor will exist when it does. The tool's claim is narrower and
honest: *if* you believe this, then this is what it is worth, and here is the belief, labelled.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import NothingComparable, RampCost, RoundTripCost, recommended_cost
from terezy.core.routes import cost, ranking
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Route
from terezy.core.routes.path import FundingPath, candidate_id
from terezy.core.scenarios import regimes
from tests.invariants import route_graphs

pytestmark = pytest.mark.worked_example

SENT = 10_000.0
"""What departs, in hryvnia. Round, so the divisions above stay readable."""

REFERENCE = 42.0
"""UAH per USD, the same for both corridors. Invented, like every rate in this feature."""

P2P_BUY_PRICE = 45.0
"""42 + 3: the wartime price going in."""

P2P_SELL_PRICE = 39.0
"""42 - 3: the wartime price coming back."""

BANK_BUY_PRICE = 42.5
"""42 + 0.5: the normalized price going in."""

BANK_SELL_PRICE = 41.5
"""42 - 0.5: the normalized price coming back."""

TRANSITION_DATE = date(2027, 7, 1)
"""The assumed date. **Nobody knows this.** It is the middle of 2027 because "mid-2027" is
what the belief says, and the first of July is the first day of that half -- a choice, stated,
rather than a fact."""

BEFORE = date(2027, 6, 30)
"""The day before. Wartime."""

ON_THE_DAY = TRANSITION_DATE
"""The transition date itself, which belongs to the regime *after* it -- see
:class:`TestTheRouteSetSwitchesOnTheDate`."""

AFTER = date(2027, 8, 15)
"""Well after. Normalized."""

AS_OF = route_graphs.AS_OF
"""When the question is asked: 2026-08-21, **today**, for every costing below.

Deliberately fixed while ``on_date`` moves a year into the future, because the two dates
answer different questions (research.md D9). ``on_date`` decides which regime is in force;
``as_of`` decides whether the declared numbers are stale. Conflating them would make the
normalized costing report every one of its inputs as stale by a year, and the drop would then
be part staleness artefact.
"""

WARTIME_ROUTES = ("monobank_to_binance_p2p", "binance_p2p_to_monobank")
NORMALIZED_ROUTES = ("bank_uah_to_broker", "broker_to_bank")

WARTIME = regimes.Regime(id="wartime", route_ids=frozenset(WARTIME_ROUTES))
"""Only the P2P corridor exists. Both directions of it: a regime that let money out but not
back would be a different claim, and it would be made by a route declaring no partner."""

NORMALIZED = regimes.Regime(id="normalized", route_ids=frozenset(NORMALIZED_ROUTES))
"""Only the bank corridor exists. The P2P book has not become illegal -- it has become
irrelevant, which for a comparison is the same thing."""

REGIMES: Mapping[str, regimes.Regime] = {WARTIME.id: WARTIME, NORMALIZED.id: NORMALIZED}

TRANSITION = regimes.RegimeTransition(
    on_date=TRANSITION_DATE,
    before=WARTIME.id,
    after=NORMALIZED.id,
    is_assumption=True,
    rationale=(
        "The owner assumes wartime capital controls are relaxed around the middle of 2027 and "
        "that ordinary bank conversion at close to the official rate becomes available again. "
        "This is a belief about the future and not an observation: no source states it, no "
        "figure in this project supports it, and the date is a stated choice."
    ),
)
"""The one transition this feature declares (data-model.md's ⚙ note: one, deliberately).

``is_assumption=True`` is written out at the construction site rather than defaulted, which is
the whole point of a field whose type admits one value: it cannot be omitted, so nobody builds
a transition without saying out loud what it is.
"""

TRANSITIONS = (TRANSITION,)


def _world() -> tuple[Mapping[str, Route], Mapping[str, FxChannel]]:
    """Every declared route and every declared channel, in both regimes at once.

    **One mapping of each, for both sides of the transition.** Declarations do not come and go
    with the owner's beliefs: the corridors are all declared, and the *regime* is what says
    which of them exist on a date. Handing each side its own world would make the regime
    unnecessary and the drop unattributable.
    """
    wartime = route_graphs.p2p_graph()
    normalized = route_graphs.bank_corridor_graph()
    return (
        {**wartime.routes, **normalized.routes},
        {**wartime.channels, **normalized.channels},
    )


def _in_force(on_date: date) -> regimes.RoutesInForce:
    routes, _ = _world()
    return regimes.routes_in_force(REGIMES, routes, transitions=TRANSITIONS, on_date=on_date)


def _costed(route_id: str, on_date: date) -> RampCost:
    """Cost 10 000 UAH along one corridor on one date, whatever the regime says.

    Every declared route is passed, so this says nothing about which corridor is in force --
    that is :func:`_in_force`'s answer, and keeping the two separate is what lets the last
    class in this module cost the *ruled-out* corridor and show that it still works.
    """
    routes, channels = _world()
    costed = cost.cost_one(
        FundingPath(destination_id="venue_1", stream_id="salary_uah", route_id=route_id),
        Money(SENT, Currency.UAH, prov.EMPTY),
        routes=routes,
        channels=channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=on_date,
        as_of=AS_OF,
    )
    assert isinstance(costed, RampCost), costed
    return costed


def _cost(route_id: str, on_date: date) -> RampCost:
    """:func:`_costed`, having first asserted the regime in force admits the corridor.

    So a test that thought it was costing the wartime corridor after the transition fails on
    the *regime* rather than quietly producing a number.
    """
    in_force = _in_force(on_date)
    assert route_id in in_force.routes, (route_id, sorted(in_force.routes))
    return _costed(route_id, on_date)


def _round_trip(costed: RampCost) -> RoundTripCost:
    assert isinstance(costed.round_trip, RoundTripCost), costed.round_trip
    return costed.round_trip


class TestTheRouteSetSwitchesOnTheDate:
    """Acceptance scenario 1: contributions before the date use the first set, after the second."""

    def test_before_the_transition_only_the_wartime_corridor_is_in_force(self) -> None:
        in_force = _in_force(BEFORE)
        assert in_force.regime.id == WARTIME.id
        assert set(in_force.routes) == set(WARTIME_ROUTES)

    def test_after_the_transition_only_the_normalized_corridor_is_in_force(self) -> None:
        in_force = _in_force(AFTER)
        assert in_force.regime.id == NORMALIZED.id
        assert set(in_force.routes) == set(NORMALIZED_ROUTES)

    def test_the_transition_date_itself_belongs_to_the_regime_after_it(self) -> None:
        # A boundary with two defensible readings, so it is decided and then asserted rather
        # than left to whichever comparison got written. "The war ends on the first of July"
        # means the first of July is a day of peace: the transition date is the first day of
        # the new regime, not the last day of the old one.
        assert _in_force(ON_THE_DAY).regime.id == NORMALIZED.id
        assert _in_force(date(2027, 6, 30)).regime.id == WARTIME.id

    def test_what_the_regime_leaves_out_is_named_rather_than_quietly_absent(self) -> None:
        # An exclusion for an *assumed* reason must still be visible, or the output would show
        # a comparison of one route with no hint that three others were ruled out by a guess.
        assert _in_force(BEFORE).excluded == tuple(sorted(NORMALIZED_ROUTES))
        assert _in_force(AFTER).excluded == tuple(sorted(WARTIME_ROUTES))

    def test_the_selection_records_the_transition_that_decided_it(self) -> None:
        # Not the regime alone: the *reason* the regime was chosen has to travel with the
        # answer, because the reason is an assumption and the answer is a number.
        for on_date in (BEFORE, ON_THE_DAY, AFTER):
            assert _in_force(on_date).decided_by is TRANSITION
            assert _in_force(on_date).on_date == on_date


class TestTheCostBeforeTheTransition:
    """13.33% round trip, because the only corridor is the P2P book."""

    def test_ten_thousand_hryvnia_buys_two_hundred_and_twenty_two_dollars(self) -> None:
        #   10 000 / 45 = 222.22222222222223 USD
        costed = _cost("monobank_to_binance_p2p", BEFORE)
        assert costed.one_way.arrived.currency is Currency.USD
        assert is_close(costed.one_way.arrived.amount, SENT / P2P_BUY_PRICE)
        assert is_close(costed.one_way.arrived.amount, 222.22222222222223)

    def test_the_round_trip_costs_two_fifteenths(self) -> None:
        #   out  222.222222... x 39 = 8 666.666666... UAH
        #   cost 10 000 - 8 666.667 = 1 333.333333... UAH
        #   fraction = 1 - 39/45 = 6/45 = 2/15 = 0.13333333333333333
        round_trip = _round_trip(_cost("monobank_to_binance_p2p", BEFORE))
        assert is_close(round_trip.fraction, 1.0 - P2P_SELL_PRICE / P2P_BUY_PRICE)
        assert is_close(round_trip.fraction, 2.0 / 15.0)
        assert is_close(round_trip.fraction, 0.13333333333333333)
        assert round_trip.arrived.currency is Currency.UAH
        assert is_close(round_trip.arrived.amount, SENT * P2P_SELL_PRICE / P2P_BUY_PRICE)
        assert is_close(round_trip.arrived.amount, 8666.666666666666)
        assert is_close(SENT - round_trip.arrived.amount, 1333.3333333333333)


class TestTheCostAfterTheTransition:
    """2.35% round trip, because the corridor is a bank at 0.5 UAH per dollar."""

    def test_ten_thousand_hryvnia_buys_two_hundred_and_thirty_five_dollars(self) -> None:
        #   10 000 / 42.5 = 235.29411764705884 USD -- 13 dollars more than the P2P price
        #   bought, on the same 10 000 and the same reference rate.
        costed = _cost("bank_uah_to_broker", AFTER)
        assert costed.one_way.arrived.currency is Currency.USD
        assert is_close(costed.one_way.arrived.amount, SENT / BANK_BUY_PRICE)
        assert is_close(costed.one_way.arrived.amount, 235.29411764705884)

    def test_the_round_trip_costs_two_eighty_fifths(self) -> None:
        #   out  235.294117... x 41.5 = 9 764.705882... UAH
        #   cost 10 000 - 9 764.706   =   235.294117... UAH
        #   fraction = 1 - 41.5/42.5 = 1/42.5 = 2/85 = 0.023529411764705882
        round_trip = _round_trip(_cost("bank_uah_to_broker", AFTER))
        assert is_close(round_trip.fraction, 1.0 - BANK_SELL_PRICE / BANK_BUY_PRICE)
        assert is_close(round_trip.fraction, 2.0 / 85.0)
        assert is_close(round_trip.fraction, 0.023529411764705882)
        assert round_trip.arrived.currency is Currency.UAH
        assert is_close(round_trip.arrived.amount, SENT * BANK_SELL_PRICE / BANK_BUY_PRICE)
        assert is_close(round_trip.arrived.amount, 9764.70588235294)
        assert is_close(SENT - round_trip.arrived.amount, 235.29411764705884)


class TestTheDrop:
    """**G4**'s figure: the difference, in rate space and in hryvnia, and nothing else in it."""

    def test_the_round_trip_fraction_drops_by_twenty_eight_two_hundred_and_fifty_fifths(
        self,
    ) -> None:
        #   2/15 - 2/85 = 34/255 - 6/255 = 28/255 = 0.10980392156862745
        # Both terms are ratios of prices, so neither needs the reference as an input and the
        # difference is exact rather than a residue of the rate that was chosen.
        before = _round_trip(_cost("monobank_to_binance_p2p", BEFORE))
        after = _round_trip(_cost("bank_uah_to_broker", AFTER))
        drop = before.fraction - after.fraction
        assert is_close(drop, 2.0 / 15.0 - 2.0 / 85.0)
        assert is_close(drop, 28.0 / 255.0)
        assert is_close(drop, 0.10980392156862745)

    def test_the_drop_in_hryvnia_on_ten_thousand_is_one_thousand_and_ninety_eight(self) -> None:
        #   1 333.333333... - 235.294117... = 1 098.039215686274... UAH
        #   equivalently 10 000 x 28/255 = 280 000/255
        # In money because a percentage is easy to discount and a number of hryvnia is not:
        # this is what the assumption is worth on a single 10 000 UAH contribution.
        before = _round_trip(_cost("monobank_to_binance_p2p", BEFORE))
        after = _round_trip(_cost("bank_uah_to_broker", AFTER))
        drop = (SENT - before.arrived.amount) - (SENT - after.arrived.amount)
        assert is_close(drop, SENT * 28.0 / 255.0)
        assert is_close(drop, 1098.0392156862745)
        # And it is the same number the other way round: what comes back rises by exactly what
        # the cost falls by, because both corridors send the same 10 000.
        assert is_close(after.arrived.amount - before.arrived.amount, drop)

    def test_the_drop_is_not_a_staleness_artefact_because_as_of_never_moved(self) -> None:
        # ``on_date`` moves fourteen months; ``as_of`` does not move at all. If the two were
        # one argument, the normalized costing would be evaluating year-old declarations and
        # part of the "drop" would be the engine changing its mind about the inputs.
        for route_id in ("monobank_to_binance_p2p", "bank_uah_to_broker"):
            early = _costed(route_id, BEFORE)
            late = _costed(route_id, AFTER)
            assert early.one_way.staleness == late.one_way.staleness
            assert is_close(early.one_way.fraction, late.one_way.fraction)


class TestARankingSeesOnlyTheCorridorsInForce:
    """The regime filters the *candidates*, and never disguises itself as a route's own limit.

    A route the regime rules out must not arrive in ``Ranking.excluded``: that field carries
    ``RouteUnusable`` records whose ``binding_constraint`` names a declared field -- a fact with
    a source. An assumed exclusion landing there would be indistinguishable from an observed
    one, which is precisely the confusion research.md D8 exists to prevent. So the regime narrows
    the candidate paths *before* the ranking, and what it left out is reported by
    :attr:`RoutesInForce.excluded` instead.
    """

    def _ranked(self, on_date: date) -> tuple[str, float]:
        routes, channels = _world()
        candidates = (
            FundingPath(
                destination_id="venue_1",
                stream_id="salary_uah",
                route_id="monobank_to_binance_p2p",
            ),
            FundingPath(
                destination_id="venue_1", stream_id="salary_uah", route_id="bank_uah_to_broker"
            ),
        )
        in_force = regimes.routes_in_force(
            REGIMES, routes, transitions=TRANSITIONS, on_date=on_date
        )
        ranked = ranking.rank(
            regimes.paths_in_force(candidates, in_force),
            Money(SENT, Currency.UAH, prov.EMPTY),
            routes=in_force.routes,
            channels=channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=on_date,
            as_of=AS_OF,
        )
        assert not isinstance(ranked, NothingComparable), ranked
        assert ranked.excluded == (), ranked.excluded
        recommended = recommended_cost(ranked)
        assert isinstance(recommended.round_trip, RoundTripCost)
        return candidate_id(recommended.path), recommended.round_trip.fraction

    def test_the_same_contribution_is_ranked_through_a_different_corridor_on_each_side(
        self,
    ) -> None:
        # The same two candidate paths, the same amount, the same channels, the same as-of
        # date. Only ``on_date`` differs, and the recommendation changes with it.
        assert self._ranked(BEFORE)[0] == "monobank_to_binance_p2p"
        assert self._ranked(AFTER)[0] == "bank_uah_to_broker"

    def test_the_recommended_round_trip_cost_drops_by_the_hand_computed_difference(self) -> None:
        # G4, end to end through the ranking rather than through a single costing: the
        # recommendation the owner would actually be shown gets 28/255 cheaper.
        assert is_close(self._ranked(BEFORE)[1] - self._ranked(AFTER)[1], 28.0 / 255.0)


class TestNothingInTheRouteDataKnowsTheTransitionDate:
    """research.md D8, stated as the absence it is: the guess is in exactly one place.

    This is the assertion that keeps the feature honest. If a future change expressed the
    regime by writing 2027-07-01 into ``available_until`` on the P2P legs, every test above
    would still pass -- the route set would still switch on the date and the cost would still
    drop by 28/255 -- and the output would then report the wartime corridor as *closed*, with a
    ``binding_constraint`` of ``leg.available_until``, in the same shape it reports a corridor
    that genuinely closed. This class is what fails instead.
    """

    def test_no_leg_in_either_corridor_declares_an_availability_window(self) -> None:
        routes, _ = _world()
        for route in routes.values():
            for leg in route.legs:
                assert leg.available_from is None, (route.id, leg.index)
                assert leg.available_until is None, (route.id, leg.index)

    def test_the_transition_date_appears_in_no_leg_field_at_all(self) -> None:
        # Broader than the window check on purpose: any date-valued leg field would do the
        # same damage, and a scan of the values catches one that has not been invented yet.
        routes, _ = _world()
        for route in routes.values():
            for leg in route.legs:
                dates = [
                    value
                    for value in (getattr(leg, field.name) for field in dataclasses.fields(leg))
                    if isinstance(value, date)
                ]
                assert TRANSITION_DATE not in dates, (route.id, leg.index, dates)

    def test_both_corridors_are_open_on_both_dates_and_the_regime_is_the_only_switch(
        self,
    ) -> None:
        # The corridor the regime rules out is perfectly costable on that date -- which is
        # what makes the exclusion an assumption rather than a fact. Costing the wartime
        # corridor *after* the transition still works and still costs 2/15; the reason not to
        # use it is a belief, and the belief lives outside the route.
        for route_id in ("monobank_to_binance_p2p", "bank_uah_to_broker"):
            for on_date in (BEFORE, AFTER):
                assert _costed(route_id, on_date).status == "open"
        wartime_after_the_war = _round_trip(_costed("monobank_to_binance_p2p", AFTER))
        assert is_close(wartime_after_the_war.fraction, 2.0 / 15.0)
