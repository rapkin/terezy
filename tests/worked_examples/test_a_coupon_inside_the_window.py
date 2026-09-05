"""A coupon collected inside a window, and the sale price it has already left.

A quoted bond price is a **dirty** price, and it falls by a coupon on the day that coupon
detaches. An early exit is struck at a dated observation -- Inzhur's sell quotation of
2026-08-24 -- so carrying that quotation to the sale date unchanged would credit a holding the
coupon it collects inside the window *and* sell it at a price that still contained the same
money. The sale is therefore struck at the quotation **less every coupon that detached after it
was observed** (``core.scenarios.early_exit.detached_since``).

**What comes out is a whole coupon where what was in the quotation was an accrual**, which is
why `Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST` is signed and why closing it needs a basis
no declaration states (`enumerated-accrued-interest` in `specs/features.toml`). The residual is
visible here without any accrual figure at all, and this module asserts it: a three-month hold
of the worked issue reaches exactly what a one-month hold reaches, because the two extra months
build accrual the model does not carry.
"""

from __future__ import annotations

import functools
from dataclasses import replace
from datetime import date, timedelta

import pytest

from terezy.core.decision.answer import AnswerInputs, section_evaluated
from terezy.core.instruments.interface import DateRange, EnumeratedTerms, PaymentKind
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.answer import Direction, Exclusion
from terezy.core.results.ramp import RampCost
from terezy.core.results.tuple import TupleOutcome
from terezy.core.routes import cost
from terezy.core.routes.path import segments_of
from tests import answer_registries as answers

pytestmark = pytest.mark.worked_example

DETACHED_PER_HORIZON = (5, 11, 12)
"""How many of each section's early exits have a coupon detach while the holding held the paper
-- the population whose sale price the subtraction moves. Measured 2026-09-03 on the shipped
registry; the horizons are `data/questions/fifty-thousand.toml`'s."""

EARLY_EXIT_CLAIMS = frozenset(
    {
        "early_exit_is_a_point_not_a_distribution",
        "early_exit_spread_is_a_sellers_quote",
        "early_exit_carries_no_rate_risk",
        "early_exit_ignores_accrued_interest",
    }
)
"""What an early-exit figure states it does not account for. 015 FR-033 named the first three;
the fourth is what subtracting whole coupons from a dirty quotation leaves behind."""

WORKED = "UA4000236228"
"""Bought 2026-09-02 at 1089.32, pays 85.50 on 2026-09-09, quoted for resale at 1087.89.

The purchase is a day after the window opens, not on it: `inzhur_direct` declares one leg of
`latency_days = 1`, and the engine buys at `horizon.start` plus the way in's own latency.

The whole arithmetic, on the owner's own 50 000 UAH and the declared minimum increment of one
whole unit::

    45 units x 1089.32 = 49 019.40 deployed, 980.60 left undeployed
    45 x    85.50      =  3 847.50  coupon, collected on 2026-09-09
         1 087.89
       -    85.50      =  1 002.39  the 2026-08-24 quotation, less the coupon that detached
    45 x  1 002.39     = 45 107.55  sale on 2026-10-01
                         48 955.05  reached

**-64.35 over the month, -0.13%**, and the check that makes it more than a subtraction is that
64.35 is 45 x 1.43 -- the whole of the gap between the buy quotation of 1 089.32 and the sell
quotation of 1 087.89. A month bought and sold at one morning's two prices returns the spread
and nothing else, which is what a constant clean price means.

Carrying the quotation forward unchanged reached 52 802.55 instead: the 3 847.50 counted once as
income and once inside a sale price quoted while it was still attached.

**What is still missing is the accrual, and it is signed.** On a straight-line reading of the
declared payment dates -- 2026-03-11 to 2026-09-09 is 182 days, so the quotation of 2026-08-24
sat 166 days into the period and the 2026-10-01 sale sits 22 days into the next -- the quotation
carried 77.98 of accrual and the sale date carries 10.34, so the sale is struck about 17.85 per
unit below what the same assumption implies. That reading is an **illustration and not a figure
this engine emits**: nothing declares the basis, and choosing one is what
`enumerated-accrued-interest` is for.
"""

