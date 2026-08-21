"""FR-018 and the spec's edge cases: every refusal is typed, specific, and unadjusted.

The requirement these tests exist for is not "reject bad input" -- it is *how*. FR-017
forbids clamping a value to zero, substituting a default, or returning an empty result to
mean a failure, and FR-018 adds that a purchase violating a declared constraint must be
reported **naming the constraint and the shortfall** and must never be silently adjusted to
fit. So each test below checks two things: that the projection refused, and that the
refusal carries enough for the owner to act on it.

Two adjustments are specifically forbidden and both are tested for by inspecting the
returned figures rather than by trusting the code not to have made them:

* **Rounding up to the minimum ticket** would spend money the owner did not agree to
  spend. The reported ``actual`` must be the amount that was actually offered.
* **A zero-length schedule** for an impossible instrument would report a holding that pays
  nothing, which is a different and false claim from "these terms cannot both hold".

Note which failure type each case produces, because the choice is not arbitrary. A
minimum ticket is a *feasibility* constraint on a purchase, so it is an
``InfeasiblePurchase`` carrying money figures. A non-positive quantity, a maturity before
its issue, and a horizon that stops short of maturity are *conflicts between two stated
terms*, so they are ``InconsistentTerms`` naming both. ``InfeasiblePurchase``'s
``required``/``actual``/``shortfall`` are all ``Money``, so it cannot express a quantity
violation without inventing a price for a unit -- and inventing one would be exactly the
fabricated input Principle I forbids.
"""

from __future__ import annotations

from datetime import date

from terezy.core.errors import InconsistentTerms, InfeasiblePurchase, UnresolvedTaxClass
from terezy.core.instruments.interface import DateRange, Holding, InstrumentDeclaration
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.results import project
from terezy.core.results.project import Projection, ProjectionOutcome
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from tests import synthetic

UAH = Currency.UAH


def _project(
    *,
    declaration: InstrumentDeclaration | None = None,
    holding: Holding | None = None,
    horizon: DateRange | None = None,
) -> ProjectionOutcome:
    """Project the synthetic holding, overriding exactly the pieces under test."""
    return project.project(
        synthetic.declaration() if declaration is None else declaration,
        synthetic.holding() if holding is None else holding,
        synthetic.horizon() if horizon is None else horizon,
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
    )


class TestBelowTheMinimumTicket:
    """The purchase is refused with its shortfall, and nothing is rounded (FR-018)."""

    def test_the_shortfall_is_reported_and_the_amount_is_not_rounded_up(self) -> None:
        # The instrument requires 1 000.00 and 400.00 is offered, so the shortfall is
        # 1 000.00 - 400.00 = 600.00. The reported "actual" must still be 400.00: an
        # engine that rounded the purchase up to the ticket would spend 600.00 nobody
        # agreed to spend, and one that rounded down would report a return on a holding
        # that was never bought.
        outcome = _project(
            holding=synthetic.holding(
                quantity=0.4,
                cost=Money(400.0, UAH, prov.of([synthetic.PURCHASE_SOURCE])),
            )
        )
        assert isinstance(outcome, InfeasiblePurchase)
        assert outcome.constraint == "min_ticket"
        assert_money_close(outcome.required, Money(1000.0, UAH, prov.EMPTY))
        assert_money_close(outcome.actual, Money(400.0, UAH, prov.EMPTY))
        assert_money_close(outcome.shortfall, Money(600.0, UAH, prov.EMPTY))
        assert "min_ticket" in outcome.reason or "at least" in outcome.reason

    def test_a_purchase_exactly_at_the_minimum_ticket_is_feasible(self) -> None:
        # The boundary is inclusive: "below the minimum" excludes being equal to it. A
        # strict comparison here would refuse the one purchase the constraint was
        # written to permit.
        outcome = _project(
            holding=synthetic.holding(
                quantity=1.0,
                cost=Money(1000.0, UAH, prov.of([synthetic.PURCHASE_SOURCE])),
            )
        )
        assert isinstance(outcome, Projection)


class TestImpossibleTerms:
    """Two declared terms that cannot both hold produce no schedule at all."""

    def test_maturity_on_the_issue_date_produces_no_schedule(self) -> None:
        outcome = _project(
            declaration=synthetic.declaration(
                terms=synthetic.terms(maturity_date=synthetic.ISSUE_DATE)
            )
        )
        assert isinstance(outcome, InconsistentTerms)
        assert {outcome.first_term, outcome.second_term} == {
            "instrument.maturity_date",
            "instrument.issue_date",
        }

    def test_maturity_before_the_issue_date_produces_no_schedule(self) -> None:
        outcome = _project(
            declaration=synthetic.declaration(
                terms=synthetic.terms(maturity_date=date(2025, 1, 15))
            )
        )
        assert isinstance(outcome, InconsistentTerms)
        assert "matures" in outcome.reason

    def test_a_purchase_after_maturity_is_refused(self) -> None:
        # US1 scenario 4: a maturity date earlier than the purchase date is reported as
        # an inconsistency. There is nothing left to hold, so there is nothing to
        # project -- and a schedule containing only a purchase would imply the money
        # simply vanished.
        outcome = _project(
            holding=synthetic.holding(purchased_on=date(2028, 6, 1)),
            horizon=synthetic.horizon(start=date(2028, 6, 1), end=date(2029, 1, 1)),
        )
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "holding.purchased_on"
        assert outcome.second_term == "instrument.maturity_date"

    def test_a_purchase_before_the_issue_date_is_refused(self) -> None:
        outcome = _project(
            holding=synthetic.holding(purchased_on=date(2025, 12, 1)),
            horizon=synthetic.horizon(start=date(2025, 12, 1)),
        )
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.second_term == "instrument.issue_date"


