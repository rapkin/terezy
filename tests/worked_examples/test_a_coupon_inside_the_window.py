"""A coupon collected inside a window, and the sale price it has already left.

A quoted bond price is a **dirty** price, and it falls by a coupon on the day that coupon
detaches. An early exit is struck at a dated observation -- Inzhur's sell quotation of
2026-08-24 -- so carrying that quotation to the sale date unchanged would credit a holding the
coupon it collects inside the window *and* sell it at a price that still contained the same
money. The sale is therefore struck at the quotation **less every coupon that detached after it
was observed** (``core.scenarios.early_exit.detached_since``).

**A coupon dated on the sale day counts as detached.** That is the convention the schedule
generators already fix rather than a new one: ``enumerated`` pays every payment with
``payment.on <= horizon.end`` and ``fixed_income`` pays a coupon whose ``paid_on`` equals the
window's end while refusing to reinvest it. The holder receives it, so it has left the price.

**What comes out is a whole coupon where what was in the quotation was an accrual**, and the
gap that leaves is signed. Under the same constant-clean-price assumption the price also
*rebuilds* by accrual between coupons, so the sale price struck here is **below** the one the
assumption implies -- by the coupons detached, less the accrual the quotation carried, plus the
accrual the sale date carries. Every one of those terms needs a basis that no declaration states
(013 FR-017 forbids inferring one; `enumerated-accrued-interest` in `specs/features.toml`), so
what ships is the direction and not the size: `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST`,
**understated**, on every sale a coupon detached from.

The residual is visible without any accrual figure at all, and this module asserts it: a
three-month hold of the worked issue reaches exactly what a one-month hold reaches, because the
two extra months build accrual the model does not carry.
"""

from __future__ import annotations

import functools
from datetime import date, timedelta

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.instruments.interface import EnumeratedTerms
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.answer import Direction, Exclusion
from terezy.core.results.ramp import RampCost
from terezy.core.results.tuple import TupleOutcome
from terezy.core.routes import cost
from terezy.core.routes.path import segments_of
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

DETACHED_PER_HORIZON = (9, 15, 12)
"""How many of each section's early exits have a coupon detach between the 2026-08-24 quotation
and the sale -- the population whose sale price the subtraction moves. Measured 2026-09-03 on
the shipped registry; the horizons are `data/questions/fifty-thousand.toml`'s."""

EARLY_EXIT_CLAIMS = frozenset(
    {
        "early_exit_is_a_point_not_a_distribution",
        "early_exit_spread_is_a_sellers_quote",
        "early_exit_carries_no_rate_risk",
        "early_exit_ignores_accrued_interest",
    }
)
"""What an early-exit figure states it does not account for. 015 FR-033 named the first three;
the fourth is what subtracting whole coupons from a dirty quotation leaves behind."""

WORKED = "UA4000236228"
"""Bought 2026-09-02 at 1089.32, pays 85.50 on 2026-09-09, quoted for resale at 1087.89.

The purchase is a day after the window opens, not on it: `inzhur_direct` declares one leg of
`latency_days = 1`, and the engine buys at `horizon.start` plus the way in's own latency.

The whole arithmetic, on the owner's own 50 000 UAH and the declared minimum increment of one
whole unit::

    45 units x 1089.32 = 49 019.40 deployed, 980.60 left undeployed
    45 x    85.50      =  3 847.50  coupon, collected on 2026-09-09
         1 087.89
       -    85.50      =  1 002.39  the 2026-08-24 quotation, less the coupon that detached
    45 x  1 002.39     = 45 107.55  sale on 2026-10-01
                         48 955.05  reached

**-64.35 over the month, -0.13%**, and the check that makes it more than a subtraction is that
64.35 is 45 x 1.43 -- the whole of the gap between the buy quotation of 1 089.32 and the sell
quotation of 1 087.89. A month bought and sold at one morning's two prices returns the spread
and nothing else, which is what a constant clean price means.

Carrying the quotation forward unchanged reached 52 802.55 instead: the 3 847.50 counted once as
income and once inside a sale price quoted while it was still attached.

**What is still missing is the accrual, and it is signed.** On a straight-line reading of the
declared payment dates -- 2026-03-11 to 2026-09-09 is 182 days, so the quotation of 2026-08-24
sat 166 days into the period and the 2026-10-01 sale sits 22 days into the next -- the quotation
carried 77.99 of accrual and the sale date carries 10.34, so the sale is struck about 17.85 per
unit below what the same assumption implies. That reading is an **illustration and not a figure
this engine emits**: nothing declares the basis, and choosing one is what
`enumerated-accrued-interest` is for.
"""

