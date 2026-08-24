"""SC-001 -- one whole round trip, worked out by hand: ramp in, purchase, lifecycle, tax,
instrument exit, ramp out.

**This is the number the feature exists to produce**, and it is the only test that catches a
join which sums the right parts in the wrong order. Every structural test in this feature
passes on such a join: the seams chain, the parts are all present, the marks propagate, the
comparison ranks. Only arithmetic worked out independently notices that the purchase was made
with what departed rather than with what arrived, or that a fee was charged once where it
should have been charged four times.

The instrument is ``ovdp_synthetic_a`` -- **synthetic, terms invented** -- and the two routes
are declared by this module, with fees chosen so that every term is visible and none of them
is zero. A round trip over the shipped domestic pair costs exactly nothing, which is the right
bar for feature 002's SC-004 and is useless here: it would make "the purchase used what
arrived" indistinguishable from "the purchase used what departed".

## The arithmetic, once, in full

Terms (from ``data/instruments/ovdp_synthetic_a.toml`` and
``data/access/instruments.toml``): face 1 000.00 UAH per unit, coupon 15.5% a year, issued
2026-01-15, maturing 2028-01-15, semiannual, ``act/365``, ``following``, minimum ticket
1 000.00, minimum increment 1 unit, quoted at par -- 1 000.00 per unit -- at ``inzhur``. Tax
class ``ua_government_bond``: nil PIT, nil levy.

Routes declared here: in, ``monobank_uah -> inzhur``, 1% plus 50.00 flat, no latency; out,
``inzhur -> monobank_uah``, 0.5% plus 10.00 flat, no latency. The outlay is 10 000.00 UAH
leaving the hryvnia salary on 2026-01-15.

**The way in.** Fees come off the amount entering the leg (``docs/METHODOLOGY.md`` §16.3)::

    percentage   10 000.00 x 0.01   =    100.00
    flat                            =     50.00
    arrived      10 000 - 100 - 50  =  9 850.00

**The purchase**, made with what **arrived** and not with what departed -- the whole of
FR-003::

    increments   floor(9 850 / 1 000 / 1)  =  9 units
    cost         9 x 1 000                 =  9 000.00
    undeployed   9 850 - 9 000             =    850.00   at `inzhur`, reported, not vanished

Buying with the departing 10 000.00 would have acquired **ten** units, which is the defect
this example exists to catch: a plausible schedule, one unit too large, and every figure
downstream of it wrong by eleven percent.

**What the rate is measured against**, which is not the same number::

    invested     10 000 - 850             =  9 150.00

The 850.00 is cash at `inzhur`, not money lost. Discounting the arrivals back to the whole
10 000.00 would price it as a **total loss** and report this bond at 8.96%; discounting them
back to the 9 000.00 of paper would forget the 150.00 ramp entirely and report 15.50%. Both
are outside the band asserted below. What the netting assumes — that the 850.00 is recoverable
at par — is not free and is stated in the outcome's own `excludes`.

**The lifecycle.** Nine units of 1 000.00 face at 15.5% is 1 395.00 of interest a year, and
each coupon is ``1 395 x days / 365`` on the accrual periods issue A's own worked example
derives (``tests/worked_examples/test_ovdp_schedule.py``): 181, 184, 181, 184 days.

    2026-07-15   1 395 x 181/365  =   691.7671232876712
    2027-01-15   1 395 x 184/365  =   703.2328767123288
    2027-07-15   1 395 x 181/365  =   691.7671232876712
    2028-01-17   1 395 x 184/365  =   703.2328767123288   (Saturday 15th -> Monday 17th)
    2028-01-17   redemption 9 x 1 000                     = 9 000.00

Total released: 2 790.00 of interest -- exactly two years of it -- plus 9 000.00 of principal.

**The tax** is five recorded charges of exactly zero, each citing the exemption.

**The instrument's exit terms** charge nothing: a bond redeems at face value on its maturity
date and its declared terms name no exit commission. That zero is a **recorded line**, not an
assumption (FR-009).

**The way out**, charged once on each amount the instrument released, on the date it released
it. The final coupon and the redemption fall on one date and travel as one movement, because
what goes home is what the owner has that day::

    2026-07-15     691.7671232876712 - 0.5% - 10  =    678.3082876712328
    2027-01-15     703.2328767123288 - 0.5% - 10  =    689.7167123287671
    2027-07-15     691.7671232876712 - 0.5% - 10  =    678.3082876712328
    2028-01-17   9 703.2328767123290 - 0.5% - 10  =  9 644.7167123287670
                                                     -------------------
    reaches                                          11 691.05

The four flat fees are 40.00 and the four percentage fees 58.95, so the way out took 98.95 of
the 11 790.00 released -- and **the same 10.00 flat fee is 1.45% of the first coupon and 0.10%
of the final movement**, fourteen times heavier on the small one. That is exactly why a
round-trip *fraction* measured on the arriving amount may not be applied to a coupon.

**The conservation check**, which is what makes the whole example checkable at a glance::

    10 000.00  =  9 000.00 (bought) + 150.00 (way in) + 850.00 (undeployed)
    11 790.00  =  11 691.05 (reached) + 98.95 (way out)
"""

