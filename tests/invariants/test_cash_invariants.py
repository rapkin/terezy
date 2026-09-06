"""What a zero-rate balance returns, over generated amounts, horizons and conventions.

023 SC-006, FR-010, FR-018 and FR-019. Two properties, and they are stated at two levels
because the class states **one** day-count convention (FR-010) and a run can therefore
exercise only that one:

* through :func:`~terezy.core.decision.tuple_outcome.evaluate`, over generated amounts and
  horizons, what reaches the endpoint is what left the stream and the implied rate is zero;
* over **every** convention in ``conventions.DAY_COUNT_FNS``, the series cash produces -- one
  outflow and one equal inflow -- has an internal rate of return of zero. That is why the
  class's choice decides nothing, asserted over the whole registry rather than claimed in a
  comment.

Both bounds are the imported project tolerance. The rate is bisected to a root, so an
exact-zero assertion would fail for a reason unrelated to the claim.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.instruments.access import InstrumentAccess
from terezy.core.instruments.cash import CashAssumptions, CashDeclaration
from terezy.core.instruments.interface import DateRange
from terezy.core.instruments.registry import CASH_BALANCE
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import DAY_COUNT_FNS, day_count
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.hurdle import CashFlow, internal_rate_of_return
from terezy.core.results.tuple import HOLD_AS_CASH, Tuple, TupleOutcome
from terezy.core.routes.path import ENTRY_BY_IDENTITY, EXIT_BY_IDENTITY
from terezy.core.scenarios.quotation import QuotationHolds
from terezy.core.streams.streams import IncomeStream, Indexation

pytestmark = pytest.mark.invariant

UAH: Final = Currency.UAH
VENUE: Final = "a_bank"
STREAM: Final = "a_salary"
CASH: Final = "a_balance"
KIND: Final = "a_kind"
AS_OF: Final = date(2026, 1, 1)
STARTS_ON: Final = date(2026, 1, 1)

UNVERIFIED: Final = prov.of(
    [
        prov.SourceRef(
            id=f"{CASH}:balance",
            citation="a fixture, standing where the owner's statement about his account stands",
            retrieved_on=AS_OF,
            verified_on=None,
            kind=KIND,
        )
    ]
)
"""`verified_on` empty, as the shipped declaration's is: every figure below renders marked."""


def _registries() -> Registries:
    """One balance at one venue the one stream already arrives at. No route anywhere."""
    return Registries(
        instruments={},
        funds={},
        cash={
            CASH: CashDeclaration(
                id=CASH,
                name="a hryvnia balance (fixture)",
                instrument_class=CASH_BALANCE,
                currency=UAH,
                is_synthetic=True,
                rate=0.0,
                rate_provenance=UNVERIFIED,
                groups=("cash",),
            )
        },
        tax_classes={},
        access={
            CASH: InstrumentAccess(
                instrument_id=CASH,
                bought_at=VENUE,
                proceeds_to=VENUE,
                quote=None,
                resale_price=None,
                risk_class="a_label",
            )
        },
        routes={},
        channels={},
        streams={
            STREAM: IncomeStream(
                id=STREAM,
                owner_id="owner-001",
                amount=Money(0.0, UAH, prov.EMPTY),
                cadence="monthly",
                arrives_at=VENUE,
                credited_to=VENUE,
                indexation=Indexation(policy="none", rate=None),
                tax_scheme=None,
            )
        },
        kinds={KIND: ObservationKind(id=KIND, staleness_days=365, note="a fixture")},
        spendable=frozenset({SpendableEndpoint(venue_id=VENUE, currency=UAH)}),
        quotation_holds=QuotationHolds(
            id="a_belief", is_assumption=True, rationale="a fixture, unread by a balance"
        ),
        base_currency=UAH,
    )


TUPLE: Final = Tuple(
    instrument_id=CASH,
    stream_id=STREAM,
    route_in=ENTRY_BY_IDENTITY,
    exit_terms=CashAssumptions(),
    route_out=EXIT_BY_IDENTITY,
)


@settings(max_examples=50, deadline=None)
@given(
    amount=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=1, max_value=4000),
)
def test_what_reaches_the_endpoint_is_what_left_the_stream(amount: float, days: int) -> None:
    """FR-018 and FR-011. No increment, so no fraction of any amount is ever stranded."""
    outlay = Money(amount, UAH, prov.EMPTY)
    outcome = evaluate(
        TUPLE,
        amount=outlay,
        horizon=DateRange(start=STARTS_ON, end=STARTS_ON + timedelta(days=days)),
        as_of=AS_OF,
        continuation=HOLD_AS_CASH,
        registries=_registries(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    assert is_close(outcome.reaches.amount, amount)
    assert outcome.undeployed is None


@settings(max_examples=50, deadline=None)
@given(
    amount=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=1, max_value=4000),
)
def test_the_implied_rate_is_zero_and_the_mark_survives(amount: float, days: int) -> None:
    """FR-019 and FR-004. A rate rather than `RateNotComparable`, and it carries the mark."""
    outcome = evaluate(
        TUPLE,
        amount=Money(amount, UAH, prov.EMPTY),
        horizon=DateRange(start=STARTS_ON, end=STARTS_ON + timedelta(days=days)),
        as_of=AS_OF,
        continuation=HOLD_AS_CASH,
        registries=_registries(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    assert isinstance(outcome.implied_rate, NominalRate), outcome.implied_rate
    assert is_close(outcome.implied_rate.value, 0.0)
    assert prov.is_unverified(outcome.provenance)


@pytest.mark.parametrize("convention", sorted(DAY_COUNT_FNS))
@settings(max_examples=25, deadline=None)
@given(
    amount=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=1, max_value=4000),
)
def test_no_declared_convention_can_move_a_zero_rate(
    convention: str, amount: float, days: int
) -> None:
    """SC-006. Why FR-010 lets the class state the convention and forbids a declaration one.

    The series is the one cash produces -- the whole amount out on the first day, the whole
    amount back on the last -- and the convention decides only *how long* that took. A root of
    zero is a root at every span, so requiring the declarer to state a convention would be
    asking for one that decides nothing.
    """
    span = day_count(convention)(STARTS_ON, STARTS_ON + timedelta(days=days))
    flows: list[CashFlow] = [(0.0, -amount), (span, amount)]
    assert is_close(internal_rate_of_return(flows), 0.0)
