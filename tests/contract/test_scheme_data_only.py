"""Principle II on the tax regime: a second scheme, and a moved verdict, are files.

SC-012, SC-004 and SC-013a. Every case here writes into a **scratch copy of the shipped data
root** and asserts a complete result comes back with **zero source lines changed**. That is
the whole of what makes the abstraction real rather than claimed: the day the owner moves to
another ФОП group or to a legal entity, applying the new scheme must be a declaration.

⚙ The verdict case is the one this feature was told to build for. The crediting-destination
verdicts are the least settled thing in it and are **expected to move**; what makes moving
one cheap is that a verdict is a declared word behind a normative table, and this asserts
that moving one changes the outcome and nothing else.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.tax import scheme as schemes
from terezy.data.declarations import resolver
from tests import official_rates

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
CREDIT_DATE = date(2027, 3, 15)
REPATRIATION_DATE = date(2027, 4, 2)
DOLLARS = Money(1_000.00, Currency.USD, prov.EMPTY)
SERIES = official_rates.series([(CREDIT_DATE, 42.00), (REPATRIATION_DATE, 43.00)])
"""Both dates the shipped table's readings recognise income on. A series covering only one
would refuse the reading that needs the other, which is right and is a different test."""

SECOND_SCHEME = """
[scheme]
id                = "xx_second_group"
name              = "SYNTHETIC FIXTURE -- a second, differently identified scheme"
jurisdiction      = "ua"
tax_currency      = "UAH"
variant           = "synthetic_variant"
reporting_cadence = "monthly"
declared_for      = "stream"

  [[scheme.rate_component]]
  id   = "xx_turnover"
  name = "SYNTHETIC податок з обороту"

    [[scheme.rate_component.rate]]
    effective_from = "2024-01-01"
    rate_pct       = 2.0
    note           = "SYNTHETIC FIXTURE -- a rate no legislature enacted."
    kind           = "tax_rule"
    source         = "SYNTHETIC FIXTURE -- an invented rate."
    retrieved_on   = "2026-08-30"
    verified_on    = ""

  [[scheme.periodic_component]]
  id     = "xx_contribution"
  name   = "SYNTHETIC синтетичний внесок"
  period = "month"

    [[scheme.periodic_component.amount]]
    effective_from = "2024-01-01"
    amount         = 1_760.0
    currency       = "UAH"
    note           = "SYNTHETIC FIXTURE -- a statutory sum nobody legislated."
    kind           = "tax_rule"
    source         = "SYNTHETIC FIXTURE -- an invented statutory sum."
    retrieved_on   = "2026-08-30"
    verified_on    = ""
"""

SECOND_DESTINATION = """
[[destination]]
scheme          = "xx_second_group"
venue           = "fop"
verdict         = "interpreted"
grounds         = "SYNTHETIC FIXTURE -- an invented judgement about an invented scheme."
resolution_path = "SYNTHETIC FIXTURE -- an invented way of closing an invented question."
kind            = "tax_rule"
source          = "SYNTHETIC FIXTURE -- an invented judgement."
retrieved_on    = "2026-08-30"
verified_on     = ""

  [[destination.reading]]
  id            = "xx_reading"
  label         = "SYNTHETIC FIXTURE -- an invented reading"
  scheme        = "xx_second_group"
  recognised_on = "credited"
  kind          = "tax_rule"
  source        = "SYNTHETIC FIXTURE -- an invented reading."
  retrieved_on  = "2026-08-30"
  verified_on   = ""
