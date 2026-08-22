"""FR-014: a route that will not carry this amount on this date says so, and says why.

FR-014: *a route unusable for a stated amount or date MUST be reported as such with the
binding constraint named, and MUST NOT be silently adjusted, rounded, or omitted from the
comparison without a recorded reason.*

**Three ways a route refuses, and one way it does not.** Below a leg's declared minimum, over
its declared maximum, or closed on the date -- each reported with the field that bound and the
gap it bound by. The way it does *not* refuse is a **monthly cap**: a cap does not make a
route unusable, it makes the route unable to carry the whole amount *at once*, and the answer
to that is FR-013's fallback rather than a refusal. Refusing would deploy nothing, which is
the opposite of SC-007's *"a plan exceeding a monthly cap deploys exactly the cap"*. The last
class here asserts that distinction, because collapsing the two would be the easiest possible
misreading of "caps MUST be enforced".

**Why "never silently adjusted" needs its own assertions.** Each of the three refusals has an
obvious, helpful-looking repair, and every one of them is wrong:

* *round up to the minimum* -- moves money the owner did not agree to move;
* *round down to the maximum* -- reports a cost for a movement that never happened;
* *drop the closed route from the comparison* -- makes an absence look like an absence of
  options rather than a route that is shut.

So the tests below check not only that a refusal happened but that the **amount was not
changed** and the **route was not dropped**: the exclusion appears in the ranking, with its
reason, beside the alternatives it was excluded from.

``RouteUnusable`` is a tagged-union member and not an exception (constitution, Engineering
Standards): a route that will not carry an amount is a *fact about the money*, and facts about
the money are typed values. A raise is for a programmer error -- an undeclared route id, a
negative amount, an amount in a currency the named stream never delivers.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results.ramp import NothingComparable, RampCost, Ranking, RouteUnusable
from terezy.core.routes import cost, ranking
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.path import FundingPath
from tests.invariants import route_graphs

AMOUNT = 10_000.0
"""What every case below asks the route to carry. One amount, so the constraint is the only
thing that varies."""

TEMPLATE = route_graphs.zero_cost_graph(with_exit=True)
"""The domestic two-leg shape with its exit declared, varied one declared field at a time.

