"""An income stream as declared, and how much of it can actually be deployed.

FR-006: *income streams MUST be declared data carrying currency, amount, cadence, arrival
venue and indexation policy.* FR-007: *a stream MAY declare an income-tax rate, and
deployable capacity MUST be reported net of it, so the amount available to invest is never
overstated.*

**Why a stream is a term in a cost at all.** ``SIMULATOR_SPEC.md`` §4.2: money that
*arrives* in dollars needs no hryvnia-to-dollar conversion to reach a dollar asset, so
§4.3.1's 5-10% ramp applies to the hryvnia salary and not to the contract income. The same
acquisition is therefore nearly free from one stream and several percent from the other,
which is why access cost is keyed by ``(destination x stream x route)`` and never by
destination alone (Principle VI, FR-008). The stream is the term that carries the finding.

## An undeclared income-tax rate is not a zero one

This module's one genuinely load-bearing decision, and it is the no-silent-default rule
(Principle IV) applied to an optional field.

``income_tax_rate`` may be omitted, and omitting it means **the owner has not stated one**.
That is a different claim from stating zero, and the difference is not pedantic: a stream
with no declared rate has an *unknown* deployable capacity, bounded above by its gross, while
a stream with a declared rate of zero has a deployable capacity that is exactly its gross
because the owner said so. Returning the gross in both cases would report a net figure that
quietly equals the gross -- a number the owner would read as "nothing is withheld", which
nobody has claimed.

So :func:`deployable` returns a tagged union: :class:`DeployableCapacity` when a rate was
declared, and :class:`IncomeTaxRateUndeclared` when none was, the latter carrying no net
field at all. There is nothing on it for a caller to mistake for a figure -- the same shape,
and the same reason, as ``ExitCostUnknown`` occupying the round-trip slot.

## Provenance, and why the arithmetic here uses ``money.scale``

A stream carries **no** ``source``/``retrieved_on``/``verified_on``, and that exemption
covers ``income_tax_rate`` too. The argument is in ``contracts/declaration-schema.md``: an
owner's own salary is not an observation needing a citation but a statement of fact by the
only person who can make it, and the rate here is not a *modelled* tax rate the engine
applies to a taxable event -- §4.2 puts the owner's income-tax position outside the simulator
entirely. It exists so the deployable figure is not overstated, and nothing else.

The consequence for the arithmetic: the withholding factor has no ``Provenance`` object
anywhere to merge, so :func:`deployable` uses ``money.scale`` and not
``money.scale_sourced``. The usual rule -- *a factor that came from declared data goes
through* ``scale_sourced`` -- exists to stop a declaration's mark being dropped silently.
Here there is no mark to drop: ``scale_sourced(amount, factor, provenance.EMPTY)`` would be
the same arithmetic while implying a source was consulted, which ``money`` itself warns
against. Nothing is laundered, because the gross's own provenance is carried through
unchanged and no rate's mark is lost -- there was never one to lose. **If a stream ever gains
a citation, this is the line to change**, and the reason it must change is written here.

## No behaviour on the records, and nothing about routes

Frozen records carrying data, free functions beside them (owner decision D-E). And nothing
in this module imports ``terezy.core.routes``: a stream is per-owner data while a route is a
curated public fact, and that Principle VII boundary is the reason this package exists
separately (see this package's ``__init__``). The one place the two meet -- whether a route
starts where a stream's money actually lands -- lives in ``terezy.core.routes.cost``, which
already holds both and is where a refusal gets reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from terezy.core.primitives import money
from terezy.core.primitives.money import Money

Cadence = Literal["monthly", "biweekly", "semimonthly"]
"""How often the money arrives.

A ``Literal`` rather than a ``str``, on the ``RouteStatus`` precedent: a misspelt cadence
should be a type error at the boundary rather than a period nothing ever matches. The three
values are ``REWRITE_BRIEF.md``'s (§"Contributions": *biweekly / monthly / semi-monthly*).
data-model.md types this field ``str`` and lists exactly these three values as its rule;
closing the set is the stronger reading of the same rule, and the declaration schema has to
reject an unknown cadence in either case (``contracts/declaration-schema.md``).
"""

IndexationPolicy = Literal["none", "cpi", "fixed_rate"]
"""How the amount is expected to grow, as declared.

