"""Hand-built registries for the composition suites, on the ``tests/coverage_registries.py`` plan.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never run.
It exists for the reason that module gives: the composition cases care about *the shape of a
route graph* -- what chains, what does not, what loops, what duplicates a declared route -- and
declaring five venues and four corridors inside each of nine test modules would mean nine places
to edit when a record gains a field.

**The worked examples do not reach for the builders below where the arithmetic is the point.**
``tests/worked_examples/test_composed_arithmetic.py`` uses :func:`two_hop` because the whole
registry is four lines of declaration and the hand arithmetic is stated beside the assertion; a
generated corridor would put noise between one declared premium and one reported cost.

**Every number here is invented and every ``verified_on`` is empty**, so every figure derived
from these registries carries the unverified mark -- which is the honest state of route data in
this project and what gives the propagation tests something real to propagate.

## The one corridor the whole feature is about

``salary_venue -> exchange -> broker``, with **no** declared ``salary_venue -> broker``. That is
the owner's own case: UAH salary into Binance is declared, Binance into IBKR is declared, and
UAH salary into IBKR via Binance exists only if somebody sits down and hand-writes the
concatenation. The numbers are chosen so the hand arithmetic closes on round figures:

* the reference is 42 UAH per USD, the P2P buy price 45 and the sell price 39.5;
* the first segment charges nothing but the spread;
* the second charges 1% and a flat 1 USD, so both fee components are non-zero and neither can
  hide behind the other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.composed import SegmentBound
from terezy.core.results.coverage import Destination, SpendableEndpoint
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteDirection, RouteStatus
from terezy.core.routes.venues import Venue
from terezy.core.streams.streams import IncomeStream, Indexation

UAH = Currency.UAH
USD = Currency.USD

OWNER_ID = "owner-001"
"""The one owner. Carried from the first commit while there is exactly one (Principle VII)."""

ON_DATE = date(2026, 8, 21)
"""When the money moves, in every case below. Data, never a clock."""

AS_OF = date(2026, 8, 21)
"""When the question is asked. A separate argument everywhere, because a projection into the
future must not report its own inputs as stale."""

RETRIEVED_ON = date(2026, 8, 1)
"""20 days before the as-of date, so the two kinds below disagree about staleness."""

REGIME_ID = "single"
"""The implicit regime a registry with no scenario is searched under. A name rather than an
empty string, so a report can say which world produced a candidate set."""

FEE_SOURCE = SourceRef(
    id="synthetic:composed-fees",
    citation="SYNTHETIC FIXTURE -- invented fee schedule. Not an observed tariff.",
    retrieved_on=RETRIEVED_ON,
    verified_on=None,
)
RATE_SOURCE = SourceRef(
    id="synthetic:composed-rate",
    citation="SYNTHETIC FIXTURE -- invented reference and premium. Not an observed quote.",
    retrieved_on=RETRIEVED_ON,
    verified_on=None,
)
FEE_SOURCES: Provenance = prov.of([FEE_SOURCE])


def fee_source_ref(corridor_id: str) -> SourceRef:
    """The single citation :func:`fee_source` wraps, for a test that wants to name it."""
    return SourceRef(
        id=f"synthetic:composed-fees:{corridor_id}",
        citation=(
            f"SYNTHETIC FIXTURE -- invented fee schedule for {corridor_id}. Not an observed tariff."
        ),
        retrieved_on=RETRIEVED_ON,
        verified_on=None,
    )


def fee_source(corridor_id: str) -> Provenance:
    """A citation of this corridor's **own** invented fee schedule.

    ⚙ **One source per corridor, not one shared object.** Every leg here used to cite the same
    ``FEE_SOURCE``, which made "the sources of every segment reach the composed figure" a claim
    no assertion could actually check: the union of one source with itself is that source, so the
    test passed whether or not the second segment's mark survived the join. Distinct ids make the
    propagation visible, and a dropped mark shows up as a missing id rather than as nothing.
    """
    return prov.of([fee_source_ref(corridor_id)])


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
"""Two thresholds far apart, so a composed candidate exercises both verdicts at once: at 20 days
old the premium is stale and the fee schedule is not, and a chain crossing both must report the
stale one rather than averaging the two away."""

CHANNEL_ID = "p2p"
PAIR = (UAH, USD)
"""``(price currency, unit currency)``: the reference is UAH per USD."""

REFERENCE = 42.0
BUY_PREMIUM = 3.0
"""Buying dollars costs 45 UAH each -- ``SIMULATOR_SPEC.md`` §4.3.1's own shape."""
SELL_PREMIUM = -2.5
"""Selling them back receives 39.5. Asymmetric on purpose: a fixture that could only express a
symmetric spread would let a round trip computed as twice the one way pass."""

