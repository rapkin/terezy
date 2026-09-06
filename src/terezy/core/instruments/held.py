"""An asset held for its price alone: no coupon, no maturity, no schedule, no yield.

025 FR-009. Every other declaration kind in this project projects an event stream out of terms
it declares -- a bond from a rate and a maturity, an enumerated schedule from its own payments,
a fund from a NAV and a distribution policy. A bitcoin has none of that. What it has is a
quantity somebody holds and a price somebody publishes, and neither is declared here: the
quantity comes from the owner's seed lots and the price from a dated observation (FR-011,
FR-012).

**It declares no access entry.** ``data/access/`` says what a unit costs to buy at a venue, and
this feature is about what he already holds rather than what he might buy.

**Its tax class is permitted to be undeclared, unlike an instrument's.** For a bond a missing
class is refused at load, because a projection would otherwise charge nothing and flatter every
after-tax figure. Here nothing is projected: the position's tax is
:class:`~terezy.core.errors.UnresolvedTaxClass` and the refusal is the reported figure, which is
the state this feature exists to represent -- the market half of the position is known and the
legal half is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.primitives.currency import Currency
    from terezy.core.tax.interface import TaxableEventKind


@dataclass(frozen=True, slots=True, kw_only=True)
class HeldAssetDeclaration:
    """One thing whose only declared property is where its price is published and in what."""

    id: str
    """Unique across the shared instrument id space: a holding names it, and a bond, a fund
    and a held asset declaring one id would resolve to whichever map was searched first."""

    name: str
    """Human-readable, non-empty. For a synthetic fixture it says so in words."""

    quantity_unit: str
    """What one unit is called -- ``BTC``. Reported beside every quantity, because a number of
    units means nothing without it and no other field carries it."""

    price_currency: Currency
    """What the observed price is expressed in.

    The currency a seed lot's cost is read in (FR-025), which is the field that narrows 008
    FR-010: a dollar cost declared as if it were the base currency is wrong by the exchange
    rate while looking entirely plausible.
    """

    venue_id: str
    """Where it sits, resolved against the declared venues. A reference, not an access entry:
    it says which venue holds the units, never what buying one there would cost."""

    is_synthetic: bool
    """``True`` for a fixture whose declaration is invented. Required with no default, so a
    real asset cannot be mistaken for a fixture through omission."""

    groups: tuple[str, ...]
    """The declared groups this asset is in, by group id (015 FR-007a).

    Required, and empty is a statement: membership is a declared label and never a rule, so a
    forgotten line would silently put this asset in no group and a question naming that group
    would answer without it.
    """

    tax_classes: Mapping[TaxableEventKind, str]
    """Which declared tax class governs each kind of income, by class id.

    An id here **need not resolve** -- see the module docstring. What may not happen is the
    reference being absent: a holding with no tax class named at all would report no tax
    because nobody said what its tax was, which is indistinguishable from a holding that is
    exempt.
    """


__all__ = ["HeldAssetDeclaration"]
