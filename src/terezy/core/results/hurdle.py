"""The hurdle rate: the number every other option in this project must beat.

``SIMULATOR_SPEC.md`` §3.1 makes the claim the whole product rests on -- a Ukrainian
government bond bought through Inzhur costs nothing to enter and is taxed at nothing, so
its yield is the bar. This record is that claim turned into a computed, traceable figure,
and the type's *name* is how FR-004's "label it as the hurdle rate" is satisfied: a caller
cannot hold one of these and think it is something else.

**Two return figures, never one** (FR-005). They answer different questions and neither
substitutes for the other:

* :attr:`HurdleRate.nominal_ytm` -- the **contractual** yield to maturity: the annual rate
  at which the bond's promised gross cash flows discount back to what was paid for them.
  A property of the terms and the price.
* :attr:`HurdleRate.nominal_cash_flow_return` -- the **cash-flow-weighted** (money-weighted)
  return actually earned: the same root-finding applied to the flows net of every tax
  charge recorded in the ledger. A property of what the owner keeps.

Under an exempt class the two series are identical and the two figures agree, which is a
fact worth asserting rather than a reason to collapse them into one field. The moment a
taxed instrument arrives they diverge, and code that had only ever seen them equal would
have picked whichever it happened to store.

**Both are nominal, and the real slot is present and explicitly empty** (FR-022, SC-011).
Inflation is not modelled in this feature, so no real figure is computed and none is
assumed. :attr:`HurdleRate.real` is typed ``RealRate | RealTermsUnavailable`` and holds the
latter, carrying its reason -- so a nominal figure cannot be assigned into it without a
mypy error, which is the mechanism decision D4 chose over a naming convention.

**The figure states its own boundaries** (:attr:`HurdleRate.excludes`). Principle VI
forbids quoting an access cost per instrument, so rather than pretending this number is
comparison-ready the record says what it does not account for. For OVDP through Inzhur the
excluded route costs happen to be reported as zero, which makes this figure nearly
complete for this one instrument -- and would make it badly misleading if compared against
a crypto ramp whose costs are five to ten percent one way.

**Why a hand-rolled bisection and not ``scipy.optimize``.** A yield is a root and needs a
root find. ``scipy`` is a project dependency, and the plan states plainly that this feature
does not use it: the arithmetic is tens of values in plain Python, and pulling an array
library into the middle of the one figure the project exists to produce would put a
compiled reduction between the inputs and the determinism digest (C4) for no benefit. A
bisection over a monotone function is twenty lines, has no tuning parameters, cannot
diverge, and runs the same way on every platform -- and the last of those is a hard
requirement here, not a preference.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable

type CashFlow = tuple[float, float]
"""One dated amount, as ``(years from the purchase, signed amount)``.

Years rather than a date, and a bare ``float`` rather than ``Money``: by this point the
figure is a dimensionless rate. The provenance of every amount behind it is unioned into
:attr:`HurdleRate.provenance` by the caller, which is the level at which a reader asks
whether the figure rests on anything unverified. Duplicating the mark on each intermediate
would create a second place for it to disagree with itself.
"""

EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "funding route costs (in)",
        "exit route costs (out)",
        "inflation (the figure is nominal)",
    }
)
"""What a feature-001 hurdle rate does not account for, in the output's own words.

Three items, each of which is a whole later feature. They are phrased for a reader rather
than as identifiers because they are meant to be shown: a figure that silently omitted a
five-to-ten-percent access cost is the predecessor project's headline defect
(``REWRITE_BRIEF.md`` §4.2), and this set is the standing reminder of it.
"""

ACCOUNTS_FOR: Final[frozenset[str]] = frozenset(
    {
        "tax on every taxable event over the holding's life",
    }
)
"""What the figure *is* net of, in the output's own words.

The sibling of :data:`EXCLUDES`, and the reason it exists is US1's second acceptance
scenario: the figure must **state** that it is after tax. A return that does not say
whether it is gross or net is exactly the ambiguity Principle I exists to prevent -- and
between two instruments where one is taxed at 0% and another at 23%, that ambiguity is
the whole decision.

Naming what is included beside what is excluded also means a later feature cannot quietly
move a term from one set to the other: adding route costs means deleting a line here and
adding one there, in the same change, where a reviewer sees both.
"""

NO_REAL_TERMS: Final[RealTermsUnavailable] = RealTermsUnavailable(
    reason=(
        "inflation is not modelled in this feature, so no real figure can be computed. "
        "None is assumed either: a real rate derived from a guessed inflation rate would "
        "be a fabricated number wearing the same label as a measured one."
    )
)
"""The occupant of the real-terms slot for every figure this feature produces.

A module constant rather than a value built at each call site, so that every result gives
the same reason and the reason can be improved in one place. It is not an error -- nothing
failed -- which is why it lives with the rate records rather than in ``core.errors``.
"""

_LOWEST_RATE: Final = -0.999999
"""The bottom of the bracket: a loss of all but a millionth of the investment.