SALARY_VENUE = "salary_venue"
EXCHANGE = "exchange"
BROKER = "broker"
WALLET = "wallet"
FUND = "fund"
"""A domestic pair, both hryvnia, used only by the capacity example.

Two hops in **one** currency on purpose: two legs sharing a rail must declare the **same**
monthly cap, and a cap is a ``Money`` in the leg's own currency -- so a pool shared across a
conversion could not be expressed at all without inventing a rate for the limit. The rail this
models is the owner's card, and a card's limit is in hryvnia.
"""

CARD_POOL = "monobank_card"
"""The rail both segments of :func:`pooled` run over.

Named rather than anonymous because it is the point: Monobank's monthly limit is one of the
four figures ``SIMULATOR_SPEC.md`` §11 item 1 records as the reason the ramp feature exists, and
it belongs to the **card**. Two hops that both touch the card consume **one** limit.
"""

CARD_CAP = 100_000.0
"""The declared monthly limit on that rail. Invented, like every number here."""

MIRROR = "mirror_exchange"
"""A second exchange declaring the *same terms* as the first.

It exists so a hand-declared end-to-end route can cost exactly what the chain through
:data:`EXCHANGE` costs while being a genuinely different journey -- same premium, same fees,
different venue in the middle. That is a **tie**, not a duplicate: FR-009 suppresses a
concatenation identical leg for leg, and two chains over different venues are two candidates
however closely their numbers agree.
"""

HOME = "home"
"""The one venue the owner spends from. An exit chain has to reach here to complete a round
trip (FR-022)."""

BROKER_USD = Destination(venue_id=BROKER, currency=USD)
EXCHANGE_USD = Destination(venue_id=EXCHANGE, currency=USD)
HOME_UAH = Destination(venue_id=HOME, currency=UAH)

SPENDABLE: frozenset[SpendableEndpoint] = frozenset(
    {SpendableEndpoint(venue_id=HOME, currency=UAH)}
)
"""Where money counts as having come back out. Hryvnia at the home rail and nowhere else --
dollars at a broker are not spent, they are held."""

SALARY = IncomeStream(
    id="salary_uah",
    owner_id=OWNER_ID,
    amount=Money(0.0, UAH, prov.EMPTY),
    cadence="monthly",
    arrives_at=SALARY_VENUE,
    indexation=Indexation(policy="cpi", rate=None),
    income_tax_rate=None,
)
"""The hryvnia salary. ``amount`` is zero and ``income_tax_rate`` is ``None`` because both are
honestly unstated: nothing in composition or costing reads either -- the amount to move is passed
explicitly -- and a fixture that invented them would be inventing numbers nothing needs."""

STREAMS: Mapping[str, IncomeStream] = {SALARY.id: SALARY}

