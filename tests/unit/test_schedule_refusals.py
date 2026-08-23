"""FR-012: an event before the schedule's earliest entry is a typed refusal, never a rate.

This is the test that makes the honest schedule safe to declare. Where a citation
establishes the current rate but not the date the previous one began, the schedule starts
at the attested date and nothing earlier is invented (research.md D2) -- which is only
tolerable because the lookup *refuses* rather than reaching for the nearest entry or
charging zero.

**A schedule that never refuses is a schedule someone back-dated.** So the refusal is
asserted twice: once on the lookup, and once end to end through a projection, because a
refusal that the wiring swallows is worse than no refusal at all.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.results import project
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry, RateUndeclaredBefore, rate_on
from tests import synthetic

EARLIEST: date = date(2026, 6, 30)


def _sources() -> Provenance:
    return prov.of(
        [
            SourceRef(
                id="fixture:earliest",
                citation="FIXTURE -- an invented schedule entry, not a legal fact",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _one_entry_class(class_id: str, *kinds: TaxableEventKind) -> TaxClass:
    return TaxClass(
        id=class_id,
        applies_to=frozenset(kinds),
        rates=(
            RateEntry(
                effective_from=EARLIEST,
                pit_rate=0.18,
                levy_rate=0.05,
                provenance=_sources(),
            ),
        ),
    )


def test_the_refusal_names_the_class_the_event_date_and_what_is_declared() -> None:
    """All three, because each answers a different question the reader has next.

    The class says which file to open, the event date says what could not be charged, and
    the earliest declared date says what a citation would have to reach back to.
    """
    refused = rate_on(_one_entry_class("ua_investment_profit"), date(2026, 6, 29))
    assert isinstance(refused, RateUndeclaredBefore), refused
    assert refused.tax_class_id == "ua_investment_profit"
    assert refused.event_date == date(2026, 6, 29)
    assert refused.earliest_declared == EARLIEST
    assert "2026-06-29" in refused.reason
    assert "2026-06-30" in refused.reason
    assert "ua_investment_profit" in refused.reason


def test_no_rate_is_defaulted_and_no_zero_is_charged() -> None:
    """The refusal is a *value*, and it carries no rate for a caller to read by mistake.

    Asserted structurally rather than by inspecting a charge: the failure this forecloses
    is a caller that treats "no entry" as "zero", and the way to make that unreachable is
    for the refusal to have no ``pit_rate`` and no ``levy_rate`` at all.
    """
    refused = rate_on(_one_entry_class("ua_investment_profit"), date(2020, 1, 1))
    assert isinstance(refused, RateUndeclaredBefore), refused
    assert not hasattr(refused, "pit_rate")
    assert not hasattr(refused, "levy_rate")


def test_a_projection_whose_first_taxable_event_precedes_the_schedule_is_refused() -> None:
    """End to end: the wiring returns the refusal instead of a projection (SC-005).

    The synthetic bond pays its first coupon on 2026-07-15, so a schedule starting the day
    after that leaves the coupon uncharged -- and the run must stop rather than report a
    holding that happens to look tax-free.
    """
    too_late = replace(
        _one_entry_class("late_class", TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN),
        rates=(
            RateEntry(
                effective_from=date(2026, 7, 16),
                pit_rate=0.18,
                levy_rate=0.05,
                provenance=_sources(),
            ),
        ),
    )
    outcome = project.project(
        synthetic.declaration(
            tax_classes={
                TaxableEventKind.COUPON: "late_class",
                TaxableEventKind.DISPOSAL_GAIN: "late_class",
            },
        ),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes={"late_class": too_late},
    )
    assert isinstance(outcome, RateUndeclaredBefore), outcome
    assert outcome.event_date == date(2026, 7, 15)
    assert outcome.tax_class_id == "late_class"
