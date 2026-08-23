"""Hypothesis strategies for valid route graphs, on the ``event_streams`` precedent.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run. It exists for the same reason ``tests/invariants/event_streams.py`` does: the
properties worth asserting about costing are properties over *many* routes, and a strategy
that produces structurally valid routes is a prerequisite for stating them.

**Every number here is invented**, and every ``verified_on`` is empty, so every figure
derived from these graphs carries the unverified mark. That is the honest state of route
data in this project (spec.md, Assumptions: none of the §11 item 1 numbers has been
observed), and it means the propagation tests have something real to propagate.

**What "valid" means here**, because the strategy has to produce it and the resolver would
otherwise reject it (research.md D6): legs chain by currency, the first leg starts in the
route's origin currency, an ``fx`` leg is the only one that changes currency, a fixed fee is
denominated in the leg it is charged on, and every ``fx`` leg names the one channel declared
for its pair. Core may assume a chained route; a strategy that produced broken ones would be
testing the wrong thing.

**One reference rate per pair, deliberately.** All ``fx`` legs share a single declared
channel, so every conversion in a generated graph is measured against the same reference.
That is not a simplification of convenience: a reference rate is a mid or official quote for
a pair on a date, and two channels quoting the *same pair* against *different references*
disagree about what the pair is worth. Such a disagreement is a revaluation, not a cost, and
it has no component to live in -- see the note in ``terezy.core.routes.cost``. Channels
differ in their markups, which is what the two-sided quote is for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from hypothesis import strategies as st

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteStatus
from terezy.core.routes.path import FundingPath
from terezy.core.routes.venues import Venue
from terezy.core.streams.streams import IncomeStream, Indexation

ON_DATE = date(2026, 8, 21)
"""When the money moves, in every generated case. Data, never a clock."""

AS_OF = date(2026, 8, 21)
"""When the question is asked. Equal to :data:`ON_DATE` here, and a *separate* argument
everywhere, because a projection into the future must not report its inputs as stale."""

RETRIEVED_ON = date(2026, 8, 1)
"""20 days before the as-of date, so the two kinds below disagree about staleness."""

FEE_SOURCE = SourceRef(
    id="synthetic:route-fees",
    citation="SYNTHETIC FIXTURE -- invented fee schedule. Not an observed tariff.",
    retrieved_on=RETRIEVED_ON,
    verified_on=None,
)
RATE_SOURCE = SourceRef(
    id="synthetic:channel-rate",
    citation="SYNTHETIC FIXTURE -- invented reference and premium. Not an observed quote.",
    retrieved_on=RETRIEVED_ON,
    verified_on=None,
)
FEE_SOURCES: Provenance = prov.of([FEE_SOURCE])
RATE_SOURCES: Provenance = prov.of([RATE_SOURCE])

P2P_PREMIUM = ObservationKind(
    id="p2p_premium",
    staleness_days=7,
    note="A peer-to-peer premium moves with demand and can shift within a week.",
)
BANK_FEE_SCHEDULE = ObservationKind(
    id="bank_fee_schedule",
    staleness_days=365,
    note="A published tariff changes on the bank's own schedule, rarely mid-year.",
)
KINDS: Mapping[str, ObservationKind] = {
    P2P_PREMIUM.id: P2P_PREMIUM,
    BANK_FEE_SCHEDULE.id: BANK_FEE_SCHEDULE,
}
"""Two kinds with very different thresholds, so a generated graph exercises both verdicts:
at 20 days old the premium is stale and the fee schedule is not."""

CHANNEL_ID = "p2p"
PAIR = (Currency.UAH, Currency.USD)
"""``(price currency, unit currency)``: the reference is UAH per USD."""

OWNER_ID = "owner-001"
"""The one owner. Carried from the first commit while there is exactly one (Principle VII)."""

ORIGIN_VENUE = "venue_0"
"""Where every fixture route starts, and therefore where both streams below arrive.

**Both streams arriving at the same venue is deliberate, not a shortcut.** It is what makes
the two-stream comparison a controlled experiment: same origin venue, same destination
venue, same value deployed, and the *only* difference between the two funding paths is the
currency the money arrived in -- which is exactly the variable §4.3.1's finding is about. It
also makes the sharper point: a per-destination cost is wrong even when the venues on both
sides are identical, because the term that differs is the stream. A multi-currency account
holding both hryvnia and dollars is the ordinary case in any event -- it is what Monobank is.
"""

SALARY_UAH = IncomeStream(
    id="salary_uah",
    owner_id=OWNER_ID,
    amount=Money(0.0, Currency.UAH, prov.EMPTY),
    cadence="monthly",
    arrives_at=ORIGIN_VENUE,
    indexation=Indexation(policy="cpi", rate=None),
    income_tax_rate=None,
)
"""The hryvnia salary. The stream that has to cross the ramp to reach a dollar asset.

