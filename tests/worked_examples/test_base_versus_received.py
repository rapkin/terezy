"""The hryvnia the base implies, the hryvnia the sale produced, and the gap between them.

SC-009 and SC-014. The dollars on a ФОП account cannot be spent domestically; they are sold
for hryvnia through a declared channel, at a cost. The tax on them was fixed on the **credit**
date at the **official** rate. Two numbers, two dates, two rates, and neither is the other.

**This feature adds no mechanism to the sale.** The received figure below comes from
``routes.cost.cost_one`` over the **shipped** ``fop_usd_to_monobank_uah`` route and its
declared channel — the same call every other corridor is costed by, with no new leg kind, no
new channel kind and no new concept of compulsion. What this feature contributes is the tax
consequence of the sale, which is precisely that there is none.

The only synthetic thing here is a stream that lands on the ФОП account in dollars, so that
the shipped route has something to carry: the owner's real monthly figure is unstated
(``SIMULATOR_SPEC.md`` §11 item 3), and the official rate is invented because no rate value
may originate from an implementer's memory.
"""

from __future__ import annotations

import dataclasses
import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results.ramp import RampCost
from terezy.core.routes import cost
from terezy.core.routes.path import FundingPath
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.core.tax import scheme as schemes
from terezy.data.declarations import resolver
from tests import official_rates, source_scan

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SCHEME_MODULE = REPO_ROOT / "src" / "terezy" / "core" / "tax" / "scheme.py"

SALE_ROUTE = "fop_usd_to_monobank_uah"
CREDIT_DATE = date(2027, 3, 15)
SALE_DATE = date(2027, 3, 20)
AS_OF = date(2027, 3, 20)

SOLD = 1_000.00
"""Dollars sold. SYNTHETIC -- the owner's real monthly figure is unstated (§11 item 3)."""

OFFICIAL_RATE = 42.50
"""SYNTHETIC hryvnia per dollar on the CREDIT date. Not a rate the NBU published."""

BASE = 42_500.00
"""1 000.00 USD x 42.50 = 42 500.00 UAH -- what the law says the income was."""

RECEIVED = 41_580.00
"""What the shipped sale produces, from the shipped channel's own declared numbers:
reference 42.00 UAH per USD, sell side 100 bps below it, so 42.00 x (1 - 0.0100) = 41.58,
and 1 000.00 USD x 41.58 = 41 580.00 UAH. Both legs declare a zero fee."""

DIFFERENCE = 920.00
"""42 500.00 - 41 580.00 = 920.00 UAH. Signed, and outside the taxable base."""

FOP_STREAM = IncomeStream(
    id="synthetic_fop_usd",
    owner_id="owner-001",
    amount=Money(SOLD, Currency.USD, prov.EMPTY),
    cadence="monthly",
    arrives_at="fop",
    credited_to="fop",
    indexation=Indexation(policy="none", rate=None),
    tax_scheme="ua_fop_group_3_non_vat",
)
"""SYNTHETIC FIXTURE -- a stream landing on the ФОП account, so the shipped sale route has
something to carry. The owner's own ``contract_usd`` is *routed* through Deel, so it cannot
fund this leg; that is exactly the routing-origin fact FR-024a keeps apart from the crediting
destination, and it is why the fixture exists rather than the shipped stream being reused."""


def _received(*, root: Path = DATA_ROOT) -> Money:
    """What the declared sale actually produces, through the existing costing path."""
    ramp = resolver.ramp_from_data_root(root, base_currency=Currency.UAH)
    outcome = cost.cost_one(
        FundingPath(destination_id="monobank_uah", stream_id=FOP_STREAM.id, route_id=SALE_ROUTE),
        Money(SOLD, Currency.USD, prov.EMPTY),
        routes=ramp.routes,
        channels=ramp.channels,
        streams={**ramp.streams, FOP_STREAM.id: FOP_STREAM},
        kinds=ramp.kinds,
        on_date=SALE_DATE,
        as_of=AS_OF,
        spendable=frozenset(),
    )
    assert isinstance(outcome, RampCost), outcome
    return outcome.one_way.arrived