QUOTED_ON = date(2026, 8, 24)
REACHED = 48955.05
DEPLOYED = 49019.40
DEPLOYED_UNITS = 45.0
COUPON_PER_UNIT = 85.50
QUOTED_SELL = 1087.89
SPREAD_PER_UNIT = 1089.32 - QUOTED_SELL

BEFORE_THE_PURCHASE = {
    # id: units, buy quotation, sell quotation, coupon paid 2026-08-26 -- after the 2026-08-24
    # quotation and before the 2026-09-02 purchase, so in BOTH prices and received by neither.
    "UA4000231195": (45.0, 1110.24, 1107.43, 87.50),
    "UA4000239081": (46.0, 1085.00, 1078.09, 82.20),
}
"""The two shipped issues paying a coupon between the quotation and the purchase.

They are what fixes the subtraction's lower bound at the **purchase** rather than at the
quotation: the buy quotation of the same morning sizes the purchase as declared, so taking that
coupon out of the sell leg alone would report a loss of a whole coupon nobody took. Measured
2026-09-03."""


@functools.cache
def _supplied() -> AnswerInputs:
    """The shipped registry, read once. `answers.inputs()` re-resolves the whole data root, and
    this module reads it once per candidate in every test below."""
    return answers.inputs()


def _latency(item: TupleOutcome) -> int:
    """How long the way in takes: the SUM along the chain, which is what `cost` accumulates and
    `tuple_outcome` adds to the horizon start -- a chain of two one-day legs is two days."""
    routes = _supplied().routes
    return sum(
        leg.latency_days
        for segment in segments_of(item.key.route_in)
        for leg in routes[segment].legs
    )


def _bought_on(item: TupleOutcome, start: date) -> date:
    return start + timedelta(days=_latency(item))


def _sold_early(horizon_index: int) -> list[TupleOutcome]:
    section = answers.answered().sections[horizon_index]
    return [item for item in section_evaluated(section) if item.sold_early is not None]


def _detached(item: TupleOutcome) -> float:
    """What came out of this candidate's quotation, per unit. `_sold_early` has already
    established that there is a sale; this is where the type system is told."""
    assert item.sold_early is not None, item.key.instrument_id
    return item.sold_early.detached_per_unit.amount


