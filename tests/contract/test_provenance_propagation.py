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

from collections.abc import Iterator, Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from terezy.core.inflation import series as cpi_series
from terezy.core.instruments.interface import (
    BondTerms,
    Holding,
    InstrumentConstraints,
    InstrumentDeclaration,
)
from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.rates import NominalRate, RealRate
from terezy.core.results import hurdle, project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxClass
from terezy.data.declarations import loader, resolver
from tests import cpi_fixtures, synthetic

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

LOADED_EXEMPTION_SOURCE_ID = "tax/ua.toml#jurisdiction.tax_class[ua_government_bond]"
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
        pit_rate=synthetic.EXEMPT_CLASS.pit_rate,
        levy_rate=synthetic.EXEMPT_CLASS.levy_rate,
        provenance=exemption_provenance,
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
        series=series,
        window=Window(first="2026-01", last=series.observations[-1].period),
        assumption=None,
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
        series=None,
        window=Window(first="2026-01", last="2026-12"),
        assumption=cpi_fixtures.forecast_assumption(0.12),
    ).assumed
    assert isinstance(figure, RealRate)

    assert len(figure.provenance.sources) == 2
    assert prov.is_unverified(figure.provenance)
