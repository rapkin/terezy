"""Fixtures for the full-tuple suites: the shipped registry, and small deliberate edits to it.

Built from ``data/`` rather than by hand, and that is the point rather than a convenience. The
join's whole claim is that it composes declarations, so a suite that hand-built every record
would be testing a world the loader never validated -- and the seam tests below are only
interesting if the thing whose seam is broken is otherwise exactly what ships.

Each helper makes **one** deliberate change to that registry and says what it is breaking. A
fixture that changed two things at once would let a test pass for the other reason.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Final

from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments.access import InstrumentAccess
from terezy.core.instruments.fund import BuybackAvailability, ChosenPoint, LiquidityMode
from terezy.core.instruments.interface import Assumptions, DateRange
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.tuple import HOLD_AS_CASH, Tuple
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.path import (
    EXIT_BY_IDENTITY,
    FROM_THE_DECLARATION,
    DeclaredExit,
    ExitChoice,
    FundingPath,
)
from terezy.core.streams.streams import IncomeStream
from terezy.data.declarations import resolver

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DATA_ROOT: Final = REPO_ROOT / "data"

UAH: Final = Currency.UAH

__all__ = [
    "AMOUNT",
    "AS_OF",
    "DATA_ROOT",
    "DOMESTIC_IN",
    "DOMESTIC_OUT",
    "EXIT_BY_IDENTITY",
    "FROM_THE_DECLARATION",
    "HOLD_AS_CASH",
    "HOLD_TO_MATURITY",
    "HORIZON",
    "HORIZON_END",
    "ISSUE_DATE",
    "MILTECH",
    "MILTECH_EXIT",
    "MILTECH_POINT",
    "OUTLAY_ON",
    "OVDP",
    "REIT",
    "SALARY",
    "UAH",
    "ChosenPoint",
    "Currency",
    "DateRange",
    "DeclaredExit",
    "FundingPath",
    "Money",
    "Registries",
    "access",
    "date",
    "fund_tuple",
    "fx_route",
    "hurdle_tuple",
    "prov",
    "replace",
    "route",
    "shipped",
    "transfer_leg",
    "with_access",
    "with_leg",
    "with_new_route",
    "with_route",
    "with_stream",
    "without_access",
    "without_latency",
    "without_tax_class",
]
"""Re-exported so a suite imports one fixture module rather than eight core modules.

``Currency``, ``Money`` and ``prov`` are here for exactly that reason: a test that has to
reach past the fixtures for a currency member is a test whose imports say more about the core
than about what it is checking.
"""

ISSUE_DATE: Final = date(2026, 1, 15)
"""Issue A's declared issue date. A purchase before it is refused by the instrument itself."""

OUTLAY_ON: Final = date(2026, 1, 14)
"""When the money leaves the stream. One day before issue A's issue date, because the shipped
domestic route declares a one-day latency and the purchase must land on or after the issue."""

HORIZON_END: Final = date(2028, 3, 31)
"""Comfortably past issue A's adjusted final payment (2028-01-17) and its three-day exit."""

AS_OF: Final = date(2026, 8, 23)
"""When the question is asked. Never a clock: staleness is a verdict about an input date."""

HORIZON: Final = DateRange(start=OUTLAY_ON, end=HORIZON_END)

AMOUNT: Final = Money(10_000.0, UAH, prov.EMPTY)
"""Ten units of issue A at its declared par price of 1 000.00, so nothing is left undeployed."""

OVDP: Final = "ovdp_synthetic_a"
SALARY: Final = "salary_uah"
DOMESTIC_IN: Final = "inzhur_direct"
DOMESTIC_OUT: Final = "inzhur_to_monobank"

HOLD_TO_MATURITY: Final = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")
"""A bond's one declared way out, and the two owner choices a projection needs."""

MILTECH: Final = "inzhur_miltech"
REIT: Final = "inzhur_reit"

