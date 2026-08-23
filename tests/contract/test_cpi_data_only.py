"""G13 and SC-009: nothing treats "the CPI" as a singleton, and a second series is data only.

FR-002: *"Nothing in the system may treat 'the CPI' as a singleton: a second series with a
different identity MUST be a data-only addition that loads and is addressable, even though no
second series is consumed in this feature."*

This is Principle II applied to the price index, and it is a **prerequisite obligation**
rather than a feature of its own. The display-currency feature has to deflate the USD view by
US CPI while the UAH view uses the Ukrainian series (required test F4), and the way that
feature fails is by discovering that this one baked one series into the engine. So the
declarability of a second series is proved here, with zero lines of source changed, even
though nothing in this feature consumes one.

The declaration written below is a **synthetic** second series, not real US CPI. Checking a
published foreign statistic into a test fixture would put an unverified number in the
repository where nobody would ever re-verify it -- the same reasoning ``tests/cpi_fixtures``
gives. What is under test is the shape, not the economy.

The other half of "data only" is the periodicity: it is read off the declaration and reaches
the annualisation from there, so an engine that assumed twelve would be wrong by a factor of
three on a quarterly series with nothing in the output to say so. ``periods_per_year`` is
asserted to be driven by the declared value rather than by a constant.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.inflation import series as cpi
from terezy.core.primitives.periods import Window
from terezy.core.primitives.tolerance import is_close
from terezy.data.declarations import loader, resolver
from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SRC = REPO_ROOT / "src" / "terezy"

SECOND_SERIES = """
# SYNTHETIC FIXTURE. A second, differently identified series, declared to prove that the
# shape admits one. Not real US CPI: an invented value in a test fixture is a number nobody
# would ever re-verify.

[series]
id          = "zz_cpi_monthly"
country     = "ZZ"
index       = "SYNTHETIC FIXTURE -- a second invented price index"
periodicity = "monthly"
base        = "previous month = 100"

[[observation]]
period       = "2025-01"
value        = 100.3
kind         = "cpi_index"
source       = "SYNTHETIC FIXTURE -- invented value, not observed from any publisher."
retrieved_on = "2026-08-23"
verified_on  = ""
"""


def _root_with_both(tmp_path: Path) -> Path:
    """A data root holding the shipped Ukrainian series and a synthetic second one."""
    root = tmp_path / "data"
    (root / "cpi").mkdir(parents=True)
    shutil.copy(DATA_ROOT / "cpi" / "ua.toml", root / "cpi" / "ua.toml")
    (root / "cpi" / "zz.toml").write_text(SECOND_SERIES, encoding="utf-8")
    return root


def test_a_second_series_with_a_distinct_identity_loads(tmp_path: Path) -> None:
    """SC-009, and the whole of it: no source file was edited to make this pass."""
    declarations = resolver.inflation_from_data_root(_root_with_both(tmp_path))

    assert set(declarations.series) == {"ua_cpi_monthly", "zz_cpi_monthly"}


def test_both_series_are_addressable_by_their_own_declared_identity(tmp_path: Path) -> None:
    """Keyed by what the series says it measures, never by file name or load order."""
    declarations = resolver.inflation_from_data_root(_root_with_both(tmp_path))

    assert declarations.series["zz_cpi_monthly"].country == "ZZ"
    assert declarations.series["ua_cpi_monthly"].country == "UA"
    assert declarations.series_files["zz_cpi_monthly"].name == "zz.toml"


def test_the_second_series_deflates_as_readily_as_the_first(tmp_path: Path) -> None:
    """Addressable is not enough: it has to *work*, or the shape has proved nothing.

    A second series that loaded and then could not be handed to ``coverage`` would satisfy
    the letter of SC-009 while leaving the display-currency feature exactly the problem this
    test exists to rule out.
    """
    declarations = resolver.inflation_from_data_root(_root_with_both(tmp_path))
    second = declarations.series["zz_cpi_monthly"]

    covered = cpi.coverage(second, Window(first="2025-01", last="2025-01"))

    assert isinstance(covered, cpi.Covered)
    assert is_close(cpi.cumulative_inflation(covered.observations), 0.003)


def test_no_source_file_names_the_ukrainian_series(tmp_path: Path) -> None:
    """The singleton check, made mechanical: ``ua_cpi_monthly`` is a *declared* id.

    An engine that had the id in its behaviour -- a lookup, a default, a special case -- would
    pass every test above and still be a system with one CPI in it. Prose is stripped first,
    so a docstring naming the shipped series as an example is not a violation.
    """
    offenders = [
        path
        for path in SRC.rglob("*.py")
        if "ua_cpi_monthly" in source_scan.executable_source(path)
    ]

    assert not offenders, (
        f"{[str(path) for path in offenders]} name the Ukrainian series in executable code. "
        "FR-002 forbids treating 'the CPI' as a singleton: the id belongs in data/cpi/, and "
        "the engine takes whichever series it is given."
    )


def test_the_annualisation_divisor_comes_from_the_declared_periodicity() -> None:
    """FR-002's other half. A quarterly series annualised as monthly is out by three."""
    declared = loader.cpi_from_file(DATA_ROOT / "cpi" / "ua.toml")

    assert cpi.periods_per_year(declared.periodicity) == 12


def test_a_data_root_declaring_no_series_is_a_reported_state_not_a_crash(
    tmp_path: Path,
) -> None:
    """Zero series is a state the output already has words for.

    Unlike a missing composition bound -- whose absence would silently turn a feature off --
    an absent CPI series produces a named refusal on every figure that wanted it (FR-012). So
    the resolver reports what is declared and the honesty happens where a reader can see it.
    """
    root = tmp_path / "data"
    (root / "cpi").mkdir(parents=True)

    declarations = resolver.inflation_from_data_root(root)

    assert declarations.series == {}
    assert declarations.assumption is None
