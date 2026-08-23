"""SC-007: two legs in different segments naming one rail consume one shared headroom.

FR-016: *capacity pools MUST bind across a composed candidate exactly as they bind across
routes: every leg naming a pool consumes the one shared monthly headroom, **including two legs
in different segments of the same candidate**, and headroom already consumed this month by
anything else applies.*

**This is a claim about feature 002's design surviving contact with composition, not about new
code** (research.md D11). The accumulator is keyed by ``(capacity_pool, year, month)`` and never
by the route, precisely because a limit belongs to a **rail** -- a card, an account, a corridor
under a regulatory ceiling -- and a route is a path that *uses* rails. Two hops that both touch
the owner's card therefore share one limit for the same reason two different routes do, and
nothing about a chain needed teaching. That is why this lands as a hand-computed example rather
than as an assertion that no code was written: the useful check is the arithmetic, and the
useful record is that the arithmetic came out right without a pool rule for chains.

## The arithmetic

```
declared      card limit                             = 100 000 UAH per month
              both segments name the same rail and the same limit

already spent earlier this month, on anything        =  40 000 UAH
headroom      100 000 - 40 000                       =  60 000 UAH

the plan asks for                                       75 000 UAH
deployed      min(75 000, 60 000)                    =  60 000 UAH
held as cash  75 000 - 60 000                        =  15 000 UAH
```

**The wrong answer this example exists to rule out is 75 000** -- what a model that gave each
segment its own full 100 000 would deploy, and what a reader would have no way to tell from the
right one. The second wrong answer is a *ceiling* of 200 000: two caps summed rather than one
rail reported once.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import RampCost
from terezy.core.routes import capacity, cost
from terezy.core.routes.legs import Leg
from terezy.core.routes.path import ComposedPath
from tests import composed_registries as fixtures

pytestmark = pytest.mark.worked_example

CAP = fixtures.CARD_CAP
"""100 000 UAH, declared on **both** segments' legs, for one rail."""

ALREADY_SPENT = 40_000.0
"""Consumed earlier in the same month, by anything at all -- 002's accumulator does not care
what spent it, only which rail (FR-015)."""

HEADROOM = CAP - ALREADY_SPENT
"""60 000 UAH."""

REQUESTED = 75_000.0
HELD_AS_CASH = REQUESTED - HEADROOM
"""15 000 UAH -- the excess, recorded with its date and its reason rather than dropped."""

CHAIN = ComposedPath(
    destination_id=fixtures.FUND,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_wallet", "in_wallet_to_fund"),
)


def _uah(amount: float) -> Money:
    return Money(amount, Currency.UAH, prov.EMPTY)


def _legs() -> tuple[Leg, ...]:
    world = fixtures.pooled()
    return cost.legs_of(CHAIN, world.routes)


def _used() -> capacity.CapacityUsed:
    """The month's consumption so far, recorded against the rail rather than against a route."""
    return capacity.record(
        {}, pool=fixtures.CARD_POOL, amount=_uah(ALREADY_SPENT), on_date=fixtures.ON_DATE
    )


class TestOneRailAcrossTwoSegmentsIsOneLimit:
    def test_both_segments_really_declare_the_same_rail_and_the_same_cap(self) -> None:
        """The precondition, checked so the example cannot pass by the pools not matching.

        Two legs naming one pool **must** declare the same cap: two numbers for one real limit
        means at least one is wrong, and picking either silently would be a guess.
        """
        world = fixtures.pooled()
        caps = [
            (leg.capacity_pool, leg.monthly_cap.amount if leg.monthly_cap else None)
            for route in world.routes.values()
            for leg in route.legs
        ]
        assert caps == [(fixtures.CARD_POOL, CAP), (fixtures.CARD_POOL, CAP)]

    def test_the_chain_reports_the_rail_once_and_not_once_per_segment(self) -> None:
        """FR-016 in its structural form. Two entries here would invite a caller to subtract
        the card's limit twice, and the sum of two full limits is the wrong answer twice over."""
        rails = capacity.caps_over(_legs(), source_id="in_salary_to_wallet+in_wallet_to_fund")
        assert len(rails) == 1
        assert rails[0].pool == fixtures.CARD_POOL
        assert is_close(rails[0].cap.amount, CAP)

    def test_the_deployable_amount_is_the_hand_computed_joint_figure(self) -> None:
        """60 000, not 75 000 and not 200 000."""
        (rail,) = capacity.caps_over(_legs(), source_id="chain")
        deployment = capacity.deploy(
            _uah(REQUESTED),
            limit=rail,
            used=_used(),
            policy=capacity.HOLD_AS_CASH,
            on_date=fixtures.ON_DATE,
            redirect_to=None,
        )
        assert is_close(deployment.deployed.amount, HEADROOM)
        assert is_close(deployment.requested.amount, REQUESTED)
        assert not is_close(deployment.deployed.amount, REQUESTED)

    def test_the_excess_is_recorded_with_its_reason_rather_than_dropped(self) -> None:
        """FR-013: every occurrence reported, with its date, its amount and what bound."""
        (rail,) = capacity.caps_over(_legs(), source_id="chain")
        deployment = capacity.deploy(
            _uah(REQUESTED),
            limit=rail,
            used=_used(),
            policy=capacity.HOLD_AS_CASH,
            on_date=fixtures.ON_DATE,
            redirect_to=None,
        )
        (fallback,) = deployment.fallbacks
        assert is_close(fallback.amount.amount, HELD_AS_CASH)
        assert fallback.occurred_on == fixtures.ON_DATE
        assert fixtures.CARD_POOL in fallback.reason
        assert str(ALREADY_SPENT) in fallback.reason

    def test_headroom_spent_earlier_in_the_month_by_anything_else_applies(self) -> None:
        """FR-015 across composition: the accumulator is keyed by rail, not by what spent it."""
        assert is_close(
            capacity.headroom(
                _used(), pool=fixtures.CARD_POOL, cap=_uah(CAP), on_date=fixtures.ON_DATE
            ).amount,
            HEADROOM,
        )


class TestTheCostedChainReportsOneCeiling:
    def test_the_ceiling_is_the_single_rail_and_not_the_two_caps_summed(self) -> None:
        """``RampCost.ceiling`` is the tightest declared cap met along the chain.

        With one rail declared twice at the same figure, the tightest is that figure -- 100 000
        -- and never 200 000. The ceiling is a cap on what passes the binding leg, not the
        largest amount that may be sent; the deployable figure above is the second question and
        the accumulator's to answer.
        """
        world = fixtures.pooled()
        costed = cost.cost_one(
            CHAIN,
            _uah(10_000.0),
            routes=world.routes,
            channels=world.channels,
            streams=world.streams,
            kinds=world.kinds,
            on_date=fixtures.ON_DATE,
            as_of=fixtures.AS_OF,
        )
        assert isinstance(costed, RampCost), costed
        assert costed.ceiling is not None
        assert is_close(costed.ceiling.amount, CAP)