MILTECH_POINT: Final = ChosenPoint(
    rate=0.25,
    is_assumption=True,
    rationale="TEST FIXTURE -- the low end of the fund's own stated range, chosen so the "
    "figure is the least flattering one the range admits rather than a midpoint nobody stated.",
)
"""A point inside MilTech's declared 25-29% range. Without one a projection is two figures."""

MILTECH_EXIT: Final = date(2028, 1, 17)
"""When the MilTech holding is exited: the same date issue A's principal comes back, so the two
tuples are compared over one span as well as over one horizon."""


def shipped() -> Registries:
    """Every declaration under ``data/``, resolved and cross-checked, as the join takes them."""
    return resolver.tuple_from_data_root(DATA_ROOT, base_currency=UAH, scenario_id=None).registries


def hurdle_tuple(*, route_out: ExitChoice = FROM_THE_DECLARATION) -> Tuple:
    """The OVDP through its declared zero-cost domestic routes: the comparison's benchmark."""
    return Tuple(
        instrument_id=OVDP,
        stream_id=SALARY,
        route_in=FundingPath(destination_id="inzhur", stream_id=SALARY, route_id=DOMESTIC_IN),
        exit_terms=HOLD_TO_MATURITY,
        route_out=route_out,
    )


def fund_tuple(
    instrument_id: str,
    *,
    exit_on: date | None,
    stream_id: str = SALARY,
    yield_point: ChosenPoint | None = None,
    liquidity_mode: LiquidityMode = "practice",
    buyback: BuybackAvailability = "available",
) -> Tuple:
    """A fund bought through the same domestic route, exited on a stated date.

    ``liquidity_mode="practice"`` and ``buyback="available"`` are the assumptions under which
    an early exit happens at all: the регламент owes no buyback before termination, so the
    legal mode with no buyback on offer is a refusal rather than a figure -- which is what
    ``tests/unit/test_tuple_refusals.py`` exercises deliberately.
    """
    return Tuple(
        instrument_id=instrument_id,
        stream_id=stream_id,
        route_in=FundingPath(destination_id="inzhur", stream_id=stream_id, route_id=DOMESTIC_IN),
        exit_terms=FundAssumptions(
            liquidity_mode=liquidity_mode,
            buyback=buyback,
            exit_on=exit_on,
            yield_point=yield_point,
            exchange_rate=None,
            consumption_method="fifo",
        ),
        route_out=FROM_THE_DECLARATION,
    )


def without_latency(registries: Registries) -> Registries:
    """The same registry with every leg of the domestic pair declaring zero days.

    **Why a test declares this rather than the repository shipping it.** The shipped domestic
    route takes one day in and three days out, and those days are inside the span the
    comparable rate is measured over (FR-015): waiting is a cost. So the tuple's rate is a
    little below feature 001's contractual yield *by exactly that waiting*, and asserting
    equality against the shipped pair would need a tolerance loose enough to hide a real
    defect. Zeroing the latency isolates the one term that differs and lets SC-002 be asserted
    at the project tolerance -- see ``tests/contract/test_the_hurdle_is_a_tuple.py``.
    """
    return _with_routes(
        registries,
        {
            route_id: replace(
                registries.routes[route_id],
                legs=tuple(
                    replace(leg, latency_days=0) for leg in registries.routes[route_id].legs
                ),
            )
            for route_id in (DOMESTIC_IN, DOMESTIC_OUT)
        },
    )


def with_leg(registries: Registries, route_id: str, **changes: Any) -> Registries:
    """The same registry with one field changed on every leg of one declared route."""
    route = registries.routes[route_id]
    return _with_routes(
        registries,
        {route_id: replace(route, legs=tuple(replace(leg, **changes) for leg in route.legs))},
    )


def with_route(registries: Registries, route_id: str, **changes: Any) -> Registries:
    """The same registry with one field changed on one declared route."""
    return _with_routes(registries, {route_id: replace(registries.routes[route_id], **changes)})


