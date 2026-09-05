"""SC-016: a purchase above face, and what the declared category does with the difference.

A secondary-market bond is usually bought at a **dirty price above face**. Held to the end
of its schedule it returns face, so the ledger realises a loss equal to the premium.
Whether that loss reduces anything is decided by the declared tax category and by nothing
this engine believes (FR-025, FR-026).

**Both answers are exercised here rather than one being warned about.** Under Ukraine's
`exempt_securities` the treatment is `outside`: the provision it cites in
`data/tax/timing/ua.toml` excludes both income *and* acquisition costs from the annual
investment result, so the premium reduces nothing and an exempt loss buys no shield.
Under a category that **nets**, the same premium reaches the year's base -- and that
case is reachable inside this feature because FR-010's fixture, whose two income kinds
carry different declared rates, lands in one.

```
enumerated_taxable_x, face 1 000.00, two coupons of 50.00, principal 1 000.00 on 2026-12-05

  2026-01-05  lot A: 10 units at 1 030.00  ->  paid 10 300.00   a premium of  300.00
  2026-01-06  lot B: 10 units at   900.00  ->  paid  9 000.00   a discount of 1 000.00

  2026-12-05  both redeem at face: 10 000.00 each
              lot A   10 000.00 - 10 300.00 = -300.00   a loss
              lot B   10 000.00 -  9 000.00 = 1 000.00  a gain

  the netting category, 2026
              netted base = 1 000.00 - 300.00 = 700.00
              at 12% + 3%                     = 105.00

  the same year with lot A bought at face instead
              netted base = 1 000.00         = 1 000.00
              at 12% + 3%                     = 150.00

  so the premium reduced the netted base by exactly 300.00, and the liability by 45.00
```

The carryforward half changes one figure: lot B bought at 9 900.00 instead, a gain of
100.00 against the 300.00 loss, so the year nets to **-200.00**, nothing is owed, and
200.00 carries into the following years.

⚙ **Two holdings of one declaration, folded once.** A premium purchase realises only a
loss, whatever the schedule's shape -- proceeds are face and the basis is above it -- so a
same-category **gain** in the same year has to come from a second lot, which is what FR-026
requires the fixture to supply. Without one the year is simply negative and *"reduces the
netted base by exactly the premium"* has nothing to reduce, collapsing the assertion into
its carryforward half while reading as though it tested both.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Final

import pytest

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    EarlyExit,
    EnumeratedTerms,
    Holding,
    InstrumentDeclaration,
    PaymentKind,
)
from terezy.core.instruments.registry import ops_for
from terezy.core.ledger import engine
from terezy.core.ledger.events import Event
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import GovernedBy, Projection, PurchasePremium
from terezy.core.scenarios.quotation import QuotationHolds
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxContext
from terezy.data.declarations import resolver
from tests import tax_years
from tests import tuple_registries as fixtures

pytestmark = pytest.mark.worked_example

UAH: Final = Currency.UAH
TAXABLE: Final = "enumerated_taxable_x"
NETTING_CATEGORY: Final = "synthetic_netting"
NETTING_CLASS: Final = "synthetic_enumerated_disposal"
EXEMPT_CATEGORY: Final = "exempt_securities"
EXEMPT_CLASS: Final = "ua_government_bond"

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
RULES = resolver.tax_rules_from_data_root(fixtures.DATA_ROOT, DECLARATIONS)
DECLARED = DECLARATIONS.instruments[TAXABLE]

PREMIUM: Final = 300.00
GAIN_ON_B: Final = 1_000.00
NETTED_BASE: Final = 700.00
NETTED_LIABILITY: Final = 105.00
BASE_WITHOUT_THE_PREMIUM: Final = 1_000.00
LIABILITY_WITHOUT_THE_PREMIUM: Final = 150.00
CARRIED: Final = 200.00

HORIZON = DateRange(start=date(2026, 1, 5), end=date(2026, 12, 31))
HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")


def _holding(*, on: date, paid: float) -> Holding:
    return Holding(
        owner_id="owner-1",
        instrument_id=TAXABLE,
        quantity=10.0,
        purchased_on=on,
        cost=Money(paid, UAH, prov.EMPTY),
    )


LOT_A = _holding(on=date(2026, 1, 5), paid=10_300.00)
"""The premium purchase: 10 units at 1 030.00, the quote
`tests/fixtures/data/access/fixtures.toml` declares for this fixture."""

LOT_B = _holding(on=date(2026, 1, 6), paid=9_000.00)
"""The same instrument a day later at a discount, so the year has a same-category gain to
net the premium's loss against. A day later because two lots opened on one date would share
a lot id, and FIFO would then have two acquisitions it could not tell apart."""


def _events(*lots: Holding) -> tuple[Event, ...]:
    """Both purchases and both schedules, in date order and renumbered as one stream."""
    produced: list[Event] = []
    for lot in lots:
        stream = ops_for(DECLARED.instrument_class).events(DECLARED, lot, HORIZON, HOLD_CASH, None)
        assert isinstance(stream, tuple), stream
        produced.extend(stream)
    ordered = sorted(produced, key=lambda event: (event.occurred_on, event.sequence))
    return tuple(replace(event, sequence=index + 1) for index, event in enumerate(ordered))


def _charges(
    state: engine.LedgerState, events: tuple[Event, ...], *, class_id: str
) -> tuple[TaxCharge, ...]:
    """One charge per disposal, through the production rule, on the signed realised gain.

    Only the disposals: the coupons are charged in a different category at a different rate
    and are asserted separately, so folding them in here would put two questions in one
    figure.
    """
    by_sequence = {event.sequence: event for event in events}
    built: list[TaxCharge] = []
    for disposal in state.disposals:
        charged = flat_rate.charge(
            by_sequence[disposal.sequence],
            DECLARATIONS.tax_classes[class_id],
            TaxContext(
                instrument_id=disposal.instrument_id,
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=disposal.realised_gain_base_ccy,
                charged_for_year=disposal.occurred_on.year,
            ),
        )
        assert isinstance(charged, TaxCharge), charged
        built.append(charged)
    return tuple(built)


def _year(*lots: Holding, jurisdiction: str, class_id: str) -> tax_year.AnnualStatement:
    """The 2026 statement for the category that class belongs to."""
    events = _events(*lots)
    state = engine.fold(events, base_currency=UAH, consumption_method="fifo")
    built = tax_year.statements(
        state,
        _charges(state, events, class_id=class_id),
        rules=RULES[jurisdiction],
        tax_classes=DECLARATIONS.tax_classes,
        filing=tax_years.filing(y2025=True, y2026=True),
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    (statement,) = [entry for entry in built if entry.tax_year == 2026]
    return statement


def _under(class_id: str) -> InstrumentDeclaration:
    """The fixture with both its income kinds taxed under one declared class.

    The two runs of SC-016 differ in the category their disposal class belongs to, and this
    is how: the schedule, the holdings and the horizon are the same objects.
    """
    return replace(
        DECLARED,
        tax_classes={
            TaxableEventKind.COUPON: class_id,
            TaxableEventKind.DISPOSAL_GAIN: class_id,
        },
    )


def _projected(lot: Holding) -> Projection:
    outcome = project.project(
        DECLARED,
        lot,
        HORIZON,
        HOLD_CASH,
        tax_classes=DECLARATIONS.tax_classes,
        assessment_rules=RULES["synthetic_fixture"],
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


class TestThePremiumIsReportedAsItsOwnFigure:
    """FR-025. Visible at purchase rather than surfacing only as a loss years later."""

    def test_it_is_what_was_paid_less_what_comes_back_as_principal(self) -> None:
        figure = _projected(LOT_A).at_purchase
        assert figure.paid.amount == 10_300.00
        assert figure.principal_returned.amount == 10_000.00
        assert is_close(figure.difference.amount, PREMIUM)

    def test_a_discount_is_the_same_figure_with_the_other_sign(self) -> None:
        assert is_close(_projected(LOT_B).at_purchase.difference.amount, -GAIN_ON_B)

    def test_a_purchase_at_face_reports_zero_rather_than_nothing(self) -> None:
        """A zero here says *par*. An absent figure would say nothing, and a reader would
        have to know that nothing meant par."""
        at_par = _projected(_holding(on=date(2026, 1, 5), paid=10_000.00)).at_purchase
        assert at_par.difference.amount == 0.0

    def test_it_names_the_category_treatment_that_governs_it(self) -> None:
        governed = _projected(LOT_A).at_purchase.governed_by
        assert isinstance(governed, GovernedBy), governed
        assert governed.category_id == NETTING_CATEGORY
        assert governed.treatment == "nets"

    def test_the_full_cost_is_the_lot_s_basis(self) -> None:
        """FR-024. Nothing is amortised, nothing imputed, and no part reclassified."""
        (disposal,) = _projected(LOT_A).ledger.disposals
        assert disposal.consumed_basis_base_ccy.amount == 10_300.00


class TestAPurchaseMadeAfterARepaymentOfPrincipal:
    """FR-025 as amended (2026-08-30): the difference is measured against what **this
    holding** gets back, not against the nominal face.

    The case the enumerated form exists for, and the one every other fixture hides: all
    four repay their whole face once, so face and remaining principal coincide and the wrong
    rule reports the right number. An amortising issue parts them.

    ```
    face 1 000.00 per unit, repaid 500.00 on 2026-06-05 and 500.00 on 2026-12-05
    bought 2026-08-01, after the first repayment, at 500.00 per unit -- the principal that
    is left, exactly. A break-even trade.

      what comes back      10 x 500.00  =  5 000.00
      paid                                 5 000.00
      difference                               0.00      par, and it says par

    measured against the nominal face it would read
      at_face              10 x 1 000.00 = 10 000.00
      difference                           -5 000.00     a discount of everything the
                                                         previous holder was already repaid
    ```
    """

    HALVES: Final = 500.00
    BOUGHT_ON: Final = date(2026, 8, 1)

    @staticmethod
    def _amortising() -> InstrumentDeclaration:
        """The fixture with its one repayment split into two, the first already
        made by the time this buyer arrives. Nothing else moves."""
        terms = DECLARED.terms
        assert isinstance(terms, EnumeratedTerms)
        repayment = next(
            payment for payment in terms.payments if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
        )
        halved = Money(
            TestAPurchaseMadeAfterARepaymentOfPrincipal.HALVES,
            UAH,
            repayment.amount.provenance,
        )
        payments = tuple(
            sorted(
                [payment for payment in terms.payments if payment is not repayment]
                + [
                    replace(repayment, on=date(2026, 6, 5), amount=halved),
                    replace(repayment, amount=halved),
                ],
                key=lambda payment: (payment.on, payment.pays.value),
            )
        )
        return replace(DECLARED, terms=replace(terms, payments=payments))

    def _bought_at(self, per_unit: float) -> PurchasePremium:
        outcome = project.project(
            self._amortising(),
            _holding(on=self.BOUGHT_ON, paid=per_unit * 10.0),
            replace(HORIZON, start=self.BOUGHT_ON),
            HOLD_CASH,
            tax_classes=DECLARATIONS.tax_classes,
            assessment_rules=RULES["synthetic_fixture"],
        )
        assert isinstance(outcome, Projection), outcome
        return outcome.at_purchase

    def test_what_comes_back_is_the_principal_still_to_be_repaid(self) -> None:
        assert self._bought_at(self.HALVES).principal_returned.amount == 5_000.00

    def test_paying_exactly_that_reports_par(self) -> None:
        """The assertion that fails on the nominal face: it reported a discount of
        5 000.00 -- a figure describing the previous holder's trade -- and named the tax
        treatment that governs it, inside the canonical digest."""
        assert self._bought_at(self.HALVES).difference.amount == 0.0

    def test_and_the_ledger_agrees_that_the_trade_broke_even(self) -> None:
        """The figure and the fold have to say the same thing, or one of them is wrong. A
        realised gain of zero beside a reported discount of 5 000.00 is the shape of the
        defect this pins."""
        outcome = project.project(
            self._amortising(),
            _holding(on=self.BOUGHT_ON, paid=self.HALVES * 10.0),
            replace(HORIZON, start=self.BOUGHT_ON),
            HOLD_CASH,
            tax_classes=DECLARATIONS.tax_classes,
            assessment_rules=RULES["synthetic_fixture"],
        )
        assert isinstance(outcome, Projection), outcome
        realised = sum(
            disposal.realised_gain_base_ccy.amount for disposal in outcome.ledger.disposals
        )
        assert is_close(realised, 0.0)
        assert is_close(outcome.at_purchase.difference.amount, realised)

    def test_a_premium_over_the_remaining_principal_is_still_a_premium(self) -> None:
        """The rule is not "always par": it measures against a different, correct base."""
        assert is_close(self._bought_at(self.HALVES + 30.0).difference.amount, 300.00)

    RESALE: Final = 995.00
    SOLD_ON: Final = date(2026, 9, 1)

    def test_a_sale_prices_what_is_left_and_leaves_what_was_repaid_alone(self) -> None:
        """015 FR-029 meeting an amortising schedule: the two halves are priced differently.

        ```
        bought 2026-01-05   10 units at 1 000.00                  = 10 000.00
        2026-06-05          500.00 per unit repaid, retiring      =      5 units
        sale 2026-09-01     the remaining 5 units at 995.00       =  4 975.00
                            plus the 5 000.00 already repaid      =  9 975.00
                            paid 10 000.00 -> premium             =     25.00
        ```

        Pricing all ten at the resale quote would report 9 950.00 and a premium of 50.00 --
        charging the spread on units nobody sold, which the issuer had already repaid at par.
        """
        outcome = project.project(
            self._amortising(),
            _holding(on=HORIZON.start, paid=1_000.00 * 10.0),
            replace(HORIZON, end=self.SOLD_ON),
            HOLD_CASH,
            tax_classes=DECLARATIONS.tax_classes,
            assessment_rules=RULES["synthetic_fixture"],
            early_exit=EarlyExit(
                price_per_unit=Money(self.RESALE, UAH, prov.EMPTY),
                # Quoted on the sale day: this example is about which UNITS a sale prices, and
                # a quotation carried across a coupon would move the per-unit figure too.
                observed_on=self.SOLD_ON,
                assumption=QuotationHolds(
                    id="test_quotation_holds",
                    is_assumption=True,
                    rationale="TEST FIXTURE -- the quoted resale price still holds at the exit.",
                ),
            ),
        )
        assert isinstance(outcome, Projection), outcome
        assert outcome.sold_early is not None
        assert outcome.sold_early.units == 5.0
        assert is_close(outcome.at_purchase.principal_returned.amount, 5_000.00 + 4_975.00)
        assert is_close(outcome.at_purchase.difference.amount, 25.00)

    def test_a_repayment_and_a_detachment_in_one_window_refuse_rather_than_mis_price(
        self,
    ) -> None:
        """The two per-unit conventions meeting, which is the case one quotation cannot serve.

        Buy 2026-01-05, and by the sale on 2026-08-01 the schedule has repaid 500.00 per unit
        (retiring five of the ten units) and paid a coupon of 50.00 (detaching from the
        quotation). The 50.00 is declared per unit **as declared**, while the 995.00 it would
        come out of now prices a unit that is half of what it was -- the subtraction would be
        too small by that ratio. Both mechanisms are right on their own; what is missing is a
        sale priced per tranche.
        """
        outcome = project.project(
            self._amortising(),
            _holding(on=HORIZON.start, paid=1_000.00 * 10.0),
            replace(HORIZON, end=date(2026, 8, 1)),
            HOLD_CASH,
            tax_classes=DECLARATIONS.tax_classes,
            assessment_rules=RULES["synthetic_fixture"],
            early_exit=EarlyExit(
                price_per_unit=Money(self.RESALE, UAH, prov.EMPTY),
                observed_on=HORIZON.start,
                assumption=QuotationHolds(
                    id="test_quotation_holds",
                    is_assumption=True,
                    rationale="TEST FIXTURE -- the quoted resale price still holds at the exit.",
                ),
            ),
        )
        assert isinstance(outcome, InconsistentTerms), outcome
        assert outcome.first_term == "instrument.schedule.payment"
        assert outcome.second_term == "access.resale_price.per_unit"
        assert "One quotation cannot price both" in outcome.reason

    def test_a_bond_that_repays_its_face_once_is_unaffected(self) -> None:
        """Why this was latent. For every declaration this repository ships, the amended
        rule and the old one give the same number -- which is exactly why the wrong rule
        passed every test on the branch that introduced it."""
        terms = DECLARED.terms
        assert isinstance(terms, EnumeratedTerms)
        figure = _projected(LOT_A).at_purchase
        assert figure.principal_returned.amount == terms.face_value.amount * 10.0


class TestUnderTheNettingCategory:
    """FR-026, and the case the specification refused to leave hypothetical."""

    def test_the_year_nets_the_premium_against_the_same_category_s_gain(self) -> None:
        assert is_close(
            _year(
                LOT_A,
                LOT_B,
                jurisdiction="synthetic_fixture",
                class_id=NETTING_CLASS,
            ).netted_base.amount,
            NETTED_BASE,
        )

    def test_the_liability_is_the_hand_computed_one(self) -> None:
        statement = _year(LOT_A, LOT_B, jurisdiction="synthetic_fixture", class_id=NETTING_CLASS)
        assert is_close(tax_year.liability_total(statement.liability).amount, NETTED_LIABILITY)

    def test_the_premium_reduces_the_base_by_exactly_itself(self) -> None:
        """The assertion FR-026 asks for, made as a difference between two runs so that the
        premium's effect is isolated from everything else in the year."""
        at_par = _holding(on=date(2026, 1, 5), paid=10_000.00)
        with_premium = _year(LOT_A, LOT_B, jurisdiction="synthetic_fixture", class_id=NETTING_CLASS)
        without = _year(
            at_par,
            LOT_B,
            jurisdiction="synthetic_fixture",
            class_id=NETTING_CLASS,
        )
        assert is_close(without.netted_base.amount, BASE_WITHOUT_THE_PREMIUM)
        assert is_close(without.netted_base.amount - with_premium.netted_base.amount, PREMIUM)
        assert is_close(
            tax_year.liability_total(without.liability).amount, LIABILITY_WITHOUT_THE_PREMIUM
        )

    def test_a_negative_year_carries_forward_instead_of_owing(self) -> None:
        """The other half of `nets`/`unlimited`: a premium larger than the year's gain
        leaves nothing owed and something carried."""
        smaller_gain = _holding(on=date(2026, 1, 6), paid=9_900.00)
        statement = _year(
            LOT_A,
            smaller_gain,
            jurisdiction="synthetic_fixture",
            class_id=NETTING_CLASS,
        )
        assert is_close(statement.netted_base.amount, -CARRIED)
        assert statement.liability.base.amount == 0.0
        assert statement.carryforward is not None
        assert is_close(statement.carryforward.created.amount, CARRIED)
        assert statement.carryforward.origins == ((2026, statement.carryforward.created),)


