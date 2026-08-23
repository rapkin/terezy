"""SC-007: every misdeclared assessment rule fails at load, naming the file and the field.

A battery rather than a handful of cases, because SC-007 is a claim about *every* way these
two files can be wrong, and a sampled version would go stale the first time somebody added a
field. Each case writes one file, loads it, and checks the message names the file and the
specific thing that is wrong -- an error saying "invalid timing file" sends a reader to read
a hundred lines by hand.

The battery covers what the success criterion lists -- a missing method, an unknown method, a
missing filing decision, a missing due-date rule, a malformed carryforward declaration -- plus
the two refusals that need a second file to see: a class mapped to a category nobody declared,
and a class that no rate pack declares.

The last tests load the **shipped** files, because a battery of broken ones proves nothing
about the files the project actually uses.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from terezy.core.ledger import engine
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import tax_year as settlement
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError
from tests import tax_years

pytestmark = pytest.mark.contract

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATA_ROOT: Final = REPO_ROOT / "data"
SHIPPED_TIMING: Final = DATA_ROOT / "tax" / "timing" / "ua.toml"
SHIPPED_POSITIONS: Final = DATA_ROOT / "scenarios" / "tax" / "owner-001.toml"

UAH: Final = Currency.UAH
SOURCE: Final = prov.of([tax_years.FIXTURE_SOURCE])

CATEGORY: Final = """
[[timing.category]]
id                    = "investment_profit"
treatment             = "{treatment}"
carryforward          = "{carryforward}"
settlement            = "self_assessed"
declare_by_month      = {declare_by_month}
declare_by_day        = 1
pay_by_month          = 8
pay_by_day            = {pay_by_day}
non_business_day_rule = "{convention}"
note                  = "SYNTHETIC FIXTURE category."
kind                  = "tax_rule"
source                = "SYNTHETIC FIXTURE -- not an observation of anything."
retrieved_on          = "2026-08-23"
verified_on           = ""
"""

METHOD: Final = """
[[timing.lot_method]]
method            = "{method}"
verdict           = "{verdict}"
what_the_law_says = "SYNTHETIC FIXTURE finding."
kind              = "tax_rule"
source            = "SYNTHETIC FIXTURE -- not an observation of anything."
retrieved_on      = "2026-08-23"
verified_on       = ""
"""

CLASS: Final = """
[[timing.class]]
tax_class = "{tax_class}"
category  = "{category}"
note      = "SYNTHETIC FIXTURE mapping."
"""

POSITIONS: Final = """
[tax_positions]
owner_id     = "owner-1"
is_synthetic = true

[[tax_positions.filing]]
year  = 2026
filed = true
note  = "SYNTHETIC FIXTURE."

[tax_positions.carryforward_chain]
position        = "{chain}"
question        = "SYNTHETIC FIXTURE question."
rationale       = "SYNTHETIC FIXTURE rationale."
resolution_path = "an individual tax consultation (art. 52 PKU)"
is_assumption   = {chain_is_assumption}

