"""The core knows no ISIN, and no script writes a declaration.

016 FR-019 and FR-023, and the paragraph in `data/README.md` that said the first of these was
*"reviewed rather than enforced"*. Reviewing it was defensible while every instrument was a
fixture. Declaring 24 real securities is what makes it worth a check: a branch on an ISIN is
the exact shape Principle II forbids, and it is now a shape somebody could reach for.

**Two scans, and each carries a control.** A scan that can never fail protects nothing, so
every one below is paired with a probe proving it catches the thing it forbids.

Prose is stripped first (`tests/source_scan.py`): half the docstrings in this repository name
the very thing being looked for, and a sentence explaining a rule is not a violation of it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

from tests import observations as obs
from tests.source_scan import executable_source, strip_prose

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CORE_ROOT: Final = REPO_ROOT / "src" / "terezy" / "core"
SCRIPTS_ROOT: Final = REPO_ROOT / "scripts"

ISIN: Final = re.compile(r"\bUA\d{10}\b|\bXS\d{10}\b")
"""An ISIN as the two sources spell one. Deliberately a shape rather than the 24 declared ids:
a branch on an issue this repository has never declared is the same defect."""

SELLER_FIELDS: Final = (
    "return_rate_buy_pct",
    "return_rate_sell_pct",
    "stated_yield",
    "available_quantity",
    "matures_on",
)
"""What the seller publishes that no figure may rest on (FR-017, FR-017a). `status` is absent
from this tuple on purpose -- it is an ordinary English word and `core/` uses it for route
status, so scanning for it would report the wrong lines. What actually keeps it out is that no
declaration carries it, which `test_no_declaration_carries_a_sellers_field` asserts."""

REGISTER_FIELDS: Final = ("auk_proc", "razm_date", "pay_period", "pgs_date", "cpcode")
"""What the register publishes that the enumerated form forbids a declaration to carry
(FR-007) and that no module may read: a coupon rate and a placement date together are exactly
the condition under which somebody reconstructs a schedule the issuer already published."""

DECLARATION_DIRS: Final = ("data/instruments", "data/access")
"""What FR-019 forbids a script to write into. A fetcher may retrieve and may write an
observation; turning one into a declaration is the human act the reasoning lives in."""


def _written_paths(source: str) -> list[str]:
    """Every filesystem path a module builds from literals, as a POSIX string.

    A script can only write to a path it constructs, and every one here is constructed the
    same way: a module-level constant, either ``Path("a/b")`` or ``ROOT / "a" / "b"``. A path
    assembled some other way would report nothing, so the control below builds one both ways.
    """
    found: list[str] = []

    def parts(node: ast.expr) -> list[str] | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.Call) and _named(node.func) in {"Path", "pathlib.Path"}:
            inner = [parts(arg) for arg in node.args]
            return [bit for group in inner if group is not None for bit in group] or None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = parts(node.left), parts(node.right)
            if right is None:
                return None
            return (left or []) + right
        return None

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            built = parts(node.value)
            if built:
                found.append("/".join(built))
    return found


def _named(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_named(node.value)}.{node.attr}"
    return ""


def _core_modules() -> list[Path]:
    return sorted(CORE_ROOT.rglob("*.py"))


def _script_modules() -> list[Path]:
    return sorted(SCRIPTS_ROOT.glob("*.py"))


def test_the_scan_reaches_the_modules_that_could_hold_such_a_branch() -> None:
    """A scan over an empty walk is a green build that checked nothing."""
    names = {path.name for path in _core_modules()}
    assert {"enumerated.py", "fixed_income.py", "tuple_outcome.py", "candidates.py"} <= names


def test_no_core_module_names_an_isin() -> None:
    found = {
        str(path.relative_to(CORE_ROOT)): ISIN.findall(executable_source(path))
        for path in _core_modules()
        if ISIN.search(executable_source(path))
    }
    assert not found, (
        "a module under core/ names a security, so that security's behaviour is code rather "
        f"than data (Principle II): {found}"
    )


def test_no_core_module_reads_a_sellers_figure_or_a_register_term() -> None:
    found = {
        str(path.relative_to(CORE_ROOT)): [
            field
            for field in (*SELLER_FIELDS, *REGISTER_FIELDS)
            if field in executable_source(path)
        ]
        for path in _core_modules()
    }
    assert not {name: fields for name, fields in found.items() if fields}


def test_the_scans_would_catch_what_they_forbid() -> None:
    """The controls, and the second half proves prose is not mistaken for behaviour."""
    behaviour = strip_prose(
        "def f(d: object) -> bool:\n"
        '    """A docstring."""\n'
        '    return d.id == "UA4000239016" and d.auk_proc > 0\n'
    )
    assert ISIN.search(behaviour)
    assert "auk_proc" in behaviour
    prose = strip_prose(
        '"""A module docstring about UA4000239016 and auk_proc."""\n'
        "X: int = 1\n"
        '"""An attribute docstring about UA4000239016."""\n'
        "# A comment about auk_proc.\n"
    )
    assert not ISIN.search(prose)
    assert "auk_proc" not in prose


def test_no_script_builds_a_path_under_a_declaration_directory() -> None:
    """FR-019, which is `scripts/fetch_inzhur.py`'s own stated refusal and was held by nothing.

    Over the paths a script BUILDS rather than the directories it mentions: every script here
    names `data/instruments/` in prose or in a citation, and saying where a declaration lives
    is not writing one.
    """
    offenders = {
        str(path.relative_to(REPO_ROOT)): built
        for path in _script_modules()
        for built in _written_paths(executable_source(path))
        if built.startswith(DECLARATION_DIRS)
    }
    assert not offenders, f"a script builds a path under a declaration directory: {offenders}"


def test_every_path_a_fetcher_builds_is_one_a_fetcher_may_write() -> None:
    """The positive half: the four fetchers write observations, the price index and the
    official-rate series, and nothing else under `data/`."""
    permitted = ("data/observations/", "data/cpi/", "data/official_rates/")
    seen = 0
    for path in sorted(SCRIPTS_ROOT.glob("fetch_*.py")):
        for built in _written_paths(executable_source(path)):
            if not built.startswith("data/"):
                continue
            seen += 1
            assert built.startswith(permitted), (path.name, built)
    assert seen == len(list(SCRIPTS_ROOT.glob("fetch_*.py"))), (
        "one output per fetcher; a fetcher whose path this scan could not read would "
        "otherwise pass by being invisible"
    )


def test_the_path_scan_sees_both_ways_a_path_is_built_here() -> None:
    """The control. A scan that reported nothing for a script that writes declarations would
    be a green build that looked at the wrong thing."""
    both = _written_paths(
        'OUTPUT = pathlib.Path("data/instruments/UA4000239016.toml")\n'
        'OTHER = REPO_ROOT / "data" / "access" / "instruments.toml"\n'
    )
    assert "data/instruments/UA4000239016.toml" in both
    assert any(built.endswith("data/access/instruments.toml") for built in both)


def test_no_declaration_carries_a_sellers_field() -> None:
    """The other half of FR-017a, over the files rather than over the modules: a status and an
    available quantity are not declared anywhere, so nothing can read one.

    The available quantity is the pointed case. It decays in hours and contradicts itself in
    the shipped observation -- 11 of the 24 active issues publish `0` while being offered, and
    a *completed* issue publishes 14 473 -- so taking it as an inventory cap would be a guess
    dressed as a constraint. That no cap is enforced is a recorded gap, not an oversight.
    """
    data = REPO_ROOT / "data"
    files = [*sorted((data / "instruments").glob("*.toml")), data / "access/instruments.toml"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        declaring = [
            line for line in text.splitlines() if not line.lstrip().startswith("#") and "=" in line
        ]
        for field in (*SELLER_FIELDS, "status", "available_quantity"):
            assert not [line for line in declaring if line.split("=")[0].strip() == field], (
                path.name,
                field,
            )


def test_the_shipped_observation_is_why_the_available_quantity_governs_nothing() -> None:
    """Measured rather than asserted, because the argument above rests on the measurement."""
    bonds = obs.seller_bonds()
    active = [bonds[isin] for isin in obs.active_isins()]
    assert sum(1 for bond in active if bond["available_quantity"] == 0) > len(active) // 3
    completed_with_stock = [
        isin
        for isin, bond in bonds.items()
        if bond["status"] == "completed" and bond["available_quantity"] > 0
    ]
    assert completed_with_stock == ["UA4000234215"]
