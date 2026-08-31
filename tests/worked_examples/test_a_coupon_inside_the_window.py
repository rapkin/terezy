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

from datetime import date

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.instruments.interface import EnumeratedTerms
from terezy.core.results.answer import Exclusion
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
"""Bought 2026-09-01 at 1089.32, pays 85.50 on 2026-09-09, sold 2026-10-01 at 1087.89.

85.50 + 1087.89 = 1173.39 against an outlay of 1089.32 -- 7.7% in one month, on a bond whose
coupon is 15.55% a year. The 85.50 is counted twice: once as income, once inside a sale price
quoted while it was still attached.
"""


def _sold_early_with_a_payment_inside(horizon_index: int) -> list[str]:
    answer = answers.answered()
    section = answer.sections[horizon_index]
    start, end = section.horizon.start, section.horizon.end
    declared = answers.inputs().registries.instruments
    found = []
    for item in section_evaluated(section):
        if item.sold_early is None:
            continue
        terms = declared[item.key.instrument_id].terms
        assert isinstance(terms, EnumeratedTerms)
        if any(start < payment.on <= end for payment in terms.payments):
            found.append(item.key.instrument_id)
    return sorted(found)


def test_the_gap_is_reached_at_every_horizon_the_owner_asked_about() -> None:
    measured = tuple(len(_sold_early_with_a_payment_inside(index)) for index in range(3))
    assert measured == AFFECTED_PER_HORIZON


def test_the_worked_instance_is_among_them_at_one_month() -> None:
    assert WORKED in _sold_early_with_a_payment_inside(0)


def test_the_worked_arithmetic_is_what_the_declarations_say() -> None:
    """The numbers in this module's docstring, read back off the files rather than retyped."""
    declared = answers.inputs().registries
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    inside = [
        payment for payment in terms.payments if date(2026, 9, 1) < payment.on <= date(2026, 10, 1)
    ]
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
