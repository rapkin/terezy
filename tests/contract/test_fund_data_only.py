"""SC-010: a third fund, different in every term, projected with zero source lines changed.

Constitution Principle II's executable claim, for funds. ``data/instruments/
synthetic_fund_c.toml`` differs from both real funds in **every** axis the spec names — its
liquidity terms, its spread, its peg and its tax schedule — plus a subscription cutoff the
REIT does not have, a payout share below 100% so its NAV moves, and a two-entry dated
schedule of its own in ``data/tax/synthetic_fixture.toml``. It produces a complete result,
and nothing in ``src/`` knows it exists.

**The "zero lines of source" half is asserted, not assumed.** A scan over the shipped
source tree proves no module mentions any fund by id: a branch on ``id ==
"inzhur_reit"`` would make a fund's behaviour code rather than data, and the abstraction
would have stopped being a framework at that line. The scan strips comments and docstrings
first, because prose naming a file is not a violation and half the docstrings in this
project cite one.

**A fourth fund is added here, in a scratch directory**, on top of the third: a shipped
fixture proves the loader accepts a different file, and a file written by this test proves
it accepts one the repository has never seen.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Final

import pytest

import terezy.core.instruments
import terezy.core.results
import terezy.data.declarations
from terezy.core.instruments.fund import ExchangeRateAssumption, FundDeclaration
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.results import fund as fund_results
from terezy.core.results.fund import FundAssumptions, FundProjection
from terezy.core.tax.interface import TaxableEventKind
from terezy.data.declarations import resolver
from tests import data_roots

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATA_ROOT: Final = data_roots.with_fixtures()
SOURCE_ROOT: Final = REPO_ROOT / "src" / "terezy"

REIT: Final = "inzhur_reit"
MILTECH: Final = "inzhur_miltech"
FUND_C: Final = "synthetic_fund_c"

PURCHASED_ON: Final = date(2027, 3, 15)
EXIT_ON: Final = date(2028, 3, 15)
HORIZON_END: Final = date(2028, 12, 31)


def _declarations(root: Path = DATA_ROOT) -> resolver.Declarations:
    return resolver.from_data_root(root)


def _assumptions() -> FundAssumptions:
    return FundAssumptions(
        liquidity_mode="legal",
        buyback="available",
        exit_on=EXIT_ON,
        yield_point=None,
        exchange_rate=None,
        consumption_method="fifo",
    )


def _projected(
    declarations: resolver.Declarations,
    identifier: str,
    *,
    quantity: float = 10.0,
) -> FundProjection:
    declared = declarations.funds[identifier]
    outcome = fund_results.project_fund(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=identifier,
            quantity=quantity,
            purchased_on=PURCHASED_ON,
            cost=Money(
                declared.nav_per_unit.amount * quantity,
                declared.unit_currency,
                prov.EMPTY,
            ),
        ),
        DateRange(start=PURCHASED_ON, end=HORIZON_END),
        _with_exchange_rate(declared, _assumptions()),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, FundProjection), f"expected a projection, got {outcome!r}"
    return outcome


def _with_exchange_rate(declared: FundDeclaration, assumptions: FundAssumptions) -> FundAssumptions:
    """Attach an owner-stated rate where — and only where — the fund's payout is pegged.

    Not a default: a fund without a peg must not be handed an exchange-rate assumption it
    has no use for, and a fund with one must not be projected without a stated rate. The
    two cases are decided from the *declaration*, which is what makes this data-driven
    rather than a per-fund branch.
    """
    terms = declared.distribution
    if terms is None or terms.peg is None:
        return assumptions
    return replace(
        assumptions,
        exchange_rate=ExchangeRateAssumption(
            uah_per_unit=42.0,
            is_assumption=True,
            rationale="TEST — an owner-stated rate, for a scenario that needs one.",
        ),
    )


class TestTheThirdFundIsDifferentInEveryTermTheSpecNames:
    """Before anything is projected: the fixture actually is what SC-010 asks for."""

    def test_its_liquidity_terms_differ_from_both_real_funds(self) -> None:
        funds = _declarations().funds
        settlements = {
            identifier: (
                declared.liquidity.legal.settlement_business_days,
                declared.liquidity.practice.settlement_business_days,
            )
            for identifier, declared in funds.items()
        }
        assert settlements[FUND_C] not in (settlements[REIT], settlements[MILTECH])

    def test_its_spread_differs(self) -> None:
        funds = _declarations().funds
        spreads = {
            identifier: (
                declared.spread.entry_markup_max,
                declared.spread.exit_discount_max,
                declared.spread.live_entry_markup,
                declared.spread.live_exit_discount,
            )
            for identifier, declared in funds.items()
        }
        assert spreads[FUND_C] not in (spreads[REIT], spreads[MILTECH])

    def test_its_peg_ceiling_starts_on_a_different_date(self) -> None:
        funds = _declarations().funds
        reit_terms = funds[REIT].distribution
        fund_c_terms = funds[FUND_C].distribution
        assert reit_terms is not None
        assert fund_c_terms is not None
        assert reit_terms.peg is not None
        assert fund_c_terms.peg is not None
        assert [entry.effective_from for entry in fund_c_terms.peg.cap] != [
            entry.effective_from for entry in reit_terms.peg.cap
        ]

    def test_its_tax_schedule_is_its_own_and_has_two_dated_entries(self) -> None:
        """Which makes it a data-only fund *and* a data-only rate change, in one file."""
        declarations = _declarations()
        classes = set(declarations.funds[FUND_C].tax_classes.values())
        assert classes.isdisjoint(set(declarations.funds[REIT].tax_classes.values()))
        payout = declarations.tax_classes["synthetic_fund_payout"]
        assert len(payout.rates) == 2
        assert [entry.effective_from for entry in payout.rates] == [
            date(2026, 1, 1),
            date(2028, 1, 1),
        ]

    def test_it_retains_part_of_its_yield_so_its_nav_moves(self) -> None:
        terms = _declarations().funds[FUND_C].distribution
        assert terms is not None
        assert terms.payout_share < 1.0


class TestItProducesACompleteResult:
    """Complete: every part a real fund's result has, none of it defaulted or empty."""

    def test_every_part_of_the_result_is_present(self) -> None:
        projection = _projected(_declarations(), FUND_C)
        assert projection.instrument_id == FUND_C
        assert projection.liquidity_mode == "legal"
        assert projection.distributions
        assert projection.exit_line is not None
        assert projection.tax_by_class
        assert projection.peg_statement is not None
        assert projection.rests_on
        assert projection.excludes
        assert projection.ledger.applied

    def test_its_two_declared_classes_both_charge_and_do_not_collide(self) -> None:
        projection = _projected(_declarations(), FUND_C)
        charged = {item.tax_class_id for item in projection.tax_by_class}
        assert charged == {"synthetic_fund_payout", "synthetic_fund_disposal"}
        for subtotal in projection.tax_by_class:
            expected = (
                TaxableEventKind.DISTRIBUTION
                if subtotal.tax_class_id == "synthetic_fund_payout"
                else TaxableEventKind.DISPOSAL_GAIN
            )
            assert subtotal.kinds == (expected,)

    def test_its_payouts_straddle_its_own_schedules_effective_date(self) -> None:
        """The two-entry schedule is not decoration: both entries are actually used.

        A fixture whose second entry never applied would prove the file loads and nothing
        else. The holding runs from March 2027 to March 2028, so payments fall on both
        sides of the 2028-01-01 step.
        """
        applied = {
            line.rate_effective_from for line in _projected(_declarations(), FUND_C).distributions
        }
        assert applied == {date(2026, 1, 1), date(2028, 1, 1)}

    def test_the_figures_carry_the_fixtures_unverified_mark(self) -> None:
        assert prov.is_unverified(_projected(_declarations(), FUND_C).provenance)