VENUES: Mapping[str, Venue] = {
    SALARY_VENUE: Venue(
        id=SALARY_VENUE, name="Salary rail (SYNTHETIC)", currencies=frozenset({UAH})
    ),
    EXCHANGE: Venue(id=EXCHANGE, name="Exchange (SYNTHETIC)", currencies=frozenset({UAH, USD})),
    BROKER: Venue(id=BROKER, name="Broker (SYNTHETIC)", currencies=frozenset({USD})),
    MIRROR: Venue(id=MIRROR, name="Mirror exchange (SYNTHETIC)", currencies=frozenset({UAH, USD})),
    WALLET: Venue(id=WALLET, name="Wallet (SYNTHETIC)", currencies=frozenset({UAH})),
    FUND: Venue(id=FUND, name="Fund platform (SYNTHETIC)", currencies=frozenset({UAH})),
    HOME: Venue(id=HOME, name="Home rail (SYNTHETIC)", currencies=frozenset({UAH})),
}

BOUND = SegmentBound(max_segments=3)
"""Enough to reach every corridor these registries declare, and small enough that the
bound-respecting property has something to bind on."""


def channel(
    *,
    reference: float = REFERENCE,
    buy_premium: float = BUY_PREMIUM,
    sell_premium: float = SELL_PREMIUM,
    channel_id: str = CHANNEL_ID,
    kind: str = P2P_PREMIUM.id,
) -> FxChannel:
    """One two-sided quote for :data:`PAIR`, in the premium form."""
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


CHANNELS: Mapping[str, FxChannel] = {CHANNEL_ID: channel()}


def leg(
    *,
    index: int,
    from_venue: str,
    to_venue: str,
    from_ccy: Currency,
    to_ccy: Currency,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
    minimum: float | None = None,
    maximum: float | None = None,
    monthly_cap: float | None = None,
    pool: str | None = None,
    latency_days: int = 0,
    window: tuple[date | None, date | None] = (None, None),
    disruption: float = 0.0,
    channel_id: str = CHANNEL_ID,
    observation: str | None = None,
    sources: Provenance | None = None,
) -> Leg:
    """One declared movement. ``fx`` when the currencies differ, a plain transfer otherwise.

    The kind is derived from the currencies rather than passed, because a leg that changes
    currency without naming a channel is a declaration the loader refuses, and a fixture that
    could express one would be modelling a file that cannot exist.
    """
    converts = from_ccy is not to_ccy
    return Leg(
        index=index,
        kind=FX if converts else TRANSFER,
        from_venue=from_venue,
        to_venue=to_venue,
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=channel_id if converts else None,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, from_ccy, FEE_SOURCES),
        minimum=None if minimum is None else Money(minimum, from_ccy, FEE_SOURCES),
        maximum=None if maximum is None else Money(maximum, from_ccy, FEE_SOURCES),
        monthly_cap=None if monthly_cap is None else Money(monthly_cap, from_ccy, FEE_SOURCES),
        capacity_pool=pool,
        latency_days=latency_days,
        available_from=window[0],
        available_until=window[1],
        disruption_probability=disruption,
        kind_of_observation=(
            observation
            if observation is not None
            else (P2P_PREMIUM.id if converts else BANK_FEE_SCHEDULE.id)
        ),
        provenance=FEE_SOURCES if sources is None else sources,
    )


