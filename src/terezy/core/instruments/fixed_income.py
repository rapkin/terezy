"""``fixed_income``: the closed-form coupon and principal schedule of a bond, as events.

The arithmetic this whole feature exists to get right, and it is deliberately small
enough to check on paper. Every coupon is

    face_value x coupon_rate x year_fraction(previous accrual date, this accrual date)

multiplied by the units held, where the year fraction comes from the issue's **declared**
day-count convention and the coupon dates come from its **declared** periodicity. Nothing
here is fixed in the engine: a second issue with a different frequency and a different day
count is a data file and no code change (FR-021, SC-012), which is the property SC-003
exists to prove.

**Accrual is measured on unadjusted dates; only the payment date moves.** The declared
business-day rule is applied to the date money changes hands, not to the period interest
accrued over. Adjusting the accrual boundary as well would make every coupon depend on
where weekends fell, and two economically identical bonds would pay different amounts --
which is not what a fixed-coupon bond does. The consequence is visible in the D1 worked
example, where the final coupon of a Saturday maturity is paid on the Monday and is
nonetheless the ordinary 184-day amount.

**Gross amounts only.** No tax is netted here (that is a ``ChargeFn``'s job downstream)
and no route or access cost is applied (per Principle VI those belong to
``(instrument x income stream x route)``, never to the instrument alone).

**The coupon policy** (FR-019) is a declared assumption, and the two policies are two
functions in :data:`COUPON_POLICY_FNS` rather than a branch: ``hold_cash`` buys nothing and
``reinvest`` buys whole units. Three things about it are decisions rather than arithmetic
and are worth stating where the code is.

*"The yield available on the coupon date" is the issue's own declared rate, and the price
is therefore par.* This feature declares exactly one yield and has no yield curve -- the
contract lists pricing off a curve among the things deliberately absent -- and a unit bought
at face value is the only unit that earns exactly the declared rate. Any other price would
be a market quote, and there is none to be had; inventing one would be a fabricated number
in the middle of the figure the project exists to produce.

*Whole units only, and the remainder is retained rather than discarded* (FR-020). A
fractional bond does not exist, so the coupon buys ``floor(coupon / (face x min_unit))``
increments and what is left stays in the cash balance. Every coupon reports the decision --
:class:`Reinvestment` carries the units bought, the money spent, the money retained and the
reason -- so a coupon too small to buy anything is a *stated* outcome rather than an absence.
A reinvestment that would fall below the declared ``min_ticket`` buys nothing for the same
reason a purchase below it is refused (FR-018): the constraint is enforced, not assumed.

*The final coupon is not reinvested.* It is paid on the maturity date, and a unit bought
that day would be redeemed the same day -- a round trip that never happened.

**The reinvestment is sized on the gross coupon**, because an instrument does not know its
tax: tax is charged downstream by a ``ChargeFn``, and the whole point of that ordering is
that a tax rule cannot change the basis it is charged on. Under this feature's exempt class
gross and net coincide, so the two are the same number. Under a *taxed* class they would
not, and reinvesting the gross coupon would spend money that went to the tax authority --
visible as a negative cash balance, which the ledger permits and never clamps, rather than
hidden. Sizing it on the net amount needs the charge to be known before the schedule
exists, which is a different pipeline than the one research.md D3 chose.

**Reinvestment is caused by an instrument term, and the policy is named in the detail.**
``CausationKind`` admits no "the owner decided something" member, so a reinvestment names
the term that priced it, as the purchase already names the term it acquired, and its
``detail`` states the declared policy, the coupon that funded it and the remainder retained.

**No cash deposit funds the purchase.** The cash balance goes negative on the purchase
date and recovers as coupons arrive, and that is the honest ledger for a feature whose
spec says "the purchase is taken as given". Inventing a funding deposit would need an event
caused by an owner action, and there is no such ``CausationKind`` member.

**Deliberately absent rather than stubbed**: secondary-market sale before maturity, the
thin-market haircut that would apply to one, accrued interest settled at purchase,
restructuring, and pricing future purchases off a yield curve. Each is named in the spec
as a later feature, and a stub would invite a caller to depend on it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from terezy.core.errors import (
    InconsistentTerms,
    InfeasiblePurchase,
    InstrumentFailure,
)
from terezy.core.instruments import acquire
from terezy.core.instruments import terms as terms_of
from terezy.core.instruments.interface import BondTerms
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import conventions, money
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close

if TYPE_CHECKING:  # pragma: no cover -- import-time cycle avoidance
    from terezy.core.instruments.interface import (
        Assumptions,
        DateRange,
        EarlyExit,
        Holding,
        InstrumentConstraints,
        InstrumentDeclaration,
    )
    from terezy.core.tax.interface import TaxableEventKind

# Most of the records this module reads are needed only by the type checker -- nothing here
# constructs an ``Assumptions`` or a ``Holding`` -- so a type-only import keeps the reference
# where it is useful and out of the runtime graph. ``BondTerms`` is the exception: it is
# passed to ``terms.narrowed`` as a value. Neither import is a cycle; the registry is what
# imports this module.


def events(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
    early_exit: EarlyExit | None,
) -> tuple[Event, ...] | InstrumentFailure:
    """The purchase, every coupon, any reinvestment, and the way the position closes.

    It closes at maturity where the horizon reaches it, and at ``horizon.end`` -- sold at the
    declared resale price -- where it does not (015 FR-029). Handed no price for a window that
    ends first, the refusal names ``access.resale_price`` rather than the maturity date: the
    money **can** be withdrawn at a spread, so what is missing is the spread and not the window.

    ``assumptions`` is read for exactly one thing: the declared coupon policy (FR-019).
    Everything else in the schedule is contractual -- the bond's terms and the owner's
    purchase decide it, and there is no third input that could change the answer.

    The stream is built in one pass with a running sequence number, because a reinvestment
    is interleaved behind the coupon that funded it and numbering the coupons first would
    mean renumbering them all. Nothing may hold a sequence number across that boundary.

    Failure is typed and specific. Every guard below returns a value naming what
    conflicts with what, rather than raising or returning an empty tuple -- an empty
    tuple means "legitimately no events in this horizon", which is a different claim
    entirely.
    """
    problem = _check_feasible(declaration, holding, horizon)
    if problem is not None:
        return problem

    terms = terms_of.narrowed(declaration, BondTerms)
    adjust = conventions.business_day_rule(terms.business_day_rule)
    redeems_on = adjust(terms.maturity_date)
    sells_early = horizon.end < redeems_on
    if sells_early and early_exit is None:
        return InconsistentTerms(
            first_term="horizon.end",
            second_term="access.resale_price",
            reason=(
                f"the horizon ends {horizon.end.isoformat()} but {declaration.id!r} redeems "
                f"{redeems_on.isoformat()}"
                + (
                    f" (the declared maturity {terms.maturity_date.isoformat()} moved by "
                    f"the {terms.business_day_rule!r} rule)"
                    if redeems_on != terms.maturity_date
                    else ""
                )
                + ", so the position is sold at the end of the window -- and no declaration "
                "says what it sells for. The price is not inferred: face value is what the "
                "issue repays and the purchase quote is what a unit costs, and striking a "
                "sale at either would report a spread of zero that nobody observed."
            ),
        )
    stream = [acquire.purchase(declaration, holding, sequence=1)]
    units = holding.quantity
    for period in coupon_plan(declaration, holding, assumptions):
        if sells_early and period.paid_on > horizon.end:
            # Ascending by payment date, so the first one past the window ends the schedule:
            # a later period's reinvestment must not add units the sale then surrenders.
            break
        stream.append(_coupon(declaration, holding, period, sequence=len(stream) + 1))
        if period.reinvestment.units_bought > 0.0:
            stream.append(_reinvestment(declaration, holding, period, sequence=len(stream) + 1))
        units += period.reinvestment.units_bought
    stream.append(
        acquire.early_sale(
            declaration,
            holding,
            units,
            on=horizon.end,
            exit_=early_exit,
            sequence=len(stream) + 1,
        )
        if sells_early and early_exit is not None
        else _redemption(declaration, holding, units, sequence=len(stream) + 1)
    )
    return tuple(stream)


def tax_classes(declaration: InstrumentDeclaration) -> Mapping[TaxableEventKind, str]:
    """Which declared class governs each kind of income this instrument produces.

    A projection of the declaration, and that is the point: the mapping is *declared*,
    so a new issue sharing an existing class is a data change. A function rather than a
    field access at the call site because a later instrument class may derive part of
    the mapping from its terms -- a fund whose distributions are taxed by what it holds
    -- and the interface should not have to change when one does.
    """
    return declaration.tax_classes


def constraints(declaration: InstrumentDeclaration) -> InstrumentConstraints:
    """The feasibility constraints a purchase of this instrument must satisfy."""
    return declaration.constraints


def _check_feasible(
    declaration: InstrumentDeclaration,
    holding: Holding,
    horizon: DateRange,
) -> InstrumentFailure | None:
    """Every reason this holding cannot be projected, in the order a reader would ask.

    Returns ``None`` when there is nothing wrong. ``None`` here is not a degraded outcome
    needing a reason of its own -- it is the absence of a failure, and the caller's next
    line is the schedule.

    Grouped into three checks by subject -- the instrument's own terms, the purchase, the
    horizon -- and the **first** problem found is the one reported. Reporting only one is
    deliberate: a reader fixing a purchase below the minimum ticket does not need to be
    told simultaneously that their horizon is short, and a list of failures invites a
    caller to handle "the first one" anyway.
    """
    for problem in (
        _terms_problem(declaration),
        _purchase_problem(declaration, holding),
        _horizon_problem(holding, horizon),
    ):
        if problem is not None:
            return problem
    return None


def _terms_problem(declaration: InstrumentDeclaration) -> InstrumentFailure | None:
    """Whether the instrument's own declared terms can hold at all."""
    terms = terms_of.narrowed(declaration, BondTerms)
    if terms.maturity_date <= terms.issue_date:
        return InconsistentTerms(
            first_term="instrument.maturity_date",
            second_term="instrument.issue_date",
            reason=(
                f"{declaration.id!r} matures {terms.maturity_date.isoformat()}, on or "
                f"before its issue date {terms.issue_date.isoformat()}. No schedule "
                "exists for such an instrument, and a zero-length schedule would be a "
                "different and false claim -- it would report a holding that pays "
                "nothing."
            ),
        )
    return None


