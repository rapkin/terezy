"""SC-001: a bond declared as four dated payments, checked on paper.

The whole arithmetic is written out below and the engine is checked against it, not the
other way round. Every term is invented; nothing here describes a bond anyone can buy.

    face value          1 000.00 UAH per unit
    coverage from       2026-02-01
    day count           act/365            (annualises; it sizes nothing)

    payments, per unit
      2026-07-15  coupon                       40.00
      2027-01-15  coupon                       40.00
      2027-07-15  coupon                       40.00
      2027-07-15  principal repayment       1 000.00

    purchase            10 units on 2026-02-01 for 10 150.00 UAH

    what the holding receives
      2026-07-15  10 x    40.00  =      400.00
      2027-01-15  10 x    40.00  =      400.00
      2027-07-15  10 x    40.00  =      400.00
      2027-07-15  10 x 1 000.00  =   10 000.00
                                     ----------
      gross received                  11 200.00
      paid                            10 150.00
      net over the life                1 050.00

    units retired by the principal repayment
      10 x (1 000.00 / 1 000.00)  =  10, the whole holding: the payment repays the
      whole face of each unit, so the whole of each unit is surrendered.

    the disposal
      proceeds 10 000.00 - basis 10 150.00 = -150.00, a realised loss of exactly the
      premium paid. Both income kinds are exempt here, so the loss buys no shield and
      the tax is zero on every line -- which is why the label being load-bearing has to
      be proved somewhere else (SC-005).

    the year fractions the yield annualises on, act/365 from the purchase date
      2026-02-01 -> 2026-07-15   164 days   164/365 = 0.4493150684931507
      2026-02-01 -> 2027-01-15   348 days   348/365 = 0.9534246575342466
      2026-02-01 -> 2027-07-15   529 days   529/365 = 1.4493150684931507

The yield itself is a root and is not hand-computable, so it is checked the way a root
is: the present value of the whole series at the reported rate is zero, and the rate sits
between the two brackets a reader can verify by inspection.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EnumeratedTerms,
    Holding,
    InstrumentConstraints,
    InstrumentDeclaration,
    PaymentKind,
    ScheduledPayment,
)
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import day_count
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results import hurdle, project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

pytestmark = pytest.mark.worked_example

FIXTURE = prov.of(
    [
        SourceRef(
            id="tests/worked_examples/test_enumerated_schedule.py:schedule",
            kind="bond_terms",
            citation=(
                "SYNTHETIC FIXTURE -- four invented payments chosen to be checkable on "
                "paper. INFERENCE: nothing here is observed from any issue."
            ),
            retrieved_on=date(2026, 8, 29),
            verified_on=None,
        )
    ]
)

UAH = Currency.UAH
FACE = Money(1000.0, UAH, FIXTURE)
COVERS_FROM = date(2026, 2, 1)
QUANTITY = 10.0
COST = Money(10_150.0, UAH, FIXTURE)

PAYMENTS = (
    (date(2026, 7, 15), 40.0, PaymentKind.COUPON),
    (date(2027, 1, 15), 40.0, PaymentKind.COUPON),
    (date(2027, 7, 15), 40.0, PaymentKind.COUPON),
    (date(2027, 7, 15), 1000.0, PaymentKind.PRINCIPAL_REPAYMENT),
)

TERMS = EnumeratedTerms(
    face_value=FACE,
    covers_from=COVERS_FROM,
    payments=tuple(
        ScheduledPayment(on=on, amount=Money(amount, UAH, FIXTURE), pays=pays)
        for on, amount, pays in PAYMENTS
    ),
    day_count="act/365",
    published_in_order=None,
    provenance=FIXTURE,
)

EXEMPT_CLASS = TaxClass(
    id="ua_government_bond",
    applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
    rates=(
        RateEntry(
            effective_from=date(2020, 1, 1),
            pit_rate=0.0,
            levy_rate=0.0,
            provenance=FIXTURE,
        ),
    ),
)
"""A FIXTURE exemption. Not a claim about Ukrainian law: the real one is in
``data/tax/ua.toml`` with the citation that attests its effective date, and this example is
about a declared schedule rather than about when an exemption came into force."""

DECLARATION = InstrumentDeclaration(
    id="enumerated_worked_example",
    name="Synthetic enumerated issue — TEST FIXTURE, payments invented",
    instrument_class="enumerated_schedule",
    currency=UAH,
    is_synthetic=True,
    terms=TERMS,
    constraints=InstrumentConstraints(
        min_ticket=Money(1000.0, UAH, FIXTURE), min_unit=1.0, provenance=FIXTURE
    ),
    tax_classes={
        TaxableEventKind.COUPON: EXEMPT_CLASS.id,
        TaxableEventKind.DISPOSAL_GAIN: EXEMPT_CLASS.id,
    },
    groups=(),
)

HOLDING = Holding(
    owner_id="owner-1",
    instrument_id=DECLARATION.id,
    quantity=QUANTITY,
    purchased_on=COVERS_FROM,
    cost=COST,
)

HORIZON = DateRange(start=COVERS_FROM, end=date(2027, 12, 31))


def _projection() -> Projection:
    outcome = project.project(
        DECLARATION,
        HOLDING,
        HORIZON,
        Assumptions(consumption_method="fifo", coupon_policy="hold_cash"),
        tax_classes={EXEMPT_CLASS.id: EXEMPT_CLASS},
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


class TestTheScheduleIsExactlyWhatWasDeclared:
    def test_it_holds_the_purchase_and_the_four_payments(self) -> None:
        rows = _projection().schedule.rows
        assert [(row.occurred_on, row.kind) for row in rows] == [
            (COVERS_FROM, EventKind.PURCHASE),
            (date(2026, 7, 15), EventKind.COUPON),
            (date(2027, 1, 15), EventKind.COUPON),
            (date(2027, 7, 15), EventKind.COUPON),
            (date(2027, 7, 15), EventKind.PRINCIPAL_REPAYMENT),
        ]

    def test_two_payments_on_one_date_survive_as_two_rows(self) -> None:
        """SC-007. The ordinary way a bond ends. Merging them would sum a coupon into a
        repayment of principal and tax the result under whichever class won."""
        rows = [row for row in _projection().schedule.rows if row.occurred_on == date(2027, 7, 15)]
        assert len(rows) == 2
        assert {row.kind for row in rows} == {EventKind.COUPON, EventKind.PRINCIPAL_REPAYMENT}

    def test_each_amount_is_the_declared_one_times_the_units_held(self) -> None:
        rows = _projection().schedule.rows
        assert rows[0].gross.amount == -10_150.0
        assert [row.gross.amount for row in rows[1:]] == [400.0, 400.0, 400.0, 10_000.0]

    def test_the_principal_repayment_surrenders_the_whole_holding(self) -> None:
        principal = next(
            row for row in _projection().schedule.rows if row.kind is EventKind.PRINCIPAL_REPAYMENT
        )
        assert principal.quantity == QUANTITY


class TestTheTotalsMatchTheArithmetic:
    def test_gross_received_over_the_life_is_eleven_thousand_two_hundred(self) -> None:
        received = sum(
            row.gross.amount for row in _projection().schedule.rows if row.gross.amount > 0.0
        )
        assert is_close(received, 400.0 + 400.0 + 400.0 + 10_000.0)

    def test_the_cash_balance_ends_one_thousand_and_fifty_up(self) -> None:
        """11 200.00 in, 10 150.00 out. No funding deposit is invented, so the balance
        goes negative on the purchase date and recovers as the payments arrive."""
        projected = _projection()
        assert is_close(projected.ledger.accounts[UAH].balance.amount, 11_200.0 - 10_150.0)

    def test_the_disposal_realises_a_loss_of_exactly_the_premium(self) -> None:
        (disposal,) = _projection().ledger.disposals
        assert is_close(disposal.realised_gain_base_ccy.amount, 10_000.0 - 10_150.0)

    def test_every_line_is_taxed_at_zero_under_the_exemption(self) -> None:
        projected = _projection()
        assert projected.hurdle.total_tax.amount == 0.0
        assert all(row.tax.amount == 0.0 for row in projected.schedule.rows)
        assert {charge.tax_class_id for charge in projected.charges} == {"ua_government_bond"}


class TestTheYieldIsAnnualisedOnTheDeclaredDayCount:
    def test_the_year_fractions_are_the_ones_written_out_above(self) -> None:
        act_365 = day_count(TERMS.day_count)
        assert act_365(COVERS_FROM, date(2026, 7, 15)) == 164 / 365
        assert act_365(COVERS_FROM, date(2027, 1, 15)) == 348 / 365
        assert act_365(COVERS_FROM, date(2027, 7, 15)) == 529 / 365

    def test_the_present_value_of_the_whole_series_at_the_reported_rate_is_zero(self) -> None:
        """A root is checked as a root. The series is the one written out in the header:
        the cost out at t=0 and the four payments in, at the year fractions above."""
        rate = _projection().hurdle.nominal_ytm.value
        flows = (
            (0.0, -10_150.0),
            (164 / 365, 400.0),
            (348 / 365, 400.0),
            (529 / 365, 400.0 + 10_000.0),
        )
        assert abs(hurdle.net_present_value(flows, rate)) < TOLERANCE

    def test_the_rate_is_between_the_brackets_a_reader_can_check_by_inspection(self) -> None:
        """1 050.00 on 10 150.00 over about 1.45 years is somewhere near 7% a year, and
        certainly between 5% and 9%. The bracket is what catches a yield computed on the
        wrong clock -- a hard-coded 365-day year against a 30/360 declaration, say."""
        rate = _projection().hurdle.nominal_ytm.value
        assert 0.05 < rate < 0.09
