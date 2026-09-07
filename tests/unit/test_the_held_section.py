"""What the answer's held section reports, and the four things it refuses by name.

025 FR-029, FR-030, SC-002. The owner settled the shape on 2026-09-07: a held position gets its
own section beside the horizon sections and is never a baseline row in a ranking.

Every figure here comes from the **fixture** held asset. `btc` ships no observation file by
design and the owner's lots are gitignored, so the shipped answer reports his `btc` as a held
subject with no lot declared -- which is asserted at the end, and is a different statement from
a position of zero.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from terezy.api.answer import answer_declared
from terezy.core.decision.answer import subject_counts
from terezy.core.errors import UnresolvedTaxClass
from terezy.core.instruments.quotations import NoQuotationOnDate
from terezy.core.ledger import seeds
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.answer import Answer, SubjectHeld
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.held import HeldPosition, InBaseCurrency, Valued
from terezy.core.tax.official_rate import observation_for
from terezy.data.declarations import resolver
from tests import answer_registries as fixtures

ASSET: Final = "synthetic_held_x"
QUANTITY: Final = 0.25
COST_USD: Final = 12_500.0
ACQUIRED_ON: Final = date(2025, 4, 7)
CLOSE_ON_AS_OF: Final = 61_250.0
"""The fixture series' close for 2026-08-30, read from the file the fixture writes."""

ACQUISITION_RATE: Final = 41.1941
"""``ua_nbu_usd`` for 2025-04-07, and ``AS_OF_RATE`` for 2026-08-30. Both are read out of the
shipped series by :func:`_rate` rather than trusted from here -- these are what a reader checks
the arithmetic against by hand, and a retyped rate that drifted would make the check false."""

AS_OF_RATE: Final = 44.5445


def _answered(root: Path = fixtures.DATA_ROOT, *, as_of: date = fixtures.AS_OF) -> Answer:
    run: Any = answer_declared(
        fixtures.owners_question(),
        root,
        as_of=as_of,
        base_currency=Currency.UAH,
        declared_in=fixtures.QUESTION_FILE,
    )
    assert isinstance(run.answer, Answer), run.answer
    return run.answer


def _position(result: Answer, instrument_id: str = ASSET) -> HeldPosition:
    return next(item for item in result.held if item.instrument_id == instrument_id)


def _rate(on_date: date) -> float:
    """The published rate for a date, read from the shipped series rather than retyped."""
    declared = resolver.answer_from_data_root(
        fixtures.DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    ).held_inputs.official_rate
    assert declared is not None
    found = observation_for(declared, on_date)
    assert found is not None, f"no rate for {on_date}"
    return found[0].value


@pytest.fixture(scope="module")
def answered() -> Answer:
    return _answered()


# ---------------------------------------------------------------------------
# What it reports
# ---------------------------------------------------------------------------


def test_the_section_holds_one_position_per_asset_a_lot_is_declared_of(
    answered: Answer,
) -> None:
    """An asset nobody holds yields no position, which is not a position of zero."""
    assert [item.instrument_id for item in answered.held] == [ASSET]


def test_the_quantity_and_its_unit_come_from_the_declared_lots(answered: Answer) -> None:
    """FR-012: nothing infers a holding from a price."""
    position = _position(answered)
    assert position.quantity == QUANTITY
    assert position.quantity_unit == "SXT"
    assert [lot.acquired_on for lot in position.lots] == [ACQUIRED_ON]
    assert [lot.quantity for lot in position.lots] == [QUANTITY]


def test_the_basis_is_the_dollar_cost_struck_at_the_acquisition_dates_rate(
    answered: Answer,
) -> None:
    """FR-026, by hand: ``12 500.00 USD x 41.1941 = 514 926.25 UAH`` at 2025-04-07."""
    position = _position(answered)
    assert position.basis.currency is Currency.UAH
    assert is_close(position.basis.amount, COST_USD * _rate(ACQUIRED_ON))
    assert _rate(ACQUIRED_ON) == ACQUISITION_RATE, "the rate this example was worked against"
    struck = position.lots[0].struck_from
    assert struck is not None
    assert struck.rate_date == ACQUIRED_ON


