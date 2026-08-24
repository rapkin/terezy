"""K3 -- the whole path, from a file on disk to a hurdle rate, against a recorded artefact.

``data/instruments/ovdp_synthetic_a.toml`` -> loader -> resolver -> ``project.project`` ->
``HurdleRate``, compared line for line against ``ovdp_synthetic_a.golden.txt``, which was
produced by an earlier run and is checked into the repository.

**Why this is not a duplicate of the contract suite.**
``tests/contract/test_data_only_extensibility.py`` already compares the loaded path
against the hand-built one, and does it on the canonical form of the whole projection --
but it compares *two things computed in the same process*. Both move together. If a
refactor changed the coupon arithmetic, the loader path and the hand-built path would
change identically and that test would stay green. What the constitution asks for under
*"golden result files for end-to-end runs on the offline snapshot, so a refactor can be
**proven** output-preserving"* is a comparison against an artefact from **before** the
refactor, and that is what the file beside this module is.

---

**What is in the golden file, and why both halves are there.**

*The digest*, ``sha256`` over ``core.results.canonical.of_projection`` via
``data.manifest.digest_of_projection``. It is the assertion: it covers every amount as
``float.hex()``, so agreement means bit-identity and not agreement to some number of
decimals. A digest alone, though, tells a reader only *that* something moved.

*A readable rendering of the same projection* -- the figures, every schedule row, every
tax charge, and the whole folded ledger including each event's causation string. It is
what makes a failure diagnosable: ``git diff`` on this file says which coupon moved and by
how much, and the causation lines say what the engine thought it was doing. Amounts are
rendered with ``repr``, which for a float64 is exact and round-trippable, so the readable
half is **stricter** than the digest rather than the same claim written out: ``repr``
distinguishes ``-0.0`` from ``0.0`` and ``canonical.of_number`` normalises it via
``(value + 0.0).hex()``. The negative zeroes in this artefact -- one per ``TAX_CHARGE``, since
that is the whole of what ``tax.year.memo_amount`` produces -- are therefore pinned by the
rendering alone, and that is a pin on how a figure prints: nothing computed depends on the
sign of a zero. The count is asserted below rather than stated here, because a count in prose
is the first thing to go stale.

Both halves live in **one** file and the test compares the whole text, so the digest cannot
drift away from the rendering it describes.

*Chosen over ``syrupy``*, which is available as a dev dependency. Two reasons. The file is
compared by plain text equality and written by a function in this module, so there is no
snapshot framework between a failing assertion and the artefact a reader has to read; and
the update path is one documented environment variable rather than a plugin flag whose
semantics live in another project's changelog. ``syrupy`` would earn its place if there
were many snapshots of many shapes. There is one.

---

**How to update it deliberately.** A golden test nobody can update becomes a golden test
everybody deletes, so the procedure is one command:

```bash
TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_end_to_end_ovdp.py
git diff tests/golden/ovdp_synthetic_a.golden.txt
```

Then **read the diff**, and say in the commit message why every changed line is intended.
That is the whole point of the exercise: the artefact is a record of what the engine used
to answer, and overwriting it without reading the diff converts a proof into a formality.

The variable is required, and a missing file is a **failure** rather than a silent
regeneration. A golden file that reappeared on its own would make a deleted artefact --
or a fresh checkout that never had one -- indistinguishable from a passing run.

---

**What is deliberately excluded, and asserted to be excluded.**

*Provenance.* The canonical form omits it on purpose (``core.results.canonical``): filling
in a ``verified_on`` changes what a result says about its *sources* and moves no computed
amount, so a digest that covered it would fail on a documentation edit and the only
available fix would be to stop trusting the digest.
``test_verifying_every_source_moves_neither_the_digest_nor_the_rendering`` asserts that
here, at the level of the artefact: the same run with every source verified produces the
same file, while ``provenance.is_unverified`` flips. The mark is not thereby lost -- it is
a separate claim, carried by the manifest and asserted by E5 in
``tests/contract/test_provenance_propagation.py``.

*The code version.* ``RunManifest.code_version`` is part of a run's identity and is
deliberately not part of this artefact: a version bump preserves output, and a golden file
that failed on one would train its reader to overwrite it unread.

*The declaration files' own digests are **not** excluded.* They are recorded, because a
change to ``ovdp_synthetic_a.toml`` **should** fail this test -- loudly, on the line that
names the file.

Tracked as **K3** in ``docs/REQUIRED_TESTS.md``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger import canonical, lots
from terezy.core.ledger.accounts import CashBalance
from terezy.core.ledger.engine import LedgerState
from terezy.core.ledger.events import Event, EventKind
from terezy.core.ledger.lots import Disposal, Lot, Position
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.rates import RealRate, RealTermsUnavailable
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.results import project
from terezy.core.results import tax_year as settlement
from terezy.core.results.project import Projection
from terezy.core.results.schedule import CashFlowRow
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxCharge, TaxClass
from terezy.data import manifest
from terezy.data.declarations import resolver

pytestmark = pytest.mark.golden

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATA_ROOT: Final = REPO_ROOT / "data"
GOLDEN_FILE: Final = Path(__file__).with_name("ovdp_synthetic_a.golden.txt")

UPDATE_VARIABLE: Final = "TEREZY_UPDATE_GOLDEN"
"""Set it to rewrite the artefact. See the module docstring for the procedure."""

INSTRUMENT_ID: Final = "ovdp_synthetic_a"
OWNER_ID: Final = "owner-1"
QUANTITY: Final = 10.0
COST: Final = 10_000.0
# ⚙ This run projects `ovdp_synthetic_a`, whose first *taxable* event is its 2026-07-15
# coupon -- fifteen days after the earliest entry the `ua_government_bond` exemption's
# citation reaches. That dependency is asserted, once, in
# `tests/contract/test_declaration_loading.py::TestTheShippedRegistryRefusesAnUncoveredEvent`.
PURCHASED_ON: Final = date(2026, 1, 15)
HORIZON_END: Final = date(2028, 1, 31)

# The hand-computed figures this run must reproduce, from
# ``tests/worked_examples/test_ovdp_schedule.py`` where the arithmetic is shown in full.
# They are restated here, and checked, so that the golden file cannot be green and wrong:
# an artefact recorded from a broken run would agree with itself forever.
#
#   10 units x 1 000.00 face = 10 000.00 of notional at 15.5% = 1 550.00 a year
#   periods of 181, 184, 181 and 184 days -> 730 days -> exactly two act/365 years
#   so the four coupons total 1 550.00 x 730/365 = 3 100.00
#   and the principal comes back at par: 10 x 1 000.00 = 10 000.00
TOTAL_COUPONS: Final = 3_100.00
PRINCIPAL: Final = 10_000.00
COUPON_COUNT: Final = 4
ADJUSTED_MATURITY: Final = date(2028, 1, 17)
"""2028-01-15 is a Saturday, so the ``following`` rule pays the last flow on the Monday."""

UAH: Final = Currency.UAH

CPI_SERIES_ID: Final = "ua_cpi_monthly"
"""The declared series this run deflates by. Named here because it is a *choice about the
run* -- which economy's prices this owner's purchasing power is measured against -- and not a
constant of the engine, which holds no CPI of its own (FR-002)."""


# --- the run under test ---------------------------------------------------------------


def _holding() -> Holding:
    """Ten units of issue A bought at par on the issue date."""
    return Holding(
        owner_id=OWNER_ID,
        instrument_id=INSTRUMENT_ID,
        quantity=QUANTITY,
        purchased_on=PURCHASED_ON,
        cost=Money(COST, UAH, prov.EMPTY),
    )


def _horizon() -> DateRange:
    return DateRange(start=PURCHASED_ON, end=HORIZON_END)


def _assumptions() -> Assumptions:
    """FIFO, coupons held as cash. Both stated: neither has a default anywhere."""
    return Assumptions(consumption_method="fifo", coupon_policy="hold_cash")


def _declarations() -> resolver.Declarations:
    """Everything under ``data/``, resolved from disk. The offline snapshot is the repo."""
    return resolver.from_data_root(DATA_ROOT)


def _inflation() -> resolver.InflationDeclarations:
    """The declared price series and the declared future-inflation belief (007).

    Read from ``data/`` like every other declaration. The run is given **both**, so this
    artefact records the real-terms slot doing each of the two things it can do: refusing
    with a specific reason, and holding a figure.
    """
    return resolver.inflation_from_data_root(DATA_ROOT)


def _project(declarations: resolver.Declarations) -> Projection:
    inflation = _inflation()
    outcome = project.project(
        declarations.instruments[INSTRUMENT_ID],
        _holding(),
        _horizon(),
        _assumptions(),
        tax_classes=declarations.tax_classes,
        cpi_series=inflation.series[CPI_SERIES_ID],
        inflation_assumption=inflation.assumption,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


# --- verifying every source, to prove the artefact does not depend on provenance -------


def _verified(sources: Provenance) -> Provenance:
    """The same sources, every one of them checked against a primary source today.

    A fabricated verification date, used for exactly one purpose: to change the *marks* on
    a run without changing a single amount, so that the artefact can be asserted
    indifferent to them. Nothing here claims the synthetic terms have been verified.
    """
    return prov.of(
        SourceRef(
            id=ref.id,
            citation=ref.citation,
            retrieved_on=ref.retrieved_on,
            verified_on=date(2026, 8, 21),
        )
        for ref in sources.sources
    )


def _verified_declaration(declaration: InstrumentDeclaration) -> InstrumentDeclaration:
    """The same declaration with every ``verified_on`` filled in, amounts untouched."""
    terms = declaration.terms
    constraints = declaration.constraints
    terms_sources = _verified(terms.provenance)
    constraint_sources = _verified(constraints.provenance)
    return replace(
        declaration,
        terms=replace(
            terms,
            provenance=terms_sources,
            face_value=replace(terms.face_value, provenance=terms_sources),
        ),
        constraints=replace(
            constraints,
            provenance=constraint_sources,
            min_ticket=replace(constraints.min_ticket, provenance=constraint_sources),
        ),
    )


def _verified_class(declared: TaxClass) -> TaxClass:
    """The same class with every dated entry's sources verified, rates untouched.

    ⚙ Per entry since feature 006: the citation moved off the class and onto the schedule,
    so verifying "the class" means verifying each entry.
    """
    return replace(
        declared,
        rates=tuple(
            replace(entry, provenance=_verified(entry.provenance)) for entry in declared.rates
        ),
    )


def _verified_declarations(declarations: resolver.Declarations) -> resolver.Declarations:
    return replace(
        declarations,
        instruments={
            identifier: _verified_declaration(declaration)
            for identifier, declaration in declarations.instruments.items()
        },
        tax_classes={
            identifier: _verified_class(declared)
            for identifier, declared in declarations.tax_classes.items()
        },
    )


# --- the rendering --------------------------------------------------------------------
#
# Every amount goes through ``repr``, which round-trips a float64 exactly -- and also
# distinguishes ``-0.0`` from ``0.0``, which the digest deliberately does not, so the readable
# half is stricter than the digest rather than equal to it. Nothing here renders provenance:
# see the module docstring for why that exclusion is deliberate and where the mark is
# asserted instead.


def _money(value: Money) -> str:
    return f"{value.amount!r} {value.currency.value}"


def _number(value: float | None) -> str:
    return "none" if value is None else repr(value)


def _optional(value: object) -> str:
    """A field's value, or ``none``. Absence is rendered, never left blank.

    A blank would make "nothing was stated" indistinguishable from "the line ran out",
    and the two are different facts in every record this artefact carries.
    """
    return "none" if value is None else str(value)


def _real_figure(label: str, figure: RealRate | RealTermsUnavailable) -> Iterable[str]:
    """One half of the real-terms slot: the number and what it rests on, or the reason not.

    ⚙ **Two entries where feature 001 rendered one** (007 FR-009). The realized figure and
    the assumed one are two claims and are rendered as two, each labelled, so that a reader
    of this artefact cannot take either for the other and a diff shows which one moved.

    A figure renders its ``basis``, the series it is real *against* and its window beside its
    value, because a bare real rate is not checkable: the same nominal figure deflated by
    observed prices and by a belief, or over two different spans, gives different answers and
    a single number cannot say which question it answered (FR-010, FR-011).
    """
    match figure:
        case RealRate():
            yield f"{label:<28} {figure.value!r}"
            yield f"{label + '_basis':<28} {figure.basis}"
            yield f"{label + '_against':<28} {figure.series_id}"
            yield f"{label + '_window':<28} {figure.window.first} .. {figure.window.last}"
        case RealTermsUnavailable():
            yield f"{label:<28} unavailable"
            yield f"{label + '_because':<28} {figure.reason}"


def _figures(result: Projection) -> Iterable[str]:
    hurdle = result.hurdle
    yield f"nominal_ytm                  {hurdle.nominal_ytm.value!r}"
    yield f"nominal_cash_flow_return     {hurdle.nominal_cash_flow_return.value!r}"
    yield from _real_figure("real_realized", hurdle.real.realized)
    yield from _real_figure("real_assumed", hurdle.real.assumed)
    yield f"total_tax                    {_money(hurdle.total_tax)}"
    for item in sorted(hurdle.accounts_for):
        yield f"accounts_for                 {item}"
    for item in sorted(hurdle.excludes):
        yield f"excludes                     {item}"


def _schedule(rows: Sequence[CashFlowRow]) -> Iterable[str]:
    for row in rows:
        yield (
            f"{row.sequence:>3}  {row.occurred_on.isoformat()}  {row.kind.value:<20}  "
            f"units={_number(row.quantity)}"
        )
        yield f"       gross {_money(row.gross)}"
        yield f"       tax   {_money(row.tax)}"
        yield f"       net   {_money(row.net)}"
        yield (
            f"       conventions {row.conventions.periodicity} / {row.conventions.day_count}"
            f" / {row.conventions.business_day_rule}"
        )
        yield f"       caused_by {row.caused_by.kind.value} {row.caused_by.id}"
        yield f"       because   {row.caused_by.detail}"


def _charges(charges: Sequence[TaxCharge]) -> Iterable[str]:
    for charge in charges:
        yield (
            f"event {charge.event_sequence:>3}  class {charge.tax_class_id}  "
            f"year {charge.charged_for_year}"
        )
        yield f"       base  {_money(charge.taxable_base)}"
        yield f"       pit   {_money(charge.pit)}"
        yield f"       levy  {_money(charge.levy)}"
        yield f"       total {_money(charge.total)}"


def _account(balance: CashBalance) -> Iterable[str]:
    yield f"{balance.currency.value}  inflows  {_money(balance.inflows)}"
    yield f"{balance.currency.value}  outflows {_money(balance.outflows)}"
    yield f"{balance.currency.value}  balance  {_money(balance.balance)}"


def _lot(held: Lot) -> Iterable[str]:
    yield f"  lot {held.lot_id}  acquired {held.acquired_on.isoformat()}"
    yield f"      quantity {held.quantity!r}"
    yield f"      cost_trade_ccy {_money(held.cost_trade_ccy)}"
    yield f"      cost_base_ccy  {_money(held.cost_base_ccy)}"
    yield f"      fx_rate_used   {_number(held.fx_rate_used)}"


def _position(position: Position) -> Iterable[str]:
    yield f"{position.instrument_id}  quantity {position.quantity!r}"
    yield f"  basis_trade_ccy {_money(position.basis_trade_ccy)}"
    yield f"  basis_base_ccy  {_money(position.basis_base_ccy)}"
    for held in position.lots:
        yield from _lot(held)


def _disposal(disposal: Disposal) -> Iterable[str]:
    yield (
        f"event {disposal.sequence:>3}  {disposal.occurred_on.isoformat()}  "
        f"{disposal.instrument_id}  quantity {disposal.quantity!r}"
    )
    yield f"       proceeds_trade_ccy       {_money(disposal.proceeds_trade_ccy)}"
    yield f"       proceeds_base_ccy        {_money(disposal.proceeds_base_ccy)}"
    yield f"       consumed_basis_trade_ccy {_money(disposal.consumed_basis_trade_ccy)}"
    yield f"       consumed_basis_base_ccy  {_money(disposal.consumed_basis_base_ccy)}"
    yield f"       allocated_fees_trade_ccy {_money(disposal.allocated_fees_trade_ccy)}"
    yield f"       allocated_fees_base_ccy  {_money(disposal.allocated_fees_base_ccy)}"
    yield f"       realised_gain_trade_ccy  {_money(disposal.realised_gain_trade_ccy)}"
    yield f"       realised_gain_base_ccy   {_money(disposal.realised_gain_base_ccy)}"
    for lot_id, units in disposal.consumed_from:
        yield f"       consumed_from {lot_id} {units!r}"


def _event(event: Event) -> Iterable[str]:
    yield f"{event.sequence:>3}  {event.occurred_on.isoformat()}  {event.kind.value}"
    yield f"       amount {_money(event.amount)}  owner {event.owner_id}"
    yield f"       units  {_number(event.quantity)}  allocated_to {_optional(event.allocated_to)}"
    lot_ref = event.lot_ref
    yield (
        "       lot_ref none"
        if lot_ref is None
        else f"       lot_ref {lot_ref.instrument_id} {_optional(lot_ref.lot_id)}"
    )
    yield f"       caused_by {event.caused_by.kind.value} {event.caused_by.id}"
    yield f"       because   {event.caused_by.detail}"


def _ledger(state: LedgerState) -> Iterable[str]:
    yield f"as_of              {state.as_of.isoformat() if state.as_of else 'none'}"
    yield f"base_currency      {state.base_currency.value}"
    yield f"consumption_method {state.consumption_method}"
    yield ""
    yield "-- accounts --"
    for currency in sorted(state.accounts, key=lambda item: item.value):
        yield from _account(state.accounts[currency])
    yield ""
    yield "-- positions --"
    for key in sorted(state.positions):
        yield from _position(state.positions[key])
    yield ""
    yield "-- disposals --"
    for disposal in state.disposals:
        yield from _disposal(disposal)
    yield ""
    yield "-- events --"
    for event in state.applied:
        yield from _event(event)


def _inputs(declarations: resolver.Declarations) -> Iterable[str]:
    """The declarations this run was given: kind, id, file, and the file's own digest.

    ``manifest.input_refs`` also carries each input's unverified source ids. They are
    deliberately dropped here: this artefact is a record of the arithmetic, and the
    verification state of a citation is not part of it (see the module docstring). The
    file digests are kept precisely because a change to a declaration file *should* fail
    this test, on the line that names the file.
    """
    refs = sorted(
        [*manifest.input_refs(declarations), *manifest.inflation_input_refs(_inflation())],
        key=lambda ref: (ref.kind, ref.id),
    )
    for ref in refs:
        yield f"{ref.kind:<20} {ref.id:<28} {ref.file:<40} {ref.version}"


HEADER: Final = (
    "# terezy golden result -- one end-to-end projection, recorded.",
    "#",
    "# Produced by tests/golden/test_end_to_end_ovdp.py, which compares this whole file",
    "# against a fresh run. Read that module's docstring before changing anything here.",
    "#",
    "# To update deliberately:",
    "#     TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_end_to_end_ovdp.py",
    "#     git diff tests/golden/ovdp_synthetic_a.golden.txt",
    "# then read the diff and say in the commit message why each changed line is intended.",
    "#",
    "# Every amount is repr of a float64: exact and round-trippable, so this rendering is",
    "# STRICTER than the digest at the foot of the file, not merely as strict -- repr tells",
    "# -0.0 from 0.0 and the digest normalises it away. Each tax_charge below therefore",
    "# carries a -0.0 pinned by this text alone: a pin on how a figure prints, not a guard",
    "# on any figure. Provenance and the code version are deliberately absent; the",
    "# declaration files' digests are present.",
    "#",
    "# THE TERMS PROJECTED HERE ARE SYNTHETIC AND UNVERIFIED. No figure below describes a",
    "# bond anyone can buy, and none of them accounts for funding-route cost or exit cost.",
    "#",
    "# The nominal figures exclude inflation and say so. Beside them the real-terms slot",
    "# carries two figures that never mix: one deflated by declared CPI observations, one",
    "# by a declared belief about future inflation. The second is an ASSUMPTION on its",
    "# face -- the declared rate is a placeholder, not a forecast -- and the first refuses",
    "# today, because the declared series ends before this holding does. See",
    "# docs/METHODOLOGY.md.",
)


def _render(result: Projection, declarations: resolver.Declarations) -> str:
    """The whole artefact: the run, its inputs, its figures, its ledger, and its digest."""
    lines: list[str] = [*HEADER, ""]

    lines += ["== run ==", ""]
    lines += [
        f"instrument         {INSTRUMENT_ID}",
        f"owner_id           {OWNER_ID}",
        f"purchased_on       {PURCHASED_ON.isoformat()}",
        f"quantity           {QUANTITY!r}",
        f"cost               {_money(_holding().cost)}",
        f"horizon            {_horizon().start.isoformat()} .. {_horizon().end.isoformat()}",
        f"consumption_method {_assumptions().consumption_method}",
        f"coupon_policy      {_assumptions().coupon_policy}",
        f"canonical_encoding {manifest.ENCODING}",
        "",
    ]

    lines += ["== inputs ==", ""]
    lines += list(_inputs(declarations))
    lines += [""]

    lines += ["== figures ==", ""]
    lines += list(_figures(result))
    lines += [""]

    lines += ["== schedule ==", ""]
    lines += list(_schedule(result.schedule.rows))
    lines += [""]

    lines += ["== tax charges ==", ""]
    lines += list(_charges(result.charges))
    lines += [""]

    lines += ["== ledger ==", ""]
    lines += list(_ledger(result.ledger))
    lines += [""]

    lines += ["== digest ==", ""]
    lines += [
        "# sha256 over core.results.canonical.of_projection, taken by",
        "# data.manifest.digest_of_projection. Amounts reach it as float.hex(), so this",
        "# asserts bit-identity -- deliberately stricter than the project tolerance.",
        manifest.digest_of_projection(result),
        "",
    ]
    return "\n".join(lines)


# --- the artefact ---------------------------------------------------------------------


def _recorded() -> str:
    """The checked-in artefact, or a failure telling the reader how to produce one.

    A missing file is **not** regenerated silently. A golden file that reappeared on its
    own would make a deleted artefact indistinguishable from a passing run, which is the
    one failure mode a golden test cannot afford.
    """
    if not GOLDEN_FILE.is_file():
        pytest.fail(
            f"there is no golden artefact at {GOLDEN_FILE}. It is not regenerated "
            "automatically, because a file that reappeared on its own would make a "
            "deleted artefact indistinguishable from a passing run. Produce it "
            f"deliberately with {UPDATE_VARIABLE}=1 uv run pytest "
            "tests/golden/test_end_to_end_ovdp.py, then read the diff."
        )
    return GOLDEN_FILE.read_text(encoding="utf-8")


def _today() -> str:
    """Today's rendering of the run, and the artefact rewritten if that was asked for.

    The write happens here rather than in a fixture so that every test in this module
    updates the same one file from the same one rendering, and so that an update run still
    asserts afterwards -- against what it just wrote, which is the point of an update.
    """
    rendered = _render(*_run())
    if os.environ.get(UPDATE_VARIABLE):
        GOLDEN_FILE.write_text(rendered, encoding="utf-8")
    return rendered


def _run() -> tuple[Projection, resolver.Declarations]:
    declarations = _declarations()
    return _project(declarations), declarations


class TestTheRecordedResultIsStillTheResult:
    """The comparison the constitution asks for: today's output against yesterday's."""

    def test_the_whole_projection_matches_the_checked_in_artefact(self) -> None:
        """Line for line. A refactor that changes any figure fails here, naming it.

        Text equality rather than a tolerance, deliberately. This is not a comparison of
        hand arithmetic against float arithmetic -- the reason a tolerance exists at all --
        but of the same code on the same inputs against what it answered before, and there
        the tolerance would hide precisely the drift the artefact exists to catch. The
        hand-computed figures are checked separately, below, with the project tolerance.
        """
        assert _today() == _recorded(), (
            "the end-to-end result no longer matches the recorded artefact. If that is "
            "intended, update it deliberately and read the diff: see this module's "
            "docstring."
        )

    def test_the_recorded_digest_is_the_digest_of_todays_result(self) -> None:
        """The assertion isolated from the rendering that explains it.

        The text comparison above already covers the digest line, but a failure there
        points at whichever line differs first. This one says plainly whether the *result*
        changed, which is the question a reader has.
        """
        result, _ = _run()
        recorded = [
            line.strip()
            for line in _recorded().splitlines()
            if line.startswith(f"{manifest.ALGORITHM}:")
        ]
        assert recorded == [manifest.digest_of_projection(result)]

    def test_no_line_of_the_artefact_ends_in_whitespace(self) -> None:
        """So that an editor which strips trailing space cannot fail this suite.

        A golden file is only useful if the only thing that changes it is a change in the
        result. Trailing whitespace is invisible, is stripped by half the tools that would
        ever open this file, and would produce a failure about a coupon that did not move.
        """
        offenders = [
            number
            for number, line in enumerate(_today().splitlines(), start=1)
            if line != line.rstrip()
        ]
        assert not offenders, f"the rendering pads a line with trailing space: {offenders}"

    def test_the_artefact_names_the_declaration_files_it_was_produced_from(self) -> None:
        """A record of inputs nobody can identify is not a record (Principle III)."""
        declarations = _declarations()
        recorded = _recorded()
        for ref in (
            *manifest.input_refs(declarations),
            *manifest.inflation_input_refs(_inflation()),
        ):
            assert ref.file in recorded, f"the artefact does not name {ref.file}"
            assert ref.version in recorded, (
                f"{ref.file} has changed since the artefact was recorded, so the run this "
                "file describes was fed a different declaration"
            )


class TestTheArtefactDoesNotDependOnProvenance:
    """Filling in a ``verified_on`` must not move a recorded result. SC-005's other half."""

    def test_verifying_every_source_moves_neither_the_digest_nor_the_rendering(self) -> None:
        """The same run, every citation verified: byte-identical artefact.

        Provenance is excluded from the canonical form on purpose, and this asserts the
        consequence at the level of the artefact rather than of the form. Without it, a
        maintainer who verified the Tax Code citation would be met by a red golden test
        and no honest way to fix it.
        """
        unverified, declarations = _run()
        verified_declarations = _verified_declarations(declarations)
        verified = _project(verified_declarations)

        assert manifest.digest_of_projection(verified) == manifest.digest_of_projection(unverified)
        assert _render(verified, verified_declarations) == _render(unverified, declarations)

    def test_the_two_runs_really_do_differ_in_their_marks(self) -> None:
        """Otherwise the test above compares one run with itself and proves nothing."""
        unverified, declarations = _run()
        verified = _project(_verified_declarations(declarations))

        assert prov.is_unverified(unverified.hurdle.provenance), (
            "issue A's terms are synthetic and its tax citation unchecked, so the figure "
            "must be marked -- FR-015, and the expected first-run state"
        )
        assert not prov.is_unverified(verified.hurdle.provenance)
        assert prov.unverified_sources(unverified.hurdle.provenance)
        assert not prov.unverified_sources(verified.hurdle.provenance)


