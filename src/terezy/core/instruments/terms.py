"""The questions a declaration answers about its own terms, in either form.

**This module is the one place in ``src/`` that matches on which form a *declaration* is
in**, and that is deliberate rather than incidental. (``core.results.canonical`` matches on
the two **conventions statements** a schedule can make, which FR-016 requires it to tell
apart; that is a value it was handed, not a declaration it interrogated, and it moves no
money.) 013 FR-012 forbids every module under
the ledger, the tax engine, the decision layer and the results from naming the enumerated
form or testing which form it was given; FR-011a permits — and requires — those modules to
*ask the declaration a question both forms answer*. The difference between the two is this
file: the match happens once, beside the records, where a third form is four arms and no
call-site change.

**What made the delegation small.** ``core.ledger.seeds`` reads an issue date to refuse an
opening lot acquired too early, and it never needed one: it needed *the earliest date from
which this instrument's terms are known*, and it asked for the only spelling that existed.
Both forms answer that question — the generative one with its issue date, the enumerated one
with its coverage start — so the site keeps one question and gains an answer rather than
gaining a case.

**A question only one form can answer does not belong here.** If one ever arises, the honest
shape is a refusal inside the answer, not an absence at the call site: a caller that has to
handle "no answer" is a caller that has learned there are two forms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, assert_never

from terezy.core.instruments.interface import (
    BondTerms,
    EnumeratedTerms,
    PaymentKind,
    ScheduledPayment,
)
from terezy.core.primitives import money
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.money import Money

if TYPE_CHECKING:  # pragma: no cover -- read by :func:`narrowed`, never constructed here
    from terezy.core.instruments.interface import InstrumentDeclaration

DeclaredTerms = BondTerms | EnumeratedTerms
"""What a declaration says about the paper, in one of the two forms it can say it."""


@dataclass(frozen=True, slots=True)
class TermsKnownFrom:
    """The earliest date an instrument's terms are known from, and how it is declared.

    Three fields rather than a bare ``date`` because the refusal this feeds names *two
    declared facts that cannot both hold* and has to name the second one. The two forms
    spell it differently, and choosing the spelling at the call site would be a test of
    which form the declaration is, written in strings instead of in types.
    """

    on: date
    """The date itself."""

    term: str
    """The declared field that states it, as a refusal's ``second_term``."""

    as_declared: str
    """The verb phrase a refusal reads in: *"was issued on"*, *"publishes its payments
    from"*. The two are different claims about the world and the sentence should say
    which one it is making."""


DIRTY_PRICE: Final = (
    "the accrued/clean split: the purchase price is a dirty price and has not been "
    "separated into a clean price and accrued interest, because two facts are missing and "
    "neither may be inferred -- the start of the accrual period containing the purchase, "
    "and the basis interest accrues on within it"
)
"""What a figure derived from a schedule of declared payments additionally does not
account for (FR-017, FR-023). Phrased for a reader, because it is meant to be shown."""


