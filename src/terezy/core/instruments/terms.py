"""The questions a declaration answers about its own terms, in either form.

**This module is the one place in ``src/`` that matches on which form a declaration is
in**, and that is deliberate rather than incidental. 013 FR-012 forbids every module under
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

from terezy.core.instruments.interface import BondTerms, EnumeratedTerms
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied

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