def with_access(registries: Registries, instrument_id: str, **changes: Any) -> Registries:
    """The same registry with one field changed on one instrument's access declaration."""
    entry = registries.access[instrument_id]
    return replace(
        registries, access={**registries.access, instrument_id: replace(entry, **changes)}
    )


def without_access(registries: Registries, instrument_id: str) -> Registries:
    """The same registry with one instrument's access declaration removed entirely."""
    return replace(
        registries,
        access={key: value for key, value in registries.access.items() if key != instrument_id},
    )


def without_tax_class(registries: Registries, class_id: str) -> Registries:
    """The same registry with one declared tax class removed."""
    return replace(
        registries,
        tax_classes={
            key: value for key, value in registries.tax_classes.items() if key != class_id
        },
    )


def with_stream(registries: Registries, stream: IncomeStream) -> Registries:
    """The same registry with one more declared income stream."""
    return replace(registries, streams={**registries.streams, stream.id: stream})


def with_new_route(registries: Registries, route: Route) -> Registries:
    """The same registry with one more declared route."""
    return _with_routes(registries, {route.id: route})


def _with_routes(registries: Registries, routes: dict[str, Route]) -> Registries:
    return replace(registries, routes={**registries.routes, **routes})


def transfer_leg(
    *,
    from_venue: str,
    to_venue: str,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
    currency: Currency = UAH,
) -> Leg:
    """One transfer leg in one currency, priced by whatever the caller states. A test fixture.

    ``currency`` sets both ends **and the fixed fee**: a leg moving dollars whose flat fee is
    declared in hryvnia cannot be costed at all, which is `money`'s currency tag doing its job
    and not something a fixture should have to remember.
    """
    return Leg(
        index=0,
        kind="transfer",
        from_venue=from_venue,
        to_venue=to_venue,
        from_ccy=currency,
        to_ccy=currency,
        channel=None,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, currency, prov.EMPTY),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation="bank_fee_schedule",
        provenance=prov.EMPTY,
    )


def route(
    route_id: str,
    *,
    origin: str,
    destination: str,
    direction: str,
    partner: str | None = None,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
    status: str = "open",
    currency: Currency = UAH,
) -> Route:
    """One declared route of one hryvnia leg. A test fixture, priced by the caller."""
    return Route(
        id=route_id,
        provider="TEST FIXTURE",
        origin=origin,
        destination=destination,
        direction="exit" if direction == "exit" else "inbound",
        partner_route=partner,
        status="closed" if status == "closed" else "open",
        legs=(
            transfer_leg(
                from_venue=origin,
                to_venue=destination,
                fee_pct=fee_pct,
                fee_fixed=fee_fixed,
                currency=currency,
            ),
        ),
    )


def fx_route(route_id: str, *, origin: str, destination: str, channel: str = "p2p") -> Route:
    """One inbound route whose single leg converts dollars to hryvnia. A test fixture.

    The channel is a shipped declaration, so the rate this crosses at is a declared two-sided
    quote rather than anything a test invented.
    """
    return Route(
        id=route_id,
        provider="TEST FIXTURE",
        origin=origin,
        destination=destination,
        direction="inbound",
        partner_route=None,
        status="open",
        legs=(
            replace(
                transfer_leg(from_venue=origin, to_venue=destination, currency=Currency.USD),
                kind="fx",
                to_ccy=UAH,
                channel=channel,
                kind_of_observation="p2p_premium",
            ),
        ),
    )


def access(
    instrument_id: str, *, bought_at: str, proceeds_to: str, price: float | None
) -> InstrumentAccess:
    """One access declaration, built in code. A test fixture."""
    return InstrumentAccess(
        instrument_id=instrument_id,
        bought_at=bought_at,
        proceeds_to=proceeds_to,
        price_per_unit=None if price is None else Money(price, UAH, prov.EMPTY),
        risk_class="test_fixture",
    )
