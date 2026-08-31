"""The sites that decide a working day without a declared calendar, counted rather than reviewed.

017 FR-018. The engine holds one uncited notion of a working day --
``conventions._is_weekend``, which is ``day.weekday() >= 5`` and knows nothing about holidays
-- and CL-1 decided on 2026-08-30 to leave it and its consumers in place. The cost of that
deferral is two notions of a working day in one tree, and the thing that makes the cost
bounded is that **a fourth site cannot appear quietly**.

## Reaching the notion through the registry counts

``conventions.business_day_rule`` resolves a declared name to a function that loops on
``_is_weekend``. A scan counting only direct callers of ``is_business_day`` would report one
site and pass, while the tree has three: ``tax/year.py::_due_on`` is reached that way and is
already counted, so the narrowing is a distinction with nothing behind it.
:func:`test_the_direct_caller_narrowing_would_miss_two_of_the_three` is the assertion that
keeps this file from being narrowed into a green lie.

## Four limits, measured on this tree rather than supposed

1. **A call is what counts, not a mention.** ``loader.py`` names ``BUSINESS_DAY_FNS`` to
   validate a declared name against it and ``canonical.py`` reads a ``business_day_rule``
   string off a record; neither decides anything about a date, and neither is counted. A
   module that reached the notion by copying ``_is_weekend``'s body would be invisible here.
2. **A holiday spelled as a computed date passes.** The literal scan reads ``date(y, m, d)``
   constructions and month-and-day pairs compared inside **one** boolean expression; a
   Paschalion, a ``timedelta`` from another date, a month-and-day assembled from variables, and
   a pair split across two ``if`` statements are all invisible to it. FR-008 forbids the first
   outright, and that prohibition is not enforceable from a syntax tree. The pairing is scoped
   to one ``BoolOp`` deliberately: a module-wide cross-product would report a holiday nobody
   wrote, which is a worse failure than missing one, because it fails a correct module.
3. **The literal scan finds nothing today, and that is a state rather than a proof.**
   Measured 2026-08-31: zero ``date(y, m, d)`` constructions and zero ``.month`` / ``.day``
   comparisons anywhere in ``src/``.
   :func:`test_the_literal_scan_would_see_a_holiday_written_into_a_module` is what keeps it
   from being a check over an empty set.
4. **The holiday list here is the searched-for thing, not a value the engine holds.** It is
   the fixed dates of ст. 73 КЗпП, retrieved 2026-08-31; the two movable ones (Пасха, Трійця)
   have no month-and-day to search for and are outside the scan by construction.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "terezy"

CALENDAR_SURFACE = "core/calendars/"
"""The calendar's own declaration surface, which FR-018 excludes by name: applying a
*declared* rest pattern is what this feature adds, and it is the opposite of the defect."""

DECLARATION_SITE = "core/primitives/conventions.py"
"""Where the uncited weekend notion is written. One module, and CL-1 left it there."""

FR_017_SITES = frozenset(
    {
        "core/instruments/fixed_income.py",
        "core/instruments/fund.py",
        "core/tax/year.py",
    }
)
"""The three consumers 017 FR-017 names, as the canonical set. A fourth fails this file."""

_DATE_PARTS = 3
"""A ``date`` construction is a year, a month and a day."""

DECIDING_CALLS = frozenset({"is_business_day", "business_day_rule"})
"""The two entry points into ``_is_weekend``. ``business_day_rule`` is the registry path."""

HOLIDAY_MONTH_DAYS = frozenset(
    {(1, 1), (3, 8), (5, 1), (5, 8), (6, 28), (7, 15), (8, 24), (10, 1), (12, 25)}
)
"""The fixed святкові дні of ст. 73 КЗпП, retrieved 2026-08-31 from
``zakon.rada.gov.ua/laws/show/322-08/print``. Searched for, never asserted as law: the
article itself is not applied during martial law, which is what the shipped calendar
declares and cites."""


def _modules() -> list[tuple[str, ast.Module]]:
    """Every module under ``src/terezy``, by its path relative to the package root."""
    return [
        (path.relative_to(SRC).as_posix(), ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(SRC.rglob("*.py"))
    ]


def _calls(tree: ast.AST) -> set[str]:
    """The names of everything called in a tree, whether ``f(...)`` or ``obj.f(...)``."""
    named: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            named.add(node.func.attr)
        elif isinstance(node.func, ast.Name):
            named.add(node.func.id)
    return named


def _deciding_modules(wanted: frozenset[str]) -> set[str]:
    return {
        name
        for name, tree in _modules()
        if not name.startswith(CALENDAR_SURFACE) and _calls(tree) & wanted
    }


def test_exactly_three_modules_decide_a_working_day_without_a_calendar() -> None:
    """FR-018, SC-009: the set is FR-017's three, and a fourth fails here."""
    found = _deciding_modules(DECIDING_CALLS)
    assert found == set(FR_017_SITES), (
        f"the modules reaching the uncited weekend notion are {sorted(found)}, and 017 FR-017 "
        f"names {sorted(FR_017_SITES)}. A NEW one is the thing this scan exists to stop: wire "
        "it to a declared calendar instead, or — if it genuinely must decide a working day "
        "without one — say so in FR-017's set and in the deferral's stated cost. One that "
        "DISAPPEARED means a site was rewired, which is good news and still needs the set "
        "narrowed here and the CL-1 deferral's cost restated."
    )


