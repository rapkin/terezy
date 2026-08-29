"""SC-014: no source-code site derives what a declaration is supposed to declare.

FR-008 and FR-021. A kind that is never inferred leaves **no behaviour to observe** -- there
is no wrong answer to catch, because the code that would produce one does not run -- so the
absence of the code is the only available evidence, and a scan is the only way to produce
it.

Five derivations, each a one-line temptation in a loader:

1. reading the **last** payment as a repayment of principal;
2. reading the **largest** payment as one;
3. dividing a declared amount by 100 to turn kopecks into hryvnia;
4. computing a **coupon rate** from an amount and an interval;
5. inferring a **coverage window** from where a published list happens to begin.

⚙ **The fourth is here for a second reason** (FR-003c). A coupon rate derived from a day
count, one coupon amount and the spacing between two coupons yields an extrapolated issue
date in one more step -- the invented legal fact this declaration form exists to refuse.
FR-003b forbids it at the field; this forbids it at the site. Two locks, because a guard
that believes itself sufficient is the one nobody adds a second lock to, and FR-003b's first
draft claimed to close the door while drawing its line one category short of it.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

import pytest

from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

DIVIDES_BY_A_HUNDRED = re.compile(r"/\s*(?:100(?:\.0*)?|_PERCENT)\b")
"""Turning one unit into another by the factor a minor unit uses.

``_PERCENT`` as well as the literal, because `loader._as_fraction` spells it that way.
"""

DIVIDING_BY_A_HUNDRED_FOR_A_REASON: Final[Mapping[str, str]] = {
    "data/declarations/loader.py": (
        "`_as_fraction`, the one place a declared **percentage** becomes a fraction. A "
        "percentage is a rate written in per-cent; a payment amount is money, and a "
        "division of one by 100 is the unit conversion FR-004 forbids the engine to perform"
    ),
    "core/inflation/series.py": (
        "a CPI observation published against the previous month = 100, turned into a growth "
        "factor. Index points are not minor units of anything, and the series says so in its "
        "own module docstring (007)"
    ),
}
"""Every site permitted to write that division, **by name and with its reason**.

An allowlist alone is fail-open: the place a future unit conversion is most likely to land
is a file nobody thought to list. Naming the reason is what makes adding a third entry a
decision rather than a shrug -- and what caught, while this scan was being written, a claim
in `loader.py` that it was the only such site in the project, which feature 007 had made
false.
"""

LAST_OR_LARGEST = re.compile(
    r"payments?\s*\[\s*-\s*1\s*\]|"
    r"max\s*\([^\n]*\.amount|"
    r"key\s*=\s*[^\n]*\.amount"
)
"""Reading a payment's meaning off its position or its size.