def _purchase_problem(
    declaration: InstrumentDeclaration,
    holding: Holding,
) -> InstrumentFailure | None:
    """Whether this purchase of that instrument is possible and permitted.

    The minimum ticket is checked last of the five, because the other four describe a
    purchase that is not a purchase at all -- no units, no money, or a date outside the
    instrument's life -- and reporting a shortfall against a ticket would be answering a
    question the caller has not yet managed to ask.
    """
    terms = terms_of.narrowed(declaration, BondTerms)
    if holding.quantity <= 0.0:
        return InconsistentTerms(
            first_term="holding.quantity",
            second_term="instrument.min_unit",
            reason=(
                f"a purchase of {holding.quantity!r} units of {declaration.id!r} "
                "acquires nothing. A holding must acquire a positive number of units; "
                "the quantity is rejected rather than rounded up to the minimum unit, "
                "because rounding it would spend money nobody agreed to spend."
            ),
        )
    if holding.cost.amount <= 0.0:
        return InconsistentTerms(
            first_term="holding.cost",
            second_term="holding.quantity",
            reason=(
                f"{holding.quantity!r} units of {declaration.id!r} were acquired for "
                f"{holding.cost.amount!r} {holding.cost.currency.value}. A purchase that "
                "costs nothing has no basis, so every figure derived from it -- the "
                "yield above all -- would be meaningless rather than merely large."
            ),
        )
    if holding.purchased_on < terms.issue_date:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.issue_date",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, "
                f"before it was issued on {terms.issue_date.isoformat()}"
            ),
        )
    if holding.purchased_on >= terms.maturity_date:
        return InconsistentTerms(
            first_term="holding.purchased_on",
            second_term="instrument.maturity_date",
            reason=(
                f"{declaration.id!r} was bought {holding.purchased_on.isoformat()}, on "
                f"or after it matures on {terms.maturity_date.isoformat()}. There is "
                "nothing left to hold."
            ),
        )
    minimum = declaration.constraints.min_ticket
    if money.compare(holding.cost, minimum) < 0:
        return InfeasiblePurchase(
            constraint="min_ticket",
            required=minimum,
            actual=holding.cost,
            shortfall=money.sub(minimum, holding.cost),
            reason=(
                f"{declaration.id!r} requires at least {minimum.amount!r} "
                f"{minimum.currency.value} per purchase; {holding.cost.amount!r} was "
                f"offered, which is {money.sub(minimum, holding.cost).amount!r} short. "
                "The amount is reported as it stands and is not adjusted to fit: "
                "rounding it up would spend money the owner did not agree to spend, and "
                "rounding it down would report a return on a holding that was never "
                "bought."
            ),
        )
    return None


