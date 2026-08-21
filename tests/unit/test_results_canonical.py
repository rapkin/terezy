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
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.rates import RealRate, RealTermsUnavailable
from terezy.core.results import canonical, project
from terezy.core.results.project import Projection
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


def test_the_real_slot_is_tagged_so_absence_cannot_look_like_zero() -> None:
    """A real rate of zero and "there is no real rate" are opposite claims."""
    assert canonical.of_real_terms(RealRate(0.0)) == ("real", float.hex(0.0))
    assert canonical.of_real_terms(RealTermsUnavailable(reason="not modelled")) == (
        "unavailable",
        "not modelled",
    )
    assert canonical.of_real_terms(RealRate(0.0)) != canonical.of_real_terms(
        RealTermsUnavailable(reason="not modelled")
    )


def test_the_exclusions_are_emitted_in_a_stable_order() -> None:
    """A ``frozenset``'s iteration order is not a promise; the digest needs one."""
    hurdle = _projection(verified=False).hurdle
    rendered = canonical.of_hurdle_rate(hurdle)[4]
    assert rendered == tuple(sorted(hurdle.excludes))
    assert canonical.of_hurdle_rate(hurdle) == canonical.of_hurdle_rate(
        replace(hurdle, excludes=frozenset(sorted(hurdle.excludes, reverse=True)))
    )


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
