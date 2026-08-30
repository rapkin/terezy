"""Deployable capacity: how much of one stream's arrival can actually be invested.

012 FR-015 and FR-016, superseding 002 FR-007. A stream names a declared taxation scheme;
this module reports what is left of one period's income after that scheme's charges, and
reports *nothing* where the owner has named no scheme at all.

## Why this is not in :mod:`terezy.core.streams.streams`

Because ``core.routes`` imports that module for :class:`~terezy.core.streams.streams.IncomeStream`,
and ``.importlinter``'s ``official-rate-never-prices-a-leg`` contract (011 FR-012) forbids
``core.routes`` from reaching ``core.tax.official_rate`` **even indirectly**. A deployable
figure is net of a charge struck at an official rate, so the records below name
``core.tax.scheme`` -- and putting them beside the declaration would have made
``routes.ranking -> streams.streams -> tax.scheme -> tax.official_rate`` a broken contract.

The split is not a workaround for the contract; it is the contract being right. What a route
needs from a stream is *where the money lands and in what currency*. What a funding decision
needs is *how much of it survives the tax*. Those are two questions, and only the second one
has any business knowing what an official rate is.

## An undeclared treatment is not a treatment that charges zero

The load-bearing decision, carried over from 002's scalar verbatim because a schema change is
exactly what deletes a carefully argued distinction by accident. The argument is at
:mod:`terezy.core.streams.streams`, where the field it is about lives.
"""

from __future__ import annotations

from dataclasses import dataclass

from terezy.core.primitives import money
from terezy.core.primitives.money import Money
from terezy.core.streams.streams import Cadence, IncomeStream
from terezy.core.tax.scheme import ChargedUnderTheScheme, SchemeCharge


@dataclass(frozen=True, slots=True, kw_only=True)
class DeployableCapacity:
    """How much of one stream's arrival can actually be invested, and what was withheld.

    Every term of ``net = gross - withheld`` is present, so the figure can be checked by
    reading it rather than trusted: an amount available to invest that did not show what it
    was net *of* would be exactly as opaque as the gross figure it replaced.
    """

    stream_id: str
    """Which stream. Never dropped: two streams' capacities are two figures and must not be
    addable by accident."""

    cadence: Cadence
    """The period all three amounts are per. Carried because a monthly figure read as an
    annual one is wrong by a factor of twelve, and nothing else in the record says which."""

    charge: SchemeCharge
    """What the named scheme charged, line by line, on a base struck at the credit date.

    The gross is ``charge.base`` and what was charged is ``charge.total``; **neither is
    copied into a field of its own**, because two fields holding one truth can disagree. The
    foreign amount that produced the base, where there was one, is ``charge.conversion``.
    """

    net: Money
    """``charge.base - charge.total``: the amount available to invest, in the tax currency.

    This is the figure a funding decision may use, so nothing else in the system needs to
    remember to apply the scheme itself -- which is how an amount available to invest comes
    to be overstated (002 FR-007).

    **In the tax currency, and it had to be.** The identity cannot hold across two
    currencies, and both ways of forcing it into the stream's own currency are forbidden:
    converting the charge back at the official rate is an official rate pricing a realised
    amount (011 FR-012), and putting it through the sale channel is a channel rate deciding a
    tax figure (012 FR-012). What is *not* claimed here is how many dollars are left.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class TaxTreatmentUndeclared:
    """The deployable slot, present and explicitly empty, because no treatment was named.

    Not an error and not a failure: the owner has simply not said which scheme this income is
    under, and the honest answer is *the deployable amount is unknown, and at most the gross*
    rather than a net figure that silently equals it.

    Unrelated to :class:`DeployableCapacity`, and **carrying no net field at all**, which is
    the guarantee rather than the documentation of one: there is nothing here for a caller to
    read as an amount available to invest. Same shape and same reason as ``ExitCostUnknown``
    in the round-trip slot and ``RealTermsUnavailable`` in the real-terms slot.
    """

    reason: str
    """Why there is no deployable figure, in the output's own words (002 FR-017)."""

    stream_id: str
    """The stream naming no treatment. Named so the remedy -- name the scheme this income is
    under -- is obvious from the output alone."""

    gross: Money
    """What arrives before any withholding. Reported because it *is* known, and because an
    upper bound on the deployable amount is worth more than nothing -- but it is deliberately
    not called ``net``, and nothing here says the two are equal.
    """


def deployable(
    stream: IncomeStream, charged: ChargedUnderTheScheme | None
) -> DeployableCapacity | TaxTreatmentUndeclared:
    """How much of ``stream``'s arrival can be invested, net of what its scheme charged.

    012 FR-015 and FR-016. Returns :class:`DeployableCapacity` when the stream names a
    treatment -- including one whose components come to nothing, where the net figure equals
    the base because a declaration says so -- and :class:`TaxTreatmentUndeclared` when it
    names none, which is a different claim and therefore a different type.

    ``charged`` is computed elsewhere and passed in, because striking it needs a credit date,
    a crediting destination and an official-rate series, none of which a stream carries. It
    must be present exactly when the stream names a treatment: a mismatch is a programmer
    error and raises rather than being resolved by a default, because both defaults available
    here are wrong -- one reports a capacity the declaration does not support, the other
    reports *nobody said* about a stream that did.

    Pure, with no clock and no I/O: a cadence is a declared word here, not a calendar. The
    arithmetic is one subtraction through ``money``, which unions both sides' provenance, so
    the scheme's citations and the arrival's both reach the net figure.

    **Nothing is clamped.** A declared rate above ``1.0`` produces a negative net figure, and
    it is reported as it comes out: a clamp here would silence a mis-entered declaration by
    making it look plausible, which is predecessor defect B13 in a new place. The loader is
    where a rate outside its range is refused, because that is where the error can name the
    file and the field.
    """
    if stream.tax_scheme is None:
        if charged is not None:
            raise ValueError(
                f"stream {stream.id!r} names no tax treatment and a charge was supplied for "
                "it. Reporting the charge would attribute a scheme to a stream whose owner "
                "named none; ignoring it would discard a figure somebody computed. Neither "
                "is a default this module may pick."
            )
        return TaxTreatmentUndeclared(
            reason=(
                f"stream {stream.id!r} names no tax treatment, so no deployable capacity is "
                "reported for it: no tax treatment declared is not a treatment that charges "
                "zero. The gross arrival is stated and is an upper bound on what could be "
                "invested; reporting it as the net figure would say nothing is charged, "
                "which nobody has claimed (012 FR-016)."
            ),
            stream_id=stream.id,
            gross=stream.amount,
        )
    if charged is None:
        raise ValueError(
            f"stream {stream.id!r} names the tax treatment {stream.tax_scheme!r} and no "
            "charge was supplied for it. A capacity reported without one would be net of "
            "nothing while claiming a treatment was applied."
        )
    return DeployableCapacity(
        stream_id=stream.id,
        cadence=stream.cadence,
        charge=charged.charge,
        net=money.sub(charged.charge.base, charged.charge.total),
    )