def corridor(
    route_id: str,
    *,
    direction: RouteDirection,
    legs: tuple[Leg, ...],
    partner_route: str | None = None,
    status: RouteStatus = "open",
    provider: str | None = None,
) -> Route:
    """One declared route over a chain of legs, with its endpoints read off the legs.

    Endpoints derived rather than passed, so a fixture cannot declare a route whose origin
    disagrees with its first leg -- the resolver refuses such a file, and a builder that could
    produce one would be testing a registry that cannot exist.
    """
    return Route(
        id=route_id,
        provider=provider if provider is not None else f"Synthetic {route_id}",
        origin=legs[0].from_venue,
        destination=legs[-1].to_venue,
        direction=direction,
        partner_route=partner_route,
        status=status,
        # Every leg cites **this corridor's** fee schedule unless it named its own, so a figure
        # derived from two segments carries two ids and a dropped mark is visible as a missing
        # one. See :func:`fee_source`.
        legs=tuple(
            leg
            if leg.provenance is not FEE_SOURCES
            else replace(leg, provenance=fee_source(route_id))
            for leg in legs
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Registry:
    """One hand-built world: what to search, what to cost it with, and where money is spent."""

    routes: Mapping[str, Route]
    channels: Mapping[str, FxChannel]
    streams: Mapping[str, IncomeStream]
    venues: Mapping[str, Venue]
    spendable: frozenset[SpendableEndpoint]
    kinds: Mapping[str, ObservationKind]


def registry(
    *routes: Route,
    channels: Mapping[str, FxChannel] | None = None,
    streams: Mapping[str, IncomeStream] | None = None,
    spendable: frozenset[SpendableEndpoint] | None = None,
) -> Registry:
    """A registry over the named routes, refusing a duplicate id the way the resolver does.

    The three overridable pieces are the ones a case genuinely varies: a second channel, a
    second stream, a different definition of where money counts as spent. Everything else is
    shared, because a fixture that could vary it would be nine worlds rather than one.
    """
    keyed: dict[str, Route] = {}
    for route in routes:
        if route.id in keyed:
            raise AssertionError(f"fixture declares route {route.id!r} twice")
        keyed[route.id] = route
    return Registry(
        routes=keyed,
        channels=CHANNELS if channels is None else channels,
        streams=STREAMS if streams is None else streams,
        venues=VENUES,
        spendable=SPENDABLE if spendable is None else spendable,
        kinds=KINDS,
    )


def reordered(source: Registry) -> Registry:
    """The same registry with its routes declared in the opposite order.

    SC-003's whole apparatus. Python dictionaries preserve insertion order, so reversing it is
    exactly the perturbation a search that trusted iteration order would show up under -- and
    nothing else about the world changes, which is what makes the comparison a controlled one.
    """
    return replace(source, routes=dict(reversed(list(source.routes.items()))))


# ---------------------------------------------------------------------------
# The corridor the feature exists for: salary -> exchange -> broker
# ---------------------------------------------------------------------------

SALARY_TO_EXCHANGE = corridor(
    "in_salary_to_exchange",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=EXCHANGE,
            from_ccy=UAH,
            to_ccy=USD,
            latency_days=1,
            disruption=0.05,
        ),
    ),
)
"""Hryvnia into dollars at the exchange. One conversion, no fees, so every hryvnia it costs is
the P2P spread and nothing else."""

EXCHANGE_TO_BROKER = corridor(
    "in_exchange_to_broker",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=EXCHANGE,
            to_venue=BROKER,
            from_ccy=USD,
            to_ccy=USD,
            fee_pct=0.01,
            fee_fixed=1.0,
            latency_days=2,
            disruption=0.02,
        ),
    ),
)
"""Dollars from the exchange to the broker. 1% and a flat dollar, so both fee components are
non-zero on the composed candidate and neither can hide behind the other."""

BROKER_TO_EXCHANGE = corridor(
    "out_broker_to_exchange",
    direction="exit",
    legs=(
        leg(
            index=0,
            from_venue=BROKER,
            to_venue=EXCHANGE,
            from_ccy=USD,
            to_ccy=USD,
            fee_fixed=2.0,
            latency_days=2,
        ),
    ),
)
"""The first half of the way out. Declared in its own right and **not** a reversal of the way
in: its flat fee is 2 dollars against the way in's 1, which is what a real corridor looks like
and what a reversal would have got wrong."""

EXCHANGE_TO_HOME = corridor(
    "out_exchange_to_home",
    direction="exit",
    legs=(
        leg(
            index=0,
            from_venue=EXCHANGE,
            to_venue=HOME,
            from_ccy=USD,
            to_ccy=UAH,
            latency_days=1,
        ),
    ),
)
"""The second half: dollars back into spendable hryvnia at the sell price. Where the composed
exit chain ends, because :data:`HOME` is the one declared spendable endpoint."""


