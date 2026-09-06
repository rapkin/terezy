"""A cash balance as declared terms: a currency held at a venue, paying exactly nothing.

The third declaration kind, and the one whose projection is not really a schedule at all. A
bond is declared by a face value it repays, a date it repays on and a periodicity; a balance
has none of the three, and every one of them is required, so declaring cash as a zero-coupon
bond could only be done by inventing three values in a sourced directory where the provenance
gate would then ask each of them for a citation nobody can give.

**The rate is `Literal`-adjacent rather than free** (FR-003). It is a float because a rate is,
and the data boundary refuses anything but exactly zero -- naming the file and the field, and
saying that a balance paying something is a **deposit** whose rate, capitalisation,
early-withdrawal penalty and interest taxation are the bank's terms and have to be cited. The
check is at the boundary rather than in this record because that is where an error can name a
file.

**What the one citation is a claim about.** Not really *zero*: it is that this Monobank
product is a zero-rate balance and **not** a deposit, which is a fact about a bank and can be
wrong. So the rate carries the four citation keys like any other observed value, and every
figure a balance produces inherits the mark.

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

UNIT_PRICE: Final = 1.0
"""What one unit of balance costs, in the balance's own currency.

Sizing is identity: one hryvnia of balance costs one hryvnia. It is a constant rather than a
declared ``[access.price]`` because a declared price would be one fact in two places, and the
resolver refuses one for exactly that reason (FR-005).
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


__all__ = ["DAY_COUNT", "UNIT_PRICE", "CashAssumptions", "CashDeclaration"]