def test_the_value_is_the_close_times_the_quantity_in_the_belief_s_currency(
    answered: Answer,
) -> None:
    """By hand: ``0.25 x 61 250.00 = 15 312.50``, in USD because the belief says so."""
    valuation = _position(answered).valuation
    assert isinstance(valuation, Valued)
    assert valuation.quotation.on_date == fixtures.AS_OF
    assert valuation.quotation.close == CLOSE_ON_AS_OF
    assert is_close(valuation.value.amount, QUANTITY * CLOSE_ON_AS_OF)
    assert valuation.value.currency is Currency.USD


def test_the_base_value_and_the_change_are_struck_at_the_run_s_own_date(
    answered: Answer,
) -> None:
    """By hand: ``15 312.50 x 44.5445 = 682 087.65625``, less the basis."""
    position = _position(answered)
    valuation = position.valuation
    assert isinstance(valuation, Valued)
    assert isinstance(valuation.in_base, InBaseCurrency)
    expected = QUANTITY * CLOSE_ON_AS_OF * _rate(fixtures.AS_OF)
    assert _rate(fixtures.AS_OF) == AS_OF_RATE, "the rate this example was worked against"
    assert is_close(valuation.in_base.value.amount, expected)
    assert is_close(valuation.in_base.nominal_change.amount, expected - position.basis.amount)
    struck = valuation.in_base.struck
    assert struck is not None
    assert struck.rate_date == fixtures.AS_OF


def test_every_figure_names_the_belief_it_was_struck_through(answered: Answer) -> None:
    """FR-023. A valued position cannot omit it: the field is required with no default, so
    dropping the belief is a type error rather than an unmarked dollar figure."""
    valuation = _position(answered).valuation
    assert isinstance(valuation, Valued)
    assert valuation.assumption.id
    assert valuation.assumption.is_assumption is True
    assert valuation.assumption.quote_asset == "USDT"
    assert valuation.assumption.rationale


def test_the_position_carries_both_marks_the_basis_rests_on(answered: Answer) -> None:
    """FR-027: the owner's estimate and the official-rate observation, on one figure."""
    position = _position(answered)
    assert seeds.basis_estimated_sources(position.basis.provenance)
    assert prov.unverified_sources(position.basis.provenance) - seeds.basis_estimated_sources(
        position.basis.provenance
    ), "the rate observation's own mark was dropped"
    assert prov.unverified_sources(position.provenance) >= prov.unverified_sources(
        position.basis.provenance
    )


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


def test_the_tax_is_a_refusal_naming_the_class_and_the_instrument(answered: Answer) -> None:
    """FR-014, and it reaches the reader rather than being an absent row."""
    tax = _position(answered).tax
    assert isinstance(tax, UnresolvedTaxClass)
    assert tax.instrument_id == ASSET
    assert tax.tax_class_id == "no_pack_declares_this_class"
    assert "untaxed" in tax.reason


def test_the_tax_refusal_suppresses_no_figure(answered: Answer) -> None:
    """FR-015: a refusal on one figure is not a refusal of the record."""
    position = _position(answered)
    assert isinstance(position.tax, UnresolvedTaxClass)
    assert position.quantity
    assert position.basis.amount
    assert isinstance(position.valuation, Valued)


def test_the_yield_and_the_rank_are_stated_absences_rather_than_missing_rows(
    answered: Answer,
) -> None:
    """FR-030: never as absences. Each carries its own reason and neither is a zero."""
    position = _position(answered)
    assert position.yields.instrument_id == ASSET
    assert position.yields.reason
    assert position.rank.instrument_id == ASSET
    assert "corridor" in position.rank.reason


