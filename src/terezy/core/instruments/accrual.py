"""A quotation is a dirty price: what it is clean, and what it is worth on another date.

```text
period(t)   the declared accrual period containing t: [c_i, c_i+1)
accrued(t)  = C_i+1 x  yf(c_i, t) / yf(c_i, c_i+1)   under the declared day count
clean       = quote - accrued(observed_on)
price(t)    = clean + accrued(t)
```

**The clean price is what is assumed constant**, and both legs of a round trip are carried by
this one formula -- the buy quotation to the purchase date, the sell quotation to the sale
date. A coupon between two dates puts them in different periods, so the price drop a
detachment causes falls out of ``price(t)`` rather than standing beside it as a subtraction of
its own.

**The accrual is linear within a period, on the declared day count** (FR-003). The NBU
depository publishes ``pay_date``, ``pay_val`` and ``pay_type`` and nothing about how interest
builds between them, so the issuer's own formula is not available and a linear reading is a
choice. It is stated on the owner's declared belief and in ``docs/METHODOLOGY.md`` §31.5.

**A period runs between two consecutive dates a coupon leaves the price on**, plus the opening
one form declares before its first coupon (:func:`terms.accrual_opens_at`): a bond declared by
its terms opens its first period at its issue date, and one declared by its payments bounds
nothing before its first listed coupon, because ``covers_from`` states where the published list
begins and not when interest began. A date in no period **refuses by name**
(FR-008) rather than being priced from a boundary nobody declared.

The day count enters **only as a ratio of two year fractions inside one period**, which is
what keeps 013 FR-003b standing: a ratio yields no coupon rate, so no issue date can be
extrapolated from it. It is still computed with the declared convention rather than as a ratio
of day counts, because the two part company across a year boundary.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import terms as terms_of
from terezy.core.primitives import conventions, money

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from datetime import date

    from terezy.core.instruments.interface import InstrumentDeclaration
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class Schedule:
    """What an accrual reads: one instrument's coupon dates and amounts, and its day count.

    Gathered into a record rather than passed as four arguments so that a coupon list from one
    declaration cannot reach a day count from another. It is built by :func:`schedule_of` from
    the declaration and the coupon schedule its own plugin produced.
    """

    instrument_id: str
    """Named in every refusal, so a reader is sent to one file rather than to a registry."""

    coupons: tuple[tuple[date, Money], ...]
    """The accrual **boundaries**, ascending, each with the amount that ends the period opening
    at it. Every coupon one unit pays is one, and :func:`schedule_of` may prepend one more that
    ends nothing and carries a zero. Empty is a zero-coupon schedule and is a figure."""

    day_count: str
    """The declared convention. No fallback: ``conventions.day_count`` raises on an unknown
    name, and both terms records require the field, so there is no absent case to guard."""

    declared_by: str
    """The declared term the coupon dates come from, for a refusal's ``second_term``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Carried:
    """A quotation restated as of another date: what it is clean, and what it has accrued."""

    clean: Money
    """``quote - accrued(observed_on)``. The thing the owner's belief assumes constant."""

    accrued: Money
    """``accrued(on)``, at the date the price is wanted for -- or a zero standing for an
    accrual that was never needed, where the quotation was used on the day it was read."""


def schedule_of(
    declaration: InstrumentDeclaration, coupons: tuple[tuple[date, Money], ...]
) -> Schedule:
    """The accrual's view of a declaration, from the coupon schedule its plugin produced.

    ``coupons`` is passed rather than looked up because reaching the instrument registry from
    here would close an import cycle: the registry imports both schedule modules, and both of
    them reach the accrual.

    Where the declaration opens its accrual before its first coupon, that boundary joins the
    list carrying a **zero** amount: it opens a period and ends none, and the amount that sizes
    an accrual is always the one at the period's far end.
    """
    opens = terms_of.accrual_opens_at(declaration.terms)
    boundaries = _merged(coupons)
    if opens is not None and boundaries:
        boundaries = ((opens, money.zero(boundaries[0][1].currency)), *boundaries)
    return Schedule(
        instrument_id=declaration.id,
        coupons=boundaries,
        day_count=terms_of.day_count_of(declaration.terms),
        declared_by=terms_of.coupon_term_of(declaration.terms),
    )


def _merged(coupons: tuple[tuple[date, Money], ...]) -> tuple[tuple[date, Money], ...]:
    """One boundary per date, carrying everything that leaves the price on it.

    Two coupons declared on one date are two payments -- the ledger records them separately and
    the tax layer may assess them under different classes -- and they are **one** boundary:
    both leave the price that morning, so the accrual toward it is sized on their sum. Reading
    only the first would understate every accrual in the period by the rest, silently, which is
    a wrong number rather than a refusal. Reachable through the loader, which refuses a
    decreasing payment list and permits a repeated date.
    """
    merged: list[tuple[date, Money]] = []
    for when, amount in coupons:
        if merged and merged[-1][0] == when:
            merged[-1] = (when, money.add(merged[-1][1], amount))
        else:
            merged.append((when, amount))
    return tuple(merged)