def _horizon_problem(holding: Holding, horizon: DateRange) -> InstrumentFailure | None:
    """Whether the window asked about can contain the purchase at all -- on **both** sides.

    Whether it also reaches the final payment is checked in :func:`events`, once the adjusted
    payment dates are known: a business-day rule can move the last flow past a horizon that
    looked long enough against the unadjusted maturity, and under 015 FR-029 that is a sale
    rather than a refusal. What is *not* a sale is a window that closes before the money
    arrives, which the hold-to-maturity refusal used to cover implicitly.
    """
    if horizon.end < horizon.start:
        return InconsistentTerms(
            first_term="horizon.start",
            second_term="horizon.end",
            reason=(
                f"the horizon runs backwards: it starts {horizon.start.isoformat()} and "
                f"ends {horizon.end.isoformat()}"
            ),
        )
    if horizon.start > holding.purchased_on:
        return InconsistentTerms(
            first_term="horizon.start",
            second_term="holding.purchased_on",
            reason=(
                f"the horizon starts {horizon.start.isoformat()}, after the purchase on "
                f"{holding.purchased_on.isoformat()}. The purchase is the origin of every "
                "time measurement in the result, so a horizon that excludes it would "
                "measure returns from a date on which nothing was bought."
            ),
        )
    if horizon.end < holding.purchased_on:
        return InconsistentTerms(
            first_term="horizon.end",
            second_term="holding.purchased_on",
            reason=(
                f"the horizon ends {horizon.end.isoformat()}, before the purchase settles on "
                f"{holding.purchased_on.isoformat()} -- the way in's declared latency runs "
                "past the window. Under 015 FR-029 the position is sold at the window's end, "
                "and a sale of something never bought is not a figure."
            ),
        )
    return None