def _base(*, rate: float = OFFICIAL_RATE, root: Path = DATA_ROOT) -> Money:
    """The taxable base: the credited dollars at the official rate on the credit date.

    The series is synthetic and the shipped one is not consulted, because what is asserted
    here is the **arithmetic**: a worked example states the values it works from, so a reader
    can check the product on paper without opening a data file. A base struck against the
    National Bank's own declared rates is ``tests/worked_examples/test_nbu_official_rate_base.py``;
    that the jurisdiction's own series is the one resolved for a run is asserted in
    ``tests/contract/test_crediting_destination_loading.py``.
    """
    declared = resolver.schemes_from_data_root(root, base_currency=Currency.UAH)
    assert declared.official_rates["ua"] is not None
    charge = schemes.charge_income(
        declared.schemes["ua_fop_group_3_non_vat"],
        Money(SOLD, Currency.USD, prov.EMPTY),
        on_date=CREDIT_DATE,
        series=official_rates.series([(CREDIT_DATE, rate)]),
    )
    assert isinstance(charge, schemes.SchemeCharge), charge
    return charge.base


class TestTwoFiguresAndNeitherIsTheOther:
    def test_the_sale_produces_the_hand_computed_hryvnia(self) -> None:
        assert_money_close(_received(), Money(RECEIVED, Currency.UAH, prov.EMPTY))

    def test_the_base_is_the_hand_computed_hryvnia_at_the_official_rate(self) -> None:
        assert_money_close(_base(), Money(BASE, Currency.UAH, prov.EMPTY))

    def test_they_are_reported_separately_and_are_not_equal_by_construction(self) -> None:
        gap = schemes.base_versus_received(_base(), _received())
        assert gap.base.amount != gap.received.amount
        assert_money_close(gap.base, Money(BASE, Currency.UAH, prov.EMPTY))
        assert_money_close(gap.received, Money(RECEIVED, Currency.UAH, prov.EMPTY))

    def test_the_difference_is_signed_and_labelled_as_outside_the_base(self) -> None:
        """FR-013: the exposure points either way, and an absolute value would hide which."""
        gap = schemes.base_versus_received(_base(), _received())
        assert_money_close(gap.difference, Money(DIFFERENCE, Currency.UAH, prov.EMPTY))
        assert "Not part of the taxable base" in gap.outside_the_base

    def test_the_difference_reverses_sign_when_the_official_rate_falls_below_the_market(
        self,
    ) -> None:
        #   base = 1 000.00 USD x 41.00 = 41 000.00 UAH
        #   gap  = 41 000.00 - 41 580.00 = -580.00 UAH
        gap = schemes.base_versus_received(_base(rate=41.00), _received())
        assert_money_close(gap.difference, Money(-580.00, Currency.UAH, prov.EMPTY))


class TestTheSaleMovesNoTaxFigure:
    def test_a_sale_at_a_different_market_rate_leaves_the_base_bit_identical(
        self, tmp_path: Path
    ) -> None:
        """SC-009's middle clause, and the market rate is actually moved.

        The sale channel's declared reference is rewritten in a scratch copy of the data root
        -- which changes what the sale produces -- and the base is compared bit-for-bit
        against the run that used the shipped one. Bit-for-bit rather than within the
        tolerance: this is not an arithmetic agreement, it is the claim that the sale is not
        an input to the base at all.
        """
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        channels = root / "channels" / "uah_usd.toml"
        text = channels.read_text(encoding="utf-8")
        assert "reference_rate = 42.0" in text
        channels.write_text(text.replace("reference_rate = 42.0", "reference_rate = 37.0"), "utf-8")

        moved = _received(root=root)
        assert moved.amount != _received().amount

        # Both bases computed, one from each root: the claim is that the run whose channel
        # moved produces the same base as the run whose channel did not.
        assert _base(root=root).amount.hex() == _base().amount.hex()
        assert _base(root=root).amount.hex() == Money(BASE, Currency.UAH, prov.EMPTY).amount.hex()

    def test_the_gap_is_reported_beside_the_two_figures_and_never_applied_to_either(
        self,
    ) -> None:
        """Netting them would assert a deduction nobody cited (FR-014).

        Structural, because the arithmetic version of this claim is an algebraic restatement
        of the subtraction and cannot fail. What can fail is a record that grew somewhere to
        put a netted figure, or a base that arrived already reduced.
        """
        gap = schemes.base_versus_received(_base(), _received())
        names = {field.name for field in dataclasses.fields(schemes.BaseVersusReceived)}
        assert names == {"base", "received", "difference", "outside_the_base"}
        assert not names & {"net", "netted", "deduction", "allowance", "adjusted"}
        # The base reported beside the gap is the base struck on its own, untouched by it.
        assert gap.base.amount.hex() == _base().amount.hex()


