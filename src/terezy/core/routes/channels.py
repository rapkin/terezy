"""FX channels: named, two-sided rate sources. A mid-rate is never used for a transaction.

FR-010: *exchange rates MUST be declared per **channel** -- official, interbank, bank
non-cash, cash desk, card, peer-to-peer -- and MUST be two-sided. A single mid-rate MUST
NEVER be used for a transaction.* FR-011: *which channel a leg uses MUST be part of the
leg's declaration, and the channel actually applied MUST appear in the attribution, because
the choice changes the result.*

**Why a rate is two numbers and a reference, not one number.** "The dollar is 42" is a
statement about a *reference* -- the official or interbank quote -- and nobody transacts at
it. What the owner actually faces is a price to buy and a different price to sell, and the
gap between them is the cost this whole feature exists to compute. A channel therefore
declares the reference it is quoted against and **both** sides independently. Neither side
is derived from the other: computing the sell side from the buy side would be using a
mid-rate with extra steps, and it would produce a symmetric spread for a market that is
routinely asymmetric.

**Two declaration forms, because the owner observes two different things.** A bank publishes
a percentage; a P2P screen shows a price per dollar against a reference. Converting the
second into a percentage by hand before entering it into a data file would put an arithmetic
step somewhere no test can see it, so both forms are declarable and the conversion happens
in :func:`_offset` -- once, here, with a worked example beside it in
``tests/worked_examples/test_channel_rates.py``.

**The sign conventions of the two forms differ, deliberately.**

* ``markup_bps`` is a **cost magnitude**. 150 bps costs 1.5% whichever way the money goes,
  so the buy rate is ``reference * (1 + m)`` and the sell rate is ``reference * (1 - m)``.
  This is how a tariff reads: "we charge 1.5% on currency conversion".
* ``premium_per_unit`` is a **signed offset from the reference**. Both sides are
  ``reference + premium``, so a buy side paying 3 UAH over declares ``+3`` and a sell side
  giving up 2.5 UAH declares ``-2.5``. This is how a P2P book reads, and it is the form
  that makes a *discount* (buying below the reference) expressible at all.

Reading one form with the other's convention is the likeliest bug in this module. Every case
is pinned by a hand-computed assertion, and the role -- buy or sell -- is a required
keyword so that no call site can leave the direction implicit.

**Two measures, and they are not interchangeable.** :func:`loss_fraction` is **the cost** --
what fraction of the money the spread took, ``p / (r + p)`` buying and ``p / r`` selling.
:func:`spread_over_reference` is ``p / r``, the spread over the reference *rate*, and is the
figure ``SIMULATOR_SPEC.md`` §4.3.1 quotes. They differ on the buy side: 6.67% against 7.14%
at §4.3.1's numbers.

The conversion itself happens at :func:`effective_rate`, so the arriving amount is the one
the venue would really hand over. An earlier version charged ``p / r`` of the amount and
converted the remainder at the reference -- reproducing §4.3.1's percentage exactly while
reporting an arriving amount short of reality. The full account is in
``terezy.core.routes.cost``.

**Where ``Provider`` will slot in.** A channel's reference rate is declared data today
because there is no network, no cache and no rate snapshot, and inventing a rate source is
the one thing Principle I forbids most firmly. The seam is the pair
``(channel, date) -> two-sided rate``: when ``Provider`` arrives, :class:`FxChannel` keeps
its markup fields and gets its reference from a provider call, and nothing that consumes
:func:`effective_rate` or :func:`loss_fraction` changes (research.md D1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final

from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance

_BASIS_POINTS_PER_UNIT: Final = 10_000.0
"""One basis point is a hundredth of a percent, so 150 bps is 0.015."""


class Side(Enum):
    """Which side of a two-sided quote a movement takes.

    An enum rather than a ``bool`` or a bare string: it is a closed sum type, which owner
    decision D-E welcomes, and a ``bool`` named ``is_buy`` would be exactly the kind of
    flag whose meaning has to be remembered at every call site.
    """

    BUY = "buy"
    """The unit currency is being acquired and the price currency handed over: UAH -> USD
    for a channel quoted as UAH per USD. Paying *more* than the reference is the cost."""

    SELL = "sell"
    """The unit currency is being given up and the price currency received: USD -> UAH.
    Receiving *less* than the reference is the cost."""


@dataclass(frozen=True, slots=True)
class ChannelSide:
    """One side of a channel's quote, declared in exactly one of the two forms."""

    markup_bps: float | None
    """A cost in basis points, always positive as a cost. ``None`` when the premium form
    is used.

    Exactly one of the two fields is set. Both set, or neither, is refused -- see
    :func:`_offset`.
    """

    premium_per_unit: Money | None
    """A signed offset from the reference, in price currency per unit of unit currency.

    ``+3`` UAH per USD is the form the owner actually observes on a P2P screen. **Zero is
    legal** and means the channel is at the reference; **negative is legal** and means it
    trades below the reference, which P2P genuinely does. A *missing* premium is refused
    (FR-010): "at the reference" is declarable as a zero, so an absence can only mean an
    unfinished declaration -- and reading an unfinished declaration as free would make the
    cheapest route the one nobody described.

    Typed ``Money`` rather than ``float`` so the premium states its currency and carries
    the provenance of the observation it came from. That provenance is what
    ``money.scale_sourced`` unions into every figure the premium touches, which is how a
    route cost admits which screenshot it rests on.
    """


