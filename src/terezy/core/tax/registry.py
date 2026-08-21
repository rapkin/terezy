"""The tax-rule registry: a mapping from a declared rule name to its implementation.

*"Registries are mappings of functions, not subclass dispatch"* (owner decision D-E).
This is that mapping, and the key set is the exact list of rule kinds the engine
implements.

**Why this is a third module rather than living in ``interface.py``.** The contract in
``specs/001-ovdp-hurdle-rate/contracts/taxrule-interface.md`` writes ``REGISTRY`` beside
the signatures, referring to ``flat_rate.OPS``. That does not import: ``flat_rate`` needs
the records from ``interface``, so ``interface`` cannot also import ``flat_rate``. The
alternatives were to build the ops record in ``interface`` -- which would make the
interface module know an implementation's function names, the coupling this design exists
to avoid -- or to separate the registry. It is separated. The semantics the contract
specifies are unchanged: a closed mapping, no subclass dispatch, and no fallback.

**There is no default rule.** :func:`ops_for` tests membership explicitly and raises
naming what is known, exactly as ``primitives.conventions`` does. A missing rule name
reaching here means the data layer's validation was bypassed, which is a programmer error
rather than a fact about the money -- hence a raise rather than a typed failure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from terezy.core.tax import flat_rate
from terezy.core.tax.interface import TaxRuleOps

FLAT_RATE: Final = "flat_rate"
"""The one rule kind implemented today. Covers the exempt case: a flat rate of zero."""

REGISTRY: Final[Mapping[str, TaxRuleOps]] = {
    FLAT_RATE: flat_rate.OPS,
}
"""Every tax rule kind this engine implements."""


def ops_for(name: str) -> TaxRuleOps:
    """The rule a declared name selects, or a raise naming it and the known names."""
    if name not in REGISTRY:
        raise KeyError(
            f"unknown tax rule {name!r}. There is no default rule: treating an "
            f"unrecognised rule as 'no tax' is the most expensive silent default "
            f"available in this domain. Known rules: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]
