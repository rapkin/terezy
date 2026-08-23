"""Tax lots and positions: what is held, what it cost, and what a disposal realised.

The predecessor project had no lots at all (``REWRITE_BRIEF.md`` §4.3, L1) and therefore
could not express a single real tax rule, because every rule that matters is a statement
about *which* units were sold and *what those units cost*. This module is the answer to
that, and the three invariants it exists to keep are asserted over generated streams in
``tests/invariants/test_ledger_conservation.py``:

* **C2** -- the sum of lot quantities is the position quantity, and no quantity is ever
  negative;
* **C3** -- the sum of lot costs is the position basis, and on a disposal
  ``realised gain = proceeds - consumed basis - allocated fees``;
* both of the above **in the trade currency and in the base currency** (FR-011).

**Why a position stores its own quantity and basis when it also stores its lots.** They
are accumulated separately as events arrive, so C2 and C3 compare two independently
maintained figures rather than a number against itself. A position that derived its
quantity by summing its lots would satisfy C2 by construction and prove nothing.

**Why both currencies are stored when this feature has only one.** ``cost_trade_ccy`` and
``cost_base_ccy`` are equal in feature 001 -- everything is UAH -- and the field's whole
purpose is the case where they differ (data-model.md). Storing them separately from the
first commit means the invariant that matters is already asserted when FX arrives.
Feature 001 has no conversion at all, and it cannot fake one: there is deliberately no
currency conversion function anywhere in the core (asserted by C5), so a trade currency
that is not the base currency is refused loudly here rather than converted at an invented
rate. ``fx_rate_used`` is ``None`` precisely because no rate was used.

**Why consumption is a registry of ordering functions.** *"Registries are mappings of
functions, not subclass dispatch"* (owner decision D-E). A selection method is an
ordering over the lots held: FIFO consumes the oldest first, LIFO the newest. Both
produce a *different hand-computable tax* on the same position, which is why the method is
configured rather than assumed, and why there is no default -- E6 in
``docs/REQUIRED_TESTS.md`` exists because picking one silently is a whole class of wrong
answers.

**No behaviour on the records.** Everything here is a free function over frozen
dataclasses, and no function in this module constructs ``Money``: every amount is derived
through ``core.primitives.money``, which is what carries provenance from the events into
the basis and out into the realised gain (FR-015).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Final

from terezy.core.errors import CurrencyMismatchError, LedgerInvariantError
from terezy.core.ledger import events as ev
from terezy.core.ledger.events import CausationRef, Event
from terezy.core.primitives import money
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE


@dataclass(frozen=True, slots=True)
class Lot:
    """One acquisition: units bought on a date at a cost, held until consumed."""

    lot_id: str
    """Identity, unique within the instrument. Comes from the opening event."""

    instrument_id: str
    """The instrument these units are of."""

    acquired_on: date
    """The acquisition date -- what a holding-period rule would be measured from."""

    quantity: float
    """Units remaining in this lot. **Strictly positive**: a lot may not exist at zero.

    A fully consumed lot is removed rather than kept as an empty shell, because an empty
    shell would keep an acquisition date alive that holds nothing and would take its turn
    in the consumption order.
    """

    cost_trade_ccy: Money
    """Cost of the units remaining, in the instrument's own currency."""

    cost_base_ccy: Money
    """Cost of the units remaining, in the base currency.

    Equal to ``cost_trade_ccy`` whenever the two currencies coincide, which is every case
    in feature 001. See the module docstring.
    """

    fx_rate_used: float | None
    """The rate that converted trade cost into base cost, or ``None`` if none was.

    ``None`` is a statement, not a gap: it says the two currencies were the same and no
    conversion took place. A figure derived from an invented rate would be exactly the
    confident wrongness Principle I forbids, so no rate is invented and the field records
    that.
    """