QUOTED_ON = date(2026, 8, 24)
REACHED = 48955.05
DEPLOYED = 49019.40
DEPLOYED_UNITS = 45.0
COUPON_PER_UNIT = 85.50
QUOTED_SELL = 1087.89
SPREAD_PER_UNIT = 1089.32 - QUOTED_SELL

DETACHED_BEFORE_THE_PURCHASE = {("UA4000231195", 87.5), ("UA4000239081", 82.2)}
"""The issues paying a coupon after the quotation and before the owner's window opens, with the
amount per unit. Their sale price is struck net of it while the **buy** quotation of the same
morning is carried to the purchase date gross of it -- an asymmetry on the other leg, recorded
here because nothing else would say so. Measured 2026-09-03."""


@functools.cache
def _supplied() -> AnswerInputs:
    """The shipped registry, read once. `answers.inputs()` re-resolves the whole data root, and
    this module reads it once per candidate across eight tests."""
    return answers.inputs()


def _latency(item: TupleOutcome) -> int:
    """How long the way in takes: the SUM along the chain, which is what `cost` accumulates and
    `tuple_outcome` adds to the horizon start -- a chain of two one-day legs is two days."""
    routes = _supplied().routes
    return sum(
        leg.latency_days
        for segment in segments_of(item.key.route_in)
        for leg in routes[segment].legs
    )


def _bought_on(item: TupleOutcome, start: date) -> date:
    return start + timedelta(days=_latency(item))


def _sold_early(horizon_index: int) -> list[TupleOutcome]:
    section = answers.answered().sections[horizon_index]
    return [item for item in section_evaluated(section) if item.sold_early is not None]


def _detached(item: TupleOutcome) -> float:
    """What came out of this candidate's quotation, per unit. `_sold_early` has already
    established that there is a sale; this is where the type system is told."""
    assert item.sold_early is not None, item.key.instrument_id
    return item.sold_early.detached_per_unit.amount


