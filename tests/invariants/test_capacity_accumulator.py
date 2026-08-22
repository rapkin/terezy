"""FR-012, FR-015: the monthly cap is state in a fold, and it belongs to a shared rail.

FR-012: *declared caps, minimums, latency and status MUST be enforced. Total deployed MUST
equal what the route allows, never what the plan requested.* FR-015: *a monthly ceiling MUST
account for capacity already consumed in the same month.*

**The accumulator keys on ``(capacity_pool, year, month)`` and never on the route**
(research.md D10). A limit belongs to a *rail* -- the owner's Monobank card, an account, a
corridor under a regulatory ceiling -- and a route is a path that *uses* rails. Two different
routes both moving money through one card consume **one** limit. Keying on the route was the
first design and it gave each route its own full monthly limit; Monobank's monthly limit is
one of the four figures ``SIMULATOR_SPEC.md`` §11 item 1 names as the reason this feature
exists, so a model that cannot express it fails at the feature's own purpose. The class of
test below named ``TestOneRailIsOneLimitHoweverManyRoutesUseIt`` is that property, asserted
with numbers rather than argued.

**There is no clock** (research.md D7). The month comes from an event's ``occurred_on``,
which is data; ``datetime.now`` is blocked in ``core`` by ``.importlinter``. Remaining
headroom is ``cap - consumed``, passed explicitly, and FR-015's "capacity already consumed in
the same month" then falls out of the fold rather than being a special case.

**Why property-based rather than by example.** The thing worth asserting is not that one cap
binds at one amount -- that is the worked example in
``tests/worked_examples/test_monthly_cap.py``. It is that *over any history*, the accumulator
agrees with an independent tally of the same events, and that a sequence of deployments each
checked against the headroom can never overrun the cap. Both are statements about every
stream, and the second is the one a hand-written case would confirm by accident.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.routes import capacity

pytestmark = pytest.mark.invariant

POOLS = ("monobank_card_uah_usd", "privat_transfer_uah", "nbu_annual_corridor")
"""Three invented rails. Every number in this module is a fixture and none is an observation."""

CAUSE = CausationRef(
    kind=CausationKind.ROUTE_TERM,
    id="synthetic_route",
    detail="SYNTHETIC FIXTURE -- an invented movement, not an observed transfer.",
)


@dataclass(frozen=True, slots=True)
class Movement:
    """One thing that pushed money through a rail: the three facts a cap is keyed on."""

    pool: str
    amount: float
    on_date: date


def _money(amount: float) -> Money:
    """A hryvnia amount with no sources. Honest for a figure invented in this file."""
    return Money(amount, Currency.UAH, prov.EMPTY)


def _event(sequence: int, movement: Movement) -> Event:
    """One movement as a ledger event, so the accumulator is exercised through the fold.

    A ``RAMP_MOVEMENT`` rather than a fee: what a rail's monthly limit counts is the money
    put *through* it, and the pool is named on the event because "which rail did this cross"
    is a fact about the movement and not something to infer from adjacency -- the same
    argument ``ledger.events`` makes for ``allocated_to``.
    """
    return Event(
        sequence=sequence,
        occurred_on=movement.on_date,
        kind=EventKind.RAMP_MOVEMENT,
        amount=_money(-movement.amount),
        owner_id="owner-001",
        caused_by=CAUSE,
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=movement.pool,
    )


def _stream(movements: Sequence[Movement]) -> tuple[Event, ...]:
    """The movements as a foldable stream: ascending dates, dense sequence numbers."""
    ordered = sorted(movements, key=lambda movement: movement.on_date)
    return tuple(_event(index, movement) for index, movement in enumerate(ordered))


def _tally(movements: Sequence[Movement]) -> Mapping[capacity.CapacityKey, float]:
    """The same total, summed here, from the same movements.

    Computed independently of the engine on purpose: an accumulator compared against a figure
    the accumulator produced proves that one loop ran. The same discipline as the ledger
    conservation suites, which recompute ``inflows - outflows`` rather than reading
    ``balance``.
    """
    totals: dict[capacity.CapacityKey, float] = {}
    for movement in movements:
        key = capacity.CapacityKey(
            pool=movement.pool, year=movement.on_date.year, month=movement.on_date.month
        )
        totals[key] = totals.get(key, 0.0) + movement.amount
    return totals


_AMOUNTS = st.floats(min_value=0.0, max_value=250_000.0, allow_nan=False, allow_infinity=False)
_DATES = st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31))
_MOVEMENTS = st.builds(Movement, pool=st.sampled_from(POOLS), amount=_AMOUNTS, on_date=_DATES)
_HISTORIES = st.lists(_MOVEMENTS, min_size=0, max_size=12)


class TestTheAccumulatorAgreesWithAnIndependentTally:
    """The fold is a sum, and it is the sum a reader would compute by hand."""

    @given(movements=_HISTORIES)
    def test_every_key_holds_exactly_what_its_month_pushed_through_its_pool(
        self, movements: list[Movement]
    ) -> None:
        folded = engine.fold(
            _stream(movements), base_currency=Currency.UAH, consumption_method="fifo"
        )
        expected = _tally(movements)
        assert set(folded.capacity) == set(expected)
        for key, total in expected.items():
            assert_money_close(folded.capacity[key], _money(total))

    @given(movements=_HISTORIES)
    def test_the_accumulator_never_loses_a_movement(self, movements: list[Movement]) -> None:
        # The weaker statement the one above implies, asserted separately because it is the
        # one that fails first when a key is computed from the wrong date field: the grand
        # total across every key is the grand total of the movements.
        folded = engine.fold(
            _stream(movements), base_currency=Currency.UAH, consumption_method="fifo"
        )
        assert_money_close(
            _money(sum(entry.amount for entry in folded.capacity.values())),
            _money(sum(movement.amount for movement in movements)),
        )

    @given(movements=_HISTORIES)
    def test_a_month_that_pushed_nothing_has_no_key_rather_than_a_zero(
        self, movements: list[Movement]
    ) -> None:
        # An absent key and a zero are different claims, and the difference matters here:
        # ``consumed`` returning ``None`` says "this rail carried nothing this month", which
        # is what makes the full cap the honest headroom. A zero conjured for every
        # (pool, month) pair the calendar allows would be a mapping of mostly fiction.
        folded = engine.fold(
            _stream(movements), base_currency=Currency.UAH, consumption_method="fifo"
        )
        touched = {
            (movement.pool, movement.on_date.year, movement.on_date.month) for movement in movements
        }
        for key in folded.capacity:
            assert (key.pool, key.year, key.month) in touched


class TestCapacityConsumedEarlierInTheMonthReducesTheHeadroom:
    """FR-015, which is the reason the accumulator exists at all."""

    @given(
        cap=st.floats(min_value=1.0, max_value=500_000.0, allow_nan=False),
        movements=_HISTORIES,
    )
    def test_headroom_is_the_cap_less_what_the_same_month_already_used(
        self, cap: float, movements: list[Movement]
    ) -> None:
        folded = engine.fold(
            _stream(movements), base_currency=Currency.UAH, consumption_method="fifo"
        )
        on_date = date(2026, 6, 15)
        pool = POOLS[0]
        already = _tally(movements).get(capacity.CapacityKey(pool=pool, year=2026, month=6), 0.0)
        assert_money_close(
            capacity.headroom(folded.capacity, pool=pool, cap=_money(cap), on_date=on_date),
            _money(cap - already),
        )

    @given(
        cap=st.floats(min_value=1_000.0, max_value=500_000.0, allow_nan=False),
        requests=st.lists(_AMOUNTS, min_size=1, max_size=8),
    )
    def test_a_month_of_deployments_each_checked_against_the_headroom_never_overruns(
        self, cap: float, requests: list[float]
    ) -> None:
        # The property FR-012 is actually about. Deploy repeatedly within one month, each
        # time consulting the accumulator, and the total deployed never exceeds the cap --
        # however many contributions arrive and whatever they ask for. This is the statement
        # an example test confirms by accident and a property test earns.
        on_date = date(2026, 3, 4)
        pool = POOLS[0]
        used: capacity.CapacityUsed = capacity.NOTHING_CONSUMED
        deployed = 0.0
        for requested in requests:
            outcome = capacity.deploy(
                _money(requested),
                limit=capacity.PoolCapacity(pool=pool, cap=_money(cap)),
                used=used,
                policy="hold_as_cash",
                on_date=on_date,
                redirect_to=None,
            )
            deployed += outcome.deployed.amount
            used = capacity.record(used, pool=pool, amount=outcome.deployed, on_date=on_date)
        # ``<=`` or equal within the **project** tolerance, imported rather than invented: the
        # total is a sum of up to eight float subtractions, so an exact ``<=`` would fail on
        # last-bit drift and any locally chosen bound would be a second tolerance policy.
        assert deployed <= cap or is_close(deployed, cap), (
            "a sequence of deployments each checked against the remaining headroom overran "
            f"the cap: {deployed!r} deployed against a cap of {cap!r} (FR-012, FR-015)"
        )

    def test_the_next_month_starts_from_the_full_cap_again(self) -> None:
        # A calendar month, not a rolling window: the cap is declared per calendar month, so
        # the first of the next month is a new key and the full cap is available. Asserted
        # rather than assumed because "monthly" admits a rolling reading, and a rolling one
        # would need a window nothing in the declaration states.
        pool = POOLS[0]
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool=pool,
            amount=_money(100_000.0),
            on_date=date(2026, 3, 31),
        )
        assert_money_close(
            capacity.headroom(used, pool=pool, cap=_money(100_000.0), on_date=date(2026, 3, 31)),
            _money(0.0),
        )
        assert_money_close(
            capacity.headroom(used, pool=pool, cap=_money(100_000.0), on_date=date(2026, 4, 1)),
            _money(100_000.0),
        )

    def test_the_same_month_of_a_different_year_is_a_different_key(self) -> None:
        pool = POOLS[0]
        used = capacity.record(
            capacity.NOTHING_CONSUMED, pool=pool, amount=_money(60_000.0), on_date=date(2026, 3, 10)
        )
        assert_money_close(
            capacity.headroom(used, pool=pool, cap=_money(100_000.0), on_date=date(2027, 3, 10)),
            _money(100_000.0),
        )

    @given(on_date=_DATES)
    def test_every_day_of_a_month_maps_to_that_month(self, on_date: date) -> None:
        # The key is derived from the date's year and month and from nothing else, so any two
        # days of one month share a key. Stated over generated dates because a key built from
        # an ISO week number or a day-of-year would pass a single hand-picked example.
        first = on_date.replace(day=1)
        last = on_date.replace(day=calendar.monthrange(on_date.year, on_date.month)[1])
        assert capacity.key_for(POOLS[0], first) == capacity.key_for(POOLS[0], last)
        assert capacity.key_for(POOLS[0], first) == capacity.key_for(POOLS[0], on_date)


class TestOneRailIsOneLimitHoweverManyRoutesUseIt:
    """**research.md D10.** The property the first design got wrong, in numbers."""

    def test_two_routes_through_one_card_consume_one_limit(self) -> None:
        # Two movements on two different routes, both naming the owner's Monobank card. The
        # card's monthly limit is 100 000 UAH. The first route puts 70 000 through it; the
        # second may then put 30 000 and no more.
        #
        # Under the rejected design -- keyed by ``(route_id, year, month)`` -- each route
        # would have carried its own 100 000, so the card would have carried 140 000 against
        # a 100 000 limit and the tool would have reported a plan that cannot execute.
        card = "monobank_card_uah_usd"
        cap = _money(100_000.0)
        on_date = date(2026, 5, 12)

        used = capacity.record(
            capacity.NOTHING_CONSUMED, pool=card, amount=_money(70_000.0), on_date=on_date
        )
        assert_money_close(
            capacity.headroom(used, pool=card, cap=cap, on_date=on_date), _money(30_000.0)
        )

        second_route = capacity.deploy(
            _money(50_000.0),
            limit=capacity.PoolCapacity(pool=card, cap=cap),
            used=used,
            policy="hold_as_cash",
            on_date=on_date,
            redirect_to=None,
        )
        assert_money_close(second_route.deployed, _money(30_000.0))
        assert len(second_route.fallbacks) == 1
        assert_money_close(second_route.fallbacks[0].amount, _money(20_000.0))

    def test_two_pools_are_two_independent_limits(self) -> None:
        # The other half of the same claim, and the one that fails if the pool were dropped
        # from the key: exhausting the card must not touch the bank transfer's limit.
        on_date = date(2026, 5, 12)
        used = capacity.record(
            capacity.NOTHING_CONSUMED,
            pool="monobank_card_uah_usd",
            amount=_money(100_000.0),
            on_date=on_date,
        )
        assert_money_close(
            capacity.headroom(
                used, pool="privat_transfer_uah", cap=_money(100_000.0), on_date=on_date
            ),
            _money(100_000.0),
        )

    def test_the_key_carries_no_route_at_all(self) -> None:
        # Structural, and the reason it is worth asserting: a ``route_id`` field on the key
        # would be the whole defect back, and it would read as a helpful extra dimension.
        fields = set(capacity.CapacityKey.__dataclass_fields__)
        assert fields == {"pool", "year", "month"}
        assert "route_id" not in fields
        assert "route" not in fields