@dataclass(frozen=True, slots=True)
class Position:
    """Everything held of one instrument: the lots, and the totals kept beside them."""

    instrument_id: str
    """The instrument held."""

    quantity: float
    """Total units held, accumulated as events arrive. C2 compares it to the lot sum."""

    basis_trade_ccy: Money
    """Total cost basis in the trade currency. C3 compares it to the lot cost sum."""

    basis_base_ccy: Money
    """Total cost basis in the base currency."""

    lots: tuple[Lot, ...]
    """The lots held, in acquisition order.

    Acquisition order, not consumption order: the order is a fact about the history and
    each selection method draws on them in its own way (see :data:`SELECTION_FNS`).
    Keeping the tuple in one canonical order also means two positions holding the same
    lots compare equal, which C4's digest relies on.
    """


@dataclass(frozen=True, slots=True)
class Consumption:
    """The outcome of taking units out of a position: what is left, and what it cost."""

    position: Position
    """The position after the units were removed."""

    consumed_quantity: float
    """Units removed. Equal to the quantity requested."""

    consumed_basis_trade_ccy: Money
    """Cost basis removed, in the trade currency. Carries the provenance of the lots."""

    consumed_basis_base_ccy: Money
    """Cost basis removed, in the base currency."""

    consumed_from: tuple[tuple[str, float], ...]
    """``(lot_id, units)`` per lot touched, in the order the method consumed them.

    Kept so that a disposal can be traced to the specific acquisitions it drew on, which
    is what FR-008 asks of a figure and what a holding-period rule will need later.
    """


@dataclass(frozen=True, slots=True)
class Disposal:
    """A realised disposal, with every term of FR-011's identity stored separately.

    The gain is stored *and* so is each input to it. That is deliberate: C3 asserts the
    identity ``gain == proceeds - basis - fees``, and an identity is only assertable if
    both sides exist. Storing only the gain would make the test either impossible or a
    restatement of the code that produced it.
    """

    sequence: int
    """The sequence number of the event that disposed of the units."""

    occurred_on: date
    """The disposal date -- the date a tax charge on this gain would be assessed to."""

    instrument_id: str
    """The instrument disposed of."""

    quantity: float
    """Units disposed of."""

    proceeds_trade_ccy: Money
    """What was received, in the trade currency."""

    proceeds_base_ccy: Money
    """What was received, in the base currency."""

    consumed_basis_trade_ccy: Money
    """The cost basis the disposal consumed, in the trade currency."""

    consumed_basis_base_ccy: Money
    """The cost basis the disposal consumed, in the base currency."""

    allocated_fees_trade_ccy: Money
    """Fees charged against this disposal, in the trade currency. Zero is a real value."""

    allocated_fees_base_ccy: Money
    """Fees charged against this disposal, in the base currency."""

    realised_gain_trade_ccy: Money
    """``proceeds - basis - fees`` in the trade currency. May be negative: a loss."""

    realised_gain_base_ccy: Money
    """``proceeds - basis - fees`` in the base currency.

    Separate from the trade-currency figure because they are genuinely different numbers
    the moment the two currencies differ -- a position flat in USD across a devaluation
    realises a gain in UAH, which is F1 in ``docs/REQUIRED_TESTS.md`` and the reason the
    rewrite exists.
    """

    consumed_from: tuple[tuple[str, float], ...]
    """``(lot_id, units)`` per lot consumed, so the gain traces to its acquisitions."""

    caused_by: CausationRef
    """The term or rule that caused the disposal, copied from its event (FR-008)."""


class LotMethod(Enum):
    """The four basis methods, as a closed set. **No default anywhere** (FR-020).

    ⚙ **Feature 009 added the two that 001 left out**, and put them here rather than in a tax
    module because two of them already lived here: four methods split across two modules is
    how a fifth ends up in a third (research.md D10).

    The value strings are the data contract -- what a scenario declares and what
    :data:`SELECTION_FNS` is keyed by. The enum exists beside them so that a **figure** cannot
    carry an unchecked method name: :func:`method_named` is the one place a name becomes a
    member.

    What the law says about each method is **not** here: that is declared data with a
    citation.
    """

    FIFO = "fifo"
    LIFO = "lifo"
    AVERAGE_COST = "average_cost"
    SPECIFIC_LOT = "specific_lot"


