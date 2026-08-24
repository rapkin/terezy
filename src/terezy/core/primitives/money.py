"""Money: float64, currency-tagged, provenance-carrying. The only way to combine it.

Three requirements meet in this one record, and each of them is the reason for one of
its three fields.

**float64** (owner decision D-A). Money is a ``float``, not a ``Decimal``. The
consequence is that the specification's "reproduces a hand-computed schedule exactly"
is implemented as "within the project tolerance", and that tolerance is defined once, in
``terezy.core.primitives.tolerance``, and imported. Nothing in this module compares
amounts for financial equality -- see the note on ``compare`` below.

**Currency-tagged** (FR-006, FR-007, C5). Every amount states its denomination, and
every combining function here refuses a mismatch by raising. A currency mismatch is a
programmer error, not a business outcome, which is why it is one of the very few places
the constitution asks for a ``raise`` rather than a typed failure value.

**Provenance-carrying** (FR-015, E5). Every combining function returns money whose
provenance is the union of its operands'. Because these functions are the only way to
combine money, *there is no way to add two amounts and forget to carry the mark*: the
failure mode FR-015 calls top-severity becomes structurally unreachable rather than a
thing to remember. The cost is that the most-used record in the system is heavier than
an ``(amount, currency)`` pair, and that cost is recorded deliberately in plan.md's
Complexity Tracking.

**No operator dunders** (owner decision D-E). ``money.add(a, b)``, never ``a + b``. Two
reasons, one stylistic and one structural. The structural one is what matters: the
provenance union has exactly one home per operation, and a reviewer checking FR-015
reads five short functions rather than auditing every arithmetic expression in the
codebase. Adding ``__add__`` as a "thin convenience" would give the codebase two ways to
do the same thing, and the convenient one would bypass the reviewable one.

**Conversion is here too, and only here.** :func:`convert` is the one function that returns
an amount in a currency other than its input's, and it exists in this module for the same
reason everything else does: it is the single place a currency can change, so it is the
single place a rate's provenance can be forgotten -- and it demands the rate's sources in
its signature so it cannot be. Every other function refuses a mismatch by raising; that
prohibition only means something if the sanctioned exception is one named, reviewable
function rather than a ``Money`` built by hand somewhere else.

**The one hole.** This record is constructible anywhere, so code elsewhere could build
an amount with ``provenance.EMPTY`` and launder an unverified input into an apparently
unmarked figure. No gate can see that. It is guarded by
``tests/contract/test_money_construction_guard.py``, which scans the source tree for
direct construction outside this module and the declaration loader, and by manual
review. If you need money somewhere else, derive it here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from terezy.core.errors import CurrencyMismatchError
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import Provenance


@dataclass(frozen=True, slots=True)
class Money:
    """An amount of one currency, and the sources it rests on.

    Frozen and hashable, carrying only data. Every operation is a free function below.
    """

    amount: float
    """float64, per owner decision D-A."""

    currency: Currency
    """Always present. Never inferred, never defaulted."""

    provenance: Provenance = field(compare=False)
    """The sources this amount rests on -- **excluded from equality**.

    ``compare=False`` is load-bearing, not cosmetic. Two amounts equal in value are
    equal regardless of the path that produced them; without this, the conservation
    invariants (C1, C2, C3) would fail for reasons entirely unrelated to conservation,
    because the same balance reached by two different routes would compare unequal.
    Because ``compare`` also governs the generated ``__hash__``, provenance is excluded
    from hashing too, which keeps equality and hashing consistent.

    Note what this does *not* mean: provenance is excluded from *equality*, never from
    *propagation*. Every function below unions it.
    """


def zero(currency: Currency) -> Money:
    """No amount, of a stated currency, resting on no source.

    The additive identity, and the only legitimate use of ``provenance.EMPTY`` in
    arithmetic: the starting point of a sum has no source because it is not an
    observation. This is not a licence to give a *declared* value empty provenance --
    that is the laundering this module exists to prevent.
    """
    return Money(0.0, currency, prov.EMPTY)


def _same_currency(left: Money, right: Money, operation: str) -> Currency:
    """The shared currency of two amounts, or a raised mismatch.

    Identity comparison on the enum member, not equality on its value: there is exactly
    one ``Currency.UAH`` object, and comparing identity means a string can never
    accidentally satisfy this check.
    """
    if left.currency is not right.currency:
        raise CurrencyMismatchError(
            f"cannot {operation} {left.currency.value} and {right.currency.value}: "
            "no implicit conversion exists (FR-007). Convert explicitly, at a dated "
            "rate, with its own provenance."
        )
    return left.currency


def add(left: Money, right: Money) -> Money:
    """Sum of two amounts of the same currency, resting on both their sources."""
    currency = _same_currency(left, right, "add")
    return Money(
        left.amount + right.amount,
        currency,
        prov.merge(left.provenance, right.provenance),
    )


def sub(left: Money, right: Money) -> Money:
    """``left - right``, resting on both their sources.

    Provenance is unioned rather than taken from the left operand: a difference depends
    on the subtrahend just as much as on the minuend, so a realised gain computed
    against an unverified cost basis is itself unverified.
    """
    currency = _same_currency(left, right, "subtract")
    return Money(
        left.amount - right.amount,
        currency,
        prov.merge(left.provenance, right.provenance),
    )


def scale(amount: Money, factor: float) -> Money:
    """Multiply an amount by a dimensionless factor, preserving its provenance.

    There is deliberately no money-times-money function: that product is not money. A
    plain ``float`` factor carries no provenance of its own, so there is nothing to
    merge -- which is also a warning. A factor that *did* come from a source (a declared
    rate, a fraction read from a file) must not come through here, because its own
    provenance would be lost silently: use :func:`scale_sourced` instead, which demands
    the factor's sources in its signature. This function is for factors that are
    arithmetic rather than observation -- lot fractions, signs, unit counts.
    """
    return Money(amount.amount * factor, amount.currency, amount.provenance)


def scale_sourced(amount: Money, factor: float, sources: Provenance) -> Money:
    """Multiply by a factor that itself rests on sources, unioning them into the result.

    The companion to :func:`scale`, and the function to reach for whenever the factor
    came from *data*: a declared tax rate, a declared coupon rate, any number a
    declaration file supplied. ``scale`` would carry only the amount's own provenance,
    so applying a declared rate through it would produce a figure that does not admit
    where its rate came from -- and a zero tax charge that cannot cite its exemption is
    indistinguishable from a rule that never ran.

    The sources are a required positional argument rather than an optional one, so the
    caller cannot reach this function and forget them. Passing ``provenance.EMPTY``
    here is legitimate only for a factor that genuinely came from nowhere, in which case
    :func:`scale` says the same thing more plainly.

    Note that this can only ever *add* sources. There is no function anywhere that
    removes one, which is what makes the mark monotone: a figure's provenance grows as
    it is derived and never shrinks, so a mark cannot be laundered out of a chain of
    arithmetic (FR-015).
    """
    return Money(
        amount.amount * factor,
        amount.currency,
        prov.merge(amount.provenance, sources),
    )


def also_resting_on(amount: Money, sources: Provenance) -> Money:
    """The same amount, additionally resting on inputs that decided it without scaling it.

    Some declared inputs change a figure without appearing in its arithmetic. A netting
    treatment is why a year's gains and losses were summed into one base at all; a declared
    deadline is why the resulting liability is the one that falls due. Neither is a factor, so
    neither can travel through :func:`scale_sourced` -- and without a way to union them in, an
    unverified *rule* would mark whatever record happens to carry a ``Provenance`` field while
    the money it governs went out unmarked.

    The amount is returned bit-identical: no multiplication, no addition, nothing that could
    move a last bit. Only the sources grow, and like every function here this one can add a
    source and never remove one, so the mark stays monotone.
    """
    return Money(amount.amount, amount.currency, prov.merge(amount.provenance, sources))


def convert(amount: Money, *, to_currency: Currency, rate: float, sources: Provenance) -> Money:
    """Restate an amount in another currency at a dated rate, unioning the rate's sources.

    The only function in the project that produces an amount in a currency other than its
    input's, and therefore the only place a currency conversion can happen at all. Every
    other function here refuses a mismatch by raising; this one performs the conversion the
    others exist to prevent happening implicitly, which is why it demands the rate's
    provenance in its signature and states its direction in the parameter name.

    ``rate`` is **units of ``to_currency`` per one unit of ``amount.currency``**. That is
    stated here, once, because an inverted rate is the classic FX defect: every figure stays
    plausible and every one is wrong by a factor of the rate squared. A caller converting
    UAH to USD against a channel quoting 42 UAH per USD passes ``1 / 42``, and the inversion
    happens in one reviewable place next to the channel that supplied the number.

    ``sources`` is required and keyword-only, for the reason :func:`scale_sourced` exists: a
    rate is *always* an observation -- a channel's declared reference, an official quote on a
    date -- so a conversion that carried only the amount's own provenance would produce a
    figure that cannot say which rate it rests on. There is no overload without it.

    **A conversion to the same currency is refused**, rather than returned unchanged. It is
    not a conversion, and accepting it would let a bug that lost track of a currency pass
    through here silently while collecting a rate's provenance it never used.

    **A rate of zero or less is refused.** Zero is not a rate and neither is a negative
    number; either would produce a figure that looks like money. This is a declined
    question, not a clamp -- nothing is quietly adjusted to make the arithmetic work.
    """
    if amount.currency is to_currency:
        raise ValueError(
            f"a conversion from {amount.currency.value} to {to_currency.value} is not a "
            "conversion. Same-currency arithmetic goes through scale, add or sub; reaching "
            "here means a currency was lost track of."
        )
    if rate <= 0.0:
        raise ValueError(
            f"a rate of {rate!r} is not a rate: a conversion needs a strictly positive "
            f"number of {to_currency.value} per {amount.currency.value}"
        )
    return Money(amount.amount * rate, to_currency, prov.merge(amount.provenance, sources))


def from_pegged_term(
    quantity: float,
    *,
    sized_in: Currency,
    paid_in: Currency,
    rate: float,
    sources: Provenance,
) -> Money:
    """Size a term denominated in one currency into money paid in another.

    ⚙ **Added by feature 006** for owner decision A: a Ukrainian commercial lease is
    priced in USD-equivalent terms and settled in hryvnia, so the fund's income is
    *declared* in one currency and *paid* in another. The USD-equivalent figure is a term
    of the lease, not a dollar anyone holds -- it is a
    :class:`terezy.core.instruments.fund.PeggedAmount`, deliberately not a ``Money`` --
    and this is the one function that turns such a term into an amount.

    It lives here for the same reason :func:`convert` does: this module is the only place
    a currency can appear, so it is the only place a rate's provenance can be forgotten,
    and demanding ``sources`` in the signature is what stops that. The difference from
    :func:`convert` is only in what it starts from: ``convert`` restates money that
    already exists, and this creates money from a term that was never money.

    ``rate`` is **units of ``paid_in`` per one unit of ``sized_in``**, stated in the
    parameter names because an inverted rate is the classic FX defect: every figure stays
    plausible and every one is wrong by the rate squared. What rate to apply -- a market
    quote, an owner's assumption, a lease's capped ceiling -- is the caller's decision and
    deliberately not this function's.

    **Sizing into the same currency is refused.** A term already denominated in what it is
    paid in is not pegged to anything, and accepting it here would let a lost currency pass
    through while collecting a rate's provenance it never used.

    **A rate of zero or less is refused**, exactly as in :func:`convert`: neither is a
    rate, and both would produce something that looks like money. A declined question, not
    a clamp.
    """
    if sized_in is paid_in:
        raise ValueError(
            f"a term sized in {sized_in.value} and paid in {paid_in.value} is not pegged "
            "to anything. Same-currency amounts are declared as money at the data "
            "boundary; reaching here means a currency was lost track of."
        )
    if rate <= 0.0:
        raise ValueError(
            f"a rate of {rate!r} is not a rate: sizing a {sized_in.value} term into "
            f"{paid_in.value} needs a strictly positive number of {paid_in.value} per "
            f"{sized_in.value}"
        )
    return Money(quantity * rate, paid_in, sources)


def total(items: Iterable[Money], currency: Currency) -> Money:
    """Sum an iterable of amounts, resting on the union of all their sources.

    The currency is a required argument rather than inferred from the first item, for
    two reasons. An empty iterable has no first item, and inferring would mean either
    guessing or failing on a legitimately empty sum. And a stated currency turns a
    mixed-currency list into a raised mismatch on the first foreign item, rather than a
    sum that silently adopts whichever denomination happened to come first.
    """
    running = zero(currency)
    for item in items:
        running = add(running, item)
    return running


def compare(left: Money, right: Money) -> Literal[-1, 0, 1]:
    """Order two amounts of the same currency: ``-1``, ``0`` or ``1``.

    This is an **exact** float comparison and it is deliberately not the financial
    comparison. Because money is float64, two amounts that should be equal after
    different arithmetic paths routinely differ in the last bits; asking whether they
    are *the same number* is a different question from asking whether they are *the same
    amount of money*. For the latter, use ``tolerance.is_close`` or
    ``tolerance.assert_money_close``, which apply the single project tolerance.

    Returned as an integer rather than a bool triple so that a caller cannot get the
    ordering half-right by testing only ``<``.
    """
    _same_currency(left, right, "compare")
    if left.amount < right.amount:
        return -1
    if left.amount > right.amount:
        return 1
    return 0
