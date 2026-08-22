"""One movement of money, the route that chains them, and the leg-kind algorithm registry.

FR-001: *the system MUST cost a stated amount through a declared route by applying each leg
in order, and MUST report what arrives at the far end.* A leg is that unit of application: a
transfer, a conversion, a trade, a withdrawal, carrying its own fees, limits, latency,
availability window, disruption probability and provenance.

**The registry is a mapping of functions, and it is not a fifth plugin interface**
(research.md D1, and the argument in this package's ``__init__``). ``LEG_COST_FNS`` is an
*algorithm* registry on the precedent set by ``DAY_COUNT_FNS`` in
``primitives.conventions``: the choice of kind is data, the arithmetic behind each kind is
code. Principle II requires that adding an instrument, venue, tax regime or jurisdiction be
data-only, and a leg kind is none of those four. Adding a leg that *uses* a kind is data,
which is the property the principle actually protects.

**Three of the four kinds share one implementation, and that is stated rather than hidden.**
A transfer, a trade and a withdrawal all charge a percentage of the amount plus a fixed fee
and convert nothing; their arithmetic genuinely is identical. Inventing a difference to
justify three functions would be fabricating domain behaviour, which is a worse fault than
sharing one. What the three distinct *names* buy is real: the attribution tells a reader
which kind of thing charged them, the resolver can hold each kind to different structural
rules, and a genuine difference later -- a tiered trading commission, a withdrawal minimum
in the venue's own currency -- lands without renaming a single declaration.

**Where ``Route`` lives, and why here.** A route is its ordered chain of legs; the two are
one declaration read from one table, and splitting the record from the thing it is made of
would put two halves of the same file's contents in two modules. Nothing else in this
package needs ``Route`` without also needing ``Leg``.

**Chaining is validated at load, not here** (research.md D6). Currency and venue continuity
-- leg *n* ending where leg *n+1* begins, the first leg at the route's declared origin, the
last at its destination -- is a structural property of the declaration, knowable with no
amount and no date, so it is checked in ``terezy.data.declarations.resolver`` where the error
can name the file and the leg index. Core may assume a chained route. What core does *not*
assume is the per-leg consistency each cost function needs to do arithmetic at all -- an
``fx`` leg with no channel, a transfer declaring two currencies -- because those would make
this module invent a rate, and every one of them raises here as well.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.routes import channels
from terezy.core.routes.channels import FxChannel, Side

TRANSFER: Final = "transfer"
"""Value moves between two venues, one currency, a percentage and/or a fixed fee."""

FX: Final = "fx"
"""Value changes currency through a declared channel. The only kind that converts."""

TRADE: Final = "trade"
"""Value is bought or sold at a venue; the fee is the commission."""

WITHDRAWAL: Final = "withdrawal"
"""Value leaves a venue for an external account; the fee is usually flat."""

RouteDirection = Literal["inbound", "exit"]
"""Declared, never inferred. An exit route is a separate declaration, not a reversal
(FR-027)."""

RouteStatus = Literal["open", "constrained", "closed"]
"""A ``Literal`` rather than a ``str`` so a misspelt status is a type error rather than a
route that is silently never closed."""


@dataclass(frozen=True, slots=True)
class Leg:
    """One movement, as declared. Carries only data; the arithmetic is below."""

    index: int
    """Position in the chain, from zero. Stated rather than taken from list order, so a
    load-time error can name the leg the declaration itself names."""

    kind: str
    """A key of :data:`LEG_COST_FNS`. An unknown kind fails at load naming the value and
    the known ones -- there is no fallback kind, because silently applying ``transfer`` to
    a leg that declared ``fx`` would produce a plausible cost with no conversion in it."""

    from_venue: str
    """Venue id this leg starts at."""

    to_venue: str
    """Venue id this leg ends at."""

    from_ccy: Currency
    """Currency in. Equal to :attr:`to_ccy` for every kind except ``fx``."""

    to_ccy: Currency
    """Currency out."""

    channel: str | None
    """The ``FxChannel`` id applied, **required** when ``kind == "fx"`` and **forbidden**
    otherwise (FR-011). A transfer with a channel is a declaration that means nothing, and
    accepting it would let a reader believe a conversion happened."""

    fee_pct: float
    """A fraction of the amount entering this leg -- ``0.01``, never ``1.0`` for one
    percent. Percent lives only in declaration files, where a ``_pct`` suffix names it, and
    is divided by 100 exactly once at the data boundary."""

    fee_fixed: Money
    """A flat fee, in its own declared currency.

    Typed ``Money`` rather than ``float`` on purpose: a fee declared in a currency other
    than the leg's ``from_ccy`` cannot be subtracted, and the currency tag raises rather
    than picking a rate to make the subtraction work (C5).
    """

    minimum: Money | None
    """The smallest amount this leg will carry, or ``None`` when none is declared. An
    amount below it makes the route unusable, reported with the shortfall -- never rounded
    up (FR-014)."""

    maximum: Money | None
    """The largest amount this leg will carry per movement, or ``None``."""

    monthly_cap: Money | None
    """The most this leg will carry in a calendar month, or ``None``. Capacity already
    consumed in the same month is the accumulator's business (FR-015)."""

    capacity_pool: str | None
    """The shared resource whose monthly limit this leg consumes, or ``None`` for none.

    A limit belongs to a **rail** -- a card, an account, a corridor under a regulatory
    ceiling -- and a route is a path that *uses* rails. Two different routes both moving money
    through the owner's Monobank card consume **one** limit, so both legs name the same pool
    and the accumulator keys on the pool rather than on the route.

    Keying on the route instead was the first design, and it was wrong in a way that mattered:
    each route would have received its own full monthly limit, and Monobank's limit is one of
    the four figures §11 item 1 names as the reason this feature exists. Two legs naming one
    pool must declare the **same** cap; a mismatch is a load-time failure, because two numbers
    for one real limit means at least one is wrong and choosing either would be a guess.
    """

    latency_days: int
    """How long this leg takes. Non-negative. Summed over the chain, and reported beside
    the cost rather than inside it -- a slow route is not an expensive one."""

    available_from: date | None
    """First date this leg works, or ``None`` for "always".

    **A fact about the leg, with a source** -- "this corridor closed in March 2025". Never
    an assumption: a regime transition ("the war ends mid-2027") is scenario data with an
    explicit assumption marker, because burying a guess in a field whose every other value
    is an observation would make the two indistinguishable in every output (research.md D8).
    """

    available_until: date | None
    """Last date this leg works, or ``None``. Same epistemic status as
    :attr:`available_from`."""

    disruption_probability: float
    """The chance this leg stops working, in ``[0, 1]``.

    Reported, and **never folded into a cost** (FR-026). The chance a route stops working
    is a different claim from what it charges, and multiplying the two would produce a
    single number that answers neither question.
    """

    kind_of_observation: str
    """An ``ObservationKind`` id -- which staleness threshold this leg's declared numbers
    age under (FR-028)."""

    provenance: Provenance
    """The sources this leg's declared numbers rest on. Required, and unioned into every
    figure they touch."""


