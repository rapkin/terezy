"""SC-010 and FR-016: below the minimum, fees over the amount, a remainder, and the caps.

Five shapes of "this does not work" -- SC-010's three, the increment that binds where the
ticket does not, and the declared monthly ceiling **on both sides of the round trip** -- and
the failure mode they share is the flattering one:
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
from datetime import date, timedelta
from typing import Final

import pytest

from terezy.core.decision.tuple_outcome import Registries
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.tuple import (
    BelowMinimumTicket,
    BuysNoWholeUnit,
    InstrumentRefused,
    RateNotComparable,
    RemainderCameHome,
    RemainderStayed,
    RouteInCapExceeded,
    RouteInUnusable,
    SeamDoesNotChain,
    Tuple,
    TupleOutcome,
    WayOutCapExceeded,
    WayOutUnusable,
)
from terezy.core.routes.path import EXIT_BY_IDENTITY
from tests import tuple_registries as fixtures
from tests.outcomes import evaluated_outcome

UAH: Final = fixtures.UAH
FLAT_FEE_ROUTE: Final = "test_flat_fee_in"
SPENDABLE_VENUE: Final = "monobank_uah"
"""A declared spendable endpoint, so moving an instrument's proceeds there makes the way out
the identity exit."""

IN_LATENCY_DAYS: Final = 1
EXIT_LATENCY_DAYS: Final = 3
"""What `inzhur_direct` and `inzhur_to_monobank` declare."""


def _came_home(outcome: TupleOutcome) -> RemainderCameHome:
    undeployed = outcome.undeployed
    assert undeployed is not None
    assert isinstance(undeployed.journey, RemainderCameHome), undeployed.journey
    return undeployed.journey


def _rate_of(outcome: TupleOutcome) -> float:
    rate = outcome.implied_rate
    assert isinstance(rate, NominalRate), rate
    return rate.value


def _registries(*, flat: float = 0.0, out_route: str = fixtures.DOMESTIC_OUT) -> Registries:
    return fixtures.with_new_route(
        fixtures.declared(),
        fixtures.route(
            FLAT_FEE_ROUTE,
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
            partner=out_route,
            fee_fixed=flat,
        ),
    )


INSTANT_OUT: Final = "test_instant_out"
"""A way out declaring no latency at all, where the shipped `inzhur_to_monobank` declares
three days. Free either way, so the only difference between the two is the wait."""


def _registries_out_instantly(*, flat: float) -> Registries:
    return fixtures.with_new_route(
        _registries(flat=flat, out_route=INSTANT_OUT),
        fixtures.route(INSTANT_OUT, origin="inzhur", destination="monobank_uah", direction="exit"),
    )


AT_ISSUE = fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
"""The flat-fee route declares no latency, so a window opened on :data:`OUTLAY_ON` would buy
the day before issue A exists -- and a quotation cannot be carried to a date before the paper
was issued. Opened on the issue date, the purchase lands on the day the fixture quotations
were read and the carry is a no-op."""


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
    return evaluated_outcome(
        candidate if instrument_id is None else replace(candidate, instrument_id=instrument_id),
        amount=Money(amount, UAH, prov.EMPTY),
        horizon=horizon or fixtures.HORIZON,
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

    def test_the_remainder_comes_home_and_is_part_of_what_reaches_the_endpoint(self) -> None:
        # Owner decision 2026-09-06: it can be withdrawn from the broker, so it is, along the
        # tuple's own declared way out. The two purchases hold the same one unit and return
        # the same arrivals; what separates them is the 500.00 coming back.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome)
        one_unit = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_000.0)
        assert isinstance(one_unit, TupleOutcome)
        undeployed = outcome.undeployed
        assert undeployed is not None
        # `inzhur_to_monobank` charges nothing, so all 500.00 of it arrives -- and the
        # subtraction is against the record's own figure rather than against 500.00, so a
        # route that charged would still be checked here.
        assert_money_close(_came_home(outcome).reached, Money(500.0, UAH, prov.EMPTY))
        assert is_close(
            outcome.reaches.amount - one_unit.reaches.amount, _came_home(outcome).reached.amount
        )
        assert one_unit.undeployed is None

    def test_it_leaves_on_the_purchase_date_and_arrives_the_way_outs_latency_later(self) -> None:
        # It never became a position, so it waits for nothing: it leaves on the purchase
        # date, which is `inzhur_direct`'s one declared day after the outlay, and arrives
        # `inzhur_to_monobank`'s three declared days after that. Both are inside the span.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome)
        journey = _came_home(outcome)
        assert journey.left_on == fixtures.HORIZON.start + timedelta(days=IN_LATENCY_DAYS)
        assert journey.arrived_on == journey.left_on + timedelta(days=EXIT_LATENCY_DAYS)

    def _rate_over_flat_fee(self, flat: float, sent: float) -> float:
        """The rate of one purchase over a way in charging a flat fee and nothing else.

        A **flat** fee rather than a percentage: it keeps ``outlay`` and ``arrived`` different
        numbers -- which a free route does not, and which is what the tests below turn on --
        while leaving two amounts that buy the same units with the same money invested.
        """
        outcome = _evaluate(_registries(flat=flat), _via_flat_fee(), sent, horizon=AT_ISSUE)
        assert isinstance(outcome, TupleOutcome), outcome
        return _rate_of(outcome)

    def test_a_remainder_home_the_same_day_moves_the_rate_by_nothing(self) -> None:
        # **Two rates, compared**, and over a way in that *charges* -- because on a free route
        # the outlay and the arriving amount are the same number, and then "the remainder came
        # back" and "the remainder never left" cannot be told apart.
        #
        #   100.00 flat, 10 100.00 sent -> 10 000.00 arrives -> 10 units, nothing left over
        #   100.00 flat, 10 500.00 sent -> 10 400.00 arrives -> 10 units, 400.00 left over
        #
        # Both hold the same ten units of issue A and return the same arrivals on the same
        # dates. Over a way out that is free and instant the 400.00 is back on the purchase
        # date, so the series is 10 500.00 out and 400.00 straight back in -- arithmetically
        # the 10 100.00 of the other, and the rates are equal to the last bit. Charging the
        # remainder as a loss puts these two figures percentage points apart and reports a 16%
        # sovereign bond well below its coupon.
        registries = _registries_out_instantly(flat=100.0)
        exact = _evaluate(registries, _via_flat_fee(), 10_100.0, horizon=AT_ISSUE)
        remainder = _evaluate(registries, _via_flat_fee(), 10_500.0, horizon=AT_ISSUE)
        assert isinstance(exact, TupleOutcome), exact
        assert isinstance(remainder, TupleOutcome), remainder
        assert exact.undeployed is None
        assert remainder.undeployed is not None
        assert_money_close(remainder.undeployed.amount, Money(400.0, UAH, prov.EMPTY))
        assert _rate_of(remainder) == _rate_of(exact)

    def test_the_three_days_the_way_out_declares_are_what_separates_them(self) -> None:
        # The same pair over `inzhur_to_monobank`, which is free and takes three days. Waiting
        # is a cost (010 FR-015), so the outcome carrying a remainder now returns strictly
        # less -- and by three days of it on 400.00, which is basis points and not percent.
        # Ignoring the declared latency makes these two equal again.
        exact = self._rate_over_flat_fee(100.0, 10_100.0)
        remainder = self._rate_over_flat_fee(100.0, 10_500.0)
        assert remainder < exact
        assert exact - remainder < 0.001

    def test_the_denominator_is_the_outlay_and_not_what_arrived(self) -> None:
        # The discriminator, with no present-value arithmetic in it: two purchases whose
        # **arriving** amounts are identical and whose outlays are not.
        #
        #   100.00 flat, 10 100.00 sent -> 10 000.00 arrives -> 10 units
        #   500.00 flat, 10 500.00 sent -> 10 000.00 arrives -> 10 units
        #
        # Same holding, same arrivals, same dates. A rate measured on what arrived would
        # report one figure for both and hide a 400.00 fee completely; measured on what left
        # the stream, the dearer way in returns less, which is the sentence this project
        # exists to be able to write.
        cheap = self._rate_over_flat_fee(100.0, 10_100.0)
        dear = self._rate_over_flat_fee(500.0, 10_500.0)
        assert not is_close(cheap, dear)
        assert dear < cheap

    def test_the_outcome_no_longer_excludes_the_cost_of_recovering_the_remainder(self) -> None:
        # The scope statements are what a reader meets, so they move with the behaviour: this
        # remainder's journey home is priced, so `excludes` may no longer say it is not costed.
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 1_500.0)
        assert isinstance(outcome, TupleOutcome)
        undeployed = outcome.undeployed
        assert undeployed is not None
        assert isinstance(undeployed.journey, RemainderCameHome), undeployed.journey
        assert not [item for item in outcome.excludes if "undeployed" in item]

    def test_an_exact_multiple_leaves_no_remainder_at_all(self) -> None:
        # `None` rather than a zero, because "there was nothing left over" and "the leftover
        # was zero" are the same fact and one place is enough for it. This is also the guard
        # against a floating-point floor throwing away a whole unit: 10 000 / 1 000 must be
        # ten units, not nine and a remainder of 999.999...
        outcome = _evaluate(_registries(), fixtures.hurdle_tuple(), 10_000.0)
        assert isinstance(outcome, TupleOutcome), outcome
        assert outcome.undeployed is None


class TestARemainderTheDeclaredWayOutWillNotCarry:
    """The remainder is at the **purchase** venue and the way out departs from where the
    proceeds land, which are two declarations (FR-003a).

    The fixture moves one instrument's ``proceeds_to`` to a venue the owner already spends
    from, so the way out is the identity exit and there is nothing declared that carries cash
    from `inzhur` to it. That is the shape `tests/unit/test_identity_exit_candidate.py` builds
    for a different reason, and it is why this arm is a reported state rather than a branch
    nothing reaches.
    """

    def _outcome(self, amount: float) -> TupleOutcome:
        registries = fixtures.with_access(_registries(), fixtures.OVDP, proceeds_to=SPENDABLE_VENUE)
        candidate = replace(fixtures.hurdle_tuple(), route_out=EXIT_BY_IDENTITY)
        outcome = _evaluate(registries, candidate, amount)
        assert isinstance(outcome, TupleOutcome), outcome
        return outcome

    def test_the_tuple_is_reported_and_the_remainder_stays_where_it_was_left(self) -> None:
        # Not a refusal: the position came home perfectly well, and what is stranded is the
        # 500.00 of change. Refusing the whole tuple would throw away a complete answer.
        outcome = self._outcome(1_500.0)
        undeployed = outcome.undeployed
        assert undeployed is not None
        assert isinstance(undeployed.journey, RemainderStayed), undeployed.journey
        assert_money_close(undeployed.amount, Money(500.0, UAH, prov.EMPTY))
        assert undeployed.venue_id == "inzhur"
        assert "inzhur" in undeployed.journey.reason
        assert SPENDABLE_VENUE in undeployed.journey.reason

    def test_it_is_out_of_what_reaches_the_endpoint(self) -> None:
        # The same holding either way, so the 500.00 is the whole of the difference -- and
        # here there is none, because it never travelled.
        assert is_close(
            self._outcome(1_500.0).reaches.amount, self._outcome(1_000.0).reaches.amount
        )

    def test_the_rate_is_refused_rather_than_pricing_the_stranded_amount(self) -> None:
        # Principle I. On the whole outlay the 500.00 is priced at zero and this 16% bond
        # reports -7.11%; netted off the outlay it is priced at par. Nothing declares which
        # stranded cash is worth, and both figures read as a rate -- so there is no figure.
        # The exact multiple beside it strands nothing and keeps its rate, which is what says
        # the refusal is about the remainder and not about the fixture.
        refused = self._outcome(1_500.0).implied_rate
        assert isinstance(refused, RateNotComparable), refused
        assert "500.0" in refused.reason
        assert "never came home" in refused.reason
        assert isinstance(self._outcome(1_000.0).implied_rate, NominalRate)


class TestTheWayOutRefusesTheRemainderAndCarriesEveryRelease:
    """The other two ways a remainder stays put, and both need the way out to refuse **it**
    while carrying everything the holding released -- which is what makes them different
    findings from the refusals `_repatriate` raises one step earlier.
    """

    def test_a_leg_minimum_above_the_remainder_and_below_every_release(self) -> None:
        # 100.00 flat, 10 500.00 sent -> 10 400.00 arrives -> 10 units, 400.00 over. A 500.00
        # minimum on the way out carries the 775.00 coupons and the 10 775.00 redemption and
        # will not carry the 400.00 -- the "a fixed minimum makes small movements
        # unrepatriable" case `WayOutUnusable` names, arriving at the remainder instead.
        registries = fixtures.with_leg(
            _registries(flat=100.0), fixtures.DOMESTIC_OUT, minimum=Money(500.0, UAH, prov.EMPTY)
        )
        outcome = _evaluate(registries, _via_flat_fee(), 10_500.0, horizon=AT_ISSUE)
        assert isinstance(outcome, TupleOutcome), outcome
        undeployed = outcome.undeployed
        assert undeployed is not None
        assert isinstance(undeployed.journey, RemainderStayed), undeployed.journey
        assert_money_close(undeployed.amount, Money(400.0, UAH, prov.EMPTY))
        assert "leg" in undeployed.journey.reason
        assert outcome.arrivals, "every release still came home"
        assert isinstance(outcome.implied_rate, RateNotComparable)

    def test_a_monthly_ceiling_the_remainder_alone_is_over(self) -> None:
        # A remainder is smaller than every release on a bond quoted at par, so reaching this
        # needs a unit dearer than what it repays: quoted at 1 500.00 against a 1 000.00 face,
        # 2 900.00 buys one unit and strands 1 400.00 while the redemption is 1 000.00. A
        # 1 200.00 ceiling then carries every release and refuses the change.
        registries = fixtures.with_leg(
            fixtures.with_access(_registries(), fixtures.OVDP, quote=fixtures.quote(1_500.0)),
            fixtures.DOMESTIC_OUT,
            monthly_cap=Money(1_200.0, UAH, prov.EMPTY),
        )
        outcome = _evaluate(registries, fixtures.hurdle_tuple(), 2_900.0)
        assert isinstance(outcome, TupleOutcome), outcome
        undeployed = outcome.undeployed
        assert undeployed is not None
        assert isinstance(undeployed.journey, RemainderStayed), undeployed.journey
        assert_money_close(undeployed.amount, Money(1_400.0, UAH, prov.EMPTY))
        assert "monthly ceiling of 1200.0" in undeployed.journey.reason
        assert "200.0 of the remainder is over it" in undeployed.journey.reason
        assert "The tuple is refused" not in undeployed.journey.reason, (
            "the tuple was not refused; the ceiling rule's own reason says it was, which is "
            "why that reason is not the one carried here"
        )


class TestADeclarationWithNoIncrementLeavesNoRemainderAtAll:
    """A fund's arriving amount buys exactly what it buys, so there is nothing left over.

    Not "a very small remainder": a remainder is what a **declared increment** leaves behind,
    and a declaration that names none has no such quantity. What ``price * (arrived / price)``
    leaves in binary floating point is not money -- and it shipped as money, at the shipped
    fund's own net asset value:

        undeployed.amount = -1.1368683772161603e-13 UAH
        reason: bought in increments of 0.0 unit(s) ...

    A **negative** "money that made the trip in and bought nothing" is a state the record
    forbids in its own words, and the rate then subtracted it and made the invested amount
    exceed the outlay. The sentence even quoted `0.0` as the increment, which is the sentinel
    for *no increment declared*.
    """

    def _fund_outcome(self, amount: float) -> TupleOutcome:
        outcome = evaluated_outcome(
            fixtures.fund_tuple(
                fixtures.MILTECH,
                exit_on=fixtures.MILTECH_EXIT,
                yield_point=fixtures.MILTECH_POINT,
            ),
            amount=Money(amount, UAH, prov.EMPTY),
            horizon=fixtures.HORIZON,
            as_of=fixtures.AS_OF,
            continuation=fixtures.HOLD_AS_CASH,
            registries=fixtures.declared(),
        )
        assert isinstance(outcome, TupleOutcome), outcome
        return outcome

    @pytest.mark.parametrize("amount", [1_007.0, 1_006.97, 5_000.0, 10_000.0, 33_333.33])
    def test_no_amount_leaves_a_residue(self, amount: float) -> None:
        # 1 007.00 against a net asset value of 1 006.97 is the case that shipped one.
        assert self._fund_outcome(amount).undeployed is None

    def test_the_rate_is_measured_on_the_whole_outlay(self) -> None:
        # The consequence, and the reason a residue was worse than untidy: `_rate` nets the
        # remainder off, so a negative one made the money invested exceed the money sent.
        outcome = self._fund_outcome(1_007.0)
        assert outcome.undeployed is None
        assert_money_close(outcome.outlay, Money(1_007.0, UAH, prov.EMPTY))


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
            _registries(),
            "ovdp_synthetic_b",
            quote=fixtures.quote(1_200.0, observed_on=date(2026, 7, 3)),
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


class TestTheDeclaredMonthlyCeilingAndThePerTransactionMaximum:
    """FR-016: two limits, two reasons, two refusals -- and the pair is the test.

    They are tested together because the defect they exist to prevent was found by comparing
    them and by nothing else. A ``leg.maximum`` of 5 000.00 against a 10 000.00 outlay refused;
    a ``leg.monthly_cap`` of 5 000.00 against the same outlay produced a **complete outcome**
    that bought ten units and reported 13 100.00 coming home. Nothing looked wrong: there was
    no refusal to read and no figure out of place. Either case alone still passes with the
    other broken, which is how the silent one survived a whole feature.
    """

    def _limited(self, **limit: Money) -> object:
        return _evaluate(
            fixtures.with_leg(fixtures.declared(), fixtures.DOMESTIC_IN, **limit),
            fixtures.hurdle_tuple(),
            10_000.0,
        )

    def test_a_monthly_ceiling_below_the_amount_refuses_naming_the_excess(self) -> None:
        #   ceiling 5 000.00, requested 10 000.00, excess 5 000.00
        refusal = self._limited(monthly_cap=Money(5_000.0, UAH, prov.EMPTY))
        assert isinstance(refusal, RouteInCapExceeded), refusal
        assert_money_close(refusal.ceiling, Money(5_000.0, UAH, prov.EMPTY))
        assert_money_close(refusal.requested, Money(10_000.0, UAH, prov.EMPTY))
        assert_money_close(refusal.excess, Money(5_000.0, UAH, prov.EMPTY))
        assert refusal.path == fixtures.hurdle_tuple().route_in

    def test_the_refusal_says_partial_deployment_is_deferred_and_when_that_was_decided(
        self,
    ) -> None:
        # The deferral belongs in the output a reader meets, not only in the specification:
        # "this refuses" without "and here is why nobody split it" reads as a missing feature
        # rather than as a decision somebody took on a date.
        refusal = self._limited(monthly_cap=Money(5_000.0, UAH, prov.EMPTY))
        assert isinstance(refusal, RouteInCapExceeded)
        assert "FR-018" in refusal.reason
        assert "2026-08-22" in refusal.reason

    def test_a_per_transaction_maximum_is_the_other_refusal_entirely(self) -> None:
        # 002's own, carried whole. A maximum says this route cannot carry this movement at
        # all; a monthly cap says this rail carries this much a month and the rest waits. The
        # remedies differ -- split the movement, or wait for the month -- so a reader who
        # could not tell them apart would be given the wrong advice.
        refusal = self._limited(maximum=Money(5_000.0, UAH, prov.EMPTY))
        assert isinstance(refusal, RouteInUnusable), refusal
        assert refusal.refused.binding_constraint == "leg.maximum"

    def test_neither_limit_ever_yields_a_figure(self) -> None:
        # The whole point. The cap case used to produce a complete, plausible outcome for a
        # purchase the rail would not have carried -- Principle VI's highest severity, with
        # nothing in the output to notice.
        for field in ("monthly_cap", "maximum"):
            outcome = self._limited(**{field: Money(5_000.0, UAH, prov.EMPTY)})
            assert not isinstance(outcome, TupleOutcome), (field, outcome)

    def test_a_broken_seam_is_reported_before_the_cap(self) -> None:
        # A seam mismatch says the tuple is impossible at **any** amount in any month; a cap
        # says it is impossible at this amount this month. Reporting the cap first would hand
        # the owner a remedy that reads as actionable -- send at most the ceiling -- and
        # sending less would then reveal a seam the first refusal had concealed.
        registries = fixtures.with_access(
            fixtures.with_leg(
                fixtures.declared(),
                fixtures.DOMESTIC_IN,
                monthly_cap=Money(5_000.0, UAH, prov.EMPTY),
            ),
            fixtures.OVDP,
            bought_at="monobank_uah",
        )
        refusal = _evaluate(registries, fixtures.hurdle_tuple(), 10_000.0)
        assert isinstance(refusal, SeamDoesNotChain), refusal

    def test_an_amount_at_the_ceiling_passes(self) -> None:
        # Strictly above, so a cap the amount exactly meets is not a refusal. A ceiling is the
        # most the rail carries, not the most it carries minus one.
        outcome = self._limited(monthly_cap=Money(10_000.0, UAH, prov.EMPTY))
        assert isinstance(outcome, TupleOutcome), outcome


class TestTheSameTwoLimitsOnTheWayOut:
    """FR-016 says the feasibility rules apply on the way in **and the way out**.

    The inbound pair above was fixed while this one still shipped: a 1.00 hryvnia monthly cap
    on the declared exit route produced a **complete outcome** reporting 13 100.00 reaching
    the endpoint. Identical defect, identical severity, mirrored -- and it survived because
    the inbound case was closed without asking what its sibling did.
    """

    def _limited(self, **limit: Money) -> object:
        return _evaluate(
            fixtures.with_leg(fixtures.declared(), fixtures.DOMESTIC_OUT, **limit),
            fixtures.hurdle_tuple(),
            10_000.0,
        )

    def test_a_monthly_ceiling_below_a_release_refuses_naming_it(self) -> None:
        # The first coupon of ten units of issue A is 775.00, well over a 1.00 ceiling.
        refusal = self._limited(monthly_cap=Money(1.0, UAH, prov.EMPTY))
        assert isinstance(refusal, WayOutCapExceeded), refusal
        assert_money_close(refusal.ceiling, Money(1.0, UAH, prov.EMPTY))
        assert refusal.released_on == date(2026, 7, 15)
        assert_money_close(refusal.excess, Money(refusal.requested.amount - 1.0, UAH, prov.EMPTY))
        assert "FR-018" in refusal.reason
        assert "2026-08-22" in refusal.reason

    def test_it_names_the_release_that_could_not_go_home(self) -> None:
        # The field the inbound record has no room for, and the first thing a reader needs: a
        # way out that carries every coupon and refuses the redemption is a different finding
        # from one that carries nothing, and only the date tells them apart. A ceiling of
        # 5 000.00 clears all four coupons and binds on the 10 775.00 redemption.
        refusal = self._limited(monthly_cap=Money(5_000.0, UAH, prov.EMPTY))
        assert isinstance(refusal, WayOutCapExceeded), refusal
        assert refusal.released_on == date(2028, 1, 17)
        assert refusal.requested.amount > 10_000.0

    def test_a_per_transaction_maximum_is_the_other_refusal_here_too(self) -> None:
        refusal = self._limited(maximum=Money(1.0, UAH, prov.EMPTY))
        assert isinstance(refusal, WayOutUnusable), refusal
        assert refusal.refused.binding_constraint == "leg.maximum"

    def test_neither_limit_ever_yields_a_figure(self) -> None:
        # What shipped: `reaches = 13 100.00` under a 1.00 cap, with nothing on the record to
        # say the rail would not have carried a penny of it.
        for field in ("monthly_cap", "maximum"):
            outcome = self._limited(**{field: Money(1.0, UAH, prov.EMPTY)})
            assert not isinstance(outcome, TupleOutcome), (field, outcome)

    def test_a_ceiling_above_every_release_passes(self) -> None:
        outcome = self._limited(monthly_cap=Money(100_000.0, UAH, prov.EMPTY))
        assert isinstance(outcome, TupleOutcome), outcome
        assert_money_close(outcome.reaches, Money(13_100.0, UAH, prov.EMPTY))
