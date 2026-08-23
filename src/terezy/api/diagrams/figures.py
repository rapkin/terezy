"""The declared figures an edge carries: the leg's fees, and the quote its channel applies.

Shared by both renderers, because both draw the same edge. FR-006 puts the declared per-leg
figures on the registry graph; FR-007 and FR-008 put them on the costed path, where the
result carries no per-leg attribution of its own. One module so the two cannot disagree about
what a declared figure on an edge *is* -- and so the field prefixes below are one definition
rather than two literals that drift.

## Why a premium has to say which way it is applied

The two declared forms of a channel side have **different sign conventions**, and
``core.routes.channels`` says so in as many words:

* ``premium_per_unit`` is a **signed offset**. Both sides are ``reference + premium``, so
  ``+3`` pays 45 against a reference of 42 and ``-2.5`` receives 39.5. The sign carries the
  direction.
* ``markup_bps`` is a **cost magnitude**. It costs 1.5% whichever way the money goes, so the
  engine *adds* it on the buy side and *subtracts* it on the sell side. The number carries no
  direction at all.

So ``150.00 bps over reference 42.00 UAH per USD`` is the same eleven words for an edge that
charges +1.5% and an edge that charges -1.5%: two different corridors drawn identically, and
the sell-side one drawn in the opposite direction from what the engine charges. That is the
mislabelled figure in picture form, in the one form where the declaration itself cannot
prevent it.

**The carrier is a direction phrase, taken from the core's own rule.** :func:`quote_for` asks
``channels.effective_rate`` where the rate actually lands for *this leg's role* and renders
``applied above the reference``, ``applied below the reference`` or ``applied at the
reference``. The side name is on the label too, but the direction phrase is the load-bearing
half: a reader must be able to tell a +1.5% edge from a -1.5% edge without knowing which side
a leg takes, and without holding two sign conventions in their head.

**The effective rate itself is not rendered.** It is computed rather than declared, and
FR-008 permits the renderer no figure its input does not carry. A *word* naming a direction is
not a figure; a rate is.

## Staleness is carried, not decided

A :class:`Quote` keeps the reference's sources and the applied side's **apart**, each with the
``kind`` its own table declared. A channel file declares a kind three times because the
reference rate and the two sides go out of date at three speeds, and aging a 7-day P2P premium
under a 365-day schedule threshold reports it fresh at 82 days -- the silent permissive default
FR-028 exists to close, and the defect ``cost._channel_verdicts`` was written to fix.

Which side of the split a caller uses depends on what it has. The registry graph ages them
itself, through :func:`verdicts`, because it holds the kind registry and the as-of date. The
costed path does not age anything: the result it draws already carries a verdict computed the
same way, so it matches source ids against that verdict instead. Two computations of one fact
eventually disagree.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from terezy.api.diagrams import numbers
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import ObservationKind, StalenessVerdict
from terezy.core.primitives.tolerance import is_close
from terezy.core.routes import channels as fx
from terezy.core.routes.channels import ChannelSide, FxChannel, Side
from terezy.core.routes.legs import Leg, channel_for

FIGURE_FIELD: Final = "declared "
"""The prefix every declared-figure field begins with.

One shared prefix, because SC-012's assertion is that the two registry-graph modes differ *by
figures only*: the test strips every field beginning with this prefix from the with-figures
text and requires what is left to be the topology text, byte for byte. A figure field added
without the prefix would make that assertion silently weaker, which is why the two below are
built from it rather than spelled out -- and why both renderers import these three rather than
repeating the literals.
"""

FEE_FIELD: Final = f"{FIGURE_FIELD}fee "
"""The leg's own declared fees: a fraction of the amount, plus a flat fee."""

PREMIUM_FIELD: Final = f"{FIGURE_FIELD}premium "
"""The declared quote an ``fx`` leg's channel applies, on the side this leg takes.

**This is the figure that matters most on either diagram.** Every fee on the §4.3.1 corridor is
declared zero; the entire 6.67% one-way cost is the channel's ``+3.00 UAH per USD`` against a
42.00 reference. A diagram showing only the fees draws the most expensive corridor in the
registry as free -- the mislabelled figure in picture form, which is the one thing this feature
exists to refuse. A caption disclaiming it does not repair that: a disclaimer at the top does
not survive someone looking at one edge.

It is a **declared** observation with its own source, its own kind and its own verification
date, exactly like a leg fee -- so FR-006's prohibition does not reach it. What FR-006 forbids
on a registry graph is a *computed ramp cost*, which exists only per
``(destination x stream x route)``, a triple that diagram does not name.
"""

ABOVE: Final = "applied above the reference"
BELOW: Final = "applied below the reference"
AT: Final = "applied at the reference"
"""Where the declared quote puts the rate actually transacted at, for this leg's role.

Three phrases and no fourth, because ``effective_rate`` has three outcomes. :data:`AT` is a
real case and not a rounding artefact: a zero premium is a legal declaration meaning the
channel trades at its reference, and reporting it as "above" would invent a cost.
"""


@dataclass(frozen=True, slots=True)
class Quote:
    """The declared quote one ``fx`` leg applies, and the two observations behind it.

    The reference and the side are kept apart rather than unioned, because they age under
    different declared kinds. Unioning them here is precisely the collapse FR-028 forbids, and
    a record that had already lost the split could not be un-collapsed by any caller.
    """

    figure: str
    """The rendered quote: the declared number, the direction it is applied in, and the
    reference it is quoted against."""

    reference: Provenance
    """The reference rate's own sources -- the channel's, with both sides' taken out."""

    reference_kind: str
    """The ``ObservationKind`` id the *channel* declares, which governs the reference rate."""

    side: Provenance
    """The applied side's sources. Not the unapplied side's: that observation is not behind
    this edge's figure, and marking this edge with it would report a corridor stale because of
    a rate it does not use."""

    side_kind: str
    """The ``ObservationKind`` id the *side* declares. Usually the faster of the two."""


