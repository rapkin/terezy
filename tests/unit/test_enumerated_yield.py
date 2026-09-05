"""SC-010, SC-011, SC-015: what a declared schedule says, and what it still computes.

Two halves of one requirement, and FR-016 separates them deliberately.

*What the rows say.* No periodicity generated the date, no business-day rule moved it, and
no day count sized the amount -- the amount is declared. A row naming all three would claim
two conventions that never ran.

*What is still produced.* The contractual yield, which does **not** refuse (FR-018). It
needs no issue date -- which is the whole of what the generative form supplies here that
this one cannot -- and it needs a day count, which FR-003a supplies. The obvious reading of
FR-017 is that every price-derived figure goes, and a refusal that looks like caution but is
really a missing figure is the worse defect: nobody audits what a careful system declines
to say.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from terezy.core.instruments import terms as instrument_terms
from terezy.core.instruments.interface import Assumptions, DateRange, EnumeratedTerms, Holding
from terezy.core.primitives import conventions
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.conventions import AmountsAsDeclared
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results import canonical, hurdle, project
from terezy.core.results.project import Projection
from terezy.data.declarations import resolver
from tests import declared_terms
from tests import tuple_registries as fixtures

DECLARATIONS = resolver.from_data_root(fixtures.DATA_ROOT)
GENERATIVE = "ovdp_synthetic_a"
MIRROR = "ovdp_enumerated_mirror"

PURCHASE = Holding(
    owner_id="owner-1",
    instrument_id=GENERATIVE,
    quantity=10.0,
    purchased_on=fixtures.ISSUE_DATE,
    cost=Money(10_000.0, Currency.UAH, prov.EMPTY),
)
HORIZON = DateRange(start=fixtures.ISSUE_DATE, end=fixtures.HORIZON_END)
HOLD_CASH = Assumptions(consumption_method="fifo", coupon_policy="hold_cash")


def _projected(instrument_id: str, *, day_count: str | None = None) -> Projection:
    declared = DECLARATIONS.instruments[instrument_id]
    if day_count is not None:
        terms = declared.terms
        assert isinstance(terms, EnumeratedTerms)
        declared = replace(declared, terms=replace(terms, day_count=day_count))
    outcome = project.project(
        declared,
        replace(PURCHASE, instrument_id=instrument_id),
        HORIZON,
        HOLD_CASH,
        tax_classes=DECLARATIONS.tax_classes,
    )
    assert isinstance(outcome, Projection), outcome
    return outcome


class TestEveryRowStatesWhatShapedIt:
    """SC-010."""

    def test_it_names_the_day_count_that_annualises(self) -> None:
        for row in _projected(MIRROR).schedule.rows:
            assert isinstance(row.conventions, AmountsAsDeclared)
            assert row.conventions.day_count == "act/365"

    def test_it_denies_all_three_generative_claims(self) -> None:
        for row in _projected(MIRROR).schedule.rows:
            assert isinstance(row.conventions, AmountsAsDeclared)
            assert "no periodicity generated this date" in row.conventions.reason
            assert "no business-day rule moved it" in row.conventions.reason
            assert "no day count sized this amount" in row.conventions.reason

    def test_no_row_names_a_periodicity_or_a_business_day_rule(self) -> None:
        """Asserted on the record's **fields** rather than on its text, because that is the
        claim: there is nowhere here to put a periodicity or a business-day rule, which is
        the point of two records over one with two nullable fields. A text scan would also
        have to explain why "annualises" contains "annual"."""
        for row in _projected(MIRROR).schedule.rows:
            assert set(type(row.conventions).__dataclass_fields__) == {"day_count", "reason"}

    def test_the_canonical_encoding_distinguishes_it_from_three_named_conventions(self) -> None:
        declared = {
            canonical.of_conventions(row.conventions) for row in _projected(MIRROR).schedule.rows
        }
        generated = {
            canonical.of_conventions(row.conventions)
            for row in _projected(GENERATIVE).schedule.rows
        }
        assert {rendered[:2] for rendered in declared} == {("declared", "act/365")}
        assert generated == {("semiannual", "act/365", "following")}
        assert declared.isdisjoint(generated)

    def test_the_statement_s_own_words_reach_the_encoding(self) -> None:
        """`AmountsAsDeclared.reason` is overridable, so two rows can make different
        statements about what shaped them -- and a digest ignoring it would call two
        differently-explained results identical, which is the argument the ledger's
        canonical form already makes about a causation's detail."""
        row = _projected(MIRROR).schedule.rows[0]
        assert isinstance(row.conventions, AmountsAsDeclared)
        assert canonical.of_conventions(row.conventions)[2] == row.conventions.reason
        assert canonical.of_conventions(
            replace(row.conventions, reason="something else entirely")
        ) != canonical.of_conventions(row.conventions)

    def test_the_generative_encoding_is_unchanged_by_this_feature(self) -> None:
        """SC-017 for the half a digest can see: the three-name rendering is untagged and
        byte-for-byte what it has always been, so no generative row's digest moves."""
        for row in _projected(GENERATIVE).schedule.rows:
            applied = declared_terms.generated(row.conventions)
            assert canonical.of_conventions(applied) == (
                applied.periodicity,
                applied.day_count,
                applied.business_day_rule,
            )


