"""E5 and FR-015 -- the unverified mark reaches every figure, and drops from none.

*"A value with an empty verification date MUST be marked as unverified, and every figure
computed from it MUST carry that mark. A transform that drops the mark is a defect of the
highest severity"* (FR-015). The constitution says the same thing twice: Principle I calls
a derived figure that loses its parent's mark a defect, and the Engineering Standards put
lost provenance in the top severity class alongside wrong numbers.

This is the compliance test for that claim. The yield of the issue under test has an empty
``verified_on`` -- which is the honest state of the real OVDP terms
(``SIMULATOR_SPEC.md`` §11 item 2) and not a contrivance -- and every figure downstream is
checked for the mark: the schedule, every tax line, ``total_tax``, and both return
figures.

**Why the check is a walk and not a list of spot assertions.** SC-005 is written as *"100%
of figures derived from it carry the unverified mark, and no derived figure appears
unmarked"*, which is a claim about **every** amount in the result rather than about the
handful a test author remembered. :func:`_amounts` therefore enumerates every ``Money``
reachable in a projection -- events, balances, lots, positions, disposals, schedule rows,
charges and the headline figure -- and the first test asserts over all of them. A spot check
would go stale the moment a new figure is added; a walk fails until the new figure is
either marked or explicitly listed as one of the enumerated exceptions.

**The two legitimate exceptions**, both stated rather than tolerated:

* A **zero resting on no source** -- ``money.zero`` on a schedule row where no tax rule
  ran. Its provenance is empty because nothing was observed, not because a mark was
  dropped, and ``provenance.EMPTY`` is deliberately *not* unverified (a sum of nothing
  rests on nothing). Every such amount in the result is checked to be exactly zero, so an
  unmarked non-zero figure cannot hide among them.
* Nothing else. In particular the purchase, whose amount comes from the owner's own stated
  cost, carries that statement's own source here so that it is marked like everything
  else.

**Both construction paths are checked.** The hand-built records of ``tests.synthetic``
prove the *engine* propagates the mark; the declarations loaded from ``data/`` prove the
*loader* attaches a real one, with its own file-and-table source ids, and that nothing
between the file and the figure launders it. The engine is the same in both cases and the
provenance is not, which is exactly why one path cannot stand in for the other.

**And the mark is proved falsifiable.** ``TestTheMarkTracksTheDataAndNotTheCode`` runs the
identical projection with every source verified and asserts that *nothing* is marked. A
mark that is always on carries no information, and it is the failure mode a propagation
test cannot otherwise see -- it would pass just as green.

Tracked as **E5** in ``docs/REQUIRED_TESTS.md``. Closes FR-015 and SC-005.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from terezy.core.inflation import series as cpi_series
from terezy.core.instruments.fund import ExchangeRateAssumption
from terezy.core.instruments.interface import (
    BondTerms,
    DateRange,
    Holding,
    InstrumentConstraints,
    InstrumentDeclaration,
)
from terezy.core.ledger import engine, lots
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.rates import NominalRate, RealRate
from terezy.core.results import fund as fund_results
from terezy.core.results import hurdle, project
from terezy.core.results import tax_year as settlement
from terezy.core.results.fund import FundAssumptions, FundProjection
from terezy.core.results.project import Projection
from terezy.core.tax import flat_rate
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass, TaxContext
from terezy.data.declarations import loader, resolver
from tests import cpi_fixtures, synthetic, tax_years

pytestmark = pytest.mark.contract

UAH = Currency.UAH

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
"""The curated declarations, read through the loader like any other run."""

KINDS_FILE = DATA_ROOT / "observation_kinds.toml"
"""Where the staleness thresholds are declared. Read, never assumed."""

ISSUE_A = "ovdp_synthetic_a"
"""The synthetic issue whose terms are unverified because they are invented."""

LOADED_TERMS_SOURCE_ID = f"instruments/{ISSUE_A}.toml#instrument.terms"
"""The loader's own id for the yield: file and table, not merely a citation string.

Asserted literally, because the *shape* of the id is what makes a marked figure traceable
back to the line of the file that declared it rather than only to a URL.
"""

LOADED_EXEMPTION_SOURCE_ID = "tax/ua.toml#jurisdiction.tax_class[ua_government_bond].rate[0]"
"""The loader's id for the exemption -- the zero whose citation matters most."""


# --- the two projections under test ---------------------------------------------------


def _from_code(*, verified: bool) -> Projection:
    """The hand-built records, with every source either unverified or verified.

    All four sources move together. That is deliberate: the interesting question is not
    which of them is unverified but whether *any* unverified input marks the whole result,
    and ``verified=True`` gives the falsifiability check a state where nothing is marked.
    """
    when = date(2026, 8, 21) if verified else None
    terms_source = replace(synthetic.TERMS_SOURCE, verified_on=when)
    terms_provenance = prov.of([terms_source])
    constraints_provenance = prov.of([replace(synthetic.CONSTRAINTS_SOURCE, verified_on=when)])
    exemption_provenance = prov.of([replace(synthetic.EXEMPTION_SOURCE, verified_on=when)])
    purchase_provenance = prov.of([replace(synthetic.PURCHASE_SOURCE, verified_on=when)])

    terms: BondTerms = synthetic.terms(
        face_value=Money(1000.0, UAH, terms_provenance),
        provenance=terms_provenance,
    )
    constraints: InstrumentConstraints = synthetic.constraints(
        min_ticket=Money(1000.0, UAH, constraints_provenance),
        provenance=constraints_provenance,
    )
    exempt_class = TaxClass(
        id=synthetic.EXEMPT_CLASS.id,
        applies_to=synthetic.EXEMPT_CLASS.applies_to,
        rates=tuple(
            replace(entry, provenance=exemption_provenance)
            for entry in synthetic.EXEMPT_CLASS.rates
        ),
    )
    declaration: InstrumentDeclaration = synthetic.declaration(
        terms=terms,
        constraints=constraints,
    )
    holding: Holding = synthetic.holding(
        cost=Money(10_000.0, UAH, purchase_provenance),
    )
    return _project(
        declaration,
        holding,
        tax_classes={exempt_class.id: exempt_class},
    )


