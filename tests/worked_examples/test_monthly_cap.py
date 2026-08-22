"""**G3**, FR-013, SC-007: a contribution over the cap deploys the cap, and says so.

Required test **G3**: *a plan exceeding a monthly cap queues the excess per the fallback
policy and reports each occurrence; total deployed equals the cap, never the plan.*
SC-007 turns it into a measurement: *a plan exceeding a monthly cap deploys exactly the cap,
and every fallback occurrence appears in the output with date, amount and reason. Count of
occurrences reported is never zero when occurrences happened.*

**"Queue" is *hold as cash*.** §4.3.4's own wording is "queue as UAH cash", and that is what
G3's "queues" means. It does **not** mean carrying the excess into next month's capacity:
nothing in the specification asks for that, and no policy in the closed set of four expresses
it. The next-month assertion at the foot of this module is the positive statement of that
reading -- September starts from the *full* cap, not from the cap plus August's leftover.

## The arithmetic, worked by hand

Every figure below is an **invented fixture**. ``SIMULATOR_SPEC.md`` §11 item 1 records that
none of the real route numbers -- including Monobank's monthly limit -- has been observed, so
a test asserting a real one would be asserting a number nobody has checked.

The rail is the owner's Monobank card, which declares a monthly limit of **100 000 UAH**. Two
routes run over it. Nothing has moved yet in August 2026.

```
declared cap on the card                          100 000
consumed in August 2026 so far                          0
                                                 --------
headroom                                          100 000

contribution planned on 2026-08-21                150 000
deployed  = min(plan, headroom)                   100 000    <- the cap, never the plan
fallback  = plan - deployed                        50 000    <- hold as cash, reported

the route charges nothing, so what arrives is     100 000
consumed in August 2026 after the movement        100 000
headroom now                                            0

a second contribution, on the SECOND route         80 000
headroom (the same card, the same month)                0
deployed                                                0    <- one rail, one limit
fallback                                           80 000    <- hold as cash, reported

occurrences reported                                    2
total deployed across both                        100 000 == the cap
```

**The second contribution is the whole point of research.md D10.** It runs over a *different
route* and the card has nothing left, because the limit belongs to the card. Under the
rejected design -- an accumulator keyed by ``(route_id, year, month)`` -- the second route
would have found its own untouched 100 000, the tool would have reported 180 000 deployed
through a card that allows 100 000, and the plan it recommended could not have executed.
Monobank's monthly limit is one of the four figures §11 item 1 names as the reason this
feature exists.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date

import pytest

from terezy.core.ledger import engine
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results.ramp import RampCost
from terezy.core.routes import capacity, cost, execute
from terezy.core.routes.legs import Route
from terezy.core.routes.path import FundingPath
from tests.invariants import route_graphs

pytestmark = pytest.mark.worked_example

CAP = 100_000.0
"""The card's declared monthly limit. **SYNTHETIC FIXTURE** -- §11 item 1: unobserved."""

PLAN = 150_000.0
"""What the owner planned to move in August. Invented, and deliberately over the cap."""

SECOND_PLAN = 80_000.0
"""A second contribution the same month, over the *other* route on the same card."""

AUGUST = date(2026, 8, 21)
SEPTEMBER = date(2026, 9, 1)
OWNER = route_graphs.OWNER_ID


def _uah(amount: float) -> Money:
    """A hryvnia amount with no sources -- honest for a figure invented in this file."""
    return Money(amount, Currency.UAH, prov.EMPTY)


def _two_routes_over_one_card() -> tuple[Mapping[str, Route], FundingPath, FundingPath]:
    """Two declared routes whose legs name the **same** ``capacity_pool``.

    Built from one fixture and renamed rather than written twice, so that the only difference
    between them is the route id: if the accumulator were keyed on the route, nothing else
    about these two declarations could explain a different answer.
    """
    first = route_graphs.capped_graph(cap=CAP, route_id="monobank_to_inzhur")
    second = route_graphs.capped_graph(cap=CAP, route_id="monobank_to_inzhur_premium")
    routes = {**first.routes, **second.routes}
    return routes, first.path, second.path