Zero fees throughout, so a refusal is never confused with a cost: the route either carries the
amount for nothing or refuses it, and there is no third outcome to explain away.
"""


def _uah(amount: float) -> Money:
    """A hryvnia amount with no sources -- honest for a figure invented in this file."""
    return Money(amount, Currency.UAH, prov.EMPTY)


def _with_first_leg(**changes: object) -> Mapping[str, Route]:
    """The template's routes, with the named fields changed on the **first** leg.

    The first leg because it is the one the stream's money enters, so the constraint binds on
    the full amount and the arithmetic in each expectation is a single subtraction.
    """
    first, second = TEMPLATE.route.legs
    altered: Leg = dataclasses.replace(first, **changes)  # type: ignore[arg-type]
    return {
        **TEMPLATE.routes,
        TEMPLATE.route.id: dataclasses.replace(TEMPLATE.route, legs=(altered, second)),
    }


def _refused(
    routes: Mapping[str, Route],
    *,
    amount: float = AMOUNT,
    on_date: date = route_graphs.ON_DATE,
) -> RouteUnusable:
    outcome = cost.cost_one(
        TEMPLATE.path,
        _uah(amount),
        routes=routes,
        channels=TEMPLATE.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=on_date,
        as_of=route_graphs.AS_OF,
    )
    assert isinstance(outcome, RouteUnusable), outcome
    return outcome


def _rank(routes: Mapping[str, Route], *paths: FundingPath) -> Ranking | NothingComparable:
    return ranking.rank(
        list(paths),
        _uah(AMOUNT),
        routes=routes,
        channels=TEMPLATE.channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=route_graphs.ON_DATE,
        as_of=route_graphs.AS_OF,
    )


class TestBelowADeclaredMinimum:
    """The refusal whose helpful-looking repair moves money the owner never agreed to move."""

    def test_the_binding_constraint_is_named_as_the_declared_field(self) -> None:
        refused = _refused(_with_first_leg(minimum=_uah(25_000.0)))
        assert refused.binding_constraint == "leg.minimum"

    def test_the_shortfall_is_the_gap_and_not_a_restatement_of_the_minimum(self) -> None:
        # 25 000 required, 10 000 offered, 15 000 short. Carried on the record rather than left
        # to the caller to subtract, so the figure the owner sees comes from one arithmetic.
        refused = _refused(_with_first_leg(minimum=_uah(25_000.0)))
        assert refused.required is not None
        assert refused.actual is not None
        assert refused.shortfall is not None
        assert_money_close(refused.required, _uah(25_000.0))
        assert_money_close(refused.actual, _uah(10_000.0))
        assert_money_close(refused.shortfall, _uah(15_000.0))

    def test_the_amount_is_not_rounded_up_to_the_minimum(self) -> None:
        # The whole point. A route that "helpfully" carried 25 000 would have moved 15 000 the
        # owner never asked to move, and the cost reported would be a cost of a different
        # transaction.
        refused = _refused(_with_first_leg(minimum=_uah(25_000.0)))
        assert refused.actual is not None
        assert refused.actual.amount == AMOUNT

    def test_the_reason_names_both_numbers_in_words(self) -> None:
        refused = _refused(_with_first_leg(minimum=_uah(25_000.0)))
        assert "25000.0" in refused.reason
        assert "10000.0" in refused.reason

    def test_exactly_the_minimum_is_carried_rather_than_refused(self) -> None:
        # The boundary, in the direction that must *not* refuse: "carries no less than" is
        # inclusive, and an off-by-one here would refuse the one amount that exactly fits.
        outcome = cost.cost_one(
            TEMPLATE.path,
            _uah(25_000.0),
            routes=_with_first_leg(minimum=_uah(25_000.0)),
            channels=TEMPLATE.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(outcome, RampCost)
        assert_money_close(outcome.one_way.arrived, _uah(25_000.0))


class TestOverADeclaredMaximum:
    """The mirror image, whose repair reports a cost for a movement that never happened."""

    def test_the_binding_constraint_is_named_as_the_declared_field(self) -> None:
        refused = _refused(_with_first_leg(maximum=_uah(4_000.0)))
        assert refused.binding_constraint == "leg.maximum"

    def test_the_shortfall_is_the_excess_carried_as_a_negative_figure(self) -> None:
        # 4 000 allowed, 10 000 offered. ``shortfall`` is ``required - actual`` in every case,
        # one subtraction in one direction, so the figure does not depend on which constraint
        # bound: -6 000 here reads as an excess of 6 000.
        refused = _refused(_with_first_leg(maximum=_uah(4_000.0)))
        assert refused.shortfall is not None
        assert_money_close(refused.shortfall, _uah(-6_000.0))

    def test_the_amount_is_not_rounded_down_to_the_maximum(self) -> None:
        refused = _refused(_with_first_leg(maximum=_uah(4_000.0)))
        assert refused.actual is not None
        assert refused.actual.amount == AMOUNT

    def test_exactly_the_maximum_is_carried_rather_than_refused(self) -> None:
        outcome = cost.cost_one(
            TEMPLATE.path,
            _uah(4_000.0),
            routes=_with_first_leg(maximum=_uah(4_000.0)),
            channels=TEMPLATE.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(outcome, RampCost)


class TestClosedOnTheDate:
    """A route or a leg that is shut, and an absence that is visible rather than silent."""

    def test_a_closed_route_names_its_status_and_carries_no_amounts(self) -> None:
        # A closed route binds without any amount being involved, so ``required``, ``actual``
        # and ``shortfall`` are all ``None``: inventing a zero for them would put a number
        # where there is none, and a zero shortfall reads as "it very nearly worked".
        routes = {
            **TEMPLATE.routes,
            TEMPLATE.route.id: dataclasses.replace(TEMPLATE.route, status="closed"),
        }
        refused = _refused(routes)
        assert refused.binding_constraint == "route.status"
        assert refused.required is None
        assert refused.actual is None
        assert refused.shortfall is None
        assert "closed" in refused.reason

    def test_a_leg_not_yet_open_names_the_date_it_opens(self) -> None:
        refused = _refused(_with_first_leg(available_from=date(2027, 1, 1)))
        assert refused.binding_constraint == "leg.available_from"
        assert "2027-01-01" in refused.reason
        assert route_graphs.ON_DATE.isoformat() in refused.reason

    def test_a_leg_already_shut_names_the_date_it_shut(self) -> None:
        refused = _refused(_with_first_leg(available_until=date(2026, 1, 1)))
        assert refused.binding_constraint == "leg.available_until"
        assert "2026-01-01" in refused.reason

    def test_the_same_leg_carries_the_amount_on_a_date_inside_its_window(self) -> None:
        # The window is a *fact* about the corridor with a source -- "this closed in March
        # 2025" -- and it is evaluated against the date the money moves, which is data. No
        # clock is consulted, so the same leg answers differently for two dates and identically
        # for the same one forever.
        routes = _with_first_leg(available_from=date(2027, 1, 1))
        outcome = cost.cost_one(
            TEMPLATE.path,
            _uah(AMOUNT),
            routes=routes,
            channels=TEMPLATE.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=date(2027, 6, 1),
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(outcome, RampCost)


class TestARefusedRouteIsExcludedWithItsReasonAndNotDropped:
    """FR-014's second clause: never omitted from the comparison without a recorded reason."""

    def _usable_alternative(self) -> tuple[FundingPath, Mapping[str, Route]]:
        """A second route that does carry the amount, so the ranking has something to rank."""
        alternative_exit = dataclasses.replace(
            TEMPLATE.routes["inzhur_exit"], id="alternative_exit"
        )
        alternative = dataclasses.replace(
            TEMPLATE.route, id="alternative", partner_route=alternative_exit.id
        )
        return (
            dataclasses.replace(TEMPLATE.path, route_id=alternative.id),
            {alternative.id: alternative, alternative_exit.id: alternative_exit},
        )

    def test_the_refusal_appears_in_the_ranking_beside_the_route_that_worked(self) -> None:
        alternative_path, alternative_routes = self._usable_alternative()
        refused_routes = _with_first_leg(minimum=_uah(25_000.0))
        ranked = _rank({**refused_routes, **alternative_routes}, TEMPLATE.path, alternative_path)
        assert isinstance(ranked, Ranking)
        assert len(ranked.costed) == 1
        assert len(ranked.excluded) == 1
        assert ranked.excluded[0].binding_constraint == "leg.minimum"
        assert ranked.excluded[0].path == TEMPLATE.path

    def test_every_candidate_is_accounted_for_somewhere(self) -> None:
        # The totality claim: a route is costed, excluded with a reason, or reported as not
        # comparable -- never absent. An absence is what makes an infeasible plan look like a
        # plan with fewer options.
        alternative_path, alternative_routes = self._usable_alternative()
        refused_routes = _with_first_leg(maximum=_uah(4_000.0))
        ranked = _rank({**refused_routes, **alternative_routes}, TEMPLATE.path, alternative_path)
        assert isinstance(ranked, Ranking)
        accounted = (
            [entry.path for entry in ranked.costed]
            + [entry.path for entry in ranked.excluded]
            + [entry.path for entry in ranked.not_comparable]
        )
        assert sorted(entry.route_id for entry in accounted) == ["alternative", "inzhur_direct"]

    def test_when_every_candidate_refuses_the_answer_is_not_a_ranking(self) -> None:
        # There is no honest index into an empty tuple, so the type says so rather than a
        # sentinel standing in for it (research.md D13), and each refusal is still carried.
        ranked = _rank(_with_first_leg(minimum=_uah(25_000.0)), TEMPLATE.path)
        assert isinstance(ranked, NothingComparable)
        assert len(ranked.excluded) == 1
        assert ranked.excluded[0].binding_constraint == "leg.minimum"


