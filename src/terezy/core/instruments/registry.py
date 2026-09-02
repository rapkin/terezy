"""The instrument registry: which declaration kinds project as an **event stream**.

The key set of :data:`REGISTRY` is readable in one line and impossible to extend at a
distance -- no registration decorator, no import-time side effect, no subclass scan.

**:data:`REGISTRY` is not the list of everything this engine calls an instrument.** It is
the dispatch for declaration kinds whose projection *is* a stream of ledger events, which is
what :class:`~terezy.core.instruments.interface.InstrumentOps` describes. A
collective-investment fund is a declared instrument class and is deliberately **not** here;
:data:`DECLARATION_KINDS` at the foot of this module is the complete vocabulary, and the
section comment above it says why the two lists differ.

**Why this is a third module rather than living in ``interface.py``.** The contract in
``specs/001-ovdp-hurdle-rate/contracts/instrument-interface.md`` writes ``REGISTRY``
beside the signatures, referring to ``fixed_income.OPS``. Written literally that is a
circular import: ``fixed_income`` needs the records from ``interface``, so ``interface``
cannot also import ``fixed_income``. The alternative -- building the ops record inside
``interface`` -- would make the interface module know the implementation's function names,
which is the coupling the record exists to avoid. So the registry is its own module and
the contract's semantics are unchanged.

**An unknown instrument class is a failure, never a fallback.** :func:`ops_for` tests
membership explicitly and raises naming what is known, exactly as
``primitives.conventions`` does. The data layer validates the class name when it loads a
declaration and reports file and field; a name reaching here unrecognised means that
validation was bypassed, which is a programmer error rather than a fact about the money.

Note what is *not* a dispatch key: the instrument's ``id``. Behaviour comes from declared
terms, and a branch on ``id == "ovdp_synthetic_a"`` would be a Principle II violation --
the abstraction would have stopped being a framework at that line.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from terezy.core.instruments import enumerated, fixed_income
from terezy.core.instruments.interface import InstrumentOps

FIXED_INCOME: Final = "fixed_income"
"""A bond declared by its terms: the schedule is computed from a rate, a periodicity, an
issue date and a maturity date."""

ENUMERATED_SCHEDULE: Final = "enumerated_schedule"
"""A bond declared by the payments it will make: the schedule *is* the declaration.

**A second entry, and not a second interface.** It takes the same arguments, returns
the same event stream, and fails with the same union, so it belongs in this mapping where a
fund does not -- the three mismatches recorded below hold for none of it. Why the two forms
are kept apart rather than merged is argued where the records are, in
`core.instruments.interface`.
"""

OPS: Final[InstrumentOps] = InstrumentOps(
    events=fixed_income.events,
    tax_classes=fixed_income.tax_classes,
    constraints=fixed_income.constraints,
    coupons_per_unit=fixed_income.coupons_per_unit,
)
"""``fixed_income``'s three functions, gathered into the interface's record.

Built here rather than in ``fixed_income`` for the import reason in the module docstring.
It is the implementation's declaration that it satisfies the interface, so it lives as
close to the implementation as the import graph allows.
"""

ENUMERATED_OPS: Final[InstrumentOps] = InstrumentOps(
    events=enumerated.events,
    tax_classes=enumerated.tax_classes,
    constraints=enumerated.constraints,
    coupons_per_unit=enumerated.coupons_per_unit,
)
"""``enumerated``'s three functions, gathered into the same record, unchanged."""

REGISTRY: Final[Mapping[str, InstrumentOps]] = {
    FIXED_INCOME: OPS,
    ENUMERATED_SCHEDULE: ENUMERATED_OPS,
}
"""Every declaration kind whose projection is an event stream.

**Not every instrument class**: see :data:`DECLARATION_KINDS` for the full vocabulary and
the section comment beside it for why a fund is not in here.
"""


