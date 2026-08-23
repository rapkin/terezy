"""How an instrument is reached: the terms a tuple needs that the instrument does not state.

Feature 010 joins a costed route to an instrument purchase, and the join has two seams --
*the route in ends where the purchase begins* and *the instrument's exit produces a balance
where the route out starts* (FR-004). Anchoring either one needs a **venue**, and nothing in
``data/instruments/`` declares one: an ``InstrumentDeclaration`` and a ``FundDeclaration``
both carry a currency and stop there.
``IncomeStream.arrives_at`` is the only non-route declaration in the project that names a
venue at all.

**That gap is why this record exists, and it is not a small one.** Feature 004 shipped an
exit chain anchored at neither end: money moved between venues for free and the record still
read as a coherent three-hop journey, with an arriving amount in one currency beside a cost
fraction computed in another. Checking only the currency at this feature's two seams would
reproduce exactly that. So the venue is declared, and a mismatch is refused naming both
sides.

**Three facts, and each is a fact about the instrument *as reached*, not about the paper:**

* where it is bought and where its proceeds land -- properties of the venue that sells it;
* what one unit costs at that venue -- a quote, cited like any other observation. A fund
  states its own price (``nav_per_unit`` plus the declared entry markup) and therefore
  declares none here; a bond states a face value, which is what it *repays*, and no purchase
  price at all;
* the declared risk class -- Principle VI's fifth term. It sits here rather than on the
  instrument because the term the principle names is a property of the **option** -- this
  instrument, reached this way -- and not of the security. It is carried into every outcome
  and **scored nowhere** (research.md D9).

⚙ **Why a separate declaration rather than three keys on the instrument file.** The
instrument's own file is the more natural home for the price and arguably for the risk class,
and the honest reason it is not used is recorded rather than dressed up: the golden result
file records the sha256 of every instrument declaration, so a key added to a shipped
instrument file moves a golden that feature 010 must not move. The seam is named in
``docs/METHODOLOGY.md`` §28.6 so that a later feature can move these fields deliberately,
with the golden re-recorded and the diff read.

No behaviour, per owner decision D-E. The record is data; whether it resolves against the
declared venues and instruments is the resolver's question, where the file and the field can
be named.
"""

from __future__ import annotations

from dataclasses import dataclass

from terezy.core.primitives.money import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentAccess:
    """One instrument, as it is reached: the venues, the unit price, and the risk class.

    Keyword-only, because five of the six fields are strings and a positional constructor
    would let ``bought_at`` and ``proceeds_to`` be transposed with no type error anywhere --
    the same trade :class:`~terezy.core.routes.path.FundingPath` makes, and for the same
    reason: transposing those two is a silent defect that produces a coherent-looking round
    trip through the wrong venues.
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

    price_per_unit: Money | None
    """What one unit costs at :attr:`bought_at`, or ``None`` where the instrument states it.

    ``None`` is a *statement*, not an omission, and the resolver enforces which kinds may make
    it: a collective-investment fund prices from its own declared NAV and the declared entry
    markup, so a price here would be a second place for one fact and the two would disagree
    the day one of them was updated. A fixed-income declaration states a **face value** --
    what it repays -- and no purchase price, so it must declare one here or no purchase can be
    sized from an arriving amount without inventing a price.
    """

    risk_class: str
    """The declared risk class of this option. **Carried, never scored** (research.md D9).

    Non-empty. Scoring it needs a model nobody has declared, and an unscored declared label is
    honest where a computed score would not be.
    """
