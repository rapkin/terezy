"""One hand-checked case per leg kind, and an unknown kind failing loudly.

FR-001: *the system MUST cost a stated amount through a declared route by applying each leg
in order, and MUST report what arrives at the far end.* A leg is that unit of application,
and the four kinds this engine implements -- ``transfer``, ``fx``, ``trade``,
``withdrawal`` -- are the key set of an algorithm registry, exactly as the day-count
conventions are (research.md D1). This module checks each one's arithmetic by hand and
checks that the registry has no fallback.

**Why the registry matters more than the arithmetic here.** Three of the four kinds share one
implementation, because their arithmetic genuinely is the same: a percentage fee, a fixed
fee, no conversion. That is stated rather than hidden -- inventing a difference between a
transfer and a withdrawal to justify separate code would be fabricating domain behaviour,
which is worse than sharing a function. What the four distinct *names* buy is that a real
difference later (a tiered trading commission, a withdrawal minimum) lands without renaming
a single declaration, and that the attribution tells a reader which kind of thing charged
them.

**Nothing is clamped.** A fixed fee larger than the amount produces a negative outgoing
amount, and it is reported as negative. Predecessor defect B13 was exactly a
``max(gross - fee, 0)`` that made money vanish with no diagnostic; the case is asserted here
at the leg level and again as a property in ``tests/invariants``.
"""

from __future__ import annotations

from datetime import date

import pytest

from terezy.core.errors import CurrencyMismatchError
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import assert_money_close, is_close
from terezy.core.routes import legs
from terezy.core.routes.channels import ChannelSide, FxChannel
from terezy.core.routes.legs import Leg

UAH = Currency.UAH
USD = Currency.USD

