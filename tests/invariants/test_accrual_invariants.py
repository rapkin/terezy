"""Properties of the accrual that must hold for every declared schedule, not only the worked one.

The worked example pins three dates on one real issue. These are the claims that must hold
everywhere between them:

* **A quotation carried nowhere is the quotation.** ``price(clean(q, d), d) == q`` for every
  date the schedule can price. This is the identity that makes the clean price a *restatement*
  of the quotation rather than a second figure, and it is what a sign error in either direction
  breaks.
* **Accrual grows inside a period and resets at each coupon date.** ``accrued(c_i) == 0``, and
  ``accrued`` is non-decreasing on ``[c_i, c_i+1)``. A period boundary is where a coupon
  detaches, so the drop is the reset rather than a subtraction standing beside it.
* **It is bounded by the coupon that ends the period**: ``0 <= accrued(t) <= C``, strict at the
  top for the actual-day conventions because the interval is half-open -- the day the coupon is
  worth its whole amount is the day it detaches, and that day opens the next period at zero.
  Not strict under 30/360; :func:`_within_its_coupon` carries the counterexample.

Nothing here invents a tolerance; ``is_close`` from ``primitives.tolerance`` is imported.
"""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise
from typing import Final

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import accrual
from terezy.core.primitives import conventions, money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import DAY_COUNT_FNS
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, is_close

pytestmark = pytest.mark.invariant

UAH = Currency.UAH

DECLARED = prov.of(
    (
        prov.SourceRef(
            id="tests.invariants.test_accrual_invariants",
            citation="a generated schedule, declared by this module",
            retrieved_on=date(2026, 9, 5),
            verified_on=None,
        ),
    )
)
"""A generated schedule is not a citation of anything, but it must carry *some* mark: an
amount built with empty provenance would let this suite pass while the propagation it is
checking had been dropped."""

THIRTY_360: Final = "30/360"
"""The one convention whose upper bound is not strict. Asserted to be a declared name, so a
rename of the convention leaves this module red rather than quietly exempting nothing."""

day_counts = st.sampled_from(sorted(DAY_COUNT_FNS))
amounts = st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False)
quotes = st.floats(min_value=1.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
spans = st.integers(min_value=1, max_value=400)
first_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 1, 1))


@st.composite
def schedules(draw: st.DrawFn) -> tuple[tuple[date, Money], ...]:
    """A coupon schedule of two to six dated per-unit amounts, ascending and distinct."""
    start = draw(first_dates)
    gaps = draw(st.lists(spans, min_size=1, max_size=5))
    amount = draw(amounts)
    dates = [start]
    for gap in gaps:
        dates.append(dates[-1] + timedelta(days=gap))
    return tuple((on, Money(amount, UAH, DECLARED)) for on in dates)


def _schedule(coupons: tuple[tuple[date, Money], ...], day_count: str) -> accrual.Schedule:
    return accrual.Schedule(
        instrument_id="generated",
        coupons=coupons,
        day_count=day_count,
        declared_by="instrument.schedule.payment",
    )


def _assume_measurable(coupons: tuple[tuple[date, Money], ...], day_count: str) -> None:
    """Skip a generated pair of dates the drawn convention puts zero years apart.

    30/360 does that to two adjacent month-end days, and the accrual refuses it by name --
    `tests/unit/test_accrual_refuses.py` is where that refusal is asserted. The properties
    below are about schedules that can be priced at all, so the degenerate draw is excluded
    here rather than absorbed into a weaker claim.
    """
    year_fraction = conventions.day_count(day_count)
    for (start, _), (end, _) in pairwise(coupons):
        assume(year_fraction(start, end) > 0.0)


def _accrued(on: date, coupons: tuple[tuple[date, Money], ...], day_count: str) -> Money:
    figure = accrual.accrued_on(
        _schedule(coupons, day_count),
        on=on,
        currency=UAH,
        dated_term="tests.invariants.test_accrual_invariants",
    )
    assert not isinstance(figure, InconsistentTerms), figure
    return figure


@given(schedules(), day_counts, st.data())
def test_a_quotation_carried_nowhere_is_the_quotation(
    coupons: tuple[tuple[date, Money], ...], day_count: str, data: st.DataObject
) -> None:
    """``price(clean(q, d), d) == q``: the split is a restatement, never a second figure."""
    _assume_measurable(coupons, day_count)
    on = data.draw(_priceable(coupons))
    quote = Money(data.draw(quotes), UAH, DECLARED)
    carried = accrual.carried_to(
        _schedule(coupons, day_count),
        quote=quote,
        observed_on=on,
        on=on,
        quoted_term="access.price.observed_on",
        dated_term="tests.invariants.test_accrual_invariants",
    )
    assert not isinstance(carried, InconsistentTerms), carried
    assert is_close(accrual.price(carried).amount, quote.amount)
    # The mark survives the round trip: the clean price rests on the quotation and on the
    # declared coupon the accrual came out of, and neither is laundered by the subtraction.
    assert quote.provenance.sources <= carried.clean.provenance.sources
    if carried.accrued.amount != 0.0:
        assert DECLARED.sources <= carried.clean.provenance.sources