class TestAFourthFundNeedsNoSourceChangeEither:
    """A file the repository has never seen, written into a scratch directory."""

    def _scratch(self, tmp_path: Path) -> Path:
        (tmp_path / "instruments").mkdir()
        (tmp_path / "tax").mkdir()
        shutil.copy2(DATA_ROOT / "groups.toml", tmp_path / "groups.toml")
        for name in ("ua.toml", "synthetic_fixture.toml"):
            (tmp_path / "tax" / name).write_text(
                (DATA_ROOT / "tax" / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        text = (
            (DATA_ROOT / "instruments" / f"{FUND_C}.toml")
            .read_text(encoding="utf-8")
            .replace(f'id                   = "{FUND_C}"', 'id                   = "fund_d"')
            .replace('day_count            = "act/365"', 'day_count            = "act/act"')
            .replace("payout_share_pct = 60.0", "payout_share_pct = 25.0")
            .replace("payment_day      = 20", "payment_day      = 7")
            .replace("minimum_units = 4.0", "minimum_units = 1.0")
        )
        (tmp_path / "instruments" / "fund_d.toml").write_text(text, encoding="utf-8")
        return tmp_path

    def test_a_fourth_fund_projects_with_nothing_registered_and_nothing_edited(
        self, tmp_path: Path
    ) -> None:
        declarations = _declarations(self._scratch(tmp_path))
        projection = _projected(declarations, "fund_d")
        assert projection.instrument_id == "fund_d"
        assert projection.distributions
        assert projection.exit_line is not None

    def test_it_differs_from_the_fund_it_was_copied_from(self, tmp_path: Path) -> None:
        """Otherwise the test would be proving that the same file loads twice."""
        declarations = _declarations(self._scratch(tmp_path))
        fourth = _projected(declarations, "fund_d")
        third = _projected(_declarations(), FUND_C, quantity=10.0)
        assert fourth.distributions[0].gross.amount != third.distributions[0].gross.amount
        assert tuple(line.paid_on.day for line in fourth.distributions) != tuple(
            line.paid_on.day for line in third.distributions
        )


class TestNoModuleKnowsAnyFundByName:
    """Principle II's line: behaviour comes from declared terms, never from an id.

    A branch on ``id == "inzhur_reit"`` would be the moment the framework became one
    person's script, and it is the kind of edit that looks harmless in review.
    """

    def _is_prose(self, statement: ast.stmt) -> bool:
        return (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )

    def _executable_source(self, path: Path) -> str:
        """Source with comments and docstrings removed, so the scan sees only behaviour."""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if isinstance(block, list) and any(isinstance(item, ast.stmt) for item in block):
                    kept = [item for item in block if not self._is_prose(item)]
                    setattr(node, field, kept or [ast.Pass()])
        return ast.unparse(tree)

    @pytest.mark.parametrize("identifier", [REIT, MILTECH, FUND_C])
    def test_no_shipped_module_mentions_a_fund_id_in_its_code(self, identifier: str) -> None:
        offenders = [
            str(path.relative_to(SOURCE_ROOT))
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
            if identifier in self._executable_source(path)
        ]
        assert not offenders, (
            f"these modules branch on or mention {identifier!r} in code rather than in "
            f"prose: {offenders}. A fund's behaviour must come from its declared terms."
        )

    def test_the_scan_reaches_the_packages_that_could_hold_such_a_branch(self) -> None:
        """A scan of nothing passes forever. This names what it walked."""
        walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in SOURCE_ROOT.rglob("*.py")}
        for expected in (
            "core/instruments/fund.py",
            "core/results/fund.py",
            "data/declarations/loader.py",
            "data/declarations/resolver.py",
        ):
            assert expected in walked

    def test_every_module_in_the_three_packages_imports_cleanly(self) -> None:
        """So the scan above is over modules that exist rather than over dead files."""
        for package in (
            terezy.core.instruments,
            terezy.core.results,
            terezy.data.declarations,
        ):
            for info in pkgutil.iter_modules(package.__path__):
                module = importlib.import_module(f"{package.__name__}.{info.name}")
                assert module.__name__.startswith(package.__name__)
