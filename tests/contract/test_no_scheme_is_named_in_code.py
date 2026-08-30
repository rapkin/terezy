"""SC-002 and SC-012: nothing in the engine knows a scheme, a component or a destination.

*No component name appears in source code as a branch, and no engine branch exists for "the
levy".* Principle II applied to the tax regime: which scheme applies is a **declaration**, so
adding one — a different ФОП group, a legal entity, another jurisdiction's — must be a file.

**What is scanned, and why it is not the whole of the claim.** mypy enforces nothing here:
``if component.id == "viyskovyi_zbir"`` is perfectly well typed. So this module reads every
module under ``src/terezy`` with comments and docstrings stripped, and fails on any that
mentions a declared identifier at all in executable code. A prose mention is not a branch and
is not caught; a branch is.

**A scan that matches nothing passes for ever**, so two things are asserted beside it: that
the walk reached the modules that could actually hold such a branch, and that the scan sees a
planted branch and does not see planted prose.

⚙ **The declared date names are deliberately NOT in this scan, and the reason is worth
stating rather than leaving as an omission.** A reading recognises income on a date whose
*name* is declared, and the shipped names are ordinary English words — ``credited``,
``repatriated`` — which appear in refusal messages all over the tree as words. A word scan
over them reports prose-shaped code and says nothing about branching. What proves the engine
does not know them is a **rename**: the same rows under different date names produce the same
figures, asserted in ``test_scheme_data_only.py`` against a scratch data root. That is the
stronger claim anyway, and it is the one a reader should look for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.tax.scheme import PeriodicComponent, RateComponent, TaxationScheme, Verdict
from terezy.data.declarations import resolver
from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

MUST_BE_WALKED = (
    "core/tax/scheme.py",
    "core/streams/capacity.py",
    "core/streams/streams.py",
    "data/declarations/loader.py",
    "data/declarations/resolver.py",
    "data/declarations/schema.py",
)
"""Where a branch on a declared name would most plausibly be written. A scan whose walk
missed the module holding the branch is a scan that passes while the rule is broken."""


def _declared() -> resolver.SchemeDeclarations:
    return resolver.schemes_from_data_root(DATA_ROOT, base_currency=Currency.UAH)


def _identifiers() -> frozenset[str]:
    """Every id and name the shipped declarations carry, read off the data rather than typed.

    Read off the files so the scan widens on its own when a scheme, a component or a
    destination is added -- a hand-written list stops covering the tree the moment somebody
    declares something, and it stops silently.
    """
    declared = _declared()
    names: set[str] = set(declared.schemes)
    for scheme in declared.schemes.values():
        names.add(scheme.variant)
        for component in _components(scheme):
            names.update({component.id, component.name})
            names.update(item.id for item in component.context)
    for (scheme_id, venue_id), row in declared.destinations.items():
        names.update({scheme_id, venue_id})
        names.update(reading.id for reading in row.readings)
    return frozenset(names)


def _components(scheme: TaxationScheme) -> list[RateComponent | PeriodicComponent]:
    """Both kinds in one list, typed as their union so a shared field can be read."""
    components: list[RateComponent | PeriodicComponent] = list(scheme.rate_components)
    components.extend(scheme.periodic_components)
    return components


def _mentions(identifier: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(identifier)}\b")
    return [
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if pattern.search(source_scan.executable_source(path))
    ]


class TestNothingInTheEngineKnowsWhatItIsCharging:
    def test_no_module_mentions_a_declared_identifier_in_executable_code(self) -> None:
        offenders = {
            identifier: _mentions(identifier)
            for identifier in sorted(_identifiers())
            if _mentions(identifier)
        }
        assert not offenders, (
            "these identifiers appear in code rather than in prose: "
            f"{offenders}. A scheme, a component, a crediting destination and a date name "
            "are declared data; a branch on one makes the next scheme a source change."
        )

    def test_the_scan_is_looking_at_something(self) -> None:
        """A scan over an empty identifier set is a green build that checks nothing."""
        identifiers = _identifiers()
        assert len(identifiers) >= 20
        assert "ua_fop_group_3_non_vat" in identifiers
        assert "військовий збір" in identifiers
        assert "payoneer" in identifiers
        assert "termination_on_the_end_of_martial_law" in identifiers

    def test_the_walk_reaches_the_modules_that_could_hold_such_a_branch(self) -> None:
        walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in SOURCE_ROOT.rglob("*.py")}
        for expected in MUST_BE_WALKED:
            assert expected in walked, expected

    def test_the_scan_would_catch_a_branch_and_would_not_catch_prose(self) -> None:
        branch = 'if component.id == "viyskovyi_zbir":\n    pass\n'
        prose = '"""The військовий збір is charged from 2025-01-01."""\n# viyskovyi_zbir\nx = 1\n'
        assert "viyskovyi_zbir" in source_scan.strip_prose(branch)
        assert "viyskovyi_zbir" not in source_scan.strip_prose(prose)
        assert "військовий збір" not in source_scan.strip_prose(prose)


class TestTheEngineBranchesOnDeclaredWordsAndNothingElse:
    """The other half: what the engine *may* dispatch on is a closed set the core defines."""

    def test_the_verdict_vocabulary_is_the_cores_own_closed_set(self) -> None:
        assert {member.value for member in Verdict} == {"interpreted", "unsettled"}
        for row in _declared().destinations.values():
            assert row.verdict in Verdict

    def test_no_scheme_is_reached_by_anything_but_its_declared_id(self) -> None:
        """The registry is a mapping keyed by what the file declares, never by file order."""
        declared = _declared()
        for identifier, scheme in declared.schemes.items():
            assert scheme.id == identifier
        assert set(declared.scheme_files) == set(declared.schemes)