def test_the_direct_caller_narrowing_would_miss_two_of_the_three() -> None:
    """SC-009: a scan scoped to direct callers passes green while asserting something false.

    ``fixed_income.py`` and ``year.py`` reach ``_is_weekend`` only through the
    declared-convention registry, so counting direct callers of ``is_business_day`` reports
    one site out of three. This is the narrowing FR-018 names, asserted rather than warned
    against.
    """
    direct = _deciding_modules(frozenset({"is_business_day"}))
    through_registry = _deciding_modules(frozenset({"business_day_rule"}))
    assert direct == {"core/instruments/fund.py"}
    assert through_registry == {"core/instruments/fixed_income.py", "core/tax/year.py"}
    assert direct | through_registry == set(FR_017_SITES)


def test_one_module_derives_a_working_day_from_a_weekday_number() -> None:
    """The uncited notion is written in exactly one place, and it is the one CL-1 deferred."""
    deriving = {
        name
        for name, tree in _modules()
        if not name.startswith(CALENDAR_SURFACE) and _calls(tree) & {"weekday", "isoweekday"}
    }
    assert deriving == {DECLARATION_SITE}, (
        f"these modules derive a working day from a weekday number: {sorted(deriving)}. "
        f"Outside {DECLARATION_SITE} and the calendar's own declaration surface, which "
        "weekdays a jurisdiction rests on is declared data with a citation (FR-002), not a "
        "comparison against 5."
    )


def _holiday_literals(tree: ast.AST) -> list[tuple[int, int]]:
    """Month-and-day pairs a module writes down: ``date(y, m, d)``, or ``x.month == m``."""
    found: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "date"
            and len(node.args) == _DATE_PARTS
        ):
            parts = [
                argument.value
                for argument in node.args
                if isinstance(argument, ast.Constant) and isinstance(argument.value, int)
            ]
            if len(parts) == _DATE_PARTS:
                found.append((parts[1], parts[2]))
    for joined in ast.walk(tree):
        if not isinstance(joined, ast.BoolOp):
            continue
        months = _constant_comparisons(joined, "month")
        days = _constant_comparisons(joined, "day")
        found.extend((month, day) for month in months for day in days)
    return [pair for pair in found if pair in HOLIDAY_MONTH_DAYS]


