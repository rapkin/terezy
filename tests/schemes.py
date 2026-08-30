"""Clearly-labelled synthetic taxation schemes, and nothing that describes Ukraine.

Not a test module -- ``pytest`` collects only ``test_*.py``. It exists so the values under
test are **stated in the test that uses them** rather than read out of a data file
(spec.md, Assumptions): the examples check the engine's arithmetic, not Ukrainian tax law.

Every citation says SYNTHETIC FIXTURE in its own text, so a value that escaped into an
output would announce itself, and no identifier here collides with a shipped one.

**Every ``SourceRef`` carries its kind**, for the reason ``tests/official_rates.py`` gives:
a blank kind ages nothing, and a staleness assertion over it passes by checking nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import SourceRef
from terezy.core.tax.scheme import (
    ComponentAmount,
    ComponentRate,
    CreditingDestination,
    DeclaredContext,
    DeclaredFor,
    PeriodicComponent,
    RateComponent,
    Reading,
    TaxationScheme,
    Verdict,
)

TAX_RULE_KIND = "tax_rule"
"""The declared kind every citation in this feature ages under (``data/observation_kinds.toml``)."""

CITATION = "SYNTHETIC FIXTURE -- an invented tax rule. No legislature enacted it."

RETRIEVED_ON = date(2026, 8, 30)
"""The fixture's retrieval date. An argument everywhere it is aged against, never a clock."""

CREDITED = "credited"
"""A declared date name. The engine never compares against it; a caller supplies its date."""

REPATRIATED = "repatriated"
"""A second declared date name, so a reading recognised on a different date is exercisable."""


def sources(
    identifier: str, *, verified_on: date | None = None, retrieved_on: date = RETRIEVED_ON
) -> prov.Provenance:
    """One kind-stamped synthetic citation, unverified unless a test says otherwise."""
    return prov.of(
        [
            SourceRef(
                id=f"synthetic:scheme:{identifier}",
                citation=CITATION,
                retrieved_on=retrieved_on,
                verified_on=verified_on,
                kind=TAX_RULE_KIND,
            )
        ]
    )


def context(
    identifier: str = "recorded_not_applied", *, verified_on: date | None = None
) -> DeclaredContext:
    """A cited fact recorded on a component and deliberately not applied."""
    return DeclaredContext(
        id=identifier,
        statement="SYNTHETIC FIXTURE -- an invented provision this schedule does not apply.",
        not_applied_because="it is conditioned on an event nothing in this system models",
        provenance=sources(identifier, verified_on=verified_on),
    )


def rate_component(
    schedule: Sequence[tuple[date, float]],
    *,
    component_id: str = "synthetic_levy",
    name: str = "SYNTHETIC синтетичний збір",
    recorded: Sequence[DeclaredContext] = (),
    verified_on: date | None = None,
) -> RateComponent:
    """A rate component over the stated ``(effective_from, rate)`` pairs, in the order given."""
    return RateComponent(
        id=component_id,
        name=name,
        schedule=tuple(
            ComponentRate(
                effective_from=effective_from,
                rate=rate,
                provenance=sources(
                    f"{component_id}:{effective_from.isoformat()}", verified_on=verified_on
                ),
            )
            for effective_from, rate in schedule
        ),
        context=tuple(recorded),
    )


def periodic_component(
    schedule: Sequence[tuple[date, float]],
    *,
    component_id: str = "synthetic_contribution",
    name: str = "SYNTHETIC синтетичний внесок",
    currency: Currency = Currency.UAH,
    recorded: Sequence[DeclaredContext] = (),
    verified_on: date | None = None,
) -> PeriodicComponent:
    """A periodic component over the stated ``(effective_from, amount)`` pairs.

    The amount is money, not a rate: there is no ``rate`` anywhere on this record, which is
    what makes FR-019's confusion unspellable rather than merely discouraged.
    """

    entries = [
        (
            effective_from,
            amount,
            sources(f"{component_id}:{effective_from}", verified_on=verified_on),
        )
        for effective_from, amount in schedule
    ]
    return PeriodicComponent(
        id=component_id,
        name=name,
        period="month",
        schedule=tuple(
            ComponentAmount(
                effective_from=effective_from,
                amount=money.Money(amount, currency, cited),
                provenance=cited,
            )
            for effective_from, amount, cited in entries
        ),
        context=tuple(recorded),
    )


def scheme(
    *,
    scheme_id: str = "synthetic_scheme",
    name: str = "SYNTHETIC FIXTURE -- an invented taxation scheme",
    jurisdiction_id: str = "xx",
    tax_currency: Currency = Currency.UAH,
    variant: str = "synthetic_variant",
    reporting_cadence: str = "quarterly",
    declared_for: DeclaredFor = "stream",
    rate_components: Sequence[RateComponent] = (),
    periodic_components: Sequence[PeriodicComponent] = (),
) -> TaxationScheme:
    """A scheme charging exactly the components it is given, and nothing else."""
    return TaxationScheme(
        id=scheme_id,
        name=name,
        jurisdiction_id=jurisdiction_id,
        tax_currency=tax_currency,
        variant=variant,
        reporting_cadence=reporting_cadence,
        declared_for=declared_for,
        rate_components=tuple(rate_components),
        periodic_components=tuple(periodic_components),
    )


def reading(
    *,
    reading_id: str = "synthetic_reading",
    label: str = "SYNTHETIC FIXTURE -- an invented reading of an invented position",
    scheme_id: str | None = "synthetic_scheme",
    recognised_on: str | None = CREDITED,
    uncomputable_because: str | None = None,
    departs_from_source: str | None = None,
    verified_on: date | None = None,
) -> Reading:
    """One candidate treatment at a destination: a declared scheme, or a stated reason it is not."""
    return Reading(
        id=reading_id,
        label=label,
        scheme_id=scheme_id,
        uncomputable_because=uncomputable_because,
        recognised_on=recognised_on,
        departs_from_source=departs_from_source,
        provenance=sources(f"reading:{reading_id}", verified_on=verified_on),
    )


def destination(
    readings: Sequence[Reading],
    *,
    scheme_id: str = "synthetic_scheme",
    venue_id: str = "synthetic_venue",
    verdict: Verdict = Verdict.UNSETTLED,
    grounds: str = "SYNTHETIC FIXTURE -- an invented judgement about an invented destination.",
    resolution_path: str = "SYNTHETIC FIXTURE -- an invented way of closing an invented question.",
    verified_on: date | None = None,
) -> CreditingDestination:
    """One row of a normative table: a scheme, a venue, a verdict and its candidate readings."""
    return CreditingDestination(
        scheme_id=scheme_id,
        venue_id=venue_id,
        verdict=verdict,
        grounds=grounds,
        resolution_path=resolution_path,
        readings=tuple(readings),
        provenance=sources(f"destination:{scheme_id}:{venue_id}", verified_on=verified_on),
    )