@dataclass(frozen=True, slots=True)
class Route:
    """An ordered chain of legs from one venue to another, as declared."""

    id: str
    """Unique across every route declaration."""

    provider: str
    """The named provider -- ``TransferGo``, ``Monobank``, ``Binance P2P``.

    Registry identity is ``(provider x currency path x venue)`` and **not** provider alone
    (FR-023), because the number of conversions is usually the largest difference between
    two ways of doing the same thing. A duplicate triple is a load-time failure.
    """

    origin: str
    """Venue id the first leg starts at."""

    destination: str
    """Venue id the last leg ends at."""

    direction: RouteDirection
    """``inbound`` or ``exit``, declared rather than inferred (FR-027)."""

    partner_route: str | None
    """The exit route paired with this inbound one.

    ``None`` is a legitimate declaration and means *nobody has costed the way out*. It
    yields ``ExitCostUnknown`` and **no round-trip figure** (FR-030) -- never a reversal of
    this route, and never the one-way figure promoted into the round-trip slot.
    """

    status: RouteStatus
    """Whether the route works at all. A closed route is excluded from a comparison *with
    its status recorded*, never silently omitted (FR-014)."""

    legs: tuple[Leg, ...]
    """Non-empty. A route with no legs is refused at load rather than costed as free --
    free is the answer a reader would least question and the one most likely to be wrong."""