def test_the_window_and_the_holding_cannot_disagree_about_what_is_inside() -> None:
    """A payment between the horizon's start and the candidate's own purchase would be received
    by nobody and detach from the quotation all the same, so the two readings of *inside* would
    part company. They agree only while no declared payment falls in that gap -- a fact about
    the data rather than about either rule, so it is asserted rather than assumed.
    """
    declared = _supplied().registries.instruments
    gaps = []
    latencies = []
    for index, section in enumerate(answers.answered().sections):
        for item in _sold_early(index):
            # Not `getattr(terms, "payments", ())`: a generative bond has no payment list, and
            # skipping one silently would drop it from a check whose subject IS which payments
            # fall inside a window. None carries a resale price today; the day one does, this
            # must be widened rather than quietly pass.
            terms = declared[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            latencies.append(_latency(item))
            bought = _bought_on(item, section.horizon.start)
            gaps += [
                (item.key.instrument_id, payment.on)
                for payment in terms.payments
                if section.horizon.start < payment.on <= bought
            ]
    assert not gaps, gaps
    # Over the SAME population the check ranges over, and non-empty: an empty set, or one where
    # only the candidates this check skips carry a latency, would make `gaps` empty for the
    # vacuous reason rather than the true one.
    assert latencies
    assert set(latencies) != {0}


def _coupons_declared_between(name: str, opens: date, closes: date) -> list[float]:
    """The declared coupon amounts per unit falling in ``(opens, closes]``, read off the file.

    Deliberately not ``SoldEarly.detached_per_unit``: a population counted with the same field
    the engine branches on is a tautology, and the previous version of this module pinned a
    float artefact for exactly that reason.
    """
    terms = _supplied().registries.instruments[name].terms
    assert isinstance(terms, EnumeratedTerms), name
    return [
        payment.amount.amount
        for payment in terms.payments
        if payment.pays is PaymentKind.COUPON and opens < payment.on <= closes
    ]


def test_the_subtraction_is_reached_at_every_horizon_the_owner_asked_about() -> None:
    """And does not reach every sale: a window with no coupon date in it is struck at the
    quotation itself, which is what makes the count a measurement rather than a tautology.

    The expected population is computed from the **declared schedules**, so the engine and the
    check reach it by different routes; the counts are the measurement.
    """
    declared = _supplied().registries.access
    measured = []
    untouched = []
    for index, section in enumerate(answers.answered().sections):
        sold = _sold_early(index)
        assert sold
        expected = set()
        for item in sold:
            quote = declared[item.key.instrument_id].resale_price
            assert quote is not None, item.key.instrument_id
            coupons = _coupons_declared_between(
                item.key.instrument_id,
                max(quote.observed_on, _bought_on(item, section.horizon.start)),
                section.horizon.end,
            )
            if coupons:
                expected.add(item.key.instrument_id)
            assert _detached(item) == pytest.approx(sum(coupons), abs=TOLERANCE), (
                item.key.instrument_id
            )
        assert {item.key.instrument_id for item in sold if _detached(item) > 0.0} == expected
        measured.append(len(expected))
        untouched += [item for item in sold if not _detached(item)]
    assert tuple(measured) == DETACHED_PER_HORIZON
    assert untouched


MULTI_COUPON = ("UA4000239081", 2, 82.20)
"""An issue detaching MORE than one coupon inside the owner's twelve-month window, with how
many and what each pays per unit. The residual this leaves grows with every one of them, which
is why it is not bounded by a coupon. Measured 2026-09-03."""


def test_more_than_one_coupon_detaches_and_every_one_of_them_comes_out() -> None:
    """The multi-coupon case, which is where "not bounded by one coupon" stops being a claim.

    Two coupons of 82.20 leave the quotation over the owner's year, so the sale is struck
    164.40 per unit below it. Under the same belief the price also rebuilds by accrual between
    them, and none of that is carried -- which is what the accrued-interest exclusion states,
    and why the residual is not bounded by a coupon.
    """
    name, count, per_coupon = MULTI_COUPON
    twelve = answers.answered().sections[2]
    quote = _supplied().registries.access[name].resale_price
    assert quote is not None
    item = next(one for one in _sold_early(2) if one.key.instrument_id == name)
    coupons = _coupons_declared_between(
        name,
        max(quote.observed_on, _bought_on(item, twelve.horizon.start)),
        twelve.horizon.end,
    )
    assert len(coupons) == count
    assert coupons == [per_coupon] * count
    assert item.sold_early is not None
    assert _detached(item) == pytest.approx(count * per_coupon, abs=TOLERANCE)
    assert item.sold_early.price_per_unit.amount == pytest.approx(
        quote.price.amount - count * per_coupon, abs=TOLERANCE
    )


def test_a_coupon_paid_before_the_purchase_stays_in_both_prices() -> None:
    """The case that fixes the lower bound at the purchase, and it is worth 87.50 a unit.

    UA4000231195, over the owner's one month::

        coupon 2026-08-26   87.50 per unit -- after the quotation, before the purchase,
                            and received by whoever held the paper that morning
        bought 2026-09-02   1 110.24 x 45 units = 49 960.80
        sold   2026-10-01   1 107.43 x 45 units = 49 834.35
                            the month returns 45 x 2.81 = 126.45 less than it deployed

    Neither price moves, and the month returns the bid-ask spread and nothing else. Opening the
    subtraction at the quotation instead would have taken 87.50 out of the sale while the buy
    quotation of the same morning still held it -- a loss of 45 x 87.50 that nobody took.
    """
    assert answers.answered().sections[0].horizon.end == date(2026, 10, 1)
    for name, (units, buy, sell, coupon) in BEFORE_THE_PURCHASE.items():
        item = next(one for one in _sold_early(0) if one.key.instrument_id == name)
        assert item.sold_early is not None
        assert _coupons_declared_between(name, QUOTED_ON, date(2026, 9, 2)) == [coupon]
        assert item.sold_early.units == units
        assert _detached(item) == 0.0
        assert item.sold_early.price_per_unit.amount == pytest.approx(sell, abs=TOLERANCE)
        assert item.reaches.amount == pytest.approx(units * sell, abs=TOLERANCE)
        assert item.reaches.amount - units * buy == pytest.approx(
            -units * (buy - sell), abs=TOLERANCE
        )


def test_no_early_exit_window_contains_a_repayment_of_principal() -> None:
    """The one place the two per-unit conventions would disagree, asserted to be out of reach.

    A repayment retires units, so what *a unit* means changes at that date; a coupon declared
    after one is per original unit while the quotation it is subtracted from is per remaining
    unit. Both mechanisms are right on their own and they do not compose, so the subtraction
    would be too small by the ratio. Nothing on the shipped registry pays principal inside an
    early-exit window -- every real issue repays once, at maturity, past the owner's horizons.
    """
    declared = _supplied().registries.instruments
    checked = 0
    inside = []
    for index, section in enumerate(answers.answered().sections):
        for item in _sold_early(index):
            terms = declared[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            assert item.sold_early is not None
            checked += 1
            inside += [
                (item.key.instrument_id, payment.on)
                for payment in terms.payments
                if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
                and section.horizon.start < payment.on <= item.sold_early.on
            ]
    assert checked
    assert not inside, inside


def test_no_declared_coupon_falls_on_the_quotation_day() -> None:
    """The lower bound is strict, so a coupon dated ON the quotation day counts as still inside
    it -- and whether a morning quotation on a payment date holds that coupon is something
    nobody has declared. Unreachable on the shipped registry, asserted rather than supposed,
    because the day it is reachable the convention has to be chosen rather than inherited from
    a comparison operator.
    """
    declared = _supplied().registries
    checked = 0
    landed = []
    for index in range(len(answers.answered().sections)):
        for item in _sold_early(index):
            quote = declared.access[item.key.instrument_id].resale_price
            assert quote is not None, item.key.instrument_id
            terms = declared.instruments[item.key.instrument_id].terms
            assert isinstance(terms, EnumeratedTerms), item.key.instrument_id
            checked += 1
            landed += [
                (item.key.instrument_id, payment.on)
                for payment in terms.payments
                if payment.on == quote.observed_on
            ]
    assert checked
    assert not landed, landed


def test_the_worked_arithmetic_is_what_the_declarations_say() -> None:
    """The numbers in this module's docstring, read back off the files rather than retyped."""
    declared = _supplied().registries
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    worked = next(item for item in section_evaluated(section) if item.key.instrument_id == WORKED)
    bought = _bought_on(worked, section.horizon.start)
    assert bought == date(2026, 9, 2)
    inside = [
        payment for payment in terms.payments if QUOTED_ON < payment.on <= section.horizon.end
    ]
    assert [(payment.on, payment.amount.amount) for payment in inside] == [
        (date(2026, 9, 9), COUPON_PER_UNIT)
    ]
    access = declared.access[WORKED]
    assert access.quote is not None
    assert access.resale_price is not None
    assert access.quote.price.amount == 1089.32
    assert access.resale_price.price.amount == QUOTED_SELL
    assert access.resale_price.kind == "venue_terms"
    assert access.resale_price.observed_on == QUOTED_ON


def test_the_engine_strikes_the_sale_at_the_quotation_net_of_the_coupon() -> None:
    """The docstring's arithmetic, read back off the owner's own answer.

    The whole month returns the spread: 45 x 1 002.39 sold plus 45 x 85.50 collected is
    45 x 1 087.89, which is 45 x 1.43 short of the 45 x 1 089.32 that was deployed.
    """
    worked = [item for item in _sold_early(0) if item.key.instrument_id == WORKED]
    assert len(worked) == 1
    outcome = worked[0]
    assert outcome.sold_early is not None
    assert outcome.sold_early.units == DEPLOYED_UNITS
    assert outcome.sold_early.detached_per_unit.amount == pytest.approx(
        COUPON_PER_UNIT, abs=TOLERANCE
    )
    assert outcome.sold_early.price_per_unit.amount == pytest.approx(
        QUOTED_SELL - COUPON_PER_UNIT, abs=TOLERANCE
    )
    assert outcome.reaches.amount == pytest.approx(REACHED, abs=TOLERANCE)
    assert outcome.reaches.amount == pytest.approx(DEPLOYED_UNITS * QUOTED_SELL, abs=TOLERANCE)
    # What was deployed, read off the outcome rather than retyped: `outlay` less what the join
    # could not deploy is what it actually spent, so the spread identity below is a claim about
    # the engine and not about the two literals above it.
    assert outcome.undeployed is not None
    paid = outcome.outlay.amount - outcome.undeployed.amount.amount
    assert paid == pytest.approx(DEPLOYED, abs=TOLERANCE)
    assert outcome.reaches.amount - paid == pytest.approx(
        -DEPLOYED_UNITS * SPREAD_PER_UNIT, abs=TOLERANCE
    )


def test_two_extra_months_of_accrual_reach_nothing_at_all() -> None:
    """The residual, visible without an accrual figure and asserted rather than argued.

    One coupon falls inside the one-month window and no further one inside the three-month
    window, so the model has the position reach **the same amount** over three months as over
    one: the accrual those two months build is not carried. That is the whole content of the
    `early_exit_ignores_accrued_interest` claim, and its sign -- the longer hold is understated.
    """
    one_month = next(item for item in _sold_early(0) if item.key.instrument_id == WORKED)
    three_months = next(item for item in _sold_early(1) if item.key.instrument_id == WORKED)
    assert one_month.sold_early is not None
    assert three_months.sold_early is not None
    assert three_months.sold_early.on > one_month.sold_early.on
    assert three_months.sold_early.detached_per_unit == one_month.sold_early.detached_per_unit
    assert three_months.reaches.amount == pytest.approx(one_month.reaches.amount, abs=TOLERANCE)


def test_the_accrued_residual_is_stated_on_every_early_exit() -> None:
    """FR-023a at the level that matters: an omission that is not stated is a silent default.

    **On every sale, not only the ones a coupon detached from.** The quotation is a dirty price
    carried across the gap between its own day and the sale, and that gap builds accrual whether
    or not a coupon interrupts it -- so 18 of this section's 23 sales would have stated nothing
    while being understated all the same.

    **Stated on every one; signed on most.** Which of them may carry a direction is a separate
    question with its own warrant and its own test below -- this one is about the claim being
    made at all, because the figure is approximate on every sale whether or not the direction
    of the approximation can be stated.
    """
    assert {item.value for item in Exclusion} & EARLY_EXIT_CLAIMS == EARLY_EXIT_CLAIMS
    section = answers.answered().sections[0]
    accrued = [
        item
        for item in section.excludes
        if item.what is Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST
    ]
    sold = _sold_early(0)
    assert {item.applies_to for item in accrued} == {item.key for item in sold}
    # Non-vacuous in the direction that matters: most of this population detached nothing, so a
    # gate on the detachment would have left them silent.
    assert [item for item in sold if _detached(item) == 0.0]
    stated = {item.what.value for item in section.excludes if item.what.value in EARLY_EXIT_CLAIMS}
    assert stated == EARLY_EXIT_CLAIMS


def test_the_residual_loses_its_sign_where_a_coupon_left_before_the_purchase() -> None:
    """The warrant, and the exact population it does not cover, from the declared schedules.

    The residual is ``a(sale) - a(quotation) + detached``, and what makes it positive is that
    ``detached`` covers the accrual the quotation had built -- an accrual within a period being
    smaller than the coupon that ends it. A coupon that detached before the holding bought the
    paper comes out of neither price, so it is missing from ``detached`` while having reset the
    accrual, and the residual goes the other way. Measured on UA4000231195, whose coupon of
    87.50 fell on 2026-08-26::

        a(2026-08-24)   87.50 x 180/182 = 86.54   -- two days short of the coupon
        a(2026-10-01)   87.50 x  36/182 = 17.31   -- 36 days into the next period
        residual        17.31 - 86.54 + 0.00 = **-69.23**, struck too HIGH

    The population is computed from the payment lists rather than from
    ``skipped_before_purchase``, so the engine and the check reach it by different routes.
    """
    declared = _supplied().registries
    unsigned = set()
    signed = set()
    for index, section in enumerate(answers.answered().sections):
        for item in _sold_early(index):
            quote = declared.access[item.key.instrument_id].resale_price
            assert quote is not None, item.key.instrument_id
            skipped = _coupons_declared_between(
                item.key.instrument_id,
                quote.observed_on,
                _bought_on(item, section.horizon.start),
            )
            stated = next(
                one
                for one in section.excludes
                if one.what is Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST
                and one.applies_to == item.key
            )
            if skipped:
                unsigned.add(item.key.instrument_id)
                assert stated.direction is None, item.key.instrument_id
            else:
                signed.add(item.key.instrument_id)
                assert stated.direction is Direction.SALE_STRUCK_TOO_LOW, item.key.instrument_id
    assert unsigned == set(BEFORE_THE_PURCHASE)
    assert len(signed) > len(unsigned)


def test_a_backdated_window_states_the_residual_without_a_direction() -> None:
    """The half of the sign the warrant does not cover, reached rather than argued.

    Both arguments for `the_sale_is_struck_too_low` need the quotation to predate the sale. Ask
    the same question over a window that closed before the 2026-08-24 quotation was taken and
    the quotation is used unchanged, the accrual runs the other way, and the claim is stated
    with no direction at all -- which is what SC-026's rule about unwarranted signs requires.
    """
    closed = replace(
        answers.owners_question(),
        horizons=(DateRange(start=date(2026, 5, 1), end=date(2026, 8, 1)),),
    )
    section = answers.answered(question=closed).sections[0]
    sold = [
        (item, item.sold_early)
        for item in section_evaluated(section)
        if item.sold_early is not None
    ]
    assert sold
    assert all(sale.quoted_on > sale.on for _, sale in sold)
    accrued = [
        item
        for item in section.excludes
        if item.what is Exclusion.EARLY_EXIT_IGNORES_ACCRUED_INTEREST
    ]
    assert {item.applies_to for item in accrued} == {item.key for item, _ in sold}
    assert all(item.direction is None for item in accrued)


def test_the_carried_price_keeps_the_marks_of_both_the_quote_and_the_coupon() -> None:
    """Principle I: the struck price is an assumption derived from an unverified quotation less
    a declared coupon, and subtracting one from the other may not launder either source away."""
    declared = _supplied().registries
    quote = declared.access[WORKED].resale_price
    assert quote is not None
    terms = declared.instruments[WORKED].terms
    assert isinstance(terms, EnumeratedTerms)
    section = answers.answered().sections[0]
    outcome = next(item for item in _sold_early(0) if item.key.instrument_id == WORKED)
    assert outcome.sold_early is not None
    inside = [
        payment for payment in terms.payments if QUOTED_ON < payment.on <= section.horizon.end
    ]
    assert inside
    behind = outcome.sold_early.price_per_unit.provenance.sources
    assert quote.price.provenance.sources <= behind
    for payment in inside:
        assert payment.amount.provenance.sources <= behind
    assert not any(source.verified_on for source in behind)


def test_the_latency_this_module_sums_is_the_one_the_engine_adds() -> None:
    """`_latency` re-derives `tuple_outcome`'s `horizon.start + routed.latency_days`, because
    `TupleOutcome` exposes no purchase date. Re-deriving a rule is how a check quietly keeps
    comparing against the old one, so the sum is pinned against the accumulator the engine
    actually uses -- `cost.cost_one`, whose `RampCost.latency_days` is what the join adds.
    """
    registries = _supplied().registries
    section = answers.answered().sections[0]
    checked = 0
    for item in section_evaluated(section):
        priced = cost.cost_one(
            item.key.route_in,
            item.outlay,
            routes=_supplied().routes,
            channels=registries.channels,
            streams=registries.streams,
            kinds=registries.kinds,
            on_date=section.horizon.start,
            as_of=answers.AS_OF,
            spendable=registries.spendable,
        )
        assert isinstance(priced, RampCost), item.key.instrument_id
        assert priced.latency_days == _latency(item), item.key.instrument_id
        checked += 1
    assert checked
