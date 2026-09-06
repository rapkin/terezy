"""A cash balance as declared terms: a currency held at a venue, paying exactly nothing.

**A zero-coupon bond was the alternative and it is rejected** (FR-003). A bond is declared by a
face value it repays, a date it repays on and a periodicity; a balance has none of the three,
every one is required, so the declaration could only be written by inventing three values in a
sourced directory where the provenance gate then asks each of them for a citation nobody can
give.

**The rate is refused at the data boundary rather than in this record**, because that is where
an error can name a file and a field.

**No minimum ticket, no unit increment, no tax class, and no field for one.** Any amount of
the currency is holdable, so there is nothing to round to and nothing can be stranded; and a
release returns the basis, so no gain and no income arise and no class is needed to charge
zero. A field here would be somewhere for a later contributor to put one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.provenance import Provenance

DAY_COUNT: Final = "act/365"
"""The convention a balance's figures are annualised on, stated once for the class.

**A declaration may not state one** (FR-010). With the rate pinned at zero no convention can
move the implied rate -- a series of one outflow and one equal inflow has a root of zero at
every span -- so requiring the declarer to state one would be asking for a convention that
decides nothing. ``tests/invariants/test_cash_invariants.py`` asserts that over the whole
registry of declared conventions rather than leaving it as a claim here.
"""


@dataclass(frozen=True, slots=True)
class CashDeclaration:
    """One balance held in one currency, as declared in data. Curated and version-controlled."""

    id: str
    """Unique across every instrument file, of any kind. A duplicate is a load-time failure."""

    name: str
    """Human-readable, non-empty."""

    instrument_class: str
    """``"cash_balance"``. The only permitted dispatch key, as on every other declaration."""

    currency: Currency
    """The denomination the balance is held in."""

    is_synthetic: bool
    """``True`` for a fixture whose terms are invented rather than held.

    Required with no default, so a real account cannot be mistaken for a fixture through
    omission -- the omission would run the wrong way round.
    """

    rate: float
    """What the balance pays, as a fraction per annum. Exactly ``0.0``; see the module head."""

    rate_provenance: Provenance
    """The citation behind :attr:`rate`, with its own ``verified_on``.

    Separate from the rate rather than a ``Money`` wrapping it, because a rate is not money.
    It reaches every figure through the projection, which is where a bond's terms already
    arrive.

    What it vouches for is not the zero: it is that the product is a **balance** and not a
    deposit, which is a fact about a bank and can be wrong.
    """

    groups: tuple[str, ...]
    """The declared groups this balance is in, by group id (015 FR-007a).

    Required, and empty is a statement: a forgotten line must never read as *in no group*.
    Every id resolves against ``data/groups.toml``.
    """


@dataclass(frozen=True, slots=True)
class CashAssumptions:
    """How a balance is run: **nothing**, and the emptiness is the declaration.

    014 FR-003 refuses an instrument with no run plan, so the plan has to exist; nothing about
    running a balance is chooseable, so it holds no field. A consumption method would suggest
    a choice between lots that cannot arise -- one purchase opens one lot and one release
    closes it -- and a coupon policy a coupon that does not exist.
    """


__all__ = ["DAY_COUNT", "CashAssumptions", "CashDeclaration"]