FIFO: Final = LotMethod.FIFO.value
LIFO: Final = LotMethod.LIFO.value
AVERAGE_COST: Final = LotMethod.AVERAGE_COST.value
SPECIFIC_LOT: Final = LotMethod.SPECIFIC_LOT.value


@dataclass(frozen=True, slots=True)
class LotNotNamed:
    """A specific-lot disposal that names no lot (FR-021)."""

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class LotNamedUnderWrongMethod:
    """A disposal names a lot under a method that does not select by name (FR-022).

    Refused rather than ignored: ignoring the naming would consume a different basis from the
    one the caller asked for, and produce a plausible tax on it.
    """

    instrument_id: str
    lot_id: str
    method: LotMethod
    reason: str


@dataclass(frozen=True, slots=True)
class NamedLotUnavailable:
    """The named lot does not exist, is already consumed, or holds too few units (FR-021).

    One record for the three, because they are one fact -- the named lot cannot supply what
    was asked -- and :attr:`available` tells them apart: absent and exhausted both hold
    nothing (an exhausted lot is dropped from the position), and too-few holds something.
    """

    instrument_id: str
    lot_id: str
    requested: float
    available: float
    reason: str


LotRefusal = LotNotNamed | LotNamedUnderWrongMethod | NamedLotUnavailable
"""Why a disposal's basis could not be selected. Match exhaustively."""

Selection = tuple[tuple[Lot, float], ...]
"""Which lots a disposal draws on and how many units from each, in consumption order."""

SelectionFn = Callable[[tuple[Lot, ...], float, str | None], Selection | LotRefusal]
"""A basis method: ``(lots, quantity, the lot named by the disposal) -> what to consume``.

⚙ **Feature 009 widened this from an ordering.** FIFO and LIFO are orderings, and average
cost is not -- it takes a share of *every* lot -- and specific-lot is not either, since it
depends on what the disposal named. Keeping the narrower shape would have forced two of the
four methods to be expressed as something they are not.
"""


def _greedy(ordered: tuple[Lot, ...], quantity: float) -> Selection:
    """Take whole lots in the given order until the quantity is met, splitting the last.

    Shared by FIFO and LIFO, which differ only in the order they are handed.
    """
    remaining = quantity
    taken: list[tuple[Lot, float]] = []
    for lot in ordered:
        if remaining <= TOLERANCE:
            break
        units = min(lot.quantity, remaining)
        taken.append((lot, units))
        remaining -= units
    return tuple(taken)


def _oldest_first(
    lots: tuple[Lot, ...], quantity: float, named: str | None
) -> Selection | LotRefusal:
    """FIFO: the earliest acquisition is consumed first.

    Sorted on ``(acquired_on, lot_id)`` rather than relying on the tuple already being in
    acquisition order. The tie-break on ``lot_id`` matters: two lots acquired on the same date
    would otherwise be ordered by sort stability, and the basis consumed -- and so the tax --
    would depend on the order the collection happened to be built in.
    """
    refused = _refuse_naming(lots, named, LotMethod.FIFO)
    if refused is not None:
        return refused
    return _greedy(tuple(sorted(lots, key=lambda lot: (lot.acquired_on, lot.lot_id))), quantity)


def _newest_first(
    lots: tuple[Lot, ...], quantity: float, named: str | None
) -> Selection | LotRefusal:
    """LIFO: the most recent acquisition is consumed first, with the same tie-break."""
    refused = _refuse_naming(lots, named, LotMethod.LIFO)
    if refused is not None:
        return refused
    return _greedy(
        tuple(sorted(lots, key=lambda lot: (lot.acquired_on, lot.lot_id), reverse=True)),
        quantity,
    )


