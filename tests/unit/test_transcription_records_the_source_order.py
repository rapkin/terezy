"""SC-018: what the source published, kept as a fact about the source (FR-020a).

An observation about **the source**, not about the money, and the one that silently
disappears: that a publisher lists the repayment of principal after a coupon dated later than
it is a fact about how that publisher reports, and sorting the list is precisely the act that
would delete it.

The fixture is modelled on Inzhur's published list for `UA4000235865` and is deliberately
**not** it. 016 declared that issue from the ISSUER's depository, which puts both final
payments on 2026-09-16, the ordinary way a bond ends -- so the ordering is the seller's
transcription error and not a fact about how the issuer pays, and there is no real instance of
what FR-020a exists for. The mechanism survives its example being a mistake, and a seller's
error is exactly the kind of thing recording a published order preserves.

**The second half is what makes the field evidence rather than boilerplate**: rewrite the
declared order to the ascending one and the record does not survive, because a field that
can be filled in without saying anything has stopped tracking anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terezy.core.instruments.interface import EnumeratedTerms, PaymentKind
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

DECLARATION = data_roots.FIXTURES / "instruments" / "enumerated_out_of_order.toml"
DECLARED_ORDER = 'published_in_order = ["2026-10-01", "2027-04-01", "2027-03-31"]'


def _terms(path: Path) -> EnumeratedTerms:
    terms = loader.enumerated_instrument_from_file(path).terms
    assert isinstance(terms, EnumeratedTerms)
    return terms


def _rewritten(tmp_path: Path, order: str | None) -> Path:
    text = DECLARATION.read_text(encoding="utf-8")
    assert DECLARED_ORDER in text, "the fixture no longer declares a published order"
    path = tmp_path / DECLARATION.name
    path.write_text(text.replace(DECLARED_ORDER, order or ""), encoding="utf-8")
    return path


class TestTheShippedFixtureCarriesTheRecord:
    def test_the_payments_are_in_date_order(self) -> None:
        """Ordering is settled at transcription. The loader neither sorts nor accepts an
        unordered list, so a declaration that reached the engine is already in order."""
        dates = [payment.on for payment in _terms(DECLARATION).payments]
        assert dates == sorted(dates)

    def test_the_principal_falls_before_the_final_coupon(self) -> None:
        """The shape of the real counterexample: a bond that returns its principal a day
        before it pays its last coupon."""
        payments = _terms(DECLARATION).payments
        principal = next(p for p in payments if p.pays is PaymentKind.PRINCIPAL_REPAYMENT)
        assert principal.on < max(p.on for p in payments)

    def test_the_source_s_own_order_is_recorded_and_differs(self) -> None:
        terms = _terms(DECLARATION)
        assert terms.published_in_order is not None
        assert terms.published_in_order != tuple(payment.on for payment in terms.payments)

    def test_the_recorded_order_is_a_rearrangement_of_these_very_payments(self) -> None:
        terms = _terms(DECLARATION)
        assert terms.published_in_order is not None
        assert sorted(terms.published_in_order) == sorted(p.on for p in terms.payments)


class TestTheFieldTracksTheSourceRatherThanBeingBoilerplate:
    def test_rewriting_it_to_the_ascending_order_removes_the_record(self, tmp_path: Path) -> None:
        """SC-018's second half, and it is a **refusal** rather than a silently accepted
        no-op: a declaration stating the order its payments are already in records no
        difference, and accepting it would let the field be filled in by habit."""
        ascending = 'published_in_order = ["2026-10-01", "2027-03-31", "2027-04-01"]'
        with pytest.raises(DeclarationError) as raised:
            loader.enumerated_instrument_from_file(_rewritten(tmp_path, ascending))
        assert raised.value.field_path == "instrument.schedule.published_in_order"
        assert "records no difference" in raised.value.problem

    def test_omitting_it_loads_and_records_nothing(self, tmp_path: Path) -> None:
        """The ordinary case: a source that published in date order leaves nothing to keep."""
        assert _terms(_rewritten(tmp_path, None)).published_in_order is None

    def test_an_order_over_other_dates_is_refused(self, tmp_path: Path) -> None:
        """It records what the source published. A list that is not these payments cannot
        be that, whatever else it might be."""
        elsewhere = 'published_in_order = ["2026-10-01", "2027-04-01", "2028-01-01"]'
        with pytest.raises(DeclarationError) as raised:
            loader.enumerated_instrument_from_file(_rewritten(tmp_path, elsewhere))
        assert "rearrangement" in raised.value.problem


def test_the_loader_would_have_refused_the_list_as_the_source_published_it(
    tmp_path: Path,
) -> None:
    """The point of the whole record, asserted rather than described: transcribed in the
    order the source gave, this declaration does not load. Sorting it is a human step, and
    the record is what stops that step being invisible."""
    entry = "  [[instrument.schedule.payment]]"
    head, first, principal, final = DECLARATION.read_text(encoding="utf-8").split(entry)
    as_published = f"{head}{entry}{first}{entry}{final}{entry}{principal}"
    path = tmp_path / "as_published.toml"
    path.write_text(as_published.replace(DECLARED_ORDER, ""), encoding="utf-8")

    with pytest.raises(DeclarationError) as raised:
        loader.enumerated_instrument_from_file(path)
    assert "ascending date order" in raised.value.problem
