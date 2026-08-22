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
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteStatus
from terezy.core.routes.path import FundingPath

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


@dataclass(frozen=True, slots=True)
class Graph:
    """One generated route graph and everything needed to cost a path through it."""

    path: FundingPath
    route: Route
    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    reference_rate: float


def _channel(reference: float, buy_premium: float, sell_premium: float) -> FxChannel:
    return FxChannel(
        id=CHANNEL_ID,
        pair=PAIR,
        reference_rate=reference,
        buy_side=ChannelSide(
            markup_bps=None, premium_per_unit=Money(buy_premium, PAIR[0], RATE_SOURCES)
        ),
        sell_side=ChannelSide(
            markup_bps=None, premium_per_unit=Money(sell_premium, PAIR[0], RATE_SOURCES)
        ),
        observed_on=RETRIEVED_ON,
        kind=P2P_PREMIUM.id,
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
) -> Leg:
    return Leg(
        index=index,
        kind=kind,
        from_venue=f"venue_{index}",
        to_venue=f"venue_{index + 1}",
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=CHANNEL_ID if kind == FX else None,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, from_ccy, FEE_SOURCES),
        minimum=None if minimum is None else Money(minimum, from_ccy, FEE_SOURCES),
        maximum=None if maximum is None else Money(maximum, from_ccy, FEE_SOURCES),
        monthly_cap=None if monthly_cap is None else Money(monthly_cap, from_ccy, FEE_SOURCES),
        latency_days=index,
        available_from=window[0],
        available_until=window[1],
        disruption_probability=disruption,
        kind_of_observation=P2P_PREMIUM.id if kind == FX else BANK_FEE_SCHEDULE.id,
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
"""A cap does not stop a costing -- it sets the reported ceiling -- so it needs no weighting."""

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
                monthly_cap=draw(_MONTHLY_CAP),
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
            stream_id="salary" if origin is Currency.UAH else "contract",
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


def zero_cost_graph(*, fixed_fee: float = 0.0) -> Graph:
    """The domestic path: two ``transfer`` legs in one currency, declaring zero fees.

    Built by hand rather than drawn, because it is the *bar* the generated cases are
    measured against (SC-004): a route whose every leg declares zero costs exactly zero and
    delivers exactly what was sent. A generated route cannot play that role -- the point is
    that this one has nothing in it.

    ``fixed_fee`` exists so the same shape can also express the degenerate case that most
    invites a silent clamp: a flat fee charged on an amount of zero.
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
    route = Route(
        id="inzhur_direct",
        provider="Inzhur",
        origin="venue_0",
        destination="venue_2",
        direction="inbound",
        partner_route=None,
        status="open",
        legs=legs,
    )
    return Graph(
        path=FundingPath(destination_id=route.destination, stream_id="salary", route_id=route.id),
        route=route,
        routes={route.id: route},
        channels={CHANNEL_ID: _channel(42.0, 0.0, 0.0)},
        reference_rate=42.0,
    )


def capped_graph(
    *, cap: float | None = None, disruption: tuple[float, float] = (0.0, 0.0)
) -> Graph:
    """The zero-cost domestic shape, with a declared monthly cap and per-leg disruption.

    Built by hand for the same reason :func:`zero_cost_graph` is: these tests are about one
    declared field reaching one reported field, and a generated route would put noise between
    the two.
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
            disruption=disruption[index],
        )
        for index in range(2)
    )
    route = Route(
        id="inzhur_direct",
        provider="Inzhur",
        origin="venue_0",
        destination="venue_2",
        direction="inbound",
        partner_route=None,
        status="open",
        legs=legs,
    )
    return Graph(
        path=FundingPath(destination_id=route.destination, stream_id="salary", route_id=route.id),
        route=route,
        routes={route.id: route},
        channels={CHANNEL_ID: _channel(42.0, 0.0, 0.0)},
        reference_rate=42.0,
    )
