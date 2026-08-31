"""Every refusal in ``contracts/fund-declaration.md``, one case per enforced rule.

FR-003 for a fund: *loading MUST fail loudly -- naming the file and the field -- on a
malformed value, an unrecognised field, a missing required field, a duplicate identifier,
a reference to an undeclared tax class, or an internally inconsistent declaration. No
default MUST ever be substituted.*

**Every case is a mutation of a file that is shipped and valid**, following
``test_declaration_loading.py``'s discipline: the broken variants are edits to the text of
``data/instruments/inzhur_reit.toml``, so each test also proves the real file still
contains what the test thinks it does. A battery written against an invented template
keeps passing after the shipped format changes underneath it, which is how a suite like
this rots.

**Two refusals here have no analogue in the bond battery**, and they are the two that
carry the feature's design:

* a ``verification_task`` that carries a **value** is refused, because the whole point of
  that record is that it holds none -- there must be nowhere for a later contributor in a
  hurry to put a plausible number (research.md D8);
* ``is_assumption_driven = false`` is refused, because the core field is ``Literal[True]``
  and a fund with an observed price history is a different declaration entirely
  (research.md D10).
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.instruments.registry import COLLECTIVE_INVESTMENT_FUND
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.tax.interface import TaxableEventKind
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
REIT = DATA_ROOT / "instruments" / "inzhur_reit.toml"
FUND_C = DATA_ROOT / "instruments" / "synthetic_fund_c.toml"
BOND = DATA_ROOT / "instruments" / "ovdp_synthetic_a.toml"


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped fixture no longer declares {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    lines = text.splitlines(keepends=True)
    matching = [line for line in lines if needle in line and not _is_comment(line)]
    assert len(matching) == 1, f"expected exactly one line declaring {needle!r}"
    return "".join(line for line in lines if line not in matching)


def _written(tmp_path: Path, name: str, text: str) -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


def _refused(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        loader.fund_from_file(path)
    return raised.value


def _assert_names(raised: DeclarationError, *, file: Path, field_path: str) -> None:
    """Both halves of FR-016 together, because half of it is worthless."""
    assert raised.file == file
    assert raised.field_path == field_path, f"expected {field_path!r}, got {raised.field_path!r}"
    rendered = str(raised)
    assert file.name in rendered
    assert field_path in rendered
    assert raised.problem


class TestTheShippedFundsLoad:
    """Before any broken variant: the real files load and say what the spec says they do."""

    def test_the_reit_declares_two_different_tax_classes(self) -> None:
        """FR-006 and contract G1: the two values differ, which is the whole feature."""
        declared = loader.fund_from_file(REIT)
        assert declared.tax_classes == {
            TaxableEventKind.DISTRIBUTION: "ua_ci_fund_distribution",
            TaxableEventKind.DISPOSAL_GAIN: "ua_investment_profit",
        }
        assert len(set(declared.tax_classes.values())) == 2

    def test_the_reit_is_assumption_driven_and_says_so_in_the_type(self) -> None:
        assert loader.fund_from_file(REIT).is_assumption_driven is True

    def test_percent_became_a_fraction_exactly_once(self) -> None:
        """9.5% is ``0.095``, and 1% is ``0.01``. Twice and not at all are both invisible."""
        declared = loader.fund_from_file(REIT)
        assert declared.declared_yield.low == 0.095
        assert declared.declared_yield.high == 0.095
        assert declared.spread.entry_markup_max == 0.01
        assert declared.spread.live_exit_discount == 0.0

    def test_every_term_is_unverified_and_that_is_the_expected_state(self) -> None:
        """FR-002: researched is not verified, and the mark is what says so."""
        declared = loader.fund_from_file(REIT)
        assert prov.is_unverified(declared.nav_per_unit.provenance)
        assert prov.is_unverified(declared.declared_yield.provenance)
        assert prov.is_unverified(declared.spread.provenance)
        assert prov.is_unverified(declared.liquidity.practice.provenance)

    def test_the_verification_tasks_are_recorded_and_carry_no_value(self) -> None:
        """research.md D8, asserted on the record's own shape rather than on its contents."""
        declared = loader.fund_from_file(REIT)
        assert len(declared.verification_tasks) == 5
        for task in declared.verification_tasks:
            assert task.question
            assert task.searched
            assert not hasattr(task, "value")
            assert not hasattr(task, "amount")

    def test_the_fee_facts_are_context_and_carry_no_number(self) -> None:
        """Owner decision B: nothing accrues from these, and there is nowhere for it to."""
        for fee in loader.fund_from_file(REIT).fee_context:
            assert fee.what
            assert not hasattr(fee, "rate")
            assert not hasattr(fee, "amount")

    def test_the_peg_is_declared_with_its_dated_ceiling_ladder(self) -> None:
        declared = loader.fund_from_file(REIT)
        assert declared.distribution is not None
        peg = declared.distribution.peg
        assert peg is not None
        assert peg.sized_in is Currency.USD
        assert [entry.effective_from for entry in peg.cap] == [
            date(2023, 1, 1),
            date(2024, 1, 1),
        ]

    def test_the_third_fund_loads_through_the_same_function_with_no_branch_on_id(self) -> None:
        """SC-010's precondition: a fund is data, and the loader has never heard of this one."""
        declared = loader.fund_from_file(FUND_C)
        assert declared.id == "synthetic_fund_c"
        assert declared.subscription_cutoff == date(2028, 6, 30)
        assert declared.minimum_units == 4.0


