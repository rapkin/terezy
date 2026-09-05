"""The four questions a declaration answers, whichever form it is in (FR-011a, FR-011b).

This is the module the whole feature turns on. Three modules outside the instrument layer
read a generative field today, and FR-011 asks not that they be unchanged -- they cannot be
-- but that **none of them branch on the form**. That is only achievable if every question
they ask is one both forms can answer.

The observation that makes it delegation rather than branching, and the reason the change is
small: `core.ledger.seeds` never needed an *issue date*. It needed the earliest date from
which the instrument's terms are known, and it asked for the only spelling that existed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from terezy.core.instruments import terms as declared_terms
from terezy.core.instruments.interface import (
    BondTerms,
    EnumeratedTerms,
    InstrumentConstraints,
    InstrumentDeclaration,
    PaymentKind,
    ScheduledPayment,
)
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import AmountsAsDeclared, ConventionsApplied
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money

SOURCES = prov.EMPTY

GENERATIVE = BondTerms(
    face_value=Money(1000.0, Currency.UAH, SOURCES),
    coupon_rate=0.155,
    issue_date=date(2026, 1, 15),
    maturity_date=date(2028, 1, 15),
    periodicity="semiannual",
    day_count="act/365",
    business_day_rule="following",
    provenance=SOURCES,
)

ENUMERATED = EnumeratedTerms(
    face_value=Money(1000.0, Currency.UAH, SOURCES),
    covers_from=date(2026, 2, 1),
    payments=(
        ScheduledPayment(
            on=date(2026, 7, 15), amount=Money(77.5, Currency.UAH, SOURCES), pays=PaymentKind.COUPON
        ),
        ScheduledPayment(
            on=date(2027, 1, 15),
            amount=Money(1000.0, Currency.UAH, SOURCES),
            pays=PaymentKind.PRINCIPAL_REPAYMENT,
        ),
    ),
    day_count="act/365",
    published_in_order=None,
    provenance=SOURCES,
)


DECLARATION = InstrumentDeclaration(
    id="terms_fixture",
    name="Synthetic declaration — TEST FIXTURE, terms invented",
    instrument_class="fixed_income",
    currency=Currency.UAH,
    is_synthetic=True,
    terms=GENERATIVE,
    constraints=InstrumentConstraints(
        min_ticket=Money(1000.0, Currency.UAH, SOURCES), min_unit=1.0, provenance=SOURCES
    ),
    tax_classes={},
    groups=(),
)


class TestTheEarliestDateTheTermsAreKnownFrom:
    def test_a_generative_declaration_answers_with_its_issue_date(self) -> None:
        answer = declared_terms.known_from(GENERATIVE)
        assert answer.on == date(2026, 1, 15)

    def test_an_enumerated_declaration_answers_with_its_coverage_start(self) -> None:
        answer = declared_terms.known_from(ENUMERATED)
        assert answer.on == date(2026, 2, 1)

    def test_each_answer_names_the_declared_term_that_states_it(self) -> None:
        """A refusal naming *two declared facts that cannot both hold* has to name the
        second one, and the two forms spell it differently. Naming it at the call site
        would be a form test written in strings."""
        assert declared_terms.known_from(GENERATIVE).term == "instrument.terms.issue_date"
        assert declared_terms.known_from(ENUMERATED).term == "instrument.schedule.covers_from"

    def test_each_answer_carries_the_words_a_refusal_reads_in(self) -> None:
        assert "issued" in declared_terms.known_from(GENERATIVE).as_declared
        assert "publishes" in declared_terms.known_from(ENUMERATED).as_declared


class TestTheConventionThatAnnualises:
    def test_both_forms_declare_one(self) -> None:
        """FR-003a: required on the enumerated form too, because the contractual yield
        cannot be computed without it and a hard-coded 365 is forbidden at the site that
        would need one."""
        assert declared_terms.day_count_of(GENERATIVE) == "act/365"
        assert declared_terms.day_count_of(ENUMERATED) == "act/365"


class TestWhatARowShouldSayAboutTheConventionsThatShapedIt:
    def test_a_generative_declaration_answers_with_all_three(self) -> None:
        assert declared_terms.conventions_of(GENERATIVE) == ConventionsApplied(
            periodicity="semiannual", day_count="act/365", business_day_rule="following"
        )

    def test_an_enumerated_declaration_answers_with_the_one_that_ran(self) -> None:
        answer = declared_terms.conventions_of(ENUMERATED)
        assert isinstance(answer, AmountsAsDeclared)
        assert answer.day_count == "act/365"

    def test_the_question_is_one_question(self) -> None:
        """FR-011b. `core.results.project` builds both the row's statement and its year
        fractions from what the declaration answers, and asks nothing about which form it
        was given -- which it could not avoid doing if the statement were assembled there.
        """
        for terms in (GENERATIVE, ENUMERATED):
            statement = declared_terms.conventions_of(terms)
            assert statement.day_count == declared_terms.day_count_of(terms)


class TestWhatAFigureDerivedFromTheseTermsAdditionallyExcludes:
    """022 FR-013: neither form adds anything today, and the empty set is an answer.

    013 FR-023's dirty-price clause is gone because it stopped being true -- an enumerated
    purchase price is separated into a clean price and an accrual like any other. The question
    stays, and stays asked of the declaration, because FR-023 requires the exclusions to be
    able to differ by declaration and a caller that stopped asking could not tell.
    """

    def test_neither_form_adds_anything(self) -> None:
        assert declared_terms.excludes_of(GENERATIVE) == frozenset()
        assert declared_terms.excludes_of(ENUMERATED) == frozenset()


class TestNarrowingToTheFormAGeneratorReads:
    """The one place a schedule generator is allowed to learn which form it was given.

    A raise rather than a typed failure: which functions project a declaration is decided by
    its declared class at the data boundary, so a declaration reaching a generator carrying
    terms it cannot read means that dispatch was bypassed -- a programmer error rather than
    a fact about the money.
    """

    def test_it_returns_the_terms_when_the_form_matches(self) -> None:
        declared = replace(DECLARATION, terms=ENUMERATED)
        assert declared_terms.narrowed(declared, EnumeratedTerms) is ENUMERATED
        assert declared_terms.narrowed(DECLARATION, BondTerms) is GENERATIVE

    def test_it_raises_naming_both_forms_when_it_does_not(self) -> None:
        with pytest.raises(TypeError, match="EnumeratedTerms") as raised:
            declared_terms.narrowed(DECLARATION, EnumeratedTerms)
        assert "BondTerms" in str(raised.value)
        assert DECLARATION.id in str(raised.value)

    def test_the_message_says_the_declared_class_is_the_only_dispatch_key(self) -> None:
        """So a reader who hits this looks at the class the file declares rather than at the
        generator, which is where the mistake actually is."""
        with pytest.raises(TypeError, match="only dispatch key"):
            declared_terms.narrowed(replace(DECLARATION, terms=ENUMERATED), BondTerms)