@dataclass(frozen=True, slots=True)
class LegOutcome:
    """What one leg did: what left it, and what it charged, split by component.

    Three named fields rather than a mapping keyed by a component name. The closed set is
    the point (FR-003): a free-form mapping would let a leg invent a component name, and
    the components-sum-to-total invariant would then be satisfiable by a cost hiding under
    a key nobody sums. ``terezy.core.results.ramp.CostComponent`` is the same closed set at
    the route level, and ``cost`` is the single place the two are bound together.
    """

    outgoing: Money
    """What leaves this leg, in :attr:`Leg.to_ccy`. **May be zero or negative** when the
    fees exceed the amount, and is reported that way (B13)."""

    conversion_spread: Money
    """What the channel's spread cost, in :attr:`Leg.from_ccy`. Exactly zero -- not a small
    residual -- for every kind but ``fx`` (FR-009)."""

    percentage_fee: Money
    """``fee_pct`` applied to the amount entering the leg, in :attr:`Leg.from_ccy`."""

    fixed_fee: Money
    """The declared flat fee, in its own currency, which must be :attr:`Leg.from_ccy`."""

    spread_over_reference: float | None
    """The leg's spread as a fraction of the reference **rate**, or ``None`` for a leg that
    converts nothing.

    ``p / r`` for a premium form -- the figure ``SIMULATOR_SPEC.md`` §4.3.1 quotes, and the
    arithmetic behind its "4.8-9.5% one way". Carried through to the result so SC-002's "both
    figures present, each labelled" is true of the *result record* and not only of a function
    a caller could call. It is **not** the cost: that is ``conversion_spread``, derived from
    :func:`channels.loss_fraction`. The two differ on the buy side and the difference is a
    correction this project already got wrong once.
    """

    channel_applied: str | None
    """Which channel this leg used, or ``None`` for a leg that converts nothing. Reaches
    the result's ``channels_applied`` because the choice changes the number (FR-011)."""


LegCostFn = Callable[[Leg, Money, FxChannel | None], LegOutcome]
"""Cost one leg: ``(leg, amount entering it, its channel or None) -> outcome``.

Obligations, all of them checkable by reading one implementation:

* **Pure.** No clock, no I/O, no state. Called twice with equal arguments it returns equal
  results, which is what makes C4 determinism reachable.
* **Nothing clamped.** If the fees exceed the amount, ``outgoing`` goes to or below zero and
  is reported (B13). No ``max(..., 0)`` anywhere.
* **Every declared factor applied through ``money.scale_sourced``**, so the figure admits
  which observation it rests on. A fee or a premium applied through plain ``money.scale``
  would silently drop the declaration's mark, and that is the top-severity defect class.
* **Attribution complete.** Every component of the charge appears in exactly one field, and
  the three fields plus ``outgoing`` account for the whole amount that entered.
"""


