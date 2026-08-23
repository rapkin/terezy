"""The instrument registry: a mapping from a declared instrument class to its functions.

*"Registries are mappings of functions, not subclass dispatch"* (owner decision D-E).
The key set of :data:`REGISTRY` is the exact list of instrument classes this engine
implements, readable in one line and impossible to extend at a distance -- no
registration decorator, no import-time side effect, no subclass scan.

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

from terezy.core.instruments import fixed_income
from terezy.core.instruments.interface import InstrumentOps

FIXED_INCOME: Final = "fixed_income"
"""The one instrument class implemented today: contractual schedules from bond terms."""

OPS: Final[InstrumentOps] = InstrumentOps(
    events=fixed_income.events,
    tax_classes=fixed_income.tax_classes,
    constraints=fixed_income.constraints,
)
"""``fixed_income``'s three functions, gathered into the interface's record.

Built here rather than in ``fixed_income`` for the import reason in the module docstring.
It is the implementation's declaration that it satisfies the interface, so it lives as
close to the implementation as the import graph allows.
"""

REGISTRY: Final[Mapping[str, InstrumentOps]] = {
    FIXED_INCOME: OPS,
}
"""Every instrument class this engine implements."""


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
# 006-inzhur-instruments: the declaration kinds, which are not all instruments
# ---------------------------------------------------------------------------
#
# ⚙ **A fund is a declared instrument class, and it is deliberately NOT in `REGISTRY`.**
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
# **What this leaves open, for the owner rather than for an implementer.** Principle II
# permits exactly four plugin interfaces and says a fifth needs an amendment. This feature
# adds no fifth *registry* -- there is no `FundOps`, no second mapping of functions -- but
# it does add a second declaration kind dispatched by the same `class` key, which is the
# substance of the question if not its letter. Whether that requires an amendment is a
# constitutional call and it is recorded in `specs/006-inzhur-instruments/plan.md` and in
# `specs/features.toml` rather than settled here.
#
# What generic code consumes both today: `data.manifest.input_refs`, per kind, and
# `data.declarations.resolver.Declarations`, which keys both into one id space. What
# feature 010 will need in order to rank a bond against a fund is a common *result* --
# an after-tax, after-cost figure with its provenance and its exclusions -- which
# `core.results.fund.BesideTheHurdle` begins. That unification belongs at the result layer,
# and widening the instrument interface would not have moved it forward.

COLLECTIVE_INVESTMENT_FUND: Final = "collective_investment_fund"
"""A collective-investment fund: `core.instruments.fund`, projected by
`core.results.fund.project_fund`."""

DECLARATION_KINDS: Final[frozenset[str]] = frozenset({FIXED_INCOME, COLLECTIVE_INVESTMENT_FUND})
"""Every ``[instrument] class`` a declaration file may name, instrument or otherwise.

The vocabulary lives in `core` because it is domain knowledge; which *loader* parses each
one is the data layer's business and lives beside the loaders. Reading the set from here
is what lets `data.declarations.resolver` dispatch on a declared name rather than on an
``if`` naming one class -- a branch that would have to be edited for a third kind.
"""
