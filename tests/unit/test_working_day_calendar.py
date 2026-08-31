"""The four questions a calendar answers, and the three ways it refuses.

017 FR-011 to FR-014. No rate series, no series identity and no money anywhere in this file:
what is under test is the classification, not anything a classification would later decide.

The calendars here are **synthetic and say so in their ids**. Real Ukrainian dates live in
``data/calendars/ua_civil.toml`` with their citations; nothing here is law.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from terezy.core.calendars import working_day as wd
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance, SourceRef

MONDAY = 0
SATURDAY = 5
SUNDAY = 6


def _sources(name: str, *, verified: bool = False) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=name,
                citation=f"synthetic://{name}",
                retrieved_on=date(2026, 1, 1),
                verified_on=date(2026, 1, 2) if verified else None,
                kind="tax_rule",
            )
        ]
    )


WEEK = wd.DeclaredWeek(
    rest_days=frozenset({SATURDAY, SUNDAY}),
    starts_on=MONDAY,
    provenance=_sources("week"),
)

# A fortnight, Monday 2026-03-02 to Sunday 2026-03-15, with three declared exceptions.
HOLIDAY = date(2026, 3, 5)  # Thursday, an enumerated public holiday
PRE_HOLIDAY = date(2026, 3, 4)  # Wednesday before it, working and shortened
MOVED_TO_WORKING = date(2026, 3, 7)  # Saturday an act moved into working status

FORTNIGHT = wd.WorkingDayCalendar(
    id="synthetic_fortnight",
    jurisdiction="XX",
    authority="a synthetic authority",
    scope=wd.CalendarScope.CIVIL,
    covers=(date(2026, 3, 2), date(2026, 3, 15)),
    covered_by=_sources("coverage"),
    week=WEEK,
    rows=(
        wd.WorkingDay(
            on_date=PRE_HOLIDAY,
            decided_by=wd.DecidedBy.DECLARED_MOVE,
            pre_holiday=True,
            provenance=_sources("pre_holiday"),
        ),
        wd.NonWorkingDay(
            on_date=HOLIDAY,
            decided_by=wd.DecidedBy.ENUMERATED_NON_WORKING_DAY,
            provenance=_sources("holiday"),
        ),
        wd.WorkingDay(
            on_date=MOVED_TO_WORKING,
            decided_by=wd.DecidedBy.DECLARED_MOVE,
            pre_holiday=False,
            provenance=_sources("moved"),
        ),
    ),
)

SETTLEMENT = wd.WorkingDayCalendar(
    id="synthetic_venue",
    jurisdiction="XX",
    authority="a synthetic operator",
    scope=wd.CalendarScope.SETTLEMENT,
    covers=(date(2026, 3, 2), date(2026, 3, 15)),
    covered_by=_sources("coverage"),
    week=WEEK,
    rows=(),
)

CALENDARS = {FORTNIGHT.id: FORTNIGHT, SETTLEMENT.id: SETTLEMENT}

QUERIES = (
    wd.classify,
    wd.first_working_day_on_or_after,
    wd.last_working_day_on_or_before,
    wd.last_working_day_of_week,
)


# ---------------------------------------------------------------------------
# The three refusals, asserted field by field (SC-003)
# ---------------------------------------------------------------------------


def test_the_refusal_union_has_exactly_three_members_and_none_for_a_jurisdiction() -> None:
    """FR-011. A fourth member, or one keyed to a jurisdiction, fails here.

    There is deliberately no *this jurisdiction has no calendar* reason: FR-003a means nothing
    looks a calendar up by jurisdiction, so nothing can discover that a jurisdiction has none,
    and shipping the reason would be a guard whose message is false.
    """
    members = {member.__name__ for member in wd.CalendarUnavailable.__value__.__args__}
    assert members == {"CalendarNotDeclared", "CalendarScopeMismatch", "CalendarOutOfCoverage"}
    for member in wd.CalendarUnavailable.__value__.__args__:
        assert "jurisdiction" not in member.__dataclass_fields__


def test_an_unknown_id_carries_the_id_and_no_window() -> None:
    """FR-011 reason 1. No calendar was found, so nothing is known to have a window."""
    refused = wd.classify(
        CALENDARS, "no_such_calendar", scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY
    )
    assert isinstance(refused, wd.CalendarNotDeclared)
    assert refused.wanted_id == "no_such_calendar"
    assert not hasattr(refused, "covers")
    assert "no_such_calendar" in refused.reason


def test_the_wrong_scope_carries_both_scopes() -> None:
    """FR-011 reason 2, SC-007: a consumer wanting `civil` handed a `settlement` calendar."""
    refused = wd.classify(
        CALENDARS, SETTLEMENT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 3)
    )
    assert isinstance(refused, wd.CalendarScopeMismatch)
    assert refused.calendar_id == SETTLEMENT.id
    assert refused.scope_wanted is wd.CalendarScope.CIVIL
    assert refused.scope_found is wd.CalendarScope.SETTLEMENT


@pytest.mark.parametrize(
    ("asked", "missed"),
    [
        (date(2026, 3, 1), wd.Missed.BEFORE_WINDOW),
        (date(2026, 3, 16), wd.Missed.AFTER_WINDOW),
    ],
)
def test_a_date_outside_the_window_carries_the_window_and_which_way_it_missed(
    asked: date, missed: wd.Missed
) -> None:
    """FR-010, FR-011 reason 3. The rest pattern is never extended past either end."""
    refused = wd.classify(CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=asked)
    assert isinstance(refused, wd.CalendarOutOfCoverage)
    assert refused.calendar_id == FORTNIGHT.id
    assert refused.on_date == asked
    assert refused.covers == FORTNIGHT.covers
    assert refused.missed is missed


def test_the_three_discriminators_are_distinct_and_exactly_three() -> None:
    assert {member.value for member in wd.Missed} == {
        "before_window",
        "after_window",
        "ran_off_an_end",
    }


# ---------------------------------------------------------------------------
# SC-002: the out-of-window battery, and nothing that turns it into an answer
# ---------------------------------------------------------------------------


def test_a_forward_search_that_leaves_the_window_refuses_rather_than_returning_its_edge() -> None:
    """FR-013. Sunday 2026-03-15 is the last covered date and it is a rest day."""
    refused = wd.first_working_day_on_or_after(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 15)
    )
    assert isinstance(refused, wd.CalendarOutOfCoverage)
    assert refused.missed is wd.Missed.RAN_OFF_AN_END
    assert refused.on_date == date(2026, 3, 15)


def test_a_backward_search_that_leaves_the_window_refuses() -> None:
    """FR-013 in the other direction: a window that opens on a rest day has nothing behind it.

    Both cases run against the same calendar, so what separates them is the question rather
    than the declaration: from Friday the search finds a working day inside the window, and
    from Sunday it walks back over two rest days and off the near end.
    """
    weekend_open = wd.WorkingDayCalendar(
        id="synthetic_weekend_open",
        jurisdiction="XX",
        authority="a synthetic authority",
        scope=wd.CalendarScope.CIVIL,
        covers=(date(2026, 3, 7), date(2026, 3, 13)),  # Saturday to the following Friday
        covered_by=_sources("coverage"),
        week=WEEK,
        rows=(),
    )
    calendars = {weekend_open.id: weekend_open}
    found = wd.last_working_day_on_or_before(
        calendars, weekend_open.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 13)
    )
    assert isinstance(found, wd.WorkingDay)
    assert found.on_date == date(2026, 3, 13)

    ran_off = wd.last_working_day_on_or_before(
        calendars, weekend_open.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 8)
    )
    assert isinstance(ran_off, wd.CalendarOutOfCoverage)
    assert ran_off.missed is wd.Missed.RAN_OFF_AN_END
    assert ran_off.on_date == date(2026, 3, 8)


def test_a_week_straddling_the_boundary_refuses_even_though_it_holds_a_working_day() -> None:
    """FR-014. The window's last week is Monday 2026-03-09 to Sunday 2026-03-15, so a calendar
    ending mid-week cannot see the end of the week it is asked about."""
    truncated = wd.WorkingDayCalendar(
        id="synthetic_truncated",
        jurisdiction="XX",
        authority="a synthetic authority",
        scope=wd.CalendarScope.CIVIL,
        covers=(date(2026, 3, 2), date(2026, 3, 11)),  # ends on a Wednesday
        covered_by=_sources("coverage"),
        week=WEEK,
        rows=(),
    )
    refused = wd.last_working_day_of_week(
        {truncated.id: truncated},
        truncated.id,
        scope=wd.CalendarScope.CIVIL,
        on_date=date(2026, 3, 10),
    )
    assert isinstance(refused, wd.CalendarOutOfCoverage)
    assert refused.missed is wd.Missed.RAN_OFF_AN_END


def test_no_query_has_a_default_that_would_answer_one_of_these() -> None:
    """SC-002, SC-011: no configuration, flag or default turns a refusal into an answer.

    A default for ``calendars`` or ``on_date`` would let a caller ask without supplying one,
    which is the module-held calendar FR-016 forbids; any *other* parameter with a default
    would be the declared option SC-002 says must not exist.
    """
    for query in QUERIES:
        signature = inspect.signature(query)
        assert list(signature.parameters) == [
            "calendars",
            "calendar_id",
            "scope",
            "on_date",
        ], query.__name__
        for name, parameter in signature.parameters.items():
            assert parameter.default is inspect.Parameter.empty, f"{query.__name__}.{name}"


def test_every_query_refuses_the_same_three_ways() -> None:
    """The preconditions are shared, so a query that forgot one is visible here."""
    for query in QUERIES:
        unknown = query(CALENDARS, "absent", scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY)
        assert isinstance(unknown, wd.CalendarNotDeclared), query.__name__
        mismatched = query(CALENDARS, SETTLEMENT.id, scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY)
        assert isinstance(mismatched, wd.CalendarScopeMismatch), query.__name__
        outside = query(
            CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 2, 1)
        )
        assert isinstance(outside, wd.CalendarOutOfCoverage), query.__name__
        assert outside.missed is wd.Missed.BEFORE_WINDOW, query.__name__


# ---------------------------------------------------------------------------
# FR-012 to FR-014 over the fortnight (SC-008)
# ---------------------------------------------------------------------------


def test_a_working_day_the_pattern_decided_says_the_pattern_decided_it() -> None:
    answer = wd.classify(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 2)
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.decided_by is wd.DecidedBy.REST_PATTERN
    assert answer.pre_holiday is False
    assert {ref.id for ref in answer.provenance.sources} == {"week", "coverage"}


def test_a_pre_holiday_day_is_reported_as_working_and_as_pre_holiday() -> None:
    """FR-012, Story 3 scenario 3: the two facts are not collapsed into one."""
    answer = wd.classify(CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=PRE_HOLIDAY)
    assert isinstance(answer, wd.WorkingDay)
    assert answer.pre_holiday is True


def test_a_pre_holiday_non_working_day_is_unrepresentable() -> None:
    """Key Entities: refused by the shape of the record, not by a check at the query."""
    assert "pre_holiday" in wd.WorkingDay.__dataclass_fields__
    assert "pre_holiday" not in wd.NonWorkingDay.__dataclass_fields__


def test_the_first_working_day_after_a_holiday_skips_every_consecutive_rest_day() -> None:
    """Story 3 scenario 2. Thursday 2026-03-05 is a holiday; Friday is an ordinary working
    day, so the answer is Friday and the moved Saturday is not reached."""
    answer = wd.first_working_day_on_or_after(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.on_date == date(2026, 3, 6)


def test_the_last_working_day_of_the_week_uses_the_declared_week_start() -> None:
    """FR-014. Week one runs Monday 2026-03-02 to Sunday 2026-03-08 and its last working day
    is the moved Saturday 2026-03-07, not Friday: the move is what decides it."""
    answer = wd.last_working_day_of_week(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 4)
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.on_date == MOVED_TO_WORKING
    assert answer.decided_by is wd.DecidedBy.DECLARED_MOVE


def test_a_different_declared_week_start_gives_a_different_answer_to_the_same_date() -> None:
    """FR-014: the week start is data, not an assumption.

    Two calendars differing in nothing but ``starts_on``, asked about Sunday 2026-03-08. Under
    a Monday start that Sunday closes the week the moved Saturday belongs to; under a Sunday
    start it opens the next one, whose last working day is the following Friday.
    """

    def _three_weeks(identity: str, starts_on: int) -> wd.WorkingDayCalendar:
        return wd.WorkingDayCalendar(
            id=identity,
            jurisdiction="XX",
            authority="a synthetic authority",
            scope=wd.CalendarScope.CIVIL,
            covers=(date(2026, 3, 1), date(2026, 3, 21)),
            covered_by=_sources("coverage"),
            week=wd.DeclaredWeek(
                rest_days=frozenset({SATURDAY, SUNDAY}),
                starts_on=starts_on,
                provenance=_sources("week"),
            ),
            rows=FORTNIGHT.rows,
        )

    answers: dict[str, date] = {}
    for identity, starts_on in (("monday_start", MONDAY), ("sunday_start", SUNDAY)):
        calendar = _three_weeks(identity, starts_on)
        answer = wd.last_working_day_of_week(
            {identity: calendar},
            identity,
            scope=wd.CalendarScope.CIVIL,
            on_date=date(2026, 3, 8),
        )
        assert isinstance(answer, wd.WorkingDay)
        answers[identity] = answer.on_date
    assert answers == {
        "monday_start": MOVED_TO_WORKING,
        "sunday_start": date(2026, 3, 13),
    }


def test_the_last_working_day_on_or_before_a_holiday_is_the_day_before_it() -> None:
    answer = wd.last_working_day_on_or_before(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.on_date == PRE_HOLIDAY
    assert answer.pre_holiday is True


def test_an_unverified_row_marks_the_answer_it_decided() -> None:
    """SC-005: the mark is the deciding declaration's own, so it survives onto the answer."""
    answer = wd.classify(CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=HOLIDAY)
    assert isinstance(answer, wd.NonWorkingDay)
    assert prov.is_unverified(answer.provenance)
    assert {ref.id for ref in prov.unverified_sources(answer.provenance)} == {
        "holiday",
        "coverage",
    }