class TestACapIsNotARefusal:
    """The distinction FR-012 and FR-013 draw together, asserted so it cannot be collapsed."""

    def test_an_amount_over_the_monthly_cap_is_still_costed(self) -> None:
        # 10 000 asked of a rail that allows 4 000 a month. The route is perfectly usable -- it
        # will carry 4 000 of it now -- so ``cost_one`` costs it and reports the ceiling, and
        # ``capacity.deploy`` is what decides how much goes and what falls back (FR-013).
        # Refusing here would deploy nothing at all.
        graph = route_graphs.capped_graph(cap=4_000.0)
        outcome = cost.cost_one(
            graph.path,
            _uah(AMOUNT),
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
        )
        assert isinstance(outcome, RampCost)
        assert outcome.ceiling is not None
        assert_money_close(outcome.ceiling, _uah(4_000.0))

    def test_a_constrained_route_is_ranked_and_flagged_rather_than_excluded(self) -> None:
        # ``constrained`` means usable but not freely -- §4.3 uses it for the IBKR route. Only
        # ``closed`` excludes; treating ``constrained`` as closed would delete a real option,
        # and treating it as open would hide that a declared limit binds in normal use.
        routes = {
            **TEMPLATE.routes,
            TEMPLATE.route.id: dataclasses.replace(TEMPLATE.route, status="constrained"),
        }
        ranked = _rank(routes, TEMPLATE.path)
        assert isinstance(ranked, Ranking)
        assert ranked.excluded == ()
        assert ranked.costed[0].status == "constrained"


