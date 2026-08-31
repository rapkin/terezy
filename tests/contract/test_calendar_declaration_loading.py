"""017 FR-007 and SC-004: every broken calendar file fails at load, naming the offence.

*"Loading a calendar MUST fail loudly -- naming the file and the offending field or date --
on a malformed value, an unrecognised field, a missing required field, a missing coverage
window, a missing or empty rest pattern, a rest pattern naming every weekday, a missing week
start, a duplicated calendar identity, two rows classifying the same date, a row dated
outside the coverage window, a pre-holiday fact attached to a non-working date, or an
undeclared observation kind. No default MUST be substituted for anything absent."*

A battery rather than a handful, because SC-004 is a claim about *every* way a file can be
wrong and a sampled version would go stale the first time somebody added a field.

**Two cases are this feature's own.**

*A pre-holiday fact on a non-working date.* A pre-holiday day is a working day the law
shortens, so declaring one on a holiday is two facts that cannot both hold. It is writable in
TOML on purpose and refused here; in the core there is no field for it at all, so the wrong
state is unrepresentable rather than repeatedly checked.

*A week inside the window with no working day.* The all-seven rest pattern is refused for a
stated reason, and seven consecutive non-working rows reach the same state by another road.
Refusing here keeps the query total and keeps the refusal union at FR-011's three reasons.

The last tests load the **shipped** ``data/calendars/ua_civil.toml``, because a battery of
broken files proves nothing about the file the project actually uses.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from terezy.core.calendars import working_day as wd
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.staleness import ObservationKind
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
_KINDS = {"tax_rule": ObservationKind(id="tax_rule", staleness_days=180, note="a synthetic kind")}
SHIPPED = REPO_ROOT / "data" / "calendars" / "ua_civil.toml"

WHOLE = """
# ``day`` sits above ``[calendar]`` because TOML binds a bare key to the table it follows:
# written below, it would declare ``calendar.day``.
day = []

[calendar]
id           = "xx_civil"
jurisdiction = "XX"
authority    = "SYNTHETIC FIXTURE -- an invented legislature"
scope        = "civil"

[calendar.coverage]
first        = "2026-03-02"
last         = "2026-03-15"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented reading of an invented law."
retrieved_on = "2026-03-01"
verified_on  = ""

