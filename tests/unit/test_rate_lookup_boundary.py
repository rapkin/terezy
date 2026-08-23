"""FR-011 at the boundary: an entry is in force **from** its effective date, inclusive.

The boundary is stated once, in ``core.tax.schedule``, and it is tested here *at* the
boundary rather than inferred at each call site (research.md D3, contract G1). One day
either side of an effective date is the whole of the rule, and it is the half of a rate
schedule that a reader assumes rather than checks: an off-by-one here charges a whole
period at the wrong rate and every figure downstream still looks plausible.

Nothing in this module reads a file. The schedules are built in code from rates that are
deliberately unlike any real one -- 1%, 2%, 3% -- so that a test failure names a boundary
rather than a jurisdiction, and so that no reader can mistake a fixture for a legal fact.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry, RateUndeclaredBefore, rate_on

FIRST: date = date(2024, 1, 1)
SECOND: date = date(2025, 6, 15)
THIRD: date = date(2026, 3, 1)


def _sources(name: str) -> Provenance:
    """A distinct citation per entry, so a test can tell which entry a figure came from.

    Per entry rather than per class, because two rates cited by two sources are two
    observations (research.md D1, contract G4).
    """
    return prov.of(
        [
            SourceRef(
                id=f"fixture:{name}",
                citation=f"FIXTURE {name} -- an invented schedule entry, not a legal fact",
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _class_of(*entries: RateEntry) -> TaxClass:
    return TaxClass(
        id="fixture_class",
        applies_to=frozenset({TaxableEventKind.COUPON}),
        rates=entries,
    )


def _three_entries() -> TaxClass:
    """Three dated entries at 1%, 2% and 3% -- unlike any rate anyone could believe."""
    return _class_of(
        RateEntry(
            effective_from=FIRST, pit_rate=0.01, levy_rate=0.001, provenance=_sources("first")
        ),
        RateEntry(
            effective_from=SECOND, pit_rate=0.02, levy_rate=0.002, provenance=_sources("second")
        ),
        RateEntry(
            effective_from=THIRD, pit_rate=0.03, levy_rate=0.003, provenance=_sources("third")
        ),
    )


@pytest.mark.parametrize(
    ("on_date", "expected_from", "expected_pit"),
    [
        (FIRST, FIRST, 0.01),
        (date(2025, 6, 14), FIRST, 0.01),
        (SECOND, SECOND, 0.02),
        (date(2025, 6, 16), SECOND, 0.02),
        (date(2026, 2, 28), SECOND, 0.02),
        (THIRD, THIRD, 0.03),
        (date(2099, 12, 31), THIRD, 0.03),
    ],
)
def test_the_entry_in_force_is_the_latest_one_on_or_before_the_date(
    on_date: date,
    expected_from: date,
    expected_pit: float,
) -> None:
    """G1, at every boundary the schedule has and one day either side of two of them."""
    found = rate_on(_three_entries(), on_date)
    assert isinstance(found, RateEntry), found
    assert found.effective_from == expected_from
    assert found.pit_rate == expected_pit


def test_the_day_before_the_first_entry_is_a_refusal_and_not_the_first_entry() -> None:
    """The inclusive boundary read from the other side: 2023-12-31 is *before* the schedule.

    Stated as its own test rather than folded into the parametrisation above, because the
    dangerous failure is not "the wrong entry" but "an entry at all". A lookup that
    reached for the first entry here would silently charge 2024's rate on a 2023 event.
    """
    refused = rate_on(_three_entries(), date(2023, 12, 31))
    assert isinstance(refused, RateUndeclaredBefore), refused
    assert refused.earliest_declared == FIRST


def test_a_single_entry_schedule_is_in_force_from_its_date_forever_after() -> None:
    """The shape every real class in ``data/tax/ua.toml`` has: one cited entry, no history.

    That is not an unfinished schedule. Where a source establishes the current rate and
    not the date the previous one began, no earlier entry is invented and everything
    before the attested date refuses (research.md D2).
    """
    only = RateEntry(
        effective_from=SECOND, pit_rate=0.02, levy_rate=0.002, provenance=_sources("only")
    )
    declared = _class_of(only)
    assert rate_on(declared, SECOND) is only
    assert rate_on(declared, date(2100, 1, 1)) is only
    assert isinstance(rate_on(declared, date(2025, 6, 14)), RateUndeclaredBefore)
