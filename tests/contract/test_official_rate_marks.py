"""The mark and the age reach every figure struck through an official rate.

SC-005 and SC-006, and Principle I's clause that a derived figure losing its parent's mark is
a defect of the top severity class. An official rate is the single input that turns a foreign
amount into a legal one, so an unmarked tax figure resting on an unverified rate is exactly
the confidently-wrong number this project exists to refuse.

**Both directions are checked**, because a propagation test that only runs one way passes for
half the right reason: an unverified *rate* must mark a base struck from a verified amount,
and a marked *amount* must survive a fully verified rate. Neither side launders the other.

**Ageing goes through** ``staleness.staleness_of_sources``, which reads each citation's own
``kind``. That is the only call that works here: by the time a liability rests on the rate,
the amount, the tax class's dated entry and the timing rule, no record is in hand to name a
threshold.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.tax import official_rate
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError
from tests import official_rates

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_KINDS = REPO_ROOT / "data" / "observation_kinds.toml"

ON_DATE = date(2026, 3, 2)
RETRIEVED_ON = official_rates.RETRIEVED_ON

VERIFIED_AMOUNT = Money(
    100.0,
    Currency.USD,
    prov.of(
        [
            SourceRef(
                id="tests/official_rate_marks#amount",
                citation="SYNTHETIC FIXTURE -- an invented receipt.",
                retrieved_on=RETRIEVED_ON,
                verified_on=RETRIEVED_ON,
                kind="bond_terms",
            )
        ]
    ),
)

MARKED_AMOUNT = Money(
    100.0,
    Currency.USD,
    prov.of(
        [
            SourceRef(
                id="tests/official_rate_marks#unverified-amount",
                citation="SYNTHETIC FIXTURE -- an invented receipt nobody has checked.",
                retrieved_on=RETRIEVED_ON,
                verified_on=None,
                kind="bond_terms",
            )
        ]
    ),
)


def _struck(
    amount: Money, *, verified_on: date | None, retrieved_on: date = RETRIEVED_ON
) -> official_rate.TaxCurrencyConversion:
    series = official_rates.series(
        [(ON_DATE, 41.5)], verified_on=verified_on, retrieved_on=retrieved_on
    )
    struck = official_rate.strike_base(amount, series, tax_currency=Currency.UAH, on_date=ON_DATE)
    assert isinstance(struck, official_rate.TaxCurrencyConversion), struck
    return struck


class TestTheMarkTravelsInBothDirections:
    def test_an_unverified_rate_marks_a_base_struck_from_a_verified_amount(self) -> None:
        struck = _struck(VERIFIED_AMOUNT, verified_on=None)

        assert prov.is_unverified(struck.base.provenance)
        responsible = {ref.id for ref in prov.unverified_sources(struck.base.provenance)}
        assert responsible == {"synthetic:official_rate:2026-03-02"}

    def test_a_marked_amount_survives_a_fully_verified_rate(self) -> None:
        """Converting a marked amount never launders the mark."""
        struck = _struck(MARKED_AMOUNT, verified_on=RETRIEVED_ON)

        assert prov.is_unverified(struck.base.provenance)
        responsible = {ref.id for ref in prov.unverified_sources(struck.base.provenance)}
        assert responsible == {"tests/official_rate_marks#unverified-amount"}

    def test_a_verified_rate_and_a_verified_amount_leave_no_mark(self) -> None:
        """So the two assertions above fail for the reason they name, not by construction."""
        struck = _struck(VERIFIED_AMOUNT, verified_on=RETRIEVED_ON)

        assert not prov.is_unverified(struck.base.provenance)

    def test_the_base_rests_on_the_rate_as_well_as_on_the_amount(self) -> None:
        struck = _struck(VERIFIED_AMOUNT, verified_on=RETRIEVED_ON)

        assert {ref.id for ref in struck.base.provenance.sources} == {
            "tests/official_rate_marks#amount",
            "synthetic:official_rate:2026-03-02",
        }


class TestAnAgedRateReportsItsStalenessOnWhatItStruck:
    """SC-006, through the citation's own kind -- the only thing that survives the merge."""

    def _verdict(self, *, days_old: int) -> staleness.StalenessVerdict:
        struck = _struck(VERIFIED_AMOUNT, verified_on=None)
        return staleness.staleness_of_sources(
            struck.base.provenance,
            official_rates.KINDS | {"bond_terms": _bond_terms_kind()},
            as_of=RETRIEVED_ON + timedelta(days=days_old),
        )

    def test_a_rate_past_its_threshold_names_the_observation_and_the_threshold(self) -> None:
        verdict = self._verdict(days_old=30)

        assert staleness.any_stale(verdict)
        stale = next(s for s in verdict.stale if s.kind_id == "official_rate")
        assert stale.source_id == "synthetic:official_rate:2026-03-02"
        assert stale.threshold_days == 7
        assert stale.age_days == 30
        assert stale.overdue_days == 23

    def test_a_freshly_retrieved_rate_produces_no_staleness_warning(self) -> None:
        verdict = self._verdict(days_old=1)

        assert not staleness.any_stale(verdict)
        assert "synthetic:official_rate:2026-03-02" in verdict.assessed


class TestTheKindItselfCannotExistWithoutAThreshold:
    """FR-006's other half: no permissive default, and a kind without one fails at load."""

    def test_the_shipped_file_declares_the_official_rate_kind_with_a_threshold(self) -> None:
        declared = {kind.id: kind for kind in loader.observation_kinds_from_file(SHIPPED_KINDS)}

        assert declared["official_rate"].staleness_days > 0
        assert declared["official_rate"].note

    def test_declaring_the_kind_without_a_threshold_fails_at_load(self, tmp_path: Path) -> None:
        path = tmp_path / "observation_kinds.toml"
        path.write_text(
            '[[kind]]\nid = "official_rate"\nnote = "SYNTHETIC FIXTURE."\n', encoding="utf-8"
        )

        with pytest.raises(DeclarationError) as caught:
            loader.observation_kinds_from_file(path)

        assert "staleness_days" in str(caught.value)


def _bond_terms_kind() -> staleness.ObservationKind:
    return staleness.ObservationKind(
        id="bond_terms",
        staleness_days=365,
        note="SYNTHETIC FIXTURE -- long enough that the rate is the only thing that ages.",
    )