def test_the_window_and_the_holding_cannot_disagree_about_what_is_inside() -> None:
    """A payment between the horizon's start and the candidate's own purchase would be received
    by nobody and detach from the quotation all the same, so the two readings of *inside* would
    part company. They agree only while no declared payment falls in that gap -- a fact about
    the data rather than about either rule, so it is asserted rather than assumed.
    """
    declared = _supplied().registries.instruments
    gaps = []
    latencies = []
    for index, section in enumerate(answers.answered().sections):
        for item in _sold_early(index):
            # Not `getattr(terms, "payments", ())`: a generative bond has no payment list, and
            # skipping one silently would drop it from a check whose subject IS which payments
            # fall inside a window. None carries a resale price today; the day one does, this
            # must be widened rather than quietly pass.
            terms = declared[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            latencies.append(_latency(item))
            bought = _bought_on(item, section.horizon.start)
            gaps += [
                (item.key.instrument_id, payment.on)
                for payment in terms.payments
                if section.horizon.start < payment.on <= bought
            ]
    assert not gaps, gaps
    # Over the SAME population the check ranges over, and non-empty: an empty set, or one where
    # only the candidates this check skips carry a latency, would make `gaps` empty for the
    # vacuous reason rather than the true one.
    assert latencies
    assert set(latencies) != {0}


def test_the_subtraction_is_reached_at_every_horizon_the_owner_asked_about() -> None:
    """And does not reach every sale: a window with no coupon date in it is struck at the
    quotation itself, which is what makes the count a measurement rather than a tautology."""
    measured = []
    for index in range(len(answers.answered().sections)):
        sold = _sold_early(index)
        assert sold
        detached = [item for item in sold if _detached(item) > 0.0]
        measured.append(len(detached))
    assert tuple(measured) == DETACHED_PER_HORIZON
    untouched = [item for item in _sold_early(0) if _detached(item) == 0.0]
    assert untouched


def test_a_coupon_between_the_quotation_and_the_purchase_still_leaves_the_price() -> None:
    """The window opens at the quotation's own day, and this is the population that proves it.

    Such a coupon is one the holder never receives, and it comes out of the sale price anyway --
    because it came out of the market price too. What is *not* symmetric is the other leg: the
    buy quotation of the same morning sizes the purchase gross of it. Named here so the
    asymmetry is a recorded measurement rather than a silence.
    """
    declared = _supplied().registries
    found = set()
    on_the_quotation_day = set()
    for index, section in enumerate(answers.answered().sections):
        for item in _sold_early(index):
            quote = declared.access[item.key.instrument_id].resale_price
            assert quote is not None, item.key.instrument_id
            terms = declared.instruments[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            bought = _bought_on(item, section.horizon.start)
            found |= {
                (item.key.instrument_id, payment.amount.amount)
                for payment in terms.payments
                if quote.observed_on < payment.on <= bought
            }
            on_the_quotation_day |= {
                item.key.instrument_id
                for payment in terms.payments
                if payment.on == quote.observed_on
            }
    assert found == DETACHED_BEFORE_THE_PURCHASE
    # The lower bound is strict, so a coupon dated ON the quotation day would be treated as
    # still inside it -- and whether a morning quotation on a payment date holds that coupon is
    # something nobody has declared. Unreachable on the shipped registry, asserted rather than
    # supposed, because the day it is reachable the convention has to be chosen rather than
    # inherited from a comparison operator.
    assert not on_the_quotation_day


def test_the_worked_arithmetic_is_what_the_declarations_say() -> None:
    """The numbers in this module's docstring, read back off the files rather than retyped."""
    declared = _supplied().registries
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    worked = next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)
    bought = _bought_on(worked, section.horizon.start)
    assert bought == date(2026, 9, 2)
    inside = [
        payment for payment in terms.payments if QUOTED_ON < payment.on <= section.horizon.end
    ]
    assert [(payment.on, payment.amount.amount) for payment in inside] == [
        (date(2026, 9, 9), COUPON_PER_UNIT)
    ]
    access = declared.access[WORKED]
    assert access.quote is not None
    assert access.resale_price is not None
    assert access.quote.price.amount == 1089.32
    assert access.resale_price.price.amount == QUOTED_SELL
    assert access.resale_price.kind == "venue_terms"
    assert access.resale_price.observed_on == QUOTED_ON


def test_the_engine_strikes_the_sale_at_the_quotation_net_of_the_coupon() -> None:
    """The docstring's arithmetic, read back off the owner's own answer.

    The whole month returns the spread: 45 x 1 002.39 sold plus 45 x 85.50 collected is
    45 x 1 087.89, which is 45 x 1.43 short of the 45 x 1 089.32 that was deployed.
    """
    worked = [item for item in _sold_early(0) if item.key.instrument_id == WORKED]
    assert len(worked) == 1
    outcome = worked[0]
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == DEPLOYED_UNITS
    assert outcome.sold_early.detached_per_unit.amount == pytest.approx(
        COUPON_PER_UNIT, abs=TOLERANCE
    )
    assert outcome.sold_early.price_per_unit.amount == pytest.approx(
        QUOTED_SELL - COUPON_PER_UNIT, abs=TOLERANCE
    )
    assert outcome.reaches.amount == pytest.approx(REACHED, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(DEPLOYED_UNITS * QUOTED_SELL, abs=TOLERANCE)
    assert outcome.reaches.amount - DEPLOYED == pytest.approx(
        -DEPLOYED_UNITS * SPREAD_PER_UNIT, abs=TOLERANCE
    )


def test_two_extra_months_of_accrual_reach_nothing_at_all() -> None:
    """The residual, visible without an accrual figure and asserted rather than argued.

    One coupon falls inside the one-month window and no further one inside the three-month
    window, so the model has the position reach **the same amount** over three months as over
    one: the accrual those two months build is not carried. That is the whole content of the
    `early_exit_ignores_accrued_interest` claim, and its sign -- the longer hold is understated.
    """
    one_month = next(item for item in _sold_early(0) if item.key.instrument_id == WORKED)
    three_months = next(item for item in _sold_early(1) if item.key.instrument_id == WORKED)
    assert one_month.sold_early is not None
    assert three_months.sold_early is not None
    assert three_months.sold_early.on > one_month.sold_early.on
    assert three_months.sold_early.detached_per_unit == one_month.sold_early.detached_per_unit
    assert three_months.reaches.amount == pytest.approx(one_month.reaches.amount, abs=TOLERANCE)


def test_the_accrued_residual_is_stated_where_a_coupon_detached_and_nowhere_else() -> None:
    """FR-023a at the level that matters: an omission that is not stated is a silent default.

    Signed, and the sign is warranted rather than assumed: what came out of the quotation is a
    whole coupon where what was in it was that period's accrual, and an accrual within a period
    is smaller than the period's own coupon -- so the struck price is below the one the belief
    implies, always. A sale from which nothing detached has no such residual and states none.
    """
    assert {item.value for item in Exclusion} & EARLY_EXIT_CLAIMS == EARLY_EXIT_CLAIMS
    section = answers.answered().sections[0]
    accrued = [
        item
        for item in section.excludes
        if item.what is Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST
    ]
    assert accrued
    assert all(item.direction is Direction.UNDERSTATED for item in accrued)
    assert {item.applies_to for item in accrued} == {
        item.key for item in _sold_early(0) if _detached(item) > 0.0
    }
    stated = {item.what.value for item in section.excludes if item.what.value in EARLY_EXIT_CLAIMS}
    assert stated == EARLY_EXIT_CLAIMS


def test_the_carried_price_keeps_the_marks_of_both_the_quote_and_the_coupon() -> None:
    """Principle I: the struck price is an assumption derived from an unverified quotation less
    a declared coupon, and subtracting one from the other may not launder either source away."""
    declared = _supplied().registries
    quote = declared.access[WORKED].resale_price
    assert quote is not None
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    outcome = next(item for item in _sold_early(0) if item.key.instrument_id == WORKED)
    assert outcome.sold_early is not None
    inside = [
        payment for payment in terms.payments if QUOTED_ON < payment.on <= section.horizon.end
    ]
    assert inside
    behind = outcome.sold_early.price_per_unit.provenance.sources
    assert quote.price.provenance.sources <= behind
    for payment in inside:
        assert payment.amount.provenance.sources <= behind
    assert not any(source.verified_on for source in behind)


def test_the_latency_this_module_sums_is_the_one_the_engine_adds() -> None:
    """`_latency` re-derives `tuple_outcome`'s `horizon.start + routed.latency_days`, because
    `TupleOutcome` exposes no purchase date. Re-deriving a rule is how a check quietly keeps
    comparing against the old one, so the sum is pinned against the accumulator the engine
    actually uses -- `cost.cost_one`, whose `RampCost.latency_days` is what the join adds.
    """
    registries = _supplied().registries
    section = answers.answered().sections[0]
    checked = 0
    for item in section_evaluated(section):
        priced = cost.cost_one(
            item.key.route_in,
            item.outlay,
            routes=_supplied().routes,
            channels=registries.channels,
            streams=registries.streams,
            kinds=registries.kinds,
            on_date=section.horizon.start,
            as_of=answers.AS_OF,
            spendable=registries.spendable,
        )
        assert isinstance(priced, RampCost), item.key.instrument_id
        assert priced.latency_days == _latency(item), item.key.instrument_id
        checked += 1
    assert checked
