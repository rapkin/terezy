"""The root find behind the yield: what it computes, and what it refuses to guess.

A yield is a root, so it cannot be checked against a closed form -- which makes it exactly
the kind of figure that gets believed without checking. The tests below pin it down three
ways instead: against cases whose answer *is* known in closed form, against the identity
that defines it, and against the boundary where it must refuse rather than extrapolate.

Every comparison uses the single project tolerance (FR-002). The two places where a looser
bound would be needed are not here at all: they are stated in the worked example, beside
the assertion that needs them.
"""

from __future__ import annotations

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import hurdle


class TestNetPresentValue:
    """Discounting, against cases a reader can verify without a calculator."""

    def test_a_flow_at_time_zero_is_not_discounted(self) -> None:
        assert hurdle.net_present_value([(0.0, -100.0)], 0.25) == -100.0

    def test_a_flow_one_year_out_is_divided_by_one_plus_the_rate(self) -> None:
        # 110 / 1.10 = 100
        assert is_close(hurdle.net_present_value([(1.0, 110.0)], 0.10), 100.0)

    def test_a_flow_two_years_out_compounds(self) -> None:
        # 121 / 1.10**2 = 121 / 1.21 = 100
        assert is_close(hurdle.net_present_value([(2.0, 121.0)], 0.10), 100.0)

    def test_a_zero_rate_leaves_every_amount_alone(self) -> None:
        assert is_close(hurdle.net_present_value([(0.0, -100.0), (3.5, 100.0)], 0.0), 0.0)


class TestInternalRateOfReturn:
    """The root, on series whose answer is known independently."""

    def test_doubling_your_money_in_one_year_is_a_hundred_percent(self) -> None:
        # -100 now, 200 in a year: (200 / 100) - 1 = 1.0
        assert is_close(hurdle.internal_rate_of_return([(0.0, -100.0), (1.0, 200.0)]), 1.0)

    def test_a_single_receipt_two_years_out_is_the_square_root(self) -> None:
        # -100 now, 121 in two years: sqrt(121/100) - 1 = 1.1 - 1 = 0.10
        assert is_close(hurdle.internal_rate_of_return([(0.0, -100.0), (2.0, 121.0)]), 0.10)

    def test_getting_exactly_your_money_back_is_a_zero_return(self) -> None:
        assert is_close(hurdle.internal_rate_of_return([(0.0, -100.0), (4.0, 100.0)]), 0.0)

    def test_losing_half_over_a_year_is_minus_fifty_percent(self) -> None:
        assert is_close(hurdle.internal_rate_of_return([(0.0, -100.0), (1.0, 50.0)]), -0.5)

    def test_the_root_satisfies_the_identity_that_defines_it(self) -> None:
        # The general check, for a series with no closed form: at the rate returned, the
        # flows discount to zero. Compared against the *scale of the investment* rather
        # than against an absolute bound, because a present value is only meaningfully
        # "zero" relative to the money involved.
        flows = [(0.0, -10_000.0), (0.5, 700.0), (1.25, 750.0), (2.0, 10_400.0)]
        rate = hurdle.internal_rate_of_return(flows)
        residual = hurdle.net_present_value(flows, rate)
        assert is_close(10_000.0 + residual, 10_000.0)

    def test_the_answer_does_not_depend_on_the_order_of_the_flows(self) -> None:
        # Determinism's smaller cousin: a sum is order-independent in exact arithmetic and
        # only nearly so in float64, and a root find that reordered its inputs would move
        # its answer in the last bits for no reason a reader could see.
        flows = [(0.0, -1000.0), (1.0, 300.0), (2.0, 400.0), (3.0, 500.0)]
        assert is_close(
            hurdle.internal_rate_of_return(flows),
            hurdle.internal_rate_of_return(list(reversed(flows))),
        )

    def test_two_calls_on_the_same_flows_return_the_same_bits(self) -> None:
        flows = [(0.0, -10_000.0), (1.7, 1200.0), (3.0, 9500.0)]
        assert hurdle.internal_rate_of_return(flows) == hurdle.internal_rate_of_return(flows)


class TestRefusalToExtrapolate:
    """Outside the bracket there is no answer, and none is invented."""

    def test_a_series_that_never_crosses_zero_is_refused(self) -> None:
        # Money out and nothing ever coming back: the present value is negative at every
        # rate, so there is no root. Returning the bracket's edge would be reporting
        # "-99.9999%" as though it had been computed.
        with pytest.raises(ValueError, match="no yield exists"):
            hurdle.internal_rate_of_return([(0.0, -100.0), (1.0, -100.0)])

    def test_a_series_of_pure_receipts_is_refused(self) -> None:
        # Nothing was paid, so there is nothing to earn a return *on*. A number here
        # would be a rate of return on zero investment.
        with pytest.raises(ValueError, match="never crosses zero"):
            hurdle.internal_rate_of_return([(0.0, 100.0), (1.0, 100.0)])


class TestAssembly:
    """``of_flows`` keeps the two series apart and fills the real slot the same way."""

    def test_the_two_series_produce_two_independently_computed_figures(self) -> None:
        gross = [(0.0, -100.0), (1.0, 120.0)]
        net = [(0.0, -100.0), (1.0, 110.0)]
        figure = hurdle.of_flows(
            contractual=gross,
            received=net,
            total_tax=Money(10.0, Currency.UAH, prov.EMPTY),
            provenance=prov.EMPTY,
        )
        assert is_close(figure.nominal_ytm.value, 0.20)
        assert is_close(figure.nominal_cash_flow_return.value, 0.10)
        # No deflation input was given, so the slot holds the two named refusals rather
        # than a number -- and `is` rather than `==`, because `NOT_DEFLATED` is the one
        # value every undeflated figure shares (007 FR-006).
        assert figure.real is hurdle.NOT_DEFLATED
        assert figure.excludes == hurdle.EXCLUDES