class TestANonPositiveQuantity:
    """ "Zero or negative purchase quantity -- rejected as invalid input" (spec edge case)."""

    def test_zero_units_acquires_nothing_and_is_rejected(self) -> None:
        outcome = _project(holding=synthetic.holding(quantity=0.0))
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "holding.quantity"
        assert "acquires nothing" in outcome.reason

    def test_negative_units_are_rejected_rather_than_read_as_a_sale(self) -> None:
        # A negative quantity is not a short sale: this feature has no such concept, and
        # silently reinterpreting the sign would produce a plausible schedule for a
        # position nobody described.
        outcome = _project(holding=synthetic.holding(quantity=-5.0))
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "holding.quantity"

    def test_a_purchase_that_cost_nothing_is_rejected(self) -> None:
        # No basis means no meaningful yield: the root find would be discounting
        # receipts against nothing paid.
        outcome = _project(
            holding=synthetic.holding(cost=Money(0.0, UAH, prov.of([synthetic.PURCHASE_SOURCE])))
        )
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "holding.cost"


class TestTheHorizon:
    """A window that cannot contain the whole schedule is refused, never truncated."""

    def test_a_horizon_ending_before_maturity_is_refused_not_truncated(self) -> None:
        # A truncated schedule would omit the principal, so the yield computed from it
        # would be a large loss rather than a partial answer -- wrong rather than
        # incomplete. An implicit liquidation at the horizon is the other option and the
        # spec forbids it: nobody asked to sell.
        outcome = _project(horizon=synthetic.horizon(end=date(2027, 6, 1)))
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "horizon.end"
        assert "hold-to-maturity" in outcome.reason

    def test_a_horizon_ending_on_the_unadjusted_maturity_is_still_short(self) -> None:
        # 2028-01-15 is a Saturday and the declared rule pays on the Monday, so a
        # horizon ending on the maturity date itself does not contain the payment. The
        # refusal says which rule moved it, because a reader looking at a two-day gap
        # deserves to be told why it is there.
        outcome = _project(horizon=synthetic.horizon(end=synthetic.MATURITY_DATE))
        assert isinstance(outcome, InconsistentTerms)
        assert "following" in outcome.reason

    def test_a_horizon_starting_after_the_purchase_is_refused(self) -> None:
        outcome = _project(horizon=synthetic.horizon(start=date(2026, 6, 1)))
        assert isinstance(outcome, InconsistentTerms)
        assert outcome.first_term == "horizon.start"

    def test_a_horizon_that_runs_backwards_is_refused(self) -> None:
        outcome = _project(
            horizon=synthetic.horizon(start=date(2028, 1, 31), end=synthetic.ISSUE_DATE)
        )
        assert isinstance(outcome, InconsistentTerms)
        assert "backwards" in outcome.reason


class TestAnUnresolvedTaxClass:
    """A missing class is reported, never treated as an exemption."""

    def test_an_instrument_referencing_an_undeclared_class_is_refused(self) -> None:
        # The dangerous default this guards against: an unresolved class silently
        # becoming "no tax". The comfortable answer is also the wrong one, and it would
        # flatter every figure derived from the holding.
        outcome = _project(
            declaration=synthetic.declaration(
                tax_classes={
                    TaxableEventKind.COUPON: "a_class_nobody_declared",
                    TaxableEventKind.DISPOSAL_GAIN: synthetic.EXEMPT_CLASS.id,
                }
            )
        )
        assert isinstance(outcome, UnresolvedTaxClass)
        assert outcome.tax_class_id == "a_class_nobody_declared"
        assert outcome.instrument_id == "ovdp_synthetic_test"

    def test_a_class_that_does_not_cover_the_income_it_governs_is_refused(self) -> None:
        # The instrument names a class for its coupons, the class resolves, and the class
        # says it only covers disposal gains. That is a declaration disagreeing with
        # itself, and the projection stops rather than charging zero on the coupons --
        # "no rule covers this" and "the rule charged nothing" are opposite claims.
        narrow = TaxClass(
            id="disposals_only",
            applies_to=frozenset({TaxableEventKind.DISPOSAL_GAIN}),
            pit_rate=0.0,
            levy_rate=0.0,
            provenance=prov.of([synthetic.EXEMPTION_SOURCE]),
        )
        outcome = project.project(
            synthetic.declaration(
                tax_classes={
                    TaxableEventKind.COUPON: narrow.id,
                    TaxableEventKind.DISPOSAL_GAIN: narrow.id,
                }
            ),
            synthetic.holding(),
            synthetic.horizon(),
            synthetic.assumptions(),
            tax_classes={narrow.id: narrow},
        )
        assert isinstance(outcome, UnresolvedTaxClass)
        assert outcome.tax_class_id == "disposals_only"
        assert "does not cover" in outcome.reason

    def test_an_instrument_declaring_no_class_for_an_income_it_produces_is_refused(
        self,
    ) -> None:
        outcome = _project(
            declaration=synthetic.declaration(
                tax_classes={TaxableEventKind.DISPOSAL_GAIN: synthetic.EXEMPT_CLASS.id}
            )
        )
        assert isinstance(outcome, UnresolvedTaxClass)
        assert "coupon" in outcome.reason
