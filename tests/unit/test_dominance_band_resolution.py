"""FR-011d: a fraction resolves per currency, lazily, against the question's own amount.

019 research D6. Three mechanics, and the second is the one that bites first:

* the width for a currency is ``fraction x amount``, where *amount* is the **one** amount the
  question states in that currency -- never a sum of two, and never a candidate's own figure;
* **absent** and **ambiguous** are two typed refusals rather than a zero or an incomparable
  pair, because the cause is a declaration and not a figure;
* resolution is **lazy**: a currency no pair is actually compared in is never resolved, so the
  token 1.00 USD the owner's question states to make an empty stream visible cannot produce a
  width nobody reads.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results.dominance import (
    BandInAnotherCurrency,
    NoQuestionAmountInTheCurrencyCompared,
    SeveralQuestionAmountsInTheCurrencyCompared,
)
from terezy.core.results.objectives import AbsoluteBand, Criterion, DaysBand
from tests import dominance_sections as sections


def test_the_width_is_the_fraction_of_the_amount_the_question_states() -> None:
    """0.0001 x 50 000 = 5.00 UAH, with the amount it came from reported beside it (FR-023)."""
    result = sections.result(sections.section())
    assert len(result.resolved_bands) == 1
    band = result.resolved_bands[0]
    assert band.criterion is Criterion.MONEY_AT_THE_ENDPOINT
    assert band.currency is Currency.UAH
    assert_money_close(band.from_amount, Money(50_000.0, Currency.UAH, prov.EMPTY))
    assert_money_close(band.width, Money(5.0, Currency.UAH, prov.EMPTY))


def test_the_token_dollar_amount_resolves_to_nothing_because_no_pair_is_in_dollars() -> None:
    """Lazy resolution, and the half of the USD hazard it does close.

    The question states 1.00 USD so an empty stream is visible in the answer. No candidate the
    shipped registry evaluates delivers dollars, so no pair is compared in them and no width is
    computed -- a band nobody chose is never applied and never reported.
    """
    result = sections.result(sections.section())
    assert Currency.USD not in {band.currency for band in result.resolved_bands}


def test_a_currency_only_one_candidate_delivers_is_still_not_resolved() -> None:
    """*Some pair is actually compared in it* is the rule, and one candidate is no pair.

    Planted rather than argued: one candidate's money arrives in dollars, so USD appears in the
    section and in no pair of its own. Every pair involving it crosses a currency and is
    incomparable, which is a property of those pairs and not a width to resolve.
    """
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016"])
    result = sections.result(planted)
    assert Currency.USD not in {band.currency for band in result.resolved_bands}
    assert result.incomparable, "no pair crossed a currency, so this asserts nothing"


def test_a_currency_two_candidates_deliver_resolves_a_width_of_its_own() -> None:
    """And two widths on one criterion is why ``resolved_bands`` is keyed by the pair."""
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016", "UA4000238281"])
    result = sections.result(planted, amounts=sections.question_amounts(usd=200.0))
    by_currency = {band.currency: band for band in result.resolved_bands}
    assert set(by_currency) == {Currency.UAH, Currency.USD}
    assert_money_close(by_currency[Currency.USD].width, Money(0.02, Currency.USD, prov.EMPTY))


def test_no_amount_in_the_currency_compared_is_a_refusal_naming_the_criterion() -> None:
    """A fraction band with nothing to be a fraction **of**.

    Recorded as a refusal rather than as an incomparable pair: both figures are present and in
    one currency, so reporting the population *not placed* would say the figures could not be
    read when what happened is that the question states no amount to size the band against.
    """
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016", "UA4000238281"])
    refusal = sections.run(planted, amounts=sections.question_amounts(usd=None))
    assert isinstance(refusal, NoQuestionAmountInTheCurrencyCompared)
    assert refusal.currency is Currency.USD
    assert refusal.criterion is Criterion.MONEY_AT_THE_ENDPOINT


def test_two_amounts_in_one_currency_are_a_different_refusal_that_names_the_streams() -> None:
    """The likelier of the two costs of the fraction shape, and it is a routine data edit away.

    015 requires an amount for **every** declared stream, so a second hryvnia stream puts two
    UAH amounts in the question -- and FR-011's relation has to be symmetric, so one currency
    admits one width and there is genuinely no way to pick between two the owner stated. The
    streams are named because the remedy is a question edit and *which two* is what a reader
    needs; an absolute band, which FR-011d permits, is immune to it.
    """
    stated = sections.question_amounts()
    stated["a_second_uah_stream"] = stated["salary_uah"]
    refusal = sections.run(sections.section(), amounts=stated)
    assert isinstance(refusal, SeveralQuestionAmountsInTheCurrencyCompared)
    assert refusal.currency is Currency.UAH
    assert set(refusal.stream_ids) == {"a_second_uah_stream", "salary_uah"}
    assert len(refusal.amounts) == 2


def test_the_two_refusals_differ_rather_than_sharing_one_record() -> None:
    """Absent and ambiguous have different remedies -- state an amount, or state one fewer."""
    both = sections.delivering_dollars(sections.section(), ["UA4000239016", "UA4000238281"])
    ambiguous = sections.question_amounts()
    ambiguous["a_second_uah_stream"] = ambiguous["salary_uah"]
    assert type(sections.run(both, amounts=sections.question_amounts(usd=None))) is not type(
        sections.run(sections.section(), amounts=ambiguous)
    )


def test_an_absolute_band_in_another_currency_refuses_rather_than_converting() -> None:
    """The shape that does not resolve against the question at all, and its own refusal.

    An absolute band **is** its width, and a width in hryvnia says nothing about how close two
    dollar figures are. Refused rather than converted, because no exchange rate is consulted
    anywhere in this pass -- and refused rather than ignored, because a band silently dropped is
    the silent default this repository refuses everywhere.
    """
    declared = sections.objectives()
    absolute = replace(
        declared,
        objectives=(
            replace(
                declared.objectives[0],
                band=AbsoluteBand(amount=Money(5.0, Currency.UAH, prov.EMPTY)),
            ),
            declared.objectives[1],
        ),
    )
    planted = sections.delivering_dollars(sections.section(), ["UA4000239016", "UA4000238281"])
    refusal = sections.run(planted, declared=absolute)
    assert isinstance(refusal, BandInAnotherCurrency)
    assert refusal.declared_in is Currency.UAH
    assert refusal.compared_in is Currency.USD
    assert refusal.criterion is Criterion.MONEY_AT_THE_ENDPOINT


def test_an_absolute_band_in_the_currency_compared_is_the_width_itself() -> None:
    """The other half of the pair: an absolute band resolves to itself and is reported in its
    declared form, so ``resolved_bands`` -- which reports fractions -- stays empty."""
    declared = sections.objectives()
    absolute = replace(
        declared,
        objectives=(
            replace(
                declared.objectives[0],
                band=AbsoluteBand(amount=Money(5.0, Currency.UAH, prov.EMPTY)),
            ),
            declared.objectives[1],
        ),
    )
    result = sections.result(sections.section(), declared=absolute)
    assert result.resolved_bands == ()
    assert result.non_dominated


@pytest.mark.parametrize(
    ("position", "band"),
    [
        (0, DaysBand(days=7)),
        (1, AbsoluteBand(amount=Money(5.0, Currency.UAH, prov.EMPTY))),
    ],
)
def test_a_band_of_the_wrong_shape_for_its_criterion_is_a_programmer_error(
    position: int, band: object
) -> None:
    """The loader refuses both shapes, so a record reaching the pass with one was built by hand
    against its own criterion -- which is a mistake about the code rather than about the money,
    and Principle IV puts ``raise`` there."""
    declared = sections.objectives()
    objectives = list(declared.objectives)
    objectives[position] = replace(objectives[position], band=band)  # type: ignore[arg-type]
    mismatched = replace(declared, objectives=tuple(objectives))
    with pytest.raises(TypeError, match="the loader refuses that shape"):
        sections.run(sections.section(), declared=mismatched)
