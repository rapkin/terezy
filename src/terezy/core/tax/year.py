"""The tax year: what a charge does *not* do at event time, and what the year does with it.

Feature 001 charged tax per event and left the timing open. Feature 009 closes it, and the
first thing that means is a subtraction: **a charge stops moving money**.

``core.results.project`` and ``core.results.fund`` both used to give a tax charge the negated
charge as its cash effect, on the date the income arrived. That is the predecessor's defect
B5 in miniature -- ``REWRITE_BRIEF`` §4.3 -- and it was invisible only because every class
in the shipped registry was exempt, so the amount deducted happened to be zero. It is not
zero for ``ua_investment_profit`` at 23%, and a portfolio that pays its tax on the day of the
trade both misstates the position and hides the fact that the money is actually needed in
August of the following year.

So: the gross amount lands in the ledger, :func:`memo_amount` gives the charge event no cash
effect at all, and the year is assembled afterwards from the charges that were recorded
beside the events. ``events.check_shape`` refuses a charge that moves money, which is what
makes this structural rather than advisory (research.md D1).
"""

from __future__ import annotations

from typing import Final

from terezy.core.primitives import money
from terezy.core.primitives.money import Money

_NO_CASH_EFFECT: Final = -0.0
"""The factor that turns a charge into a memo: it settles nothing, so it moves nothing.

**Why a negative zero rather than a positive one.** Signed zero carries no information about
an amount -- ``0.0 == -0.0`` -- and the sign convention in this ledger is that an outflow is
negative. A charge is recorded on the outflow side of the account (it is a debt being
recognised, never a receipt), and multiplying by ``-0.0`` keeps the recorded amount on that
side while making its magnitude nothing. It also keeps the recorded stream byte-identical to
feature 001's for an exempt class, where the charge was zero and the old negation produced
``-0.0`` -- which is why 001's golden artefact does not move (FR-026, research.md D9).
"""


def memo_amount(total: Money) -> Money:
    """The cash effect of recording one tax charge in the ledger: none, in its own currency.

    The charge's own provenance rides along -- ``money.scale`` preserves it -- so the event
    still cites the rate entry, and the exemption, that produced the figure. An amount of
    zero built with :func:`terezy.core.primitives.money.zero` would rest on no source at all
    and would quietly drop that citation, which is the one thing a zero charge exists to
    carry (``tax.interface``: *zero is a charge, not an absence*).
    """
    return money.scale(total, _NO_CASH_EFFECT)