HOLD_CASH: Final = "hold_cash"
"""The coupon policy that spends nothing: the money stays in the cash balance."""

REINVEST: Final = "reinvest"
"""The coupon policy that buys whole units at the declared yield on the coupon date."""

CouponPolicyFn = Callable[[Money, Money, float], float]
"""How many units a coupon buys: ``(coupon, price per unit, minimum unit) -> units``.

A function of three amounts and nothing else. It is deliberately not given the declaration
or the date: a policy decides *how much of a coupon to spend*, and letting it see the issue
would let a policy branch on the instrument, which is the Principle II violation the
registry exists to prevent.
"""


def _hold_as_cash(_coupon: Money, _price_per_unit: Money, _min_unit: float) -> float:
    """``hold_cash``: buy nothing. The coupon stays where it was paid.

    Zero units rather than "no decision": the policy ran, and this is its answer. Every
    argument is unused, which is the point -- holding cash does not depend on the price.
    """
    return 0.0


def _reinvest_whole_units(coupon: Money, price_per_unit: Money, min_unit: float) -> float:
    """``reinvest``: as many whole increments as the coupon covers, and no fraction.

    A fractional bond does not exist, so this floors. The one subtlety is that it floors a
    *float* ratio: an exact multiple can land a hair below itself in binary floating point,
    and a bare ``floor`` would then throw away a whole unit the owner could actually buy --
    a real unit lost to representation rather than to the minimum-unit rule. So a ratio
    within the single project tolerance of a whole number is treated as that whole number.
    The tolerance is imported, never redefined (FR-002).

    The coupon is non-negative by construction -- positive face, non-negative rate,
    positive year fraction -- so the floor of the ratio is non-negative and nothing is
    clamped here. The price and the minimum unit are positive because the data boundary
    refuses anything else (``loader._positive``), which is why the division is written
    without a guard: a zero here could only come from a declaration built in code, and that
    is a programmer error rather than a fact about the money.
    """
    increments = coupon.amount / (price_per_unit.amount * min_unit)
    nearest = round(increments)
    whole = nearest if is_close(increments, float(nearest)) else math.floor(increments)
    return whole * min_unit


