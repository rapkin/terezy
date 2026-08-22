"""FR-004 and FR-010: what a declared premium or markup costs, worked out by hand.

This is the arithmetic the whole feature rests on. ``SIMULATOR_SPEC.md`` §4.3.1 makes the
largest single claim in the product -- *a P2P premium of +2 to +4 UAH per dollar is roughly
4.8-9.5% one way* -- and that range is nothing more than ``premium / reference`` for a
reference near 42. FR-004 turns it into a requirement: *a declared premium in base currency
per unit of foreign currency MUST produce a cost percentage equal to the premium divided by
the stated reference rate, reproducing §4.3.1 exactly.*

So the number is checked here, by hand, in one line of arithmetic per assertion:

    3 / 42 = 0.0714285714...   -> 7.14% one way, the middle of the §4.3.1 range

**Two declaration forms, because the owner observes two different things.** A bank publishes
"1.5% on card transactions"; a P2P screen shows "45 UAH per dollar" against a reference of
42. Converting the second into a percentage by hand before typing it into a data file would
put an arithmetic step in a place with no tests, so both forms are declarable and the
conversion happens here, once.

**The sign conventions differ between the two forms, deliberately, and this module is where
that is pinned down.** ``markup_bps`` is a **cost magnitude**: 150 bps costs 1.5% whichever
way the money is going. ``premium_per_unit`` is a **signed offset from the reference**: the
buy side pays reference *plus* the premium, the sell side receives reference *plus* the
premium, so a sell side that gives up 2.5 UAH per dollar declares ``-2.5``. Reading them the
same way is the likeliest bug in this file, which is why every case below states the
expected rate as well as the expected fraction.

**Both sides always, and neither derived from the other** (FR-010). A single mid-rate is
never used for a transaction, and computing the sell side from the buy side would be using a
mid-rate with extra steps. There is no function here that takes one side and returns the
other; the tests assert that the two sides of one channel are genuinely independent numbers.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.routes import channels
from terezy.core.routes.channels import ChannelSide, FxChannel, Side

pytestmark = pytest.mark.worked_example

REFERENCE = 42.0
"""The stated reference rate: UAH per USD. Invented, like everything else in this module."""

SOURCE = SourceRef(
    id="synthetic:channel",
    citation="SYNTHETIC FIXTURE -- invented reference and premium. Not an observed quote.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)
SOURCES = prov.of([SOURCE])


def _premium(amount: float) -> ChannelSide:
    """A side declared as UAH per USD off the reference -- the form P2P is observed in."""
    return ChannelSide(
        markup_bps=None,
        premium_per_unit=Money(amount, Currency.UAH, SOURCES),
        kind="p2p_premium",
        provenance=SOURCES,
    )


def _markup(bps: float) -> ChannelSide:
    """A side declared as a markup in basis points -- the form a bank publishes."""
    return ChannelSide(
        markup_bps=bps, premium_per_unit=None, kind="bank_fee_schedule", provenance=SOURCES
    )


class TestAPremiumInBaseCurrencyPerUnit:
    """FR-004: the §4.3.1 arithmetic, one hand-computed line per case."""

    def test_a_three_hryvnia_premium_on_a_forty_two_reference_costs_three_over_forty_two(
        self,
    ) -> None:
        # The headline number of the feature.
        #   effective rate = 42 + 3            = 45 UAH per USD
        #   cost fraction  = (45 - 42) / 42    = 3 / 42 = 0.07142857142857142
        # §4.3.1 quotes 4.8-9.5% for premiums of +2 to +4, and 7.14% is the middle of it.
        side = _premium(3.0)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), 45.0)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.BUY), 3.0 / 42.0)
        assert is_close(
            channels.spread_over_reference(side, REFERENCE, role=Side.BUY), 0.07142857142857142
        )

    @pytest.mark.parametrize(
        ("premium", "expected_rate", "expected_fraction"),
        [
            (2.0, 44.0, 2.0 / 42.0),  # 0.047619... -> the 4.8% end of the §4.3.1 range
            (4.0, 46.0, 4.0 / 42.0),  # 0.095238... -> the 9.5% end of it
        ],
    )
    def test_the_ends_of_the_spec_range_reproduce_the_quoted_percentages(
        self, premium: float, expected_rate: float, expected_fraction: float
    ) -> None:
        # §4.3.1's "+2 to +4 UAH per dollar is roughly 4.8-9.5% one way" is exactly this
        # division and nothing else. Both ends are asserted so that a formula which
        # happened to be right at +3 -- say one that divided by the effective rate rather
        # than the reference -- would still fail somewhere.
        side = _premium(premium)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), expected_rate)
        assert is_close(
            channels.spread_over_reference(side, REFERENCE, role=Side.BUY), expected_fraction
        )

    def test_a_zero_premium_means_the_channel_is_at_the_reference(self) -> None:
        # Legal, and a distinct claim from a *missing* premium: "this channel trades at
        # the reference" is an observation, and refusing it would force the owner to
        # express it as an absence, which the loader refuses.
        side = _premium(0.0)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), REFERENCE)
        assert channels.spread_over_reference(side, REFERENCE, role=Side.BUY) == 0.0

    def test_a_negative_premium_on_the_buy_side_is_a_discount_and_is_reported_as_one(
        self,
    ) -> None:
        # P2P does trade below the reference. Buying at 41 against a reference of 42:
        #   effective rate = 42 + (-1)         = 41 UAH per USD
        #   cost fraction  = (41 - 42) / 42    = -1 / 42 = -0.023809523809523808
        # A negative cost is reported as negative. Clamping it at zero would be the same
        # defect class as clamping a fee at the amount (B13) -- a number quietly improved
        # on its way to the reader.
        side = _premium(-1.0)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), 41.0)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.BUY), -1.0 / 42.0)

    def test_a_negative_premium_on_the_sell_side_is_a_cost_of_that_size(self) -> None:
        # The sign convention, stated as arithmetic. Selling dollars for 2.5 UAH less
        # than the reference:
        #   effective rate = 42 + (-2.5)       = 39.5 UAH per USD received
        #   cost fraction  = (42 - 39.5) / 42  = 2.5 / 42 = 0.05952380952380952
        # The subtraction runs the other way on the sell side because receiving less than
        # the reference is what costs you there. One formula for both sides would have the
        # sell side reporting a discount for a spread it actually paid.
        side = _premium(-2.5)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.SELL), 39.5)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.SELL), 2.5 / 42.0)


class TestTheTwoMeasuresAreDifferentAndBothReported:
    """The correction: what left your pocket, versus the spread over the reference rate.

    An earlier implementation reported ``p / r`` as *the* cost, because FR-004 said so, and
    consequently reported an arriving amount **1.13 USD short** of what the venue would hand
    over on a 10 000 UAH purchase. FR-004 was corrected rather than the arithmetic bent to
    it. Both figures are real and both are reported; only one of them is the cost.

    Hand arithmetic, premium +3 against a reference of 42, so the P2P price is 45:

        buy 10 000 UAH  ->  10 000 / 45      = 222.222222... USD    (what you get)
        at reference    ->  222.2222 x 42    =  9 333.333... UAH    (what that is worth)
        spread          ->  10 000 - 9 333.33 =   666.666... UAH
        loss fraction   ->  666.667 / 10 000 =   0.0666666...  = 3/45 = p/(r+p)
        spread/reference->                       0.0714285...  = 3/42 = p/r
    """

    def test_the_buy_side_loss_is_the_premium_over_the_price_not_the_reference(self) -> None:
        side = _premium(3.0)
        assert is_close(channels.loss_fraction(side, REFERENCE, role=Side.BUY), 3.0 / 45.0)
        assert is_close(channels.loss_fraction(side, REFERENCE, role=Side.BUY), 0.06666666666666665)

    def test_the_rate_space_spread_still_reproduces_the_specification_figure(self) -> None:
        """§4.3.1's own arithmetic, kept reproducible and kept labelled as rate-space."""
        side = _premium(3.0)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.BUY), 3.0 / 42.0)

    def test_the_two_differ_on_the_buy_side(self) -> None:
        side = _premium(3.0)
        assert not is_close(
            channels.loss_fraction(side, REFERENCE, role=Side.BUY),
            channels.spread_over_reference(side, REFERENCE, role=Side.BUY),
        )

    def test_the_two_coincide_exactly_on_the_sell_side(self) -> None:
        """Which is why the correction moved the buy side only: ``1 - (r-p)/r`` is ``p/r``."""
        side = _premium(-2.5)
        assert is_close(
            channels.loss_fraction(side, REFERENCE, role=Side.SELL),
            channels.spread_over_reference(side, REFERENCE, role=Side.SELL),
        )

    def test_the_effective_rate_is_the_price_a_screen_would_show(self) -> None:
        side = _premium(3.0)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), 45.0)