def _fee_components(leg: Leg, amount: Money) -> tuple[Money, Money]:
    """The percentage and fixed fees this leg charges on an amount entering it.

    Both in the leg's ``from_ccy``. ``fee_pct`` goes through ``money.scale_sourced``
    because it came from a declaration file: the leg's provenance is unioned into the fee,
    and from there into everything derived from it. The fixed fee already *is* a declared
    ``Money`` and carries its own mark; if its currency is not the leg's, the subtraction
    below raises rather than inventing a rate.
    """
    percentage = money.scale_sourced(amount, leg.fee_pct, leg.provenance)
    return percentage, leg.fee_fixed


def _fee_only_cost(leg: Leg, amount: Money, channel: FxChannel | None) -> LegOutcome:
    """``transfer``, ``trade`` and ``withdrawal``: fees, no conversion.

    One implementation under three names. See the module docstring for why that is stated
    rather than papered over with three copies.

    Refuses a channel and refuses two different currencies. Either would mean this leg was
    declared as a conversion while being costed as one that converts nothing, and the only
    way to satisfy such a declaration would be to invent a rate.
    """
    if channel is not None or leg.channel is not None or leg.from_ccy is not leg.to_ccy:
        raise ValueError(
            f"leg {leg.index} of kind {leg.kind!r} does not convert: it may not name a "
            f"channel and its currencies must match, but it declares channel "
            f"{leg.channel!r} and {leg.from_ccy.value} -> {leg.to_ccy.value}. Only an "
            f"{FX!r} leg converts (FR-011)."
        )
    percentage, fixed = _fee_components(leg, amount)
    return LegOutcome(
        outgoing=money.sub(money.sub(amount, percentage), fixed),
        # A zero that cites the declaration saying this leg converts nothing, rather than
        # ``money.zero``'s unmarked identity. FR-009 wants the conversion component to be
        # *exactly* zero here, and Principle I wants it to say why: a zero that cannot cite
        # its own declaration is indistinguishable from a conversion nobody costed, exactly
        # as a zero tax charge that cannot cite its exemption is indistinguishable from a
        # rule that never ran.
        conversion_spread=money.scale_sourced(amount, 0.0, leg.provenance),
        percentage_fee=percentage,
        fixed_fee=fixed,
        # ``None``, not ``0.0``: this leg has no reference rate to have a spread over, and a
        # zero would read as "at the reference" -- a claim about a conversion that never
        # happened (FR-009).
        spread_over_reference=None,
        channel_applied=None,
    )


def _fx_cost(leg: Leg, amount: Money, channel: FxChannel | None) -> LegOutcome:
    """``fx``: charge the channel side's spread, then cross at the reference rate.

    **The convention.** The conversion happens at the rate actually transacted at --
    ``r + p`` on the buy side, ``r - p`` on the sell side -- so the arriving amount is the
    one the venue would really hand over. 10 000 UAH at a P2P price of 45 buys 222.22 USD,
    which is what the screen says. The spread is then *derived* as what that conversion cost
    in the sending currency, so no figure in the result is computed twice by two routes.

    The reference is never transacted at, which is what FR-010's prohibition on a mid-rate
    is about, and the side taken is recorded in :attr:`LegOutcome.channel_applied` (FR-011).

    **This is a correction.** The first implementation charged ``p / r`` of the amount and
    converted the remainder at the reference, because FR-004 named ``p / r`` as the cost. It
    reproduced §4.3.1's percentage exactly and reported an arriving amount **1.13 USD short**
    of reality on a 10 000 UAH purchase. FR-004 was corrected instead: ``p / r`` is the
    spread over the reference *rate* and is reported as such by
    :func:`channels.spread_over_reference`, while the cost of the conversion is
    :func:`channels.loss_fraction`. On the sell side the two coincide, so only the buy side
    moved.

    Refuses a missing channel outright. A conversion with no declared channel is a mid-rate
    transaction, and there is no "just this once" for it.
    """
    if channel is None:
        raise ValueError(
            f"leg {leg.index} of kind {FX!r} requires a channel: a conversion with no "
            "declared two-sided quote would be a mid-rate transaction, which FR-010 "
            "forbids outright"
        )
    side, role = channels.side_for(channel, leg.from_ccy, leg.to_ccy)
    percentage, fixed = _fee_components(leg, amount)
    after_fees = money.sub(money.sub(amount, percentage), fixed)

    # Convert at the rate actually transacted at, so the arriving amount is the one the
    # venue would really hand over. The reference quotes price currency per unit currency,
    # so buying the unit currency divides and selling multiplies; the inversion lives here,
    # once, beside the channel that supplied the number.
    effective = channels.effective_rate(side, channel.reference_rate, role=role)
    rate = 1.0 / effective if role is Side.BUY else effective
    outgoing = money.convert(
        after_fees, to_currency=leg.to_ccy, rate=rate, sources=channel.provenance
    )

    # The spread is then what that conversion *cost*, valued in the sending currency: the
    # difference between the value handed over and what the arriving amount is worth at the
    # reference. Derived from the same effective rate the conversion used, so the components
    # sum to the whole cost exactly rather than approximately (FR-003).
    spread = money.scale_sourced(
        after_fees,
        channels.loss_fraction(side, channel.reference_rate, role=role),
        channel.provenance,
    )
    return LegOutcome(
        outgoing=outgoing,
        conversion_spread=spread,
        percentage_fee=percentage,
        fixed_fee=fixed,
        spread_over_reference=channels.spread_over_reference(
            side, channel.reference_rate, role=role
        ),
        channel_applied=channel.id,
    )


