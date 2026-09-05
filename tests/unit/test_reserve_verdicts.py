"""What he may need back, and when -- and the two things a verdict may never say.

015 SC-014 and SC-015. A reserve is a **stated need**, never a constraint: it produces a verdict
per candidate per horizon and removes nothing. There are exactly two values and the second is a
refusal -- *a partial exit would be needed, and a partly-liquidated holding is not projected* --
because *the reserve cannot be met* is a claim this system cannot make, and after FR-031 the
missing thing is not a price either: selling 20 000 of a 50 000 position is priced by the same
declared term. What does not exist is the **projection**.

**No rate is consulted anywhere here** (FR-021). A reserve in a currency the candidate's
arrivals do not deliver is short by the whole of it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from terezy.core.decision.answer import section_evaluated
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.answer import Answer, CoveredByThePlan, PartialExitWouldBeNeeded
from terezy.core.results.question import Reserve
from terezy.core.results.tuple import Arrival
from tests import answer_registries as fixtures

TWELVE_MONTHS = 2
"""The index of the horizon that evaluates anything at all over the declared registry."""


def _twelve_month_only() -> Answer:
    return fixtures.answered(fixtures.one_horizon(fixtures.owners_question(), TWELVE_MONTHS))


def _first_arrival() -> tuple[str, Arrival]:
    """One evaluated candidate and the date its first hryvnia reaches a spendable endpoint."""
    section = _twelve_month_only().sections[0]
    outcome = section_evaluated(section)[0]
    return outcome.key.instrument_id, outcome.arrivals[0]


def _with_reserve(amount: float, currency: Currency, by: date) -> Answer:
    question = fixtures.one_horizon(fixtures.owners_question(), TWELVE_MONTHS)
    return fixtures.answered(
        replace(
            question,
            reserves=(Reserve(amount=Money(amount, currency, prov.EMPTY), by=by),),
        )
    )


def test_a_reserve_the_first_arrival_covers_is_covered_by_the_plan() -> None:
    instrument_id, arrival = _first_arrival()
    result = _with_reserve(arrival.amount.amount / 2, Currency.UAH, arrival.arrived_on)
    verdict = next(
        item for item in result.sections[0].reserves if item.key.instrument_id == instrument_id
    )
    assert isinstance(verdict, CoveredByThePlan), verdict
    assert verdict.covered_on == arrival.arrived_on
    assert arrival in verdict.arrivals_read


def test_dating_it_one_day_earlier_flips_the_verdict() -> None:
    """SC-014. One day, one arrival, and the two values are the whole vocabulary."""
    instrument_id, arrival = _first_arrival()
    amount = arrival.amount.amount / 2
    before = _with_reserve(amount, Currency.UAH, arrival.arrived_on - timedelta(days=1))
    after = _with_reserve(amount, Currency.UAH, arrival.arrived_on)

    earlier = next(
        item for item in before.sections[0].reserves if item.key.instrument_id == instrument_id
    )
    later = next(
        item for item in after.sections[0].reserves if item.key.instrument_id == instrument_id
    )
    assert isinstance(earlier, PartialExitWouldBeNeeded), earlier
    assert isinstance(later, CoveredByThePlan), later
    assert earlier.arrivals_read == ()


def test_a_stated_need_never_removes_an_option() -> None:
    """FR-018. Excluding a candidate for failing to meet a reserve would be a feasibility rule.

    Asserted as an equality between the two runs rather than as *the candidate is present*: a
    verdict that quietly reordered or re-costed anything would pass the weaker claim.
    """
    _, arrival = _first_arrival()
    amount = arrival.amount.amount / 2
    before = _with_reserve(amount, Currency.UAH, arrival.arrived_on - timedelta(days=1))
    after = _with_reserve(amount, Currency.UAH, arrival.arrived_on)
    assert section_evaluated(before.sections[0]) == section_evaluated(after.sections[0])
    assert before.sections[0].outcome == after.sections[0].outcome


def test_a_reserve_larger_than_everything_that_arrives_names_what_is_missing() -> None:
    section = _with_reserve(10_000_000.0, Currency.UAH, fixtures.AS_OF.replace(year=2030)).sections[
        0
    ]
    for verdict in section.reserves:
        assert isinstance(verdict, PartialExitWouldBeNeeded), verdict
        assert verdict.short_by.amount > 0.0
        assert verdict.short_by.currency is Currency.UAH


def test_a_reserve_in_a_currency_the_arrivals_do_not_deliver_consults_no_rate() -> None:
    """SC-015. Short by the whole of it, rather than converted at a rate nobody declared."""
    _, arrival = _first_arrival()
    section = _with_reserve(1.0, Currency.USD, arrival.arrived_on).sections[0]
    for verdict in section.reserves:
        assert isinstance(verdict, PartialExitWouldBeNeeded), verdict
        assert verdict.short_by == Money(1.0, Currency.USD, prov.EMPTY)
        assert verdict.arrivals_read == ()


def test_a_question_with_no_reserve_produces_no_verdict() -> None:
    """Empty is a question that states no need, not a need of zero."""
    assert fixtures.answered().sections[0].reserves == ()
