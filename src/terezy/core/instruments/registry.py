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