def test_a_week_with_no_working_day_is_a_violated_invariant_rather_than_a_refusal() -> None:
    """The loader refuses such a calendar, so reaching here means one was built by hand.

    The window holds **two** weeks and only the second is shut, which is what makes this a
    regression rather than a tautology: a search bounded by the coverage window instead of by
    the week walks back into week one and returns Friday 2026-03-06 — a working day, in the
    wrong week, indistinguishable from a correct answer. FR-011 fixes the refusal union at
    three reasons and none of them is *this week has no working day*, so the answer is a
    violated invariant.
    """
    shut = wd.WorkingDayCalendar(
        id="synthetic_shut",
        jurisdiction="XX",
        authority="a synthetic authority",
        scope=wd.CalendarScope.CIVIL,
        covers=(date(2026, 3, 2), date(2026, 3, 15)),
        covered_by=_sources("coverage"),
        week=WEEK,
        rows=tuple(
            wd.NonWorkingDay(
                on_date=date(2026, 3, 9) + wd.ONE_DAY * offset,
                decided_by=wd.DecidedBy.ENUMERATED_NON_WORKING_DAY,
                provenance=_sources("shut"),
            )
            for offset in range(5)
        ),
    )
    assert wd.week_without_a_working_day(shut) == date(2026, 3, 9)
    with pytest.raises(ValueError, match="synthetic_shut"):
        wd.last_working_day_of_week(
            {shut.id: shut}, shut.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 10)
        )


def test_the_first_week_still_answers_from_inside_itself() -> None:
    """The complement: the same shape asked about the week that is intact."""
    assert wd.week_without_a_working_day(FORTNIGHT) is None
    answer = wd.last_working_day_of_week(
        CALENDARS, FORTNIGHT.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 10)
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.on_date == date(2026, 3, 13)
