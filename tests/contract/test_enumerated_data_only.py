"""SC-004: a third bond declared as its payments, in data only, runs the whole pipeline.

Constitution Principle II: *adding an instrument must be a data-only change; if it requires
an engine edit, the abstraction is wrong.* Feature 001 proved that for a bond declared by
its terms, feature 006 for a fund. This proves it for the form 013 adds -- and the claim is
made under the loosest conditions available: a file this repository has never seen, in a
scratch data root, differing from the fixture it is modelled on in its payments, its coverage claim,
its face value and its day count.

The **duplicate identifier** half of SC-006 lives here rather than in the loading battery,
because it is a relation between two files and the resolver is what holds both.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EnumeratedTerms,
    Holding,
)
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = data_roots.with_fixtures()
SHIPPED = "ovdp_enumerated_a"
THIRD = "ovdp_enumerated_c"

CITATION = "INFERENCE: SYNTHETIC FIXTURE — invented for a data-only test; observed nowhere."

DECLARATION = f"""
[instrument]
id           = "{THIRD}"
name         = "Synthetic enumerated issue C — TEST FIXTURE, payments invented"
class        = "enumerated_schedule"
currency     = "UAH"
is_synthetic = true
groups       = []

[instrument.schedule]
face_value   = 500.0
covers_from  = "2026-03-01"
day_count    = "30/360"
kind         = "bond_terms"
source       = "{CITATION}"
retrieved_on = "2026-08-29"
verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2026-09-01"
  amount       = 25.0
  pays         = "coupon"
  kind         = "bond_terms"
  source       = "{CITATION}"
  retrieved_on = "2026-08-29"
  verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2027-03-01"
  amount       = 25.0
  pays         = "coupon"
  kind         = "bond_terms"
  source       = "{CITATION}"
  retrieved_on = "2026-08-29"
  verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2027-03-01"
  amount       = 500.0
  pays         = "principal_repayment"
  kind         = "bond_terms"
  source       = "{CITATION}"
  retrieved_on = "2026-08-29"
  verified_on  = ""

[instrument.constraints]
min_ticket   = 500.0
min_unit     = 1.0
kind         = "venue_terms"
source       = "SYNTHETIC FIXTURE — an invented minimum ticket of one bond."
retrieved_on = "2026-08-29"
verified_on  = ""

[instrument.tax_classes]
coupon        = "ua_government_bond"
disposal_gain = "ua_government_bond"

[[instrument.verification_task]]
settles     = "face_value"
question    = "What face value does this issue actually have?"
searched    = "SYNTHETIC FIXTURE — nothing was searched; the value is invented."
searched_on = "2026-08-29"

[[instrument.verification_task]]
settles     = "payment_kind"
question    = "Which payments are coupons and which repay principal?"
searched    = "SYNTHETIC FIXTURE — nothing was searched; the labels are invented."
searched_on = "2026-08-29"

[[instrument.verification_task]]
settles     = "minor_unit_conversion"
question    = "Do the published figures denote hryvnia or kopecks?"
searched    = "SYNTHETIC FIXTURE — no conversion was performed."
searched_on = "2026-08-29"

