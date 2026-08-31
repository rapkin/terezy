"""A second jurisdiction's calendar is a data-only addition, and nothing consumes either.

017 Story 4, SC-006, SC-007, SC-010 and SC-011. Principle II applied to the input most likely
to be hard-coded as a singleton: a five-day week, a Monday week start and a Saturday-Sunday
weekend are all facts about one country, and a calendar shaped around them would make a second
jurisdiction's silently Ukrainian.

The second calendar here rests six days a week and starts its week on Sunday, so a Ukrainian
assumption baked into the shape shows up as a wrong answer rather than as a passing test.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from terezy.core.calendars import working_day as wd
from terezy.core.primitives.staleness import ObservationKind
from terezy.data.declarations import resolver

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "terezy"
SHIPPED_DIR = REPO_ROOT / "data" / "calendars"

KINDS = {"tax_rule": ObservationKind(id="tax_rule", staleness_days=180, note="a synthetic kind")}

SECOND_JURISDICTION = """
day = []

[calendar]
id           = "zz_civil"
jurisdiction = "ZZ"
authority    = "SYNTHETIC FIXTURE -- an invented legislature"
scope        = "civil"

[calendar.coverage]
first        = "2026-03-01"
last         = "2026-03-31"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented reading of an invented law."
retrieved_on = "2026-03-01"
verified_on  = ""

