"""A coupon collected inside a window, and the sale price it has already left.

A bond's market price falls by its coupon on the day the coupon detaches. An early exit is
struck at a **dated observation** -- Inzhur's sell quotation of 2026-08-24 -- so a window
containing a coupon date would credit the holding the coupon **and** sell it at a price observed
while that coupon was still attached, counting the same money twice. The sale is therefore
struck at the quotation **less every coupon that detached while this holding held the paper**
(``core.scenarios.early_exit.price_at``), which is the clean-price-is-constant reading of the
owner's declared belief.

**A coupon dated on the sale day counts as detached.** That is the convention the schedule
generators already fix rather than a new one: ``enumerated`` pays every payment with
``payment.on <= horizon.end`` and ``fixed_income`` pays a coupon whose ``paid_on`` equals the
window's end while refusing to reinvest it. The holder receives it, so it has left the price.

**The window opens at the later of the quotation and the purchase, and the purchase half is
load-bearing.** Two shipped issues pay a coupon on 2026-08-26 -- after the 2026-08-24 quotation
and before the owner's window opens -- while the *buy* quotation of the same morning is carried
to the purchase date unadjusted. Subtracting such a coupon from the sell leg alone would report
a loss of a whole coupon that nobody took, so the population is named and pinned below.

**What is left behind is accrued interest**, and it is stated rather than fixed: the quotation
carried an accrual on 2026-08-24 and the sale date carries a different one, no declaration
states the basis interest accrues on (the ``enumerated-accrued-interest`` future entry), and the
residual is smaller than a coupon and unsigned. It reaches the reader as the fourth typed
exclusion on every early-exit figure.
"""

from __future__ import annotations

import functools
from datetime import date, timedelta

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.instruments.interface import EnumeratedTerms
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.answer import Exclusion
from terezy.core.results.ramp import RampCost
from terezy.core.results.tuple import TupleOutcome
from terezy.core.routes import cost
from terezy.core.routes.path import segments_of
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

AFFECTED_PER_HORIZON = (5, 11, 12)
"""How many candidates, at each of the owner's three horizons, are sold before their own terms
end AND collect at least one payment inside the window -- the population whose sale price the
carry-forward moves. Measured 2026-08-31 on the shipped registry; the horizons are
`data/questions/fifty-thousand.toml`'s."""

EARLY_EXIT_CLAIMS = frozenset(
    {
        "early_exit_is_a_point_not_a_distribution",
        "early_exit_spread_is_a_sellers_quote",
        "early_exit_carries_no_rate_risk",
        "early_exit_ignores_accrued_interest",
    }
)
"""What an early-exit figure states it does not account for. The fourth is this module's: the
coupon itself is now computed, and what remains of it is the accrual on either side."""

WORKED = "UA4000236228"
"""Bought 2026-09-02 at 1089.32, pays 85.50 on 2026-09-09, sold 2026-10-01.

The purchase is a day after the window opens, not on it: `inzhur_direct` declares one leg of
`latency_days = 1`, and the engine buys at `horizon.start` plus the way in's own latency.

The whole arithmetic, on the owner's own 50 000 UAH and the declared minimum increment of one
whole unit::

    45 units x 1089.32 = 49 019.40 deployed, 980.60 left undeployed
    45 x    85.50      =  3 847.50  coupon, collected on 2026-09-09
         1 087.89
       -    85.50      =  1 002.39  the 2026-08-24 quotation, net of the coupon that detached
    45 x  1 002.39     = 45 107.55  sale on 2026-10-01
                         48 955.05  reached

Against 49 019.40 deployed that is **-64.35 over the month, -0.1313%** -- and the check that
makes it more than a subtraction is that 64.35 is 45 x 1.43, the whole of the gap between the
buy quotation of 1 089.32 and the sell quotation of 1 087.89. A month of a 17.1% coupon bought
and sold at one morning's two prices returns the spread and nothing else, which is what a
constant clean price means.

Carrying the quotation forward unchanged reached 52 802.55 instead -- +7.72% in one month on a
bond whose coupon is 17.1% a year (`auk_proc` 17.1 against a nominal of 1 000, halved for the
182-day period: 85.50) -- because the 3 847.50 was counted once as income and once inside a
sale price quoted while it was still attached.
"""

QUOTED_ON = date(2026, 8, 24)
REACHED = 48955.05
DEPLOYED = 49019.40
DEPLOYED_UNITS = 45.0
SPREAD_PER_UNIT = 1089.32 - 1087.89


@functools.cache
def _supplied() -> AnswerInputs:
    """The shipped registry, read once. `answers.inputs()` re-resolves the whole data root, and
    this module reads it once per candidate across seven tests."""
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


def _sold_early_with_a_payment_inside(horizon_index: int) -> list[str]:
    answer = answers.answered()
    section = answer.sections[horizon_index]
    end = section.horizon.end
    declared = _supplied().registries.instruments
    found = []
    for item in section_evaluated(section):
        if item.sold_early is None:
            continue
        terms = declared[item.key.instrument_id].terms
        assert isinstance(terms, EnumeratedTerms)
        bought = _bought_on(item, section.horizon.start)
        if any(bought < payment.on <= end for payment in terms.payments):
            found.append(item.key.instrument_id)
    return sorted(found)


