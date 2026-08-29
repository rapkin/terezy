"""SC-006, SC-019, SC-021: every way a declared schedule can be wrong, refused at load.

Principle II: *data files fail loudly at load time on a malformed or unknown field, naming
the file and the field. Silent defaulting is a defect.* This is that requirement for the
second declaration form, and the battery below is the specification's own list.

**Nothing in here is repaired on the way in.** No payment is sorted, merged, deduplicated
or reordered, and no default is substituted for anything. Ordering in particular is settled
at **transcription** -- the same declared human step that turns kopecks into hryvnia -- and
a loader that sorted the list would delete the one fact FR-020a exists to keep: that the
source published it in a different order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terezy.core.instruments.interface import EnumeratedTerms, PaymentKind
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

BASE = """
[instrument]
id           = "enumerated_fixture"
name         = "Synthetic enumerated fixture — TEST FIXTURE, payments invented"
class        = "enumerated_schedule"
currency     = "UAH"
is_synthetic = true

[instrument.schedule]
face_value   = 1000.0
covers_from  = "2026-02-01"
day_count    = "act/365"
kind         = "bond_terms"
source       = "INFERENCE: SYNTHETIC FIXTURE — invented, not observed from any issue."
retrieved_on = "2026-08-29"
verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2026-07-15"
  amount       = 40.0
  pays         = "coupon"
  kind         = "bond_terms"
  source       = "INFERENCE: SYNTHETIC FIXTURE — the kind is a reading of a list of numbers."
  retrieved_on = "2026-08-29"
  verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2027-07-15"
  amount       = 40.0
  pays         = "coupon"
  kind         = "bond_terms"
  source       = "INFERENCE: SYNTHETIC FIXTURE — the kind is a reading of a list of numbers."
  retrieved_on = "2026-08-29"
  verified_on  = ""

  [[instrument.schedule.payment]]
  on           = "2027-07-15"
  amount       = 1000.0
  pays         = "principal_repayment"
  kind         = "bond_terms"
  source       = "INFERENCE: SYNTHETIC FIXTURE — the kind is a reading of a list of numbers."
  retrieved_on = "2026-08-29"
  verified_on  = ""

[instrument.constraints]
min_ticket   = 1000.0
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
question    = "Which of these payments is a coupon and which is a repayment of principal?"
searched    = "SYNTHETIC FIXTURE — nothing was searched; the labels are invented."
searched_on = "2026-08-29"

[[instrument.verification_task]]
settles     = "minor_unit_conversion"
question    = "Do the published figures denote hryvnia or kopecks?"
searched    = "SYNTHETIC FIXTURE — no conversion was performed; the figures are invented."
searched_on = "2026-08-29"