def two_hop() -> Registry:
    """The feature's own case: a broker reachable only by chaining, and out again by chaining.

    Four declared routes, two in and two out, and **no** end-to-end declaration in either
    direction. Everything the worked examples assert is arithmetic over these four.
    """
    return registry(SALARY_TO_EXCHANGE, EXCHANGE_TO_BROKER, BROKER_TO_EXCHANGE, EXCHANGE_TO_HOME)


SALARY_TO_BROKER_VIA_MIRROR = corridor(
    "in_salary_to_broker_via_mirror",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=MIRROR,
            from_ccy=UAH,
            to_ccy=USD,
            latency_days=1,
            disruption=0.05,
        ),
        leg(
            index=1,
            from_venue=MIRROR,
            to_venue=BROKER,
            from_ccy=USD,
            to_ccy=USD,
            fee_pct=0.01,
            fee_fixed=1.0,
            latency_days=2,
            disruption=0.02,
        ),
    ),
    partner_route=BROKER_TO_EXCHANGE.id,
)
"""A hand-declared end-to-end route whose numbers match the chain's exactly.

Same premium, same 1% and flat dollar, same latencies -- and a **different venue in the
middle**, so its legs differ and FR-009 leaves both candidates standing. The two therefore cost
the same within the project tolerance and are a tie, which is the shape SC-003 is about: a tie
is reported as a tie and never resolved in favour of whichever the search found first.
"""

SALARY_TO_BROKER_SAME_LEGS = corridor(
    "in_salary_to_broker_declared",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=EXCHANGE,
            from_ccy=UAH,
            to_ccy=USD,
            latency_days=1,
            disruption=0.05,
        ),
        leg(
            index=1,
            from_venue=EXCHANGE,
            to_venue=BROKER,
            from_ccy=USD,
            to_ccy=USD,
            fee_pct=0.01,
            fee_fixed=1.0,
            latency_days=2,
            disruption=0.02,
        ),
    ),
    partner_route=BROKER_TO_EXCHANGE.id,
)
"""The chain's **exact segment-wise equivalent**, declared end to end by hand.

Leg for leg identical to concatenating ``in_salary_to_exchange`` with
``in_exchange_to_broker`` -- same venues, same currencies, same fees, same latencies. It is the
same real-world sequence of movements, so a ranking holds it **once**, as the declared route
(FR-009). The trap SC-013 exists to catch is that ``Leg.index`` is per route, so the
concatenation numbers its legs ``0, 0`` where this route numbers them ``0, 1``: compared
naively they never match and the duplicate survives.
"""


def tied() -> Registry:
    """The two-hop corridor plus a hand-declared equivalent over a different middle venue."""
    return registry(
        SALARY_TO_EXCHANGE,
        EXCHANGE_TO_BROKER,
        SALARY_TO_BROKER_VIA_MIRROR,
        BROKER_TO_EXCHANGE,
        EXCHANGE_TO_HOME,
    )


def duplicated() -> Registry:
    """The two-hop corridor plus a hand-declared route with the identical leg chain."""
    return registry(
        SALARY_TO_EXCHANGE,
        EXCHANGE_TO_BROKER,
        SALARY_TO_BROKER_SAME_LEGS,
        BROKER_TO_EXCHANGE,
        EXCHANGE_TO_HOME,
    )


FUND_UAH = Destination(venue_id=FUND, currency=UAH)

SALARY_TO_WALLET = corridor(
    "in_salary_to_wallet",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=WALLET,
            from_ccy=UAH,
            to_ccy=UAH,
            monthly_cap=CARD_CAP,
            pool=CARD_POOL,
        ),
    ),
)

