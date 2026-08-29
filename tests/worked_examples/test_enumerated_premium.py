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

from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.instruments.registry import ops_for
from terezy.core.ledger import engine
from terezy.core.ledger.events import Event
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import GovernedBy, Projection
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
"""The premium purchase: 10 units at 1 030.00, the quote `data/access/instruments.toml`
declares for this fixture."""

LOT_B = _holding(on=date(2026, 1, 6), paid=9_000.00)
"""The same instrument a day later at a discount, so the year has a same-category gain to
net the premium's loss against. A day later because two lots opened on one date would share
a lot id, and FIFO would then have two acquisitions it could not tell apart."""


def _events(*lots: Holding) -> tuple[Event, ...]:
    """Both purchases and both schedules, in date order and renumbered as one stream."""
    produced: list[Event] = []
    for lot in lots:
        stream = ops_for(DECLARED.instrument_class).events(DECLARED, lot, HORIZON, HOLD_CASH)
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

    def test_it_is_what_was_paid_less_face_times_quantity(self) -> None:
        figure = _projected(LOT_A).at_purchase
        assert figure.paid.amount == 10_300.00
        assert figure.at_face.amount == 10_000.00
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


class TestUnderTheNettingCategory:
    """FR-026, and the case the specification refused to leave hypothetical."""

    def test_the_year_nets_the_premium_against_the_same_category_s_gain(self) -> None:
        assert is_close(
            _year(
                LOT_A,
                LOT_B,
                jurisdiction="synthetic_fixture",
                class_id="synthetic_enumerated_disposal",
            ).netted_base.amount,
            NETTED_BASE,
        )

    def test_the_liability_is_the_hand_computed_one(self) -> None:
        statement = _year(
            LOT_A, LOT_B, jurisdiction="synthetic_fixture", class_id="synthetic_enumerated_disposal"
        )
        assert is_close(tax_year.liability_total(statement.liability).amount, NETTED_LIABILITY)

    def test_the_premium_reduces_the_base_by_exactly_itself(self) -> None:
        """The assertion FR-026 asks for, made as a difference between two runs so that the
        premium's effect is isolated from everything else in the year."""
        at_par = _holding(on=date(2026, 1, 5), paid=10_000.00)
        with_premium = _year(
            LOT_A, LOT_B, jurisdiction="synthetic_fixture", class_id="synthetic_enumerated_disposal"
        )
        without = _year(
            at_par,
            LOT_B,
            jurisdiction="synthetic_fixture",
            class_id="synthetic_enumerated_disposal",
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
            class_id="synthetic_enumerated_disposal",
        )
        assert is_close(statement.netted_base.amount, -CARRIED)
        assert statement.liability.base.amount == 0.0
        assert statement.carryforward is not None
        assert is_close(statement.carryforward.created.amount, CARRIED)
        assert statement.carryforward.origins == ((2026, statement.carryforward.created),)


class TestUnderTheExemptCategory:
    """The two runs differ in the declared category and in nothing else."""

    @staticmethod
    def _exempt(declared: InstrumentDeclaration) -> InstrumentDeclaration:
        return replace(
            declared,
            tax_classes={
                TaxableEventKind.COUPON: EXEMPT_CLASS,
                TaxableEventKind.DISPOSAL_GAIN: EXEMPT_CLASS,
            },
        )

    def test_the_year_owes_nothing(self) -> None:
        statement = _year(LOT_A, LOT_B, jurisdiction="ua", class_id=EXEMPT_CLASS)
        assert statement.category == EXEMPT_CATEGORY
        assert tax_year.liability_total(statement.liability).amount == 0.0

    def test_nothing_carries_forward(self) -> None:
        """`carryforward = "none"`: an exempt loss buys no shield, which is the unwelcome
        half of the exemption and the half that has to be modelled."""
        statement = _year(LOT_A, LOT_B, jurisdiction="ua", class_id=EXEMPT_CLASS)
        assert statement.carryforward is None

    def test_no_other_category_s_base_moves_by_any_amount(self) -> None:
        """`outside` means outside on both sides. The premium reduces nothing anywhere."""
        events = _events(LOT_A, LOT_B)
        state = engine.fold(events, base_currency=UAH, consumption_method="fifo")
        built = tax_year.statements(
            state,
            _charges(state, events, class_id=EXEMPT_CLASS),
            rules=RULES["ua"],
            tax_classes=DECLARATIONS.tax_classes,
            filing=tax_years.filing(y2025=True, y2026=True),
            switches=tax_years.positions(),
        )
        assert isinstance(built, tuple), built
        assert {statement.category for statement in built} == {EXEMPT_CATEGORY}
        assert all(
            tax_year.liability_total(statement.liability).amount == 0.0 for statement in built
        )

    def test_the_figure_names_that_treatment_instead(self) -> None:
        outcome = project.project(
            self._exempt(DECLARED),
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