class TestTheClassKeyChoosesTheLoader:
    """One directory, two kinds of declaration, told apart by the one key they share."""

    def test_a_fund_file_is_recognised_by_its_declared_class(self) -> None:
        assert loader.declared_class_of(REIT) == COLLECTIVE_INVESTMENT_FUND

    def test_a_bond_file_is_not(self) -> None:
        assert loader.declared_class_of(BOND) == "fixed_income"

    def test_a_file_with_no_class_is_refused_rather_than_guessed(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "unlabelled.toml",
            _drop_line(REIT.read_text(encoding="utf-8"), "class                ="),
        )
        with pytest.raises(DeclarationError) as raised:
            loader.declared_class_of(broken)
        _assert_names(raised.value, file=broken, field_path="instrument.class")

    def test_a_file_with_no_instrument_table_is_refused(self, tmp_path: Path) -> None:
        broken = _written(tmp_path, "empty.toml", "# nothing here\n")
        with pytest.raises(DeclarationError) as raised:
            loader.declared_class_of(broken)
        _assert_names(raised.value, file=broken, field_path="instrument")

    def test_an_unknown_kind_is_refused_by_the_resolver_naming_what_exists(
        self, tmp_path: Path
    ) -> None:
        """The dispatch is a mapping over a declared vocabulary, so it can say what is known.

        A branch naming one class could only say "this is not a fund". This says which
        kinds exist, which is the difference between an error and a remedy.
        """
        (tmp_path / "instruments").mkdir()
        (tmp_path / "tax").mkdir()
        shutil.copy2(DATA_ROOT / "groups.toml", tmp_path / "groups.toml")
        (tmp_path / "tax" / "ua.toml").write_text(
            (DATA_ROOT / "tax" / "ua.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (tmp_path / "instruments" / "odd.toml").write_text(
            _replace(
                REIT.read_text(encoding="utf-8"),
                'class                = "collective_investment_fund"',
                'class                = "structured_note"',
            ),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.from_data_root(tmp_path)
        assert raised.value.field_path == "instrument.class"
        assert "structured_note" in str(raised.value)
        assert COLLECTIVE_INVESTMENT_FUND in str(raised.value)
        assert "fixed_income" in str(raised.value)

    def test_a_fund_declaring_a_class_the_fund_loader_does_not_implement_is_refused(
        self, tmp_path: Path
    ) -> None:
        broken = _written(
            tmp_path,
            "wrong_class.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                'class                = "collective_investment_fund"',
                'class                = "hedge_fund"',
            ),
        )
        _assert_names(_refused(broken), file=broken, field_path="instrument.class")


class TestTheRefusalsTheContractNames:
    """One test per row of contracts/fund-declaration.md's *Refusals at load* table."""

    def test_a_term_with_a_value_and_no_citation_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "uncited.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                '  source       = "https://www.inzhur.reit/offer/inzhur-reit — the net asset',
                '  source       = ""  # ',
            ),
        )
        _assert_names(_refused(broken), file=broken, field_path="instrument.nav.source")

    def test_an_extra_key_is_refused_rather_than_ignored(self, tmp_path: Path) -> None:
        """A misspelled field sitting unread beside the real one is a term that does nothing."""
        broken = _written(
            tmp_path,
            "extra.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "day_count            =",
                'day_countt           = "act/365"\n  day_count            =',
            ),
        )
        raised = _refused(broken)
        assert raised.file == broken
        assert "day_countt" in str(raised)

    def test_a_verification_task_carrying_a_value_is_refused(self, tmp_path: Path) -> None:
        """The record's whole purpose is that it holds none (research.md D8).

        ``extra="forbid"`` is what enforces it, and this is the test that says the
        enforcement is deliberate rather than incidental: somebody adding ``value = 41.24``
        to a task -- the single most tempting edit in this file -- gets a load error rather
        than a number nobody sourced.
        """
        broken = _written(
            tmp_path,
            "valued_task.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                '  searched_on = "2026-08-22"',
                '  searched_on = "2026-08-22"\n  value       = 41.24',
            ),
        )
        raised = _refused(broken)
        assert raised.file == broken
        assert "value" in str(raised)

    def test_is_assumption_driven_false_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "observed.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "is_assumption_driven = true",
                "is_assumption_driven = false",
            ),
        )
        _assert_names(_refused(broken), file=broken, field_path="instrument.is_assumption_driven")

    def test_a_missing_termination_date_is_refused(self, tmp_path: Path) -> None:
        """A fund with no end has no guaranteed exit, which is what FR-019 needs to name."""
        broken = _written(
            tmp_path,
            "endless.toml",
            _drop_line(REIT.read_text(encoding="utf-8"), "terminates_on        ="),
        )
        raised = _refused(broken)
        assert raised.file == broken
        assert "terminates_on" in str(raised)

    def test_a_termination_before_the_subscription_cutoff_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "backwards.toml",
            _replace(
                FUND_C.read_text(encoding="utf-8"),
                'terminates_on        = "2031-12-31"',
                'terminates_on        = "2027-12-31"',
            ),
        )
        _assert_names(_refused(broken), file=broken, field_path="instrument.terminates_on")

    def test_a_markup_above_one_hundred_percent_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "absurd_markup.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "entry_markup_max_pct   = 1.0",
                "entry_markup_max_pct   = 140.0",
            ),
        )
        _assert_names(
            _refused(broken), file=broken, field_path="instrument.spread.entry_markup_max_pct"
        )

    def test_a_live_setting_above_the_declared_maximum_is_refused(self, tmp_path: Path) -> None:
        """The two disagree and the engine cannot say which is wrong, so neither wins."""
        broken = _written(
            tmp_path,
            "over_max.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "live_entry_markup_pct  = 1.0",
                "live_entry_markup_pct  = 3.0",
            ),
        )
        _assert_names(
            _refused(broken),
            file=broken,
            field_path="instrument.spread.live_entry_markup_pct",
        )

    def test_a_negative_settlement_delay_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "negative_delay.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "settlement_business_days   = 15",
                "settlement_business_days   = -1",
            ),
        )
        _assert_names(
            _refused(broken),
            file=broken,
            field_path="instrument.liquidity.legal.settlement_business_days",
        )

    def test_a_practice_declared_irrevocable_is_refused(self, tmp_path: Path) -> None:
        """An unrevocable practice is an obligation, and obligations live in the legal terms."""
        broken = _written(
            tmp_path,
            "irrevocable.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "is_revocable             = true",
                "is_revocable             = false",
            ),
        )
        _assert_names(
            _refused(broken),
            file=broken,
            field_path="instrument.liquidity.practice.is_revocable",
        )

    def test_a_yield_range_written_backwards_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "backwards_range.toml",
            _replace(
                FUND_C.read_text(encoding="utf-8"), "low_pct      = 8.0", "low_pct      = 12.0"
            ),
        )
        _assert_names(
            _refused(broken), file=broken, field_path="instrument.declared_yield.high_pct"
        )

    def test_an_unrecognised_declared_yield_basis_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "odd_basis.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                'basis    = "usd_equivalent_annual"',
                'basis    = "monthly_compounded"',
            ),
        )
        _assert_names(_refused(broken), file=broken, field_path="instrument.declared_yield.basis")

    def test_a_payment_day_no_month_has_is_refused(self, tmp_path: Path) -> None:
        """The 31st would pay in seven months of the year and silently skip the rest."""
        broken = _written(
            tmp_path,
            "impossible_day.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "payment_day      = 10",
                "payment_day      = 31",
            ),
        )
        _assert_names(
            _refused(broken), file=broken, field_path="instrument.distribution.payment_day"
        )

    def test_a_cap_ceiling_of_zero_is_refused(self, tmp_path: Path) -> None:
        """Zero would size every pegged payment at nothing, which is not "no ceiling"."""
        broken = _written(
            tmp_path,
            "zero_cap.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                "uah_per_unit   = 37.49",
                "uah_per_unit   = 0.0",
            ),
        )
        _assert_names(
            _refused(broken),
            file=broken,
            field_path="instrument.distribution.peg.cap[0].uah_per_unit",
        )

    def test_an_out_of_order_cap_ladder_is_refused_rather_than_sorted(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "unsorted_cap.toml",
            _replace(
                REIT.read_text(encoding="utf-8"),
                'effective_from = "2024-01-01"',
                'effective_from = "2022-01-01"',
            ),
        )
        _assert_names(
            _refused(broken),
            file=broken,
            field_path="instrument.distribution.peg.cap[1].effective_from",
        )

    def test_a_minimum_of_zero_units_is_refused(self, tmp_path: Path) -> None:
        broken = _written(
            tmp_path,
            "no_minimum.toml",
            _replace(
                REIT.read_text(encoding="utf-8"), "minimum_units = 1.0", "minimum_units = 0.0"
            ),
        )
        _assert_names(
            _refused(broken), file=broken, field_path="instrument.constraints.minimum_units"
        )