COUPON_POLICY_FNS: Final[Mapping[str, CouponPolicyFn]] = {
    HOLD_CASH: _hold_as_cash,
    REINVEST: _reinvest_whole_units,
}
"""The coupon policies this instrument class implements. Exactly the two FR-019 names.

A mapping of functions rather than subclass dispatch or an ``if`` on the policy name
(owner decision D-E), so the set of implemented policies is one readable line and adding a
third -- sweeping accumulated cash, say -- is an entry and a function rather than another
branch in the schedule generator.
"""


def coupon_policy(name: str) -> CouponPolicyFn:
    """The policy a declared name selects, or a raise naming it and what is known.

    An explicit membership test rather than ``dict.get`` with a default, exactly as
    ``primitives.conventions`` does: there is no default policy, because the two policies
    give different terminal amounts (SC-010) and defaulting would make one of the two
    answers the one you get by not thinking about it.
    """
    if name not in COUPON_POLICY_FNS:
        raise KeyError(
            f"unknown coupon policy {name!r}. There is no default policy: what happens to "
            f"a coupon changes the answer, so a run must state it. Known policies: "
            f"{sorted(COUPON_POLICY_FNS)}"
        )
    return COUPON_POLICY_FNS[name]


@dataclass(frozen=True, slots=True)
class Reinvestment:
    """What the declared policy did with one coupon, including when it did nothing.

    Always present on a :class:`CouponPeriod`, never ``None``. "The policy considered this
    coupon and bought nothing" and "nothing was considered" are different claims, and
    FR-020 asks for the remainder to be *reported* -- so a coupon too small to buy a whole
    unit is a stated outcome carrying its reason, not an absence a reader has to interpret.
    """

    units_bought: float
    """Whole increments of ``min_unit`` acquired. ``0.0`` under ``hold_cash``, and under
    ``reinvest`` whenever the coupon does not cover one increment or one minimum ticket."""

    price_per_unit: Money
    """What a unit cost: the declared face value. See the module docstring on why par."""

    reinvested: Money
    """``units_bought x price_per_unit`` -- the money spent, as a positive amount."""

    retained_as_cash: Money
    """``coupon - reinvested`` -- the unreinvested remainder, which stays in the balance.

    Never discarded and never rounded away (FR-020). It is a positive amount, and it equals
    the whole coupon whenever nothing was bought.
    """

    reason: str
    """Why this many units and no more, in plain language, quoting the figures.

    Written for the output rather than for a log: FR-017 requires a degraded outcome to
    carry its reason, and "the coupon of 768.63 does not cover one unit at 1 000.00" is the
    sentence that makes the retained cash comprehensible instead of surprising.
    """


@dataclass(frozen=True, slots=True)
class CouponPeriod:
    """One accrual period of a holding: what it paid, and what was done with the payment.

    The closed form as a *value*, before it becomes events (research.md D3). Producing it
    separately is what lets a hand-computed example check the arithmetic in isolation, and
    what lets a reader ask what happened to a coupon without folding a ledger first.
    """

    accrual_start: date
    """Start of the period interest accrued over. Unadjusted."""

    accrual_end: date
    """End of the period interest accrued over. Unadjusted -- only the payment moves."""

    paid_on: date
    """The date money changed hands, after the declared business-day rule."""

    year_fraction: float
    """The declared day count's fraction of a year for this period."""

    units_held: float
    """Units accruing over this period: the purchase, plus every earlier reinvestment."""

    coupon: Money
    """``face x rate x year_fraction x units_held``, resting on the declared terms."""

    reinvestment: Reinvestment
    """What the declared coupon policy did with :attr:`coupon`."""