def sources(quote: Quote) -> Provenance:
    """Everything this quote rests on, for the marks that are not about age."""
    return prov.merge(quote.reference, quote.side)


def verdicts(
    quote: Quote, kinds: Mapping[str, ObservationKind], as_of: date
) -> tuple[StalenessVerdict, ...]:
    """One verdict per observation, each aged under the kind its own table declared.

    Two verdicts rather than one over the union: the reference under the channel's kind, the
    applied side under the side's. Collapsing them to
    ``staleness_of(channel.provenance, kind=channel.kind)`` ages a 7-day premium under a
    365-day threshold and reports it fresh at 82 days.
    """
    return (
        staleness.staleness_of(quote.reference, kinds, kind=quote.reference_kind, as_of=as_of),
        staleness.staleness_of(quote.side, kinds, kind=quote.side_kind, as_of=as_of),
    )


def _reference_sources(channel: FxChannel) -> Provenance:
    """The channel's own sources with both sides' taken out -- the reference rate's.

    The derivation ``core.routes.cost._channel_verdicts`` uses, and for the reason recorded
    there: a channel file declares a kind **three times**, because the reference rate and the
    two sides are three observations going out of date at three speeds.

    Repeated here rather than imported because the two questions differ: costing ages **both**
    sides, since a round trip crosses both, while one edge applies exactly one and must not be
    marked by the other.
    """
    used_by_sides = channel.buy_side.provenance.sources | channel.sell_side.provenance.sources
    return prov.of(ref for ref in channel.provenance.sources if ref not in used_by_sides)


def _direction(channel: FxChannel, side: ChannelSide, role: Side) -> str:
    """Where this side puts the transacted rate relative to the reference, in words.

    Asked of ``channels.effective_rate`` rather than worked out here, so the diagram and the
    engine cannot disagree about a direction -- which is the classic FX bug: every number stays
    plausible while every spread is inverted. The comparison uses the single project tolerance
    rather than a bound invented at this call site.
    """
    effective = fx.effective_rate(side, channel.reference_rate, role=role)
    if is_close(effective, channel.reference_rate):
        return AT
    return ABOVE if effective > channel.reference_rate else BELOW


def _declared(channel: FxChannel, side: ChannelSide) -> str:
    """One side's number, in the form and the unit the declaration actually used.

    Neither form is converted into the other: converting would be the renderer deriving a
    figure, and it would erase which of the two the file used -- which is what a reader
    checking the declaration needs to know.

    Exactly one of the two is set; the loader refuses a side with both or neither (FR-010),
    and so does ``channels._offset``. A side reaching here with neither means that validation
    was bypassed, so it raises rather than rendering a premium of nothing -- which would draw
    the corridor at the reference, the cheapest it could possibly be.
    """
    _, unit_currency = channel.pair
    if side.premium_per_unit is not None:
        return numbers.premium_per_unit(side.premium_per_unit, unit=unit_currency)
    if side.markup_bps is not None:
        return numbers.basis_points(side.markup_bps)
    raise ValueError(
        f"channel {channel.id!r} declares a side with neither a premium nor a markup. "
        "Exactly one of the two forms is required (FR-010): 'at the reference' is declarable "
        "as a zero premium, so an absence can only be an unfinished declaration, and "
        "rendering it as nothing would draw the corridor as free"
    )


def quote_for(leg: Leg, channels: Mapping[str, FxChannel]) -> Quote | None:
    """The quote this leg applies, or ``None`` for a leg that converts nothing.

    ``channel_for`` is the core's own lookup and it raises on an unknown channel id naming the
    known ones -- there is deliberately no default channel, because substituting "the official
    rate" for a misspelt id would reprice a P2P leg at the reference and delete the entire
    spread this project exists to measure. A diagram must fail the same way for the same
    reason: the wrong picture here is a cheap-looking corridor.
    """
    channel = channel_for(channels, leg)
    if channel is None:
        return None
    side, role = fx.side_for(channel, leg.from_ccy, leg.to_ccy)
    price_currency, unit_currency = channel.pair
    reference = numbers.rate(channel.reference_rate, price=price_currency, unit=unit_currency)
    return Quote(
        figure=(
            f"({role.value} side) {_declared(channel, side)}, "
            f"{_direction(channel, side, role)} {reference}"
        ),
        reference=_reference_sources(channel),
        reference_kind=channel.kind,
        side=side.provenance,
        side_kind=side.kind,
    )


def fee_field(leg: Leg) -> str:
    """The leg's own declared fees, as one label field."""
    return f"{FEE_FIELD}{numbers.percent(leg.fee_pct)} + {numbers.amount(leg.fee_fixed)}"


def premium_field(quote: Quote) -> str:
    """The channel quote this leg applies, as one label field."""
    return f"{PREMIUM_FIELD}{quote.figure}"


def edge_figures(leg: Leg, quote: Quote | None) -> list[str]:
    """Every declared-figure field one edge carries, in a fixed order.

    One function so the registry graph and the costed path put the same figures on the same
    edge in the same order. They draw the same leg; a reader comparing the two diagrams is
    entitled to compare them line by line.
    """
    fields = [fee_field(leg)]
    if quote is not None:
        fields.append(premium_field(quote))
    return fields


def edge_provenance(leg: Leg, quote: Quote | None) -> Provenance:
    """Everything an edge's label rests on, so ``unsourced`` is asked of all of it."""
    return leg.provenance if quote is None else prov.merge(leg.provenance, sources(quote))