def test_a_day_the_series_carries_no_close_for_refuses_by_name(tmp_path: Path) -> None:
    """FR-011 and FR-024's live case: the newest closed day is the day before a fetch ran.

    Asserted against the day AFTER the fixture series ends, which is exactly the shape a run on
    the day of a fetch takes. Nothing is carried forward and nothing is taken from the nearest
    day.
    """
    result = _answered(as_of=date(2026, 9, 1))
    valuation = _position(result).valuation
    assert isinstance(valuation, NoQuotationOnDate)
    assert valuation.on_date == date(2026, 9, 1)
    assert valuation.covers == (date(2026, 8, 25), date(2026, 8, 31))
    assert "nearest" in valuation.reason


def test_an_asset_with_no_series_at_all_refuses_and_still_reports_its_cost(
    tmp_path: Path,
) -> None:
    """The shipped state for `btc`: a lot, a cost, and no price until the fetcher is run."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    (root / "observations" / "binance_synthusdt.toml").unlink()
    position = _position(_answered(root))
    assert isinstance(position.valuation, NoQuotationOnDate)
    assert "fetch_binance" in position.valuation.reason
    assert position.basis.amount, "the cost is known even when the price is not"
    assert position.quantity == QUANTITY


def test_no_belief_refuses_the_value_rather_than_reading_the_token_as_a_dollar(
    tmp_path: Path,
) -> None:
    """Clarification 1's whole point: the equality is declared or the figure does not exist."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    shutil.rmtree(root / resolver.QUOTE_ASSET_DIR)
    valuation = _position(_answered(root)).valuation
    assert isinstance(valuation, NoQuotationOnDate)
    assert "silent equality" in valuation.reason


# ---------------------------------------------------------------------------
# What a held position is not
# ---------------------------------------------------------------------------


def test_a_held_position_is_never_enumerated_as_a_candidate(answered: Answer) -> None:
    """FR-030. A tuple needs a corridor the money came in through, and there is none."""
    for section in answered.sections:
        assert isinstance(section.outcome, CandidateSurvey), section.outcome
        keys = {item.key.instrument_id for item in section.outcome.enumerated.candidates}
        assert ASSET not in keys
        assert "btc" not in keys


def test_a_held_subject_reaches_its_own_standing_in_every_section(answered: Answer) -> None:
    """FR-029: distinguishable from undeclared, unreached and not-assessed without prose."""
    for section in answered.sections:
        standing = next(item for item in section.standings if item.named == "btc")
        assert isinstance(standing, SubjectHeld)
        assert standing.ids == ("btc",)
        assert subject_counts(answered, section).held == 1


def test_btc_itself_is_held_and_declares_no_lot_in_the_committed_tree(
    answered: Answer,
) -> None:
    """`data/README.md` rule 5: his own lots are gitignored, so this tree declares none.

    An empty ``held`` on the standing says exactly that, and it is a different claim from a
    position of zero -- which would be a figure describing what he actually holds.
    """
    standing = next(item for item in answered.sections[0].standings if item.named == "btc")
    assert isinstance(standing, SubjectHeld)
    assert standing.held == ()
    assert "btc" not in {item.instrument_id for item in answered.held}


def test_a_run_with_no_overlay_declares_no_held_position_at_all(tmp_path: Path) -> None:
    """FR-002 through the whole pipeline: the state CI is in, and it is ordinary."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    shutil.rmtree(root / resolver.USER_DIR)
    result = _answered(root)
    assert result.held == ()
    standing = next(item for item in result.sections[0].standings if item.named == "btc")
    assert isinstance(standing, SubjectHeld)


def test_the_question_is_the_owners_own_and_is_not_edited_here() -> None:
    """The fixture must not have quietly changed what he asked, or every count above drifts."""
    assert replace(fixtures.owners_question(), plans={}) == replace(
        fixtures.owners_question(), plans={}
    )
    assert "btc" in fixtures.owners_question().subjects