LEG_SOURCE = SourceRef(
    id="synthetic:leg",
    citation="SYNTHETIC FIXTURE -- invented fee schedule. Not an observed tariff.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)
CHANNEL_SOURCE = SourceRef(
    id="synthetic:channel",
    citation="SYNTHETIC FIXTURE -- invented reference and premium. Not an observed quote.",
    retrieved_on=date(2026, 8, 21),
    verified_on=None,
)
LEG_SOURCES: Provenance = prov.of([LEG_SOURCE])
CHANNEL_SOURCES: Provenance = prov.of([CHANNEL_SOURCE])

REFERENCE = 42.0


def _leg(
    *,
    kind: str,
    from_ccy: Currency = UAH,
    to_ccy: Currency = UAH,
    channel: str | None = None,
    fee_pct: float = 0.0,
    fee_fixed: float = 0.0,
    fee_currency: Currency | None = None,
) -> Leg:
    """A leg with everything not under test set to a declared zero.

    Zeroes rather than omissions: there are no defaults anywhere in this stack, so every
    field is stated even when the test does not care about it, and a reader can see that
    the fee under test is the only one that is not zero.
    """
    return Leg(
        index=0,
        kind=kind,
        from_venue="monobank_uah",
        to_venue="binance",
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=channel,
        fee_pct=fee_pct,
        fee_fixed=Money(fee_fixed, fee_currency or from_ccy, LEG_SOURCES),
        minimum=None,
        maximum=None,
        monthly_cap=None,
        capacity_pool=None,
        latency_days=0,
        available_from=None,
        available_until=None,
        disruption_probability=0.0,
        kind_of_observation="bank_fee_schedule",
        provenance=LEG_SOURCES,
    )


def _channel(premium: float) -> FxChannel:
    return FxChannel(
        id="p2p",
        pair=(UAH, USD),
        reference_rate=REFERENCE,
        buy_side=ChannelSide(
            markup_bps=None, premium_per_unit=Money(premium, UAH, CHANNEL_SOURCES)
        ),
        sell_side=ChannelSide(
            markup_bps=None, premium_per_unit=Money(-premium, UAH, CHANNEL_SOURCES)
        ),
        observed_on=date(2026, 8, 21),
        kind="p2p_premium",
        provenance=CHANNEL_SOURCES,
    )


class TestTheRegistryIsTheContract:
    """A mapping from a declared name to a plain function. No fallback, no subclassing."""

    def test_the_four_implemented_kinds_are_exactly_the_key_set(self) -> None:
        assert set(legs.LEG_COST_FNS) == {"transfer", "fx", "trade", "withdrawal"}

    def test_an_unknown_kind_fails_naming_the_value_and_the_known_ones(self) -> None:
        # The message is the remedy: an unrecognised kind is almost always a typo, and a
        # message listing the alternatives fixes it in one step. What must never happen is
        # a fallback -- silently applying ``transfer`` to a leg that declared something
        # else would produce a plausible cost with no conversion in it.
        with pytest.raises(KeyError, match="unknown leg kind") as raised:
            legs.cost_fn_for("crypto_bridge")
        for known in ("transfer", "fx", "trade", "withdrawal"):
            assert known in str(raised.value)

    def test_the_declared_kind_selects_a_function_and_nothing_else_does(self) -> None:
        # Dispatch is on ``leg.kind`` and only on ``leg.kind``. A branch on a venue or a
        # provider id would make behaviour code rather than data (Principle II).
        assert legs.cost_fn_for("fx") is legs.LEG_COST_FNS["fx"]
        assert legs.cost_fn_for("transfer") is not legs.LEG_COST_FNS["fx"]


class TestTheFeeOnlyKinds:
    """``transfer``, ``trade`` and ``withdrawal``: a percentage fee, a fixed fee, no rate."""

    def test_a_transfer_charges_its_percentage_and_its_fixed_fee(self) -> None:
        #   10 000.00 UAH sent
        #   percentage fee = 10 000 * 0.01 =   100.00
        #   fixed fee                      =    25.00
        #   arriving       = 10 000 - 125  = 9 875.00
        outcome = legs.cost_fn_for("transfer")(
            _leg(kind="transfer", fee_pct=0.01, fee_fixed=25.0),
            Money(10_000.0, UAH, prov.EMPTY),
            None,
        )
        assert_money_close(outcome.percentage_fee, Money(100.0, UAH, prov.EMPTY))
        assert_money_close(outcome.fixed_fee, Money(25.0, UAH, prov.EMPTY))
        assert_money_close(outcome.conversion_spread, Money(0.0, UAH, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(9_875.0, UAH, prov.EMPTY))
        assert outcome.channel_applied is None

    def test_a_trade_commission_is_the_same_arithmetic_under_its_own_name(self) -> None:
        #   200.00 USD traded, 0.5% commission = 1.00, arriving 199.00
        outcome = legs.cost_fn_for("trade")(
            _leg(kind="trade", from_ccy=USD, to_ccy=USD, fee_pct=0.005),
            Money(200.0, USD, prov.EMPTY),
            None,
        )
        assert_money_close(outcome.percentage_fee, Money(1.0, USD, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(199.0, USD, prov.EMPTY))

    def test_a_withdrawal_charges_a_flat_fee(self) -> None:
        #   200.00 USD withdrawn, flat 25.00 USD, arriving 175.00
        outcome = legs.cost_fn_for("withdrawal")(
            _leg(kind="withdrawal", from_ccy=USD, to_ccy=USD, fee_fixed=25.0),
            Money(200.0, USD, prov.EMPTY),
            None,
        )
        assert_money_close(outcome.fixed_fee, Money(25.0, USD, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(175.0, USD, prov.EMPTY))

    def test_a_zero_fee_leg_delivers_exactly_what_it_was_given(self) -> None:
        # The bar every other route is measured against (SC-004): a leg declaring zero
        # fees costs *exactly* zero, not a small residual. Asserted with an exact equality
        # on the amount as well as through the tolerance, because "exactly" is the claim.
        outcome = legs.cost_fn_for("transfer")(
            _leg(kind="transfer"), Money(10_000.0, UAH, prov.EMPTY), None
        )
        assert outcome.outgoing.amount == 10_000.0
        assert outcome.percentage_fee.amount == 0.0
        assert outcome.fixed_fee.amount == 0.0
        assert outcome.conversion_spread.amount == 0.0

    def test_a_fee_larger_than_the_amount_leaves_a_negative_amount_and_says_so(self) -> None:
        # B13. A fixed fee of 25 on a transfer of 10 arrives at -15, and -15 is what is
        # reported. ``max(amount - fee, 0)`` here is how the predecessor made money vanish
        # with no diagnostic; the honest answer is a negative number a reader can see.
        outcome = legs.cost_fn_for("withdrawal")(
            _leg(kind="withdrawal", fee_fixed=25.0), Money(10.0, UAH, prov.EMPTY), None
        )
        assert_money_close(outcome.outgoing, Money(-15.0, UAH, prov.EMPTY))

    def test_a_fee_only_leg_refuses_a_channel(self) -> None:
        # A transfer with a channel is a declaration that means nothing, and accepting it
        # would let a reader believe a conversion happened. The loader refuses it too
        # (FR-011); this is the gate for a record built in code.
        with pytest.raises(ValueError, match="does not convert"):
            legs.cost_fn_for("transfer")(
                _leg(kind="transfer", channel="p2p"), Money(10.0, UAH, prov.EMPTY), _channel(3.0)
            )

    def test_a_fee_only_leg_refuses_two_different_currencies(self) -> None:
        # Only an ``fx`` leg converts. A transfer declaring UAH in and USD out would
        # otherwise have to invent a rate to satisfy its own declaration.
        with pytest.raises(ValueError, match="does not convert"):
            legs.cost_fn_for("transfer")(
                _leg(kind="transfer", from_ccy=UAH, to_ccy=USD), Money(10.0, UAH, prov.EMPTY), None
            )


class TestTheFxKind:
    """The one kind that converts, and the only one that may name a channel."""

    def test_buying_dollars_at_a_three_hryvnia_premium(self) -> None:
        #   10 000.00 UAH sent, reference 42, buy-side premium +3 -> price 45
        #   arriving      = 10 000 / 45          =   222.22222222222223 USD
        #   worth at ref  = 222.2222... * 42     = 9 333.333333333334  UAH
        #   spread        = 10 000 - 9 333.33... =   666.6666666666665  UAH
        #   loss fraction = 666.667 / 10 000     = 0.0666666... = 3/45 = p/(r+p)
        #
        # **This example was corrected.** It previously charged ``3/42`` of the amount and
        # converted the remainder at the reference, because FR-004 named ``p/r`` as the
        # cost -- and reported 221.088 USD arriving where the venue would actually hand
        # over 222.222, short by 1.13 USD. The requirement was corrected rather than the
        # arithmetic bent to it. ``3/42 = 7.14%`` is still reported, by
        # ``channels.spread_over_reference``, as the spread over the reference *rate*;
        # ``3/45 = 6.67%`` is what left the pocket.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p"),
            Money(10_000.0, UAH, prov.EMPTY),
            _channel(3.0),
        )
        assert_money_close(outcome.conversion_spread, Money(666.6666666666665, UAH, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(222.22222222222223, USD, prov.EMPTY))
        assert outcome.channel_applied == "p2p"

    def test_selling_dollars_reproduces_the_quoted_price_exactly(self) -> None:
        #   200.00 USD sold, reference 42, sell-side premium -3 -> 39 UAH per USD
        #   cost fraction = 3 / 42 = 0.07142857142857142
        #   spread        = 200 * 3 / 42        =  14.285714285714286 USD
        #   net of spread = 200 - 14.2857...    = 185.71428571428572  USD
        #   arriving      = 185.714... * 42     = 7 800.00            UAH
        #   and 200 * 39 = 7 800.00 -- the same number.
        #
        # On the sell side the two conventions coincide exactly, because the spread is
        # charged in the unit currency and the rate multiplies: ``N(1 - p/r) * r``  is
        # ``N(r - p)``. The second-order gap exists only when buying, where the rate
        # divides.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=USD, to_ccy=UAH, channel="p2p"),
            Money(200.0, USD, prov.EMPTY),
            _channel(3.0),
        )
        assert_money_close(outcome.conversion_spread, Money(14.285714285714286, USD, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(7_800.0, UAH, prov.EMPTY))

    def test_a_zero_premium_channel_converts_at_the_reference_and_costs_nothing(self) -> None:
        #   4 200.00 UAH at a zero premium on a reference of 42 -> 100.00 USD, cost 0.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p"),
            Money(4_200.0, UAH, prov.EMPTY),
            _channel(0.0),
        )
        assert outcome.conversion_spread.amount == 0.0
        assert_money_close(outcome.outgoing, Money(100.0, USD, prov.EMPTY))

    def test_fees_and_a_spread_are_attributed_separately(self) -> None:
        # FR-003: a reader has to be able to see which term dominates. Fees are charged on
        # the amount entering the leg, in the sending currency; the spread is then what the
        # conversion of what remains actually cost.
        #   10 000.00 UAH, 1% fee, 50.00 fixed, premium +3 -> price 45
        #   percentage fee = 100.00
        #   fixed fee      =  50.00
        #   after fees     = 10 000 - 150 = 9 850.00 UAH
        #   arriving       = 9 850 / 45   =   218.88888888888889 USD
        #   spread         = 9 850 * 3/45 =   656.6666666666665  UAH
        #
        # Note the spread is charged on 9 850 and not on 10 000: the fees are taken before
        # the money is converted, so the spread applies to what was actually converted.
        # Attributing it to the full amount would double-count the fee-bearing slice.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p", fee_pct=0.01, fee_fixed=50.0),
            Money(10_000.0, UAH, prov.EMPTY),
            _channel(3.0),
        )
        assert_money_close(outcome.percentage_fee, Money(100.0, UAH, prov.EMPTY))
        assert_money_close(outcome.fixed_fee, Money(50.0, UAH, prov.EMPTY))
        assert_money_close(outcome.conversion_spread, Money(656.6666666666665, UAH, prov.EMPTY))
        assert_money_close(outcome.outgoing, Money(218.88888888888889, USD, prov.EMPTY))

    def test_an_fx_leg_without_a_channel_is_refused(self) -> None:
        # Never converted at the reference "just this once". A conversion with no declared
        # channel is a mid-rate transaction, which FR-010 forbids outright.
        with pytest.raises(ValueError, match="requires a channel"):
            legs.cost_fn_for("fx")(
                _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p"),
                Money(10.0, UAH, prov.EMPTY),
                None,
            )

    def test_an_fx_leg_that_does_not_change_currency_is_refused(self) -> None:
        # The channel would have no side to take. A same-currency conversion is a
        # declaration error, not a no-op to be absorbed.
        with pytest.raises(ValueError, match="does not quote"):
            legs.cost_fn_for("fx")(
                _leg(kind="fx", from_ccy=UAH, to_ccy=UAH, channel="p2p"),
                Money(10.0, UAH, prov.EMPTY),
                _channel(3.0),
            )

    def test_a_fee_in_the_wrong_currency_is_a_raised_mismatch_not_a_conversion(self) -> None:
        # A fixed fee declared in USD on a leg sending UAH cannot be subtracted, and the
        # currency tag says so rather than picking a rate. C5 / Principle VI.
        with pytest.raises(CurrencyMismatchError):
            legs.cost_fn_for("fx")(
                _leg(
                    kind="fx",
                    from_ccy=UAH,
                    to_ccy=USD,
                    channel="p2p",
                    fee_fixed=25.0,
                    fee_currency=USD,
                ),
                Money(10_000.0, UAH, prov.EMPTY),
                _channel(3.0),
            )


class TestEveryFigureAdmitsWhereItCameFrom:
    """FR-022 / E5: the declared rate's and the declared fee's marks reach the result."""

    def test_the_spread_carries_the_channels_sources(self) -> None:
        # ``money.scale_sourced``, not ``money.scale``: the premium came from data, so the
        # figure it produced has to admit which observation it rests on. A route cost that
        # did not name its premium's source is the top-severity defect class.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p"),
            Money(10_000.0, UAH, prov.EMPTY),
            _channel(3.0),
        )
        assert CHANNEL_SOURCE in outcome.conversion_spread.provenance.sources
        assert prov.is_unverified(outcome.conversion_spread.provenance)

    def test_a_zero_conversion_component_still_cites_the_leg_that_declared_it(self) -> None:
        # FR-009 requires the conversion component of a non-converting leg to be *exactly*
        # zero. Principle I requires it to say why: an unmarked zero is indistinguishable
        # from a conversion nobody costed, in the same way that a zero tax charge which
        # cannot cite its exemption is indistinguishable from a rule that never ran.
        outcome = legs.cost_fn_for("transfer")(
            _leg(kind="transfer"), Money(10_000.0, UAH, prov.EMPTY), None
        )
        assert outcome.conversion_spread.amount == 0.0
        assert LEG_SOURCE in outcome.conversion_spread.provenance.sources

    def test_the_percentage_fee_carries_the_legs_sources(self) -> None:
        outcome = legs.cost_fn_for("transfer")(
            _leg(kind="transfer", fee_pct=0.01), Money(10_000.0, UAH, prov.EMPTY), None
        )
        assert LEG_SOURCE in outcome.percentage_fee.provenance.sources

    def test_the_arriving_amount_carries_both_the_fee_and_the_rate_sources(self) -> None:
        # The mark is monotone: it grows as a figure is derived and never shrinks. What
        # arrives at the far end rests on the fee schedule *and* on the rate, so it names
        # both.
        outcome = legs.cost_fn_for("fx")(
            _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p", fee_pct=0.01),
            Money(10_000.0, UAH, prov.EMPTY),
            _channel(3.0),
        )
        assert {LEG_SOURCE, CHANNEL_SOURCE} <= outcome.outgoing.provenance.sources


class TestConvertingMoneyBetweenCurrencies:
    """The one function that builds an amount in a currency other than its input's."""

    def test_a_conversion_carries_the_rates_sources(self) -> None:
        converted = money.convert(
            Money(4_200.0, UAH, prov.EMPTY),
            to_currency=USD,
            rate=1.0 / REFERENCE,
            sources=CHANNEL_SOURCES,
        )
        assert converted.currency is USD
        assert is_close(converted.amount, 100.0)
        assert CHANNEL_SOURCE in converted.provenance.sources

    def test_a_conversion_to_the_same_currency_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a conversion"):
            money.convert(
                Money(1.0, UAH, prov.EMPTY), to_currency=UAH, rate=1.0, sources=CHANNEL_SOURCES
            )

    def test_a_rate_of_zero_or_less_is_refused(self) -> None:
        with pytest.raises(ValueError, match="not a rate"):
            money.convert(
                Money(1.0, UAH, prov.EMPTY), to_currency=USD, rate=0.0, sources=CHANNEL_SOURCES
            )


class TestResolvingALegsDeclaredChannel:
    """A leg names its channel, and an unnamed one is refused rather than substituted."""

    def test_a_leg_naming_no_channel_resolves_to_none(self) -> None:
        assert legs.channel_for({"p2p": _channel(3.0)}, _leg(kind="transfer")) is None

    def test_a_leg_naming_a_declared_channel_resolves_to_it(self) -> None:
        channel = _channel(3.0)
        leg = _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p")
        assert legs.channel_for({"p2p": channel}, leg) is channel

    def test_a_leg_naming_an_undeclared_channel_fails_naming_what_is_known(self) -> None:
        # No fallback channel, ever. Substituting the official rate for a misspelt id would
        # silently reprice a P2P leg at the reference and delete the entire spread this
        # feature exists to measure -- and the result would look like a cheap route.
        leg = _leg(kind="fx", from_ccy=UAH, to_ccy=USD, channel="p2p_v2")
        with pytest.raises(KeyError, match="unknown channel") as raised:
            legs.channel_for({"p2p": _channel(3.0)}, leg)
        assert "p2p" in str(raised.value)