``amount`` is ``0.0`` and ``income_tax_rate`` is ``None`` because both are honestly unknown:
``SIMULATOR_SPEC.md`` §11 item 3 records that the owner's monthly figures have not been
stated, and ``None`` says *no rate has been declared* rather than asserting a zero one. No
costing reads either field -- the amount to move is passed to ``cost_one`` explicitly -- so a
fixture that invented them would be inventing numbers nothing needs. The tests that do need
a stated amount or rate declare their own, and say there that they invented it.
"""

CONTRACT_USD = IncomeStream(
    id="contract_usd",
    owner_id=OWNER_ID,
    amount=Money(0.0, Currency.USD, prov.EMPTY),
    cadence="monthly",
    arrives_at=ORIGIN_VENUE,
    indexation=Indexation(policy="none", rate=None),
    income_tax_rate=None,
)
"""The dollar contract income. The stream that needs no conversion at all, which is the
whole of §4.2's structural point."""

STREAMS: Mapping[str, IncomeStream] = {
    SALARY_UAH.id: SALARY_UAH,
    CONTRACT_USD.id: CONTRACT_USD,
}
"""The owner's declared streams, keyed by id -- what every ``cost_one`` call resolves a
path's ``stream_id`` against.

Two of them, in two currencies, because one stream makes the per-stream requirement
untestable in exactly the way one currency made ``C5`` untestable in feature 001.
"""


@dataclass(frozen=True, slots=True)
class Graph:
    """One generated route graph and everything needed to cost a path through it."""

    path: FundingPath
    route: Route
    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    reference_rate: float


def _channel(
    reference: float,
    buy_premium: float,
    sell_premium: float,
    *,
    channel_id: str = CHANNEL_ID,
    kind: str = P2P_PREMIUM.id,
) -> FxChannel:
    """One two-sided quote for :data:`PAIR`.

    ``channel_id`` and ``kind`` are parameters so a fixture can declare a *second* channel
    for the same pair -- a bank quote beside a peer-to-peer one. Two channels quoting one
    pair against the same reference and different markups is the ordinary case and is what
    the two-sided quote is for; two channels quoting different *references* is the
    disagreement this module's docstring refuses, so the reference stays one argument.
    """
    return FxChannel(
        id=channel_id,
        pair=PAIR,
        reference_rate=reference,
        buy_side=ChannelSide(
            markup_bps=None,
            premium_per_unit=Money(buy_premium, PAIR[0], RATE_SOURCES),
            kind=kind,
            provenance=RATE_SOURCES,
        ),
        sell_side=ChannelSide(
            markup_bps=None,
            premium_per_unit=Money(sell_premium, PAIR[0], RATE_SOURCES),
            kind=kind,
            provenance=RATE_SOURCES,
        ),
        observed_on=RETRIEVED_ON,
        kind=kind,
        provenance=RATE_SOURCES,
    )


def _leg(
    *,
    index: int,
    kind: str,
    from_ccy: Currency,
    to_ccy: Currency,
    fee_pct: float,
    fee_fixed: float,
    minimum: float | None,
    maximum: float | None = None,
    monthly_cap: float | None = None,
    window: tuple[date | None, date | None] = (None, None),
    disruption: float = 0.0,
    pool: str | None = None,
    channel_id: str = CHANNEL_ID,
    observation: str | None = None,
) -> Leg:
    """One leg of a hand-built fixture route.

    ``channel_id`` names which declared channel an ``fx`` leg crosses at, so a second
    corridor can price its conversion against a different quote for the same pair.
    ``observation`` overrides which staleness threshold the leg's numbers age under; left
    ``None`` it follows the kind, which is the right default for every fixture whose only
    conversion is a peer-to-peer one.
    """
    return Leg(
        index=index,
        kind=kind,
        from_venue=f"venue_{index}",
        to_venue=f"venue_{index + 1}",
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=channel_id if kind == FX else None,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, from_ccy, FEE_SOURCES),
        minimum=None if minimum is None else Money(minimum, from_ccy, FEE_SOURCES),
        maximum=None if maximum is None else Money(maximum, from_ccy, FEE_SOURCES),
        monthly_cap=None if monthly_cap is None else Money(monthly_cap, from_ccy, FEE_SOURCES),
        capacity_pool=pool,
        latency_days=index,
        available_from=window[0],
        available_until=window[1],
        disruption_probability=disruption,
        kind_of_observation=(
            observation
            if observation is not None
            else (P2P_PREMIUM.id if kind == FX else BANK_FEE_SCHEDULE.id)
        ),
        provenance=FEE_SOURCES,
    )