class TestTheArtefactAgreesWithTheHandComputedSchedule:
    """A golden file recorded from a broken run would agree with itself forever.

    So the figures the artefact carries are tied back to the arithmetic worked out by hand
    in ``tests/worked_examples/test_ovdp_schedule.py``. These are the assertions that use
    the project tolerance, because here float arithmetic really is being compared against
    hand arithmetic.
    """

    def test_the_four_coupons_total_exactly_two_years_of_interest(self) -> None:
        # 10 units x 1 000.00 x 15.5% = 1 550.00 a year; 181 + 184 + 181 + 184 = 730 days
        # = exactly two act/365 years, so the coupons come to 1 550.00 x 2 = 3 100.00.
        result, _ = _run()
        coupons = [row for row in result.schedule.rows if row.kind is EventKind.COUPON]
        assert len(coupons) == COUPON_COUNT
        assert is_close(sum(row.gross.amount for row in coupons), TOTAL_COUPONS)

    def test_the_principal_comes_back_at_par_on_the_adjusted_date(self) -> None:
        result, _ = _run()
        principal = [
            row for row in result.schedule.rows if row.kind is EventKind.PRINCIPAL_REPAYMENT
        ]
        assert len(principal) == 1
        assert_money_close(principal[0].gross, Money(PRINCIPAL, UAH, prov.EMPTY))
        # 2028-01-15 is a Saturday and the issue declares ``following``, so the money
        # arrives on the Monday while the accrual still runs to the 15th.
        assert principal[0].occurred_on == ADJUSTED_MATURITY

    def test_the_exempt_class_charges_exactly_zero_on_every_taxable_event(self) -> None:
        """SC-002. Zero because zeroes were recorded and summed, not because none were."""
        result, _ = _run()
        assert result.hurdle.total_tax.amount == 0.0
        assert len(result.charges) == COUPON_COUNT + 1, "four coupons and the redemption"
        for charge in result.charges:
            assert charge.provenance.sources, "the zero cites the exemption it applied"

    def test_every_negative_zero_in_the_artefact_is_a_charge_memo_and_nothing_else(self) -> None:
        """Finding the count rather than claiming it, and saying what the sign is worth.

        ``repr`` tells ``-0.0`` from ``0.0`` and ``canonical.of_number`` does not, so these
        are pinned by the rendered text and by nothing else. There is one per ``TAX_CHARGE``:
        ``memo_amount`` scales the charge by ``-0.0`` to keep it on the outflow side of the
        account at no magnitude, and no other figure in the run produces one. That the digest
        is indifferent to all five is the other half of the claim.
        """
        lines = GOLDEN_FILE.read_text(encoding="utf-8").splitlines()
        # The rendering puts an event's kind on its header line and its amount on the next,
        # so the kind a `-0.0` belongs to is the header immediately above it.
        rendered = [
            (lines[index - 1].split()[-1], line)
            for index, line in enumerate(lines)
            if "-0.0 UAH" in line
        ]

        assert len(rendered) == COUPON_COUNT + 1, rendered
        assert all("amount -0.0 UAH" in line for _, line in rendered)
        assert {kind for kind, _ in rendered} == {EventKind.TAX_CHARGE.value}, rendered
        assert canonical.of_number(-0.0) == canonical.of_number(0.0)

    def test_the_two_return_figures_agree_because_and_only_because_tax_is_zero(self) -> None:
        """FR-005: two figures, never one -- and the fact that they coincide here is a
        property of the exemption, not of the code that computes them."""
        result, _ = _run()
        assert is_close(
            result.hurdle.nominal_ytm.value,
            result.hurdle.nominal_cash_flow_return.value,
        )
        assert result.hurdle.nominal_ytm.value > 0.0


