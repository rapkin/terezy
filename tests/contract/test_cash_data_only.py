"""023 SC-004: a second balance, at another venue, with zero source lines changed.

Constitution Principle II's executable claim for the third declaration kind. The shipped
balance is bought and spent where the hryvnia salary already arrives, so **both** its legs are
identity — which makes it the one instance that could pass while the class itself did nothing
generic. The balance written here is bought at `inzhur` and its proceeds land there, so it is
reached by `inzhur_direct` and left by `inzhur_to_monobank` like any bond: an ordinary routed
candidate whose only unusual term is that it pays nothing.

It is written into a scratch directory the repository has never seen, on
``tests/contract/test_fund_data_only.py``'s discipline, and it enumerates, evaluates and ranks
against the shipped registry with no engine edit.

**The "zero lines of source" half is asserted, not assumed.** A scan over the shipped tree
proves no module mentions a balance by id, with comments and docstrings stripped first: a
branch on ``id == "cash_uah_monobank"`` would be the moment the framework became one person's
script. The *class* string is not scanned, because it is a dispatch key and
``core.instruments.registry`` is where it is supposed to appear.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path
from typing import Final

import pytest

from terezy.core.decision.candidates import enumerate_candidates, evaluated, survey
from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments.cash import CashAssumptions
from terezy.core.primitives.currency import Currency
from terezy.core.results.candidates import CandidateSet, CandidateSurvey, Question
from terezy.core.results.tuple import Comparison
from terezy.core.routes.path import entry_segments_of, exit_segments_of
from terezy.data.declarations import resolver
from tests import candidate_registries as fixtures
from tests import data_roots

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SOURCE_ROOT: Final = REPO_ROOT / "src" / "terezy"

SHIPPED: Final = "cash_uah_monobank"
SECOND: Final = "cash_uah_inzhur"
"""The second balance: hryvnia again, at the venue the ОВДП are bought at.

Chosen so **neither** leg is an identity: `inzhur` is not where the salary arrives and is not
a declared spendable endpoint, so the way in is `inzhur_direct` and the way out is
`inzhur_to_monobank`. A twin at `monobank_uah` would prove only that the short-circuit fires
twice.
"""

ACCESS_ROW: Final = f'''
[[access]]
instrument_id = "{SECOND}"
bought_at     = "inzhur"
proceeds_to   = "inzhur"
risk_class    = "a_second_balance_fixture"
'''


def _scratch(tmp_path: Path) -> Path:
    """The shipped root plus one declaration and one access row, and nothing else."""
    root = tmp_path / "data"
    shutil.copytree(data_roots.SHIPPED, root)
    declaration = (
        (root / "instruments" / f"{SHIPPED}.toml")
        .read_text(encoding="utf-8")
        .replace(f'id            = "{SHIPPED}"', f'id            = "{SECOND}"')
        .replace(
            'name          = "Monobank hryvnia balance (0 %)"',
            'name          = "A second hryvnia balance (TEST FIXTURE)"',
        )
        .replace("is_synthetic  = false", "is_synthetic  = true")
    )
    (root / "instruments" / f"{SECOND}.toml").write_text(declaration, encoding="utf-8")
    with (root / "access" / "instruments.toml").open("a", encoding="utf-8") as handle:
        handle.write(ACCESS_ROW)
    return root


def _registries(root: Path) -> Registries:
    return resolver.tuple_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=None
    ).registries


def _asked(root: Path) -> tuple[Registries, Question]:
    declared = _registries(root)
    return declared, fixtures.question(declared, plans=fixtures.one_plan_each(declared))


def test_the_second_balance_loads_with_nothing_registered_and_nothing_edited(
    tmp_path: Path,
) -> None:
    """The declaration reaches the resolver's third mapping, which is what enumeration reads."""
    declared = _registries(_scratch(tmp_path))
    assert set(declared.cash) == {SHIPPED, SECOND}
    assert declared.cash[SECOND].rate == 0.0
    assert declared.access[SECOND].bought_at == "inzhur"


def test_it_is_reached_by_declared_corridors_rather_than_by_the_identity_entry(
    tmp_path: Path,
) -> None:
    """The claim the fixture was chosen for: the class works with no identity anywhere.

    Both terms name a declaration under ``routes/``, so nothing about this candidate rests on
    the short-circuit the shipped balance takes.
    """
    declared, question = _asked(_scratch(tmp_path))
    enumerated = enumerate_candidates(
        registries=declared,
        routes=declared.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
    )
    assert isinstance(enumerated, CandidateSet), enumerated
    keys = [item.key for item in enumerated.candidates if item.key.instrument_id == SECOND]
    assert len(keys) == 1
    assert entry_segments_of(keys[0].route_in) == ("inzhur_direct",)
    assert exit_segments_of(keys[0].route_out) == ("inzhur_to_monobank",)  # type: ignore[arg-type]
    assert isinstance(keys[0].exit_terms, CashAssumptions)


def test_it_evaluates_and_is_ranked_beside_everything_else(tmp_path: Path) -> None:
    """SC-004's whole claim: enumerated, evaluated and ranked, with no engine edit."""
    declared, question = _asked(_scratch(tmp_path))
    result = survey(
        registries=declared,
        routes=declared.routes,
        question=question,
        ceiling=fixtures.ceiling(10_000),
        benchmark=fixtures.benchmark_key(
            declared, SHIPPED, question_=question, ceiling_=fixtures.ceiling(10_000)
        ),
    )
    assert isinstance(result, CandidateSurvey), result
    scored = {item.key.instrument_id for item in evaluated(result.comparison)}
    assert {SHIPPED, SECOND} <= scored
    assert isinstance(result.comparison, Comparison)
    assert SECOND in {item.key.instrument_id for item in result.comparison.ranked}


def _is_prose(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _executable_source(path: Path) -> str:
    """Source with comments and docstrings removed, so the scan sees only behaviour."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and any(isinstance(item, ast.stmt) for item in block):
                kept = [item for item in block if not _is_prose(item)]
                setattr(node, field, kept or [ast.Pass()])
    return ast.unparse(tree)


def test_no_shipped_module_mentions_a_balance_id_in_its_code() -> None:
    """Principle II's line: behaviour comes from declared terms, never from an id."""
    offenders = [
        str(path.relative_to(SOURCE_ROOT))
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if SHIPPED in _executable_source(path)
    ]
    assert not offenders, (
        f"these modules branch on or mention {SHIPPED!r} in code rather than in prose: "
        f"{offenders}. A balance's behaviour must come from its declared terms."
    )


def test_the_scan_reaches_the_modules_that_could_hold_such_a_branch() -> None:
    """A scan of nothing passes forever. This names what it walked."""
    walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in SOURCE_ROOT.rglob("*.py")}
    assert {
        "core/instruments/cash.py",
        "core/results/cash.py",
        "core/decision/tuple_outcome.py",
        "core/decision/candidates.py",
        "data/declarations/loader.py",
        "data/declarations/resolver.py",
    } <= walked