def ops_for(instrument_class: str) -> InstrumentOps:
    """The functions a declared instrument class selects, or a raise naming the known."""
    if instrument_class not in REGISTRY:
        raise KeyError(
            f"unknown instrument class {instrument_class!r}. There is no default class: "
            f"an instrument must declare one this engine implements. Known classes: "
            f"{sorted(REGISTRY)}"
        )
    return REGISTRY[instrument_class]


# ---------------------------------------------------------------------------
# The declaration kinds, which are not all instruments
# ---------------------------------------------------------------------------
#
# **A fund is a declared instrument class, and it is deliberately NOT in `REGISTRY`.**
# `InstrumentOps` is the `Instrument` plugin interface of Principle II, and a fund does not
# satisfy it. Three concrete mismatches, none of them cosmetic:
#
#   1. **Different inputs.** `EventsFn` takes `Assumptions` -- a consumption method and a
#      coupon policy. A fund run additionally needs a liquidity mode, whether the
#      discretionary buyback is on offer, an exit date, a chosen point inside a stated
#      range and an exchange-rate assumption. None of those has a default anywhere, so a
#      widened `Assumptions` would force every bond run to state a liquidity mode.
#   2. **Different failures.** A fund refuses in ways a bond cannot -- after the
#      subscription cutoff, with no buyback owed, with no rate assumption to size a peg,
#      with a value recorded only as an unanswered question. `InstrumentFailure` covers
#      none of them.
#   3. **A different arity of answer.** A fund stating a range and no chosen point yields
#      *two* projections. No signature returning one schedule can express that, and
#      collapsing it is the midpoint this feature exists to refuse.
#
# Making `InstrumentOps` generic over both would put `Any` in the registry and force every
# call site to narrow before it could call -- a registry that type-checks nothing, claiming
# a uniformity it cannot deliver. That is a worse lie than two records, so the two are kept
# apart and the difference is written down here.
#
# **Is a fund a fifth plugin interface? No -- ruled on by the owner, 2026-08-23.** Principle
# II permits exactly four and says a fifth needs an amendment. This adds no fifth: there is
# no `FundOps`, no second mapping of functions, no new dispatch mechanism, and adding a
# third fund is a data-only change (SC-010 proves it, and a fourth is added in a scratch
# directory by `tests/contract/test_fund_data_only.py`). What it adds is a second
# declaration *kind* under the same concept, projected by its own function because its
# result shape differs. **No amendment is required, and none was made.**
#
# The decisive point is mismatch 3 above, and it is worth being exact about: the fund does
# not fit `EventsFn` because its **output genuinely differs**, not because of a typing
# accident. There are only two ways to force a range through a signature returning one
# stream -- pick a point inside it, which FR-023 forbids by name, or widen the return type
# for bonds too, which would make every existing caller handle a case that cannot arise for
# a bond. Neither is an improvement; both are the interface bending to a shape it was not
# built for.
#
# What generic code consumes both today: `data.manifest.input_refs`, per kind, and
# `data.declarations.resolver.Declarations`, which keys both into one id space.
#
# **The recorded seam for feature 010.** What 010 needs in order to rank a bond against a
# fund in one candidate set is a common *result* -- an after-tax, after-cost figure carrying
# its provenance and its exclusions -- not a common instrument interface.
# `core.results.fund.BesideTheHurdle` is the first of those and is where to start; widening
# the instrument interface would not have advanced it by a line.

COLLECTIVE_INVESTMENT_FUND: Final = "collective_investment_fund"
"""A collective-investment fund: `core.instruments.fund`, projected by
`core.results.fund.project_fund`."""

DECLARATION_KINDS: Final[frozenset[str]] = frozenset(
    {FIXED_INCOME, ENUMERATED_SCHEDULE, COLLECTIVE_INVESTMENT_FUND}
)
"""Every ``[instrument] class`` a declaration file may name, instrument or otherwise.

The vocabulary lives in `core` because it is domain knowledge; which *loader* parses each
one is the data layer's business and lives beside the loaders. Reading the set from here
is what lets `data.declarations.resolver` dispatch on a declared name rather than on an
``if`` naming one class -- a branch that would have to be edited for a third kind.
"""
