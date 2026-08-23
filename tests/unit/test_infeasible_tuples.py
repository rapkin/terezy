"""SC-010: below the minimum, fees over the amount, and a remainder -- each reported honestly.

Three shapes of "this does not work", and the failure mode they share is the flattering one:
rounding the amount up to the minimum spends money the owner did not agree to spend, rounding
it down reports a return on a holding that was never bought, and clamping a negative arriving
amount to zero makes money vanish with no diagnostic -- which is the predecessor's B13 defect
in a new hat.

Nothing here is clamped, rounded or dropped. Every case names the constraint that bound, and
the refusals carry **which way in delivered the amount they are refusing**: "1 000 short" says
nothing until a reader knows which stream and which route produced what arrived, and the same
purchase is feasible from one and infeasible from another.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.tuple import (
    BelowMinimumTicket,
    BuysNoWholeUnit,
    InstrumentRefused,
    Tuple,
    TupleOutcome,
)
from tests import tuple_registries as fixtures

UAH: Final = fixtures.UAH
FLAT_FEE_ROUTE: Final = "test_flat_fee_in"


def _registries(*, flat: float = 0.0) -> Registries:
    return fixtures.with_new_route(
        fixtures.shipped(),
        fixtures.route(
            FLAT_FEE_ROUTE,
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
            partner=fixtures.DOMESTIC_OUT,
            fee_fixed=flat,
        ),
    )


def _via_flat_fee() -> Tuple:
    return replace(
        fixtures.hurdle_tuple(),
        route_in=fixtures.FundingPath(
            destination_id="inzhur", stream_id=fixtures.SALARY, route_id=FLAT_FEE_ROUTE
        ),
    )


def _evaluate(
    registries: Registries,
    candidate: Tuple,
    amount: float,
    instrument_id: str | None = None,
    horizon: fixtures.DateRange | None = None,
) -> object:
    return evaluate(
        candidate if instrument_id is None else replace(candidate, instrument_id=instrument_id),
        amount=Money(amount, UAH, prov.EMPTY),
        horizon=horizon or fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )


class TestAnAmountBelowTheMinimumTicket:
    """FR-017: infeasible for this amount, with the minimum and the shortfall named."""

    def test_it_is_refused_with_the_arithmetic_on_the_record(self) -> None:
        #   issue A requires 1 000.00; 900.00 arrives over a route that charges nothing.
        #   shortfall = 1 000 - 900 = 100.00
        refusal = _evaluate(_registries(), fixtures.hurdle_tuple(), 900.0)
        assert isinstance(refusal, BelowMinimumTicket), refusal
        assert_money_close(refusal.required, Money(1_000.0, UAH, prov.EMPTY))
        assert_money_close(refusal.actual, Money(900.0, UAH, prov.EMPTY))
        assert_money_close(refusal.shortfall, Money(100.0, UAH, prov.EMPTY))

    def test_it_names_the_way_in_that_delivered_the_amount(self) -> None:
        refusal = _evaluate(_registries(), fixtures.hurdle_tuple(), 900.0)
        assert isinstance(refusal, BelowMinimumTicket)
        assert refusal.path == fixtures.hurdle_tuple().route_in

    def test_nothing_is_rounded_up_to_fit(self) -> None:
        # The whole point. An engine that rounded 900 up to the 1 000 minimum would produce a
        # complete, plausible outcome for a purchase the owner never made.
        assert not isinstance(
            _evaluate(_registries(), fixtures.hurdle_tuple(), 900.0), TupleOutcome
        )


class TestFeesExceedingTheAmount:
    """B13, extended through the join: the money does not vanish and the diagnostic says so."""

    def test_a_flat_fee_larger_than_the_transfer_leaves_a_negative_arriving_amount(
        self,
    ) -> None:
        #   1 000.00 sent, 2 000.00 flat fee -> -1 000.00 arrives.
        # Reported as it stands. `max(gross - fee, 0)` is what made money disappear with no
        # diagnostic in the predecessor, and a zero here would read as "the transfer was free
        # and bought nothing".
        refusal = _evaluate(_registries(flat=2_000.0), _via_flat_fee(), 1_000.0)
        assert isinstance(refusal, BelowMinimumTicket), refusal
        assert_money_close(refusal.actual, Money(-1_000.0, UAH, prov.EMPTY))
        assert_money_close(refusal.shortfall, Money(2_000.0, UAH, prov.EMPTY))

    def test_the_reason_says_the_fees_exceeded_the_amount(self) -> None:
        # Not merely a shortfall: a reader seeing "1 000 short of the minimum" would look for
        # more money to send, when what actually happened is that this route cannot carry this
        # amount at all.
        refusal = _evaluate(_registries(flat=2_000.0), _via_flat_fee(), 1_000.0)
        assert isinstance(refusal, BelowMinimumTicket)
        assert "fees exceeded" in refusal.reason


class TestARemainderTheIncrementCannotDeploy:
    """FR-003: undeployed cash is reported with its amount and its location."""

    def test_fifteen_hundred_buys_one_unit_and_leaves_five_hundred(self) -> None:
        #   floor(1 500 / 1 000) = 1 unit at 1 000.00, remainder 500.00 sitting at `inzhur`.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome), outcome
        undeployed = outcome.undeployed
        assert undeployed is not None
        assert_money_close(undeployed.amount, Money(500.0, UAH, prov.EMPTY))
        assert undeployed.venue_id == "inzhur"

    def test_the_remainder_is_not_in_the_amount_that_reaches_the_endpoint(self) -> None:
        # It is money that made the trip and bought nothing, and it is still at the venue.
        # Sweeping it into `reaches` would report it as having come home.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome)
        one_unit = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_000.0)
        assert isinstance(one_unit, TupleOutcome)
        assert is_close(outcome.reaches.amount, one_unit.reaches.amount)

    def test_the_remainder_moves_the_rate_by_nothing(self) -> None:
        # **Two rates, compared** -- because the interesting question about a remainder is not
        # whether the word appears in a scope statement, it is what the figure does.
        #
        # 1 500.00 and 1 000.00 over a route that charges nothing both buy exactly one unit of
        # issue A at 1 000.00, so both holdings are the same holding and both return the same
        # arrivals on the same dates. The rate is therefore identical, and it is identical
        # because the 500.00 sitting at `inzhur` is netted off the outlay rather than
        # discounted as a loss: charging it as one makes these two figures 23 percentage
        # points apart and reports a 16% sovereign bond at -7%.
        remainder = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        exact = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_000.0)
        assert isinstance(remainder, TupleOutcome)
        assert isinstance(exact, TupleOutcome)
        assert remainder.undeployed is not None
        assert exact.undeployed is None
        stranded, deployed = remainder.implied_rate, exact.implied_rate
        assert isinstance(stranded, NominalRate)
        assert isinstance(deployed, NominalRate)
        assert is_close(stranded.value, deployed.value)
        assert stranded.value > 0.15

    def test_the_assumption_the_netting_makes_is_on_the_outcomes_face(self) -> None:
        # Netting the remainder off the outlay assumes it is recoverable at par, and it is
        # not: it sits behind the same exit the holding does. The assumption is stated rather
        # than buried, which is the only thing that makes the netting honest.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome)
        clause = next(item for item in outcome.excludes if "undeployed" in item)
        assert "money actually invested" in clause
        assert "what getting it back would cost" in clause

    def test_an_exact_multiple_leaves_no_remainder_at_all(self) -> None:
        # `None` rather than a zero, because "there was nothing left over" and "the leftover
        # was zero" are the same fact and one place is enough for it. This is also the guard
        # against a floating-point floor throwing away a whole unit: 10 000 / 1 000 must be
        # ten units, not nine and a remainder of 999.999...
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 10_000.0)
        assert isinstance(outcome, TupleOutcome), outcome
        assert outcome.undeployed is None


class TestAnAmountThatWillNotBuyOneIncrement:
    """A different constraint from the ticket, and it names a different figure."""

    def test_a_unit_dearer_than_what_arrived_is_its_own_refusal(self) -> None:
        # The minimum ticket is 1 000.00 and 10 000.00 arrived, so the ticket does not bind at
        # all -- and the purchase is still impossible, because one unit costs 20 000.00.
        # Reporting this as "below the minimum ticket" would be false.
        registries = fixtures.with_access(
            _registries(),
            fixtures.OVDP,
            quote=fixtures.quote(20_000.0),
        )
        refusal = _evaluate(registries, fixtures.hurdle_tuple(), 10_000.0)
        assert isinstance(refusal, BuysNoWholeUnit), refusal
        assert_money_close(refusal.price_per_unit, Money(20_000.0, UAH, prov.EMPTY))
        assert refusal.min_unit == 1.0
        assert_money_close(refusal.actual, Money(10_000.0, UAH, prov.EMPTY))

    def test_a_purchase_the_increment_shrinks_below_the_ticket_is_the_instruments_refusal(
        self,
    ) -> None:
        # Issue B requires 5 000.00 a purchase. At a quote of 1 200.00 a unit, 5 500.00 buys
        # four units for 4 800.00 -- past this module's own check, and refused by the
        # instrument that owns the constraint, with its own shortfall. Two refusals for two
        # genuinely different facts: what arrived, and what was spent.
        registries = fixtures.with_access(
            _registries(), "ovdp_synthetic_b", quote=fixtures.quote(1_200.0)
        )
        refusal = _evaluate(
            registries,
            fixtures.hurdle_tuple(),
            5_500.0,
            instrument_id="ovdp_synthetic_b",
            # Issue B is issued 2026-03-02, and a holding bought at issue is refused for a
            # different reason entirely: its first coupon falls before the earliest entry the
            # exemption's citation reaches. Buying in July steps past that, so the constraint
            # this test is about is the one that binds.
            horizon=fixtures.DateRange(start=date(2026, 7, 2), end=date(2029, 6, 30)),
        )
        assert isinstance(refusal, InstrumentRefused), refusal
        assert "min_ticket" in refusal.reason or "5000.0" in refusal.reason