class TestARefusalIsAValueAndAProgrammerErrorIsARaise:
    """The split the constitution draws, at the one boundary this feature adds."""

    def test_an_undeclared_route_id_raises_rather_than_refusing(self) -> None:
        # A route nobody declared is not a fact about the money; it is a caller holding an id
        # that does not exist. Returning a ``RouteUnusable`` for it would make a typo look like
        # a corridor that is closed.
        with pytest.raises(KeyError, match="unknown route"):
            cost.cost_one(
                dataclasses.replace(TEMPLATE.path, route_id="a_route_nobody_declared"),
                _uah(AMOUNT),
                routes=TEMPLATE.routes,
                channels=TEMPLATE.channels,
                streams=route_graphs.STREAMS,
                kinds=route_graphs.KINDS,
                on_date=route_graphs.ON_DATE,
                as_of=route_graphs.AS_OF,
            )

    def test_a_negative_amount_raises_rather_than_refusing(self) -> None:
        # A negative movement is not this route in reverse -- the way out is its own
        # declaration (FR-027) -- so it can only be the caller's arithmetic error, and costing
        # it would report a negative cost that reads as a gain.
        with pytest.raises(ValueError, match="negative movement"):
            cost.cost_one(
                TEMPLATE.path,
                _uah(-1_000.0),
                routes=TEMPLATE.routes,
                channels=TEMPLATE.channels,
                streams=route_graphs.STREAMS,
                kinds=route_graphs.KINDS,
                on_date=route_graphs.ON_DATE,
                as_of=route_graphs.AS_OF,
            )

    def test_a_refusal_is_not_a_cost_of_zero(self) -> None:
        # ``RouteUnusable`` is unrelated to ``RampCost`` and carries no cost figure at all: a
        # zero there would read as "free", which is the answer a reader would least question
        # and the one most likely to be wrong.
        # The ``isinstance`` a reader would reach for here is not written, because mypy
        # already proves it: ``RouteUnusable`` and ``RampCost`` have disjoint bases, so the
        # check is unreachable code. The field scan is what remains to assert -- that this
        # record carries no cost figure under any name.
        refused = _refused(_with_first_leg(minimum=_uah(25_000.0)))
        fields = {field.name for field in dataclasses.fields(refused)}
        assert not fields & {"sent", "arrived", "fraction", "components", "one_way"}
