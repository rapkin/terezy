"""Every declared payment, against the issuer's own record. Row by row, all 24.

016 SC-002 to SC-006 and SC-009. The transcription is where a real declaration goes wrong
silently: one wrong digit in a payment row produces a schedule that loads, projects and reports
a plausible yield. So this compares the whole of every declaration against the observation it
was transcribed from, rather than sampling.

**Against the register, never against the seller.** The seller publishes the same schedules
with dates of its own, and which of the two a declaration matches is the whole question.
`test_two_sources_disagree.py` is where the disagreement itself lives.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.instruments.interface import EnumeratedTerms, PaymentKind
from terezy.core.primitives.currency import Currency
from terezy.core.results.tuple import TupleOutcome
from terezy.data.declarations import resolver
from tests import answer_registries as answers
from tests import data_roots
from tests import observations as obs

pytestmark = pytest.mark.worked_example

DATA_ROOT = data_roots.with_fixtures()
DAY_COUNT = "act/365"
"""013 FR-003a: a convention of computation, claiming nothing about the issue, and the same
one the fixtures declare so the yields are comparable (016 FR-010)."""

TAX_CLASS = "ua_government_bond"


def _terms(isin: str) -> EnumeratedTerms:
    declared = resolver.from_data_root(DATA_ROOT).instruments[isin]
    terms = declared.terms
    assert isinstance(terms, EnumeratedTerms), isin
    return terms


def _rows(isin: str) -> list[tuple[date, float, PaymentKind]]:
    """The register's payment rows for one issue: date, amount, and the issuer's own kind."""
    return [
        (
            date.fromisoformat(row["pay_date"]),
            float(row["pay_val"]),
            PaymentKind.COUPON
            if row["pay_type"] == obs.COUPON
            else PaymentKind.PRINCIPAL_REPAYMENT,
        )
        for row in obs.register_issues()[isin]["payment"]
    ]


def test_every_payment_of_every_declared_issue_equals_the_registers() -> None:
    """SC-002. Date, amount and kind, over the whole schedule of all 24.

    Amounts compared exactly rather than within the project tolerance: this is a transcription
    of one published figure into a file, not arithmetic, and a tolerance here would hide the
    only kind of error there is.
    """
    for isin in obs.declared_isins():
        declared = [
            (payment.on, payment.amount.amount, payment.pays) for payment in _terms(isin).payments
        ]
        assert declared == _rows(isin), isin


def test_no_declared_amount_is_a_sellers_figure_divided_by_anything() -> None:
    """SC-002's second half. The register publishes major units and the seller publishes the
    same amounts multiplied by 100, so a transcription from the seller would have had to choose
    a reading. Nothing here chose one: every amount is the register's own number."""
    for isin in obs.declared_isins():
        published = {row["pay_val"] for row in obs.register_issues()[isin]["payment"]}
        for payment in _terms(isin).payments:
            assert payment.amount.amount in published, (isin, payment.on)


def test_every_currency_and_face_value_is_the_registers() -> None:
    """SC-003. `val_code` and `nominal`, both stated by the issuer. No file records a currency
    inference or a task settling one, because there is nothing left to settle."""
    declared = resolver.from_data_root(DATA_ROOT)
    for isin in obs.declared_isins():
        issue = obs.register_issues()[isin]
        assert declared.instruments[isin].currency is Currency(issue["val_code"]), isin
        assert _terms(isin).face_value.amount == float(issue["nominal"]), isin
        assert _terms(isin).face_value.currency is Currency(issue["val_code"]), isin


def test_principal_repayments_are_exactly_the_registers_type_two_rows() -> None:
    """SC-004. No kind is read off an amount, a date or a position: the issuer labels it."""
    for isin in obs.declared_isins():
        registered = {
            date.fromisoformat(row["pay_date"])
            for row in obs.register_issues()[isin]["payment"]
            if row["pay_type"] == obs.PRINCIPAL
        }
        declared = {
            payment.on
            for payment in _terms(isin).payments
            if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
        }
        assert declared == registered, isin


def test_coverage_starts_at_placement_and_the_list_ends_at_maturity() -> None:
    """SC-005. The coverage claim is what the register's list actually is -- complete from
    placement -- and taking the earliest PAYMENT instead would refuse a purchase four of the
    24 plainly admit, because their first coupon falls after the owner's own outlay date."""
    for isin in obs.declared_isins():
        issue = obs.register_issues()[isin]
        terms = _terms(isin)
        assert terms.covers_from == date.fromisoformat(issue["razm_date"]), isin
        assert terms.covers_from <= min(payment.on for payment in terms.payments), isin
        assert max(payment.on for payment in terms.payments) == date.fromisoformat(
            issue["pgs_date"]
        ), isin


def test_all_twenty_four_name_one_day_count_and_it_is_the_fixtures() -> None:
    """SC-006's first half. Comparability across the registry is the only reason it matters."""
    declared = resolver.from_data_root(DATA_ROOT)
    for isin in obs.declared_isins():
        assert _terms(isin).day_count == DAY_COUNT, isin
    fixtures = {
        name: item.terms.day_count
        for name, item in declared.instruments.items()
        if item.is_synthetic and isinstance(item.terms, EnumeratedTerms)
    }
    assert DAY_COUNT in set(fixtures.values())


def test_no_declaration_records_the_order_a_source_published_in() -> None:
    """FR-009a. The field records that a source published out of ascending order; the register
    publishes all 195 schedules in ascending order, so the field is an ABSENCE here rather than
    a value. `UA4000235865`'s out-of-order publication is the seller's and lives in the
    disagreement check -- putting it here would answer a question about the wrong source."""
    for isin in obs.declared_isins():
        assert _terms(isin).published_in_order is None, isin


def test_each_issue_is_priced_by_exactly_one_access_declaration_at_the_buy_quotation() -> None:
    """SC-009's first half. One row per instrument is a load-time rule, so what is checked here
    is the figure: the price is the seller's published buy and nothing else."""
    access = resolver.tuple_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    ).access
    for isin in obs.declared_isins():
        quote = access[isin].quote
        assert quote is not None, isin
        assert quote.price.amount == obs.seller_bonds()[isin]["buy"], isin
        assert quote.price.currency is Currency.UAH, isin


def test_every_issue_names_the_shipped_government_bond_class_for_both_income_kinds() -> None:
    """SC-019's first half. FR-026: the class is named, and no rate, category or treatment is
    declared here."""
    declared = resolver.from_data_root(DATA_ROOT)
    for isin in obs.declared_isins():
        classes = {
            kind.value: name for kind, name in declared.instruments[isin].tax_classes.items()
        }
        assert classes == {"coupon": TAX_CLASS, "disposal_gain": TAX_CLASS}, isin


def test_the_tax_term_of_every_real_tuple_charges_zero() -> None:
    """SC-019's second half. ОВДП income is exempt on both sides -- the coupon under
    пп. 165.1.2 ПКУ and the disposal gain under пп. 165.1.52 -- so the tax part of the round
    trip is a RECORDED zero rather than an absent line, and no other category's base moves.
    """
    outcomes = _real_outcomes()
    assert outcomes, "the shipped registry must actually evaluate a real issue"
    for outcome in outcomes:
        charged = [item for item in outcome.parts if item.part == "tax"]
        assert len(charged) == 1, outcome.key.instrument_id
        assert charged[0].amount.amount == 0.0, outcome.key.instrument_id


def _real_outcomes() -> list[TupleOutcome]:
    real = set(obs.declared_isins())
    return [
        item
        for section in answers.answered().sections
        for item in section_evaluated(section)
        if item.key.instrument_id in real
    ]
