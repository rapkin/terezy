"""A coupon collected inside a window, and a sale struck at a price quoted before it.

**A measured gap, and a correction of what it is.** An early exit is struck at the resale price
on the access record, and that price is a **dated observation** -- Inzhur's sell quotation of
2026-08-24 -- carried to the sale date unchanged. A bond quotation is a **dirty** price: the
clean price plus the interest accrued by the day it was read. So a window that collects a coupon
is credited that accrual twice -- once in the coupon it receives, once inside a sale price that
still contains it.

**What is double-counted is the accrual, not the coupon**, and the distinction decides what a
fix would have to be. Under a constant clean price the dirty price falls by a coupon on the day
it detaches and then **recovers by accrual** until the next one, so the movement from the
quotation to the sale is bounded by **one** coupon however many detach in between. Subtracting
every detached coupon from the sale price is therefore not the fix it looks like: built and
measured on 2026-09-03, it makes ``reaches`` identically ``units x the quotation`` at every
horizon -- a year in a 17.1% issue reporting the bid-ask spread and nothing else, and the twelve
issues that redeem inside the owner's one-year window separated from the twelve sold early by an
artifact. It was reverted.

**Closing it needs accrued interest, which no declaration supports.** 013 FR-017 forbids an
accrued figure, a clean price or any split of a price into the two for an enumerated instrument,
because the basis interest accrues on is not declared -- and FR-003b says the declared day count
sizes nothing. That is the `enumerated-accrued-interest` entry in `specs/features.toml`, and this
module is the shipped instance that makes it worth building.

**What ships instead is the claim.** `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST` states the
omission on every early-exit figure, **unsigned**: the error is the accrual at the purchase less
the accrual at the sale, and which way that runs depends on where each date falls inside its own
coupon period.
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
end AND collect at least one payment inside the window -- the population the gap reaches.
Measured 2026-08-31 on the shipped registry; the horizons are
`data/questions/fifty-thousand.toml`'s."""

EARLY_EXIT_CLAIMS = frozenset(
    {
        "early_exit_is_a_point_not_a_distribution",
        "early_exit_spread_is_a_sellers_quote",
        "early_exit_carries_no_rate_risk",
        "early_exit_ignores_accrued_interest",
    }
)
"""What an early-exit figure states it does not account for. The fourth is this module's, and
015 FR-033 named only the first three."""

WORKED = "UA4000236228"
"""Bought 2026-09-02 at 1089.32, pays 85.50 on 2026-09-09, sold 2026-10-01 at 1087.89.

The purchase is a day after the window opens, not on it: `inzhur_direct` declares one leg of
`latency_days = 1`, and the engine buys at `horizon.start` plus the way in's own latency.

The whole arithmetic, on the owner's own 50 000 UAH and the declared minimum increment of one
whole unit::

    45 units x 1089.32 = 49 019.40 deployed, 980.60 left undeployed
    45 x    85.50      =  3 847.50  coupon, collected on 2026-09-09
    45 x  1 087.89     = 48 955.05  sale, at a price quoted 2026-08-24 -- BEFORE the coupon
                         52 802.55  reached

7.7% on the money deployed in one month, on a bond whose coupon is 17.1% a year (`auk_proc`
17.1 against a nominal of 1 000, halved for the 182-day period: 85.50). The month collects a
whole half-year coupon and the sale price does not fall by so much as an hour of accrual: the
reported gain is exactly the coupon less the 1.43 bid-ask spread, per unit.

**How much of it is the double count** cannot be stated, and the reason is the gap itself. On a
straight-line reading of the declared payment dates -- 2026-03-11 to 2026-09-09 is 182 days, the
purchase sits 175 of them in and the sale 22 days into the next period -- the accrual carried at
the purchase would be 82.21 and at the sale 10.34, so about 72 of the 84.07 per unit reported
would be it. That reading is an **illustration and not a figure this engine emits**: nothing
declares the basis, and choosing one is what `enumerated-accrued-interest` is for.
"""

REACHED = 52802.55
DEPLOYED = 49019.40
DEPLOYED_UNITS = 45.0
COUPON_PER_UNIT = 85.50
QUOTED_SELL = 1087.89
SPREAD_PER_UNIT = 1089.32 - QUOTED_SELL


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
    assert [(payment.on, payment.amount.amount) for payment in inside] == [
        (date(2026, 9, 9), COUPON_PER_UNIT)
    ]
    access = declared.access[WORKED]
    assert access.quote is not None
    assert access.resale_price is not None
    assert access.quote.price.amount == 1089.32
    assert access.resale_price.price.amount == QUOTED_SELL
    assert access.resale_price.kind == "venue_terms"


def test_the_sale_is_struck_at_the_quotation_carried_forward_unchanged() -> None:
    """The defect, as an equality rather than a complaint.

    The month's whole reported gain is the coupon less the bid-ask spread, per unit: the sale
    price has not fallen by so much as an hour of the accrual that coupon paid out. An
    implementation that began adjusting the price would fail here -- and the adjustment must not
    be *less every detached coupon*, which this module's docstring records as built, measured
    and reverted.
    """
    section = answers.answered().sections[0]
    worked = [item for item in section_evaluated(section) if item.key.instrument_id == WORKED]
    assert len(worked) == 1
    outcome = worked[0]
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == DEPLOYED_UNITS
    assert outcome.sold_early.price_per_unit.amount == QUOTED_SELL
    assert outcome.reaches.amount == pytest.approx(REACHED, abs=TOLERANCE)
    assert outcome.reaches.amount - DEPLOYED == pytest.approx(
        DEPLOYED_UNITS * (COUPON_PER_UNIT - SPREAD_PER_UNIT), abs=TOLERANCE
    )


def test_a_window_that_reaches_maturity_carries_no_such_figure() -> None:
    """The gap is an early exit's, not the instrument's. This issue redeems 2027-03-10, inside
    the owner's twelve-month window, so that section sells nothing and states no early-exit
    claim about it -- which is what says the omission is scoped to the sale rather than to the
    paper.
    """
    twelve = answers.answered().sections[2]
    worked = next(item for item in section_evaluated(twelve) if item.key.instrument_id == WORKED)
    assert worked.sold_early is None
    assert not [
        item
        for item in twelve.excludes
        if item.applies_to == worked.key and item.what.value in EARLY_EXIT_CLAIMS
    ]


def test_the_accrued_double_count_is_stated_and_carries_no_sign() -> None:
    """FR-023a at the level that matters: an omission that is not stated is a silent default.

    Unsigned, and the absence is asserted rather than tolerated. The error is the accrual at the
    purchase less the accrual at the sale, and a window can end either earlier or later inside
    its coupon period than it began -- so a direction here would be a sign without a warrant.
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
    assert {item.applies_to for item in accrued} == {
        item.key for item in section_evaluated(section) if item.sold_early is not None
    }


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
