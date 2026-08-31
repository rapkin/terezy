"""Every date of a fortnight classified by hand, then by the engine (017 SC-001).

**The calendar below is SYNTHETIC. Its dates are invented, not observed**, exactly as 011's
acceptance examples used synthetic rate observations. What is under test is the classification
rule -- how a declared rest pattern and an enumerated set of exceptions combine -- not
Ukrainian law. The real Ukrainian calendar is ``data/calendars/ua_civil.toml``, which carries
its own citations and declares no holidays at all, because ст. 53 and ст. 73 КЗпП are not
applied during martial law.

## The declaration, stated once so the table below can be checked against it

* **Window**: Monday 2026-03-02 to Sunday 2026-03-15. Fourteen days, two whole weeks.
* **Rest pattern**: Saturday and Sunday. **Week starts**: Monday.
* **Three enumerated exceptions**, each with its own citation:
  * ``2026-03-04`` (Wednesday) -- a **pre-holiday** working day, shortened because a holiday
    follows it;
  * ``2026-03-05`` (Thursday) -- an enumerated **public holiday**;
  * ``2026-03-07`` (Saturday) -- a rest day a **declared move** turned into a working day.

## The table, worked out by hand from those five facts

| date | weekday | working? | decided by | pre-holiday? |
| --- | --- | --- | --- | --- |
| 2026-03-02 | Monday | yes | rest pattern | no |
| 2026-03-03 | Tuesday | yes | rest pattern | no |
| 2026-03-04 | Wednesday | yes | declared move | **yes** |
| 2026-03-05 | Thursday | **no** | enumerated non-working day | — |
| 2026-03-06 | Friday | yes | rest pattern | no |
| 2026-03-07 | Saturday | **yes** | declared move | no |
| 2026-03-08 | Sunday | no | rest pattern | — |
| 2026-03-09 | Monday | yes | rest pattern | no |
| 2026-03-10 | Tuesday | yes | rest pattern | no |
| 2026-03-11 | Wednesday | yes | rest pattern | no |
| 2026-03-12 | Thursday | yes | rest pattern | no |
| 2026-03-13 | Friday | yes | rest pattern | no |
| 2026-03-14 | Saturday | no | rest pattern | — |
| 2026-03-15 | Sunday | no | rest pattern | — |

Ten working days out of fourteen, one of them shortened, and exactly three of the fourteen
decided by something other than the pattern. Every one of those three is a declared row; the
other eleven are the ordinary case, which is listed rather than assumed because an enumerated
form could otherwise be read as needing a row per day.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.calendars import working_day as wd
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance, SourceRef

pytestmark = pytest.mark.worked_example

MONDAY = 0
SATURDAY = 5
SUNDAY = 6


def _cited(name: str) -> Provenance:
    """One synthetic citation per declaration element, unverified, as the real file's are."""
    return prov.of(
        [
            SourceRef(
                id=f"synthetic_fortnight.{name}",
                citation=f"synthetic://fortnight/{name}",
                retrieved_on=date(2026, 3, 1),
                verified_on=None,
                kind="tax_rule",
            )
        ]
    )


FORTNIGHT = wd.WorkingDayCalendar(
    id="synthetic_fortnight",
    jurisdiction="XX",
    authority="a synthetic authority",
    scope=wd.CalendarScope.CIVIL,
    covers=(date(2026, 3, 2), date(2026, 3, 15)),
    covered_by=_cited("coverage"),
    week=wd.DeclaredWeek(
        rest_days=frozenset({SATURDAY, SUNDAY}),
        starts_on=MONDAY,
        provenance=_cited("week"),
    ),
    rows=(
        wd.WorkingDay(
            on_date=date(2026, 3, 4),
            decided_by=wd.DecidedBy.DECLARED_MOVE,
            pre_holiday=True,
            provenance=_cited("pre_holiday"),
        ),
        wd.NonWorkingDay(
            on_date=date(2026, 3, 5),
            decided_by=wd.DecidedBy.ENUMERATED_NON_WORKING_DAY,
            provenance=_cited("holiday"),
        ),
        wd.WorkingDay(
            on_date=date(2026, 3, 7),
            decided_by=wd.DecidedBy.DECLARED_MOVE,
            pre_holiday=False,
            provenance=_cited("moved"),
        ),
    ),
)

