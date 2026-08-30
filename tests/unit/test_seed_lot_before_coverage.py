"""SC-022: the three sites that read a generative field answer for both forms.

FR-011a's observation, and the reason the change was small: `core.ledger.seeds` never needed
an **issue date**. It needed *the earliest date from which this instrument's terms are
known*, and it asked for the only spelling that existed. Both forms answer that -- one with
its issue date, one with its coverage start -- so the site keeps one question and gains an
answer rather than gaining a case.

What is asserted here is that the refusal is **the same typed failure** on both sides, and
that the site did not acquire a test of which form it was given: the message names whichever
term the declaration states, because the declaration is what says it.
"""

from __future__ import annotations

from datetime import date, timedelta

from terezy.core.errors import InconsistentTerms
from terezy.core.instruments import terms as instrument_terms
from terezy.core.ledger import seeds
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.data.declarations import resolver
from tests import tuple_registries as fixtures

DECLARED = resolver.from_data_root(fixtures.DATA_ROOT).instruments
GENERATIVE = "ovdp_synthetic_a"
ENUMERATED = "ovdp_enumerated_a"
OPENS_ON = date(2026, 8, 1)


def _lot(instrument_id: str, acquired_on: date) -> SeedLot:
    return SeedLot(
        owner_id="owner-1",
        is_synthetic=True,
        lot_id=f"seed-{instrument_id}",
        declared_at=f"tests/test_seed_lot_before_coverage#{instrument_id}",
        instrument_id=instrument_id,
        quantity=1.0,
        acquired_on=acquired_on,
        cost=Money(1000.0, Currency.UAH, prov.EMPTY),
        basis=seeds.KNOWN,
    )


def _refusal(instrument_id: str, *, days_early: int) -> InconsistentTerms:
    known = instrument_terms.known_from(DECLARED[instrument_id].terms)
    outcome = seeds.opening_events(
        (_lot(instrument_id, known.on - timedelta(days=days_early)),),
        DECLARED,
        opens_on=OPENS_ON,
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    return outcome


class TestALotAcquiredBeforeTheTermsAreKnown:
    def test_both_forms_refuse_with_the_same_typed_failure(self) -> None:
        for instrument_id in (GENERATIVE, ENUMERATED):
            refusal = _refusal(instrument_id, days_early=1)
            assert refusal.first_term == "seed.acquired_on"

    def test_each_refusal_names_the_term_its_own_declaration_states(self) -> None:
        """Not a branch in `seeds`: the declaration answers with the field path, because
        the two forms genuinely state the date in different places."""
        assert _refusal(GENERATIVE, days_early=1).second_term == "instrument.terms.issue_date"
        assert _refusal(ENUMERATED, days_early=1).second_term == "instrument.schedule.covers_from"

    def test_each_refusal_reads_in_its_own_declaration_s_words(self) -> None:
        assert "was issued on" in _refusal(GENERATIVE, days_early=1).reason
        assert "publishes its payments from" in _refusal(ENUMERATED, days_early=1).reason

    def test_a_lot_acquired_on_that_very_date_is_admitted_in_both_forms(self) -> None:
        for instrument_id in (GENERATIVE, ENUMERATED):
            known = instrument_terms.known_from(DECLARED[instrument_id].terms)
            opened = seeds.opening_events(
                (_lot(instrument_id, known.on),), DECLARED, opens_on=OPENS_ON
            )
            assert isinstance(opened, tuple), opened
            assert len(opened) == 1

    def test_the_lot_is_never_silently_re_dated(self) -> None:
        """Moving it would change the acquisition date every holding-period rule and every
        consumption order is measured from."""
        for instrument_id in (GENERATIVE, ENUMERATED):
            assert "not silently re-dated" in _refusal(instrument_id, days_early=30).reason


class TestTheQuestionIsOneQuestion:
    def test_the_two_declarations_answer_it_differently_and_both_answer_it(self) -> None:
        generative = instrument_terms.known_from(DECLARED[GENERATIVE].terms)
        enumerated = instrument_terms.known_from(DECLARED[ENUMERATED].terms)
        assert generative.on != enumerated.on
        assert generative.term != enumerated.term

    def test_the_answer_is_what_a_third_form_would_have_to_supply(self) -> None:
        """The shape of the seam, asserted rather than described: a form that could not
        answer would have to say so **in the answer**, not leave the caller to notice."""
        for declared in DECLARED.values():
            answer = instrument_terms.known_from(declared.terms)
            assert isinstance(answer.on, date)
            assert answer.term.startswith("instrument.")
            assert answer.as_declared

    def test_a_seed_lot_needs_no_change_when_a_form_is_added(self) -> None:
        """The regression this whole file guards: `seeds._inconsistency` reads one date and
        one field path, and would read the same two for a form nobody has written."""
        source = fixtures.DATA_ROOT.parent / "src" / "terezy" / "core" / "ledger" / "seeds.py"
        assert "issue_date" not in source.read_text(encoding="utf-8")


def test_a_lot_acquired_after_the_ledger_opens_is_still_the_other_refusal() -> None:
    """The two guards are separate facts and stay separate: one is about the declaration,
    the other about the run."""
    outcome = seeds.opening_events(
        (_lot(ENUMERATED, OPENS_ON + timedelta(days=1)),), DECLARED, opens_on=OPENS_ON
    )
    assert isinstance(outcome, InconsistentTerms), outcome
    assert outcome.second_term == "projection.opens_on"