def known_from(terms: DeclaredTerms) -> TermsKnownFrom:
    """From what date are this instrument's terms known?"""
    match terms:
        case BondTerms():
            return TermsKnownFrom(
                on=terms.issue_date,
                term="instrument.terms.issue_date",
                as_declared="was issued on",
            )
        case EnumeratedTerms():
            return TermsKnownFrom(
                on=terms.covers_from,
                term="instrument.schedule.covers_from",
                as_declared="publishes its payments from",
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def day_count_of(terms: DeclaredTerms) -> str:
    """Which declared convention turns a span of days into a fraction of a year?

    A convention of **computation**, which is why both forms declare one and why the
    enumerated form's is not an exception to FR-003's prohibition on generative terms: it
    describes how a span is annualised, not what the paper promises. What it must never
    reach is an amount, a date, a schedule, an accrual period or a coupon rate (FR-003b).
    """
    match terms:
        case BondTerms() | EnumeratedTerms():
            return terms.day_count
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def conventions_of(terms: DeclaredTerms) -> ConventionsApplied | AmountsAsDeclared:
    """What conventions shaped this schedule, and what should a row say about them?

    **One question, not two**, and FR-011b names that as a requirement rather than a
    convenience. The statement genuinely differs between the forms, so the natural
    implementation at the reading site is a test of which form it was given — which is
    exactly what FR-012 forbids. Asking here is what makes the reading site ask rather than
    decide.
    """
    match terms:
        case BondTerms():
            return ConventionsApplied(
                periodicity=terms.periodicity,
                day_count=terms.day_count,
                business_day_rule=terms.business_day_rule,
            )
        case EnumeratedTerms():
            return AmountsAsDeclared(day_count=terms.day_count)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def payments_after(
    payments: tuple[ScheduledPayment, ...], bought_on: date
) -> tuple[ScheduledPayment, ...]:
    """The declared payments a buyer acquiring on ``bought_on`` is actually paid.

    Strictly after, never on: a payment falling on the settlement date went to whoever held
    the paper that morning, which is the same convention a bond declared by its terms applies
    to a coupon dated on its purchase.

    ⚙ **Here rather than in the schedule generator, because two things need it and they must
    not disagree** -- what the generator *emits*, and what :func:`principal_returned` says the
    buyer gets back. They were one set for one commit and a review found the day they were
    not: the answer to "what does this holding receive" has to be given once.
    """
    return tuple(payment for payment in payments if payment.on > bought_on)


def face_value_of(terms: DeclaredTerms) -> Money:
    """The redemption amount one unit is declared to repay. Both forms state one.

    ⚙ **It is not what a purchase is measured against, and that is the whole reason this
    function carries a warning rather than being a bare passthrough.** Measuring a premium
    against face is defect F2, found on this branch: a schedule that has already repaid part
    of its principal reports a discount of everything the previous holder was repaid.
    :func:`principal_returned` is the question a purchase asks; this one answers *what does
    the paper say a unit redeems at*, which is a different question and has a narrower set of
    honest uses -- none of them arithmetic on what somebody paid.

    It exists so the two forms stay symmetric and so a sealed module has something to ask
    instead of reading the field: ``face_value`` is one of two **terms** both forms declare,
    so a direct read of it type-checks and no gate objects (see
    ``tests/contract/test_no_layer_knows_the_form.py``).
    """
    match terms:
        case BondTerms() | EnumeratedTerms():
            return terms.face_value
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def principal_returned(terms: DeclaredTerms, *, bought_on: date) -> Money:
    """What one unit returns as principal to a buyer who acquires it on this date.

    **Not the face value**, and the difference is a schedule that has already repaid part of
    its principal. A unit of such an issue is a unit of what *remains*: a buyer paying the
    remaining principal exactly has broken even, and measuring them against the nominal face
    would report a discount of everything already repaid -- a figure describing a trade
    somebody else made, years earlier (FR-025, amended).

    For a bond declared by its terms the two coincide, because it repays its face once at
    maturity and the purchase is guaranteed to precede that.
    """
    match terms:
        case BondTerms():
            return terms.face_value
        case EnumeratedTerms():
            return money.total(
                [
                    payment.amount
                    for payment in payments_after(terms.payments, bought_on)
                    if payment.pays is PaymentKind.PRINCIPAL_REPAYMENT
                ],
                terms.face_value.currency,
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def excludes_of(terms: DeclaredTerms) -> frozenset[str]:
    """What does a figure derived from these terms fail to account for, beyond the usual?

    Added to the boundaries every figure already states, never replacing them. FR-023 asks
    for the exclusions to be able to **differ by declaration**; today exactly one does.
    """
    match terms:
        case BondTerms():
            return frozenset()
        case EnumeratedTerms():
            return frozenset({DIRTY_PRICE})
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(terms)


def narrowed[T: DeclaredTerms](declaration: InstrumentDeclaration, form: type[T]) -> T:
    """The declaration's terms as the form a schedule generator computes from, or a raise.

    A raise rather than a typed failure, on the reading ``registry.ops_for`` and
    ``primitives.conventions`` already established: which functions project a declaration is
    decided by its declared class at the data boundary, so a declaration reaching a generator
    carrying terms it cannot read means that dispatch was bypassed. That is a programmer
    error rather than a fact about the money, and a typed failure would offer a caller a
    business outcome where there is none.

    One function rather than one per generator, because there is one rule and one message:
    two copies would be two chances for a reader to be told two different things about the
    same mistake.
    """
    terms = declaration.terms
    if not isinstance(terms, form):
        raise TypeError(
            f"{declaration.id!r} declares class {declaration.instrument_class!r} and reached "
            f"a schedule generator expecting {form.__name__} while carrying "
            f"{type(terms).__name__}. The declared class is the only dispatch key; this can "
            "only happen if it was not the key used."
        )
    return terms
