"""Clearly-labelled synthetic official-rate series, and nothing that describes Ukraine.

Not a test module -- ``pytest`` collects only ``test_*.py``. It exists so the values under
test are **stated in the test that uses them** rather than read out of a data file
(spec.md, Assumptions): the examples check the conversion arithmetic, not the hryvnia.

Every citation says so in its own text, so a value that escaped into an output would
announce itself. Nothing here is a rate anybody published.

**Every ``SourceRef`` carries its kind**, because that is the only thing that survives a
merge of provenance -- a tax base rests on the amount's sources and the rate's, and by the
time a figure has been through that union no record knows which kind each citation ages
under. Feature 010 found that the expensive way; ``official_rate.OfficialRateObservation``
therefore has no ``kind`` field and a fixture that left the citation's blank would make
every staleness assertion pass by ageing nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.tax.official_rate import (
    NonPublicationDay,
    NonPublicationRule,
    OfficialRateObservation,
    OfficialRateSeries,
)

OFFICIAL_RATE_KIND = "official_rate"
"""The declared kind every official-rate citation ages under (``data/observation_kinds.toml``)."""

CITATION = "SYNTHETIC FIXTURE -- an invented official rate. Not published by any authority."

RETRIEVED_ON = date(2026, 8, 24)
"""The fixture's retrieval date. An argument everywhere it is aged against, never a clock."""

KINDS = {
    OFFICIAL_RATE_KIND: ObservationKind(
        id=OFFICIAL_RATE_KIND,
        staleness_days=7,
        note="SYNTHETIC FIXTURE -- mirrors the shipped threshold so a test need not load one.",
    )
}
"""A kinds registry holding one kind, for tests that age a figure without a data root."""


def observation(
    on_date: date,
    value: float,
    *,
    verified_on: date | None = None,
    retrieved_on: date = RETRIEVED_ON,
) -> OfficialRateObservation:
    """One synthetic date's rate, with its own kind-stamped citation.

    ``verified_on`` defaults to ``None`` -- unverified, like every value that will ever be
    fetched by a script -- so a test that wants the mark absent has to say so, which is the
    direction that keeps the propagation checks falsifiable.
    """
    return OfficialRateObservation(
        on_date=on_date,
        value=value,
        provenance=prov.of(
            [
                SourceRef(
                    id=f"synthetic:official_rate:{on_date.isoformat()}",
                    citation=CITATION,
                    retrieved_on=retrieved_on,
                    verified_on=verified_on,
                    kind=OFFICIAL_RATE_KIND,
                )
            ]
        ),
    )


def series(
    values: Sequence[tuple[date, float]],
    *,
    series_id: str = "synthetic_official_usd",
    pair: tuple[Currency, Currency] = (Currency.UAH, Currency.USD),
    quotation_unit: float = 1.0,
    rule: NonPublicationRule | None = None,
    verified_on: date | None = None,
    retrieved_on: date = RETRIEVED_ON,
) -> OfficialRateSeries:
    """A series over the stated ``(date, value)`` pairs, in the order given."""
    return OfficialRateSeries(
        id=series_id,
        authority="SYNTHETIC FIXTURE -- an invented publishing authority.",
        pair=pair,
        quotation_unit=quotation_unit,
        rule=rule,
        observations=tuple(
            observation(on_date, value, verified_on=verified_on, retrieved_on=retrieved_on)
            for on_date, value in values
        ),
    )


def enumerated_rule(
    days: Sequence[tuple[date, date]],
    *,
    rule_id: str = "synthetic_enumerated_rule",
    verified_on: date | None = None,
) -> NonPublicationRule:
    """A non-publication-day rule as an explicitly enumerated ``(applies_to, governed_by)`` map.

    The calendar-free form: it states which declared observation governs which unpublished
    date, one row per date, and nothing here knows what a weekend is (FR-011, FR-018).
    """
    return NonPublicationRule(
        id=rule_id,
        days=tuple(
            NonPublicationDay(applies_to=applies_to, governed_by=governed_by)
            for applies_to, governed_by in days
        ),
        provenance=prov.of(
            [
                SourceRef(
                    id=f"synthetic:official_rate_rule:{rule_id}",
                    citation=(
                        "SYNTHETIC FIXTURE -- an invented non-publication-day rule, cited so "
                        "the declared-rule path can be exercised. Not any published rule."
                    ),
                    retrieved_on=RETRIEVED_ON,
                    verified_on=verified_on,
                    kind="tax_rule",
                )
            ]
        ),
    )
