"""The projection's canonical form: composed from the ledger's, and free of provenance.

Two properties, both of which would be easy to lose and neither of which any gate sees.

**It composes rather than replaces.** ``ledger.canonical.of_result`` keeps its
``LedgerState`` signature, and ``results.canonical.of_projection`` calls it for the ledger
half. Asserted by equality against a direct call, so a future refactor that quietly
reimplemented the ledger's rendering here -- and could then disagree with it -- fails.

**Provenance is excluded, on purpose.** Filling in a ``verified_on`` changes what the
result *says about its sources* and changes no computed amount, so it must not change the
canonical form: otherwise C4 (determinism) fails whenever somebody verifies a figure, and
the only available fix would be to stop trusting C4. The unverified mark is a separate
claim, asserted separately by E5.

The digest itself is not tested here and does not exist here: hashing implies
serialisation, so it lives in ``terezy.data.manifest``. What this module tests is the
structural form the digest will be taken over.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from terezy.core.ledger import canonical as ledger_canonical
from terezy.core.ledger import engine
from terezy.core.ledger.accounts import CashBalance
from terezy.core.ledger.events import CausationKind, CausationRef, Event, EventKind, LotRef
from terezy.core.ledger.lots import Disposal, Lot, Position
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.rates import NominalRate, RealBasis, RealRate, RealTermsUnavailable
from terezy.core.results import canonical, hurdle, project
from terezy.core.results.project import Projection
from terezy.core.routes import capacity
from terezy.data import manifest
from tests import synthetic

UAH = Currency.UAH


def _projection(*, verified: bool) -> Projection:
    """The synthetic holding, with its terms' source either verified or not.

    Only the verification *date* differs between the two, which is precisely the change
    that must leave the canonical form untouched.
    """
    source = SourceRef(
        id="synthetic:terms",
        citation="SYNTHETIC FIXTURE -- invented bond terms.",
        retrieved_on=date(2026, 8, 21),
        verified_on=date(2026, 8, 21) if verified else None,
    )
    provenance = prov.of([source])
    terms = synthetic.terms(
        face_value=Money(1000.0, UAH, provenance),
        provenance=provenance,
    )
    outcome = project.project(
        synthetic.declaration(terms=terms),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection)
    return outcome


def test_the_ledger_half_is_the_ledgers_own_rendering() -> None:
    result = _projection(verified=False)
    assert canonical.of_projection(result)[0] == ledger_canonical.of_result(result.ledger)


def test_verifying_a_source_does_not_change_the_canonical_form() -> None:
    """The exclusion that matters: a documentation update must not move the digest."""
    assert canonical.of_projection(_projection(verified=False)) == canonical.of_projection(
        _projection(verified=True)
    )


def test_the_mark_itself_still_differs_so_the_test_above_is_not_vacuous() -> None:
    """Guard against the previous test passing because both runs were identical anyway.

    The two projections really do carry different provenance -- the terms source is
    verified in one and not the other -- so the canonical forms agreeing is a property of
    the form rather than of the inputs. Note that both results remain *unverified overall*,
    because the purchase and the exemption are unverified in either case: one unverified
    input taints the figure, which is the intended asymmetry.
    """
    unverified, verified = _projection(verified=False), _projection(verified=True)
    assert _terms_source(verified).verified_on is not None
    assert _terms_source(unverified).verified_on is None
    assert prov.is_unverified(unverified.hurdle.provenance)
    assert prov.is_unverified(verified.hurdle.provenance)


def _terms_source(result: Projection) -> SourceRef:
    """The one source whose verification date the two projections disagree about."""
    (source,) = [ref for ref in result.hurdle.provenance.sources if ref.id == "synthetic:terms"]
    return source


def test_every_amount_is_rendered_as_an_exact_hexadecimal_float() -> None:
    """Bit-identity, not agreement to some number of decimals (research.md D5)."""
    figures = canonical.of_hurdle_rate(_projection(verified=False).hurdle)
    assert figures[0] == float.hex(_projection(verified=False).hurdle.nominal_ytm.value)
    assert isinstance(figures[0], str)


def _real(value: float, *, basis: RealBasis = "realized_cpi", series_id: str = "s") -> RealRate:
    """A real figure with the fields feature 007 gave it, so the digest can be compared."""
    return RealRate(
        value=value,
        basis=basis,
        series_id=series_id,
        window=Window(first="2026-01", last="2026-12"),
        provenance=prov.EMPTY,
    )


def test_the_real_slot_is_tagged_so_absence_cannot_look_like_zero() -> None:
    """A real rate of zero and "there is no real rate" are opposite claims."""
    assert canonical.of_real_figure(_real(0.0)) == (
        "real",
        float.hex(0.0),
        "realized_cpi",
        "s",
        "2026-01",
        "2026-12",
    )
    assert canonical.of_real_figure(RealTermsUnavailable(reason="no CPI series")) == (
        "unavailable",
        "no CPI series",
    )
    assert canonical.of_real_figure(_real(0.0)) != canonical.of_real_figure(
        RealTermsUnavailable(reason="no CPI series")
    )


def test_the_same_number_on_two_different_bases_digests_differently() -> None:
    """007 FR-010: an observed figure and an assumed one are two claims, never one.

    The values agree; the claims do not. A canonical form that dropped ``basis`` would report
    "deflated by measured prices" and "deflated by a belief" as the same result -- which is
    the exact confusion this feature exists to prevent, arriving through the digest.
    """
    assert canonical.of_real_figure(_real(0.05, basis="realized_cpi")) != canonical.of_real_figure(
        _real(0.05, basis="declared_assumption")
    )


def test_the_same_number_against_two_different_series_digests_differently() -> None:
    """FR-011: a real rate carries what it is real *against*, and the digest carries it too."""
    assert canonical.of_real_figure(_real(0.05, series_id="ua")) != canonical.of_real_figure(
        _real(0.05, series_id="us")
    )


def test_the_slot_renders_both_figures_in_a_fixed_order() -> None:
    """Realized first, assumed second, always -- so the digest depends on which is which."""
    slot = hurdle.RealTerms(
        realized=_real(0.05),
        assumed=_real(0.05, basis="declared_assumption", series_id="belief"),
    )
    rendered = canonical.of_real_terms(slot)

    assert rendered == (
        canonical.of_real_figure(slot.realized),
        canonical.of_real_figure(slot.assumed),
    )
    assert rendered[0] != rendered[1]


def test_swapping_the_two_real_figures_changes_the_canonical_form() -> None:
    """The falsifier for the ordering claim: a set-like rendering would agree here."""
    realized, assumed = _real(0.05), _real(0.07, basis="declared_assumption", series_id="belief")

    assert canonical.of_real_terms(
        hurdle.RealTerms(realized=realized, assumed=assumed)
    ) != canonical.of_real_terms(hurdle.RealTerms(realized=assumed, assumed=realized))


def test_both_boundary_sets_are_emitted_in_a_stable_order() -> None:
    """A ``frozenset``'s iteration order is not a promise; the digest needs one."""
    hurdle = _projection(verified=False).hurdle
    rendered = canonical.of_hurdle_rate(hurdle)
    assert rendered[4] == tuple(sorted(hurdle.accounts_for))
    assert rendered[5] == tuple(sorted(hurdle.excludes))
    assert canonical.of_hurdle_rate(hurdle) == canonical.of_hurdle_rate(
        replace(
            hurdle,
            accounts_for=frozenset(sorted(hurdle.accounts_for, reverse=True)),
            excludes=frozenset(sorted(hurdle.excludes, reverse=True)),
        )
    )


