"""Small hand-built registries for the coverage suites, on the ``tests/synthetic.py`` pattern.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run. It exists for the reason ``synthetic.py`` gives: the failure cases, the regime cases and
the extensibility cases care about *the shape of a registry* rather than about any particular
corridor, and duplicating five venue declarations into each of them would mean five places to
edit when a record gains a field.

**The worked example does not use these builders**, deliberately. A hand-enumerated coverage
table that reached for a shared fixture would make a reader open two files to check one verdict,
which is exactly what a worked example exists to avoid -- so
``tests/worked_examples/test_coverage_table.py`` declares its own registry in its own file, and
these builders serve everything else.

**Every number here is invented and none of them is read.** Coverage is computed from
declarations alone: it looks at a route's direction, its endpoints, its status and the
currencies its first and last legs move, and at nothing else. The fees below are zero and the
provenance says SYNTHETIC in capitals, because a fixture that invented a plausible fee would be
inventing a number no assertion in this feature depends on.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.routes.legs import FX, TRANSFER, Leg, Route, RouteDirection, RouteStatus
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime
from terezy.core.streams.streams import IncomeStream, Indexation

UAH = Currency.UAH
USD = Currency.USD

OWNER_ID = "owner-001"
"""The one owner. Carried from the first commit while there is exactly one (Principle VII)."""

CHANNEL_ID = "p2p"
"""Named by every converting leg below. Coverage never resolves it -- it reads a leg's
currencies, not its rate -- but a converting leg with no channel is a declaration the loader
refuses, and a fixture that declared one would be modelling a file that cannot exist."""

SOURCE = SourceRef(
    id="synthetic:coverage-fixture",
    citation="SYNTHETIC FIXTURE -- invented corridor, no observed value. Not a real tariff.",
    retrieved_on=date(2026, 8, 1),
    verified_on=None,
)
SOURCES = prov.of([SOURCE])


def venue(venue_id: str, *currencies: Currency) -> Venue:
    """One venue and the currencies it declares it can hold.

    The currency set is what makes the destination universe: every venue times every currency
    it can hold (FR-001 ⚙), so a venue declared with two currencies contributes two
    destinations and two chances to be a hole.
    """
    return Venue(
        id=venue_id,
        name=f"{venue_id} (SYNTHETIC FIXTURE)",
        currencies=frozenset(currencies),
    )


def stream(stream_id: str, currency: Currency, arrives_at: str) -> IncomeStream:
    """One income stream: a currency, and the venue it lands at.

    ``amount`` is zero and ``income_tax_rate`` is ``None`` for the reason
    ``tests/invariants/route_graphs.py`` gives: both are honestly unstated, nothing in coverage
    reads either, and a fixture that invented them would be inventing numbers no assertion
    needs. What coverage *does* read is ``arrives_at`` and ``amount.currency`` -- the two
    together are what an inbound route has to match to carry this stream's money.
    """
    return IncomeStream(
        id=stream_id,
        owner_id=OWNER_ID,
        amount=Money(0.0, currency, prov.EMPTY),
        cadence="monthly",
        arrives_at=arrives_at,
        indexation=Indexation(policy="none", rate=None),
        credited_to=arrives_at,
        tax_scheme=None,
    )


def leg(
    index: int,
    *,
    from_venue: str,
    to_venue: str,
    from_ccy: Currency,
    to_ccy: Currency,
) -> Leg:
    """One movement, declaring nothing but its endpoints.

    ``fx`` exactly when the currencies differ, and a channel exactly on an ``fx`` leg -- the
    two rules the loader enforces, honoured here so a fixture never describes a file that
    would be refused at load.
    """
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
        fee_fixed=Money(0.0, from_ccy, SOURCES),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation="bank_fee_schedule",
        provenance=SOURCES,
    )


def route(
    route_id: str,
    *,
    origin: str,
    destination: str,
    direction: RouteDirection,
    from_ccy: Currency,
    to_ccy: Currency | None = None,
    status: RouteStatus = "open",
    partner_route: str | None = None,
) -> Route:
    """One declared corridor, as a single leg from one currency balance to another.

    One leg because coverage reads the **endpoints** of the chain and nothing between them
    (research.md D6): the first leg's ``from_ccy`` and the last leg's ``to_ccy``. A fixture
    with three legs would exercise the same branch and hide the rule behind arithmetic.

    ``direction`` is a required keyword. It is declared, never inferred (feature 002's FR-027),
    and it is the field that stops an exit being found by reading an inbound backwards -- so a
    builder that defaulted it would be the first step towards the composition FR-006 forbids.
    """
    ends_in = from_ccy if to_ccy is None else to_ccy
    return Route(
        id=route_id,
        provider=f"Synthetic {route_id}",
        origin=origin,
        destination=destination,
        direction=direction,
        partner_route=partner_route,
        status=status,
        legs=(leg(0, from_venue=origin, to_venue=destination, from_ccy=from_ccy, to_ccy=ends_in),),
    )


def spendable(*pairs: tuple[str, Currency]) -> frozenset[SpendableEndpoint]:
    """The declared spendable endpoints, as the core takes them."""
    return frozenset(
        SpendableEndpoint(venue_id=venue_id, currency=currency) for venue_id, currency in pairs
    )


def regime(regime_id: str, *route_ids: str) -> Regime:
    """One regime and the routes it believes in."""
    return Regime(id=regime_id, route_ids=frozenset(route_ids))


def keyed[T: Venue | IncomeStream | Route | Regime](records: Iterable[T]) -> Mapping[str, T]:
    """Records by id, which is how every core function takes them."""
    return {record.id: record for record in records}