def _pro_rata(lots: tuple[Lot, ...], quantity: float, named: str | None) -> Selection | LotRefusal:
    """Average cost: every lot gives up the same fraction of its units, and of its cost.

    The fraction is ``quantity / units held``, applied to each lot, which is what makes the
    basis consumed the average unit cost times the units sold **and** leaves the remaining
    position at the same average unit cost. Consuming the same total basis out of one or two
    lots instead would give the same tax today and a different position tomorrow.

    The lots are ordered as they are held rather than sorted, because the fraction is the same
    for all of them: no order can change the answer, so imposing one would suggest it could.
    """
    refused = _refuse_naming(lots, named, LotMethod.AVERAGE_COST)
    if refused is not None:
        return refused
    fraction = quantity / sum(lot.quantity for lot in lots)
    return tuple((lot, lot.quantity * fraction) for lot in lots)


def _named_lot(lots: tuple[Lot, ...], quantity: float, named: str | None) -> Selection | LotRefusal:
    """Specific lot: exactly the lot the disposal named, and no other.

    Where it cannot be honoured it refuses rather than falling back, because falling back
    would consume a different basis from the one the owner chose -- which is the whole reason
    the method exists.

    **One lot per disposal.** Disposing of two named lots is two disposal events, each with
    its own lot and quantity: a partially honoured multi-lot request is what the spec's edge
    case forbids, and the event vocabulary carries one ``lot_id``.
    """
    if named is None:
        return LotNotNamed(
            instrument_id=_position_of(lots),
            reason=(
                "the specific-lot method requires the disposal to name the lot it consumes, "
                "and this one names none. There is no fallback ordering: the method exists "
                "precisely so the owner chooses the basis, and choosing one for him would "
                "tax a different acquisition from the one he sold."
            ),
        )
    found = [lot for lot in lots if lot.lot_id == named]
    if not found or found[0].quantity + TOLERANCE < quantity:
        available = found[0].quantity if found else 0.0
        return NamedLotUnavailable(
            instrument_id=_position_of(lots),
            lot_id=named,
            requested=quantity,
            available=available,
            reason=(
                f"the disposal names lot {named!r} for {quantity!r} units and that lot holds "
                f"{available!r}. A lot that does not exist, one already consumed, and one "
                "holding too few units are all refused here rather than made up from "
                "another lot: the basis consumed would be one the owner did not choose."
            ),
        )
    return ((found[0], quantity),)


def _position_of(lots: tuple[Lot, ...]) -> str:
    """Which position a refusal is about."""
    return lots[0].instrument_id


def _refuse_naming(
    lots: tuple[Lot, ...], named: str | None, method: LotMethod
) -> LotNamedUnderWrongMethod | None:
    """A lot named under a method that does not select by name is a conflict (FR-022).

    ``None`` where nothing was named, which is the ordinary case. Silently ignoring the name
    would consume by the configured method instead -- a different basis, a different tax, and
    an instruction the caller believed had been followed.
    """
    if named is None:
        return None
    return LotNamedUnderWrongMethod(
        instrument_id=_position_of(lots),
        lot_id=named,
        method=method,
        reason=(
            f"the disposal names lot {named!r}, and this run consumes by {method.value!r}, "
            "which selects lots by rule rather than by name. Reported rather than ignored: "
            "ignoring the naming would consume a different basis from the one asked for and "
            f"tax it plausibly. Either declare the {SPECIFIC_LOT!r} method, or drop the name."
        ),
    )


SELECTION_FNS: Final[Mapping[str, SelectionFn]] = {
    FIFO: _oldest_first,
    LIFO: _newest_first,
    AVERAGE_COST: _pro_rata,
    SPECIFIC_LOT: _named_lot,
}
"""Every basis method this engine implements, keyed by its declared name."""