def test_a_claim_added_to_accounts_for_alone_moves_the_digest() -> None:
    """The mechanism ``ACCOUNTS_FOR`` claims, made real.

    Naming what is included beside what is excluded is only a guard if *both* reach the
    digest. It originally emitted ``excludes`` alone, so a term added to ``accounts_for``
    -- a claim that the figure is now net of something it is not -- changed nothing a
    reviewer or a golden file would notice.
    """
    hurdle = _projection(verified=False).hurdle
    overclaimed = replace(hurdle, accounts_for=hurdle.accounts_for | {"funding route costs (in)"})
    assert canonical.of_hurdle_rate(hurdle) != canonical.of_hurdle_rate(overclaimed)


def test_the_schedule_records_the_conventions_that_placed_its_dates() -> None:
    """FR-021 reaches the canonical form too: the convention is part of the answer."""
    result = _projection(verified=False)
    rendered = canonical.of_schedule(result.schedule)
    assert rendered[0] == "UAH"
    assert rendered[1] == tuple(canonical.of_row(row) for row in result.schedule.rows)
    assert result.schedule.rows
    for row in result.schedule.rows:
        assert canonical.of_row(row)[7] == ("semiannual", "act/365", "following")


def test_every_charge_names_the_class_that_produced_it() -> None:
    """Recording a zero is only useful if the zero says which rule charged it."""
    result = _projection(verified=False)
    for rendered, charge in zip(
        [canonical.of_charge(charge) for charge in result.charges],
        result.charges,
        strict=True,
    ):
        assert rendered[5] == charge.tax_class_id