class TestAMarkupInBasisPoints:
    """The published-tariff form. 150 bps is 1.5%, whichever way the money goes."""

    def test_a_hundred_and_fifty_basis_point_markup_is_one_and_a_half_percent(self) -> None:
        #   150 / 10 000 = 0.015
        #   buy rate  = 42 * (1 + 0.015) = 42.63 UAH per USD paid
        side = _markup(150.0)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.BUY), 0.015)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.BUY), 42.63)

    def test_the_same_markup_costs_the_same_on_the_sell_side(self) -> None:
        #   sell rate = 42 * (1 - 0.015) = 41.37 UAH per USD received
        # The *rate* moves the other way; the *cost* is the same 1.5%. This is the
        # difference from a premium, which is a signed offset rather than a magnitude.
        side = _markup(150.0)
        assert is_close(channels.spread_over_reference(side, REFERENCE, role=Side.SELL), 0.015)
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.SELL), 41.37)

    def test_a_zero_markup_means_the_channel_is_at_the_reference(self) -> None:
        side = _markup(0.0)
        assert channels.spread_over_reference(side, REFERENCE, role=Side.BUY) == 0.0
        assert is_close(channels.effective_rate(side, REFERENCE, role=Side.SELL), REFERENCE)


class TestASideDeclaresExactlyOneOfTheTwoForms:
    """Both set, or neither, is refused -- there is no precedence rule."""

    def test_a_side_declaring_both_forms_is_refused(self) -> None:
        # A "helpful" precedence rule ("markup wins if both are set") would silently
        # ignore one of the two numbers the owner wrote, and there is no reading of that
        # which is not a bug. The loader refuses it too (FR-010); this is the second gate,
        # for a record built in code.
        side = ChannelSide(
            markup_bps=150.0,
            premium_per_unit=Money(3.0, Currency.UAH, SOURCES),
            kind="p2p_premium",
            provenance=SOURCES,
        )
        with pytest.raises(ValueError, match="exactly one"):
            channels.spread_over_reference(side, REFERENCE, role=Side.BUY)

    def test_a_side_declaring_neither_form_is_refused(self) -> None:
        # Not treated as zero. "The channel is at the reference" is declarable as a zero
        # premium; an empty side is an incomplete declaration, and reading it as free
        # would make the cheapest possible route the one nobody finished describing.
        side = ChannelSide(
            markup_bps=None, premium_per_unit=None, kind="p2p_premium", provenance=SOURCES
        )
        with pytest.raises(ValueError, match="exactly one"):
            channels.spread_over_reference(side, REFERENCE, role=Side.SELL)


