"""An income stream as declared, and how much of it can actually be deployed.

002 FR-006: *income streams MUST be declared data carrying currency, amount, cadence, arrival
venue and indexation policy.* 002 FR-007 -- *a stream MAY declare an income-tax rate* -- is
**superseded by 012 FR-015**: a stream names a declared taxation scheme instead, exactly as
feature 006's instruments name tax classes, and deployable capacity is reported net of what
that scheme charges.

**Why a stream is a term in a cost at all.** ``SIMULATOR_SPEC.md`` §4.2: money that
*arrives* in dollars needs no hryvnia-to-dollar conversion to reach a dollar asset, so
§4.3.1's 5-10% ramp applies to the hryvnia salary and not to the contract income. The same
acquisition is therefore nearly free from one stream and several percent from the other,
which is why access cost is keyed by ``(destination x stream x route)`` and never by
destination alone (Principle VI, FR-008). The stream is the term that carries the finding.

## An undeclared treatment is not a treatment that charges zero

What the distinction produces is one module over, in :mod:`terezy.core.streams.capacity`,
which states why it is there. The distinction itself belongs here, beside the field.

This module's one genuinely load-bearing decision, and it is the no-silent-default rule
(Principle IV) applied to an optional field. It survived the migration off the scalar
verbatim, because a schema change is exactly what deletes a carefully argued distinction by
accident.

:attr:`IncomeStream.tax_scheme` may be omitted, and omitting it means **the owner has not
stated one**. That is a different claim from a scheme that charges nothing: a stream naming
no treatment has an *unknown* deployable capacity, bounded above by its gross, while a stream
under a scheme whose components come to nothing has a deployable capacity that is exactly its
gross because a declaration says so. Returning the gross in both cases would report a net
figure that quietly equals the gross -- a number the owner would read as "nothing is
charged", which nobody has claimed.

So the figure comes back as a **tagged union**: a capacity when a treatment was named, and
an explicitly-empty slot when none was, the second carrying no net field at all. There is
nothing on it for a caller to mistake for a figure -- the same shape, and the same reason, as
``ExitCostUnknown`` occupying the round-trip slot. Both records and the function that returns
them are in :mod:`terezy.core.streams.capacity`, which states why they are not here.

## Where the legal values went, and why the boundary is sharper for it

A stream carries **no** ``source``/``retrieved_on``/``verified_on``, and the argument for
that exemption is in ``contracts/declaration-schema.md``: an owner's own salary is not an
observation needing a citation but a statement of fact by the only person who can make it.

That argument holds for an amount and a cadence. It never held for a **tax rate**, which is a
public legal fact about the Republic rather than a statement about the owner -- and the
retired scalar let one be written into per-owner data uncited. After 012 the owner declares
*which scheme he is in* (a fact about him, uncited, correctly) and the scheme's rates live in
``data/tax/schemes/`` with their sources (public facts, cited, correctly). So there is no
longer any arithmetic in this module that applies a declared rate: the charge arrives already
computed, its lines already carrying the citations of the entries that produced them, and
what is left to do is one subtraction.

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

    In the declaration files this is ``0.0`` -- the honest placeholder, because
    ``SIMULATOR_SPEC.md`` §11 item 3 records that the owner's real monthly figures have not
    been stated. A zero produces a zero result rather than a made-up one.

    ⚙ A second string literal sat under this field until 2026-08-30, saying the same thing in
    different words. Only the first was an attribute docstring; the second was a dead
    expression nothing rendered, and the two had already drifted apart.
    """

    cadence: Cadence
    """How often :attr:`amount` arrives. Carried on every deployable figure, so a
    monthly number cannot be read as an annual one."""

    arrives_at: str
    """The venue id the money lands in -- the **routing origin**, and the node every funding
    route for this stream starts from.

    A funding route that starts somewhere else cannot carry this stream's money, and that
    mismatch is **reported** rather than assumed away (spec.md, Edge Cases). The check is in
    ``terezy.core.routes.cost``, where both the stream and the route are in hand.
    """

    credited_to: str
    """The venue id the income is credited at for tax purposes -- the **tax event's
    location**, and a different declared fact from :attr:`arrives_at` (012 FR-024a).

    Neither is defaulted from the other, in either direction, and a declaration supplying one
    without the other fails at load. They answer different questions and for the owner today
    they hold different values: his contract income is *routed* through Deel and *credited* to
    a ФОП account. A default either way would settle the tax treatment by accident -- turning
    a charge into a switch or a switch into an uncited charge, depending on which way it ran.
    """

    indexation: Indexation
    """The declared growth policy. Required; see :class:`Indexation`."""

    tax_scheme: str | None
    """The id of the declared taxation scheme this income is under, or ``None``.

    ``None`` means **the owner has not named one**, which is *not* a scheme that charges
    nothing. See the module docstring: the two are different claims and
    :mod:`terezy.core.streams.capacity` returns different types for them, so no net figure
    can quietly equal a gross one.

    A scheme declared for a *reading* rather than for a stream may not be named here, and a
    scheme no file declares fails at load naming the file, the stream and the treatment. There
    is no default treatment and none is substituted.
    """
