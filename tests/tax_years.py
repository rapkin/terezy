"""A clearly-labelled synthetic set of assessment rules, for tests that need a tax year.

**Every rate, deadline and category here is invented.** Nothing in this module describes
Ukrainian law: the real deadlines and the real rates live in ``data/tax/``, cited, and the
tests that check *those* load them from disk (``tests/contract/test_tax_declaration_loading``).
What lives here is the shape -- a netting category, a per-event one, an exempt one, and a
timing rule -- so that the arithmetic of ``core.tax.year`` can be checked by hand without a
file anywhere near it.

**The rates are deliberately not the Ukrainian ones.** 10% and 5% are round numbers chosen so
that every figure in the worked examples is checkable in the head, and so that no figure
computed here could be mistaken for a real liability. A test quoting the rate the shipped pack
declares would look like an answer.

Not a test module -- ``pytest`` collects only ``test_*.py``, so this file is imported, never
run.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from terezy.core.ledger.lots import LotMethod
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import SourceRef
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.schedule import RateEntry

UAH = Currency.UAH

FIXTURE_SOURCE = SourceRef(
    id="tests/tax_years#fixture",
    citation="SYNTHETIC FIXTURE -- invented categories, deadlines and rates. Not any law.",
    retrieved_on=date(2026, 8, 23),
    verified_on=date(2026, 8, 23),
)
"""Verified, so that a test asserting the propagation of an *unverified* mark has to declare
one of its own rather than inheriting one by accident."""

UNVERIFIED_SOURCE = SourceRef(
    id="tests/tax_years#unverified",
    citation="SYNTHETIC FIXTURE -- an invented rule nobody has checked.",
    retrieved_on=date(2026, 8, 23),
    verified_on=None,
)

INVESTMENT = "fixture_investment_profit"
"""The netting category: gains and losses net, and a loss carries without limit."""

DISTRIBUTION = "fixture_fund_distribution"
"""The per-event category: each payout charged on its own, nothing nets, nothing carries."""

EXEMPT = "fixture_exempt_securities"
"""The category outside the calculation on both sides -- income and costs alike."""

TAXED_CLASS_ID = "fixture_taxed_disposal"
DISTRIBUTION_CLASS_ID = "fixture_taxed_distribution"
EXEMPT_CLASS_ID = "fixture_exempt_bond"

PIT_RATE = 0.10
LEVY_RATE = 0.05
"""Round fixture rates. See the module docstring: not Ukrainian, and chosen to be obviously
not Ukrainian."""


def rate_entry(
    *, pit: float = PIT_RATE, levy: float = LEVY_RATE, effective_from: date = date(2020, 1, 1)
) -> RateEntry:
    """One dated entry of the fixture schedule, starting long before any fixture event."""
    return RateEntry(
        effective_from=effective_from,
        pit_rate=pit,
        levy_rate=levy,
        provenance=prov.of([FIXTURE_SOURCE]),
    )


TAXED_CLASS = TaxClass(
    id=TAXED_CLASS_ID,
    applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
    rates=(rate_entry(),),
)

DISTRIBUTION_CLASS = TaxClass(
    id=DISTRIBUTION_CLASS_ID,
    applies_to=frozenset({TaxableEventKind.DISTRIBUTION}),
    rates=(rate_entry(),),
)

EXEMPT_CLASS = TaxClass(
    id=EXEMPT_CLASS_ID,
    applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
    rates=(rate_entry(pit=0.0, levy=0.0),),
)

TAX_PACK = {
    TAXED_CLASS_ID: TAXED_CLASS,
    DISTRIBUTION_CLASS_ID: DISTRIBUTION_CLASS,
    EXEMPT_CLASS_ID: EXEMPT_CLASS,
}


def timing(
    category_id: str,
    *,
    settlement: tax_year.SettlementBehaviour = tax_year.SettlementBehaviour.SELF_ASSESSED,
    pay_by: tuple[int, int] = (8, 1),
    non_business_day_rule: str = "following",
) -> tax_year.TimingRule:
    """A fixture timing rule: declare by 1 May, pay by 1 August, ``following``.

    The **shape** of the researched Ukrainian rule, with fixture provenance. The real dates,
    with their citations, are in ``data/tax/timing/ua.toml``; a test that needs to prove the
    dates are data changes them there and watches the payment move.

    ``following`` is a **fixture choice and not the shipped one**, deliberately: it is the
    convention that actually moves a date, so a worked example can put a deadline on a Sunday
    and watch it land on the Monday. What ships declares ``none``, which is a claim about the
    law rather than about a calendar, and is pinned against the file itself in
    ``tests/contract/test_tax_declaration_loading.py``.
    """
    return tax_year.TimingRule(
        category_id=category_id,
        settlement=settlement,
        declare_by=tax_year.AnnualDate(month=5, day=1),
        pay_by=tax_year.AnnualDate(month=pay_by[0], day=pay_by[1]),
        non_business_day_rule=non_business_day_rule,
        note="SYNTHETIC FIXTURE deadline. Not a Ukrainian one.",
        provenance=prov.of([FIXTURE_SOURCE]),
    )


def category(
    identifier: str,
    treatment: tax_year.Treatment,
    carryforward: tax_year.Carryforward,
) -> tax_year.IncomeCategory:
    return tax_year.IncomeCategory(
        id=identifier,
        treatment=treatment,
        carryforward=carryforward,
        note="SYNTHETIC FIXTURE category.",
        provenance=prov.of([FIXTURE_SOURCE]),
    )


def standing(
    method: LotMethod,
    verdict: tax_year.MethodVerdict = tax_year.MethodVerdict.SELF_DECLARANT_GUIDANCE,
) -> tax_year.MethodStanding:
    return tax_year.MethodStanding(
        method=method,
        verdict=verdict,
        what_the_law_says="SYNTHETIC FIXTURE finding. Not a reading of any real source.",
        provenance=prov.of([FIXTURE_SOURCE]),
    )


STANDINGS = {
    LotMethod.FIFO: standing(LotMethod.FIFO, tax_year.MethodVerdict.TAX_AGENT_METHODOLOGY),
    LotMethod.LIFO: standing(LotMethod.LIFO, tax_year.MethodVerdict.NO_SOURCE),
    LotMethod.AVERAGE_COST: standing(
        LotMethod.AVERAGE_COST, tax_year.MethodVerdict.SELF_DECLARANT_GUIDANCE
    ),
    LotMethod.SPECIFIC_LOT: standing(LotMethod.SPECIFIC_LOT, tax_year.MethodVerdict.NO_SOURCE),
}
"""The four verdicts arranged as the researched ones are: FIFO backed for the agent case,
average cost backed by the guidance for a self-declarant, and the other two backed by nothing.
Fixture findings with fixture citations -- the real ones are in ``data/tax/timing/ua.toml``."""


def rules(**overrides: Any) -> tax_year.AssessmentRules:
    """The whole fixture rule set: three categories, three classes, four method standings.

    Keyword overrides typed ``Any`` for the reason ``tests/synthetic.py`` gives at its own
    builders: ``dataclasses.replace`` accepts whatever fields the record has, the result is
    still the record's own type, and a misspelled field therefore fails in the test that used
    it rather than being silently ignored.
    """
    base = tax_year.AssessmentRules(
        jurisdiction_id="fixture",
        tax_currency=UAH,
        categories={
            INVESTMENT: category(
                INVESTMENT, tax_year.Treatment.NETS, tax_year.Carryforward.UNLIMITED
            ),
            DISTRIBUTION: category(
                DISTRIBUTION, tax_year.Treatment.PER_EVENT, tax_year.Carryforward.NONE
            ),
            EXEMPT: category(EXEMPT, tax_year.Treatment.OUTSIDE, tax_year.Carryforward.NONE),
        },
        category_of_class={
            TAXED_CLASS_ID: INVESTMENT,
            DISTRIBUTION_CLASS_ID: DISTRIBUTION,
            EXEMPT_CLASS_ID: EXEMPT,
        },
        timing={
            INVESTMENT: timing(INVESTMENT),
            DISTRIBUTION: timing(DISTRIBUTION),
            EXEMPT: timing(EXEMPT),
        },
        methods=STANDINGS,
    )
    return replace(base, **overrides)


def filing(**by_year: bool) -> tax_year.FilingDecisions:
    """Filing decisions keyed by year, written as ``filing(y2026=True, y2027=False)``.

    The ``y`` prefix is a Python identifier requirement, not part of the data: a year is an
    ``int`` everywhere in the records. Writing them as keywords keeps a test's two branches
    one character apart, which is what makes the filed/unfiled pair readable side by side.
    """
    return tax_year.FilingDecisions(
        owner_id="owner-1",
        declared_at="tests/tax_years#filing",
        by_year={int(name.lstrip("y")): filed for name, filed in by_year.items()},
    )


def switch(question: str, position: str) -> tax_year.UnsettledSwitch:
    return tax_year.UnsettledSwitch(
        question=question,
        position=position,
        resolution_path="an individual tax consultation (art. 52 PKU)",
        declared_at="tests/tax_years#switch",
    )


def positions(
    *,
    chain: tax_year.ChainPosition | None = None,
    method: LotMethod | None = LotMethod.AVERAGE_COST,
) -> tax_year.UnsettledPositions:
    """The declared positions on the two unsettled questions.

    ``chain`` defaults to **undeclared**, because most tests never reach the question and one
    that does should have to say which branch it is testing. ``method`` defaults to declared,
    because every assessment under a source-backed method needs it and a test about
    carryforward should not have to repeat it.
    """
    return tax_year.UnsettledPositions(
        chain=(
            None
            if chain is None
            else tax_year.ChainContinuity(
                position=chain,
                switch=switch(
                    "whether a loss survives a year whose declaration was missed",
                    chain.value,
                ),
            )
        ),
        method=(
            None
            if method is None
            else tax_year.SelfDeclarantMethod(
                method=method,
                switch=switch(
                    "which source-backed basis method governs a self-declarant",
                    method.value,
                ),
            )
        ),
    )