def _other(currency: Currency) -> Currency:
    return Currency.USD if currency is Currency.UAH else Currency.UAH


_KIND_TOKENS = st.sampled_from([TRANSFER, FX, "trade", "withdrawal"])
_FEE_PCT = st.floats(min_value=0.0, max_value=0.05, allow_nan=False, allow_infinity=False)
_FEE_FIXED = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_MINIMUM = st.one_of(
    st.none(), st.floats(min_value=0.0, max_value=5_000.0, allow_nan=False, allow_infinity=False)
)
_MAXIMUM = st.one_of(
    st.none(),
    st.none(),
    st.none(),
    st.floats(min_value=500_000.0, max_value=2_000_000.0, allow_nan=False, allow_infinity=False),
)
"""Weighted towards absent, because a maximum that binds ends the walk early.

``st.one_of`` picks roughly uniformly among its branches, so the repeated ``none()`` is how a
strategy expresses "usually not declared". Without the weighting most generated routes would
be unusable and the attribution property would pass by never reaching any arithmetic.
"""

_MONTHLY_CAP = st.one_of(
    st.none(),
    st.floats(min_value=1_000.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
)
"""A cap does not stop a costing -- it sets the reported ceiling -- so it needs no weighting.

A generated cap always comes with a **pool**, one per leg. A monthly limit belongs to a rail,
and a limit with no rail has no key to accumulate under, so ``capacity.caps_of`` refuses the
combination rather than inventing one (research.md D10). One pool per leg rather than one
shared across the route because two legs naming the same pool must declare the *same* cap, and
independently drawn caps would not.
"""

_WINDOW = st.one_of(
    st.just((None, None)),
    st.just((None, None)),
    st.just((None, None)),
    st.just((date(2027, 1, 1), None)),
    st.just((None, date(2026, 1, 1))),
)
"""Availability windows, two of which exclude :data:`ON_DATE`. A leg's window is a *fact*
about the corridor with a source, never an assumption -- a regime transition is the
assumption, and it lives in scenario data (research.md D8)."""

_DISRUPTION = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def _chain(
    draw: st.DrawFn, start: Currency, first_index: int, length: int
) -> tuple[tuple[Leg, ...], Currency]:
    """A chained run of legs starting in one currency, and the currency it ends in."""
    legs: list[Leg] = []
    currency = start
    for offset in range(length):
        kind = draw(_KIND_TOKENS)
        to_ccy = _other(currency) if kind == FX else currency
        legs.append(
            _leg(
                index=first_index + offset,
                kind=kind,
                from_ccy=currency,
                to_ccy=to_ccy,
                fee_pct=draw(_FEE_PCT),
                fee_fixed=draw(_FEE_FIXED),
                minimum=draw(_MINIMUM),
                maximum=draw(_MAXIMUM),
                monthly_cap=(cap := draw(_MONTHLY_CAP)),
                pool=None if cap is None else f"pool_{first_index + offset}",
                window=draw(_WINDOW),
                disruption=draw(_DISRUPTION),
            )
        )
        currency = to_ccy
    return tuple(legs), currency


@st.composite
def route_graphs(
    draw: st.DrawFn,
    *,
    base: Currency | None = None,
    with_partner: bool | None = None,
    status: RouteStatus = "open",
) -> Graph:
    """A valid inbound route, optionally paired with a declared exit route.

    ``base`` fixes the currency the money starts in; left open it is drawn, so a property
    that has only ever seen UAH is not mistaken for a property about the ledger. Feature 001
    produced only UAH, and a conversion invariant asserted in one currency asserts very
    little.
    """
    origin = base if base is not None else draw(st.sampled_from(Currency))
    reference = draw(st.floats(min_value=5.0, max_value=60.0, allow_nan=False))
    channel = _channel(
        reference,
        draw(st.floats(min_value=-4.0, max_value=4.0, allow_nan=False)),
        draw(st.floats(min_value=-4.0, max_value=4.0, allow_nan=False)),
    )
    inbound_legs, destination_currency = draw(
        _chain(start=origin, first_index=0, length=draw(st.integers(min_value=1, max_value=3)))
    )
    paired = draw(st.booleans()) if with_partner is None else with_partner
    routes: dict[str, Route] = {}
    partner_id = "exit_route" if paired else None
    if paired:
        exit_legs, _ = draw(
            _chain(
                start=destination_currency,
                first_index=0,
                length=draw(st.integers(min_value=1, max_value=2)),
            )
        )
        routes["exit_route"] = Route(
            id="exit_route",
            provider="Synthetic Provider",
            origin=f"venue_{len(inbound_legs)}",
            destination="venue_home",
            direction="exit",
            partner_route=None,
            status="open",
            legs=exit_legs,
        )
    inbound = Route(
        id="inbound_route",
        provider="Synthetic Provider",
        origin="venue_0",
        destination=f"venue_{len(inbound_legs)}",
        direction="inbound",
        partner_route=partner_id,
        status=status,
        legs=inbound_legs,
    )
    routes[inbound.id] = inbound
    return Graph(
        path=FundingPath(
            destination_id=inbound.destination,
            stream_id=SALARY_UAH.id if origin is Currency.UAH else CONTRACT_USD.id,
            route_id=inbound.id,
        ),
        route=inbound,
        routes=routes,
        channels={CHANNEL_ID: channel},
        reference_rate=reference,
    )


AMOUNTS = st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
"""Amounts to move, including zero -- a fixed fee on nothing is a case worth asserting."""


def base_factor(legs: tuple[Leg, ...], start: Currency, reference: float) -> float:
    """Base-currency value of one unit of the currency the chain ends in.

    Recomputed here, independently of the engine, so the attribution invariant checks the
    fold against a tally drawn from the same declarations rather than against another
    figure the fold produced. The same discipline as the ledger conservation suites.
    """
    factor = 1.0
    currency = start
    for leg in legs:
        if leg.kind != FX:
            continue
        factor = factor * reference if currency is PAIR[0] else factor / reference
        currency = leg.to_ccy
    return factor


def zero_cost_graph(*, fixed_fee: float = 0.0, with_exit: bool = False) -> Graph:
    """The domestic path: two ``transfer`` legs in one currency, declaring zero fees.

    Built by hand rather than drawn, because it is the *bar* the generated cases are
    measured against (SC-004): a route whose every leg declares zero costs exactly zero and
    delivers exactly what was sent. A generated route cannot play that role -- the point is
    that this one has nothing in it.

    ``fixed_fee`` exists so the same shape can also express the degenerate case that most
    invites a silent clamp: a flat fee charged on an amount of zero.

    ``with_exit`` declares the way back out, which is what makes this route *comparable*
    rather than merely costed. Without it the round trip is ``ExitCostUnknown`` and the route
    is kept out of every ranking (FR-030), so the default stays ``False`` -- the honest state
    of a route nobody has costed the exit for -- and a comparison asks for the exit
    explicitly.
    """
    legs = tuple(
        _leg(
            index=index,
            kind=TRANSFER,
            from_ccy=Currency.UAH,
            to_ccy=Currency.UAH,
            fee_pct=0.0,
            fee_fixed=fixed_fee,
            minimum=None,
        )
        for index in range(2)
    )
    routes: dict[str, Route] = {}
    partner_id = "inzhur_exit" if with_exit else None
    if partner_id is not None:
        routes[partner_id] = Route(
            id=partner_id,
            provider="Inzhur",
            origin="venue_2",
            destination="venue_3",
            direction="exit",
            partner_route=None,
            status="open",
            legs=(
                _leg(
                    index=2,
                    kind=TRANSFER,
                    from_ccy=Currency.UAH,
                    to_ccy=Currency.UAH,
                    fee_pct=0.0,
                    fee_fixed=fixed_fee,
                    minimum=None,
                ),
            ),
        )
    route = Route(
        id="inzhur_direct",
        provider="Inzhur",
        origin="venue_0",
        destination="venue_2",
        direction="inbound",
        partner_route=partner_id,
        status="open",
        legs=legs,
    )
    routes[route.id] = route
    return Graph(
        path=FundingPath(
            destination_id=route.destination, stream_id=SALARY_UAH.id, route_id=route.id
        ),
        route=route,
        routes=routes,
        channels={CHANNEL_ID: _channel(42.0, 0.0, 0.0)},
        reference_rate=42.0,
    )


def p2p_graph(
    *, buy_premium: float = 3.0, sell_premium: float = -3.0, reference: float = 42.0
) -> Graph:
    """The §4.3.1 shape: one hryvnia-to-dollar conversion in, one declared conversion out.

    Every fee is zero, so every hryvnia this route costs is the channel's spread and nothing
    else. That is what makes the hand arithmetic in
    ``tests/worked_examples/test_ramp_p2p_premium.py`` one division per leg rather than a
    reconciliation, and it is why this fixture is built rather than drawn: a generated route
    would put fees between one declared premium and one reported cost.

    The exit route is **declared, not derived** (FR-027). Its premium is a separate argument
    because a real P2P book is asymmetric, and a fixture that could only express a symmetric
    spread would let a round trip computed as twice the one way pass.
    """
    exit_route = Route(
        id="binance_p2p_to_monobank",
        provider="Binance P2P",
        origin="venue_1",
        destination="venue_2",
        direction="exit",
        partner_route=None,
        status="open",
        legs=(
            _leg(
                index=1,
                kind=FX,
                from_ccy=Currency.USD,
                to_ccy=Currency.UAH,
                fee_pct=0.0,
                fee_fixed=0.0,
                minimum=None,
            ),
        ),
    )
    inbound = Route(
        id="monobank_to_binance_p2p",
        provider="Binance P2P",
        origin="venue_0",
        destination="venue_1",
        direction="inbound",
        partner_route=exit_route.id,
        status="open",
        legs=(
            _leg(
                index=0,
                kind=FX,
                from_ccy=Currency.UAH,
                to_ccy=Currency.USD,
                fee_pct=0.0,
                fee_fixed=0.0,
                minimum=None,
            ),
        ),
    )
    return Graph(
        path=FundingPath(
            destination_id=inbound.destination, stream_id=SALARY_UAH.id, route_id=inbound.id
        ),
        route=inbound,
        routes={inbound.id: inbound, exit_route.id: exit_route},
        channels={CHANNEL_ID: _channel(reference, buy_premium, sell_premium)},
        reference_rate=reference,
    )


BANK_CHANNEL_ID = "bank"
"""A second declared quote for the same pair: a bank's rate rather than a P2P book's.

The same reference, a much narrower spread. Two channels quoting one pair against one
reference and different markups is the ordinary case -- it is what a two-sided quote is
*for* -- and it is what makes :func:`bank_corridor_graph` a controlled comparison against
:func:`p2p_graph` rather than a second world with its own idea of what a dollar is worth.
"""


def bank_corridor_graph(
    *, buy_premium: float = 0.5, sell_premium: float = -0.5, reference: float = 42.0
) -> Graph:
    """The narrow corridor: one conversion in and one declared conversion out, at a bank.

    Same shape as :func:`p2p_graph`, same origin venue, same destination venue, same stream,
    same reference rate, zero fees -- and a spread of 0.5 UAH per dollar instead of 3. So the
    **only** thing that differs between the two graphs is which corridor carries the money,
    which is what makes the regime example (``tests/worked_examples/test_regime_transition.py``)
    a controlled experiment: the cost drop is attributable to the route set and to nothing else.

    Its channel is declared under its own id, so a caller costing both corridors passes **one**
    channels mapping holding both quotes. That matters: had each regime been costed against its
    own mapping, the rate would have changed with the route set and the drop would have had two
    causes.

    The bank's numbers age as a ``bank_fee_schedule`` rather than a ``p2p_premium`` -- a
    published bank rate does not move the way a P2P book does -- so the two corridors also
    carry different staleness verdicts against the same ``as_of``. Nothing in the arithmetic
    depends on that; it is stated because a fixture calling a bank quote a peer-to-peer premium
    would be inventing a fact about how the number was observed.

    Every figure here is **invented**, with an empty ``verified_on``, exactly like every other
    route number in this project.
    """
    exit_route = Route(
        id="broker_to_bank",
        provider="Universal Bank",
        origin="venue_1",
        destination="venue_2",
        direction="exit",
        partner_route=None,
        status="open",
        legs=(
            _leg(
                index=1,
                kind=FX,
                from_ccy=Currency.USD,
                to_ccy=Currency.UAH,
                fee_pct=0.0,
                fee_fixed=0.0,
                minimum=None,
                channel_id=BANK_CHANNEL_ID,
                observation=BANK_FEE_SCHEDULE.id,
            ),
        ),
    )
    inbound = Route(
        id="bank_uah_to_broker",
        provider="Universal Bank",
        origin=ORIGIN_VENUE,
        destination="venue_1",
        direction="inbound",
        partner_route=exit_route.id,
        status="open",
        legs=(
            _leg(
                index=0,
                kind=FX,
                from_ccy=Currency.UAH,
                to_ccy=Currency.USD,
                fee_pct=0.0,
                fee_fixed=0.0,
                minimum=None,
                channel_id=BANK_CHANNEL_ID,
                observation=BANK_FEE_SCHEDULE.id,
            ),
        ),
    )
    return Graph(
        path=FundingPath(
            destination_id=inbound.destination, stream_id=SALARY_UAH.id, route_id=inbound.id
        ),
        route=inbound,
        routes={inbound.id: inbound, exit_route.id: exit_route},
        channels={
            BANK_CHANNEL_ID: _channel(
                reference,
                buy_premium,
                sell_premium,
                channel_id=BANK_CHANNEL_ID,
                kind=BANK_FEE_SCHEDULE.id,
            )
        },
        reference_rate=reference,
    )


def usd_direct_graph() -> Graph:
    """The dollar stream's way in: one zero-fee ``transfer`` leg, and **no conversion at all**.

    The other half of the **G1** comparison, and the reason the finding is a finding. It ends
    at the same destination venue as :func:`p2p_graph` -- ``venue_1``, dollars at the
    exchange -- and starts at the same origin venue. Same origin, same destination, same value
    deployed; the only thing that differs is which stream funds it, and therefore whether a
    hryvnia-to-dollar conversion has to happen at all.

    There is deliberately **no** ``fx`` leg and the leg names **no channel**, so nothing in
    this route consults a rate. That is what makes FR-009's *exactly* zero exact rather than
    small: no conversion happens, so there is no spread to round. The channel is still
    declared in the returned graph, which is the stronger statement -- a channel being
    available does not make a conversion happen.

    ``partner_route`` is ``None``, and that is honest rather than lazy: nobody has declared
    how dollars at an exchange get back to spendable hryvnia, and §4.2 notes that converting
    the dollar stream *to* hryvnia is the expensive direction. So the round trip is
    ``ExitCostUnknown`` (FR-030) and this route is not comparison-ready -- which is exactly
    what the owner should be told about it.
    """
    route = Route(
        id="usd_direct_to_binance",
        provider="Binance",
        origin=ORIGIN_VENUE,
        destination="venue_1",
        direction="inbound",
        partner_route=None,
        status="open",
        legs=(
            _leg(
                index=0,
                kind=TRANSFER,
                from_ccy=Currency.USD,
                to_ccy=Currency.USD,
                fee_pct=0.0,
                fee_fixed=0.0,
                minimum=None,
            ),
        ),
    )
    return Graph(
        path=FundingPath(
            destination_id=route.destination,
            stream_id=CONTRACT_USD.id,
            route_id=route.id,
        ),
        route=route,
        routes={route.id: route},
        channels={CHANNEL_ID: _channel(42.0, 3.0, -3.0)},
        reference_rate=42.0,
    )


CARD_POOL = "monobank_card_uah_usd"
"""The rail the capped fixtures run over: the owner's Monobank card.

Named rather than anonymous because it is the point. Monobank's monthly limit is one of the
four figures ``SIMULATOR_SPEC.md`` §11 item 1 records as the reason this feature exists, and it
belongs to the **card** -- so two routes both touching the card consume one limit, and both
name this pool (research.md D10). The limit's *value* is still a fixture and unobserved.
"""


def capped_graph(
    *,
    cap: float | None = None,
    disruption: tuple[float, float] = (0.0, 0.0),
    pool: str = CARD_POOL,
    route_id: str = "inzhur_direct",
) -> Graph:
    """The zero-cost domestic shape, with a declared monthly cap and per-leg disruption.

    Built by hand for the same reason :func:`zero_cost_graph` is: these tests are about one
    declared field reaching one reported field, and a generated route would put noise between
    the two.

    Both legs name the **same** pool and declare the **same** cap, which is what D10 requires
    of two legs sharing a rail -- and it means ``capacity.caps_of`` reports the card's limit
    once rather than twice. ``route_id`` varies so that a second route can be built over the
    same rail, which is the property the accumulator exists for.
    """
    legs = tuple(
        _leg(
            index=index,
            kind=TRANSFER,
            from_ccy=Currency.UAH,
            to_ccy=Currency.UAH,
            fee_pct=0.0,
            fee_fixed=0.0,
            minimum=None,
            monthly_cap=cap,
            pool=None if cap is None else pool,
            disruption=disruption[index],
        )
        for index in range(2)
    )
    route = Route(
        id=route_id,
        provider="Inzhur",
        origin="venue_0",
        destination="venue_2",
        direction="inbound",
        partner_route=None,
        status="open",
        legs=legs,
    )
    return Graph(
        path=FundingPath(
            destination_id=route.destination, stream_id=SALARY_UAH.id, route_id=route.id
        ),
        route=route,
        routes={route.id: route},
        channels={CHANNEL_ID: _channel(42.0, 0.0, 0.0)},
        reference_rate=42.0,
    )


# ---------------------------------------------------------------------------
# 003-route-coverage: registries the coverage audit and costing can both be run over
# ---------------------------------------------------------------------------
#
# The strategies above generate one route at a time, because the properties they serve are
# about *arithmetic*. The coverage properties are about a whole registry -- every venue, every
# stream, every corridor -- so they need a generator that produces one, and
# ``test_coverage_costing_agreement.py`` needs the registry to be one where the audit and
# ``cost_one`` are answering the same question.
#
# ⚙ **Four scoping decisions, each of which keeps a refusal that is out of scope out of the
# generated data** (003 research.md D11). FR-018's agreement is scoped to costing's
# *route-existence* refusals -- no matching route, and ``ExitCostUnknown`` -- because those are
# the same fact coverage reports. ``RouteUnusable`` is *feasibility today*, which FR-022
# deliberately excludes from coverage, so a generator that produced it would fail the property
# for a reason the property is not about. The fix would then look like weakening the coverage
# rule, which is exactly the pressure D11 exists to remove. So:
#
# 1. **No minimum, no maximum, no monthly cap.** Every one of them binds on an amount and
#    yields ``RouteUnusable``.
# 2. **No availability window.** Same, on a date.
# 3. **Every route ``open``.** A closed route is ``RouteUnusable`` at costing time and is
#    *declared* for coverage (FR-022) -- a real disagreement between the two views, and a
#    deliberate one, so it is asserted in ``test_coverage_data_only.py`` rather than generated
#    into a property that would read it as a defect.
# 4. **Partner-closed.** An inbound route declares its exit as ``partner_route`` if and only if
#    that exit exists. Coverage finds an exit by its own direction and origin and never by
#    following the partner link (D6), and costing finds it *only* by the partner link -- so a
#    registry where the two can disagree is a registry where the property is not about what it
#    claims to be. The disagreement itself is real and is feature 004's to reconcile.
#
# One more, which is not a scoping decision but a modelling one: **every venue here holds
# exactly one currency**. Coverage's destination is a currency balance at a venue and costing's
# ``FundingPath.destination_id`` is a venue, so with two currencies at one venue the two views
# are keyed differently and the comparison would need a mapping that could itself be wrong.

BASE_CURRENCY = Currency.UAH
"""What the owner earns and spends, and what an exit has to deliver to count as a way out."""

HOME_VENUE = "home_uah"
"""Where the salary lands and the only place money counts as spent. Holds hryvnia only."""

CONTRACT_VENUE = "coin_usd"
"""Where the dollar contract income lands. Holds dollars only."""

COVERAGE_SALARY = IncomeStream(
    id="salary_uah",
    owner_id=OWNER_ID,
    amount=Money(0.0, Currency.UAH, prov.EMPTY),
    cadence="monthly",
    arrives_at=HOME_VENUE,
    indexation=Indexation(policy="cpi", rate=None),
    income_tax_rate=None,
)
COVERAGE_CONTRACT = IncomeStream(
    id="contract_usd",
    owner_id=OWNER_ID,
    amount=Money(0.0, Currency.USD, prov.EMPTY),
    cadence="monthly",
    arrives_at=CONTRACT_VENUE,
    indexation=Indexation(policy="none", rate=None),
    income_tax_rate=None,
)
COVERAGE_STREAMS: Mapping[str, IncomeStream] = {
    COVERAGE_SALARY.id: COVERAGE_SALARY,
    COVERAGE_CONTRACT.id: COVERAGE_CONTRACT,
}
"""Two streams in two currencies arriving at two venues.

Two currencies because the currency half of an inbound match is what a one-currency registry
cannot exercise, and two *venues* because the venue half is what a one-venue registry cannot.
"""

COVERAGE_AMOUNTS: Mapping[str, Money] = {
    COVERAGE_SALARY.id: Money(10_000.0, Currency.UAH, prov.EMPTY),
    COVERAGE_CONTRACT.id: Money(1_000.0, Currency.USD, prov.EMPTY),
}
"""What to cost, per stream. Comfortably inside every declared limit -- because there are no
declared limits, which is scoping decision 1 above."""


@dataclass(frozen=True, slots=True)
class CoverageRegistry:
    """One generated registry, and everything both views of it need."""

    venues: Mapping[str, Venue]
    streams: Mapping[str, IncomeStream]
    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    spendable: frozenset[SpendableEndpoint]


def _unlimited_leg(
    index: int, *, from_venue: str, to_venue: str, from_ccy: Currency, to_ccy: Currency
) -> Leg:
    """One movement with no limit and no window, so nothing about it can bind on an amount."""
    converts = from_ccy is not to_ccy
    return Leg(
        index=index,
        kind=FX if converts else TRANSFER,
        from_venue=from_venue,
        to_venue=to_venue,
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=CHANNEL_ID if converts else None,
        fee_pct=0.0,
        fee_fixed=Money(0.0, from_ccy, FEE_SOURCES),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation=P2P_PREMIUM.id if converts else BANK_FEE_SCHEDULE.id,
        provenance=FEE_SOURCES,
    )


def _corridor(
    route_id: str,
    *,
    origin: str,
    destination: str,
    direction: str,
    from_ccy: Currency,
    to_ccy: Currency,
    partner_route: str | None = None,
) -> Route:
    """One open, unlimited, single-leg corridor."""
    return Route(
        id=route_id,
        provider=f"Synthetic {route_id}",
        origin=origin,
        destination=destination,
        direction="inbound" if direction == "inbound" else "exit",
        partner_route=partner_route,
        status="open",
        legs=(
            _unlimited_leg(
                0,
                from_venue=origin,
                to_venue=destination,
                from_ccy=from_ccy,
                to_ccy=to_ccy,
            ),
        ),
    )


@st.composite
def coverage_registries(draw: st.DrawFn) -> CoverageRegistry:
    """A registry with a drawn set of holes in it, over which both views can be run.

    One to three destination venues, each holding one drawn currency, and for each of them
    three independent booleans: is there a way in from the salary, is there a way in from the
    contract income, is there a way out. Every combination of the three is reachable, which is
    what makes the property a property rather than an example -- including the two that matter
    most, a destination reachable from both streams with no exit, and one reachable from
    neither with an exit nobody can use.

    The exit always ends in hryvnia at :data:`HOME_VENUE`, which is the single declared
    spendable endpoint. So "an exit exists" and "an exit reaches somewhere spendable" coincide
    here by construction; deficit 3, where they come apart, is exercised by the unit and
    contract suites, which can declare a non-spendable landing place on purpose.
    """
    venues: dict[str, Venue] = {
        HOME_VENUE: Venue(
            id=HOME_VENUE,
            name="Home rail (SYNTHETIC FIXTURE)",
            currencies=frozenset({Currency.UAH}),
        ),
        CONTRACT_VENUE: Venue(
            id=CONTRACT_VENUE,
            name="Contract rail (SYNTHETIC FIXTURE)",
            currencies=frozenset({Currency.USD}),
        ),
    }
    routes: dict[str, Route] = {}
    for index in range(draw(st.integers(min_value=1, max_value=3))):
        venue_id = f"dest_{index}"
        currency = draw(st.sampled_from(Currency))
        venues[venue_id] = Venue(
            id=venue_id,
            name=f"{venue_id} (SYNTHETIC FIXTURE)",
            currencies=frozenset({currency}),
        )
        exit_id = f"out_{index}" if draw(st.booleans()) else None
        if exit_id is not None:
            routes[exit_id] = _corridor(
                exit_id,
                origin=venue_id,
                destination=HOME_VENUE,
                direction="exit",
                from_ccy=currency,
                to_ccy=BASE_CURRENCY,
            )
        for stream, origin in (
            (COVERAGE_SALARY, HOME_VENUE),
            (COVERAGE_CONTRACT, CONTRACT_VENUE),
        ):
            if not draw(st.booleans()):
                continue
            inbound_id = f"in_{stream.id}_{index}"
            routes[inbound_id] = _corridor(
                inbound_id,
                origin=origin,
                destination=venue_id,
                direction="inbound",
                from_ccy=stream.amount.currency,
                to_ccy=currency,
                # Partner-closed: the exit is declared as the partner exactly when it exists,
                # which is what keeps the two views answering one question (scoping note 4).
                partner_route=exit_id,
            )
    if not routes:
        # Every boolean came up false. A registry with **no declared route at all** is not a
        # coverage report -- it is ``RegistryDimensionEmpty``, which is a different claim and
        # is exercised by ``tests/unit/test_coverage_empty.py`` on purpose. Rather than
        # discarding the example, the least distorting repair is one orphan exit: it declares
        # a corridor without declaring any way in, so every pair stays not-ready and the
        # "destination nothing reaches" shape is preserved rather than papered over.
        first = venues["dest_0"]
        (currency,) = first.currencies
        routes["out_0"] = _corridor(
            "out_0",
            origin=first.id,
            destination=HOME_VENUE,
            direction="exit",
            from_ccy=currency,
            to_ccy=BASE_CURRENCY,
        )
    return CoverageRegistry(
        venues=venues,
        streams=COVERAGE_STREAMS,
        routes=routes,
        channels={CHANNEL_ID: _channel(42.0, 3.0, -3.0)},
        spendable=frozenset({SpendableEndpoint(venue_id=HOME_VENUE, currency=BASE_CURRENCY)}),
    )