[calendar.week]
rest_days    = ["saturday", "sunday"]
starts_on    = "monday"
kind         = "tax_rule"
source       = "SYNTHETIC FIXTURE -- an invented rest pattern."
retrieved_on = "2026-03-01"
verified_on  = ""
"""

ROW = """
[[day]]
on_date        = "{on_date}"
classification = "{classification}"
pre_holiday    = {pre_holiday}
kind           = "{kind}"
source         = "SYNTHETIC FIXTURE -- an invented classification."
retrieved_on   = "2026-03-01"
verified_on    = ""
"""


HEADER = WHOLE.replace("day = []\n", "")
"""``WHOLE`` without its ``day = []``, because TOML refuses a key redefined as a table array:
a fixture that declared an empty enumeration and then appended a row would fail to parse, and
every row case below would pass on the wrong fault."""


def _row(
    on_date: str,
    classification: str = "public_holiday",
    *,
    pre_holiday: bool = False,
    kind: str = "tax_rule",
) -> str:
    return ROW.format(
        on_date=on_date,
        classification=classification,
        pre_holiday=str(pre_holiday).lower(),
        kind=kind,
    )


def _written(tmp_path: Path, text: str, name: str = "xx_civil.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _refused(tmp_path: Path, text: str) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        loader.working_day_calendar_from_file(_written(tmp_path, text))
    return raised.value


def test_the_whole_fixture_loads_so_the_battery_below_isolates_one_fault_each(
    tmp_path: Path,
) -> None:
    """The baseline every case mutates. Without it a case could pass on the wrong fault."""
    calendar = loader.working_day_calendar_from_file(_written(tmp_path, WHOLE))
    assert calendar.id == "xx_civil"
    assert calendar.scope is wd.CalendarScope.CIVIL
    assert calendar.covers == (
        date(2026, 3, 2),
        date(2026, 3, 15),
    )
    assert calendar.week.rest_days == frozenset({5, 6})
    assert calendar.week.starts_on == 0
    assert calendar.rows == ()


@pytest.mark.parametrize(
    ("case", "mutated", "field_path"),
    [
        (
            "an unrecognised field",
            WHOLE.replace('scope        = "civil"', 'scope = "civil"\nregion = "north"'),
            "calendar.region",
        ),
        (
            "a missing coverage window",
            WHOLE.replace('first        = "2026-03-02"\n', ""),
            "calendar.coverage.first",
        ),
        (
            "a missing rest pattern",
            WHOLE.replace('rest_days    = ["saturday", "sunday"]\n', ""),
            "calendar.week.rest_days",
        ),
        (
            "a missing week start",
            WHOLE.replace('starts_on    = "monday"\n', ""),
            "calendar.week.starts_on",
        ),
        (
            "a missing verification date",
            WHOLE.replace('retrieved_on = "2026-03-01"\nverified_on  = ""\n', "", 1),
            "calendar.coverage.retrieved_on",
        ),
        (
            "an omitted enumeration",
            WHOLE.replace("day = []\n", ""),
            "day",
        ),
    ],
)
def test_a_missing_or_unrecognised_field_names_itself(
    tmp_path: Path, case: str, mutated: str, field_path: str
) -> None:
    """FR-007: the shape validation names the field, and nothing is substituted for it."""
    refused = _refused(tmp_path, mutated)
    assert refused.field_path == field_path, case


@pytest.mark.parametrize(
    ("case", "mutated", "field_path", "quoted"),
    [
        (
            "a malformed coverage date",
            WHOLE.replace('first        = "2026-03-02"', 'first        = "2 March 2026"'),
            "calendar.coverage.first",
            "2 March 2026",
        ),
        (
            "a window running backwards",
            WHOLE.replace('last         = "2026-03-15"', 'last         = "2026-02-15"'),
            "calendar.coverage.last",
            "2026-02-15",
        ),
        (
            "an empty rest pattern",
            WHOLE.replace('rest_days    = ["saturday", "sunday"]', "rest_days    = []"),
            "calendar.week.rest_days",
            "",
        ),
        (
            "a rest pattern naming every weekday",
            WHOLE.replace(
                'rest_days    = ["saturday", "sunday"]',
                'rest_days    = ["monday", "tuesday", "wednesday", "thursday", "friday", '
                '"saturday", "sunday"]',
            ),
            "calendar.week.rest_days",
            "",
        ),
        (
            "a weekday declared twice",
            WHOLE.replace(
                'rest_days    = ["saturday", "sunday"]',
                'rest_days    = ["sunday", "sunday"]',
            ),
            "calendar.week.rest_days",
            "",
        ),
        (
            "an unrecognised weekday",
            WHOLE.replace('starts_on    = "monday"', 'starts_on    = "mondey"'),
            "calendar.week.starts_on",
            "mondey",
        ),
        (
            "an unrecognised scope",
            WHOLE.replace('scope        = "civil"', 'scope        = "publication"'),
            "calendar.scope",
            "publication",
        ),
        (
            "an empty identity",
            WHOLE.replace('id           = "xx_civil"', 'id           = ""'),
            "calendar.id",
            "",
        ),
        (
            "an unrecognised classification",
            HEADER + _row("2026-03-05", "bank_holiday"),
            "day[0].classification",
            "bank_holiday",
        ),
        (
            "two rows for one date",
            HEADER + _row("2026-03-05") + _row("2026-03-05"),
            "day[1].on_date",
            "2026-03-05",
        ),
        (
            "rows out of order",
            HEADER + _row("2026-03-06") + _row("2026-03-05"),
            "day[1].on_date",
            "2026-03-05",
        ),
        (
            "a row before the window",
            HEADER + _row("2026-03-01"),
            "day[0].on_date",
            "2026-03-01",
        ),
        (
            "a row after the window",
            HEADER + _row("2026-03-16"),
            "day[0].on_date",
            "2026-03-16",
        ),
        (
            "a pre-holiday day on a public holiday",
            HEADER + _row("2026-03-05", "public_holiday", pre_holiday=True),
            "day[0].pre_holiday",
            "2026-03-05",
        ),
        (
            "a pre-holiday day on a moved rest day",
            HEADER + _row("2026-03-05", "rest_day", pre_holiday=True),
            "day[0].pre_holiday",
            "2026-03-05",
        ),
        (
            "a rest pattern with no citation",
            WHOLE.replace(
                'source       = "SYNTHETIC FIXTURE -- an invented rest pattern."',
                'source       = ""',
            ),
            "calendar.week.source",
            "",
        ),
        (
            "a coverage window with no citation",
            WHOLE.replace(
                'source       = "SYNTHETIC FIXTURE -- an invented reading of an invented law."',
                'source       = ""',
            ),
            "calendar.coverage.source",
            "",
        ),
        (
            "a row with no citation",
            (HEADER + _row("2026-03-05")).replace(
                'source         = "SYNTHETIC FIXTURE -- an invented classification."',
                'source         = ""',
            ),
            "day[0].source",
            "",
        ),
        (
            "a row naming no observation kind",
            HEADER + _row("2026-03-05", kind=""),
            "day[0].kind",
            "",
        ),
    ],
)
def test_a_malformed_value_names_the_file_and_the_field_or_date(
    tmp_path: Path, case: str, mutated: str, field_path: str, quoted: str
) -> None:
    """FR-007, SC-004: every case names the file, names where, and substitutes no default."""
    refused = _refused(tmp_path, mutated)
    assert refused.field_path == field_path, case
    assert refused.file.name == "xx_civil.toml", case
    if quoted:
        assert quoted in refused.problem, case


def test_a_week_with_no_working_day_inside_the_window_is_refused_at_load(
    tmp_path: Path,
) -> None:
    """Monday 2026-03-09 to Friday 2026-03-13 declared non-working closes a whole week, since
    the pattern already rests Saturday and Sunday. The refusal names the week, not a date the
    caller asked about."""
    shut = HEADER + "".join(_row(f"2026-03-{day:02d}") for day in range(9, 14))
    refused = _refused(tmp_path, shut)
    assert refused.field_path == "day"
    assert "2026-03-09" in refused.problem


def test_a_week_straddling_the_window_needs_no_working_day(tmp_path: Path) -> None:
    """The complement of the case above, and the reason it is scoped to whole weeks: a partial
    week at either end is refused at the query with the ran-off-an-end discriminator, so
    requiring a working day in it would refuse a legitimate declaration at load."""
    partial = HEADER.replace('last         = "2026-03-15"', 'last         = "2026-03-18"')
    partial += _row("2026-03-16") + _row("2026-03-17") + _row("2026-03-18")
    calendar = loader.working_day_calendar_from_file(_written(tmp_path, partial))
    assert len(calendar.rows) == 3


def test_two_files_declaring_one_identity_name_both(tmp_path: Path) -> None:
    """A relation rather than a property of one file, so it belongs to the resolver."""
    root = tmp_path / "data"
    (root / resolver.CALENDARS_DIR).mkdir(parents=True)
    for name in ("a.toml", "b.toml"):
        (root / resolver.CALENDARS_DIR / name).write_text(WHOLE, encoding="utf-8")
    with pytest.raises(DeclarationError) as raised:
        resolver.working_day_calendars_from_data_root(root, _KINDS)
    assert raised.value.field_path == "calendar.id"
    assert "a.toml" in raised.value.problem
    assert raised.value.file.name == "b.toml"


@pytest.mark.parametrize("table", ["calendar.coverage", "calendar.week"])
def test_an_undeclared_observation_kind_on_a_numberless_table_is_refused(
    tmp_path: Path, table: str
) -> None:
    """The two tables that carry a citation and can never carry a number.

    A calendar declaring ``day = []`` has only these left, and a misspelt kind on either would
    otherwise load clean and raise from ``staleness.kind_for`` when a figure it marked is aged
    -- a crash at report time for a file that could have been refused by name at load.
    """
    root = tmp_path / "data"
    (root / resolver.CALENDARS_DIR).mkdir(parents=True)
    marker = "SYNTHETIC FIXTURE -- an invented reading of an invented law."
    other = "SYNTHETIC FIXTURE -- an invented rest pattern."
    target = marker if table == "calendar.coverage" else other
    mutated = WHOLE.replace(
        f'kind         = "tax_rule"\nsource       = "{target}"',
        f'kind         = "no_such_kind"\nsource       = "{target}"',
    )
    assert "no_such_kind" in mutated
    (root / resolver.CALENDARS_DIR / "xx_civil.toml").write_text(mutated, encoding="utf-8")
    with pytest.raises(DeclarationError) as raised:
        resolver.working_day_calendars_from_data_root(root, _KINDS)
    assert raised.value.field_path == f"{table}.kind"


def test_an_absent_calendars_directory_is_an_empty_set(tmp_path: Path) -> None:
    """Nothing consumes a calendar, so a data root without one is an ordinary state and a
    consumer that wanted one refuses by name rather than the whole root failing to load."""
    declared = resolver.working_day_calendars_from_data_root(tmp_path / "data", {})
    assert declared.calendars == {}


# ---------------------------------------------------------------------------
# The shipped calendar, which is the only one a run would ever see
# ---------------------------------------------------------------------------


def test_the_shipped_ukrainian_calendar_loads_and_declares_what_its_header_says() -> None:
    """The window, the rest pattern and the empty enumeration, asserted rather than read."""
    calendar = loader.working_day_calendar_from_file(SHIPPED)
    assert calendar.id == "ua_civil"
    assert calendar.jurisdiction == "UA"
    assert calendar.scope is wd.CalendarScope.CIVIL
    assert calendar.covers == (date(2025, 1, 1), date(2026, 10, 30))
    assert calendar.week.rest_days == frozenset({6})
    assert calendar.week.starts_on == 0
    assert calendar.rows == ()


def test_every_citation_on_the_shipped_calendar_is_unverified_and_says_so() -> None:
    """No value here has been checked against a primary source by the owner, and the mark is
    what says so on every answer it produces."""
    calendar = loader.working_day_calendar_from_file(SHIPPED)
    for provenance in (calendar.covered_by, calendar.week.provenance):
        assert prov.is_unverified(provenance)
        assert all(ref.citation.strip() for ref in provenance.sources)


def test_the_shipped_calendar_classifies_a_martial_law_new_year_as_working() -> None:
    """The consequence of the empty enumeration, asserted so the file's header cannot drift
    from what it declares: ст. 73 КЗпП is not applied, so 1 January is not a holiday here."""
    calendar = loader.working_day_calendar_from_file(SHIPPED)
    calendars = {calendar.id: calendar}
    answer = wd.classify(
        calendars, calendar.id, scope=wd.CalendarScope.CIVIL, on_date=date(2026, 1, 1)
    )
    assert isinstance(answer, wd.WorkingDay)
    assert answer.decided_by is wd.DecidedBy.REST_PATTERN


def test_the_shipped_calendar_refuses_the_day_after_its_window() -> None:
    """FR-010: the staleness is loud. 2026-10-31 is the day the cited martial-law extension
    runs out on, and the calendar stops rather than extending its pattern into it."""
    calendar = loader.working_day_calendar_from_file(SHIPPED)
    refused = wd.classify(
        {calendar.id: calendar},
        calendar.id,
        scope=wd.CalendarScope.CIVIL,
        on_date=date(2026, 10, 31),
    )
    assert isinstance(refused, wd.CalendarOutOfCoverage)
    assert refused.missed is wd.Missed.AFTER_WINDOW
    assert refused.covers == (date(2025, 1, 1), date(2026, 10, 30))