[calendar.week]
rest_days    = ["friday"]
starts_on    = "sunday"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented rest pattern: one rest day, and not ours."
retrieved_on = "2026-03-01"
verified_on  = ""
"""

A_VENUES_SETTLEMENT_CALENDAR = SECOND_JURISDICTION.replace(
    'id           = "zz_civil"', 'id           = "zz_venue"'
).replace('scope        = "civil"', 'scope        = "settlement"')


def _root(tmp_path: Path, *files: str) -> Path:
    """A scratch data root holding the shipped calendar plus whatever a case adds."""
    root = tmp_path / "data"
    directory = root / resolver.CALENDARS_DIR
    directory.mkdir(parents=True)
    for shipped in sorted(SHIPPED_DIR.glob("*.toml")):
        (directory / shipped.name).write_text(shipped.read_text(encoding="utf-8"), encoding="utf-8")
    for index, text in enumerate(files):
        (directory / f"added_{index}.toml").write_text(text, encoding="utf-8")
    return root


def test_a_second_jurisdiction_loads_and_is_addressable_by_its_own_id(tmp_path: Path) -> None:
    """SC-006, first half: a file, and no source change."""
    declared = resolver.working_day_calendars_from_data_root(
        _root(tmp_path, SECOND_JURISDICTION), KINDS
    )
    assert set(declared.calendars) == {"ua_civil", "zz_civil"}
    assert declared.calendars["zz_civil"].jurisdiction == "ZZ"
    assert declared.calendars["zz_civil"].week.rest_days == frozenset({4})
    assert declared.calendars["zz_civil"].week.starts_on == 6


def test_the_second_calendar_classifies_by_its_own_pattern_and_leaves_the_first_alone(
    tmp_path: Path,
) -> None:
    """SC-006, second half. Friday 2026-03-06 rests under ZZ's pattern and works under UA's;
    Sunday 2026-03-08 is the reverse. Two calendars, one date, two answers, each naming its
    own calendar -- which is what makes the second one a real addition rather than a copy."""
    calendars = resolver.working_day_calendars_from_data_root(
        _root(tmp_path, SECOND_JURISDICTION), KINDS
    ).calendars
    expected = {
        ("zz_civil", date(2026, 3, 6)): False,
        ("ua_civil", date(2026, 3, 6)): True,
        ("zz_civil", date(2026, 3, 8)): True,
        ("ua_civil", date(2026, 3, 8)): False,
    }
    for (calendar_id, on_date), working in expected.items():
        answer = wd.classify(calendars, calendar_id, scope=wd.CalendarScope.CIVIL, on_date=on_date)
        assert isinstance(answer, wd.WorkingDay | wd.NonWorkingDay)
        assert isinstance(answer, wd.WorkingDay) is working, (calendar_id, on_date)


def test_two_calendars_for_one_jurisdiction_are_not_a_load_error(tmp_path: Path) -> None:
    """FR-003a: a jurisdiction may legitimately have a civil calendar and a venue's settlement
    one, and picking between them by jurisdiction would decide a legal question by directory
    contents. So only the **id** collides."""
    declared = resolver.working_day_calendars_from_data_root(
        _root(tmp_path, SECOND_JURISDICTION, A_VENUES_SETTLEMENT_CALENDAR), KINDS
    )
    assert set(declared.calendars) == {"ua_civil", "zz_civil", "zz_venue"}
    jurisdictions = [calendar.jurisdiction for calendar in declared.calendars.values()]
    assert jurisdictions.count("ZZ") == 2


def test_a_consumer_wanting_a_civil_calendar_refuses_a_settlement_one(tmp_path: Path) -> None:
    """SC-007, over a calendar that came from a file rather than from a constructor.

    This is what makes FR-003b's check reachable in a feature that ships no consumer: the test
    asks the question a consumer would, and the refusal is produced where the question is
    answered rather than at load, because at load there is no question to check a scope
    against.
    """
    calendars = resolver.working_day_calendars_from_data_root(
        _root(tmp_path, A_VENUES_SETTLEMENT_CALENDAR), KINDS
    ).calendars
    refused = wd.classify(
        calendars, "zz_venue", scope=wd.CalendarScope.CIVIL, on_date=date(2026, 3, 6)
    )
    assert isinstance(refused, wd.CalendarScopeMismatch)
    assert refused.scope_wanted is wd.CalendarScope.CIVIL
    assert refused.scope_found is wd.CalendarScope.SETTLEMENT
    assert "civil" in refused.reason
    assert "settlement" in refused.reason


def test_no_module_in_the_source_tree_names_the_added_calendars(tmp_path: Path) -> None:
    """SC-006's *zero source lines changed*, asserted rather than claimed.

    The scratch root above is loaded by the shipped loader with no branch for either file. If a
    module named one of these ids, the addition would not be data-only however green the tests
    above ran.
    """
    declared = resolver.working_day_calendars_from_data_root(
        _root(tmp_path, SECOND_JURISDICTION, A_VENUES_SETTLEMENT_CALENDAR), KINDS
    )
    assert {"zz_civil", "zz_venue"} <= set(declared.calendars)
    mentions = [
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if any(
            token in path.read_text(encoding="utf-8") for token in ("zz_civil", "zz_venue", '"ZZ"')
        )
    ]
    assert not mentions, f"these modules name a calendar that exists only as data: {mentions}"


def test_no_module_holds_a_calendar_of_its_own() -> None:
    """SC-011, FR-016: every calendar is an argument.

    A module-level ``WorkingDayCalendar`` would make *which calendar answered this*
    unrecoverable from a result, and every classification here is an input to a legal figure
    downstream. The other half of SC-011 -- that no query carries a default that would let a
    caller omit one -- is
    ``tests/unit/test_working_day_calendar.py::test_no_query_has_a_default_that_would_answer_one_of_these``.
    """
    constructing = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:  # module level only: a call inside a function takes arguments
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute | ast.Name)
                and getattr(value.func, "attr", getattr(value.func, "id", ""))
                == "WorkingDayCalendar"
            ):
                constructing.append(path.relative_to(SRC).as_posix())
    assert not constructing, f"these modules hold a calendar rather than taking one: {constructing}"


def test_nothing_outside_the_declaration_layer_imports_the_calendar() -> None:
    """SC-010: this feature stayed on its own side of FR-015's no-consumer line.

    A module that started importing ``core.calendars`` would be the first consumer, and the
    first thing to check would be whether a rate, a settlement or a deadline began moving. That
    is a question for whichever feature wires one up; it is not this one.
    """
    allowed = {
        "data/declarations/loader.py",
        "data/declarations/resolver.py",
    }
    importing = {
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if "terezy.core.calendars" in path.read_text(encoding="utf-8")
        and not path.relative_to(SRC).as_posix().startswith("core/calendars/")
    }
    assert importing == allowed, (
        f"these modules import the calendar: {sorted(importing)}, and 017 FR-015 ships it with "
        f"no consumer. The declaration layer is expected ({sorted(allowed)}); anything else is "
        "a consumer, and wiring one up is a decision about WHICH KIND of calendar governs that "
        "site — which only an issue's own terms, or an operator's, can answer."
    )