"""


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def _resolved(root: Path) -> resolver.SchemeDeclarations:
    return resolver.schemes_from_data_root(root, base_currency=Currency.UAH)


def _applied(
    declared: resolver.SchemeDeclarations, *, scheme_id: str, credited_to: str
) -> schemes.DestinationOutcome:
    return schemes.apply(
        scheme_id=scheme_id,
        credited_to=credited_to,
        amount=DOLLARS,
        on_dates={"credited": CREDIT_DATE, "repatriated": REPATRIATION_DATE},
        schemes=declared.schemes,
        destinations=declared.destinations,
        series=SERIES,
    )


SOURCE_ROOT = REPO_ROOT / "src" / "terezy"


def _source_digest() -> str:
    """A digest of every module under ``src/terezy``, so *zero source lines changed* is a fact.

    Compared before and against after within one case, rather than against the git index: the
    claim is about what **this test** needed, and asking git would instead ask whether the
    working tree happened to be clean, which is a different question with a different answer
    on every machine.
    """
    digest = hashlib.sha256()
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        digest.update(path.relative_to(SOURCE_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


BEFORE = _source_digest()


def _no_source_changed() -> None:
    assert _source_digest() == BEFORE, (
        "a module under src/terezy changed while this case ran. The whole claim is that a "
        "second scheme, a legislated change and a moved verdict are files"
    )


class TestASecondSchemeIsAFile:
    """SC-012: a different component set, different schedules, and a periodic component."""

    def test_it_loads_and_charges_beside_the_shipped_one(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        (root / "tax" / "schemes" / "xx_second_group.toml").write_text(
            SECOND_SCHEME, encoding="utf-8"
        )
        (root / "tax" / "destinations" / "xx.toml").write_text(SECOND_DESTINATION, encoding="utf-8")
        declared = _resolved(root)

        outcome = _applied(declared, scheme_id="xx_second_group", credited_to="fop")
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        #   base = 1 000.00 USD x 42.00 = 42 000.00 UAH
        #   xx_turnover = 42 000 x 0.02 = 840.00 UAH
        assert outcome.charge.base.amount == 42_000.00
        assert [line.component_id for line in outcome.charge.lines] == ["xx_turnover"]
        assert outcome.charge.total.amount == 840.00
        _no_source_changed()

    def test_its_periodic_component_charges_where_the_shipped_one_charges_nothing(
        self, tmp_path: Path
    ) -> None:
        """SC-010: two schemes differing in a periodic component differ by exactly it."""
        root = _root(tmp_path)
        (root / "tax" / "schemes" / "xx_second_group.toml").write_text(
            SECOND_SCHEME, encoding="utf-8"
        )
        declared = _resolved(root)
        window = Window(first="2026-09", last="2026-11")

        second = schemes.charge_periods(declared.schemes["xx_second_group"], window)
        shipped = schemes.charge_periods(declared.schemes["ua_fop_group_3_non_vat"], window)
        assert len(second) == len(shipped) == 3
        for one, other in zip(second, shipped, strict=True):
            assert isinstance(one, schemes.PeriodicCharge), one
            assert isinstance(other, schemes.PeriodicCharge), other
            assert one.charged.amount - other.charged.amount == 1_760.0
        _no_source_changed()

    def test_no_component_of_it_has_a_name_the_engine_has_ever_seen(self, tmp_path: Path) -> None:
        """A component is charged and reported under its declared name, whatever it is."""
        root = _root(tmp_path)
        (root / "tax" / "schemes" / "xx_second_group.toml").write_text(
            SECOND_SCHEME, encoding="utf-8"
        )
        (root / "tax" / "destinations" / "xx.toml").write_text(SECOND_DESTINATION, encoding="utf-8")
        outcome = _applied(_resolved(root), scheme_id="xx_second_group", credited_to="fop")
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        assert [line.name for line in outcome.charge.lines] == ["SYNTHETIC податок з обороту"]


class TestALegislatedChangeIsOneDatedEntry:
    """SC-004: entered as data, in force on its own date, with no source line changed."""

    def test_a_new_entry_takes_effect_on_its_own_date_and_not_before(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        scheme_file = root / "tax" / "schemes" / "ua_fop_group_3.toml"
        scheme_file.write_text(
            scheme_file.read_text(encoding="utf-8")
            + """
    [[scheme.rate_component.rate]]
    effective_from = "2027-03-15"
    rate_pct       = 2.0
    note           = "SYNTHETIC FIXTURE -- a legislated change nobody legislated."
    kind           = "tax_rule"
    source         = "SYNTHETIC FIXTURE -- an invented amending law."
    retrieved_on   = "2026-08-30"
    verified_on    = ""