class TestReferencesResolveAcrossFiles:
    """What a single file cannot know: whether the classes it names exist and apply."""

    def _resolved(self, tmp_path: Path, fund_text: str, *, name: str = "fund.toml") -> None:
        (tmp_path / "instruments").mkdir(exist_ok=True)
        (tmp_path / "tax").mkdir(exist_ok=True)
        shutil.copy2(DATA_ROOT / "groups.toml", tmp_path / "groups.toml")
        (tmp_path / "instruments" / name).write_text(fund_text, encoding="utf-8")
        (tmp_path / "tax" / "ua.toml").write_text(
            (DATA_ROOT / "tax" / "ua.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        resolver.from_data_root(tmp_path)

    def test_a_fund_naming_an_undeclared_class_is_refused(self, tmp_path: Path) -> None:
        text = _replace(
            REIT.read_text(encoding="utf-8"),
            'distribution  = "ua_ci_fund_distribution"',
            'distribution  = "class_nobody_declared"',
        )
        with pytest.raises(DeclarationError) as raised:
            self._resolved(tmp_path, text)
        assert raised.value.field_path == "instrument.tax_classes.distribution"
        assert "class_nobody_declared" in str(raised.value)

    def test_a_class_pointed_at_the_wrong_kind_of_income_is_refused(self, tmp_path: Path) -> None:
        """The easiest mistake to make in a fund declaration, caught at the file.

        Swapping the two references is one keystroke and produces a declaration that would
        otherwise fail mid-projection, against an event rather than against the line that
        declared it.
        """
        text = _replace(
            REIT.read_text(encoding="utf-8"),
            'distribution  = "ua_ci_fund_distribution"',
            'distribution  = "ua_investment_profit"',
        )
        with pytest.raises(DeclarationError) as raised:
            self._resolved(tmp_path, text)
        assert raised.value.field_path == "instrument.tax_classes.distribution"
        assert "disposal_gain" in str(raised.value)

    @pytest.mark.parametrize("fund_first", [True, False])
    def test_a_fund_and_a_bond_sharing_an_id_is_a_duplicate(
        self, tmp_path: Path, *, fund_first: bool
    ) -> None:
        """The id space is shared even though the maps are not: a holding names one id.

        ⚙ **Parametrised over the load order, because the check is written twice.** The
        resolver dispatches per file, so the fund branch and the bond branch each carry
        their own duplicate test, and a single ordering exercises only one of them —
        files are loaded sorted, so the name decides which. One order left the fund
        branch's refusal with no coverage at all, which is a refusal whose message could
        have been false without anyone noticing.
        """
        (tmp_path / "instruments").mkdir()
        (tmp_path / "tax").mkdir()
        shutil.copy2(DATA_ROOT / "groups.toml", tmp_path / "groups.toml")
        (tmp_path / "tax" / "ua.toml").write_text(
            (DATA_ROOT / "tax" / "ua.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        fund_name, bond_name = (
            ("a_fund.toml", "b_bond.toml")
            if fund_first
            else (
                "b_fund.toml",
                "a_bond.toml",
            )
        )
        (tmp_path / "instruments" / fund_name).write_text(
            _replace(
                REIT.read_text(encoding="utf-8"),
                'id                   = "inzhur_reit"',
                'id                   = "ovdp_synthetic_a"',
            ),
            encoding="utf-8",
        )
        (tmp_path / "instruments" / bond_name).write_text(
            (DATA_ROOT / "instruments" / "ovdp_synthetic_a.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.from_data_root(tmp_path)
        assert "ovdp_synthetic_a" in str(raised.value)
        assert "already declared" in str(raised.value)
        # The error names the file loaded *second*, which is the one the reader must edit.
        assert raised.value.file.name == (bond_name if fund_first else fund_name)