class TestFillingTheRealSlotChangedNothingNominal:
    """007 FR-014, and this feature's entire claim to being additive.

    *"This feature MUST NOT change how any nominal figure is computed, and MUST NOT change
    any realised amount, any tax figure, or any ranking. Filling the real slot is additive;
    every 001 behaviour is preserved bit-for-bit on identical inputs."*

    The artefact comparison above already covers all of that -- but it covers it as one
    assertion over 230 lines, and a reader who sees it go red cannot tell whether a coupon
    moved or a reason was reworded. These pin the figures that must **never** move, to the
    last bit, with the value written out. Feeding the run a CPI series is what makes the
    pinning worth doing: it is the change most likely to disturb something it should not.
    """

    NOMINAL_YTM: Final = 0.16058553778779106
    """001's recorded contractual yield, transcribed from the artefact before this feature
    touched it. A literal rather than a reference, so the two cannot drift together."""

    def test_the_contractual_yield_is_the_bit_that_feature_001_recorded(self) -> None:
        result, _ = _run()

        assert result.hurdle.nominal_ytm.value == self.NOMINAL_YTM

    def test_the_cash_flow_return_is_the_bit_that_feature_001_recorded(self) -> None:
        result, _ = _run()

        assert result.hurdle.nominal_cash_flow_return.value == self.NOMINAL_YTM

    def test_deflating_moves_no_realised_amount_and_no_tax_charge(self) -> None:
        """The same run with and without the deflation inputs: every amount identical.

        Not "close": identical. A deflation that touched a cash flow would be a defect of
        the first order, and the tolerance exists for hand arithmetic rather than for this.
        """
        declarations = _declarations()
        with_cpi, _ = _run()
        without = project.project(
            declarations.instruments[INSTRUMENT_ID],
            _holding(),
            _horizon(),
            _assumptions(),
            tax_classes=declarations.tax_classes,
        )
        assert isinstance(without, Projection)

        assert [row.gross.amount for row in with_cpi.schedule.rows] == [
            row.gross.amount for row in without.schedule.rows
        ]
        assert [row.tax.amount for row in with_cpi.schedule.rows] == [
            row.tax.amount for row in without.schedule.rows
        ]
        assert [row.net.amount for row in with_cpi.schedule.rows] == [
            row.net.amount for row in without.schedule.rows
        ]
        assert [charge.total.amount for charge in with_cpi.charges] == [
            charge.total.amount for charge in without.charges
        ]
        assert with_cpi.hurdle.total_tax.amount == without.hurdle.total_tax.amount

    def test_the_two_nominal_figures_are_identical_with_and_without_the_deflation(
        self,
    ) -> None:
        """The falsifier's other half: the *only* field that may differ is ``real``."""
        declarations = _declarations()
        with_cpi, _ = _run()
        without = project.project(
            declarations.instruments[INSTRUMENT_ID],
            _holding(),
            _horizon(),
            _assumptions(),
            tax_classes=declarations.tax_classes,
        )
        assert isinstance(without, Projection)

        assert with_cpi.hurdle.nominal_ytm == without.hurdle.nominal_ytm
        assert with_cpi.hurdle.nominal_cash_flow_return == without.hurdle.nominal_cash_flow_return
        assert with_cpi.hurdle.excludes == without.hurdle.excludes
        assert with_cpi.hurdle.accounts_for == without.hurdle.accounts_for
        assert with_cpi.hurdle.provenance == without.hurdle.provenance
        assert with_cpi.hurdle.real != without.hurdle.real


