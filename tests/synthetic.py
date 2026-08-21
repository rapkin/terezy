"""A clearly-labelled synthetic issue, built in code, for tests that need one.

**Every term here is invented.** The real OVDP issue's yield, maturity and coupon terms
are not confirmed (``SIMULATOR_SPEC.md`` §11 item 2), so nothing in this module describes
a bond anyone can buy, and no figure computed from it may be quoted as if it did. Each
source ref says so in its citation, and every ``verified_on`` is empty, so anything
derived from these terms carries the unverified mark -- which is the honest state of
affairs rather than a defect to work around.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported,
never run.

**Why this exists beside the worked example rather than inside it.**
``tests/worked_examples/test_ovdp_schedule.py`` states its own terms, in its own file,
with the arithmetic beside each assertion: a hand-checked example that reached for a
shared fixture would make a reader open two files to verify one number, and the whole
point of D1 is that they should not have to. Everything *else* -- the failure cases, the
real-terms slot, the registries -- cares about behaviour rather than about a particular
schedule, and duplicating a declaration into each of those files would mean five places
to edit when the interface changes.

The override keywords are typed ``Any`` -- the one place in this suite where that is the
honest annotation. ``dataclasses.replace`` accepts whatever fields the record has, and a
narrower type here would mean either enumerating every field of every record as an
optional parameter or writing a cast per call. The type checker still checks the *result*,
because ``replace`` returns the record's own type, so a misspelled field is a runtime
failure in the test that used it rather than a value silently ignored.

The declaration is built by a function taking keyword overrides rather than exported as a
module constant, so a test that needs a broken variant (a maturity before its issue, a
minimum ticket above the purchase) asks for exactly the one field it is interested in and
inherits a valid value for everything else. A shared mutable constant would leave a
reader unsure which fields a given test actually depends on.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from terezy.core.instruments.interface import (
    Assumptions,
    BondTerms,
    DateRange,
    Holding,
    InstrumentConstraints,
    InstrumentDeclaration,
)
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.tax.interface import TaxableEventKind, TaxClass

UAH = Currency.UAH

TERMS_SOURCE = SourceRef(
    id="synthetic:terms",
    citation="SYNTHETIC FIXTURE -- invented bond terms. Not an observation of any issue.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)
"""Unverified on purpose: the terms are invented, so there is nothing to verify against."""

CONSTRAINTS_SOURCE = SourceRef(
    id="synthetic:constraints",
    citation="SYNTHETIC FIXTURE -- invented minimum ticket.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

EXEMPTION_SOURCE = SourceRef(
    id="synthetic:exemption",
    citation="SYNTHETIC FIXTURE standing in for the cited Ukrainian bond exemption.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

TAXED_SOURCE = SourceRef(
    id="synthetic:taxed",
    citation="SYNTHETIC FIXTURE -- invented non-zero rates, for testing that they apply.",
    retrieved_on=date(2026, 8, 21),
    verified_on=date(2026, 8, 21),
)
"""Verified, unlike the rest, so a test can tell a marked figure from an unmarked one."""

PURCHASE_SOURCE = SourceRef(
    id="synthetic:purchase",
    citation="Owner-stated purchase.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)

TERMS_PROVENANCE: Provenance = prov.of([TERMS_SOURCE])

ISSUE_DATE = date(2026, 1, 15)
MATURITY_DATE = date(2028, 1, 15)
ADJUSTED_MATURITY = date(2028, 1, 17)
"""2028-01-15 is a Saturday, so a ``following`` rule pays the last flow on the Monday."""

EXEMPT_CLASS = TaxClass(
    id="synthetic_government_bond",
    applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
    pit_rate=0.0,
    levy_rate=0.0,
    provenance=prov.of([EXEMPTION_SOURCE]),
)
"""The exemption: not a special type, just a class declaring zeroes with a citation."""

TAXED_CLASS = TaxClass(
    id="synthetic_taxed",
    applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
    pit_rate=0.18,
    levy_rate=0.015,
    provenance=prov.of([TAXED_SOURCE]),
)
"""Invented non-zero rates. They are **not** a claim about Ukrainian law -- they exist so
that a test can prove the rule applies whatever the class carries, and that PIT and the
levy stay separate lines. Any figure derived from them is a fixture, not a tax opinion."""

TAX_PACK = {EXEMPT_CLASS.id: EXEMPT_CLASS, TAXED_CLASS.id: TAXED_CLASS}


def terms(**overrides: Any) -> BondTerms:
    """The synthetic bond's terms: 15.5% semiannual, ``act/365``, two years to maturity."""
    base = BondTerms(
        face_value=Money(1000.0, UAH, TERMS_PROVENANCE),
        coupon_rate=0.155,
        issue_date=ISSUE_DATE,
        maturity_date=MATURITY_DATE,
        periodicity="semiannual",
        day_count="act/365",
        business_day_rule="following",
        provenance=TERMS_PROVENANCE,
    )
    return replace(base, **overrides)


def constraints(**overrides: Any) -> InstrumentConstraints:
    """A minimum ticket of one bond, and whole units only."""
    base = InstrumentConstraints(
        min_ticket=Money(1000.0, UAH, prov.of([CONSTRAINTS_SOURCE])),
        min_unit=1.0,
        provenance=prov.of([CONSTRAINTS_SOURCE]),
    )
    return replace(base, **overrides)


def declaration(**overrides: Any) -> InstrumentDeclaration:
    """The whole declaration, taxed under the exempt class on coupon and disposal."""
    base = InstrumentDeclaration(
        id="ovdp_synthetic_test",
        name="Synthetic OVDP -- TEST FIXTURE, terms invented",
        instrument_class="fixed_income",
        currency=UAH,
        is_synthetic=True,
        terms=terms(),
        constraints=constraints(),
        tax_classes={
            TaxableEventKind.COUPON: EXEMPT_CLASS.id,
            TaxableEventKind.DISPOSAL_GAIN: EXEMPT_CLASS.id,
        },
    )
    return replace(base, **overrides)


def holding(**overrides: Any) -> Holding:
    """Ten units bought at par on the issue date, for 10 000.00 UAH."""
    base = Holding(
        owner_id="owner-1",
        instrument_id="ovdp_synthetic_test",
        quantity=10.0,
        purchased_on=ISSUE_DATE,
        cost=Money(10_000.0, UAH, prov.of([PURCHASE_SOURCE])),
    )
    return replace(base, **overrides)


def horizon(**overrides: Any) -> DateRange:
    """A window from the issue date to comfortably past the adjusted maturity."""
    base = DateRange(start=ISSUE_DATE, end=date(2028, 1, 31))
    return replace(base, **overrides)


def assumptions(**overrides: Any) -> Assumptions:
    """FIFO lot consumption. Stated rather than defaulted, here as everywhere."""
    base = Assumptions(consumption_method="fifo")
    return replace(base, **overrides)