@dataclass(frozen=True, slots=True)
class FxChannel:
    """A named, dated, two-sided rate source for one ordered currency pair."""

    id: str
    """``nbu_official``, ``interbank``, ``bank_non_cash``, ``cash_desk``, ``card``,
    ``p2p``. Appears in a cost's ``channels_applied`` so the reader can see which one was
    used (FR-011)."""

    pair: tuple[Currency, Currency]
    """The ordered pair this quote is for, as ``(price currency, unit currency)``.

    ``(UAH, USD)`` with a reference of 42 means *42 UAH per USD*. The order is load-bearing:
    it is what tells :func:`side_for` whether a leg is buying or selling, and reversing it
    would invert every spread in the system while leaving every number plausible.
    """

    reference_rate: float
    """Price-currency units per one unit of the unit currency, at the reference.

    The mid or official quote the two sides are expressed against. Never used on its own
    for a transaction (FR-010) -- a side's spread is always charged first.
    """

    buy_side: ChannelSide
    """The side applied when the unit currency is being acquired. Required."""

    sell_side: ChannelSide
    """The side applied when the unit currency is being given up. Required, and **not**
    derived from :attr:`buy_side`."""

    observed_on: date
    """When this quote was seen. Data, never a clock."""

    kind: str
    """An ``ObservationKind`` id -- ``p2p_premium``, ``bank_fee_schedule``. Selects the
    staleness threshold applied to this channel's sources (FR-028)."""

    provenance: Provenance
    """The sources this quote rests on. Required, and unioned into every figure the
    channel touches through ``money.scale_sourced``."""


def _checked_reference(reference: float) -> float:
    """The reference rate, or a raise if it is not a rate at all.

    Zero and negatives are refused rather than allowed to propagate: a cost fraction
    divides by the reference and a route's attribution translates through it, so either
    would produce a figure that looks like a number. Refusing an impossible input is not
    clamping -- nothing is being quietly improved, the question is being declined.
    """
    if reference <= 0.0:
        raise ValueError(
            f"a reference rate of {reference!r} is not a rate: a channel must quote a "
            "strictly positive number of price-currency units per unit of the unit "
            "currency (FR-010)"
        )
    return reference


def _offset(side: ChannelSide, reference: float) -> float:
    """The side's offset from the reference, in price-currency units, signed.

    The single place the two declaration forms meet, so their conventions cannot drift
    apart across call sites:

    * ``markup_bps`` -> ``reference * bps / 10 000``, a cost magnitude;
    * ``premium_per_unit`` -> the declared amount, a signed offset.

    **Exactly one of the two forms, always.** There is no precedence rule: "the markup
    wins if both are set" would silently ignore one of the two numbers the owner wrote,
    and an empty side is not zero -- zero is declarable, so an absence can only be an
    incomplete declaration. The data layer refuses both cases naming file and field
    (FR-010); this is the second gate, for a record built in code, and it raises because a
    malformed record reaching here means that validation was bypassed.
    """
    if side.markup_bps is not None and side.premium_per_unit is not None:
        raise ValueError(
            "a channel side declares exactly one of markup_bps / premium_per_unit; this "
            f"one declares both: markup_bps={side.markup_bps!r} and "
            f"premium_per_unit={side.premium_per_unit!r}. There is no precedence rule -- "
            "'the markup wins' would silently ignore one of the two numbers the owner "
            "wrote (FR-010)."
        )
    if side.markup_bps is not None:
        return reference * side.markup_bps / _BASIS_POINTS_PER_UNIT
    if side.premium_per_unit is not None:
        return side.premium_per_unit.amount
    raise ValueError(
        "a channel side declares exactly one of markup_bps / premium_per_unit; this one "
        "declares neither. An empty side is not zero: 'at the reference' is declared as a "
        "zero premium, so an absence can only mean an unfinished declaration, and reading "
        "an unfinished declaration as free would make the cheapest route the one nobody "
        "described (FR-010)."
    )