* ``cpi`` -- indexed to consumer price inflation. The one value the reference material
  actually declares (``SIMULATOR_SPEC.md`` §4.2: ``indexation = { policy = "cpi", rate_pct =
  null }``).
* ``fixed_rate`` -- a stated annual growth rate, which is ``REWRITE_BRIEF.md``'s *salary
  growth* (§"Contributions", and §5.5 in the P2 table).
* ``none`` -- not indexed. Not a domain fact but the absence of one, and it is a member
  because :attr:`IncomeStream.indexation` is required: a stream that does not index needs a
  way to say so, and leaving the field out would make "not indexed" and "nobody said"
  indistinguishable.

**Nothing in this feature applies an indexation.** It is declared and carried so the field
exists where the owner states it; the projection that grows a stream over months belongs to
a later feature. No figure computed anywhere rests on it yet, which is the honest reason the
set can be this small.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Indexation:
    """The declared indexation policy, and the rate it needs if it has one."""

    policy: IndexationPolicy
    """Which policy. Required -- there is no default, because a stream whose growth nobody
    stated is a stream declaring ``none``, and the two must be written differently."""

    rate: float | None
    """The rate as a fraction per annum -- ``0.055``, never ``5.5`` -- or ``None``.

    ``None`` is legitimate for ``cpi`` (the rate comes from an inflation series nobody has
    declared yet) and for ``none`` (there is no rate). For ``fixed_rate`` it is a declaration
    that means nothing, and the loader refuses it (T038/T040): the rule is checked where the
    error can name the file and the field, not here, and **this module applies no indexation
    at all**, so no figure can rest on the unchecked combination in the meantime.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomeStream:
    """One place the owner's money arrives, in one currency, at one cadence.

    Per-owner declared data, carrying no behaviour. Keyword-only because most of the fields
    are strings: a positional constructor would let ``id`` and ``owner_id``, or
    ``arrives_at`` and ``cadence``, be transposed with no type error anywhere -- the same
    trade ``FundingPath`` makes.
    """

    id: str
    """Unique across the owner's streams -- ``salary_uah``, ``contract_usd``. Referenced by
    ``FundingPath.stream_id``, which is why it may not be defaulted or inferred."""

    owner_id: str
    """Whose stream this is. Present from the first commit while there is exactly one owner
    (Principle VII): an unused column is free, and retrofitting tenancy is the expensive
    mistake."""

    amount: Money
    """What arrives each cadence period, and **the single place this stream's currency is
    stated**.

    ``amount.currency`` is what decides whether a route has to convert, and it is what
    ``cost_one`` compares against the first leg of the route being costed.

    A separate ``currency`` field was written first, because ``data-model.md`` asks for both.
    It was removed: two fields stating one fact can disagree, a hand-built record with
    ``currency=UAH`` and ``amount`` in USD typechecks and is nonsense, and the mitigation on
    offer -- "the loader builds both from one declared value" -- puts the guarantee in a layer
    that does not exist yet and cannot help anything constructing a stream in code. One fact,
    one place.
    """
    """What arrives per :attr:`cadence`, gross.

    In the declaration files this is ``0.0`` -- the honest placeholder, because §11 item 3
    records that the owner's real monthly figures have not been stated. A zero produces a
    zero result rather than a made-up one.
    """

    cadence: Cadence
    """How often :attr:`amount` arrives. Carried on every deployable figure below, so a
    monthly number cannot be read as an annual one."""

    arrives_at: str
    """The venue id the money lands in.

    A funding route that starts somewhere else cannot carry this stream's money, and that
    mismatch is **reported** rather than assumed away (spec.md, Edge Cases). The check is in
    ``terezy.core.routes.cost``, where both the stream and the route are in hand.
    """

    indexation: Indexation
    """The declared growth policy. Required; see :class:`Indexation`."""

    income_tax_rate: float | None
    """The rate withheld from :attr:`amount` before anything can be invested, as a fraction
    -- ``0.18``, never ``18`` -- or ``None``.

    ``None`` means **the owner has not stated one**, which is *not* zero. See the module
    docstring: the two are different claims and :func:`deployable` returns different types
    for them, so no net figure can quietly equal a gross one.
    """


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

    gross: Money
    """What arrived, before withholding -- :attr:`IncomeStream.amount` unchanged."""

    income_tax_rate: float
    """The **declared** rate that produced :attr:`withheld`. Never ``None`` here: a stream
    with no declared rate produces :class:`IncomeTaxRateUndeclared` instead."""

    withheld: Money
    """``gross x income_tax_rate``. Exactly zero when the declared rate is zero, and that
    zero is a statement the owner made rather than a default this module supplied."""

    net: Money
    """``gross - withheld``: the amount available to invest.

    This is the figure a funding decision may use, so nothing else in the system needs to
    remember to apply the rate itself -- which is how an amount available to invest comes to
    be overstated (FR-007).
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomeTaxRateUndeclared:
    """The deployable slot, present and explicitly empty, because no rate was declared.

    Not an error and not a failure: the owner has simply not said what is withheld from this
    stream, and the honest answer is *the deployable amount is unknown, and at most the
    gross* rather than a net figure that silently equals it.

    Unrelated to :class:`DeployableCapacity`, and **carrying no net field at all**, which is
    the guarantee rather than the documentation of one: there is nothing here for a caller to
    read as an amount available to invest. Same shape and same reason as ``ExitCostUnknown``
    in the round-trip slot and ``RealTermsUnavailable`` in the real-terms slot.
    """

    reason: str
    """Why there is no deployable figure, in the output's own words (FR-017)."""

    stream_id: str
    """The stream whose ``income_tax_rate`` is undeclared. Named so the remedy -- declare
    the rate, or declare it as zero and mean it -- is obvious from the output alone."""

    gross: Money
    """What arrives before any withholding. Reported because it *is* known, and because an
    upper bound on the deployable amount is worth more than nothing -- but it is deliberately
    not called ``net``, and nothing here says the two are equal.
    """