def _constant_comparisons(node: ast.BoolOp, attribute: str) -> set[int]:
    """The integers **one** boolean expression compares ``something.<attribute>`` against.

    Scoped to a single ``BoolOp`` rather than to a whole module, because the pair is what
    names a date: taking the cross-product module-wide synthesises ``(12, 25)`` out of a
    ``d.month == 12`` in one function and an unrelated ``other.day == 25`` in another, and
    fails a module that writes down no holiday at all.
    """
    against: set[int] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Compare):
            continue
        if not (isinstance(inner.left, ast.Attribute) and inner.left.attr == attribute):
            continue
        against.update(
            operand.value
            for operand in inner.comparators
            if isinstance(operand, ast.Constant) and isinstance(operand.value, int)
        )
    return against


def test_no_module_writes_down_a_public_holiday() -> None:
    """FR-018, SC-009: a holiday is declared data with a citation, never a literal in code."""
    strays = {
        name: literals
        for name, tree in _modules()
        if not name.startswith(CALENDAR_SURFACE) and (literals := _holiday_literals(tree))
    }
    assert not strays, (
        f"these modules write down a public holiday's month and day: {strays}. A holiday is a "
        "legal fact and Principle I forbids one originating from an implementer's memory: "
        "declare it as a row in data/calendars/, with its own citation and its own "
        "verification date."
    )


def test_the_literal_scan_would_see_a_holiday_written_into_a_module() -> None:
    """Falsifiability, because the scan above finds nothing on this tree and always has."""
    planted = ast.parse("from datetime import date\nNEW_YEAR = date(2026, 1, 1)\n")
    assert _holiday_literals(planted) == [(1, 1)]
    compared = ast.parse("def f(d):\n    return d.month == 12 and d.day == 25\n")
    assert _holiday_literals(compared) == [(12, 25)]
    ordinary = ast.parse("from datetime import date\nSETTLED = date(2026, 2, 17)\n")
    assert _holiday_literals(ordinary) == []
    apart = ast.parse(
        "def a(d):\n    return d.month == 12\n\n\ndef b(d):\n    return d.day == 25\n"
    )
    assert _holiday_literals(apart) == [], (
        "two unrelated comparisons in two functions are not a date, and reporting one would "
        "fail a module that writes down no holiday"
    )


CHARTER = (
    "**A rule written in working days or public holidays cannot be declared against these\n"
    "records at all**, because evaluating one needs a working-day and holiday calendar and "
    "nothing\ndeclares one."
)
"""The sentence in ``core/tax/official_rate.py`` that this feature exists to answer, and which
``core/calendars/working_day.py`` quotes. A quotation of another module is a claim about
elsewhere, so it is checked."""


def test_the_charter_sentence_the_calendar_answers_is_still_written_where_it_is_quoted() -> None:
    """``core/calendars/working_day.py`` opens by quoting ``core/tax/official_rate.py``.

    If that module ever stops saying it -- because a rule in working days became declarable
    against its records after all -- the quotation becomes a claim about a sentence nobody
    wrote, and the calendar's own stated reason for existing goes with it.
    """
    charter = (SRC / "core" / "tax" / "official_rate.py").read_text(encoding="utf-8")
    assert CHARTER in charter
    quoting = (SRC / "core" / "calendars" / "working_day.py").read_text(encoding="utf-8")
    assert "cannot be declared against these records at all" in quoting


def test_the_three_corrected_sentences_name_a_calendar_that_exists() -> None:
    """FR-017a: each correction says a declared calendar exists and this site consults none.

    Half of that is checked by the scans above -- the sites consult none. The other half is
    that the calendar is real, which is what makes the sentence a correction rather than a
    second false promise.
    """
    assert (SRC / "core" / "calendars" / "working_day.py").is_file()
    assert sorted((REPO_ROOT / "data" / "calendars").glob("*.toml")), (
        "the corrected docstrings say declared calendars exist; data/calendars/ holds none"
    )
    corrected = {
        "core/primitives/conventions.py": (
            "Declared calendars exist -- ``core.calendars.working_day`` over ``data/calendars/``"
        ),
        "core/instruments/fund.py": "Declared calendars\n    exist and this consults none",
    }
    for module, sentence in corrected.items():
        assert sentence in (SRC / module).read_text(encoding="utf-8"), module
