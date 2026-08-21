"""``flat_rate`` applies whatever the class carries -- including nothing, and including a lot.

The D1 worked example covers the case this project cares most about: an exempt class, five
zero charges, a total of exactly zero. That case alone cannot tell a correct rule from a
rule that returns zero unconditionally, which is why this module exists. Here the same
function is handed **invented non-zero rates** and must apply them, keep PIT and the levy
on separate lines, and refuse an income kind its class does not cover.

The rates below are fixtures and are **not** a claim about Ukrainian tax law. No legal or
tax value in this project may originate from an implementer's or an agent's memory
(Principle I); real rates arrive as cited data in ``data/tax/``. What is being tested is
that the rule reads its rates from the class it is given, which is exactly the property
that makes the real rates safe to be data.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import UnresolvedTaxClass
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax import flat_rate, registry
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from tests import synthetic

UAH = Currency.UAH

COUPON_SOURCE = SourceRef(
    id="test:coupon",
    citation="SYNTHETIC -- the amount being taxed in these tests.",
    retrieved_on=date(2026, 8, 21),
    verified_on=date(2026, 8, 21),
)

BASE = Money(1000.0, UAH, prov.of([COUPON_SOURCE]))

EVENT = Event(
    sequence=7,
    occurred_on=date(2026, 7, 15),
    kind=EventKind.COUPON,
    amount=BASE,
    owner_id="owner-1",
    caused_by=CausationRef(
        kind=CausationKind.INSTRUMENT_TERM,
        id="fixture:coupon_rate",
        detail="a coupon, for something to charge against",
    ),
    lot_ref=None,
    quantity=None,
    allocated_to=None,
)


def _charge(tax_class: TaxClass, kind: TaxableEventKind = TaxableEventKind.COUPON) -> object:
    return flat_rate.charge(
        EVENT,
        tax_class,
        TaxContext(
            instrument_id="ovdp_synthetic_test",
            taxable_event=kind,
            taxable_base=BASE,
            charged_for_year=2026,
        ),
    )


class TestTheRatesComeFromTheClass:
    """No rate literal in the rule: whatever the class declares is what is charged."""

    def test_the_declared_rates_are_applied_to_the_stated_base(self) -> None:
        # 1 000.00 x 18%  -> 180.00 of PIT
        # 1 000.00 x 1.5% ->  15.00 of levy
        # and 180.00 + 15.00 -> 195.00 charged in total
        charge = _charge(synthetic.TAXED_CLASS)
        assert isinstance(charge, TaxCharge)
        assert_money_close(charge.pit, Money(180.0, UAH, prov.EMPTY))
        assert_money_close(charge.levy, Money(15.0, UAH, prov.EMPTY))
        assert_money_close(charge.total, Money(195.0, UAH, prov.EMPTY))
        assert_money_close(charge.taxable_base, BASE)

    def test_the_same_function_charges_nothing_under_an_exempt_class(self) -> None:
        # The exemption is data, not a branch: the same code path, a class of zeroes.
        charge = _charge(synthetic.EXEMPT_CLASS)
        assert isinstance(charge, TaxCharge)
        assert charge.total.amount == 0.0

    def test_pit_and_levy_are_separate_lines_on_their_own_bases(self) -> None:
        # Not one blended 19.5% rate. A foreign withholding credit applies against PIT
        # and not against the levy, and that case is unrepresentable once the two are
        # added together at source -- so the two lines exist now, while nothing needs
        # them, for the same reason currency tagging does.
        charge = _charge(synthetic.TAXED_CLASS)
        assert isinstance(charge, TaxCharge)
        assert is_close(charge.pit.amount, BASE.amount * synthetic.TAXED_CLASS.pit_rate)
        assert is_close(charge.levy.amount, BASE.amount * synthetic.TAXED_CLASS.levy_rate)
        assert charge.pit.amount != charge.levy.amount

    def test_the_charge_records_the_event_it_was_charged_on(self) -> None:
        # C6: a tax figure resolves to its event *and* its rule. Stored, not inferred
        # from date adjacency.
        charge = _charge(synthetic.TAXED_CLASS)
        assert isinstance(charge, TaxCharge)
        assert charge.event_sequence == EVENT.sequence
        assert charge.tax_class_id == synthetic.TAXED_CLASS.id
        assert charge.charged_for_year == 2026


class TestProvenance:
    """Every line cites both the amount it taxed and the class that taxed it."""

    def test_a_zero_charge_still_cites_the_exemption_that_produced_it(self) -> None:
        # The evidence that the exemption was applied. A zero with no citation is
        # indistinguishable from a rule that never ran.
        charge = _charge(synthetic.EXEMPT_CLASS)
        assert isinstance(charge, TaxCharge)
        assert synthetic.EXEMPTION_SOURCE in charge.pit.provenance.sources
        assert synthetic.EXEMPTION_SOURCE in charge.levy.provenance.sources
        assert COUPON_SOURCE in charge.pit.provenance.sources

    def test_an_unverified_class_marks_the_charge_it_produced(self) -> None:
        # FR-015 through the tax rule: the exemption fixture has no verification date,
        # so the charge derived from it is marked even though the base is verified.
        assert not prov.is_unverified(BASE.provenance)
        charge = _charge(synthetic.EXEMPT_CLASS)
        assert isinstance(charge, TaxCharge)
        assert prov.is_unverified(charge.provenance)
        assert prov.is_unverified(charge.total.provenance)


class TestRefusal:
    """A class that does not cover the income refuses; it does not charge zero."""

    def test_an_income_kind_outside_applies_to_is_refused(self) -> None:
        # "This rule does not apply here" and "this rule charged nothing" are opposite
        # claims about the money, and only the second one is cited. Collapsing the first
        # into the second is the dangerous default the whole interface is shaped around.
        narrow = TaxClass(
            id="coupons_only",
            applies_to=frozenset({TaxableEventKind.COUPON}),
            pit_rate=0.18,
            levy_rate=0.015,
            provenance=prov.of([synthetic.TAXED_SOURCE]),
        )
        outcome = _charge(narrow, kind=TaxableEventKind.DISPOSAL_GAIN)
        assert isinstance(outcome, UnresolvedTaxClass)
        assert outcome.tax_class_id == "coupons_only"
        assert outcome.instrument_id == "ovdp_synthetic_test"
        assert "disposal_gain" in outcome.reason

    def test_a_negative_base_yields_a_negative_charge_rather_than_a_clamp(self) -> None:
        # A realised loss times a declared rate. Whether the loss is actually creditable
        # is a loss-offset rule this feature does not model, and the honest way to say so
        # is a visible line computed as declared -- not a zero that quietly asserts an
        # answer. Clamping here would be the silent clamp the constitution puts in its
        # top severity class.
        loss = Money(-500.0, UAH, prov.of([COUPON_SOURCE]))
        outcome = flat_rate.charge(
            EVENT,
            synthetic.TAXED_CLASS,
            TaxContext(
                instrument_id="ovdp_synthetic_test",
                taxable_event=TaxableEventKind.COUPON,
                taxable_base=loss,
                charged_for_year=2026,
            ),
        )
        assert isinstance(outcome, TaxCharge)
        assert outcome.pit.amount < 0.0
        assert is_close(outcome.pit.amount, -90.0)  # -500.00 x 18%


class TestTheRegistry:
    """Dispatch is a mapping of functions, with no default rule."""

    def test_the_flat_rate_ops_are_reachable_by_their_declared_name(self) -> None:
        assert registry.ops_for(registry.FLAT_RATE) is flat_rate.OPS

    def test_an_unknown_rule_name_fails_naming_what_is_known(self) -> None:
        # Never a fallback: treating an unrecognised rule as "no tax" is the most
        # expensive silent default available in this domain.
        with pytest.raises(KeyError, match="unknown tax rule"):
            registry.ops_for("rule_nobody_wrote")


class TestTheDifferenceTaxMakes:
    """FR-005: the contractual yield and the after-tax return are genuinely two figures."""

    def test_a_taxed_holding_returns_less_than_its_contractual_yield(self) -> None:
        # Under the exemption the two coincide, which is why they must also be checked on
        # a taxed holding: code that had only ever seen them equal could have stored one
        # and reported it twice.
        outcome = project.project(
            synthetic.declaration(
                tax_classes={
                    TaxableEventKind.COUPON: synthetic.TAXED_CLASS.id,
                    TaxableEventKind.DISPOSAL_GAIN: synthetic.TAXED_CLASS.id,
                }
            ),
            synthetic.holding(),
            synthetic.horizon(),
            synthetic.assumptions(),
            tax_classes=synthetic.TAX_PACK,
        )
        assert isinstance(outcome, Projection)
        hurdle = outcome.hurdle
        assert hurdle.nominal_cash_flow_return.value < hurdle.nominal_ytm.value
        # 19.5% of every coupon, and nothing on the redemption because a bond redeemed at
        # par realises no gain: 3 100.00 of coupons x 0.195 = 604.50.
        assert is_close(hurdle.total_tax.amount, 3100.0 * 0.195)

    def test_the_tax_lines_appear_on_the_rows_they_were_charged_on(self) -> None:
        outcome = project.project(
            synthetic.declaration(
                tax_classes={
                    TaxableEventKind.COUPON: synthetic.TAXED_CLASS.id,
                    TaxableEventKind.DISPOSAL_GAIN: synthetic.TAXED_CLASS.id,
                }
            ),
            synthetic.holding(),
            synthetic.horizon(),
            synthetic.assumptions(),
            tax_classes=synthetic.TAX_PACK,
        )
        assert isinstance(outcome, Projection)
        coupons = [row for row in outcome.schedule.rows if row.kind is EventKind.COUPON]
        for row in coupons:
            assert is_close(row.tax.amount, row.gross.amount * 0.195)
            assert is_close(row.net.amount, row.gross.amount - row.tax.amount)