``8305, 8305, 8305, 100000`` is obviously three coupons and a repayment of principal to a
human and obviously nothing at all to a machine, and each of these spellings is a machine
pretending to be the human. Taking the largest *date* is not one of them: when the last
payment falls is a fact, what it **is** is a declaration.
"""


def _assignments(path: Path, named: str) -> list[ast.Assign]:
    """Every assignment in a module whose target is called ``named``.

    An AST walk rather than a regex, because the two spellings a regex cannot tell apart
    are exactly the two that matter: ``coupon_rate = <something>`` computes a rate, and
    ``coupon_rate=<something>`` passes a declared one to a constructor.
    """
    tree = ast.parse(source_scan.executable_source(path))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            (isinstance(target, ast.Name) and target.id == named)
            or (isinstance(target, ast.Attribute) and target.attr == named)
            for target in node.targets
        )
    ]


def _computed(node: ast.Assign) -> bool:
    """Whether the value assigned is arithmetic rather than a read of a declared field."""
    return any(isinstance(inner, ast.BinOp) for inner in ast.walk(node.value))


def _derivations(named: str) -> dict[str, str]:
    return {
        path.relative_to(SOURCE_ROOT).as_posix(): ast.unparse(node)
        for path in _python_files()
        for node in _assignments(path, named)
        if _computed(node)
    }


def _python_files() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("*.py"))


def _offenders(pattern: re.Pattern[str], *, allowed: Iterable[str] = ()) -> dict[str, str]:
    permitted = set(allowed)
    found: dict[str, str] = {}
    for path in _python_files():
        name = path.relative_to(SOURCE_ROOT).as_posix()
        if name in permitted:
            continue
        match = pattern.search(source_scan.executable_source(path))
        if match:
            found[name] = match.group(0)
    return found


def test_no_module_reads_the_last_or_the_largest_payment_as_principal() -> None:
    found = _offenders(LAST_OR_LARGEST)
    assert not found, (
        "a module decides what a payment *is* from where it sits in the list or from how "
        "big it is (FR-008). The kind is declared, and a schedule that declares none fails "
        f"at load: {found}"
    )


def test_only_the_two_named_sites_divide_by_a_hundred() -> None:
    found = _offenders(DIVIDES_BY_A_HUNDRED, allowed=DIVIDING_BY_A_HUNDRED_FOR_A_REASON)
    assert not found, (
        "a module converts a declared figure out of minor units (FR-004). The conversion "
        "happens at transcription and is recorded there as an inference; if this site has "
        "a reason, add it to DIVIDING_BY_A_HUNDRED_FOR_A_REASON with the reason rather "
        f"than widening the pattern: {found}"
    )


def test_every_permitted_division_still_exists() -> None:
    """The other direction, so the allowlist cannot outlive what it excuses. An entry for a
    site that no longer divides is an exemption nobody would notice had gone stale."""
    for name in DIVIDING_BY_A_HUNDRED_FOR_A_REASON:
        source = source_scan.executable_source(SOURCE_ROOT / name)
        assert DIVIDES_BY_A_HUNDRED.search(source), name


def test_no_module_derives_a_coupon_rate() -> None:
    found = _derivations("coupon_rate")
    assert not found, (
        "a module computes a coupon rate rather than reading a declared one (FR-021, "
        f"FR-003c). A rate plus the spacing yields an extrapolated issue date: {found}"
    )


def test_no_module_infers_a_coverage_window() -> None:
    found = _derivations("covers_from")
    assert not found, (
        "a module decides where a schedule's coverage begins rather than reading the "
        f"declared claim (FR-021). The claim is the transcriber's and it is cited: {found}"
    )


def test_the_scan_reaches_every_module_that_could_hold_such_a_line() -> None:
    """A scan of nothing passes forever. The loader and the schedule generator are where
    each of these would actually be written."""
    walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in _python_files()}
    assert {
        "data/declarations/loader.py",
        "core/instruments/enumerated.py",
        "core/instruments/fixed_income.py",
        "core/instruments/terms.py",
    } <= walked


@pytest.mark.parametrize(
    ("pattern", "planted"),
    [
        (LAST_OR_LARGEST, "principal = terms.payments[-1]\n"),
        (LAST_OR_LARGEST, "principal = max(payments, key=lambda p: p.amount.amount)\n"),
        (LAST_OR_LARGEST, "biggest = max(p.amount.amount for p in terms.payments)\n"),
        (DIVIDES_BY_A_HUNDRED, "amount = table.amount / 100.0\n"),
        (DIVIDES_BY_A_HUNDRED, "amount = table.amount / 100\n"),
    ],
)
def test_the_scan_would_catch_the_line_it_forbids(pattern: re.Pattern[str], planted: str) -> None:
    assert pattern.search(planted), planted


@pytest.mark.parametrize(
    ("pattern", "innocent"),
    [
        (LAST_OR_LARGEST, "last = max(payment.on for payment in terms.payments)\n"),
        (DIVIDES_BY_A_HUNDRED, "share = spent.amount / price.amount\n"),
    ],
)
def test_the_scan_permits_the_lines_that_only_look_alike(
    pattern: re.Pattern[str], innocent: str
) -> None:
    """A scan that flags the honest line beside the forbidden one is a scan somebody turns
    off. Reading the last *date* is not reading the last *payment's meaning*, and dividing
    two amounts is not converting a unit."""
    assert not pattern.search(innocent), innocent


@pytest.mark.parametrize(
    ("named", "planted", "innocent"),
    [
        (
            "coupon_rate",
            "coupon_rate = coupon.amount / (face.amount * year_fraction)",
            "coupon_rate=_as_fraction(table.coupon_rate_pct)",
        ),
        (
            "covers_from",
            "covers_from = min(payment.on for payment in payments) - one_period",
            "covers_from=covers_from",
        ),
    ],
)
def test_the_derivation_walk_tells_a_computation_from_a_declared_read(
    tmp_path: Path, named: str, planted: str, innocent: str
) -> None:
    """The distinction a regex cannot make, and the reason these two are an AST walk:
    ``x = a / b`` derives a value and ``x=a`` passes a declared one to a constructor, and
    both contain the same characters."""
    guilty = tmp_path / "guilty.py"
    guilty.write_text(planted + "\n", encoding="utf-8")
    assert [node for node in _assignments(guilty, named) if _computed(node)]

    honest = tmp_path / "honest.py"
    honest.write_text(f"Record({innocent})\n", encoding="utf-8")
    assert not _assignments(honest, named)


def test_the_prose_is_stripped_before_the_scan_reads_it() -> None:
    """Half this repository's docstrings name the very thing a scan forbids -- this file's
    own module docstring lists all five. `tests/source_scan` parses and drops them, so the
    scan reads what runs."""
    module = ast.parse(
        source_scan.executable_source(SOURCE_ROOT / "core" / "instruments" / "enumerated.py")
    )
    assert ast.get_docstring(module) is None