[tax_positions.self_declarant_method]
method          = "{method}"
question        = "SYNTHETIC FIXTURE question."
rationale       = "SYNTHETIC FIXTURE rationale."
resolution_path = "an individual tax consultation (art. 52 PKU)"
is_assumption   = true
"""


def _timing_body(
    *,
    treatment: str = "nets",
    carryforward: str = "unlimited",
    convention: str = "none",
    declare_by_month: int = 5,
    pay_by_day: int = 1,
    methods: tuple[str, ...] = ("fifo", "lifo", "average_cost", "specific_lot"),
    classes: tuple[tuple[str, str], ...] = (("ua_investment_profit", "investment_profit"),),
) -> str:
    body = '[timing]\njurisdiction = "ua"\ntax_currency = "UAH"\n'
    body += CATEGORY.format(
        treatment=treatment,
        carryforward=carryforward,
        convention=convention,
        declare_by_month=declare_by_month,
        pay_by_day=pay_by_day,
    )
    for method in methods:
        body += METHOD.format(method=method, verdict="no_source")
    for tax_class, category in classes:
        body += CLASS.format(tax_class=tax_class, category=category)
    return body


def _written(tmp_path: Path, body: str, *, name: str = "xx.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _timing_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.timing_from_file(path)
    return caught.value


def _positions_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.tax_positions_from_file(path)
    return caught.value


class TestTheControlCasesLoad:
    """Without these, every red case below could be failing for a reason nobody chose."""

    def test_a_well_formed_timing_file_loads(self, tmp_path: Path) -> None:
        declared = loader.timing_from_file(_written(tmp_path, _timing_body()))

        assert declared.jurisdiction_id == "ua"
        assert [category.id for category in declared.categories] == ["investment_profit"]
        assert len(declared.methods) == len(LotMethod)

    def test_a_well_formed_positions_file_loads(self, tmp_path: Path) -> None:
        filing, positions = loader.tax_positions_from_file(
            _written(
                tmp_path,
                POSITIONS.format(
                    chain="chain_restorable", chain_is_assumption="true", method="average_cost"
                ),
            )
        )

        assert filing.by_year == {2026: True}
        assert positions.chain is not None
        assert positions.chain.position is tax_year.ChainPosition.RESTORABLE


class TestNothingIsDefaultedInTheAssessmentRules:
    """FR-018 and FR-020: an absent or unrecognised value fails naming what would have worked."""

    def test_an_unknown_netting_treatment_lists_the_three_that_exist(self, tmp_path: Path) -> None:
        error = _timing_error(_written(tmp_path, _timing_body(treatment="aggregate")))

        assert "xx.toml" in str(error)
        assert "treatment" in str(error)
        assert "nets" in str(error)
        assert "outside" in str(error)

    def test_an_unknown_carryforward_rule_is_refused(self, tmp_path: Path) -> None:
        error = _timing_error(_written(tmp_path, _timing_body(carryforward="three_years")))

        assert "carryforward" in str(error)
        assert "unlimited" in str(error)

    def test_an_unknown_non_business_day_convention_is_refused(self, tmp_path: Path) -> None:
        """FR-008: the convention is declared, and an unrecognised one fails at load."""
        error = _timing_error(_written(tmp_path, _timing_body(convention="rolls_to_month_end")))

        assert "non_business_day_rule" in str(error)
        assert "following" in str(error)

    def test_a_deadline_that_does_not_exist_in_every_year_is_refused(self, tmp_path: Path) -> None:
        """A 30 February deadline is not a deadline, and moving it would invent a rule."""
        error = _timing_error(_written(tmp_path, _timing_body(pay_by_day=31)))

        assert "pay_by_day" in str(error)
        assert "28" in str(error)

    def test_a_month_outside_the_year_is_refused(self, tmp_path: Path) -> None:
        error = _timing_error(_written(tmp_path, _timing_body(declare_by_month=13)))

        assert "declare_by_month" in str(error)

    def test_an_unknown_basis_method_lists_the_four_that_exist(self, tmp_path: Path) -> None:
        body = _timing_body(methods=("fifo", "weighted_average"))
        error = _timing_error(_written(tmp_path, body))

        assert "weighted_average" in str(error)
        assert "specific_lot" in str(error)

    def test_a_method_declared_twice_is_refused_rather_than_collapsed(self, tmp_path: Path) -> None:
        error = _timing_error(_written(tmp_path, _timing_body(methods=("fifo", "fifo"))))

        assert "fifo" in str(error)

    def test_a_class_mapped_to_an_undeclared_category_is_refused(self, tmp_path: Path) -> None:
        body = _timing_body(classes=(("ua_investment_profit", "capital_gains"),))
        error = _timing_error(_written(tmp_path, body))

        assert "capital_gains" in str(error)
        assert "investment_profit" in str(error)

    def test_a_class_mapped_twice_is_refused(self, tmp_path: Path) -> None:
        body = _timing_body(
            classes=(
                ("ua_investment_profit", "investment_profit"),
                ("ua_investment_profit", "investment_profit"),
            )
        )
        error = _timing_error(_written(tmp_path, body))

        assert "ua_investment_profit" in str(error)

    def test_an_unrecognised_field_is_refused(self, tmp_path: Path) -> None:
        """A misspelled key sitting unread beside the real one declares nothing."""
        body = _timing_body().replace(
            'non_business_day_rule = "none"',
            'non_business_day_rule = "none"\nweekend_convention    = "following"',
        )
        error = _timing_error(_written(tmp_path, body, name="extra.toml"))

        assert "extra.toml" in str(error)
        assert "weekend_convention" in str(error)

    def test_a_missing_required_field_is_refused_and_nothing_is_defaulted(
        self, tmp_path: Path
    ) -> None:
        """Every key of the category table, removed one at a time.

        Looped rather than spot-checked, because "no default is substituted" is a claim about
        every field and a test naming two of them would let the next one arrive with a default.
        """
        for dropped in (
            "treatment",
            "carryforward",
            "settlement",
            "declare_by_month",
            "pay_by_day",
            "non_business_day_rule",
            "note",
            "kind",
            "source",
            "retrieved_on",
            "verified_on",
        ):
            body = "\n".join(
                line for line in _timing_body().splitlines() if not line.startswith(f"{dropped} ")
            )
            error = _timing_error(_written(tmp_path, body, name=f"missing_{dropped}.toml"))

            assert dropped in str(error), dropped

    def test_a_file_declaring_no_category_is_refused(self, tmp_path: Path) -> None:
        """Both spellings of "none": the key omitted, and the key present but empty.

        The second is the one a person actually writes -- ``category = []`` looks like a
        deliberate blank -- and it passes shape validation, so the loader has to refuse it.
        """
        head = '[timing]\njurisdiction = "ua"\ntax_currency = "UAH"\n'
        omitted = head + METHOD.format(method="fifo", verdict="no_source")
        empty = (
            head + "category = []\nclass = []\n" + METHOD.format(method="fifo", verdict="no_source")
        )

        for body, name in ((omitted, "omitted.toml"), (empty, "empty.toml")):
            error = _timing_error(_written(tmp_path, body, name=name))
            assert "category" in str(error), name


class TestTheOwnersOwnPositionsAreNotDefaultedEither:
    """FR-014 and FR-015: a missing decision and a mislabelled belief both fail."""

    def test_an_unknown_chain_position_lists_the_two_branches(self, tmp_path: Path) -> None:
        error = _positions_error(
            _written(
                tmp_path,
                POSITIONS.format(
                    chain="chain_survives_everything",
                    chain_is_assumption="true",
                    method="average_cost",
                ),
            )
        )

        assert "chain_broken_forfeits" in str(error)
        assert "chain_restorable" in str(error)

    def test_a_position_declared_as_anything_but_an_assumption_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A belief that renders as a finding is the failure the label exists to prevent."""
        error = _positions_error(
            _written(
                tmp_path,
                POSITIONS.format(
                    chain="chain_restorable", chain_is_assumption="false", method="average_cost"
                ),
            )
        )

        assert "is_assumption" in str(error)

    def test_a_year_declared_twice_is_refused(self, tmp_path: Path) -> None:
        body = POSITIONS.format(
            chain="chain_restorable", chain_is_assumption="true", method="average_cost"
        )
        body += '\n[[tax_positions.filing]]\nyear = 2026\nfiled = false\nnote = "x"\n'
        error = _positions_error(_written(tmp_path, body))

        assert "2026" in str(error)

    def test_a_missing_filing_decision_is_a_refusal_at_assessment_not_a_load_failure(
        self,
    ) -> None:
        """FR-014: the failure names the *year*, which a load error naming a file could not.

        A file declaring no decision for 2027 is well formed -- the owner may simply not have
        reached that year. What must not happen is a run assessing 2027 anyway.
        """
        outcome = _assess(filing=tax_years.filing(y2099=True))

        assert isinstance(outcome, tax_year.FilingStatusUndeclared), outcome
        assert outcome.tax_year == 2027
        assert "2027" in outcome.reason