def coupon_plan(
    declaration: InstrumentDeclaration,
    holding: Holding,
    assumptions: Assumptions,
) -> tuple[CouponPeriod, ...]:
    """Every coupon this holding is paid, in payment order, with the policy's decision.

    A pure fold over the declared coupon dates carrying the running unit count, because
    under ``reinvest`` each coupon is a function of what the earlier ones bought. Under
    ``hold_cash`` the count never moves and the fold degenerates to the contractual
    schedule, which is why one function serves both policies.

    Coupons dated on or before the purchase date were paid to whoever held the bond then,
    so they are not this holding's income. The coupon straddling the purchase is
    nonetheless paid to this holder **in full**: accrued interest settled at purchase is a
    secondary-market mechanic this feature does not model, and apportioning the coupon
    without modelling the settlement that pays for it would invent a cash flow. A
    reinvested unit is treated the same way -- it is the holder of record on the next
    coupon date, so it receives that whole coupon -- which is the same convention applied
    consistently rather than a second rule.

    Payment dates keep their ascending order after adjustment because consecutive coupon
    dates are whole months apart and every implemented business-day rule moves a date by
    at most a few days, so the stream cannot fold out of order.

    Assumes the terms hold. :func:`events` checks them first and reports
    ``InconsistentTerms``; called directly on an impossible instrument this raises from the
    conventions, which is the right answer for a programmer error and the wrong one for a
    caller who should have been given a typed failure.
    """
    terms = terms_of.narrowed(declaration, BondTerms)
    if terms.coupon_rate == 0.0:
        # A zero-coupon bond, which is a valid declaration and not a missing rate. It pays
        # its principal and nothing else, and emitting a stream of zero-amount coupon
        # periods would clutter every schedule with rows that never paid -- and would offer
        # a reinvestment policy a coupon of nothing to spend.
        return ()

    year_fraction = conventions.day_count(terms.day_count)
    adjust = conventions.business_day_rule(terms.business_day_rule)
    schedule = conventions.periodicity(terms.periodicity)(terms.issue_date, terms.maturity_date)
    buy = coupon_policy(assumptions.coupon_policy)

    periods: list[CouponPeriod] = []
    units = holding.quantity
    accrual_start = terms.issue_date
    for accrual_end in schedule:
        if accrual_end > holding.purchased_on:
            fraction = year_fraction(accrual_start, accrual_end)
            coupon = _coupon_amount(terms, units, fraction)
            decision = _decide(declaration, coupon, buy, accrual_end=accrual_end)
            periods.append(
                CouponPeriod(
                    accrual_start=accrual_start,
                    accrual_end=accrual_end,
                    paid_on=adjust(accrual_end),
                    year_fraction=fraction,
                    units_held=units,
                    coupon=coupon,
                    reinvestment=decision,
                )
            )
            units += decision.units_bought
        accrual_start = accrual_end
    return tuple(periods)


def _decide(
    declaration: InstrumentDeclaration,
    coupon: Money,
    buy: CouponPolicyFn,
    *,
    accrual_end: date,
) -> Reinvestment:
    """Apply the policy to one coupon, and say in words what it decided and why.

    Two refusals sit here rather than in a policy function, because neither is a property
    of the policy:

    * **The last coupon is never reinvested.** It is paid on the maturity date, so a unit
      bought with it would be redeemed the same day -- a round trip that never happened.
    * **A reinvestment below the declared minimum ticket buys nothing.** A reinvestment is
      a purchase, and FR-018 says a purchase violating a declared constraint is reported
      rather than silently adjusted to fit. Buying anyway would execute a ticket the venue
      would refuse; rounding up would spend money the owner does not have.

    **The policy is asked first, and the refusals apply only to what it wanted to buy.**
    The order matters for honesty rather than for arithmetic: under ``hold_cash`` nothing
    was going to be bought anyway, so reporting the maturity date as the reason would blame
    the calendar for a decision the policy made -- a plausible explanation that would send a
    reader looking for a bug in the wrong place.
    """
    terms = terms_of.narrowed(declaration, BondTerms)
    constraints = declaration.constraints
    price = terms.face_value

    units = buy(coupon, price, constraints.min_unit)
    if units <= 0.0:
        return _retain_everything(coupon, price, reason=_bought_nothing(declaration, coupon))

    if accrual_end >= terms.maturity_date:
        return _retain_everything(
            coupon,
            price,
            reason=(
                f"the coupon of {coupon.amount!r} {coupon.currency.value} is paid on the "
                f"maturity date {terms.maturity_date.isoformat()} and is retained as cash: "
                f"the {units!r} unit(s) the policy would buy with it would be redeemed the "
                "same day, so reinvesting it would record a round trip that never happened."
            ),
        )

    spent = money.scale_sourced(price, units, terms.provenance)
    if money.compare(spent, constraints.min_ticket) < 0:
        return _retain_everything(
            coupon,
            price,
            reason=(
                f"reinvesting {units!r} unit(s) would cost {spent.amount!r} "
                f"{spent.currency.value}, below the declared minimum ticket of "
                f"{constraints.min_ticket.amount!r}. A reinvestment is a purchase, so the "
                "constraint is enforced rather than assumed (FR-018): the coupon is "
                "retained as cash instead of buying a ticket the venue would refuse."
            ),
        )
    return Reinvestment(
        units_bought=units,
        price_per_unit=price,
        reinvested=spent,
        retained_as_cash=money.sub(coupon, spent),
        reason=(
            f"the coupon of {coupon.amount!r} {coupon.currency.value} buys {units!r} whole "
            f"unit(s) at the declared face value of {price.amount!r}, which is the price at "
            f"which a unit earns the declared {terms.coupon_rate!r} per annum. "
            f"{money.sub(coupon, spent).amount!r} is retained as cash (FR-020)."
        ),
    )