# ---------------------------------------------------------------------------
# The encoding tag moves whenever the canonical shape does
# ---------------------------------------------------------------------------

CANONICAL_SHAPE_BY_ENCODING = {
    "terezy-canonical-v3": (
        "((i,i,i),s,s,((s,(s,s),(s,s),(s,s))),"
        "((s,s,(s,s),(s,s),((s,s,(i,i,i),s,(s,s),(s,s),s)))),"
        "((i,(i,i,i),s,s,(s,s),(s,s),(s,s),(s,s),(s,s),(s,s),(s,s),(s,s),((s,s)),(s,s,s))),"
        "((i,(i,i,i),s,(s,s),s,(s,s,s),(s,s),s,i,s)),"
        "((s,i,i,(s,s))))"
        "|"
        "(s,s,((s,s,s,s,s,s),(s,s,s,s,s,s)),(s,s),(s),(s))"
    ),
}
"""One recorded shape fingerprint per encoding tag, and exactly one entry: the current tag.

The reproducibility contract (``manifest.ENCODING``'s own docstring): *bump it when the
encoding changes shape; every previously recorded digest then visibly belongs to a
different scheme instead of silently disagreeing*. Feature 002 broke that once -- the
canonical tuple gained ``capacity_pool`` and the capacity accumulator while the tag stayed
``terezy-canonical-v1``, so pre-002 digests silently disagreed under an unchanged name.
This pinned pair is what makes the next such change a red test naming the remedy.

⚙ **Two fingerprints, joined by a pipe, since feature 007** -- the ledger's and the figures'.
The pin used to cover ``ledger.canonical.of_result`` alone, which left the whole of
``results.canonical`` outside it: 007 changed the real slot from one tagged pair to two and
the pin would not have noticed, which is exactly the silent disagreement it exists to
prevent. Anything the projection's canonical form is built from belongs in here.

**v3** (2026-08): feature 007 filled the reserved real-terms slot. Where a v2 projection
rendered one ``(tag, value)`` pair, a v3 one renders two figures, each carrying its basis,
its series and its window -- so a v2 digest of the same projection no longer agrees with one
taken here, and the tag says so rather than letting the two disagree under one name.
"""


def _shape(value: ledger_canonical.Canonical) -> str:
    """The structure of a canonical value with its content erased: arity and types only.

    ``None`` renders as ``0``, an integer as ``i``, a string as ``s``, and a tuple as its
    elements' shapes in parentheses -- so two canonical forms have equal shapes exactly
    when they differ only in content, which is what a digest scheme's identity is.
    """
    if value is None:
        return "0"
    if isinstance(value, int):
        return "i"
    if isinstance(value, str):
        return "s"
    return "(" + ",".join(_shape(element) for element in value) + ")"