class TestUnderTheExemptCategory:
    """The two runs differ in the declared category and in nothing else.

    ⚙ **This class used to be structurally vacuous and is rewritten.** It built charges for
    the exempt class alone, and `tax_year.statements` emits one statement per category
    *present in the charges* — so *"every statement is the exempt category"* could not fail,
    and the liability assertion was determined by rates of 0.0 rather than by the treatment.
    All three assertions passed unchanged if `exempt_securities` had been declared
    `nets`/`unlimited`, which is the one thing they existed to distinguish.

    What tells the treatments apart is the **netted base**: `outside` leaves nothing to net,
    `nets` accumulates 700.00 from the same two lots. So that is what is asserted, and the
    same run is put through both category declarations so the difference is visible rather
    than described.
    """

    def test_the_year_owes_nothing(self) -> None:
        statement = _year(LOT_A, LOT_B, jurisdiction="ua", class_id=EXEMPT_CLASS)
        assert statement.category == EXEMPT_CATEGORY
        assert tax_year.liability_total(statement.liability).amount == 0.0

    def test_the_recorded_base_is_arithmetic_and_the_treatment_is_the_claim(self) -> None:
        """`netted_base` is **700.00 under the exempt category too**, and that is feature
        009's design rather than a leak: `core.tax.year` sums the charges for every
        treatment and says so -- *"what distinguishes the two treatments is not the
        arithmetic but the claim, and ``AnnualStatement.treatment`` carries it."*

        Asserted rather than assumed, because the obvious thing to write here is
        ``netted_base == 0`` and it is false. A test asserting it would have been red for
        the right reason and got itself "fixed" by weakening whichever half was easier.
        """
        exempt = _year(LOT_A, LOT_B, jurisdiction="ua", class_id=EXEMPT_CLASS)
        netting = _year(LOT_A, LOT_B, jurisdiction="synthetic_fixture", class_id=NETTING_CLASS)
        assert is_close(exempt.netted_base.amount, netting.netted_base.amount)
        assert exempt.treatment is tax_year.Treatment.OUTSIDE
        assert netting.treatment is tax_year.Treatment.NETS

    def test_the_two_treatments_would_not_pass_for_each_other(self) -> None:
        """The mutation the previous version of this class could not survive: every one of
        its assertions held whether `exempt_securities` was declared `outside`/`none` or
        `nets`/`unlimited`, which is the one distinction it existed to draw.

        What survives the zero rates is the **carryforward**. A liability comparison does
        not: an exempt class charges 0% and a `nets` category over 0% rates would owe
        nothing either, so a zero liability says nothing about the treatment. A loss that
        creates a carryforward under one declaration and none under the other does.
        """
        smaller_gain = _holding(on=date(2026, 1, 6), paid=9_900.00)
        exempt = _year(LOT_A, smaller_gain, jurisdiction="ua", class_id=EXEMPT_CLASS)
        netting = _year(
            LOT_A, smaller_gain, jurisdiction="synthetic_fixture", class_id=NETTING_CLASS
        )
        assert is_close(exempt.netted_base.amount, netting.netted_base.amount), (
            "the same two lots, so the arithmetic is the same and only the declared "
            "treatment differs -- which is what makes the next line a test of the treatment"
        )
        assert exempt.carryforward is None
        assert netting.carryforward is not None

    def test_nothing_carries_forward(self) -> None:
        """`carryforward = "none"`: an exempt loss buys no shield, which is the unwelcome
        half of the exemption and the half that has to be modelled.

        Asserted against the netting category's own carryforward on the same lots, so the
        claim is *this treatment does not carry* rather than *nothing carried today*.
        """
        smaller_gain = _holding(on=date(2026, 1, 6), paid=9_900.00)
        assert (
            _year(LOT_A, smaller_gain, jurisdiction="ua", class_id=EXEMPT_CLASS).carryforward
            is None
        )
        carried = _year(
            LOT_A, smaller_gain, jurisdiction="synthetic_fixture", class_id=NETTING_CLASS
        ).carryforward
        assert carried is not None
        assert is_close(carried.created.amount, CARRIED)

    def test_nothing_leaves_the_year_for_another_one_to_use(self) -> None:
        """SC-016's *"no other category's base moves by any amount"*, said in the only terms
        an annual statement can say it: a category's result reaches another year or another
        category **only** through a carryforward, and `outside`/`none` creates none.

        The previous version looped over the statements this run produced and found only the
        category it had built charges for -- true, and determined by the input.
        """
        smaller_gain = _holding(on=date(2026, 1, 6), paid=9_900.00)
        for lots in ((LOT_A, LOT_B), (LOT_A, smaller_gain)):
            statement = _year(*lots, jurisdiction="ua", class_id=EXEMPT_CLASS)
            assert statement.carryforward is None
            assert tax_year.liability_total(statement.liability).amount == 0.0

    def test_the_figure_names_that_treatment_instead(self) -> None:
        outcome = project.project(
            _under(EXEMPT_CLASS),
            LOT_A,
            HORIZON,
            HOLD_CASH,
            tax_classes=DECLARATIONS.tax_classes,
            assessment_rules=RULES["ua"],
        )
        assert isinstance(outcome, Projection), outcome
        governed = outcome.at_purchase.governed_by
        assert isinstance(governed, GovernedBy), governed
        assert (governed.category_id, governed.treatment) == (EXEMPT_CATEGORY, "outside")
        assert "buys no shield" in governed.reason