def method_named(name: str) -> LotMethod:
    """The declared name as a checked method, or a raise naming the four that exist.

    A raise rather than a typed refusal for the reason :func:`selection_for` gives: by the
    time a fold is running, the name has passed the data boundary, so an unknown one here is a
    bug in the code that assembled the run rather than a fact about the money.
    """
    for method in LotMethod:
        if method.value == name:
            return method
    raise LedgerInvariantError(
        f"unknown lot consumption method {name!r}. There is no default method: the choice "
        f"changes the basis consumed and therefore the tax. Known methods: "
        f"{sorted(SELECTION_FNS)}"
    )


def selection_for(name: str) -> SelectionFn:
    """The basis method a configured name selects, or a raise naming what is known.

    An explicit membership test rather than ``dict.get`` with a default, for the same reason
    ``primitives.conventions`` does it that way: no reading of this code should suggest that a
    default method exists. Silently applying FIFO to a scenario that configured LIFO produces
    a different tax on the same trades, and it produces it plausibly.
    """
    if name not in SELECTION_FNS:
        raise LedgerInvariantError(
            f"unknown lot consumption method {name!r}. There is no default method: the "
            f"choice changes the basis consumed and therefore the tax. Known methods: "
            f"{sorted(SELECTION_FNS)}"
        )
    return SELECTION_FNS[name]


def basis_consumed(
    lots: tuple[Lot, ...],
    quantity: float,
    *,
    method: str,
    named_lot: str | None = None,
) -> Selection | LotRefusal:
    """Which lots a disposal draws on under one method, or why it cannot be answered.

    The pure half of :func:`consume`: no position, no arithmetic on money, and every refusal
    about the *choice of lots* a value rather than a raise, so the four methods' selection
    behaviour can be checked directly.

    **A disposal larger than the lots hold raises**, here as well as in :func:`consume`, and
    the two checks are deliberately not one: this one compares against the lots themselves and
    ``consume``'s compares against the position's independently accumulated quantity, which is
    what makes C2 a comparison of two figures rather than of a number with itself. Without
    this one, a caller reaching the selection directly would get a short selection under FIFO
    and an over-100% fraction under average cost -- a wrong answer rather than a refusal.

    **A holding of nothing is refused on its own clause**, not left to the comparison above.
    At a request of exactly ``TOLERANCE`` against lots holding nothing the comparison is
    ``1e-9 > 0.0 + 1e-9``, which is false, and each method then failed differently and none of
    them well: a short selection under FIFO, a division by zero under average cost. There is
    no basis in an empty position to select from at any tolerance.
    """
    held = sum(lot.quantity for lot in lots)
    if quantity <= 0.0 or held <= 0.0 or quantity > held + TOLERANCE:
        raise LedgerInvariantError(
            f"cannot select {quantity!r} units from lots holding {held!r}. A disposal of "
            "nothing is not a disposal, a position holding nothing has no basis to consume, "
            "and a disposal larger than the holding would consume a basis that was never paid."
        )
    return selection_for(method)(lots, quantity, named_lot)


def opening(instrument_id: str, trade_currency: Currency, base_currency: Currency) -> Position:
    """An empty position: nothing held, nothing paid, no lots.

    Both currencies are stated rather than inferred from the first purchase, so that an
    empty position still knows what denomination its zero is in. ``money.zero`` is the one
    legitimate use of empty provenance -- the starting point of a sum is not an
    observation and rests on no source.
    """
    return Position(
        instrument_id=instrument_id,
        quantity=0.0,
        basis_trade_ccy=money.zero(trade_currency),
        basis_base_ccy=money.zero(base_currency),
        lots=(),
    )


def base_amount_of(amount: Money, base_currency: Currency) -> Money:
    """The same amount expressed in the base currency, when no conversion is needed.

    This is the whole of feature 001's FX handling, and it is a refusal rather than a
    conversion. If the amount is already in the base currency it is returned unchanged --
    provenance and all -- and the caller records ``fx_rate_used = None``. If it is not,
    the run stops: there is no rate here, no rate anywhere in the core, and inventing one
    would put a fabricated number underneath a tax figure.

    ``CurrencyMismatchError`` rather than a typed failure, because reaching this function
    with a foreign amount means an FX-bearing scenario was fed to an engine that does not
    model FX -- a programmer error, not an outcome the owner can act on.
    """
    if amount.currency is base_currency:
        return amount
    raise CurrencyMismatchError(
        f"an amount in {amount.currency.value} cannot be expressed in the base currency "
        f"{base_currency.value}: no exchange rate exists in this feature and none may be "
        "invented (FR-007). An instrument trading in a currency other than the base "
        "currency needs the dated-FX feature, not a rate guessed here."
    )


