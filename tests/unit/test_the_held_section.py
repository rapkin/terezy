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
from terezy.core.results.answer import Answer, SubjectHeld, SubjectReached
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.held import (
    HeldPosition,
    InBaseCurrency,
    QuoteAssetUndeclared,
    Valued,
)
from terezy.core.results.question import Question
from terezy.core.tax.official_rate import observation_for
from terezy.data.declarations import loader, resolver
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


def _asking_about_the_fixture() -> Question:
    """His question with the fixture asset among the words, so the held section reaches it.

    A held position is reported only for an asset the question **named** (FR-030), and his own
    question names `btc`, which ships no observation file. The fixture asset is the only one
    with a price, so a suite about the priced path has to ask about it.
    """
    question = fixtures.owners_question()
    named = (fixtures.OVDP, "btc", ASSET)
    return fixtures.with_plans(
        fixtures.with_subjects(question, *named),
        {word: plan for word, plan in question.plans.items() if word in named},
    )


def _answered(
    root: Path = fixtures.DATA_ROOT,
    *,
    as_of: date = fixtures.AS_OF,
    question: Question | None = None,
) -> Answer:
    run: Any = answer_declared(
        _asking_about_the_fixture() if question is None else question,
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
    assert valuation.assumption is not None, "a token-quoted asset leans on a belief"
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
    assert isinstance(valuation, QuoteAssetUndeclared)
    assert valuation.declared is None
    assert valuation.wanted == Currency.USD.value
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
        assert subject_counts(answered, section).held == 2, "btc and the fixture asset"


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


def test_the_question_is_the_owners_own_and_names_btc() -> None:
    """Every count above rests on his four words, so the fixture naming them is asserted.

    Against the **file** rather than against another call to the same helper: comparing the
    fixture to itself is a tautology that survives any edit to it, which is what this
    assertion used to be.
    """
    declared = loader.question_from_file(fixtures.QUESTION_FILE)
    assert fixtures.owners_question() == declared
    assert declared.subjects == ("cash", "ovdp", "inzhur", "btc")


# ---------------------------------------------------------------------------
# The belief speaks for one asset, and a group is not collapsed by one member
# ---------------------------------------------------------------------------

OTHER: Final = "synthetic_held_uah"
"""A second held asset quoted under the SAME symbol as the first and declaring its price is in
the base currency. The one declared belief is about USDT and dollars, so it says nothing about
this asset -- and the close it would otherwise have priced is right there to be misread."""

OTHER_DECLARATION: Final = f"""\
# SYNTHETIC FIXTURE, written by a test. Every term invented.
[instrument]
id             = "{OTHER}"
name           = "Synthetic held asset priced in hryvnia -- TEST FIXTURE"
class          = "held_asset"
quantity_unit  = "SXU"
price_currency = "UAH"
venue_id       = "binance"
symbol         = "SYNTHUSDT"
is_synthetic   = true
groups         = []

[instrument.tax_classes]
disposal_gain = "no_pack_declares_this_class"
"""


def _with_the_other_asset(tmp_path: Path) -> Path:
    """A root carrying a hryvnia-priced held asset whose symbol still ends in the token.

    It reads the same fetched series the dollar-priced fixture does, which is what puts a real
    close in front of the belief and makes the mismatch reachable rather than theoretical.
    """
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    (root / "instruments" / f"{OTHER}.toml").write_text(OTHER_DECLARATION, encoding="utf-8")
    overlay = root / resolver.USER_DIR / resolver.SEEDS_DIR / "owner-001.toml"
    overlay.write_text(
        overlay.read_text(encoding="utf-8") + "\n[[seed]]\n"
        "is_synthetic  = true\n"
        f'instrument_id = "{OTHER}"\n'
        "quantity      = 3.0\n"
        'acquired_on   = "2025-04-07"\n'
        "cost          = 900.0\n"
        'basis         = "known"\n',
        encoding="utf-8",
    )
    return root


def test_a_belief_about_another_token_does_not_price_this_asset(tmp_path: Path) -> None:
    """FR-023, and the wrong number it prevents.

    The one declared belief says a USDT is a USD. This asset declares its price is in UAH, so
    the belief says nothing about it -- and applying it anyway would tag the value USD, strike
    it through UAH/USD, and subtract a hryvnia basis from the result. That is wrong by the
    whole exchange rate with a plausible *assumes: one USDT is one USD* line beside it.
    """
    question = fixtures.owners_question()
    named = (fixtures.OVDP, OTHER)
    result = _answered(
        _with_the_other_asset(tmp_path),
        question=fixtures.with_plans(
            fixtures.with_subjects(question, *named),
            {word: plan for word, plan in question.plans.items() if word in named},
        ),
    )
    valuation = _position(result, OTHER).valuation
    assert isinstance(valuation, QuoteAssetUndeclared)
    assert valuation.wanted == Currency.UAH.value
    assert valuation.declared == "USDT = USD"
    assert _position(result, OTHER).basis.currency is Currency.UAH


def test_a_group_naming_a_held_asset_and_a_bond_still_reports_the_bond_as_reached(
    tmp_path: Path,
) -> None:
    """FR-029's limit. A group is a label and a label is data, so one word can name both.

    Deciding *held* first would hide every candidate the bonds reached and print
    *already held (0 of N)* over a ranking two of them are in -- a remedy that is wrong for
    the majority of the subject.
    """
    root = _with_the_other_asset(tmp_path)
    labelled = (root / "instruments" / f"{OTHER}.toml").read_text(encoding="utf-8")
    (root / "instruments" / f"{OTHER}.toml").write_text(
        labelled.replace("groups         = []", 'groups         = ["ovdp"]'), encoding="utf-8"
    )
    result = _answered(root, question=fixtures.owners_question())
    standing = next(item for item in result.sections[0].standings if item.named == fixtures.OVDP)
    assert isinstance(standing, SubjectReached), (
        "a group whose bonds reached candidates is reached, whatever else carries the label"
    )
    assert OTHER in standing.ids
    assert OTHER not in standing.with_candidates