# ⚙ This run projects `ovdp_synthetic_a`, whose first *taxable* event is its 2026-07-15
# coupon -- fifteen days after the earliest entry the `ua_government_bond` exemption's
# citation reaches. That dependency is asserted, once, in
# `tests/contract/test_declaration_loading.py::TestTheShippedRegistryRefusesAnUncoveredEvent`.
def _from_data() -> Projection:
    """The same purchase, from the declaration files, through the loader.

    Every ``verified_on`` in ``data/`` is empty, so this path is the unverified one by fact
    rather than by construction -- there is no verified variant of it to build, and
    inventing one by editing a data file would falsify the citation it carries.
    """
    declarations = resolver.from_data_root(DATA_ROOT)
    declaration = declarations.instruments[ISSUE_A]
    holding = Holding(
        owner_id="owner-1",
        instrument_id=ISSUE_A,
        quantity=10.0,
        purchased_on=declaration.terms.issue_date,
        cost=Money(10_000.0, UAH, prov.of([_OWNER_STATED_COST])),
    )
    return _project(declaration, holding, tax_classes=declarations.tax_classes)


_OWNER_STATED_COST = SourceRef(
    id="owner:purchase:ovdp_synthetic_a",
    citation="Owner-stated purchase: 10 units at par.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)
"""The purchase's own source. Unverified, like everything else in this run.

Given a source at all rather than ``provenance.EMPTY`` so that the walk below can hold
every non-zero amount in the result to the same standard: an amount with no source is
indistinguishable from an amount whose source was dropped, and this test exists to tell
those apart.
"""


def _project(
    declaration: InstrumentDeclaration,
    holding: Holding,
    *,
    tax_classes: Mapping[str, TaxClass],
) -> Projection:
    outcome = project.project(
        declaration,
        holding,
        synthetic.horizon(start=holding.purchased_on),
        synthetic.assumptions(),
        tax_classes=tax_classes,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


PATHS = {"hand-built records": _from_code(verified=False), "loaded declarations": _from_data()}
"""The two construction paths, built once and shared.

Built at import time rather than per test because a ``Projection`` is an immutable value:
there is nothing for one test to do to it that another could observe.
"""


# --- the walk -------------------------------------------------------------------------


def _amounts(result: Projection) -> Iterator[tuple[str, Money]]:
    """Every ``Money`` in a projection, each labelled with where it was found.

    The label is what makes a failure actionable: "an unmarked figure exists somewhere" is
    not a report anybody can act on, and the point of provenance is to be able to name the
    figure and the source behind it.

    Written as an explicit walk rather than a reflective sweep over dataclass fields. A
    reflective version would keep working when a new record is added and would therefore
    silently *stop checking* the thing it was pointed at, since nobody would notice the new
    field was never reached. This one has to be edited, and the edit is where a reviewer
    asks whether the new figure carries its mark.
    """
    for event in result.ledger.applied:
        yield f"event {event.sequence} ({event.kind.value}).amount", event.amount

    for currency, balance in result.ledger.accounts.items():
        where = f"balance[{currency.value}]"
        yield f"{where}.inflows", balance.inflows
        yield f"{where}.outflows", balance.outflows
        yield f"{where}.balance", balance.balance

    for instrument_id, position in result.ledger.positions.items():
        where = f"position[{instrument_id}]"
        yield f"{where}.basis_trade_ccy", position.basis_trade_ccy
        yield f"{where}.basis_base_ccy", position.basis_base_ccy
        for lot in position.lots:
            yield f"{where}.lot[{lot.lot_id}].cost_trade_ccy", lot.cost_trade_ccy
            yield f"{where}.lot[{lot.lot_id}].cost_base_ccy", lot.cost_base_ccy

    for disposal in result.ledger.disposals:
        where = f"disposal {disposal.sequence}"
        yield f"{where}.proceeds_trade_ccy", disposal.proceeds_trade_ccy
        yield f"{where}.proceeds_base_ccy", disposal.proceeds_base_ccy
        yield f"{where}.consumed_basis_trade_ccy", disposal.consumed_basis_trade_ccy
        yield f"{where}.consumed_basis_base_ccy", disposal.consumed_basis_base_ccy
        yield f"{where}.allocated_fees_trade_ccy", disposal.allocated_fees_trade_ccy
        yield f"{where}.allocated_fees_base_ccy", disposal.allocated_fees_base_ccy
        yield f"{where}.realised_gain_trade_ccy", disposal.realised_gain_trade_ccy
        yield f"{where}.realised_gain_base_ccy", disposal.realised_gain_base_ccy

    for row in result.schedule.rows:
        where = f"schedule row {row.sequence} ({row.kind.value})"
        yield f"{where}.gross", row.gross
        yield f"{where}.tax", row.tax
        yield f"{where}.net", row.net

    for charge in result.charges:
        where = f"charge on event {charge.event_sequence}"
        yield f"{where}.pit", charge.pit
        yield f"{where}.levy", charge.levy
        yield f"{where}.total", charge.total
        yield f"{where}.taxable_base", charge.taxable_base

    yield "hurdle.total_tax", result.hurdle.total_tax


def _derived_from_terms(result: Projection, terms_source_id: str) -> list[tuple[str, Money]]:
    """Every amount whose provenance names the issue's terms -- the yield's descendants."""
    return [
        (label, amount)
        for label, amount in _amounts(result)
        if any(ref.id == terms_source_id for ref in amount.provenance.sources)
    ]


# --- the tests ------------------------------------------------------------------------


class TestNoDerivedFigureIsUnmarked:
    """SC-005: 100% of derived figures marked, and the unmarked ones named and zero."""

    @pytest.mark.parametrize("path", PATHS)
    def test_every_amount_is_marked_or_is_a_zero_resting_on_no_source(self, path: str) -> None:
        unmarked = [
            (label, amount)
            for label, amount in _amounts(PATHS[path])
            if not prov.is_unverified(amount.provenance)
        ]
        offenders = [
            (label, amount)
            for label, amount in unmarked
            if amount.provenance != prov.EMPTY or amount.amount != 0.0
        ]
        assert not offenders, (
            "these figures rest on an unverified yield and do not say so, which FR-015 "
            "calls a defect of the highest severity:\n"
            + "\n".join(f"  {label} = {amount!r}" for label, amount in offenders)
        )

    @pytest.mark.parametrize("path", PATHS)
    def test_the_only_unmarked_amounts_are_the_ones_named_here(self, path: str) -> None:
        """The exceptions are enumerated, not merely tolerated.

        Exactly two kinds of amount in this result legitimately rest on nothing, and both
        are ``money.zero``:

        * the **tax line of a row where no rule ran** -- the purchase. A zero *charge*
          citing an exemption and a zero standing for "no rule applied here" are different
          claims, and the provenance is what tells them apart;
        * a disposal's **allocated fees**, because this feature emits no fee events at all.
          The zero is the empty sum of an empty set, not a fee whose source was lost.

        Naming both means a *third* unmarked amount appearing anywhere fails here rather
        than joining an unexamined allowance.
        """
        unmarked = {
            label for label, amount in _amounts(PATHS[path]) if amount.provenance == prov.EMPTY
        }
        expected = {
            f"schedule row {row.sequence} ({row.kind.value}).tax"
            for row in PATHS[path].schedule.rows
            if row.kind is EventKind.PURCHASE
        } | {
            f"disposal {disposal.sequence}.allocated_fees_{ccy}"
            for disposal in PATHS[path].ledger.disposals
            for ccy in ("trade_ccy", "base_ccy")
        }
        assert unmarked == expected

    @pytest.mark.parametrize("path", PATHS)
    def test_the_walk_actually_reaches_the_whole_result(self, path: str) -> None:
        """Guard against a walk that quietly enumerates nothing.

        Every test above would pass over an empty iterator. The count is written out as
        the shape of the D1 projection so that a walk which stopped reaching one of the
        records fails here rather than turning the suite green by omission:

        * 11 events -- a purchase, four coupons, the redemption, and a tax charge on each
          of the five taxable ones;
        * one UAH balance, contributing its three separately accumulated figures;
        * one position, contributing its two bases. It contributes **no lots**: the
          redemption consumes the only one, so the final state holds none. Their costs are
          not thereby unchecked -- they reach the walk as the disposal's consumed basis;
        * one disposal, contributing all eight terms of FR-011's identity;
        * six schedule rows of three amounts, five charges of four, and ``total_tax``.
        """
        labels = [label for label, _ in _amounts(PATHS[path])]
        assert len(labels) == len(set(labels)), "two amounts share a label; one is hidden"
        assert len(PATHS[path].ledger.applied) == 11
        assert len(PATHS[path].schedule.rows) == 6
        assert len(PATHS[path].charges) == 5
        assert not any(position.lots for position in PATHS[path].ledger.positions.values())
        assert len(labels) == 11 + 3 + 2 + 8 + 6 * 3 + 5 * 4 + 1


class TestTheFiguresFrRule015NamesByName:
    """The schedule, every tax figure, ``total_tax`` and both return figures."""

    @pytest.mark.parametrize("path", PATHS)
    def test_every_schedule_row_that_moved_money_is_marked(self, path: str) -> None:
        for row in PATHS[path].schedule.rows:
            assert prov.is_unverified(row.gross.provenance), f"row {row.sequence} gross"
            assert prov.is_unverified(row.net.provenance), f"row {row.sequence} net"

    @pytest.mark.parametrize("path", PATHS)
    def test_every_tax_figure_is_marked_although_every_one_of_them_is_zero(self, path: str) -> None:
        """E5 exactly: a *zero* tax figure still renders with its source and its state.

        This is the whole point of recording zeroes. An exempt charge that carried no
        provenance would be indistinguishable from a rule that never ran, and the mark is
        what says the exemption itself has not been checked against the Tax Code.
        """
        charges = PATHS[path].charges
        assert charges
        for charge in charges:
            assert charge.total.amount == 0.0
            for label, amount in (
                ("pit", charge.pit),
                ("levy", charge.levy),
                ("total", charge.total),
                ("taxable_base", charge.taxable_base),
            ):
                assert prov.is_unverified(amount.provenance), (
                    f"charge on event {charge.event_sequence}: {label} is a tax figure "
                    "resting on an unverified rule and does not say so"
                )
            assert prov.is_unverified(charge.provenance)

    @pytest.mark.parametrize("path", PATHS)
    def test_total_tax_is_exactly_zero_and_still_carries_the_mark(self, path: str) -> None:
        total_tax = PATHS[path].hurdle.total_tax
        assert total_tax.amount == 0.0
        assert prov.is_unverified(total_tax.provenance)

    @pytest.mark.parametrize("path", PATHS)
    def test_both_return_figures_report_unverified_through_the_figure_they_belong_to(
        self, path: str
    ) -> None:
        """Both rates are marked by one mark, because they rest on the same inputs.

        ``nominal_ytm`` and ``nominal_cash_flow_return`` are dimensionless rates rather
        than amounts, so the mark lives on the record that holds them
        (``HurdleRate.provenance``) rather than being duplicated onto each. Duplicating it
        would create a second place for it to disagree with itself; what matters is that a
        reader cannot obtain either figure without also obtaining the mark, which the
        record shape guarantees.
        """
        hurdle = PATHS[path].hurdle
        assert prov.is_unverified(hurdle.provenance)
        assert hurdle.nominal_ytm.value > 0.0
        assert hurdle.nominal_cash_flow_return.value > 0.0

    @pytest.mark.parametrize("path", PATHS)
    def test_the_mark_names_which_sources_are_responsible(self, path: str) -> None:
        """A mark that cannot say *why* is the run-scoped taint flag research.md D2 rejects."""
        responsible = prov.unverified_sources(PATHS[path].hurdle.provenance)
        assert responsible
        assert {ref.id for ref in responsible} == {
            ref.id for ref in PATHS[path].hurdle.provenance.sources
        }
        for ref in responsible:
            assert ref.citation
            assert ref.verified_on is None


class TestTheUnverifiedYieldReachesEveryFigureItShould:
    """The positive half: the yield's own source is *present* downstream, not just a mark."""

    def test_the_hand_built_terms_reach_the_schedule_the_charges_and_the_figure(self) -> None:
        result = PATHS["hand-built records"]
        derived = dict(_derived_from_terms(result, synthetic.TERMS_SOURCE.id))
        assert synthetic.TERMS_SOURCE in result.hurdle.provenance.sources
        for row in result.schedule.rows:
            if row.kind is EventKind.PURCHASE:
                continue  # the cost is the owner's statement, not the issue's terms
            assert f"schedule row {row.sequence} ({row.kind.value}).gross" in derived
            assert f"schedule row {row.sequence} ({row.kind.value}).net" in derived
        for charge in result.charges:
            assert f"charge on event {charge.event_sequence}.total" in derived
        assert "hurdle.total_tax" in derived

    def test_the_loaded_declaration_carries_the_file_and_table_it_came_from(self) -> None:
        """The loader's own refs, which the hand-built path cannot exercise.

        A figure has to trace back to *where it was declared*, not merely to a citation
        string, or two tables in one file become indistinguishable in a provenance set.
        """
        result = PATHS["loaded declarations"]
        ids = {ref.id for ref in result.hurdle.provenance.sources}
        assert LOADED_TERMS_SOURCE_ID in ids
        assert LOADED_EXEMPTION_SOURCE_ID in ids
        derived = dict(_derived_from_terms(result, LOADED_TERMS_SOURCE_ID))
        assert "hurdle.total_tax" in derived
        assert any(label.endswith("(coupon).gross") for label in derived)
        assert any(label.startswith("charge on event") for label in derived)

    def test_the_exemptions_citation_reaches_the_total_it_justifies(self) -> None:
        """The zero is only evidence of an exemption if it names the exemption."""
        result = PATHS["loaded declarations"]
        assert LOADED_EXEMPTION_SOURCE_ID in {
            ref.id for ref in result.hurdle.total_tax.provenance.sources
        }


class TestTheMarkTracksTheDataAndNotTheCode:
    """Falsifiability: verify every source and the whole result stops being marked.

    Without this, every assertion above would pass just as green against an implementation
    that marked everything unconditionally -- and a mark that is always on says nothing
    about the data. It is the hand-built path only: there is no verified variant of the
    declaration files, and inventing one by editing a ``verified_on`` in ``data/`` would
    falsify a citation to make a test convenient.
    """

    def test_with_every_source_verified_no_figure_is_marked(self) -> None:
        marked = [
            label
            for label, amount in _amounts(_from_code(verified=True))
            if prov.is_unverified(amount.provenance)
        ]
        assert not marked, f"these figures are marked although every source is verified: {marked}"

    def test_and_the_headline_figure_agrees(self) -> None:
        verified = _from_code(verified=True)
        assert not prov.is_unverified(verified.hurdle.provenance)
        assert not prov.unverified_sources(verified.hurdle.provenance)

    def test_verifying_a_source_changes_no_amount(self) -> None:
        """The mark is metadata: filling in a verification date moves no money.

        Asserted here because it is what makes the determinism digest able to exclude
        provenance (research.md D5) without excluding anything a figure depends on. If
        verifying a source changed an amount, one of the two claims would have to give.
        """
        unverified = dict(_amounts(_from_code(verified=False)))
        verified = dict(_amounts(_from_code(verified=True)))
        assert unverified.keys() == verified.keys()
        for label, amount in unverified.items():
            assert amount.amount == verified[label].amount, label
            assert amount.currency is verified[label].currency, label


def test_provenance_is_never_emptied_by_a_derivation() -> None:
    """Monotonicity, stated as a property of the result rather than of one function.

    ``money.scale_sourced`` can only add sources and nothing anywhere removes one, so a
    figure's provenance grows as it is derived. The observable consequence is that the
    headline figure's source set contains every source that appears anywhere in the run:
    if some derivation dropped a mark, a source would exist in an intermediate amount and
    be missing from the total.
    """
    for result in PATHS.values():
        everywhere: Provenance = prov.merge_all(amount.provenance for _, amount in _amounts(result))
        assert everywhere.sources
        assert everywhere.sources <= result.hurdle.provenance.sources | _cost_only(result)


def _cost_only(result: Projection) -> frozenset[SourceRef]:
    """The purchase cost's own sources, which the hurdle rate legitimately does not carry.

    The cost enters the yield as the *price* the flows are discounted to, through the
    purchase event, so its sources do reach ``hurdle.provenance`` in this feature. This
    escape hatch exists so that the assertion above states the containment it means --
    every source reachable in the result is either in the headline figure or is the
    owner's own statement of what they paid -- rather than asserting an equality that a
    later feature's ancillary figure would break for an uninteresting reason.
    """
    return result.ledger.applied[0].amount.provenance.sources


# ---------------------------------------------------------------------------
# 006-inzhur-instruments: the fund terms join the walk
# ---------------------------------------------------------------------------
#
# SC-008: *with any fund term left unverified, 100% of figures derived from it carry the
# unverified mark, and no derived figure appears unmarked.* A fund has more independent
# unverified observations than a bond does -- its NAV, its stated yield, its distribution
# terms, its spread, both readings of its liquidity and each dated ceiling -- and the
# figures below are built by a different projection function from the one above, so the
# earlier walk cannot stand in for this one.
#
# The same discipline applies: an explicit walk rather than a reflective sweep, so a new
# figure has to be added here and the addition is where a reviewer asks whether it carries
# its mark.


def _fund_amounts(result: FundProjection) -> Iterator[tuple[str, Money]]:
    """Every ``Money`` in a fund projection, labelled with where it was found."""
    for event in result.ledger.applied:
        yield f"event {event.sequence} ({event.kind.value}).amount", event.amount

    for currency, balance in result.ledger.accounts.items():
        where = f"balance[{currency.value}]"
        yield f"{where}.inflows", balance.inflows
        yield f"{where}.outflows", balance.outflows
        yield f"{where}.balance", balance.balance

    for disposal in result.ledger.disposals:
        where = f"disposal {disposal.sequence}"
        yield f"{where}.proceeds_base_ccy", disposal.proceeds_base_ccy
        yield f"{where}.consumed_basis_base_ccy", disposal.consumed_basis_base_ccy
        yield f"{where}.realised_gain_base_ccy", disposal.realised_gain_base_ccy

    for charge in result.charges:
        where = f"charge on event {charge.event_sequence}"
        yield f"{where}.pit", charge.pit
        yield f"{where}.levy", charge.levy
        yield f"{where}.total", charge.total
        yield f"{where}.taxable_base", charge.taxable_base

    for subtotal in result.tax_by_class:
        where = f"subtotal[{subtotal.tax_class_id}]"
        yield f"{where}.pit", subtotal.pit
        yield f"{where}.levy", subtotal.levy
        yield f"{where}.total_charged", subtotal.total_charged

    for line in result.distributions:
        where = f"distribution paid {line.paid_on.isoformat()}"
        yield f"{where}.gross", line.gross
        yield f"{where}.tax", line.tax
        yield f"{where}.net", line.net

    exit_line = result.exit_line
    if exit_line is not None:
        yield "exit.nav_per_unit", exit_line.nav_per_unit
        yield "exit.gross_proceeds", exit_line.gross_proceeds
        yield "exit.discount_amount", exit_line.discount_amount
        yield "exit.realised_gain", exit_line.realised_gain
        yield "exit.taxable_base", exit_line.taxable_base
        yield "exit.tax", exit_line.tax
        if exit_line.realised_loss is not None:
            yield "exit.realised_loss", exit_line.realised_loss

    yield "entry_spread", result.entry_spread
    yield "exit_spread", result.exit_spread
    if result.exit_discount is not None:
        yield "exit_discount", result.exit_discount
    yield "round_trip_spread", result.round_trip_spread
    yield "total_tax", result.total_tax
    yield "net_proceeds", result.net_proceeds


REIT_ID = "inzhur_reit"
REIT_NAV_SOURCE_ID = f"instruments/{REIT_ID}.toml#instrument.nav"
REIT_YIELD_SOURCE_ID = f"instruments/{REIT_ID}.toml#instrument.declared_yield"
REIT_CEILING_SOURCE_ID = f"instruments/{REIT_ID}.toml#instrument.distribution.peg.cap[1]"


def _reit_projection() -> FundProjection:
    """The real REIT, projected from ``data/`` with an owner-stated rate and an early exit.

    The shipped declaration rather than a fixture, because the claim under test is that the
    *loader* attaches a real mark and nothing between the file and the figure launders it.
    Every ``verified_on`` in that file is empty, which is the honest state of a fund read
    from its own documents on one afternoon.
    """
    declarations = resolver.from_data_root(DATA_ROOT)
    declared = declarations.funds[REIT_ID]
    outcome = fund_results.project_fund(
        declared,
        Holding(
            owner_id="owner-1",
            instrument_id=REIT_ID,
            quantity=500.0,
            purchased_on=date(2027, 2, 10),
            cost=Money(5_500.0, UAH, prov.of([_OWNER_STATED_COST])),
        ),
        DateRange(start=date(2027, 2, 10), end=date(2028, 12, 31)),
        FundAssumptions(
            liquidity_mode="legal",
            buyback="available",
            exit_on=date(2028, 2, 10),
            yield_point=None,
            exchange_rate=ExchangeRateAssumption(
                uah_per_unit=48.0,
                is_assumption=True,
                rationale="TEST — an owner-stated rate above the declared ceiling.",
            ),
            consumption_method="fifo",
        ),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, FundProjection), f"expected a projection, got {outcome!r}"
    return outcome


class TestNoFundFigureIsUnmarked:
    """SC-008, over every amount a fund projection produces."""

    def test_every_non_zero_amount_carries_the_mark(self) -> None:
        result = _reit_projection()
        unmarked = [
            (label, amount)
            for label, amount in _fund_amounts(result)
            if not prov.is_unverified(amount.provenance)
        ]
        for label, amount in unmarked:
            assert amount.amount == 0.0, (
                f"{label} is {amount.amount!r} and carries no unverified mark, although "
                "every term of the fund it was computed from has an empty verification "
                "date (FR-015, SC-008)"
            )

    def test_the_walk_actually_reaches_something(self) -> None:
        """A walk over nothing passes forever, which is how this class would rot."""
        found = list(_fund_amounts(_reit_projection()))
        assert len(found) > 30
        assert any(label.startswith("distribution paid") for label, _ in found)
        assert any(label.startswith("subtotal[") for label, _ in found)
        assert any(label == "exit.realised_gain" for label, _ in found)

    def test_the_headline_figures_name_the_terms_they_came_from(self) -> None:
        """Not merely marked: marked **by the source that made them uncertain**.

        A figure marked by some unrelated unverified input would satisfy a boolean check
        and tell the reader nothing about what to go and verify.
        """
        result = _reit_projection()
        nav_derived = {
            label
            for label, amount in _fund_amounts(result)
            if any(ref.id == REIT_NAV_SOURCE_ID for ref in amount.provenance.sources)
        }
        assert "entry_spread" in nav_derived
        assert "exit.gross_proceeds" in nav_derived
        assert "net_proceeds" in nav_derived

    def test_the_declared_yield_reaches_every_payout_and_its_tax(self) -> None:
        result = _reit_projection()
        assert result.distributions
        for line in result.distributions:
            ids = {ref.id for ref in line.gross.provenance.sources}
            assert REIT_YIELD_SOURCE_ID in ids
            assert REIT_CEILING_SOURCE_ID in ids, (
                "the ceiling is an input to a pegged payment, so its citation has to "
                "reach the figure it bounded"
            )
            assert REIT_YIELD_SOURCE_ID in {ref.id for ref in line.tax.provenance.sources}

    def test_the_per_class_subtotals_carry_the_rate_entries_own_citations(self) -> None:
        for subtotal in _reit_projection().tax_by_class:
            ids = {ref.id for ref in subtotal.provenance.sources}
            assert any("jurisdiction.tax_class" in name and ".rate[" in name for name in ids), (
                f"{subtotal.tax_class_id} cites no dated rate entry, so its charge cannot "
                "say which entry produced it"
            )

    def test_the_projections_own_provenance_is_the_union_of_what_it_rests_on(self) -> None:
        result = _reit_projection()
        every = {ref for _, amount in _fund_amounts(result) for ref in amount.provenance.sources}
        assert every <= result.provenance.sources


# ---------------------------------------------------------------------------
# 007-cpi-real-terms: the real figure's provenance is the union of both sides
# ---------------------------------------------------------------------------
#
# FR-013: *"Every real figure MUST be traceable to the CPI observations that deflated it and
# to the nominal figure it deflates. Its provenance is the union of both sides': an unverified
# mark or a staleness report on any CPI observation used, or on any input of the nominal
# figure, MUST appear on the real figure and on everything derived from it."*
#
# The walk above cannot reach these figures: it enumerates `Money`, and a rate is a bare
# float. So the union is asserted here, and **by count** rather than by sample (research.md
# D6) -- a long window really does put hundreds of sources on one figure, and a test that
# checked "some observation is in there" would pass with 411 months collapsed into one.
#
# Both directions are checked, because the two failures are different edits. Deflating a
# marked figure by clean observations must not launder the mark; deflating a clean figure by
# marked observations must add one. A transform that dropped either is top severity.


def _deflated(
    *,
    nominal_verified: bool,
    observations_verified: bool,
    months: int = 12,
) -> RealRate:
    """One realized real figure, with each side's verification set independently."""
    nominal_source = SourceRef(
        id="synthetic:nominal",
        citation="SYNTHETIC FIXTURE -- the nominal figure's own input.",
        retrieved_on=date(2026, 8, 23),
        verified_on=date(2026, 8, 23) if nominal_verified else None,
    )
    series = cpi_fixtures.series(
        cpi_fixtures.run_of("2026-01", months, 101.0),
        verified_on=date(2026, 8, 23) if observations_verified else None,
    )
    figure = hurdle.real_terms(
        nominal=NominalRate(0.155),
        nominal_provenance=prov.of([nominal_source]),
        nominal_staleness=staleness.UNASSESSED,
        deflation=cpi_fixtures.deflation(
            window=Window(first="2026-01", last=series.observations[-1].period),
            series=series,
        ),
    ).realized
    assert isinstance(figure, RealRate), figure
    return figure


def test_a_real_figure_carries_one_source_per_month_it_chained_plus_the_nominal_side() -> None:
    """Asserted by count. A shared or summarised ref would collapse this to a handful."""
    figure = _deflated(nominal_verified=True, observations_verified=True, months=24)

    assert len(figure.provenance.sources) == 25
    assert "synthetic:nominal" in {ref.id for ref in figure.provenance.sources}


def test_every_month_of_the_window_is_individually_traceable() -> None:
    """The count could be right with the wrong months in it; this says which months."""
    figure = _deflated(nominal_verified=True, observations_verified=True, months=6)
    ids = {ref.id for ref in figure.provenance.sources}

    assert ids == {"synthetic:nominal", *(f"synthetic:cpi:2026-0{month}" for month in range(1, 7))}


def test_an_unverified_observation_marks_the_real_figure() -> None:
    """One unverified month taints the figure, however many verified ones surround it."""
    figure = _deflated(nominal_verified=True, observations_verified=False)

    assert prov.is_unverified(figure.provenance)


def test_a_marked_nominal_figure_is_not_laundered_by_deflating_it() -> None:
    """The other direction, and the one an implementation is likelier to get wrong.

    Every observation is verified here, so a figure whose provenance were built from the CPI
    side alone would come back clean -- and would have dropped the nominal figure's mark in a
    change nobody would read as dropping anything.
    """
    figure = _deflated(nominal_verified=False, observations_verified=True)

    assert prov.is_unverified(figure.provenance)
    assert {ref.id for ref in prov.unverified_sources(figure.provenance)} == {"synthetic:nominal"}


def test_the_mark_is_falsifiable_on_the_real_figure_too() -> None:
    """Both sides verified means no mark. A mark that is always on carries no information."""
    figure = _deflated(nominal_verified=True, observations_verified=True)

    assert not prov.is_unverified(figure.provenance)


def test_a_stale_observation_is_reportable_from_the_figures_own_sources() -> None:
    """FR-013's staleness half: the verdict is derivable from what the figure carries.

    Derived rather than stored, on ``RoutesInForce.decided_by``'s reasoning: two places
    holding one fact eventually disagree. What matters is that the figure carries the
    *sources*, so the verdict can be taken against any as-of date the run asks about.
    """
    figure = _deflated(nominal_verified=True, observations_verified=False, months=3)
    kinds = {kind.id: kind for kind in loader.observation_kinds_from_file(KINDS_FILE)}
    observations = tuple(
        cpi_fixtures.observation(period, 101.0)
        for period, _ in cpi_fixtures.run_of("2026-01", 3, 101.0)
    )

    verdict = cpi_series.staleness_of_observations(observations, kinds, as_of=date(2027, 1, 1))

    assert staleness.any_stale(verdict)
    assert {entry.source_id for entry in verdict.stale} <= {
        ref.id for ref in figure.provenance.sources
    }


def test_the_assumed_figure_carries_the_forecasts_citation_and_the_nominal_side() -> None:
    """An assumption is not exempt from provenance when it was read somewhere (FR-015)."""
    nominal_source = SourceRef(
        id="synthetic:nominal",
        citation="SYNTHETIC FIXTURE -- the nominal figure's own input.",
        retrieved_on=date(2026, 8, 23),
        verified_on=None,
    )
    figure = hurdle.real_terms(
        nominal=NominalRate(0.155),
        nominal_provenance=prov.of([nominal_source]),
        nominal_staleness=staleness.UNASSESSED,
        deflation=cpi_fixtures.deflation(
            window=Window(first="2026-01", last="2026-12"),
            assumption=cpi_fixtures.forecast_assumption(0.12),
        ),
    ).assumed
    assert isinstance(figure, RealRate)

    assert len(figure.provenance.sources) == 2
    assert prov.is_unverified(figure.provenance)


# ---------------------------------------------------------------------------
# 009-tax-depth: an unverified legal value marks the year it assembles
# ---------------------------------------------------------------------------
#
# FR-027 and SC-008. The declared deadlines, the netting treatment, the carryforward rule and
# every finding about a basis method are legal values with empty `verified_on`, and a figure
# resting on one of them says so. The sweep below takes the money fields off the records
# themselves, so a field added later is inside the claim rather than outside it.


def _amounts_within(name: str, value: object) -> Iterator[tuple[str, Money]]:
    """Every ``Money`` reachable from one field, including inside tuples of tuples.

    Descending rather than testing ``isinstance(value, Money)`` at the top level: a field can
    be a *container* of amounts -- ``CarryforwardState.origins`` is ``(origin year, amount)``
    pairs -- and a sweep that only looked one level down would silently exclude it while
    claiming to cover the record.
    """
    if isinstance(value, Money):
        yield name, value
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from _amounts_within(f"{name}[{index}]", item)


def _statement_amounts(statement: tax_year.AnnualStatement) -> Iterator[tuple[str, Money]]:
    """Every ``Money`` a statement computes for itself, named by where it sits.

    Swept from the dataclasses rather than listed, on the same reasoning the projection sweep
    above gives: a field added to a liability or a carryforward next year is inside this claim
    without anybody remembering to add it, container-valued fields included.

    ``charges`` is deliberately outside the scope. Those amounts are feature 001's, computed by
    ``tax.flat_rate`` before any year existed and resting on their own rate entries; the claim
    here is about the figures the *year* produces from a declared assessment rule.
    """
    for field in dataclasses.fields(statement.liability):
        yield from _amounts_within(
            f"liability.{field.name}", getattr(statement.liability, field.name)
        )
    yield "netted_base", statement.netted_base
    if statement.carryforward is not None:
        for field in dataclasses.fields(statement.carryforward):
            yield from _amounts_within(
                f"carryforward.{field.name}", getattr(statement.carryforward, field.name)
            )


def _assessed_under(rules: tax_year.AssessmentRules) -> tuple[tax_year.AnnualStatement, ...]:
    """The loss-then-gain fixture assessed under one set of rules."""
    events = _tax_year_events()
    state = engine.fold(
        events, base_currency=Currency.UAH, consumption_method=lots.LotMethod.FIFO.value
    )
    charges = []
    for disposal in state.disposals:
        charge = flat_rate.charge(
            next(event for event in events if event.sequence == disposal.sequence),
            tax_years.TAXED_CLASS,
            TaxContext(
                instrument_id="fixture",
                taxable_event=TaxableEventKind.DISPOSAL_GAIN,
                taxable_base=disposal.realised_gain_base_ccy,
                charged_for_year=disposal.occurred_on.year,
            ),
        )
        assert isinstance(charge, TaxCharge), charge
        charges.append(charge)
    built = tax_year.statements(
        state,
        tuple(charges),
        rules=rules,
        tax_classes=tax_years.TAX_PACK,
        filing=tax_years.filing(y2025=True, y2026=True),
        method=lots.LotMethod.FIFO,
        switches=tax_years.positions(),
    )
    assert isinstance(built, tuple), built
    return built


def _tax_year_events() -> tuple[Event, ...]:
    term = CausationRef(kind=CausationKind.INSTRUMENT_TERM, id="fixture:term", detail="fixture")
    source = prov.of([tax_years.FIXTURE_SOURCE])

    def event(sequence: int, on: date, kind: EventKind, amount: float, **extra: object) -> Event:
        return Event(
            sequence=sequence,
            occurred_on=on,
            kind=kind,
            amount=Money(amount, Currency.UAH, source),
            owner_id="owner-1",
            caused_by=term,
            lot_ref=extra.get("lot_ref"),  # type: ignore[arg-type]
            quantity=extra.get("quantity"),  # type: ignore[arg-type]
            allocated_to=None,
            capacity_pool=None,
        )

    return (
        event(1, date(2025, 1, 5), EventKind.CASH_DEPOSIT, 40_000.0),
        event(
            2,
            date(2025, 1, 5),
            EventKind.PURCHASE,
            -10_000.0,
            lot_ref=LotRef(instrument_id="fixture", lot_id="lot-a"),
            quantity=100.0,
        ),
        event(
            3,
            date(2025, 1, 6),
            EventKind.PURCHASE,
            -10_000.0,
            lot_ref=LotRef(instrument_id="fixture", lot_id="lot-b"),
            quantity=100.0,
        ),
        event(
            4,
            date(2025, 6, 10),
            EventKind.PRINCIPAL_REPAYMENT,
            7_000.0,
            lot_ref=LotRef(instrument_id="fixture", lot_id=None),
            quantity=100.0,
        ),
        event(
            5,
            date(2026, 9, 15),
            EventKind.PRINCIPAL_REPAYMENT,
            18_000.0,
            lot_ref=LotRef(instrument_id="fixture", lot_id=None),
            quantity=100.0,
        ),
        # A year with no investment operation at all, so the sweep covers the quiet-year
        # branch as well as the loss and gain ones. Its whole statement is built out of
        # zeroes, which is exactly where an unverified rule used to stop reaching.
        event(6, date(2027, 4, 1), EventKind.CASH_DEPOSIT, 100.0),
    )


def _unverified_rules() -> tax_year.AssessmentRules:
    """The fixture rules with one legal value -- the netting category -- left unchecked."""
    verified = tax_years.rules()
    category = verified.categories[tax_years.INVESTMENT]
    return dataclasses.replace(
        verified,
        categories={
            **verified.categories,
            tax_years.INVESTMENT: dataclasses.replace(
                category, provenance=prov.of([tax_years.UNVERIFIED_SOURCE])
            ),
        },
    )


def _unverified_timing() -> tax_year.AssessmentRules:
    """The fixture rules with one legal value -- the payment deadline -- left unchecked."""
    verified = tax_years.rules()
    rule = verified.timing[tax_years.INVESTMENT]
    return dataclasses.replace(
        verified,
        timing={
            **verified.timing,
            tax_years.INVESTMENT: dataclasses.replace(
                rule, provenance=prov.of([tax_years.UNVERIFIED_SOURCE])
            ),
        },
    )


def _settled_under(rules: tax_year.AssessmentRules) -> settlement.Settlement:
    """The same fixture assessed and then paid, so the sweep reaches the cash that left."""
    outcome = settlement.settle(
        _tax_year_events(),
        _assessed_under(rules),
        owner_id="owner-1",
        base_currency=Currency.UAH,
        method=lots.LotMethod.FIFO,
        horizon_end=date(2028, 12, 31),
    )
    assert isinstance(outcome, settlement.Settlement), outcome
    return outcome


def test_an_unverified_assessment_rule_marks_every_figure_of_the_year_it_governs() -> None:
    """SC-008's 100%: the sweep is over the records' own fields, not a list somebody kept.

    The rule left unchecked is the netting treatment, and the base is what it is *because*
    that rule says the year's operations net -- so a mark that reached ``rests_on`` and
    stopped there would leave the liability, the netted base and the carryforward looking
    checked while the input behind all three was not.
    """
    marked = 0
    for statement in _assessed_under(_unverified_rules()):
        if statement.category != tax_years.INVESTMENT:
            continue
        assert prov.is_unverified(statement.liability.rests_on), statement.tax_year
        for name, amount in _statement_amounts(statement):
            assert prov.is_unverified(amount.provenance), f"{statement.tax_year} {name}"
            marked += 1
    assert marked, "the sweep found no figure to be about"


def test_the_unverified_rule_reaches_the_payment_that_settles_the_year() -> None:
    """FR-027 names payment events, and they are the last figure in the chain.

    A run whose statements are marked and whose ``TAX_PAYMENT`` is not would put an unmarked
    amount in the ledger -- the one place a reader looks to see what actually left.
    """
    settled = _settled_under(_unverified_rules())

    assert settled.payments, "the fixture must owe something for this to be about anything"
    for payment in settled.payments:
        assert prov.is_unverified(payment.amount.provenance), payment.tax_year
    paid = [event for event in settled.stream if event.kind is EventKind.TAX_PAYMENT]
    assert len(paid) == len(settled.payments)
    for event in paid:
        assert prov.is_unverified(event.amount.provenance), event.sequence


def test_an_unverified_deadline_marks_the_money_even_though_it_cannot_mark_the_date() -> None:
    """The omission a ``date`` forces, made visible instead of left silent.

    ``AnnualStatement.due_on`` and ``TaxPayment.due_on`` are bare dates, and there is no
    dated-value wrapper here the way ``Money`` is an amount carrying its sources -- so a date
    has nowhere to hold a mark. The timing rule's own ``verified_on`` therefore has to travel
    on the amounts, and this is the assertion that it does: leave the *deadline* unchecked and
    the liability and the payment say so.
    """
    settled = _settled_under(_unverified_timing())

    assert settled.payments
    for statement in settled.statements:
        assert statement.due_on is not None
        for name, amount in _statement_amounts(statement):
            assert prov.is_unverified(amount.provenance), f"{statement.tax_year} {name}"
    for payment in settled.payments:
        assert prov.is_unverified(payment.amount.provenance), payment.tax_year


def test_the_mark_is_falsifiable_on_a_tax_year_too() -> None:
    """The same assessment with everything checked is unmarked, so the tests above can fail."""
    settled = _settled_under(tax_years.rules())

    for statement in settled.statements:
        assert not prov.is_unverified(statement.liability.rests_on), statement.tax_year
        for name, amount in _statement_amounts(statement):
            assert not prov.is_unverified(amount.provenance), f"{statement.tax_year} {name}"
    assert settled.payments
    for payment in settled.payments:
        assert not prov.is_unverified(payment.amount.provenance), payment.tax_year


def test_the_unverified_rule_is_named_on_the_figure_rather_than_merely_flagged() -> None:
    """A mark that cannot say which input it rests on is a taint flag: cheap and useless."""
    marked = [
        statement
        for statement in _assessed_under(_unverified_rules())
        if statement.category == tax_years.INVESTMENT
    ]

    for statement in marked:
        assert tax_years.UNVERIFIED_SOURCE in statement.liability.rests_on.sources


def test_the_sweep_reaches_amounts_held_inside_a_container() -> None:
    """Otherwise "every field is inside this claim" is false for any container of ``Money``.

    ``CarryforwardState.origins`` is ``(origin year, amount)`` pairs, and it is already such a
    field. A sweep testing ``isinstance(value, Money)`` at the top level skips it in silence.
    """
    swept = {
        name
        for statement in _assessed_under(tax_years.rules())
        for name, _ in _statement_amounts(statement)
    }

    assert any(name.startswith("carryforward.origins[") for name in swept), sorted(swept)


def test_no_money_a_statement_carries_rests_on_nothing_at_all() -> None:
    """A figure with empty provenance would be an amount that admits no origin.

    **Zeroes included, and they are the point.** ``money.zero`` rests on nothing because the
    additive identity is not an observation -- but a *statement's* zero is: a base of zero is
    the clamp the statute puts on a negative annual result, and a carryforward of zero is what
    the declared rule says the year leaves behind. A zero that cannot cite the rule that
    produced it is indistinguishable from a rule that never ran, which is the reading
    ``money.scale_sourced`` was written to forbid.
    """
    for statement in _assessed_under(tax_years.rules()):
        for name, amount in _statement_amounts(statement):
            assert amount.provenance.sources, f"{statement.tax_year} {name}"