def test_the_window_and_the_holding_cannot_disagree_about_what_is_inside() -> None:
    """The count above opens its window at the candidate's own purchase date. Reading it from
    the horizon start instead is the looser rule a reader would reach for first, and the two
    agree only while no declared payment falls in the gap between them -- a fact about the data
    rather than about either rule, so it is asserted rather than assumed.
    """
    declared = _supplied().registries.instruments
    gaps = []
    latencies = []
    for section in answers.answered().sections:
        for item in section_evaluated(section):
            if item.sold_early is None:
                continue
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


BETWEEN_THE_QUOTATION_AND_THE_PURCHASE = {("UA4000231195", 87.5), ("UA4000239081", 82.2)}
"""The issues paying a coupon after the 2026-08-24 quotation and before the owner's window
opens, with the amount per unit. Measured 2026-09-02 on the shipped registry."""


def test_a_coupon_before_the_purchase_is_left_in_the_sale_price() -> None:
    """The case that decides the window's lower bound, and it is reached rather than argued.

    Both legs of one morning's quotation must treat such a coupon the same way, and the buy leg
    that sizes the purchase carries its quotation to the purchase date **unadjusted**. So these
    two sell at the full quotation, and a rule that opened the window at the quotation's own day
    would report each of them a whole coupon poorer than it is.
    """
    declared = _supplied().registries
    found = set()
    for section in answers.answered().sections:
        for item in section_evaluated(section):
            if item.sold_early is None:
                continue
            quote = declared.access[item.key.instrument_id].resale_price
            assert quote is not None, item.key.instrument_id
            terms = declared.instruments[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            bought = _bought_on(item, section.horizon.start)
            before = [
                payment for payment in terms.payments if quote.observed_on < payment.on <= bought
            ]
            if not before:
                continue
            found |= {(item.key.instrument_id, payment.amount.amount) for payment in before}
            inside = [
                payment.amount.amount
                for payment in terms.payments
                if bought < payment.on <= section.horizon.end
            ]
            assert item.sold_early.price_per_unit.amount == pytest.approx(
                quote.price.amount - sum(inside), abs=TOLERANCE
            ), item.key.instrument_id
    assert found == BETWEEN_THE_QUOTATION_AND_THE_PURCHASE


def test_the_gap_is_reached_at_every_horizon_the_owner_asked_about() -> None:
    sections = len(answers.answered().sections)
    measured = tuple(len(_sold_early_with_a_payment_inside(index)) for index in range(sections))
    assert measured == AFFECTED_PER_HORIZON


def test_the_worked_instance_is_among_them_at_one_month() -> None:
    assert WORKED in _sold_early_with_a_payment_inside(0)


def test_the_worked_arithmetic_is_what_the_declarations_say() -> None:
    """The numbers in this module's docstring, read back off the files rather than retyped."""
    declared = _supplied().registries
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    worked = next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)
    bought = _bought_on(worked, section.horizon.start)
    assert bought == date(2026, 9, 2)
    inside = [payment for payment in terms.payments if bought < payment.on <= section.horizon.end]
    assert [(payment.on, payment.amount.amount) for payment in inside] == [(date(2026, 9, 9), 85.5)]
    access = declared.access[WORKED]
    assert access.quote is not None
    assert access.resale_price is not None
    assert access.quote.price.amount == 1089.32
    assert access.resale_price.price.amount == 1087.89
    assert access.resale_price.kind == "venue_terms"
    assert access.resale_price.observed_on == QUOTED_ON
    assert access.quote.observed_on == QUOTED_ON


def test_the_accrued_residual_is_stated_and_the_coupon_no_longer_is() -> None:
    """What the figure still leaves out, over the closed `Exclusion` set and over the owner's
    own answer. The coupon is **computed**, so nothing claims it as an omission; the accrual on
    either side of it is not, so exactly one claim names it and it carries no direction.
    """
    assert {item.value for item in Exclusion} & EARLY_EXIT_CLAIMS == EARLY_EXIT_CLAIMS
    section = answers.answered().sections[0]
    stated = [item for item in section.excludes if item.what.value in EARLY_EXIT_CLAIMS]
    assert {item.what.value for item in stated} == EARLY_EXIT_CLAIMS
    accrued = [
        item for item in stated if item.what is Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST
    ]
    assert accrued
    assert all(item.direction is None for item in accrued)


def test_the_engine_strikes_the_sale_at_the_quotation_net_of_the_coupon() -> None:
    """The docstring's arithmetic, read back off the owner's own answer.

    The whole month returns the spread: 45 x 1 002.39 sold plus 45 x 85.50 collected is
    45 x 1 087.89, which is 45 x 1.43 short of the 45 x 1 089.32 that was deployed.
    """
    section = answers.answered().sections[0]
    worked = [item for item in section_evaluated(section) if item.key.instrument_id == WORKED]
    assert len(worked) == 1
    outcome = worked[0]
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == DEPLOYED_UNITS
    assert outcome.sold_early.price_per_unit.amount == pytest.approx(1002.39, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(REACHED, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(DEPLOYED_UNITS * 1087.89, abs=TOLERANCE)
    assert outcome.reaches.amount - DEPLOYED == pytest.approx(
        -DEPLOYED_UNITS * SPREAD_PER_UNIT, abs=TOLERANCE
    )


def test_the_carried_price_keeps_the_quotes_unverified_mark() -> None:
    """Principle I: the sale price is an assumption derived from an unverified quotation, and
    subtracting a declared coupon from it may not launder either source away."""
    declared = _supplied().registries
    quote = declared.access[WORKED].resale_price
    assert quote is not None
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    outcome = next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)
    assert outcome.sold_early is not None
    inside = [
        payment
        for payment in terms.payments
        if date(2026, 9, 2) < payment.on <= section.horizon.end
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