[[instrument.verification_task]]
settles     = "coverage"
question    = "Is this list complete from 2026-03-01 onwards?"
searched    = "SYNTHETIC FIXTURE — the claim is invented."
searched_on = "2026-08-29"
"""


def _scratch(tmp_path: Path, *, instrument_id: str = THIRD) -> Path:
    """A copy of ``data/`` with one new declaration file added, and nothing else changed."""
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    (root / "instruments" / f"{instrument_id}.toml").write_text(
        DECLARATION.replace(THIRD, instrument_id), encoding="utf-8"
    )
    return root


def _projected(root: Path, instrument_id: str) -> Projection:
    declarations = resolver.from_data_root(root)
    outcome = project.project(
        declarations.instruments[instrument_id],
        Holding(
            owner_id="owner-1",
            instrument_id=instrument_id,
            quantity=4.0,
            purchased_on=date(2026, 3, 1),
            cost=Money(2_040.0, Currency.UAH, prov.EMPTY),
        ),
        DateRange(start=date(2026, 3, 1), end=date(2027, 12, 31)),
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


class TestAThirdIssueNeedsAFileAndNothingElse:
    def test_it_loads_beside_the_shipped_declarations(self, tmp_path: Path) -> None:
        declarations = resolver.from_data_root(_scratch(tmp_path))
        assert THIRD in declarations.instruments
        assert isinstance(declarations.instruments[THIRD].terms, EnumeratedTerms)

    def test_it_projects_the_payments_it_declares(self, tmp_path: Path) -> None:
        rows = _projected(_scratch(tmp_path), THIRD).schedule.rows
        assert [(row.occurred_on, row.gross.amount) for row in rows] == [
            (date(2026, 3, 1), -2_040.0),
            (date(2026, 9, 1), 100.0),
            (date(2027, 3, 1), 100.0),
            (date(2027, 3, 1), 2_000.0),
        ]

    def test_it_declares_a_convention_the_shipped_fixtures_do_not(self, tmp_path: Path) -> None:
        """What a *data-only* test can honestly claim about the day count: a third file
        naming a convention no shipped declaration names loads, projects and annualises on
        it, with no engine edit.

        ⚙ It cannot claim the convention is what **moved** the yield, and used to: the two
        instruments differ in five things, so a different yield is over-determined and the
        assertion held with the day counts made identical. The single-variable version --
        one declaration, one field changed -- is `test_enumerated_yield.py`, and
        `test_day_count_reaches_no_amount.py` holds the bit-identity half.
        """
        root = _scratch(tmp_path)
        declarations = resolver.from_data_root(root)
        terms = declarations.instruments[THIRD].terms
        assert isinstance(terms, EnumeratedTerms)
        assert terms.day_count == "30/360"
        assert terms.day_count not in {
            declared.terms.day_count
            for identifier, declared in declarations.instruments.items()
            if identifier != THIRD and isinstance(declared.terms, EnumeratedTerms)
        }, "no shipped declaration of this form names it, so the file is what carries it"
        assert _projected(root, THIRD).hurdle.nominal_ytm.value > 0.0

    def test_it_reaches_the_declared_exemption_with_no_extra_declaration(
        self, tmp_path: Path
    ) -> None:
        """FR-013's second half: sharing an existing tax class is also data only."""
        projected = _projected(_scratch(tmp_path), THIRD)
        assert projected.hurdle.total_tax.amount == 0.0
        assert {charge.tax_class_id for charge in projected.charges} == {"ua_government_bond"}

    def test_the_premium_paid_is_recorded_in_full_as_the_lot_s_basis(self, tmp_path: Path) -> None:
        """FR-024. 2 040.00 for four units of 500.00 face is a premium of 40.00, and the
        realised loss at redemption is exactly that. Nothing is amortised or imputed."""
        (disposal,) = _projected(_scratch(tmp_path), THIRD).ledger.disposals
        assert is_close(disposal.realised_gain_base_ccy.amount, 2_000.0 - 2_040.0)


class TestTheIdSpaceIsShared:
    def test_a_duplicate_identifier_collides_across_the_two_forms(self, tmp_path: Path) -> None:
        """SC-006's last case. A file declaring an id another file already declares is a
        load-time collision whichever forms the two are in: neither is merged and neither
        is preferred, because whichever loaded second would silently win by directory
        order."""
        root = _scratch(tmp_path, instrument_id="ovdp_synthetic_a_duplicate")
        clash = root / "instruments" / "ovdp_synthetic_a_duplicate.toml"
        clash.write_text(
            clash.read_text(encoding="utf-8").replace(
                'id           = "ovdp_synthetic_a_duplicate"', 'id           = "ovdp_synthetic_a"'
            ),
            encoding="utf-8",
        )
        with pytest.raises(DeclarationError) as raised:
            resolver.from_data_root(root)
        assert "ovdp_synthetic_a" in raised.value.problem
        assert raised.value.field_path == "instrument.id"


class TestNoSourceCodeKnowsAboutTheThirdIssue:
    def test_no_module_names_it(self) -> None:
        """It cannot: the file is written by this test and has never been on disk. Stated
        as an assertion anyway, because the claim under test is exactly that no engine edit
        was needed and a reader should see it checked."""
        source_root = REPO_ROOT / "src" / "terezy"
        assert not [
            path
            for path in sorted(source_root.rglob("*.py"))
            if THIRD in path.read_text(encoding="utf-8")
        ]