class TestADueDateRuleIsRequiredAndIsData:
    """FR-005 and US5 scenario 1: no default date, and changing the declared one moves the money."""

    def test_a_category_with_taxable_events_and_no_timing_rule_refuses(self) -> None:
        outcome = _assess(rules=tax_years.rules(timing={}))

        assert isinstance(outcome, tax_year.TimingRuleUndeclared), outcome
        assert outcome.category_id == tax_years.INVESTMENT
        assert "due" in outcome.reason

    def test_changing_the_declared_deadline_moves_the_payment_and_nothing_else(self) -> None:
        """The data-only claim, executed: one field, two runs, two dates, one liability."""
        august = _settled(pay_by=(8, 1))
        december = _settled(pay_by=(12, 15))

        assert august.payments[0].due_on == date(2028, 8, 1)
        assert december.payments[0].due_on == date(2028, 12, 15)
        assert august.payments[0].amount == december.payments[0].amount


class TestAForeignCurrencyTaxableEventRefuses:
    """The boundary: the official rate is feature 011, and a channel rate may not stand in."""

    def test_it_names_the_missing_machinery_rather_than_converting(self) -> None:
        outcome = _assess(currency=Currency.USD)

        assert isinstance(outcome, tax_year.TaxCurrencyConversionUnavailable), outcome
        assert outcome.found is Currency.USD
        assert outcome.tax_currency is Currency.UAH
        assert "official" in outcome.reason
        assert "channel rate" in outcome.reason