class TestTaxDepthChangedNothingAboutTheExemptPath:
    """009 FR-026 and SC-009, as three claims rather than one artefact comparison.

    Feature 009 stopped a tax charge from moving cash and gave the ledger a payment event.
    Neither may touch a year of exclusively exempt income, and the artefact comparison above
    already says so -- as one assertion over 230 lines, which tells a reader that *something*
    moved rather than *what*. These pin the two claims that matter separately, because they
    are separate: a statement of zero still exists, and **no cash moves for it**. Both are
    asserted below, against the shipped declarations rather than against a fixture.
    """

    def test_no_tax_charge_in_the_exempt_run_moves_any_cash(self) -> None:
        """Every charge is recorded, and every one of them settles nothing."""
        result, _ = _run()

        charges = [event for event in result.ledger.applied if event.kind is EventKind.TAX_CHARGE]
        assert len(charges) == COUPON_COUNT + 1, "one per coupon, plus the redemption"
        assert all(event.amount.amount == 0.0 for event in charges)

    def test_a_year_of_exclusively_exempt_income_produces_no_payment_event(self) -> None:
        """SC-009. A zero liability is settled by nothing at all, so no cash leaves.

        This is the assertion that would catch the exempt path growing a behaviour it should
        not have: a payment event of zero would be indistinguishable from a payment in the
        totals, and it would put a date in the ledger on which nothing happened.
        """
        result, _ = _run()

        assert not [event for event in result.ledger.applied if event.kind is EventKind.TAX_PAYMENT]

    def test_a_year_of_exclusively_exempt_income_is_assessed_at_zero_and_settles_nothing(
        self,
    ) -> None:
        """SC-009's other half, against the **shipped** declarations rather than a fixture.

        The statement exists and says zero *citing the exemption* -- a missing statement and a
        statement saying zero are different claims, and only the second one says the year was
        looked at (FR-006). And no cash moves for it, which is why this artefact cannot.
        """
        result, declarations = _run()
        rules = resolver.tax_rules_from_data_root(DATA_ROOT, declarations)["ua"]
        positions = resolver.tax_positions_from_data_root(DATA_ROOT)
        assert positions is not None
        filing, switches, _ = positions

        assessed = tax_year.statements(
            result.ledger,
            result.charges,
            rules=rules,
            tax_classes=declarations.tax_classes,
            filing=filing,
            switches=switches,
        )
        assert isinstance(assessed, tuple), assessed
        assert [statement.tax_year for statement in assessed] == [2026, 2027, 2028]
        for statement in assessed:
            assert statement.zero_because is tax_year.ZeroReason.EXEMPT
            assert tax_year.liability_total(statement.liability).amount == 0.0
            assert statement.treatment is tax_year.Treatment.OUTSIDE

        settled = settlement.settle(
            result.ledger.applied,
            assessed,
            owner_id=OWNER_ID,
            base_currency=UAH,
            method=lots.LotMethod.FIFO,
            horizon_end=date(2030, 1, 1),
        )
        assert isinstance(settled, settlement.Settlement), settled
        assert settled.payments == ()
        assert settled.outstanding == ()
        assert settled.stream == result.ledger.applied

    def test_the_exempt_zeroes_still_cite_the_exemption_that_produced_them(self) -> None:
        """A memo at zero cash is still evidence: ``memo_amount`` keeps the charge's sources.

        Building the amount with ``money.zero`` instead would have dropped the citation, and
        an uncited zero is indistinguishable from a rule that never ran (E11).
        """
        result, _ = _run()

        for event in result.ledger.applied:
            if event.kind is EventKind.TAX_CHARGE:
                assert event.amount.provenance.sources


