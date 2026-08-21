"""``fixed_income`` behaviours the worked example does not reach.

The D1 example is one bond, held from issue to maturity, paying semiannual coupons. The
cases below are the ones a second declaration will hit first -- a zero-coupon issue, a
different periodicity -- plus the two small projections of the declaration that make up
the rest of the ``Instrument`` interface.

Nothing here re-derives the coupon arithmetic; that is D1's job and duplicating it would
give a reader two schedules to reconcile.
"""

from __future__ import annotations

from datetime import date

from terezy.core.instruments import fixed_income
from terezy.core.ledger.events import Event, EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind
from tests import synthetic


def _events(**term_overrides: object) -> tuple[Event, ...]:
    produced = fixed_income.events(
        synthetic.declaration(terms=synthetic.terms(**term_overrides)),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
    )
    assert isinstance(produced, tuple)
    return produced


def test_a_zero_coupon_issue_pays_its_principal_and_nothing_else() -> None:
    # ``coupon_rate = 0.0`` is a valid declaration, not a missing rate. Emitting a stream
    # of zero-amount coupon events instead would clutter every schedule with rows that
    # never paid anything, and would invite a reader to think a payment was made.
    kinds = [event.kind for event in _events(coupon_rate=0.0)]
    assert kinds == [EventKind.PURCHASE, EventKind.PRINCIPAL_REPAYMENT]


def test_a_zero_coupon_issue_bought_at_a_discount_still_yields() -> None:
    # 8 000.00 for 10 000.00 of face two years out is a real return, and it comes from the
    # price rather than from a coupon: (10 000 / 8 000) ** (365/732) - 1, since the
    # redemption is paid 732 days after purchase (730 days plus the two the Saturday
    # maturity moved). That is 1.25 ** 0.4986... = about 11.7%.
    outcome = project.project(
        synthetic.declaration(terms=synthetic.terms(coupon_rate=0.0)),
        synthetic.holding(cost=Money(8_000.0, Currency.UAH, prov.of([synthetic.PURCHASE_SOURCE]))),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection)
    expected = (10_000.0 / 8_000.0) ** (365 / 732) - 1
    assert is_close(outcome.hurdle.nominal_ytm.value, expected)


def test_a_quarterly_issue_pays_four_coupons_a_year() -> None:
    # The periodicity is declared, so a different frequency is a data change. Eight
    # quarterly coupons over the two years to maturity.
    coupons = [
        event for event in _events(periodicity="quarterly") if event.kind is EventKind.COUPON
    ]
    assert len(coupons) == 8


def test_an_annual_issue_pays_two_coupons_over_two_years() -> None:
    coupons = [event for event in _events(periodicity="annual") if event.kind is EventKind.COUPON]
    assert len(coupons) == 2


def test_the_lot_identity_is_derived_from_the_purchase_and_is_stable() -> None:
    # Not generated: a counter or a clock would make two runs of the same scenario
    # produce different-looking results and break the determinism digest (C4).
    holding = synthetic.holding()
    assert fixed_income.lot_id_for(holding) == "ovdp_synthetic_test@2026-01-15"
    assert fixed_income.lot_id_for(holding) == fixed_income.lot_id_for(
        synthetic.holding(purchased_on=date(2026, 1, 15))
    )


def test_the_declared_tax_classes_are_returned_unchanged() -> None:
    declaration = synthetic.declaration()
    assert fixed_income.tax_classes(declaration) == {
        TaxableEventKind.COUPON: synthetic.EXEMPT_CLASS.id,
        TaxableEventKind.DISPOSAL_GAIN: synthetic.EXEMPT_CLASS.id,
    }


def test_the_declared_constraints_are_returned_unchanged() -> None:
    declaration = synthetic.declaration()
    assert fixed_income.constraints(declaration) is declaration.constraints