def add_lot(position: Position, lot: Lot) -> Position:
    """Add an acquisition to a position, updating the totals kept beside the lots.

    The quantity and basis are advanced by this lot's own figures rather than recomputed
    from the whole tuple, which is what keeps them an independent accumulation for C2 and
    C3 to check.
    """
    if any(existing.lot_id == lot.lot_id for existing in position.lots):
        raise LedgerInvariantError(
            f"lot {lot.lot_id!r} already exists in position {position.instrument_id!r}. "
            "Two acquisitions sharing an identity cannot be told apart, so neither can be "
            "selected for consumption or traced to its cost."
        )
    return Position(
        instrument_id=position.instrument_id,
        quantity=position.quantity + lot.quantity,
        basis_trade_ccy=money.add(position.basis_trade_ccy, lot.cost_trade_ccy),
        basis_base_ccy=money.add(position.basis_base_ccy, lot.cost_base_ccy),
        lots=(*position.lots, lot),
    )


def consume(
    position: Position, quantity: float, method: str, *, named_lot: str | None = None
) -> Consumption:
    """Remove units from a position by the configured method, and report what they cost.

    Partial consumption of a lot splits its cost pro rata -- ``scale`` by the fraction of
    units taken -- and the remainder of the lot keeps ``cost - consumed`` rather than
    being rescaled. Subtracting means the two halves add back to the original exactly, so
    basis conservation (C3) does not depend on two independent multiplications agreeing.

    Over-consumption raises. Selling more than is held is not an owner-facing outcome the
    way an unaffordable purchase is: the event stream is generated by this engine from a
    validated declaration, so a disposal exceeding the holding is a bug in the generator,
    and a ledger that let it through would report a negative position (C2) and a basis
    consumed that was never paid.

    ⚙ **A refusal from the selection is raised here** rather than returned (009). The typed
    refusals are values at :func:`basis_consumed`, where the four methods can be checked
    directly; by the time a stream is being folded, a disposal that contradicts the run's
    method is a stream this engine cannot fold at all -- the same class of thing as a
    quantity of zero, and it stops the run for the same reason.
    """
    if quantity <= 0.0:
        raise LedgerInvariantError(
            f"cannot consume {quantity!r} units of {position.instrument_id!r}. A disposal "
            "of nothing is not a disposal."
        )
    if quantity > position.quantity + TOLERANCE:
        raise LedgerInvariantError(
            f"cannot consume {quantity!r} units of {position.instrument_id!r}: only "
            f"{position.quantity!r} are held. A ledger that allowed this would report a "
            "negative holding and a basis that was never paid."
        )

    selected = basis_consumed(position.lots, quantity, method=method, named_lot=named_lot)
    if not isinstance(selected, tuple):
        raise LedgerInvariantError(selected.reason)

    remaining_to_take = quantity
    consumed_trade: list[Money] = []
    consumed_base: list[Money] = []
    consumed_from: list[tuple[str, float]] = []
    survivors: dict[str, Lot] = {
        lot.lot_id: lot
        for lot in position.lots
        if lot.lot_id not in {taken.lot_id for taken, _ in selected}
    }

    for lot, units in selected:
        taken = min(units, lot.quantity)
        exhausted = lot.quantity - taken <= TOLERANCE
        if exhausted:
            # A residual within the tolerance is not a lot: it would be dropped below,
            # and its pro-rata share of the cost would then be left in the position's
            # basis with no lot to account for it -- a basis-conservation gap (C3) of
            # ``cost * residual / quantity``, which on a large lot is not small. So a
            # lot this close to empty is consumed whole, exactly, and the tolerance is
            # spent on the quantity rather than on the money.
            taken = lot.quantity
            part_trade = lot.cost_trade_ccy
            part_base = lot.cost_base_ccy
        else:
            fraction = taken / lot.quantity
            part_trade = money.scale(lot.cost_trade_ccy, fraction)
            part_base = money.scale(lot.cost_base_ccy, fraction)
        consumed_trade.append(part_trade)
        consumed_base.append(part_base)
        consumed_from.append((lot.lot_id, taken))
        remaining_to_take -= taken
        if not exhausted:
            survivors[lot.lot_id] = replace(
                lot,
                quantity=lot.quantity - taken,
                cost_trade_ccy=money.sub(lot.cost_trade_ccy, part_trade),
                cost_base_ccy=money.sub(lot.cost_base_ccy, part_base),
            )

    if remaining_to_take > TOLERANCE:  # pragma: no cover -- guarded above
        raise LedgerInvariantError(
            f"consumed only {quantity - remaining_to_take!r} of {quantity!r} units of "
            f"{position.instrument_id!r}; the lots and the position quantity disagree."
        )

    basis_trade = money.total(consumed_trade, position.basis_trade_ccy.currency)
    basis_base = money.total(consumed_base, position.basis_base_ccy.currency)

    return Consumption(
        position=Position(
            instrument_id=position.instrument_id,
            quantity=position.quantity - quantity,
            basis_trade_ccy=money.sub(position.basis_trade_ccy, basis_trade),
            basis_base_ccy=money.sub(position.basis_base_ccy, basis_base),
            lots=tuple(survivors[lot.lot_id] for lot in position.lots if lot.lot_id in survivors),
        ),
        consumed_quantity=quantity,
        consumed_basis_trade_ccy=basis_trade,
        consumed_basis_base_ccy=basis_base,
        consumed_from=tuple(consumed_from),
    )