def _bought_nothing(declaration: InstrumentDeclaration, coupon: Money) -> str:
    """Why a policy bought nothing: because it could not, or because it chose not to.

    Two different facts, and the sentence has to say which. Derived from the **numbers**
    rather than from the policy's name: whether the coupon covers one increment is a
    property of the coupon and the price, so this stays true for a policy nobody has written
    yet. Branching on the name here would put the set of policies in two places -- the
    registry and a message -- and the second copy is the one that would go stale.
    """
    terms = terms_of.narrowed(declaration, BondTerms)
    constraints = declaration.constraints
    price = terms.face_value
    increment = money.scale_sourced(price, constraints.min_unit, terms.provenance)
    common = (
        f"the coupon of {coupon.amount!r} {coupon.currency.value} is retained as cash in "
        "full (FR-020): it is neither discarded nor spent on a fraction of a bond, because "
        "a fraction of a bond does not exist"
    )
    if money.compare(coupon, increment) < 0:
        return (
            f"{common}. It does not cover one whole increment of "
            f"{constraints.min_unit!r} unit(s) at {price.amount!r} per unit."
        )
    return (
        f"{common}. It would cover an increment of {constraints.min_unit!r} unit(s) at "
        f"{price.amount!r} per unit, and the declared coupon policy bought nothing from it."
    )


def _retain_everything(coupon: Money, price_per_unit: Money, *, reason: str) -> Reinvestment:
    """The decision to buy nothing, with the whole coupon recorded as retained.

    Built in one place so that every "bought nothing" outcome reports the remainder the
    same way. ``money.scale(coupon, 0.0)`` rather than ``money.zero`` for the amount spent:
    a zero derived from this coupon keeps the coupon's provenance, and a zero resting on no
    source would claim the figure came from nowhere.
    """
    return Reinvestment(
        units_bought=0.0,
        price_per_unit=price_per_unit,
        reinvested=money.scale(coupon, 0.0),
        retained_as_cash=coupon,
        reason=reason,
    )


def _coupon(
    declaration: InstrumentDeclaration,
    holding: Holding,
    period: CouponPeriod,
    *,
    sequence: int,
) -> Event:
    """One coupon: face x rate x year fraction x units, resting on the declared terms."""
    terms = terms_of.narrowed(declaration, BondTerms)
    return Event(
        sequence=sequence,
        occurred_on=period.paid_on,
        kind=EventKind.COUPON,
        amount=period.coupon,
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:coupon_rate",
            detail=(
                f"coupon at {terms.coupon_rate!r} per annum on {period.units_held!r} "
                f"unit(s) accrued {period.accrual_start.isoformat()} to "
                f"{period.accrual_end.isoformat()} on {terms.day_count!r}, paid "
                f"{period.paid_on.isoformat()} under the {terms.business_day_rule!r} rule"
            ),
        ),
        lot_ref=None,
        quantity=None,
        allocated_to=None,
        capacity_pool=None,
    )