def _declared_limit(route: Route) -> capacity.PoolCapacity:
    """The card's limit, read off the declaration rather than restated as a literal.

    Both legs of the fixture declare the cap and both name the card, so ``caps_of`` reports
    the rail **once** -- which is the assertion, not an incidental convenience: a route that
    touched the card twice must not be read as having twice the allowance.
    """
    limits = capacity.caps_of(route)
    assert len(limits) == 1, limits
    return limits[0]


def _cost(path: FundingPath, routes: Mapping[str, Route], amount: Money) -> RampCost:
    costed = cost.cost_one(
        path,
        amount,
        routes=routes,
        channels=route_graphs.capped_graph().channels,
        streams=route_graphs.STREAMS,
        kinds=route_graphs.KINDS,
        on_date=AUGUST,
        as_of=route_graphs.AS_OF,
    )
    assert isinstance(costed, RampCost), costed
    return costed


class TestTheDeployedAmountIsTheCapAndNeverThePlan:
    """FR-012, SC-007, and the first line of the table above."""

    def test_the_declared_cap_is_read_off_the_declaration_once_per_rail(self) -> None:
        routes, first_path, _ = _two_routes_over_one_card()
        limit = _declared_limit(routes[first_path.route_id])
        assert limit.pool == route_graphs.CARD_POOL
        assert_money_close(limit.cap, _uah(CAP))

    def test_a_plan_of_150_000_against_a_cap_of_100_000_deploys_100_000(self) -> None:
        # 150 000 planned, 100 000 allowed, 50 000 displaced.
        #   deployed = 100 000    (the cap)
        #   fallback =  50 000    (150 000 - 100 000)
        routes, first_path, _ = _two_routes_over_one_card()
        limit = _declared_limit(routes[first_path.route_id])

        outcome = capacity.deploy(
            _uah(PLAN),
            limit=limit,
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        assert_money_close(outcome.requested, _uah(150_000.0))
        assert_money_close(outcome.deployed, _uah(100_000.0))
        assert len(outcome.fallbacks) == 1
        assert_money_close(outcome.fallbacks[0].amount, _uah(50_000.0))

    def test_the_plan_itself_is_still_reported_beside_what_was_deployed(self) -> None:
        # FR-012 is written as the gap between the two -- "total deployed MUST equal what the
        # route allows, never what the plan requested" -- so both figures are on the record. A
        # result carrying only the deployed amount would satisfy the requirement while making
        # it impossible to check.
        routes, first_path, _ = _two_routes_over_one_card()
        outcome = capacity.deploy(
            _uah(PLAN),
            limit=_declared_limit(routes[first_path.route_id]),
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        assert outcome.requested.amount == PLAN
        assert outcome.deployed.amount == CAP
        assert outcome.requested.amount - outcome.deployed.amount == 50_000.0

    def test_deploying_exactly_the_cap_displaces_nothing(self) -> None:
        # The boundary. 100 000 against 100 000 fits, and a fallback reported here would be a
        # fallback for money that was deployed -- SC-007's "never zero when occurrences
        # happened" has a mirror image, and this is it.
        routes, first_path, _ = _two_routes_over_one_card()
        outcome = capacity.deploy(
            _uah(CAP),
            limit=_declared_limit(routes[first_path.route_id]),
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        assert_money_close(outcome.deployed, _uah(100_000.0))
        assert outcome.fallbacks == ()


class TestTheWholeAugustSequenceOverOneCard:
    """The table, executed: deploy, record, deploy again over the second route."""

    def _august(self) -> tuple[capacity.Deployment, capacity.Deployment, capacity.CapacityUsed]:
        routes, first_path, second_path = _two_routes_over_one_card()
        limit = _declared_limit(routes[first_path.route_id])

        first = capacity.deploy(
            _uah(PLAN),
            limit=limit,
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        # The deployment is executed, and the ledger is what records the consumption: the
        # accumulator is folded from the events, not written beside them.
        costed = _cost(first_path, routes, first.deployed)
        folded = engine.fold(
            execute.execute(
                costed,
                owner_id=OWNER,
                sequence_from=0,
                on_date=AUGUST,
                capacity_pool=limit.pool,
            ),
            base_currency=Currency.UAH,
            consumption_method="fifo",
        )

        second = capacity.deploy(
            _uah(SECOND_PLAN),
            limit=_declared_limit(routes[second_path.route_id]),
            used=folded.capacity,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        return first, second, folded.capacity

    def test_the_route_charges_nothing_so_exactly_the_cap_arrives(self) -> None:
        # The domestic route declares zero fees on every leg, which is why this example can be
        # about the cap and nothing else: 100 000 deployed is 100 000 arrived, exactly.
        routes, first_path, _ = _two_routes_over_one_card()
        costed = _cost(first_path, routes, _uah(CAP))
        assert_money_close(costed.one_way.sent, _uah(100_000.0))
        assert_money_close(costed.one_way.arrived, _uah(100_000.0))
        assert costed.one_way.fraction == 0.0

    def test_the_declared_cap_is_reported_as_the_route_ceiling(self) -> None:
        routes, first_path, _ = _two_routes_over_one_card()
        costed = _cost(first_path, routes, _uah(CAP))
        assert costed.ceiling is not None
        assert_money_close(costed.ceiling, _uah(100_000.0))

    def test_the_fold_records_exactly_the_cap_against_the_card_for_august(self) -> None:
        _, _, used = self._august()
        key = capacity.key_for(route_graphs.CARD_POOL, AUGUST)
        assert set(used) == {key}
        assert_money_close(used[key], _uah(100_000.0))

    def test_the_second_route_over_the_same_card_finds_no_headroom_left(self) -> None:
        # **research.md D10 in one assertion.** A different route, the same rail, the same
        # month: nothing left. Keyed by route this would have been 80 000 deployed against a
        # card that had already given all it had.
        _, second, used = self._august()
        assert_money_close(
            capacity.headroom(used, pool=route_graphs.CARD_POOL, cap=_uah(CAP), on_date=AUGUST),
            _uah(0.0),
        )
        assert_money_close(second.deployed, _uah(0.0))
        assert_money_close(second.fallbacks[0].amount, _uah(80_000.0))

    def test_total_deployed_over_the_month_equals_the_cap(self) -> None:
        first, second, _ = self._august()
        assert_money_close(_uah(first.deployed.amount + second.deployed.amount), _uah(100_000.0))

    def test_the_ledger_lines_are_the_movement_and_no_fee_at_all(self) -> None:
        # FR-005 wants every fee to be an explicit line. This route charges none, so there is
        # none -- and the movement is still recorded, which is what makes the consumption
        # traceable to an event rather than asserted beside one.
        routes, first_path, _ = _two_routes_over_one_card()
        costed = _cost(first_path, routes, _uah(CAP))
        events = execute.execute(
            costed,
            owner_id=OWNER,
            sequence_from=0,
            on_date=AUGUST,
            capacity_pool=route_graphs.CARD_POOL,
        )
        assert [event.kind for event in events] == [
            EventKind.RAMP_MOVEMENT,
            EventKind.RAMP_MOVEMENT,
        ]
        assert_money_close(events[0].amount, _uah(-100_000.0))
        assert_money_close(events[1].amount, _uah(100_000.0))


class TestEveryOccurrenceAppearsWithItsDateAmountAndReason:
    """FR-013 and SC-007. A silently executed infeasible plan is a top-severity defect."""

    def test_each_occurrence_carries_all_three_facts(self) -> None:
        routes, first_path, _ = _two_routes_over_one_card()
        outcome = capacity.deploy(
            _uah(PLAN),
            limit=_declared_limit(routes[first_path.route_id]),
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        occurrence = outcome.fallbacks[0]
        assert occurrence.occurred_on == AUGUST
        assert_money_close(occurrence.amount, _uah(50_000.0))
        assert occurrence.policy == capacity.HOLD_AS_CASH
        assert "100000.0" in occurrence.reason
        assert "150000.0" in occurrence.reason
        assert "50000.0" in occurrence.reason
        assert route_graphs.CARD_POOL in occurrence.reason

    def test_the_count_of_occurrences_is_never_zero_when_occurrences_happened(self) -> None:
        # SC-007's own wording, and the clause a summary field would have quietly broken: two
        # contributions were displaced in August, and two records exist.
        routes, first_path, second_path = _two_routes_over_one_card()
        limit = _declared_limit(routes[first_path.route_id])
        used: capacity.CapacityUsed = capacity.NOTHING_CONSUMED
        occurrences: list[capacity.FallbackApplied] = []
        for path, plan in ((first_path, PLAN), (second_path, SECOND_PLAN)):
            outcome = capacity.deploy(
                _uah(plan),
                limit=limit,
                used=used,
                policy=capacity.HOLD_AS_CASH,
                on_date=AUGUST,
                redirect_to=None,
            )
            occurrences.extend(outcome.fallbacks)
            costed = _cost(path, routes, outcome.deployed)
            used = engine.fold(
                execute.execute(
                    costed,
                    owner_id=OWNER,
                    sequence_from=0,
                    on_date=AUGUST,
                    capacity_pool=limit.pool,
                ),
                base_currency=Currency.UAH,
                consumption_method="fifo",
            ).capacity
        assert len(occurrences) == 2
        assert [occurrence.amount.amount for occurrence in occurrences] == [50_000.0, 80_000.0]

    def test_redirect_names_where_the_excess_went(self) -> None:
        # FR-013 says redirect to a **named** destination, so the name is a field rather than
        # prose: a caller grouping occurrences by where the money went should not have to
        # parse a sentence.
        routes, first_path, _ = _two_routes_over_one_card()
        outcome = capacity.deploy(
            _uah(PLAN),
            limit=_declared_limit(routes[first_path.route_id]),
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.REDIRECT,
            on_date=AUGUST,
            redirect_to="inzhur_uah_fund",
        )
        assert outcome.fallbacks[0].policy == capacity.REDIRECT
        assert outcome.fallbacks[0].redirect_to == "inzhur_uah_fund"

    def test_a_redirect_with_no_destination_is_refused(self) -> None:
        routes, first_path, _ = _two_routes_over_one_card()
        with pytest.raises(ValueError, match="requires the destination"):
            capacity.deploy(
                _uah(PLAN),
                limit=_declared_limit(routes[first_path.route_id]),
                used=capacity.NOTHING_CONSUMED,
                policy=capacity.REDIRECT,
                on_date=AUGUST,
                redirect_to=None,
            )

    def test_a_destination_named_under_a_policy_that_sends_nowhere_is_refused(self) -> None:
        # The mirror of the case above. ``hold_as_cash`` keeps the excess where it is, so a
        # destination beside it describes a movement that does not happen -- and accepting the
        # field while ignoring it would put that movement in the output.
        routes, first_path, _ = _two_routes_over_one_card()
        with pytest.raises(ValueError, match="only 'redirect' sends the excess anywhere"):
            capacity.deploy(
                _uah(PLAN),
                limit=_declared_limit(routes[first_path.route_id]),
                used=capacity.NOTHING_CONSUMED,
                policy=capacity.HOLD_AS_CASH,
                on_date=AUGUST,
                redirect_to="inzhur_uah_fund",
            )

    def test_skip_still_reports_the_occurrence(self) -> None:
        # Skipping is a decision about the excess, not permission to forget it. All three
        # implemented policies deploy the same amount -- what the rail allows -- and differ in
        # what the record says became of the rest.
        routes, first_path, _ = _two_routes_over_one_card()
        outcome = capacity.deploy(
            _uah(PLAN),
            limit=_declared_limit(routes[first_path.route_id]),
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.SKIP,
            on_date=AUGUST,
            redirect_to=None,
        )
        assert_money_close(outcome.deployed, _uah(100_000.0))
        assert outcome.fallbacks[0].policy == capacity.SKIP
        assert_money_close(outcome.fallbacks[0].amount, _uah(50_000.0))


class TestThreeOfTheFourPoliciesAndTheFourthByName:
    """FR-013's ⚙ note: *place on deposit* fails, saying which feature will bring it."""

    def test_the_implemented_set_is_exactly_three(self) -> None:
        assert set(capacity.POLICIES) == {"hold_as_cash", "redirect", "skip"}

    def test_place_on_deposit_fails_and_says_what_it_needs(self) -> None:
        # Treating it as "hold as cash" would be a substituted default for a policy the owner
        # explicitly chose, which is the top severity class. Failing by name is the honest
        # answer, and naming *what is missing* is what turns the failure into a wait rather
        # than a hunt.
        with pytest.raises(ValueError, match="deposit instrument"):
            capacity.policy_for("place_on_deposit")

    def test_an_unrecognised_policy_fails_differently_and_lists_the_known_ones(self) -> None:
        # A typo and a real-but-unbuilt policy are different facts, and the owner acts
        # differently on each. A message that could not tell them apart would send him looking
        # for the first when it was the second.
        with pytest.raises(KeyError, match="unknown fallback policy"):
            capacity.policy_for("hold_as_csah")


class TestQueueDoesNotMeanCarriedIntoNextMonth:
    """The reading G3's wording most invites, stated as an assertion so it cannot drift."""

    def test_september_starts_from_the_full_cap_not_the_cap_plus_augusts_leftover(
        self,
    ) -> None:
        # A carried-over allowance would need a policy the closed set does not contain, and
        # nothing in the specification asks for one. September's headroom is 100 000 -- not
        # 150 000, and not 130 000.
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool=route_graphs.CARD_POOL,
            amount=_uah(CAP),
            on_date=AUGUST,
        )
        assert_money_close(
            capacity.headroom(used, pool=route_graphs.CARD_POOL, cap=_uah(CAP), on_date=SEPTEMBER),
            _uah(100_000.0),
        )
        assert_money_close(
            capacity.headroom(used, pool=route_graphs.CARD_POOL, cap=_uah(CAP), on_date=AUGUST),
            _uah(0.0),
        )


class TestALimitWithNoRailIsRefusedRatherThanGivenAKeyNobodyDeclared:
    """research.md D10, from the failing side."""

    def test_a_cap_declared_without_a_capacity_pool_is_refused(self) -> None:
        # Without a rail there is no key to accumulate under, so capacity already consumed in
        # the same month could never reduce this cap -- FR-015 would silently not apply to it.
        # Inferring a key from the route would be exactly the model D10 corrected.
        graph = route_graphs.capped_graph(cap=CAP)
        stripped = dataclasses.replace(
            graph.route,
            legs=tuple(dataclasses.replace(leg, capacity_pool=None) for leg in graph.route.legs),
        )
        with pytest.raises(ValueError, match="capacity_pool"):
            capacity.caps_of(stripped)

    def test_two_legs_naming_one_rail_must_declare_the_same_cap(self) -> None:
        # Two numbers for one real limit means at least one is wrong, and choosing either
        # silently would be a guess.
        graph = route_graphs.capped_graph(cap=CAP)
        first, second = graph.route.legs
        disagreeing = dataclasses.replace(
            graph.route,
            legs=(first, dataclasses.replace(second, monthly_cap=_uah(CAP / 2.0))),
        )
        with pytest.raises(ValueError, match="disagree about the monthly cap"):
            capacity.caps_of(disagreeing)

    def test_a_route_declaring_no_cap_at_all_reports_no_rail(self) -> None:
        # And ``deploy`` with no limit deploys the whole request: an undeclared cap is the
        # least constrained a route can be, and inventing one would refuse money the
        # declaration does not refuse.
        graph = route_graphs.capped_graph(cap=None)
        assert capacity.caps_of(graph.route) == ()
        outcome = capacity.deploy(
            _uah(PLAN),
            limit=None,
            used=capacity.NOTHING_CONSUMED,
            policy=capacity.HOLD_AS_CASH,
            on_date=AUGUST,
            redirect_to=None,
        )
        assert_money_close(outcome.deployed, _uah(150_000.0))
        assert outcome.fallbacks == ()