def realise(
    event: Event,
    consumption: Consumption,
    fees: Iterable[Event],
    base_currency: Currency,
) -> Disposal:
    """Build the disposal record for one closing event: FR-011's identity, term by term.

    The fee total is taken from the fee events allocated to this disposal, negated into a
    positive cost, and subtracted. A zero fee total is a real value and is recorded as
    one: ``REWRITE_BRIEF`` B13 forbids blending a cost into a market loss, and recording
    "no fee" as an absent field rather than a zero is how a cost becomes invisible.

    Provenance reaches the gain by construction. Proceeds carry the event's sources, the
    consumed basis carries the sources of every lot it drew on, and the fees carry theirs;
    ``money.sub`` unions all three (FR-015).
    """
    proceeds_trade = event.amount
    fee_total_trade = money.total(
        [money.scale(fee.amount, -1.0) for fee in fees],
        proceeds_trade.currency,
    )
    gain_trade = money.sub(
        money.sub(proceeds_trade, consumption.consumed_basis_trade_ccy),
        fee_total_trade,
    )

    proceeds_base = base_amount_of(proceeds_trade, base_currency)
    fee_total_base = base_amount_of(fee_total_trade, base_currency)
    gain_base = money.sub(
        money.sub(proceeds_base, consumption.consumed_basis_base_ccy),
        fee_total_base,
    )

    return Disposal(
        sequence=event.sequence,
        occurred_on=event.occurred_on,
        instrument_id=ev.lot_ref_of(event).instrument_id,
        quantity=consumption.consumed_quantity,
        proceeds_trade_ccy=proceeds_trade,
        proceeds_base_ccy=proceeds_base,
        consumed_basis_trade_ccy=consumption.consumed_basis_trade_ccy,
        consumed_basis_base_ccy=consumption.consumed_basis_base_ccy,
        allocated_fees_trade_ccy=fee_total_trade,
        allocated_fees_base_ccy=fee_total_base,
        realised_gain_trade_ccy=gain_trade,
        realised_gain_base_ccy=gain_base,
        consumed_from=consumption.consumed_from,
        caused_by=event.caused_by,
    )