def _channel(buy: ChannelSide, sell: ChannelSide) -> FxChannel:
    return FxChannel(
        id="p2p",
        pair=(Currency.UAH, Currency.USD),
        reference_rate=REFERENCE,
        buy_side=buy,
        sell_side=sell,
        observed_on=date(2026, 8, 21),
        kind="p2p_premium",
        provenance=SOURCES,
    )


class TestBothSidesAreDeclaredAndNeitherIsDerived:
    """FR-010: no mid-rate, and no side computed from the other."""

    def test_the_leg_direction_selects_the_side(self) -> None:
        # The pair is ordered ``(price currency, unit currency)``: 42 UAH per USD. Paying
        # UAH to obtain USD is the buy side; giving up USD to obtain UAH is the sell side.
        # Getting this backwards is the classic FX bug, so it is asserted rather than
        # trusted to a comment.
        channel = _channel(_premium(3.0), _premium(-2.5))
        side, role = channels.side_for(channel, Currency.UAH, Currency.USD)
        assert role is Side.BUY
        assert side is channel.buy_side
        side, role = channels.side_for(channel, Currency.USD, Currency.UAH)
        assert role is Side.SELL
        assert side is channel.sell_side

    def test_the_two_sides_are_independent_numbers(self) -> None:
        # A channel whose spread is +3 in and -2.5 out is asymmetric, which is what a real
        # P2P book looks like. Nothing in the module can produce one side from the other:
        # this asserts the consequence -- the two fractions differ -- so a "symmetry
        # helper" added later would fail here.
        channel = _channel(_premium(3.0), _premium(-2.5))
        buy_side, buy_role = channels.side_for(channel, Currency.UAH, Currency.USD)
        sell_side, sell_role = channels.side_for(channel, Currency.USD, Currency.UAH)
        buy = channels.spread_over_reference(buy_side, channel.reference_rate, role=buy_role)
        sell = channels.spread_over_reference(sell_side, channel.reference_rate, role=sell_role)
        assert is_close(buy, 3.0 / 42.0)
        assert is_close(sell, 2.5 / 42.0)
        assert not is_close(buy, sell)

    def test_a_leg_whose_currencies_are_not_the_channels_pair_is_refused(self) -> None:
        # Never "near enough". A channel quotes one ordered pair, and applying it to any
        # other pair would be inventing a rate -- which is the one thing Principle I
        # forbids most firmly.
        channel = _channel(_premium(3.0), _premium(-2.5))
        with pytest.raises(ValueError, match="does not quote"):
            channels.side_for(channel, Currency.UAH, Currency.UAH)

    def test_a_reference_rate_of_zero_or_less_is_refused(self) -> None:
        # A cost fraction divides by the reference, and a route's arriving amount is
        # translated by it. Zero is not a rate, and a negative rate is not a rate; either
        # would produce a figure that looks like a number.
        side = _premium(3.0)
        with pytest.raises(ValueError, match="not a rate"):
            channels.spread_over_reference(side, 0.0, role=Side.BUY)
        with pytest.raises(ValueError, match="not a rate"):
            channels.effective_rate(side, -42.0, role=Side.SELL)