class TestTheRealSlotSaysWhatItCanAndRefusesWhatItCannot:
    """007 FR-009 and FR-012, end to end on the declarations the project actually ships."""

    def test_the_realized_figure_refuses_and_names_the_months_it_is_missing(self) -> None:
        """The shipped series ends 2025-10 and this holding runs into 2028. That is the
        feature working, not a gap in it: re-running the fetcher is the fix, and the refusal
        is what stops a number being invented in the meantime (research.md D4)."""
        result, _ = _run()
        realized = result.hurdle.real.realized
        assert isinstance(realized, RealTermsUnavailable)

        assert CPI_SERIES_ID in realized.reason
        assert "2026-02" in realized.reason
        assert "2028-01" in realized.reason

    def test_the_assumed_figure_is_computed_and_labelled_an_assumption(self) -> None:
        """The other half of FR-009: the projected portion is answered, and says what it rests
        on. 1.16058553778779106 / 1.10 - 1 = 0.055077761625264454, the declared 10% belief."""
        result, _ = _run()
        assumed = result.hurdle.real.assumed
        assert isinstance(assumed, RealRate)

        assert is_close(assumed.value, 0.055077761625264454)
        assert assumed.basis == "declared_assumption"
        assert assumed.series_id == "owner_placeholder_inflation"

    def test_the_two_figures_are_never_the_same_kind_of_answer(self) -> None:
        """One refuses and one answers, in the same result, and the artefact shows both."""
        result, _ = _run()

        assert isinstance(result.hurdle.real.realized, RealTermsUnavailable)
        assert isinstance(result.hurdle.real.assumed, RealRate)
