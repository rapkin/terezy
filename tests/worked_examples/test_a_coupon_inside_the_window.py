"""A coupon collected inside a window, and a sale struck at a price quoted before it.

**A recorded gap with a sign, measured rather than argued.** It is not a defect this feature
introduced and it is not one this feature may fix: 016 is data-only by the owner's decision,
and correcting it needs a secondary-market price, which nobody has declared.

What happens. 015 strikes an early exit at the resale price on the access record, and that price
is a **dated observation** -- Inzhur's sell quotation of 2026-08-24. A bond's market price drops
by roughly its coupon on the ex-date, so where the window contains a coupon date the holding is
credited the coupon **and** sold at a price observed while that coupon was still attached. The
figure is overstated by roughly the coupon.

**Why 015's three stated exclusions do not cover it.** FR-033 has the figure state that it is
more certain than the truth (signed), that the spread is understated (signed), and that rate
risk is unsigned because it is symmetric. A coupon drop is none of those: it is not rate risk,
it is not symmetric, and its direction is known. Nothing in the record says so today.

**Why it was invisible until now.** No shipped declaration carried a resale price before 016,
so no early exit produced a figure at all; and the two fixtures that could have shown it have
invented schedules with no coupon inside the owner's windows.

The measurement is asserted here so the gap has a number that cannot go stale, and it is
recorded as the `early-exit-ignores-a-coupon-inside-the-window` future entry.
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
end AND collect at least one payment inside the window. Measured 2026-08-31 on the shipped
registry; the horizons are `data/questions/fifty-thousand.toml`'s."""

EARLY_EXIT_CLAIMS = frozenset(
    {
        "early_exit_is_a_point_not_a_distribution",
        "early_exit_spread_is_a_sellers_quote",
        "early_exit_carries_no_rate_risk",
    }
)
"""015 FR-033's three claims, and the reason a fourth is owed: none of them is about a coupon,
none of them is signed the way this omission is."""

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

7.7% on the money deployed, in one month, on a bond whose coupon is 17.1% a year (`auk_proc`
17.1 against a nominal of 1 000, halved for the 182-day period: 85.50). The 3 847.50
is counted twice: once as income and once inside a sale price quoted while it was still
attached.
"""

REACHED = 52802.55
DEPLOYED_UNITS = 45.0


@functools.cache
def _supplied() -> AnswerInputs:
    """The shipped registry, read once. `answers.inputs()` re-resolves the whole data root at
    69 ms a call, and this module reads it once per candidate across seven tests."""
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
    assert [(payment.on, payment.amount.amount) for payment in inside] == [(date(2026, 9, 9), 85.5)]
    access = declared.access[WORKED]
    assert access.quote is not None
    assert access.resale_price is not None
    assert access.quote.price.amount == 1089.32
    assert access.resale_price.price.amount == 1087.89
    assert access.resale_price.kind == "venue_terms"


def test_no_exclusion_states_the_coupon_omission_today() -> None:
    """The half that makes this a gap rather than a stated approximation.

    Over the closed `Exclusion` set, which is where 015 FR-033's three claims live, and over
    the exclusions the owner's own answer actually carries. When a feature states the fourth
    claim, this test is what says so -- and it must be replaced by its opposite rather than
    deleted, because a gap marker quietly removed is a gap nobody remembers.
    """
    assert {item.value for item in Exclusion} & EARLY_EXIT_CLAIMS == EARLY_EXIT_CLAIMS
    assert not [item.value for item in Exclusion if "coupon" in item.value]
    section = answers.answered().sections[0]
    stated = {item.what.value for item in section.excludes}
    assert stated >= EARLY_EXIT_CLAIMS, sorted(stated)
    assert not [name for name in stated if "coupon" in name]


def test_the_engine_reports_the_figure_this_module_calls_overstated() -> None:
    """The finding is load-bearing rather than illustrative: the number in the docstring is the
    one the owner's own question produces, read back off the answer."""
    section = answers.answered().sections[0]
    worked = [item for item in section_evaluated(section) if item.key.instrument_id == WORKED]
    assert len(worked) == 1
    outcome = worked[0]
    assert outcome.sold_early is not None
    assert outcome.sold_early.price_per_unit.amount == 1087.89
    assert outcome.reaches.amount == pytest.approx(REACHED, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(DEPLOYED_UNITS * (85.5 + 1087.89), abs=TOLERANCE)


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