from __future__ import annotations

from typing import Final

import pytest

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results.tuple import Part, Tuple, TupleOutcome
from terezy.core.routes.path import DeclaredExit, FundingPath
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.worked_example

UAH: Final = fixtures.UAH

IN_ROUTE: Final = "test_costed_in"
OUT_ROUTE: Final = "test_costed_out"

SENT: Final = 10_000.0
IN_PCT: Final = 0.01
IN_FLAT: Final = 50.0
OUT_PCT: Final = 0.005
OUT_FLAT: Final = 10.0

ARRIVED: Final = SENT - SENT * IN_PCT - IN_FLAT
PRICE: Final = 1_000.0
UNITS: Final = 9.0
COST: Final = UNITS * PRICE
UNDEPLOYED: Final = ARRIVED - COST
INVESTED: Final = SENT - UNDEPLOYED
"""9 150.00 -- what left the stream, less the remainder that made the trip and bought nothing.

The denominator of the rate. It is **not** ``COST``: the 150.00 the way in took is money the
owner spent to hold 9 000.00 of paper, and it belongs in the rate.
"""

RATE: Final = 0.14442645895184436
"""The internal rate of return of the four arrivals against ``INVESTED``, on act/365.

A root has no closed form, so it is recorded rather than derived -- and it is checkable by
hand at the assertion site, where discounting the four hand-listed arrivals at this rate is
shown to come back to 9 150.00 and not to 10 000.00.
"""

ANNUAL_INTEREST: Final = UNITS * PRICE * 0.155
"""1 395.00 -- nine units of 1 000.00 face at 15.5%."""

RELEASES: Final[tuple[tuple[str, float], ...]] = (
    ("2026-07-15", ANNUAL_INTEREST * 181 / 365),
    ("2027-01-15", ANNUAL_INTEREST * 184 / 365),
    ("2027-07-15", ANNUAL_INTEREST * 181 / 365),
    ("2028-01-17", ANNUAL_INTEREST * 184 / 365 + UNITS * PRICE),
)
"""What the holding releases, by the date it releases it. The final coupon and the redemption
share a date and travel as one movement."""


def _repatriated(released: float) -> float:
    return released - released * OUT_PCT - OUT_FLAT


def _registries() -> Registries:
    """The shipped registry with one costed way in and one costed way out added."""
    registries = fixtures.with_new_route(
        fixtures.shipped(),
        fixtures.route(
            IN_ROUTE,
            origin="monobank_uah",
            destination="inzhur",
            direction="inbound",
            partner=OUT_ROUTE,
            fee_pct=IN_PCT,
            fee_fixed=IN_FLAT,
        ),
    )
    return fixtures.with_new_route(
        registries,
        fixtures.route(
            OUT_ROUTE,
            origin="inzhur",
            destination="monobank_uah",
            direction="exit",
            fee_pct=OUT_PCT,
            fee_fixed=OUT_FLAT,
        ),
    )


def _outcome() -> TupleOutcome:
    candidate = Tuple(
        instrument_id=fixtures.OVDP,
        stream_id=fixtures.SALARY,
        route_in=FundingPath(destination_id="inzhur", stream_id=fixtures.SALARY, route_id=IN_ROUTE),
        exit_terms=fixtures.HOLD_TO_MATURITY,
        route_out=DeclaredExit(route_id=OUT_ROUTE),
    )
    outcome = evaluate(
        candidate,
        amount=Money(SENT, UAH, prov.EMPTY),
        horizon=fixtures.DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END),
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=_registries(),
    )
    assert isinstance(outcome, TupleOutcome), outcome
    return outcome


def _part(outcome: TupleOutcome, part: Part) -> Money:
    return next(line.amount for line in outcome.parts if line.part == part)