@st.composite
def _priceable(draw: st.DrawFn, coupons: tuple[tuple[date, Money], ...]) -> date:
    """A date inside some declared coupon period of this schedule."""
    index = draw(st.integers(min_value=0, max_value=len(coupons) - 2))
    start, end = coupons[index][0], coupons[index + 1][0]
    return draw(st.dates(min_value=start, max_value=end - timedelta(days=1)))


@given(schedules(), day_counts)
def test_the_accrual_resets_to_zero_on_every_coupon_date(
    coupons: tuple[tuple[date, Money], ...], day_count: str
) -> None:
    """``accrued(c_i) == 0``. A coupon date opens its own period: the coupon has just left."""
    _assume_measurable(coupons, day_count)
    for on, _ in coupons[:-1]:
        assert _accrued(on, coupons, day_count).amount == 0.0


@given(schedules(), day_counts, st.data())
def test_the_accrual_is_non_decreasing_inside_a_period_and_bounded_by_its_coupon(
    coupons: tuple[tuple[date, Money], ...], day_count: str, data: st.DataObject
) -> None:
    """``0 <= accrued(t) < C`` and monotone in ``t`` within one period."""
    _assume_measurable(coupons, day_count)
    earlier = data.draw(_priceable(coupons))
    later = data.draw(st.dates(min_value=earlier, max_value=coupons[-1][0] - timedelta(days=1)))
    at_earlier = _accrued(earlier, coupons, day_count).amount
    at_later = _accrued(later, coupons, day_count).amount
    coupon = coupons[0][1].amount
    assert _within_its_coupon(at_earlier, coupon, day_count), (earlier, at_earlier, coupon)
    assert _within_its_coupon(at_later, coupon, day_count), (later, at_later, coupon)
    if _period_of(earlier, coupons) == _period_of(later, coupons):
        assert at_later >= at_earlier - TOLERANCE


def _within_its_coupon(accrued: float, coupon: float, day_count: str) -> bool:
    """Whether an accrual is inside the coupon that ends its period, on this convention.

    Strict for the actual-day conventions. **Not strict for 30/360**, where the last day of a
    long month is only pulled back to the 30th when the period *started* on a 30th or 31st
    (ISDA 2006 Definitions section 4.16(f), "30/360" / Bond Basis: D1 = 30 if D1 = 31; D2 = 30
    only if D2 = 31 and D1 is 30 or 31). So 2020-07-01 -> 2021-01-31 and 2020-07-01 ->
    2021-02-01 both count 360 - 180 + 30 = 210 days, and the accrual on the 31st is the whole
    coupon a day before it detaches. `tests/worked_examples/test_day_count.py` works that pair
    out on the calendar; widening the bound for the other two conventions would let a real
    off-by-one period through.
    """
    if accrued < 0.0:
        return False
    if day_count == THIRTY_360:
        return accrued <= coupon + TOLERANCE
    return accrued < coupon


def test_the_convention_exempted_from_the_strict_bound_is_one_the_engine_declares() -> None:
    """The bound is widened for one name; a rename that left it matching nothing would make the
    widening vacuous rather than red."""
    assert THIRTY_360 in DAY_COUNT_FNS


def _period_of(on: date, coupons: tuple[tuple[date, Money], ...]) -> int:
    """Which declared period contains this date, computed here rather than asked of the module
    under test: a monotonicity claim checked against the module's own period lookup would pass
    whatever that lookup did."""
    return max(index for index, (start, _) in enumerate(coupons) if start <= on)


@given(schedules(), day_counts, st.data())
def test_a_zero_coupon_schedule_carries_the_quotation_unchanged(
    coupons: tuple[tuple[date, Money], ...], day_count: str, data: st.DataObject
) -> None:
    """A schedule declaring no coupon accrues nothing, on every date, and refuses nothing.

    The generated schedule supplies the *dates* the quotation and the sale fall on; what is
    under test is that an empty coupon list is a legitimate zero rather than an absence.
    """
    quote = Money(data.draw(quotes), UAH, DECLARED)
    observed = data.draw(st.dates(min_value=coupons[0][0], max_value=coupons[-1][0]))
    on = data.draw(st.dates(min_value=coupons[0][0], max_value=coupons[-1][0]))
    carried = accrual.carried_to(
        accrual.Schedule(
            instrument_id="zero-coupon",
            coupons=(),
            day_count=day_count,
            declared_by="instrument.schedule.payment",
        ),
        quote=quote,
        observed_on=observed,
        on=on,
        quoted_term="access.price.observed_on",
        dated_term="tests.invariants.test_accrual_invariants",
    )
    assert not isinstance(carried, InconsistentTerms), carried
    assert carried.accrued == money.zero(UAH)
    assert carried.clean == quote
    assert accrual.price(carried).amount == quote.amount
