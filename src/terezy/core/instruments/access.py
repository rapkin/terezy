"""How an instrument is reached: the terms a tuple needs that the instrument does not state.

Feature 010 joins a costed route to an instrument purchase, and two of the join's seams are
*positional* -- *the route in ends where the purchase begins* and *the instrument's exit
produces a balance where the route out starts* (FR-004). Anchoring either needs a **venue**,
and nothing in
``data/instruments/`` declares one: an ``InstrumentDeclaration`` and a ``FundDeclaration``
both carry a currency and stop there.
``IncomeStream.arrives_at`` is the only non-route declaration in the project that names a
venue at all.

**That gap is why this record exists.** Checking only the currency at either seam would
reproduce feature 004's unanchored exit chain -- see
:class:`~terezy.core.results.tuple.SeamDoesNotChain` for what that cost. So the venue is
declared, and a mismatch is refused naming both sides.

**Every field but the key is a fact about the instrument *as reached*, not about the paper:**

* where it is bought and where its proceeds land -- properties of the venue that sells it;
* what one unit costs at that venue -- a quote, cited and aged like any other observation. A
  fund states its own price (``nav_per_unit`` plus the declared entry markup) and therefore
  declares none here; a bond states a face value, which is what it *repays*, and no purchase
  price at all;
* the declared risk class -- Principle VI's fifth term. It sits here rather than on the
  instrument because the term the principle names is a property of the **option** -- this
  instrument, reached this way -- and not of the security. It is carried into every outcome
  and **scored nowhere** (research.md D9).

**Why a separate declaration rather than four keys on the instrument file.** The argument
the risk class makes above is the argument for all of them: every field here is a property of
the **option** rather than of the security, and changes if the same instrument is reached
elsewhere, while the instrument's own file states what the paper carries.

**Today that is one row per instrument, and the resolver enforces it.** The registry is keyed
by instrument id and a second row for the same id is refused at load. So this record does not
yet *express* one instrument at two venues -- selecting between two rows would need a venue
term on :class:`~terezy.core.results.tuple.Tuple`, which nothing has. What the seam buys is
that the shape becomes declarable when a second venue is declared, in one file, without
touching the instrument's terms. Building the key for a venue nobody has declared would be
speculation, which is the opposite of what this project does.

Whether this resolves against the declared venues and instruments is the resolver's question,
where the file and the field can be named.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class VenueQuote:
    """One venue's price for one unit, with the kind it ages under.

    The two travel together because a price with no threshold can never be reported stale,
    and a threshold with no price is nothing at all. Two nullable fields on
    :class:`InstrumentAccess` would let the pair come apart -- a quote whose kind was dropped
    would read as fresh forever, which is the silent permissive default FR-028 forbids.
    """

    price: Money
    """The quote, in the instrument's own currency (the resolver refuses any other)."""

    observed_on: date
    """The day this price described the market. **Arithmetic, not only staleness.**

    A quotation carried to a later date is carried *net of what left the price in between*, so
    a resale price struck at a horizon's end subtracts every coupon that detached after this
    day (:func:`terezy.core.scenarios.early_exit.detached_since`). A field rather than a read of
    ``price.provenance``, because a ``Provenance`` is a **set** with no distinguished member
    and is legitimately ``EMPTY`` for a figure built in code -- so the date a term of the sale
    price is computed from would be a lookup that can come back empty.
    """

    kind: str
    """The ``ObservationKind`` this quote ages under. A price goes out of date faster than a
    coupon rate does, which is the whole reason the threshold is declared per kind."""


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentAccess:
    """One instrument, as it is reached: the venues, the unit price, and the risk class.

    Keyword-only, because ``bought_at`` and ``proceeds_to`` are adjacent strings and a
    positional constructor would let them be transposed with no type error anywhere -- a
    silent defect producing a coherent-looking round trip through the wrong venues.
    """

    instrument_id: str
    """The declared instrument this describes. Resolved against the instrument and fund
    registries by the resolver; an id nobody declared is a load-time failure."""

    bought_at: str
    """The venue the purchase happens at, and therefore where the route in must end.

    The seam the join checks against ``route_in``'s destination **and** its arriving currency
    (FR-004). A venue that cannot hold the instrument's currency is refused at load.
    """

    proceeds_to: str
    """The venue the instrument's proceeds land at, and therefore where the route out begins.

    Declared separately from :attr:`bought_at` rather than assumed equal. They *are* equal for
    every instrument shipped today, which is exactly why assuming it would never be caught: a
    fund that pays a distribution to a bank account rather than back into the platform is an
    ordinary arrangement, and the join must be able to see that it is not the arrangement
    declared here.
    """

    quote: VenueQuote | None
    """What one unit costs at :attr:`bought_at`, or ``None`` where the instrument states it.

    ``None`` is a *statement*, not an omission, and the resolver enforces which kinds may make
    it: a collective-investment fund prices from its own declared NAV and the declared entry
    markup, so a price here would be a second place for one fact and the two would disagree
    the day one of them was updated. A fixed-income declaration states a **face value** --
    what it repays -- and no purchase price, so it must declare one here or no purchase can be
    sized from an arriving amount without inventing a price.
    """

    resale_price: VenueQuote | None
    """What one unit sells for at :attr:`bought_at`, or ``None`` where nobody has quoted one.

    015 FR-031. A horizon means the money comes out at its end, so an instrument whose terms
    run past it is sold there -- and the price is a **declaration**, never a face value, a NAV
    or the purchase price standing in for one. ``None`` refuses by name through
    ``DeclarationMissing(part="access")`` rather than inferring a price -- the fixture
    instruments still make that statement, while every real issue declares a quote.

    Distinct from :attr:`quote`, which is what a unit **costs**. The gap between the two is the
    loss an early exit takes, and one field holding both would make it zero by construction.
    """

    risk_class: str
    """The declared risk class of this option. **Carried, never scored** (research.md D9).

    Non-empty. Scoring it needs a model nobody has declared, and an unscored declared label is
    honest where a computed score would not be.
    """