CALENDARS = {FORTNIGHT.id: FORTNIGHT}

PATTERN = wd.DecidedBy.REST_PATTERN
ENUMERATED = wd.DecidedBy.ENUMERATED_NON_WORKING_DAY
MOVE = wd.DecidedBy.DECLARED_MOVE

BY_HAND: tuple[tuple[date, bool, wd.DecidedBy, bool], ...] = (
    (date(2026, 3, 2), True, PATTERN, False),
    (date(2026, 3, 3), True, PATTERN, False),
    (date(2026, 3, 4), True, MOVE, True),
    (date(2026, 3, 5), False, ENUMERATED, False),
    (date(2026, 3, 6), True, PATTERN, False),
    (date(2026, 3, 7), True, MOVE, False),
    (date(2026, 3, 8), False, PATTERN, False),
    (date(2026, 3, 9), True, PATTERN, False),
    (date(2026, 3, 10), True, PATTERN, False),
    (date(2026, 3, 11), True, PATTERN, False),
    (date(2026, 3, 12), True, PATTERN, False),
    (date(2026, 3, 13), True, PATTERN, False),
    (date(2026, 3, 14), False, PATTERN, False),
    (date(2026, 3, 15), False, PATTERN, False),
)
"""The docstring's table as data: date, working, what decided it, whether it is pre-holiday."""


@pytest.mark.parametrize(("on_date", "working", "decided_by", "pre_holiday"), BY_HAND)
def test_each_date_of_the_window_classifies_as_the_hand_table_says(
    on_date: date, working: bool, decided_by: wd.DecidedBy, pre_holiday: bool
) -> None:
    answer = wd.classify(CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=on_date)
    assert isinstance(answer, wd.WorkingDay | wd.NonWorkingDay)
    assert isinstance(answer, wd.WorkingDay) is working
    assert answer.on_date == on_date
    assert answer.decided_by is decided_by
    if isinstance(answer, wd.WorkingDay):
        assert answer.pre_holiday is pre_holiday


def test_the_table_covers_the_whole_window_and_nothing_outside_it() -> None:
    """A table shorter than the window would leave dates the parametrised test never asks
    about, and the classification it never asserts is exactly the one that would be wrong."""
    first, last = FORTNIGHT.covers
    dated = [row[0] for row in BY_HAND]
    assert dated == [first + wd.ONE_DAY * offset for offset in range((last - first).days + 1)]


def test_the_counts_the_docstring_states_are_the_counts_the_table_holds() -> None:
    """The docstring's *ten working days, one shortened, three decided by a row* as a check."""
    assert sum(1 for _, working, _, _ in BY_HAND if working) == 10
    assert sum(1 for _, _, _, pre_holiday in BY_HAND if pre_holiday) == 1
    assert sum(1 for _, _, decided_by, _ in BY_HAND if decided_by is not PATTERN) == 3
    assert len(FORTNIGHT.rows) == 3


def test_every_answer_carries_the_mark_of_the_declaration_that_decided_it() -> None:
    """Principle I's propagation, per date.

    Two citations on every answer and not one: the deciding declaration's, and the coverage
    window's. The second is load-bearing rather than decorative -- *no row for this date*
    means *the law declared no exception here* only because somebody read the law for this
    window, and without that claim it would mean *nobody transcribed this date*.
    """
    expected = {
        date(2026, 3, 4): "synthetic_fortnight.pre_holiday",
        date(2026, 3, 5): "synthetic_fortnight.holiday",
        date(2026, 3, 7): "synthetic_fortnight.moved",
        date(2026, 3, 9): "synthetic_fortnight.week",
    }
    for on_date, source_id in expected.items():
        answer = wd.classify(CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=on_date)
        assert isinstance(answer, wd.WorkingDay | wd.NonWorkingDay)
        assert prov.is_unverified(answer.provenance)
        assert {ref.id for ref in answer.provenance.sources} == {
            source_id,
            "synthetic_fortnight.coverage",
        }