class TestTheCrossFileRelationsAreCheckedToo:
    """Four refusals a per-file validator structurally cannot make."""

    def test_a_class_no_rate_pack_declares_is_refused(self, tmp_path: Path) -> None:
        """A category for a class that does not exist governs nothing, and looks satisfied."""
        root = _scratch_root(tmp_path)
        (root / "tax" / "timing" / "ua.toml").write_text(
            _timing_body(classes=(("ua_capital_gains", "investment_profit"),)), encoding="utf-8"
        )

        with pytest.raises(DeclarationError, match="ua_capital_gains"):
            resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

    def test_two_files_declaring_one_jurisdiction_are_refused_by_name(self, tmp_path: Path) -> None:
        root = _scratch_root(tmp_path)
        (root / "tax" / "timing" / "second.toml").write_text(_timing_body(), encoding="utf-8")

        with pytest.raises(DeclarationError, match="already declares"):
            resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

    def test_a_data_root_with_no_assessment_rules_is_refused(self, tmp_path: Path) -> None:
        """Unlike an absent CPI series: there is no figure to come back unavailable."""
        root = _scratch_root(tmp_path)
        for path in (root / "tax" / "timing").glob("*.toml"):
            path.unlink()

        with pytest.raises(DeclarationError, match="no assessment rules"):
            resolver.tax_rules_from_data_root(root, resolver.from_data_root(root))

    def test_two_sets_of_owner_positions_are_refused(self, tmp_path: Path) -> None:
        """Two positions on an unsettled question are two runs, each naming what it assumed."""
        root = _scratch_root(tmp_path)
        (root / "scenarios" / "tax" / "second.toml").write_text(
            POSITIONS.format(chain="chain_restorable", chain_is_assumption="true", method="fifo"),
            encoding="utf-8",
        )

        with pytest.raises(DeclarationError, match="one run rests on one set"):
            resolver.tax_positions_from_data_root(root)

    def test_a_data_root_with_no_declared_positions_reports_none(self, tmp_path: Path) -> None:
        """A run that never reaches a taxable year needs none; the refusals that do name it."""
        root = _scratch_root(tmp_path)
        for path in (root / "scenarios" / "tax").glob("*.toml"):
            path.unlink()

        assert resolver.tax_positions_from_data_root(root) is None