LEG_COST_FNS: Final[Mapping[str, LegCostFn]] = {
    TRANSFER: _fee_only_cost,
    FX: _fx_cost,
    TRADE: _fee_only_cost,
    WITHDRAWAL: _fee_only_cost,
}
"""The leg kinds this engine implements. The key set is the whole contract.

Readable in one line and impossible to extend at a distance: no registration decorator, no
import-time side effect, no subclass scan. Adding a kind is a line here and a function above;
adding a *leg* that uses one is a line in a data file and no engine edit at all, which is the
Principle II boundary this design keeps.
"""


def channel_for(channels: Mapping[str, FxChannel], leg: Leg) -> FxChannel | None:
    """The channel a leg names, ``None`` if it names none, or a raise if it names an unknown.

    Separated from the cost functions because it is a *lookup* rather than arithmetic, and
    because a leg naming an undeclared channel is the same class of failure as a leg naming
    an undeclared kind: the resolver validates channel references at load and can name the
    file and the leg index, so reaching here unresolved means that validation was bypassed.

    There is deliberately no fallback channel. Substituting "the official rate" for a
    misspelt channel id would silently reprice a P2P leg at the reference and delete the
    entire spread this feature exists to measure.
    """
    if leg.channel is None:
        return None
    if leg.channel not in channels:
        raise KeyError(
            f"leg {leg.index} names unknown channel {leg.channel!r}. There is no default "
            f"channel: substituting one would reprice the leg at a rate nobody declared. "
            f"Known channels: {sorted(channels)}"
        )
    return channels[leg.channel]


def cost_fn_for(kind: str) -> LegCostFn:
    """The cost function a declared leg kind selects, or a raise naming what is known.

    An explicit membership test rather than ``LEG_COST_FNS.get(kind, default)``, so that no
    reading of this code suggests a default exists. The data layer validates the kind when
    it loads a declaration and reports file and field; a kind reaching here unrecognised
    means that validation was bypassed, which is a programmer error rather than a fact
    about the money -- hence a raise. The message lists the known kinds because an
    unrecognised kind is almost always a typo, and naming the alternatives fixes it in one
    step.
    """
    if kind not in LEG_COST_FNS:
        raise KeyError(
            f"unknown leg kind {kind!r}. There is no default kind: a leg must declare one "
            f"this engine implements. Known kinds: {sorted(LEG_COST_FNS)}"
        )
    return LEG_COST_FNS[kind]