Not ``-1.0``: at exactly ``-1`` the discount factor is a division by zero for any flow
after the purchase. A rate below this is not a rate this project will report -- it is a
total loss, and a total loss is described by saying so, not by quoting a percentage.
"""

_HIGHEST_RATE: Final = 100.0
"""The top of the bracket: 10 000% per annum. Above this the answer is not a yield."""

_MAX_ITERATIONS: Final = 200
"""Enough for the bracket to collapse to adjacent floats, with room to spare.

Halving a bracket of about 101 down to float resolution takes roughly sixty steps. The
cap exists so a bug cannot spin forever, not because the loop is expected to reach it.
"""


@dataclass(frozen=True, slots=True)
class HurdleRate:
    """The benchmark return of one holding, with its boundaries and its sources."""

    nominal_ytm: NominalRate
    """The contractual yield to maturity, in nominal terms. See the module docstring."""

    nominal_cash_flow_return: NominalRate
    """The cash-flow-weighted return net of tax, in nominal terms. Kept separate."""

    real: RealRate | RealTermsUnavailable
    """The real-terms figure, or a typed statement of why there is none.

    Always ``RealTermsUnavailable`` in this feature. Present and explicitly empty rather
    than absent, so that the feature which introduces CPI fills the slot without changing
    the shape of the result or anything that consumes it (SC-011).
    """

    total_tax: Money
    """Every tax charge over the life of the holding, summed. Exactly zero for an exempt
    class -- and zero because zeroes were recorded and added up, not because nothing
    was."""

    accounts_for: frozenset[str]
    """What this figure *is* net of -- in particular, that it is after tax (US1
    scenario 2). See :data:`ACCOUNTS_FOR`."""

    excludes: frozenset[str]
    """What this figure does not account for. See :data:`EXCLUDES`."""

    provenance: Provenance
    """The union of every source behind every amount that fed this figure.

    ``provenance.is_unverified`` is ``True`` while any of them lacks a verification date,
    which for the OVDP yield is the expected first-run state (FR-015, E5).
    """


def net_present_value(flows: Sequence[CashFlow], rate: float) -> float:
    """Discount a series of dated amounts back to the purchase date at ``rate``.

    Continuous annual compounding of a discrete rate -- ``(1 + r) ** years`` with
    fractional years -- rather than per-period compounding on a period count. The year
    fractions come from the issue's declared day-count convention, so the annualisation
    is measured the same way the coupons were accrued; a separate hard-coded 365 here
    would make the yield disagree with the schedule it was computed from.
    """
    total = 0.0
    for years, amount in flows:
        total += amount / (1.0 + rate) ** years
    return total


def internal_rate_of_return(flows: Sequence[CashFlow]) -> float:
    """The rate at which ``flows`` discount to zero, found by bisection.

    Bisection rather than Newton: for a conventional series -- one payment out at the
    start, receipts afterwards -- the present value is strictly decreasing in the rate, so
    a bracket that straddles zero contains exactly one root and halving it cannot fail.
    Newton is faster and can leave the bracket on a badly conditioned series, which is a
    silent wrong answer rather than a slow one.

    Raises ``ValueError`` when the bracket does not straddle zero. That is a statement
    about the code, not about the money: by the time a series reaches here the purchase
    cost is known positive and the redemption known positive, which guarantees a sign
    change, so a failure means the caller built a series this function was never given.
    """
    low, high = _LOWEST_RATE, _HIGHEST_RATE
    at_low = net_present_value(flows, low)
    at_high = net_present_value(flows, high)
    if (at_low > 0.0) == (at_high > 0.0):
        raise ValueError(
            f"no yield exists between {low!r} and {high!r} for these cash flows: the "
            f"present value is {at_low!r} at the bottom of the bracket and {at_high!r} at "
            "the top, so it never crosses zero. A conventional purchase -- money out "
            "first, receipts afterwards -- always crosses; a series that does not is not "
            "one this function was given a definition for, and extrapolating past the "
            "bracket would invent a rate."
        )

    for _ in range(_MAX_ITERATIONS):
        middle = (low + high) / 2.0
        if middle in (low, high):
            # The bracket has collapsed to adjacent floats. Halving again would return
            # one of the endpoints unchanged and loop forever.
            break
        value = net_present_value(flows, middle)
        if value == 0.0:
            return middle
        if (value > 0.0) == (at_low > 0.0):
            low, at_low = middle, value
        else:
            high = middle
    return (low + high) / 2.0


def of_flows(
    *,
    contractual: Sequence[CashFlow],
    received: Sequence[CashFlow],
    total_tax: Money,
    provenance: Provenance,
) -> HurdleRate:
    """Assemble the result from the two series, the tax total and the merged sources.

    Both series are required, and they are required *separately*, because computing one
    and reusing it for the other is the substitution FR-005 forbids. Under an exemption
    they happen to be identical -- and passing the same series twice would be a caller's
    honest statement that the flows really are the same, not this function's assumption
    that they always are.
    """
    return HurdleRate(
        nominal_ytm=NominalRate(internal_rate_of_return(contractual)),
        nominal_cash_flow_return=NominalRate(internal_rate_of_return(received)),
        real=NO_REAL_TERMS,
        total_tax=total_tax,
        accounts_for=ACCOUNTS_FOR,
        excludes=EXCLUDES,
        provenance=provenance,
    )