def _scratch_root(tmp_path: Path) -> Path:
    """A copy of the shipped data root, so a case changes exactly one thing about it."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


class TestTheShippedFilesLoad:
    """A battery of broken files proves nothing about the files the project uses."""

    def test_the_shipped_assessment_rules_resolve_against_the_shipped_rate_packs(self) -> None:
        declarations = resolver.from_data_root(DATA_ROOT)
        rules = resolver.tax_rules_from_data_root(DATA_ROOT, declarations)

        assert sorted(rules) == ["ua"]
        assert set(rules["ua"].methods) == set(LotMethod)
        for class_id in rules["ua"].category_of_class:
            assert class_id in declarations.tax_classes

    def test_every_shipped_category_has_a_timing_rule(self) -> None:
        rules = resolver.tax_rules_from_data_root(DATA_ROOT, resolver.from_data_root(DATA_ROOT))

        assert set(rules["ua"].categories) == set(rules["ua"].timing)

    def test_every_shipped_legal_value_is_unverified_and_therefore_marks_what_it_touches(
        self,
    ) -> None:
        """FR-027: nothing here has been checked, and everything derived from it says so."""
        rules = resolver.tax_rules_from_data_root(DATA_ROOT, resolver.from_data_root(DATA_ROOT))

        for category in rules["ua"].categories.values():
            assert prov.is_unverified(category.provenance)
        for standing in rules["ua"].methods.values():
            assert prov.is_unverified(standing.provenance)

    def test_the_shipped_positions_are_labelled_assumptions_with_a_resolution_path(self) -> None:
        found = resolver.tax_positions_from_data_root(DATA_ROOT)

        assert found is not None
        _, positions, path = found
        assert path == SHIPPED_POSITIONS
        assert positions.chain is not None
        assert positions.method is not None
        assert "art. 52 PKU" in positions.chain.switch.resolution_path
        assert "art. 52 PKU" in positions.method.switch.resolution_path


# --- one small ledger, reused by the assessment-level cases above ----------------------


def _events(currency: Currency = Currency.UAH) -> tuple[Event, ...]:
    term = CausationRef(kind=CausationKind.INSTRUMENT_TERM, id="fixture:term", detail="fixture")
    return (
        Event(
            sequence=1,
            occurred_on=date(2027, 1, 5),
            kind=EventKind.PURCHASE,
            amount=Money(-1_000.00, currency, SOURCE),
            owner_id="owner-1",
            caused_by=term,
            lot_ref=LotRef(instrument_id="fixture", lot_id="lot-a"),
            quantity=10.0,
            allocated_to=None,
            capacity_pool=None,
        ),
        Event(
            sequence=2,
            occurred_on=date(2027, 6, 5),
            kind=EventKind.PRINCIPAL_REPAYMENT,
            amount=Money(1_600.00, currency, SOURCE),
            owner_id="owner-1",
            caused_by=term,
            lot_ref=LotRef(instrument_id="fixture", lot_id=None),
            quantity=10.0,
            allocated_to=None,
            capacity_pool=None,
        ),
    )


def _charged(state: engine.LedgerState, events: tuple[Event, ...]) -> TaxCharge:
    charge = flat_rate.charge(
        events[1],
        tax_years.TAXED_CLASS,
        TaxContext(
            instrument_id="fixture",
            taxable_event=TaxableEventKind.DISPOSAL_GAIN,
            taxable_base=state.disposals[0].realised_gain_base_ccy,
            charged_for_year=2027,
        ),
    )
    assert isinstance(charge, TaxCharge), charge
    return charge


def _assess(
    *,
    rules: tax_year.AssessmentRules | None = None,
    filing: tax_year.FilingDecisions | None = None,
    currency: Currency = Currency.UAH,
) -> tuple[tax_year.AnnualStatement, ...] | tax_year.TaxYearRefused:
    events = _events(currency)
    state = engine.fold(events, base_currency=currency, consumption_method=LotMethod.FIFO.value)
    return tax_year.statements(
        state,
        (_charged(state, events),),
        rules=rules if rules is not None else tax_years.rules(),
        tax_classes=tax_years.TAX_PACK,
        filing=filing if filing is not None else tax_years.filing(y2027=True),
        method=LotMethod.FIFO,
        switches=tax_years.positions(),
    )


def _settled(*, pay_by: tuple[int, int]) -> settlement.Settlement:
    events = _events()
    state = engine.fold(events, base_currency=UAH, consumption_method=LotMethod.FIFO.value)
    statements = tax_year.statements(
        state,
        (_charged(state, events),),
        rules=tax_years.rules(
            timing={
                tax_years.INVESTMENT: tax_years.timing(tax_years.INVESTMENT, pay_by=pay_by),
                tax_years.DISTRIBUTION: tax_years.timing(tax_years.DISTRIBUTION),
                tax_years.EXEMPT: tax_years.timing(tax_years.EXEMPT),
            }
        ),
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2027=True),
        method=LotMethod.FIFO,
        switches=tax_years.positions(),
    )
    assert isinstance(statements, tuple), statements
    outcome = settlement.settle(
        events,
        statements,
        owner_id="owner-1",
        base_currency=UAH,
        method=LotMethod.FIFO,
        horizon_end=date(2029, 1, 1),
    )
    assert isinstance(outcome, settlement.Settlement), outcome
    return outcome