def accrued_on(
    schedule: Schedule, *, on: date, currency: Currency, dated_term: str
) -> Money | InconsistentTerms:
    """What one unit has accrued by ``on``, or the refusal saying why it cannot be known.

    ``dated_term`` names the declared field the date came from, so a refusal names two declared
    facts that cannot both hold rather than one fact and a date from nowhere.
    """
    if not schedule.coupons:
        # FR-009: a zero-coupon schedule accrues nothing on every date by definition. Refusing
        # here would refuse a correct figure, which is the mirror of a silent default.
        return money.zero(currency)
    dates = [when for when, _ in schedule.coupons]
    index = bisect_right(dates, on) - 1
    if index < 0 or index >= len(dates) - 1:
        return _outside(schedule, on=on, dated_term=dated_term)
    start, end = dates[index], dates[index + 1]
    year_fraction = conventions.day_count(schedule.day_count)
    period = year_fraction(start, end)
    if period == 0.0:
        return _no_period(schedule, on=on, start=start, end=end, dated_term=dated_term)
    _, opening = schedule.coupons[index]
    _, closing = schedule.coupons[index + 1]
    # `also_resting_on` the coupon that OPENED the period: its declared date is what the
    # fraction is measured from, so the figure rests on it as much as on the amount it scales.
    return money.also_resting_on(
        money.scale(closing, year_fraction(start, on) / period), opening.provenance
    )


def carried_to(
    schedule: Schedule,
    *,
    quote: Money,
    observed_on: date,
    on: date,
    quoted_term: str,
    dated_term: str,
) -> Carried | InconsistentTerms:
    """A quotation observed on one date, restated as of another.

    Either leg refusing refuses the whole carry: a clean price separated out of a quotation
    whose own accrual is unknown is a number with no arithmetic behind it.
    """
    at_observation = accrued_on(
        schedule, on=observed_on, currency=quote.currency, dated_term=quoted_term
    )
    at_date = (
        at_observation
        if on == observed_on
        else accrued_on(schedule, on=on, currency=quote.currency, dated_term=dated_term)
    )
    if isinstance(at_observation, InconsistentTerms):
        if on == observed_on:
            # **Nothing was carried, so nothing had to be known.** A quotation used on its own
            # observation day IS the price, by observation rather than by model, and refusing
            # it would refuse a figure resting on no assumption at all. Where the accrual is
            # available the split below is reported instead, so this is the unknown-accrual
            # case only and never a cheaper path to the same answer.
            return Carried(clean=quote, accrued=money.zero(quote.currency))
        return at_observation
    if isinstance(at_date, InconsistentTerms):
        return at_date
    return Carried(clean=money.sub(quote, at_observation), accrued=at_date)


def price(carried: Carried) -> Money:
    """What one unit is worth on the date it was carried to."""
    return money.add(carried.clean, carried.accrued)


def _outside(schedule: Schedule, *, on: date, dated_term: str) -> InconsistentTerms:
    """FR-008: a date in no declared coupon period, named with the dates it falls outside."""
    dates = [when for when, _ in schedule.coupons]
    return InconsistentTerms(
        first_term=dated_term,
        second_term=schedule.declared_by,
        reason=(
            f"{schedule.instrument_id!r} is asked for a price as of {on.isoformat()}, which "
            f"falls in none of its declared coupon periods: its coupon dates run from "
            f"{dates[0].isoformat()} to {dates[-1].isoformat()}, and a period is the half-open "
            "interval between two consecutive ones. Nothing before the first and nothing on or "
            "after the last belongs to one. The coverage start is not substituted for a coupon "
            "date -- it states when the published list begins, not when interest began "
            "accruing, and opening the first period there would accrue a full coupon over a "
            "stub. Deriving the true start from the amounts is the invented issue date the "
            "enumerated form exists to refuse."
        ),
    )


def _no_period(
    schedule: Schedule, *, on: date, start: date, end: date, dated_term: str
) -> InconsistentTerms:
    """Two consecutive coupon dates the declared convention puts no year fraction apart.

    30/360 caps a start day at 30 and pulls a 31st back to it, so a pair of adjacent month-end
    dates is zero-length to the convention and non-zero to the schedule. The accrual would be
    a division by that, which is an exception reaching a caller in place of a figure.
    """
    return InconsistentTerms(
        first_term=dated_term,
        second_term=schedule.declared_by,
        reason=(
            f"{schedule.instrument_id!r} is asked for a price as of {on.isoformat()}, in the "
            f"coupon period {start.isoformat()} to {end.isoformat()}, which its declared "
            f"{schedule.day_count!r} convention makes zero years long. An accrual is the "
            "elapsed fraction of its period and there is no fraction of nothing, so the two "
            "declarations -- the payment dates and the convention that measures between them "
            "-- cannot both describe this paper."
        ),
    )


__all__ = ["Carried", "Schedule", "accrued_on", "carried_to", "price", "schedule_of"]