def deployable(stream: IncomeStream) -> DeployableCapacity | IncomeTaxRateUndeclared:
    """How much of ``stream``'s arrival can be invested, net of any **declared** income tax.

    FR-007. Returns :class:`DeployableCapacity` when the stream declares a rate -- including
    a declared **zero**, where the net figure equals the gross because the owner said so --
    and :class:`IncomeTaxRateUndeclared` when it declares none, which is a different claim
    and therefore a different type.

    Pure, with no clock and no I/O: a cadence is a declared word here, not a calendar. The
    arithmetic is one multiplication and one subtraction, both through ``money``, so the
    withheld figure is reported rather than implied.

    **Nothing is clamped.** A declared rate above ``1.0`` produces a negative net figure and
    a rate below zero produces a net above gross, and both are reported as they come out: a
    clamp here would silence a mis-entered declaration by making it look plausible, which is
    predecessor defect B13 in a new place. The loader is where a rate outside its range is
    refused, because that is where the error can name the file and the field.
    """
    if stream.income_tax_rate is None:
        return IncomeTaxRateUndeclared(
            reason=(
                f"stream {stream.id!r} declares no income-tax rate, so no deployable "
                "capacity is reported for it: no income-tax rate declared is not a rate of "
                "zero. The gross arrival is stated and is an upper bound on what could be "
                "invested; reporting it as the net figure would say nothing is withheld, "
                "which nobody has claimed (FR-007)."
            ),
            stream_id=stream.id,
            gross=stream.amount,
        )
    withheld = money.scale(stream.amount, stream.income_tax_rate)
    return DeployableCapacity(
        stream_id=stream.id,
        cadence=stream.cadence,
        gross=stream.amount,
        income_tax_rate=stream.income_tax_rate,
        withheld=withheld,
        net=money.sub(stream.amount, withheld),
    )