""",
            encoding="utf-8",
        )
        declared = _resolved(root)
        scheme = declared.schemes["ua_fop_group_3_non_vat"]

        before = schemes.charge_income(
            scheme,
            DOLLARS,
            on_date=date(2027, 3, 14),
            series=official_rates.series([(date(2027, 3, 14), 42.00)]),
        )
        on_the_day = schemes.charge_income(scheme, DOLLARS, on_date=CREDIT_DATE, series=SERIES)
        assert isinstance(before, schemes.SchemeCharge), before
        assert isinstance(on_the_day, schemes.SchemeCharge), on_the_day
        levy = "viyskovyi_zbir"
        assert next(x for x in before.lines if x.component_id == levy).rate == 0.01
        assert next(x for x in on_the_day.lines if x.component_id == levy).rate == 0.02
        _no_source_changed()


class TestAMovedVerdictIsARow:
    """The change this feature was built for, since the verdicts are expected to move."""

    def test_moving_a_row_to_interpreted_turns_a_switch_into_a_charge(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        text = table.read_text(encoding="utf-8")

        before = _applied(
            _resolved(root), scheme_id="ua_fop_group_3_non_vat", credited_to="coinbase"
        )
        assert isinstance(before, schemes.UnsettledDestination), before
        assert len(before.figures) == 1

        # One word, in one file: the crypto-exchange row's verdict.
        marker = 'venue           = "coinbase"\nverdict         = "unsettled"'
        assert marker in text
        table.write_text(
            text.replace(marker, 'venue           = "coinbase"\nverdict         = "interpreted"'),
            encoding="utf-8",
        )
        after = _applied(
            _resolved(root), scheme_id="ua_fop_group_3_non_vat", credited_to="coinbase"
        )

        assert isinstance(after, schemes.ChargedUnderTheScheme), after
        assert after.charge.base.amount == before.figures[0].charge.base.amount
        _no_source_changed()


class TestTheEngineKnowsNoDateName:
    """A reading's ``recognised_on`` is a declared word, proved by renaming every one of them.

    The shipped names are ordinary English -- ``credited``, ``repatriated`` -- so a source
    scan over them reports refusal messages rather than branches. A rename is the claim
    itself: rows recognising income on ``xx_alpha`` and ``xx_beta`` must produce exactly the
    figures the shipped names produce, because nothing in the engine reads either.
    """

    def test_renaming_every_declared_date_name_changes_no_figure(self, tmp_path: Path) -> None:
        root = _root(tmp_path)
        table = root / "tax" / "destinations" / "ua.toml"
        text = table.read_text(encoding="utf-8")
        assert '"credited"' in text
        assert '"repatriated"' in text

        before = _applied(
            _resolved(root), scheme_id="ua_fop_group_3_non_vat", credited_to="payoneer"
        )
        table.write_text(
            re.sub(
                r'(recognised_on\s*=\s*)"repatriated"',
                r'\1"xx_beta"',
                re.sub(r'(recognised_on\s*=\s*)"credited"', r'\1"xx_alpha"', text),
            ),
            encoding="utf-8",
        )
        renamed = schemes.apply(
            scheme_id="ua_fop_group_3_non_vat",
            credited_to="payoneer",
            amount=DOLLARS,
            on_dates={"xx_alpha": CREDIT_DATE, "xx_beta": REPATRIATION_DATE},
            schemes=_resolved(root).schemes,
            destinations=_resolved(root).destinations,
            series=SERIES,
        )

        assert isinstance(before, schemes.UnsettledDestination), before
        assert isinstance(renamed, schemes.UnsettledDestination), renamed
        assert [figure.charge.total.amount for figure in renamed.figures] == [
            figure.charge.total.amount for figure in before.figures
        ]
        assert [figure.recognised_on for figure in renamed.figures] == [
            "xx_alpha",
            "xx_beta",
            "xx_alpha",
        ]
        _no_source_changed()

    def test_a_date_name_the_caller_does_not_supply_refuses_rather_than_borrowing_one(
        self, tmp_path: Path
    ) -> None:
        """A switch short of a reading reads as complete when it is not."""
        declared = _resolved(_root(tmp_path))
        outcome = schemes.apply(
            scheme_id="ua_fop_group_3_non_vat",
            credited_to="payoneer",
            amount=DOLLARS,
            on_dates={"credited": CREDIT_DATE},
            schemes=declared.schemes,
            destinations=declared.destinations,
            series=SERIES,
        )
        assert isinstance(outcome, schemes.ReadingRefused), outcome
        assert isinstance(outcome.because, schemes.ReadingDateUndeclared)
        assert outcome.because.recognised_on == "repatriated"


class TestTheShippedStreamIsChargedRatherThanRefused:
    """SC-013a: the owner's own case, whose two venues differ."""

    def test_its_routing_origin_and_crediting_destination_are_different_venues(self) -> None:
        ramp = _resolved(DATA_ROOT).ramp
        contract = ramp.streams["contract_usd"]
        assert contract.arrives_at == "deel"
        assert contract.credited_to == "fop"

    def test_it_is_charged_under_the_interpreted_row_and_not_refused(self) -> None:
        declared = _resolved(DATA_ROOT)
        contract = declared.ramp.streams["contract_usd"]
        assert contract.tax_scheme is not None
        outcome = _applied(
            declared, scheme_id=contract.tax_scheme, credited_to=contract.credited_to
        )
        assert isinstance(outcome, schemes.ChargedUnderTheScheme), outcome
        assert [line.component_id for line in outcome.charge.lines] == [
            "ediniy_podatok",
            "viyskovyi_zbir",
        ]

    def test_reading_the_routing_origin_as_the_destination_would_refuse(self) -> None:
        """The default FR-024a forbids, shown to change the answer rather than argued.

        Deel is a declared venue and the table has no row for it, so a reader who defaulted
        the crediting destination from ``arrives_at`` would turn an INTERPRETED charge into a
        refusal — and at another row, into a switch.
        """
        declared = _resolved(DATA_ROOT)
        contract = declared.ramp.streams["contract_usd"]
        assert contract.tax_scheme is not None
        outcome = _applied(declared, scheme_id=contract.tax_scheme, credited_to=contract.arrives_at)
        assert isinstance(outcome, schemes.CreditingDestinationRefused), outcome
        assert outcome.state is schemes.RefusedState.NO_DECLARED_JUDGEMENT