class TestTheContractualYieldIsProducedRatherThanRefused:
    """SC-011, FR-018."""

    def test_it_exists(self) -> None:
        assert _projected(MIRROR).hurdle.nominal_ytm.value > 0.0

    def test_it_equals_the_equivalent_generative_yield(self) -> None:
        assert is_close(
            _projected(MIRROR).hurdle.nominal_ytm.value,
            _projected(GENERATIVE).hurdle.nominal_ytm.value,
        )

    def test_a_declaration_differing_only_in_the_day_count_yields_differently(self) -> None:
        """And that is correct rather than a defect: it is what makes the day count a
        declared fact instead of a hidden constant. The two figures annualise the same
        cash flows on two different clocks."""
        assert not is_close(
            _projected(MIRROR).hurdle.nominal_ytm.value,
            _projected(MIRROR, day_count="30/360").hurdle.nominal_ytm.value,
        )

    def test_the_present_value_of_the_declared_flows_at_that_rate_is_zero(self) -> None:
        """A root checked as a root, on the flows the declaration itself lists."""
        projected = _projected(MIRROR)
        year_fraction = conventions.day_count(
            instrument_terms.day_count_of(DECLARATIONS.instruments[MIRROR].terms)
        )
        flows = tuple(
            (year_fraction(PURCHASE.purchased_on, row.occurred_on), row.gross.amount)
            for row in projected.schedule.rows
        )
        assert abs(hurdle.net_present_value(flows, projected.hurdle.nominal_ytm.value)) < TOLERANCE


class TestNeitherFormExcludesTheAccruedCleanSplit:
    """022 FR-013: 013 FR-023's dirty-price clause is removed, because it is no longer true.

    The declared payment dates bound the accrual periods and the declaration carries a day
    count, so an enumerated purchase price **is** separated into a clean price and an accrual
    (`core.instruments.accrual`). What is left is the boundaries every figure already states,
    identical for both forms -- which is what makes them comparable at all.
    """

    def test_neither_form_widens_the_standing_boundaries(self) -> None:
        assert _projected(MIRROR).hurdle.excludes == hurdle.EXCLUDES
        assert _projected(GENERATIVE).hurdle.excludes == hurdle.EXCLUDES


def test_the_yield_needs_no_issue_date_and_the_declaration_has_none() -> None:
    """The point of FR-018, stated as an assertion: the one generative term the yield could
    have wanted is absent, and the figure is produced anyway."""
    terms = DECLARATIONS.instruments[MIRROR].terms
    assert not hasattr(terms, "issue_date")
    assert _projected(MIRROR).hurdle.nominal_ytm.value > 0.0
    assert isinstance(instrument_terms.known_from(terms).on, date)