class TestTheSaleUsesOnlyMachineryThatAlreadyExisted:
    """SC-014, asserted against the shipped declaration rather than described."""

    @staticmethod
    def _route() -> object:
        ramp = resolver.ramp_from_data_root(DATA_ROOT, base_currency=Currency.UAH)
        return ramp.routes[SALE_ROUTE]

    def test_it_declares_only_leg_kinds_the_registry_already_had(self) -> None:
        route = self._route()
        kinds = {leg.kind for leg in route.legs}  # type: ignore[attr-defined]
        assert kinds <= {"fx", "transfer", "withdrawal", "deposit"}

    def test_it_converts_through_a_declared_channel_at_a_declared_venue(self) -> None:
        route = self._route()
        converting = [leg for leg in route.legs if leg.kind == "fx"]  # type: ignore[attr-defined]
        assert [leg.channel for leg in converting] == ["bank_fop"]
        assert {leg.from_venue for leg in converting} == {"fop"}

    def test_the_costing_call_is_the_one_every_other_corridor_uses(self) -> None:
        """There is no second costing function to have used instead."""
        assert cost.cost_one.__module__ == "terezy.core.routes.cost"
        assert [name for name in dir(cost) if name.startswith("cost_")] == [
            "cost_exit",
            "cost_one",
        ]


class TestTheBaseIsNeverStruckFromTheChannel:
    """011 FR-013 and SC-017a's second half, at the one place both figures are in hand."""

    def test_the_two_rates_are_different_numbers_on_different_dates(self) -> None:
        ramp = resolver.ramp_from_data_root(DATA_ROOT, base_currency=Currency.UAH)
        assert ramp.channels["bank_fop"].reference_rate != OFFICIAL_RATE
        assert CREDIT_DATE != SALE_DATE

    def test_the_scheme_module_reads_no_channel_rate_and_imports_no_route(self) -> None:
        """The value-level half of ``no-tax-base-from-a-channel``, over executable source.

        The import-linter contract forbids the *import*; this forbids the *read*, which is
        the thing that would actually put a market rate in a tax base. Asserted over stripped
        source, so the word appearing in a sentence about why it may not appear does not
        count — which is exactly what happens two functions above.
        """
        executable = source_scan.executable_source(SCHEME_MODULE)
        assert "reference_rate" not in executable
        assert "terezy.core.routes" not in executable
        # Falsifiable: the scan does see the read where the read is code.
        assert "reference_rate" in source_scan.strip_prose("x = channel.reference_rate\n")
        assert "reference_rate" not in source_scan.strip_prose('"""never a reference_rate."""\n')


@pytest.mark.parametrize("rate", [41.00, 42.00, 43.50])
def test_the_base_moves_only_with_the_official_rate(rate: float) -> None:
    """One credited amount, three declared official rates, three bases, one received figure."""
    assert_money_close(_base(rate=rate), Money(SOLD * rate, Currency.UAH, prov.EMPTY))
    assert_money_close(_received(), Money(RECEIVED, Currency.UAH, prov.EMPTY))