def _representative_state() -> engine.LedgerState:
    """One ledger state with every optional branch populated, exactly once each.

    Hand-built rather than folded so the fingerprint depends on the *shape* of the
    canonical form alone and not on how many coupons a fixture happens to pay: one
    account, one position with one lot, one disposal, one event, one capacity entry, and
    no ``None`` anywhere a record could carry a value -- an optional field left absent
    would hide its populated shape from the fingerprint.
    """
    sources = prov.EMPTY
    cause = CausationRef(kind=CausationKind.ROUTE_TERM, id="fixture", detail="shape fixture")
    one = Money(1.0, UAH, sources)
    lot = Lot(
        lot_id="lot-1",
        instrument_id="fixture",
        acquired_on=date(2026, 8, 21),
        quantity=1.0,
        cost_trade_ccy=one,
        cost_base_ccy=one,
        fx_rate_used=1.0,
    )
    return engine.LedgerState(
        as_of=date(2026, 8, 21),
        base_currency=UAH,
        consumption_method="fifo",
        accounts={
            UAH: CashBalance(currency=UAH, inflows=one, outflows=one, balance=one),
        },
        positions={
            "fixture": Position(
                instrument_id="fixture",
                quantity=1.0,
                basis_trade_ccy=one,
                basis_base_ccy=one,
                lots=(lot,),
            )
        },
        disposals=(
            Disposal(
                sequence=1,
                occurred_on=date(2026, 8, 21),
                instrument_id="fixture",
                quantity=1.0,
                proceeds_trade_ccy=one,
                proceeds_base_ccy=one,
                consumed_basis_trade_ccy=one,
                consumed_basis_base_ccy=one,
                allocated_fees_trade_ccy=one,
                allocated_fees_base_ccy=one,
                realised_gain_trade_ccy=one,
                realised_gain_base_ccy=one,
                consumed_from=(("lot-1", 1.0),),
                caused_by=cause,
            ),
        ),
        applied=(
            Event(
                sequence=1,
                occurred_on=date(2026, 8, 21),
                kind=EventKind.RAMP_MOVEMENT,
                amount=one,
                owner_id="owner-1",
                caused_by=cause,
                lot_ref=LotRef(instrument_id="fixture", lot_id="lot-1"),
                quantity=1.0,
                allocated_to=1,
                capacity_pool="fixture_rail",
            ),
        ),
        capacity={capacity.CapacityKey(pool="fixture_rail", year=2026, month=8): one},
    )


def _representative_hurdle() -> hurdle.HurdleRate:
    """One hurdle rate with every optional branch populated, exactly once each.

    Both real figures hold a *rate* rather than an unavailable value, because the populated
    shape is the larger one and an absent figure would hide it from the fingerprint -- the
    same reasoning ``_representative_state`` gives for leaving no ``None`` in the ledger.
    """
    return hurdle.HurdleRate(
        nominal_ytm=NominalRate(0.15),
        nominal_cash_flow_return=NominalRate(0.15),
        real=hurdle.RealTerms(
            realized=_real(0.05),
            assumed=_real(0.05, basis="declared_assumption", series_id="belief"),
        ),
        total_tax=Money(0.0, UAH, prov.EMPTY),
        accounts_for=frozenset({"tax"}),
        excludes=frozenset({"inflation"}),
        provenance=prov.EMPTY,
    )


def test_the_encoding_tag_moves_whenever_the_canonical_shape_does() -> None:
    """The reproducibility contract, made mechanical (manifest.py's own promise).

    A digest is comparable only against digests of the same scheme, and the scheme is
    named by ``manifest.ENCODING``. So a change to the canonical tuple's shape under an
    unchanged tag makes old and new digests silently disagree while claiming one scheme --
    which is exactly what a golden digest flipping under an unchanged tag looks like. This
    test fails on either half changing alone, and its message says which line to move.

    ⚙ **Both halves of the projection's form are fingerprinted** (007). Pinning the ledger
    alone left every figure outside the pin, which is where 007's own change landed.
    """
    fingerprint = "|".join(
        (
            _shape(ledger_canonical.of_result(_representative_state())),
            _shape(canonical.of_hurdle_rate(_representative_hurdle())),
        )
    )
    assert manifest.ENCODING in CANONICAL_SHAPE_BY_ENCODING, (
        f"manifest.ENCODING is {manifest.ENCODING!r}, which this test does not know. "
        "Record the tag with its shape fingerprint in CANONICAL_SHAPE_BY_ENCODING -- and "
        "keep exactly one entry, because a digest names the scheme it was taken under."
    )
    assert CANONICAL_SHAPE_BY_ENCODING[manifest.ENCODING] == fingerprint, (
        "the canonical tuple's shape changed while manifest.ENCODING stayed "
        f"{manifest.ENCODING!r}. Every previously recorded digest would now silently "
        "disagree under an unchanged scheme name. Bump ENCODING to the next version, "
        "regenerate the golden artefacts by their documented procedure, and record the "
        f"new shape here.\nrecorded: {CANONICAL_SHAPE_BY_ENCODING[manifest.ENCODING]}\n"
        f"actual:   {fingerprint}"
    )