def reinvestment_lot_id_for(instrument_id: str, paid_on: date) -> str:
    """The identity of a lot a reinvested coupon opens: instrument and payment date.

    Derived rather than generated, for the reason `acquire.lot_id_for` gives -- the core has
    no counter and no clock, and two runs of the same scenario must produce the same lot
    ids or the determinism digest compares two different-looking results (C4). The suffix
    keeps it distinct from the lot a purchase on the same date would open, so the two can
    never be mistaken for one acquisition.
    """
    return f"{instrument_id}@{paid_on.isoformat()}#reinvested"


def _reinvestment(
    declaration: InstrumentDeclaration,
    holding: Holding,
    period: CouponPeriod,
    *,
    sequence: int,
) -> Event:
    """Cash out and a new lot in, funded by the coupon just paid (FR-019).

    Dated on the coupon's **payment** date rather than its accrual end: the money has to
    arrive before it can be spent, and dating the purchase earlier would spend a coupon the
    business-day rule has not yet delivered.

    A distinct event kind from a purchase, because the two answer different questions of
    the projection -- how much was put in from outside, and how much of the return was
    ploughed back -- and the schedule reports them as separate lines for the same reason.
    """
    decision = period.reinvestment
    return Event(
        sequence=sequence,
        occurred_on=period.paid_on,
        kind=EventKind.REINVESTMENT,
        amount=money.scale(decision.reinvested, -1.0),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:reinvestment",
            detail=(
                f"reinvestment of the coupon paid {period.paid_on.isoformat()}: {decision.reason}"
            ),
        ),
        lot_ref=LotRef(
            instrument_id=declaration.id,
            lot_id=reinvestment_lot_id_for(declaration.id, period.paid_on),
        ),
        quantity=decision.units_bought,
        allocated_to=None,
        capacity_pool=None,
    )


def _coupon_amount(terms: BondTerms, quantity: float, fraction: float) -> Money:
    """``face x rate x fraction x units``, carrying the terms it was computed from.

    Through ``money.scale_sourced`` rather than ``money.scale``, because the rate and the
    day-count fraction are *declared* values: the factor has sources of its own, and
    ``scale`` would carry only the face value's. The two usually coincide -- a file
    declares face and coupon in one table -- and relying on that coincidence is how a
    mark gets lost the day they are separated.
    """
    return money.scale_sourced(
        terms.face_value,
        terms.coupon_rate * fraction * quantity,
        terms.provenance,
    )


def _redemption(
    declaration: InstrumentDeclaration,
    holding: Holding,
    quantity: float,
    *,
    sequence: int,
) -> Event:
    """The principal at maturity: cash in, units surrendered.

    ``quantity`` is passed rather than read off the holding, because under a reinvesting
    policy it is not the quantity that was bought: every unit acquired along the way is
    redeemed too. Taking it from the holding would redeem the original purchase and leave
    the reinvested lots held forever -- a position that never closes, and a yield computed
    against principal that never came back.

    Redemption is a **disposal**, not a cash receipt. It consumes basis and realises a
    gain or a loss, which is why it carries a quantity and closes lots -- and why the
    disposal-gain tax class has something to be applied to even for a bond redeemed at
    par, where that gain is exactly zero. Treating it as cash-only would make the gain
    unassertable and the tax on it invisible.

    The lot is deliberately **not** named: which lots a disposal consumes is decided by
    the configured consumption method, and an event that named one would be asking for
    specific-lot selection, which the ledger refuses loudly rather than ignoring.
    """
    terms = terms_of.narrowed(declaration, BondTerms)
    paid_on = conventions.business_day_rule(terms.business_day_rule)(terms.maturity_date)
    return Event(
        sequence=sequence,
        occurred_on=paid_on,
        kind=EventKind.PRINCIPAL_REPAYMENT,
        amount=money.scale_sourced(terms.face_value, quantity, terms.provenance),
        owner_id=holding.owner_id,
        caused_by=CausationRef(
            kind=CausationKind.INSTRUMENT_TERM,
            id=f"{declaration.id}:maturity_date",
            detail=(
                f"redemption of {quantity!r} units at face value on "
                f"{terms.maturity_date.isoformat()}, paid {paid_on.isoformat()} under "
                f"the {terms.business_day_rule!r} rule"
            ),
        ),
        lot_ref=LotRef(instrument_id=declaration.id, lot_id=None),
        quantity=quantity,
        allocated_to=None,
        capacity_pool=None,
    )