WALLET_TO_FUND = corridor(
    "in_wallet_to_fund",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=WALLET,
            to_venue=FUND,
            from_ccy=UAH,
            to_ccy=UAH,
            monthly_cap=CARD_CAP,
            pool=CARD_POOL,
        ),
    ),
)


def pooled() -> Registry:
    """Two hops that both run over the owner's card, declaring the **same** limit on it.

    The shape SC-007 is about: one rail, two segments, one monthly headroom. Both legs declare
    the same cap because two legs naming one pool must -- two numbers for one real limit means
    at least one is wrong, and choosing either would be a guess (002 research.md D10).
    """
    return registry(SALARY_TO_WALLET, WALLET_TO_FUND)


SALARY_TO_HOME = corridor(
    "in_salary_to_home",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=HOME,
            from_ccy=UAH,
            to_ccy=UAH,
            fee_pct=0.005,
        ),
    ),
)
"""A way in that lands on the **spendable endpoint itself**, declaring no partner route.

The shape feature 003's FR-002 is about and the one `features.toml` recorded as
`identity-exit-vs-partner-requirement`: coverage calls the pair ready by identity -- the money
is already where it can be spent -- while 002's costing, which required a declared partner,
refused it with `ExitCostUnknown`. Declaring **no** ``partner_route`` here is deliberate: it is
what makes the two views disagree, and therefore what the sentinel has to reconcile.
"""


def stranded() -> Registry:
    """The two-hop corridor with the last exit segment missing.

    From the broker, ``out_broker_to_exchange`` runs to the exchange and stops -- and dollars at
    an exchange are not spendable. So no chain of declared exit segments reaches a spendable
    endpoint, 002 FR-030 stands unchanged, and the destination has no round-trip figure at all.
    """
    return registry(SALARY_TO_EXCHANGE, EXCHANGE_TO_BROKER, BROKER_TO_EXCHANGE)


def spendable_destination() -> Registry:
    """A way in that lands where the owner spends, with nothing declared to come back out."""
    return registry(SALARY_TO_HOME)


HOME_TO_WALLET = corridor(
    "out_home_to_wallet",
    direction="exit",
    legs=(
        leg(
            index=0,
            from_venue=HOME,
            to_venue=WALLET,
            from_ccy=UAH,
            to_ccy=UAH,
            fee_pct=0.05,
        ),
    ),
)
"""A declared way out **of** the spendable endpoint, charging ten times the way in.

The fee is deliberately large: it exists so that "identity supersedes a declared partner" is a
claim with a visible consequence rather than a preference between two figures that agree. Where
the two rules disagree they disagree by a factor of ten, so a test can tell which one ran.
"""

SALARY_TO_HOME_PARTNERED = corridor(
    "in_salary_to_home_partnered",
    direction="inbound",
    legs=(
        leg(
            index=0,
            from_venue=SALARY_VENUE,
            to_venue=HOME,
            from_ccy=UAH,
            to_ccy=UAH,
            fee_pct=0.005,
        ),
    ),
    partner_route=HOME_TO_WALLET.id,
)
"""A way in that lands on the spendable endpoint **and** names a declared way out of it.

The one registry where 003's identity rule and 002's partner rule both apply and disagree. It is
the shape ``superseded-exit-visibility`` is about, and until it existed the branch order in
``_exit_chain_of`` could be swapped without any test noticing.
"""


def spendable_destination_with_partner() -> Registry:
    """A spendable destination that also declares an exit, and a second spendable rail.

    Two endpoints, because the partner has to *land* somewhere spendable for the comparison to
    be between two figures rather than between a figure and a refusal: it leaves the home rail
    and reaches the wallet, and the owner spends from both.
    """
    return registry(
        SALARY_TO_HOME_PARTNERED,
        HOME_TO_WALLET,
        spendable=frozenset(
            {
                SpendableEndpoint(venue_id=HOME, currency=UAH),
                SpendableEndpoint(venue_id=WALLET, currency=UAH),
            }
        ),
    )
