"""SC-001: a chain nobody declared end to end, costed leg by leg, against hand arithmetic.

The registry declares ``salary_venue -> exchange`` and ``exchange -> broker`` and **no**
``salary_venue -> broker``. That is the owner's own case, from the spec's opening: UAH salary
into Binance is declared, Binance into IBKR is declared, and UAH salary into IBKR *via* Binance
does not exist unless somebody sits down and hand-writes the concatenation.

Every figure below is worked out by hand and checked in beside the assertion, from the declared
premium and the declared fees and nothing else. The point is not that the engine agrees with
itself; it is that the engine agrees with arithmetic a reader can redo on paper.

## The arithmetic, in full

Declared: reference **42** UAH per USD, buy premium **+3** (so the price is 45), and two
segments -- the first charging nothing but the spread, the second charging **1%** and a flat
**1 USD**.

```
segment 0  in_salary_to_exchange   one fx leg, UAH -> USD, no fees
    price        = 42 + 3                      = 45      UAH per USD
    arriving     = 10 000 / 45                 = 222.222222...  USD
    spread cost  = 10 000 * (1 - 42/45)
                 = 10 000 * 3/45               = 666.666666...  UAH

segment 1  in_exchange_to_broker   one transfer leg, USD -> USD, 1% + 1 USD
    percentage   = 222.222222... * 0.01        =   2.222222...  USD
    fixed        =                                 1.000000     USD
    arriving     = 222.222222 - 2.222222 - 1   = 219.000000     USD

    valued in the sending currency at the reference the conversion crossed (42):
    percentage   = 2.222222... * 42            =  93.333333...  UAH
    fixed        = 1 * 42                      =  42.000000     UAH

total cost       = 666.666666 + 93.333333 + 42 = 802.000000     UAH
one-way fraction = 802 / 10 000                =   0.0802
```

**The independent check**, from the other direction: 10 000 UAH is 238.095238 USD at the
reference, and 219.000000 USD arrived, so 19.095238 USD went missing -- which is 802.00 UAH at
42. Two readings of the same journey, agreeing, neither derived from the other.

## Why the fees are on the *second* segment

Deliberately, and it is the trap this example exists to catch. A cost charged after a conversion
has to be valued back into the sending currency to be added to one that was charged before it,
and the valuation factor is built from the channel that leg crossed. Put both fees on the first
segment and the whole example would pass with the factor never applied at all.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.ramp import CostComponent, RampCost
from terezy.core.routes import cost
from terezy.core.routes.path import ComposedExit, ComposedPath
from tests import composed_registries as fixtures

pytestmark = pytest.mark.worked_example

SENT = 10_000.0
"""What is moved, in hryvnia. The figure the arithmetic above is worked out for."""

PRICE = 45.0
"""``reference + buy premium`` -- what a dollar costs, and what the screen would say."""

ARRIVED_AT_EXCHANGE = SENT / PRICE
"""222.222222... USD. Written as the division rather than as a decimal so a reader can see
which two declared numbers it came from."""

SPREAD_UAH = SENT * (1.0 - fixtures.REFERENCE / PRICE)
"""666.666666... UAH -- ``10 000 * 3/45``. The **cost** of the conversion, not ``3/42``: the
two differ on the buy side, and reporting the second where the first belongs is the mistake
this project already made once."""

PERCENTAGE_USD = ARRIVED_AT_EXCHANGE * 0.01
FIXED_USD = 1.0
ARRIVED_AT_BROKER = ARRIVED_AT_EXCHANGE - PERCENTAGE_USD - FIXED_USD
"""219.000000 USD."""

PERCENTAGE_UAH = PERCENTAGE_USD * fixtures.REFERENCE
FIXED_UAH = FIXED_USD * fixtures.REFERENCE
"""93.333333 and 42.000000 UAH -- the second segment's charges valued where the money started,
at the reference the conversion crossed. A **valuation**, not a transaction: no money moves at
the reference without a declared side's spread being charged first."""

TOTAL_UAH = SPREAD_UAH + PERCENTAGE_UAH + FIXED_UAH
"""802.000000 UAH."""

FRACTION = TOTAL_UAH / SENT
"""0.0802."""

AT_THE_REFERENCE = SENT / fixtures.REFERENCE
"""238.095238 USD -- what 10 000 UAH is worth with no spread and no fee. The independent
check's starting point."""

CHAIN = ComposedPath(
    destination_id=fixtures.BROKER,
    stream_id=fixtures.SALARY.id,
    segments=("in_salary_to_exchange", "in_exchange_to_broker"),
)
EXIT_CHAIN = ComposedExit(segments=("out_broker_to_exchange", "out_exchange_to_home"))


def _costed() -> RampCost:
    world = fixtures.two_hop()
    outcome = cost.cost_one(
        CHAIN,
        Money(SENT, Currency.UAH, prov.EMPTY),
        exit_path=EXIT_CHAIN,
        routes=world.routes,
        channels=world.channels,
        streams=world.streams,
        kinds=world.kinds,
        on_date=fixtures.ON_DATE,
        as_of=fixtures.AS_OF,
        spendable=world.spendable,
    )
    assert isinstance(outcome, RampCost), outcome
    return outcome