class TestTheWayInAndThePurchase:
    """FR-003: bought with what arrived, in whole declared increments, remainder reported."""

    def test_the_way_in_took_one_percent_and_fifty_hryvnia(self) -> None:
        #   10 000 x 0.01 = 100.00, plus 50.00 flat = 150.00
        assert_money_close(_part(_outcome(), "ramp_in"), Money(-150.0, UAH, prov.EMPTY))

    def test_nine_units_were_bought_with_the_nine_thousand_eight_hundred_and_fifty(self) -> None:
        #   floor(9 850 / 1 000) = 9, and 9 x 1 000 = 9 000.00.
        # Buying with the departing 10 000 would have acquired ten, which is a plausible
        # schedule that is wrong by a whole unit -- the defect FR-003 exists to prevent.
        assert is_close(ARRIVED, 9_850.0)
        assert_money_close(_part(_outcome(), "entry"), Money(-COST, UAH, prov.EMPTY))
        assert_money_close(_part(_outcome(), "entry"), Money(-9_000.0, UAH, prov.EMPTY))

    def test_the_remainder_is_reported_as_undeployed_cash_where_it_is_sitting(self) -> None:
        #   9 850 - 9 000 = 850.00, at `inzhur`, having made the trip and bought nothing.
        undeployed = _outcome().undeployed
        assert undeployed is not None
        assert_money_close(undeployed.amount, Money(UNDEPLOYED, UAH, prov.EMPTY))
        assert_money_close(undeployed.amount, Money(850.0, UAH, prov.EMPTY))
        assert undeployed.venue_id == "inzhur"

    def test_what_left_the_stream_is_what_was_bought_plus_the_ramp_plus_the_remainder(
        self,
    ) -> None:
        # The conservation identity. Nothing vanishes between the salary and the holding, and
        # this is the assertion that would catch a fee charged twice or a remainder dropped.
        outcome = _outcome()
        undeployed = outcome.undeployed
        assert undeployed is not None
        accounted = (
            -_part(outcome, "entry").amount
            - _part(outcome, "ramp_in").amount
            + undeployed.amount.amount
        )
        assert is_close(accounted, SENT)


class TestTheLifecycleAndTheTax:
    """What the holding paid, and the exemption that took none of it."""

    def test_the_four_coupons_and_the_redemption_are_the_lifecycle_line(self) -> None:
        #   2 790.00 of interest -- exactly two years of 1 395.00 -- plus 9 000.00 principal.
        expected = 2 * ANNUAL_INTEREST + UNITS * PRICE
        assert is_close(expected, 11_790.0)
        assert_money_close(_part(_outcome(), "lifecycle"), Money(expected, UAH, prov.EMPTY))

    def test_the_tax_line_is_exactly_zero_under_the_exemption(self) -> None:
        # Exactly, not approximately: five charges of zero sum to zero and no tolerance is
        # involved. "Approximately exempt" is not a thing.
        assert _part(_outcome(), "tax").amount == 0.0

    def test_the_exit_terms_line_is_a_recorded_zero_and_says_what_it_rests_on(self) -> None:
        # FR-009: a declared zero is a value like any other and appears as a line. Only an
        # *absent* declaration is a refusal, and a bond's way out is declared -- redemption at
        # face value, on the maturity date, charging nothing.
        line = next(item for item in _outcome().parts if item.part == "exit_terms")
        assert line.amount.amount == 0.0
        assert "maturity" in line.source


class TestTheWayOutIsChargedOnceOnEachRelease:
    """The join's own model, and the reason a round-trip fraction may not be reused."""

    def test_each_release_arrives_net_of_a_percentage_and_a_flat_fee(self) -> None:
        outcome = _outcome()
        assert [arrival.released_on.isoformat() for arrival in outcome.arrivals] == [
            on for on, _ in RELEASES
        ]
        for arrival, (_, released) in zip(outcome.arrivals, RELEASES, strict=True):
            assert_money_close(arrival.released, Money(released, UAH, prov.EMPTY))
            assert_money_close(arrival.amount, Money(_repatriated(released), UAH, prov.EMPTY))

    def test_the_same_flat_fee_costs_the_small_release_fourteen_times_more(self) -> None:
        #   10.00 / 691.7671232876712    = 0.0144557...  ->  1.45% of the first coupon
        #   10.00 / 9 703.2328767123290  = 0.001031...  ->  0.10% of the final movement
        # A fixed fee does not scale, so one fraction cannot price both -- which is why the
        # way out is costed once per release rather than by multiplying a fraction.
        outcome = _outcome()
        first, last = outcome.arrivals[0], outcome.arrivals[-1]
        first_fraction = 1.0 - first.amount.amount / first.released.amount
        last_fraction = 1.0 - last.amount.amount / last.released.amount
        assert is_close(first_fraction, OUT_PCT + OUT_FLAT / first.released.amount)
        assert is_close(last_fraction, OUT_PCT + OUT_FLAT / last.released.amount)
        flat_share = OUT_FLAT / first.released.amount
        assert is_close(flat_share, 0.014455731796669242)
        assert flat_share > 14.0 * (OUT_FLAT / last.released.amount)

    def test_the_way_out_took_ninety_eight_ninety_five_in_total(self) -> None:
        #   percentage 58.95 + flat 4 x 10.00 = 98.95
        charged = sum(released * OUT_PCT + OUT_FLAT for _, released in RELEASES)
        assert is_close(charged, 98.95)
        assert_money_close(_part(_outcome(), "ramp_out"), Money(-charged, UAH, prov.EMPTY))

    def test_what_the_holding_released_is_what_reached_the_endpoint_plus_the_way_out(
        self,
    ) -> None:
        # The second conservation identity. 11 790.00 released, 98.95 charged, 11 691.05 home.
        outcome = _outcome()
        assert is_close(
            outcome.reaches.amount - _part(outcome, "ramp_out").amount,
            _part(outcome, "lifecycle").amount,
        )