def effective_rate(side: ChannelSide, reference: float, *, role: Side) -> float:
    """The rate actually transacted at, in price-currency units per unit currency.

    ``role`` is a required keyword because the direction is the thing a call site must
    never leave implicit: on the buy side the offset is paid, on the sell side it is given
    up, and the same declared number therefore moves the rate in opposite directions.

    For the premium form both sides are ``reference + premium``, so the *signed* premium
    does the work: ``+3`` on the buy side pays 45 against a reference of 42, and ``-2.5``
    on the sell side receives 39.5. For the markup form the offset is a cost magnitude, so
    it is added on the buy side and subtracted on the sell side.
    """
    checked = _checked_reference(reference)
    offset = _offset(side, checked)
    if side.markup_bps is not None and role is Side.SELL:
        return checked - offset
    return checked + offset


def loss_fraction(side: ChannelSide, reference: float, *, role: Side) -> float:
    """The fraction of value actually lost to this side's spread. **The cost figure.**

    ``1 - reference/effective`` when buying the unit currency, ``1 - effective/reference``
    when selling. Both read as "of the value handed over, how much did the spread take",
    which is the question a cost figure answers.

    **This is not :func:`spread_over_reference`, and the difference is the point.** For a
    premium ``p`` against a reference ``r``, buying gives ``p / (r + p)`` here and ``p / r``
    there -- 6.67% against 7.14% at §4.3.1's numbers. The first is what leaves your pocket:
    10 000 UAH at a P2P price of 45 buys 222.22 USD, and 222.22 USD is worth 9 333.33 UAH at
    the reference, so 666.67 UAH went to the spread. The second is the spread measured
    against the reference *rate* -- a real and useful figure, and not a fraction of your
    money.

    An earlier implementation charged ``p / r`` of the amount and converted the remainder at
    the reference, because FR-004 named that as the cost. It reproduced §4.3.1's percentage
    exactly and reported an **arriving amount 1.13 USD short of what the exchange would
    actually hand over** on a 10 000 UAH purchase. The requirement was corrected rather than
    the arithmetic bent to it: a figure labelled "cost" has to be the cost, and the money has
    to be the money.

    On the **sell** side the two coincide exactly -- ``1 - (r-p)/r`` is ``p/r`` -- so this
    correction changed the buy side only.

    **May be negative** where a channel trades above the reference on the buy side. That is a
    discount, reported as one; clamping it would be the defect class of clamping a fee at the
    amount moved.
    """
    checked = _checked_reference(reference)
    effective = effective_rate(side, checked, role=role)
    if role is Side.SELL:
        return 1.0 - effective / checked
    return 1.0 - checked / effective


def spread_over_reference(side: ChannelSide, reference: float, *, role: Side) -> float:
    """The spread as a fraction of the **reference rate** -- a rate-space measure.

    For a premium of ``p`` against a reference of ``r`` this is exactly ``p / r``, which is
    the figure ``SIMULATOR_SPEC.md`` §4.3.1 quotes: ``3 / 42 = 7.14%``, and the arithmetic
    behind its "4.8-9.5% one way" for premiums of +2 to +4. For a markup of ``m`` basis
    points it is exactly ``m / 10 000``.

    Reported **beside** :func:`loss_fraction`, never instead of it. §4.3.1 labels its own
    arithmetic illustrative ("substitute the live rate; this is illustrative"), so treating
    it as the definition of cost was a misreading of the document. Keeping it means the
    tool's output stays traceable to the claim in the specification that motivated the whole
    feature, while the cost figure says what actually left the pocket.
    """
    checked = _checked_reference(reference)
    effective = effective_rate(side, checked, role=role)
    if role is Side.SELL:
        return (checked - effective) / checked
    return (effective - checked) / checked


def side_for(
    channel: FxChannel, from_currency: Currency, to_currency: Currency
) -> tuple[ChannelSide, Side]:
    """Which side of this channel a movement between two currencies takes.

    The pair is ordered ``(price currency, unit currency)``. Moving from the price currency
    to the unit currency acquires the unit currency, which is the **buy** side; the reverse
    is the **sell** side. Getting this backwards is the classic FX bug -- every number stays
    plausible while every spread is inverted -- so the mapping is returned as a value and
    asserted in a worked example rather than left to a comment at each call site.

    Any other pair of currencies raises. A channel quotes one ordered pair and applying it
    to another would be inventing a rate, which no amount of convenience justifies. The
    resolver checks the same thing at load time and can name the file and the leg index;
    reaching here with a mismatch means that check was bypassed.
    """
    price_currency, unit_currency = channel.pair
    if from_currency is price_currency and to_currency is unit_currency:
        return channel.buy_side, Side.BUY
    if from_currency is unit_currency and to_currency is price_currency:
        return channel.sell_side, Side.SELL
    raise ValueError(
        f"channel {channel.id!r} does not quote "
        f"{from_currency.value} -> {to_currency.value}: it quotes "
        f"{price_currency.value} per {unit_currency.value}. No rate is inferred for any "
        "other pair (FR-010)."
    )
