"""The instrument registry: which declaration kinds project as an **event stream**.

The key set of :data:`REGISTRY` is readable in one line and cannot be extended at a distance
-- no registration decorator, no import-time side effect, no subclass scan.

:data:`REGISTRY` is not the list of everything this engine calls an instrument. It is the
dispatch for declaration kinds whose projection *is* a stream of ledger events, which is what
:class:`~terezy.core.instruments.interface.InstrumentOps` describes; :data:`DECLARATION_KINDS`
at the foot of this module is the complete vocabulary.

**Why this is a third module rather than living in ``interface.py``.** ``fixed_income`` needs
the records from ``interface``, so ``interface`` cannot import ``fixed_income`` back. The
alternative -- building the ops record inside ``interface`` -- would make the interface module
know the implementation's function names, which is the coupling the record exists to avoid.

An unknown class raises rather than returning a typed refusal: the data layer validates the
class name when it loads a declaration and reports file and field, so a name arriving here
unrecognised is a programmer error, not a fact about the money.

Note what is *not* a dispatch key: the instrument's ``id``. Behaviour comes from declared
terms, and a branch on ``id == "ovdp_synthetic_a"`` would be a Principle II violation.
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
"""A bond declared by the payments it will make: the schedule *is* the declaration."""

OPS: Final[InstrumentOps] = InstrumentOps(
    events=fixed_income.events,
    tax_classes=fixed_income.tax_classes,
    constraints=fixed_income.constraints,
    coupons_per_unit=fixed_income.coupons_per_unit,
)

ENUMERATED_OPS: Final[InstrumentOps] = InstrumentOps(
    events=enumerated.events,
    tax_classes=enumerated.tax_classes,
    constraints=enumerated.constraints,
    coupons_per_unit=enumerated.coupons_per_unit,
)

REGISTRY: Final[Mapping[str, InstrumentOps]] = {
    FIXED_INCOME: OPS,
    ENUMERATED_SCHEDULE: ENUMERATED_OPS,
}
"""Every declaration kind whose projection is an event stream."""


def ops_for(instrument_class: str) -> InstrumentOps:
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
# A fund, a cash balance and a held asset are declared instrument classes and are
# deliberately not in `REGISTRY`: each projects through its own arm because its inputs, its
# failures, or the arity of its answer differ from `InstrumentOps`. A fund stating a range
# and no chosen point yields *two* projections and no signature returning one schedule can
# express that; the alternative -- making `InstrumentOps` generic over both -- would put
# `Any` in the registry and force every call site to narrow before it could call, a registry
# that type-checks nothing.

COLLECTIVE_INVESTMENT_FUND: Final = "collective_investment_fund"
"""A collective-investment fund: `core.instruments.fund`, projected by
`core.results.fund.project_fund`."""

CASH_BALANCE: Final = "cash_balance"
"""A balance held at a venue, in one currency, paying a declared zero:
`core.instruments.cash`, projected by `core.results.cash.project_cash`.

Out of :data:`REGISTRY`: a balance produces no event stream at all.
"""

HELD_ASSET: Final = "held_asset"
"""An asset held for its price alone: `core.instruments.held`.

Out of :data:`REGISTRY`: it declares no rate, no schedule and no price -- the price is a
dated observation.
"""

DECLARATION_KINDS: Final[frozenset[str]] = frozenset(
    {FIXED_INCOME, ENUMERATED_SCHEDULE, COLLECTIVE_INVESTMENT_FUND, CASH_BALANCE, HELD_ASSET}
)
"""Every ``[instrument] class`` a declaration file may name, instrument or otherwise.

The vocabulary lives in `core` because it is domain knowledge; which *loader* parses each one
is the data layer's business and lives beside the loaders.
"""