class TestTheTwoFigures:
    """FR-015 and research.md D8: the amount, and the rate, each labelled."""

    def test_eleven_thousand_six_hundred_and_ninety_one_reaches_the_endpoint(self) -> None:
        expected = sum(_repatriated(released) for _, released in RELEASES)
        assert is_close(expected, 11_691.049999999999)
        assert_money_close(_outcome().reaches, Money(expected, UAH, prov.EMPTY))
        assert _outcome().reaches.currency is UAH

    def test_the_rate_discounts_the_arrivals_back_to_what_was_actually_invested(self) -> None:
        # The identity that defines the rate, and -- because the denominator is the thing that
        # can be wrong -- the two wrong denominators, named and excluded.
        #
        # At the returned rate the present value of the four arrivals listed above is the
        # 9 150.00 that was actually invested. It is *not* the 10 000.00 that left the stream:
        # discounting back to that would be pricing the 850.00 sitting at `inzhur` as a total
        # loss, and this assertion is what fails if it ever does again.
        #
        # Times are act/365 -- the instrument's own convention, so the tuple's rate and
        # feature 001's hurdle are measured on the same clock -- from the outlay on
        # 2026-01-15 to each arrival:
        #   2026-07-15 -> 181 days     2027-01-15 -> 365 days
        #   2027-07-15 -> 546 days     2028-01-17 -> 732 days
        rate = _outcome().implied_rate
        assert isinstance(rate, NominalRate)
        assert is_close(rate.value, RATE)
        days = (181, 365, 546, 732)
        present_value = sum(
            _repatriated(released) / (1.0 + rate.value) ** (day / 365)
            for day, (_, released) in zip(days, RELEASES, strict=True)
        )
        assert is_close(INVESTED, 9_150.0)
        assert is_close(present_value, INVESTED)
        assert not is_close(present_value, SENT)
        assert not is_close(present_value, COST)

    def test_the_rate_is_the_coupon_less_the_ramp_and_the_way_out(self) -> None:
        # A sanity band, stated as loose rather than dressed up as the project tolerance
        # (docs/METHODOLOGY.md §11.3), and its arithmetic is the three terms that move it:
        #
        #   coupons      1 395.00 a year on 9 150.00 invested        =  15.25%
        #   way out         98.95 over two years, ~49.48 a year      =  -0.54%
        #   the ramp     9 000.00 comes back against 9 150.00 out,
        #                a 150.00 shortfall over two years           =  -0.82%
        #                                                               -------
        #                                                               ~13.9%, and
        # compounding lifts it to 14.44%. The band is what rules out the two ways the
        # denominator can be wrong: charging the 850.00 remainder as a loss lands at 8.96%,
        # and measuring against the 9 000.00 of paper forgets the ramp and lands at 15.50%.
        rate = _outcome().implied_rate
        assert isinstance(rate, NominalRate)
        assert 0.14 < rate.value < 0.15

    def test_the_span_runs_from_the_outlay_to_the_last_arrival(self) -> None:
        # Latency is inside the span (FR-015). Both routes declare none here, so the span ends
        # on the adjusted maturity itself; the shipped pair's four days are what
        # `tests/contract/test_the_hurdle_is_a_tuple.py` isolates.
        outcome = _outcome()
        assert outcome.span.start == fixtures.ISSUE_DATE
        assert outcome.span.end.isoformat() == "2028-01-17"