class TestTheCorridorNobodyDeclaredEndToEnd:
    def test_the_registry_really_has_no_end_to_end_route(self) -> None:
        """Without this the example proves nothing: a declared ``salary -> broker`` route would
        make the composed candidate a duplicate rather than the only way through."""
        world = fixtures.two_hop()
        assert not [
            route
            for route in world.routes.values()
            if route.origin == fixtures.SALARY_VENUE and route.destination == fixtures.BROKER
        ]

    def test_the_arriving_amount_is_the_hand_computed_one(self) -> None:
        assert is_close(_costed().one_way.arrived.amount, ARRIVED_AT_BROKER)
        assert _costed().one_way.arrived.currency is Currency.USD

    def test_the_arriving_amount_agrees_with_the_check_from_the_other_side(self) -> None:
        """10 000 UAH is 238.095238 USD at the reference; 219.000000 arrived; the 19.095238 USD
        difference is 802.00 UAH at 42 -- the total cost, reached without touching the fold."""
        missing_usd = AT_THE_REFERENCE - _costed().one_way.arrived.amount
        assert is_close(missing_usd * fixtures.REFERENCE, TOTAL_UAH)

    def test_the_cost_fraction_is_the_hand_computed_one(self) -> None:
        assert is_close(_costed().one_way.fraction, FRACTION)

    def test_each_component_is_the_hand_computed_one(self) -> None:
        components = _costed().one_way.components
        assert is_close(components[CostComponent.CONVERSION_SPREAD].amount, SPREAD_UAH)
        assert is_close(components[CostComponent.PERCENTAGE_FEE].amount, PERCENTAGE_UAH)
        assert is_close(components[CostComponent.FIXED_FEE].amount, FIXED_UAH)

    def test_every_component_is_valued_in_the_sending_currency(self) -> None:
        """Otherwise they could not be added at all -- and ``money.add`` would say so."""
        assert all(
            charge.currency is Currency.UAH for charge in _costed().one_way.components.values()
        )


class TestTheAttributionNamesTheSegmentAndTheComponent:
    """SC-014: which segment dominates, which term dominates, and both traceable."""

    def test_each_segment_carries_the_charges_its_own_declaration_made(self) -> None:
        first, second = _costed().one_way.by_segment
        assert first.route_id == "in_salary_to_exchange"
        assert is_close(first.components[CostComponent.CONVERSION_SPREAD].amount, SPREAD_UAH)
        assert is_close(first.components[CostComponent.PERCENTAGE_FEE].amount, 0.0)
        assert second.route_id == "in_exchange_to_broker"
        assert is_close(second.components[CostComponent.CONVERSION_SPREAD].amount, 0.0)
        assert is_close(second.components[CostComponent.PERCENTAGE_FEE].amount, PERCENTAGE_UAH)
        assert is_close(second.components[CostComponent.FIXED_FEE].amount, FIXED_UAH)

    def test_the_dominating_segment_is_the_conversion_and_it_can_be_named(self) -> None:
        """666.67 of the 802 UAH is the first segment's spread -- 83% of the whole cost. The
        sentence this feature exists to let the tool write is *"most of the gap is the ramp"*,
        and on a chain the useful version of it names **which hop**."""
        dominating = max(
            _costed().one_way.by_segment,
            key=lambda entry: sum(charge.amount for charge in entry.components.values()),
        )
        assert dominating.route_id == "in_salary_to_exchange"
        assert dominating.position == 0

    def test_the_dominating_component_is_the_spread(self) -> None:
        components = _costed().one_way.components
        assert max(components, key=lambda key: components[key].amount) is (
            CostComponent.CONVERSION_SPREAD
        )

    def test_the_two_axes_sum_to_the_same_total(self) -> None:
        """Both mappings sum to 802.00 UAH: a leg cannot hide in either (research.md D7)."""
        costed = _costed()
        by_component = sum(charge.amount for charge in costed.one_way.components.values())
        by_segment = sum(
            charge.amount
            for entry in costed.one_way.by_segment
            for charge in entry.components.values()
        )
        assert is_close(by_component, TOTAL_UAH)
        assert is_close(by_segment, TOTAL_UAH)

    def test_every_attributed_figure_traces_to_a_declaration(self) -> None:
        """FR-018 and SC-014's second half. A figure that cannot name the file it rests on is
        not traceable, and every number in this registry is unverified -- so every figure
        derived from one carries the mark."""
        for entry in _costed().one_way.by_segment:
            for charge in entry.components.values():
                assert charge.provenance.sources, entry.route_id
                assert prov.is_unverified(charge.provenance), entry.route_id


class TestTheChainReportsWhatTheSegmentsDeclare:
    def test_latency_accumulates_across_the_chain(self) -> None:
        """One day for the conversion and two for the transfer, exactly as a declared route
        with the same concatenated legs would report (FR-004)."""
        assert _costed().latency_days == 1 + 2

    def test_the_conversion_is_reported_once_and_names_its_channel(self) -> None:
        assert _costed().one_way.channels_applied == (fixtures.CHANNEL_ID,)

    def test_the_rate_space_spread_is_reported_beside_the_cost_and_not_as_it(self) -> None:
        """``3/42 = 7.14%`` is §4.3.1's own figure; ``3/45 = 6.67%`` is what left the pocket.
        Both are present, under different names, because reporting the first where the second
        belongs understated the arriving amount the last time it happened."""
        costed = _costed()
        assert costed.one_way.spreads_over_reference == (3.0 / 42.0,)
        assert not is_close(costed.one_way.fraction, 3.0 / 42.0)