[[instrument.verification_task]]
settles     = "coverage"
question    = "Is this list complete from the coverage date to the end of the issue's life?"
searched    = "SYNTHETIC FIXTURE — nothing was searched; the claim is invented."
searched_on = "2026-08-29"
"""


def _written(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "enumerated_fixture.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _replaced(old: str, new: str) -> str:
    assert old in BASE, f"the battery's base file no longer contains {old!r}"
    return BASE.replace(old, new, 1)


class TestTheWellFormedDeclarationLoads:
    def test_it_becomes_a_declaration_carrying_listed_terms(self, tmp_path: Path) -> None:
        declared = loader.enumerated_instrument_from_file(_written(tmp_path, BASE))
        assert declared.instrument_class == "enumerated_schedule"
        assert isinstance(declared.terms, EnumeratedTerms)

    def test_the_payments_arrive_in_the_declared_order_and_number(self, tmp_path: Path) -> None:
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, BASE)).terms
        assert isinstance(terms, EnumeratedTerms)
        assert [(payment.on.isoformat(), payment.amount.amount) for payment in terms.payments] == [
            ("2026-07-15", 40.0),
            ("2027-07-15", 40.0),
            ("2027-07-15", 1000.0),
        ]

    def test_two_payments_on_one_date_are_two_payments(self, tmp_path: Path) -> None:
        """SC-007 at the boundary. Merging them would be the loader deciding that a coupon
        and a repayment of principal are one payment, which they are not: they are taxed
        under different declared classes."""
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, BASE)).terms
        assert isinstance(terms, EnumeratedTerms)
        on_the_last_date = [p for p in terms.payments if p.on.isoformat() == "2027-07-15"]
        assert [p.pays for p in on_the_last_date] == [
            PaymentKind.COUPON,
            PaymentKind.PRINCIPAL_REPAYMENT,
        ]

    def test_no_generative_term_is_invented_for_it(self, tmp_path: Path) -> None:
        """US1 scenario 2. There is nowhere to put an issue date, a coupon rate, a
        periodicity, a business-day rule or a maturity date, so none is substituted."""
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, BASE)).terms
        for absent in (
            "issue_date",
            "coupon_rate",
            "periodicity",
            "business_day_rule",
            "maturity_date",
        ):
            assert not hasattr(terms, absent)

    def test_the_declared_amounts_are_carried_through_unscaled(self, tmp_path: Path) -> None:
        """FR-004. A figure published in minor units is converted at transcription, and the
        engine performs no unit scaling of a declared amount."""
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, BASE)).terms
        assert isinstance(terms, EnumeratedTerms)
        assert terms.face_value.amount == 1000.0
        assert {payment.amount.amount for payment in terms.payments} == {40.0, 1000.0}


class TestTheBatteryOfBrokenDeclarations:
    """SC-006. Every one names the file and the offending entry, and defaults nothing."""

    def _refused(self, tmp_path: Path, text: str) -> DeclarationError:
        with pytest.raises(DeclarationError) as raised:
            loader.enumerated_instrument_from_file(_written(tmp_path, text))
        assert raised.value.file == tmp_path / "enumerated_fixture.toml"
        return raised.value

    def test_a_declaration_in_both_forms_at_once(self, tmp_path: Path) -> None:
        both = _replaced(
            "[instrument.schedule]",
            "[instrument.terms]\nface_value = 1000.0\n\n[instrument.schedule]",
        )
        assert "instrument" in self._refused(tmp_path, both).field_path

    def test_a_declaration_in_neither_form(self, tmp_path: Path) -> None:
        neither = BASE.replace("[instrument.schedule]", "[instrument.nothing_at_all]", 1)
        assert self._refused(tmp_path, neither).field_path

    def test_an_empty_payment_list(self, tmp_path: Path) -> None:
        empty = (
            BASE[: BASE.index("  [[instrument.schedule.payment]]")]
            + BASE[BASE.index("[instrument.constraints]") :]
        )
        refused = self._refused(tmp_path, empty)
        assert refused.field_path == "instrument.schedule.payment"

    def test_a_payment_list_out_of_date_order(self, tmp_path: Path) -> None:
        """The loader neither sorts nor accepts it (FR-006). Sorting would delete the fact
        FR-020a exists to keep."""
        unordered = _replaced('  on           = "2026-07-15"', '  on           = "2028-07-15"')
        refused = self._refused(tmp_path, unordered)
        assert "ascending" in refused.problem
        assert "sorted" in refused.problem or "sort" in refused.problem

    def test_a_payment_before_the_coverage_start(self, tmp_path: Path) -> None:
        early = _replaced('covers_from  = "2026-02-01"', 'covers_from  = "2026-12-01"')
        refused = self._refused(tmp_path, early)
        assert "2026-07-15" in refused.problem
        assert "2026-12-01" in refused.problem

    def test_a_non_positive_amount(self, tmp_path: Path) -> None:
        zero = _replaced("  amount       = 40.0", "  amount       = 0.0")
        assert self._refused(tmp_path, zero).field_path.startswith("instrument.schedule.payment[0]")

    def test_a_missing_payment_kind(self, tmp_path: Path) -> None:
        missing = _replaced('  pays         = "coupon"\n', "")
        assert "pays" in self._refused(tmp_path, missing).field_path

    def test_an_unrecognised_payment_kind(self, tmp_path: Path) -> None:
        unknown = _replaced('  pays         = "coupon"', '  pays         = "premium_rebate"')
        refused = self._refused(tmp_path, unknown)
        assert "premium_rebate" in refused.problem
        assert "coupon" in str(refused)

    def test_a_schedule_with_no_principal_repayment(self, tmp_path: Path) -> None:
        no_principal = _replaced(
            '  pays         = "principal_repayment"', '  pays         = "coupon"'
        )
        refused = self._refused(tmp_path, no_principal)
        assert refused.field_path == "instrument.schedule.payment"
        assert "principal" in refused.problem

    def test_a_declared_maturity_date(self, tmp_path: Path) -> None:
        """SC-019. The endpoint gives one and it disagrees with the last published payment
        in over half the observed issues; accepting it would import that disagreement in
        exchange for a field nothing reads. The count is measured in
        `tests/contract/test_the_observation_the_form_rests_on.py`."""
        with_maturity = _replaced(
            'day_count    = "act/365"', 'day_count    = "act/365"\nmaturity_date = "2027-07-16"'
        )
        refused = self._refused(tmp_path, with_maturity)
        assert "maturity_date" in refused.field_path

    @pytest.mark.parametrize(
        ("line", "field"),
        [
            ('issue_date = "2026-01-15"', "issue_date"),
            ("coupon_rate_pct = 15.5", "coupon_rate_pct"),
            ('periodicity = "semiannual"', "periodicity"),
            ('business_day_rule = "following"', "business_day_rule"),
        ],
    )
    def test_a_declared_generative_term(self, tmp_path: Path, line: str, field: str) -> None:
        """SC-019. Forbidden rather than optional: each would be either invented or unread."""
        with_term = _replaced('day_count    = "act/365"', f'day_count    = "act/365"\n{line}')
        assert field in self._refused(tmp_path, with_term).field_path

    def test_a_missing_day_count(self, tmp_path: Path) -> None:
        """SC-019's second half. Required, because the contractual yield cannot be computed
        without one and a hard-coded 365 is forbidden at the site that would need it."""
        without = _replaced('day_count    = "act/365"\n', "")
        assert "day_count" in self._refused(tmp_path, without).field_path

    def test_an_unrecognised_day_count(self, tmp_path: Path) -> None:
        unknown = _replaced('day_count    = "act/365"', 'day_count    = "act/360"')
        refused = self._refused(tmp_path, unknown)
        assert "act/360" in refused.problem
        assert "act/365" in str(refused)

    def test_a_second_coverage_bound(self, tmp_path: Path) -> None:
        """SC-021. A two-ended window cannot be expressed: the field does not exist, so a
        schedule truncated at the far end is an unrepresentable state rather than a
        silently short projection."""
        two_ended = _replaced(
            'covers_from  = "2026-02-01"',
            'covers_from  = "2026-02-01"\ncovers_until = "2027-02-01"',
        )
        assert "covers_until" in self._refused(tmp_path, two_ended).field_path

    def test_an_income_kind_with_no_declared_tax_class(self, tmp_path: Path) -> None:
        """FR-009. A missing rule and a cited exemption are opposite claims, and only one
        of them has a source."""
        no_disposal = _replaced('disposal_gain = "ua_government_bond"\n', "")
        refused = self._refused(tmp_path, no_disposal)
        assert "disposal_gain" in refused.problem
        assert "principal_repayment" in refused.problem


class TestTheTranscribedSourceOrder:
    """FR-020a, SC-018. What the source published, kept as a fact about the source."""

    OUT_OF_ORDER = _replaced(
        'day_count    = "act/365"',
        'day_count    = "act/365"\npublished_in_order = ["2026-07-15", "2027-07-15", "2027-07-15"]',
    )

    def test_a_declared_order_is_carried(self, tmp_path: Path) -> None:
        reordered = self.OUT_OF_ORDER.replace(
            'published_in_order = ["2026-07-15", "2027-07-15", "2027-07-15"]',
            'published_in_order = ["2027-07-15", "2026-07-15", "2027-07-15"]',
        )
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, reordered)).terms
        assert isinstance(terms, EnumeratedTerms)
        assert terms.published_in_order is not None

    def test_declaring_the_ascending_order_is_refused(self, tmp_path: Path) -> None:
        """The field records a **difference**. Declaring the order the payments are already
        in records nothing, and a field that can be filled in without saying anything is a
        field that stops tracking the source."""
        with pytest.raises(DeclarationError) as raised:
            loader.enumerated_instrument_from_file(_written(tmp_path, self.OUT_OF_ORDER))
        assert "published_in_order" in raised.value.field_path

    def test_an_order_that_is_not_a_permutation_of_the_payments_is_refused(
        self, tmp_path: Path
    ) -> None:
        wrong = self.OUT_OF_ORDER.replace(
            'published_in_order = ["2026-07-15", "2027-07-15", "2027-07-15"]',
            'published_in_order = ["2027-07-15", "2026-07-15"]',
        )
        with pytest.raises(DeclarationError) as raised:
            loader.enumerated_instrument_from_file(_written(tmp_path, wrong))
        assert "published_in_order" in raised.value.field_path

    def test_omitting_it_is_the_ordinary_case(self, tmp_path: Path) -> None:
        terms = loader.enumerated_instrument_from_file(_written(tmp_path, BASE)).terms
        assert isinstance(terms, EnumeratedTerms)
        assert terms.published_in_order is None