def advance(
    positions: Mapping[str, Position],
    event: Event,
    *,
    base_currency: Currency,
    consumption_method: str,
    fees: Iterable[Event],
) -> tuple[Mapping[str, Position], Disposal | None]:
    """Apply one event to the holdings, returning the new holdings and any disposal.

    A plain tuple rather than a record: two values, both named by the signature, and a
    wrapper would only have to be unpacked again. ``None`` for the disposal means this
    event closed nothing -- it is not a degraded outcome, so it is not a typed failure.

    Events that touch no holding pass straight through. That is not a silent default: the
    shape rules in ``events.check_shape`` have already established that such an event
    carries neither a quantity nor a lot reference, so there is nothing here to drop.
    """
    if ev.opens_lot(event):
        return _open(positions, event, base_currency=base_currency), None
    if ev.closes_lot(event):
        return _close(
            positions,
            event,
            base_currency=base_currency,
            consumption_method=consumption_method,
            fees=fees,
        )
    return positions, None


def _open(
    positions: Mapping[str, Position],
    event: Event,
    *,
    base_currency: Currency,
) -> Mapping[str, Position]:
    ref = ev.lot_ref_of(event)
    lot_id = ref.lot_id
    if lot_id is None:  # pragma: no cover -- guaranteed by events.check_shape
        raise LedgerInvariantError(f"event {event.sequence} opens a lot without naming it")

    cost_trade = money.scale(event.amount, -1.0)
    cost_base = base_amount_of(cost_trade, base_currency)
    position = positions.get(ref.instrument_id) or opening(
        ref.instrument_id, cost_trade.currency, base_currency
    )
    lot = Lot(
        lot_id=lot_id,
        instrument_id=ref.instrument_id,
        acquired_on=event.occurred_on,
        quantity=ev.quantity_of(event),
        cost_trade_ccy=cost_trade,
        cost_base_ccy=cost_base,
        fx_rate_used=None,
    )
    return {**positions, ref.instrument_id: add_lot(position, lot)}


def _close(
    positions: Mapping[str, Position],
    event: Event,
    *,
    base_currency: Currency,
    consumption_method: str,
    fees: Iterable[Event],
) -> tuple[Mapping[str, Position], Disposal]:
    ref = ev.lot_ref_of(event)
    position = positions.get(ref.instrument_id)
    if position is None:
        raise LedgerInvariantError(
            f"event {event.sequence} disposes of {ref.instrument_id!r}, which is not "
            "held. Proceeds without a basis would be reported as pure gain."
        )
    consumption = consume(
        position,
        ev.quantity_of(event),
        consumption_method,
        named_lot=ref.lot_id,
    )
    disposal = realise(event, consumption, fees, base_currency)
    return {**positions, ref.instrument_id: consumption.position}, disposal


def rebuild(
    items: Iterable[Event],
    *,
    base_currency: Currency,
    consumption_method: str,
) -> Mapping[str, Position]:
    """The holdings implied by an event stream: what is held, of what, at what cost.

    The narrower half of the ledger, answering "what is held?" without folding cash. It
    shares :func:`advance` with the engine on purpose -- two implementations of "what is
    held" would be two answers to the same question, and a figure whose value depends on
    which entry point computed it is not traceable to the events at all.

    Fees are indexed up front by ``events.allocated_fees``, so the result does not depend
    on whether a fee precedes or follows the disposal it is charged against.
    """
    records = tuple(items)
    fee_index = ev.allocated_fees(records)
    positions: Mapping[str, Position] = {}
    for event in ev.in_sequence(records):
        positions, _ = advance(
            positions,
            event,
            base_currency=base_currency,
            consumption_method=consumption_method,
            fees=fee_index.get(event.sequence, ()),
        )
    return positions
