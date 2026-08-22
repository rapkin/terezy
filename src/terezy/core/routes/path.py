"""``FundingPath``: the triple that makes a per-destination cost unrepresentable.

FR-008: *access cost MUST be reported per ``(destination x stream x route)``. A cost
attributed to a destination alone MUST NOT be representable -- **not merely
discouraged**.* This module is that requirement's whole mechanism, and it is three fields
long.

**What it prevents.** ``SIMULATOR_SPEC.md`` §4.3.1's finding is that the same acquisition is
nearly free funded from USD contract income and 5-10% expensive funded from a UAH salary. A
function named ``cost_of_reaching(venue)`` reads perfectly reasonable, would pass review from
anyone not holding that finding in mind, and would blend the two into a single figure --
destroying the result while leaving every number plausible. Principle VI's rule is the one
most likely to be broken by accident rather than by intent, and a convention cannot stop
that. A missing type can: with every cost keyed by this record, "the cost of reaching
Binance" has **no type to live in**. It is not a discouraged call; it is an expression that
does not typecheck.

**Why not a required keyword argument.** Better than nothing, and still expressible: a caller
in a hurry passes a constant stream id and gets past it, which is precisely the shortcut this
exists to remove. And why not a naming convention with review? Because that is the mechanism
that already failed once in this repository -- the ``nominal_ytm`` mislabelling in feature 001
passed review and two agents (research.md D2).

**It deliberately does not carry the amount.** A path is *which way*; an amount is *how
much*. Folding the amount in would make a cost's key include the cost's own input, so two
amounts through one route would look like two paths -- and the monthly capacity accumulator,
which is keyed by route, would stop working (plan.md, post-Phase-1 note).

**The fields are keyword-only.** All three are strings, so a positional triple lets a caller
transpose the route id and the destination id and get a confidently wrong answer with no type
error anywhere. Naming them costs one line per call site and removes a class of silent
defect, which is the same trade the rest of this project makes everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class FundingPath:
    """One way of getting money to one place from one income stream.

    All three terms required, no defaults, no optional variant, and no amount. Frozen and
    hashable because costs are keyed by it; carrying no behaviour because a method here
    would be the natural home for exactly the per-destination helper this record exists to
    make impossible (owner decision D-E).
    """

    destination_id: str
    """The venue the money is going to. A currency balance at a place -- "USD at Binance" --
    not an instrument: what is bought once the money is there is a later feature."""

    stream_id: str
    """Which income stream funds it.

    **The term that carries the finding.** The same USD acquisition funded from the USD
    contract income performs no conversion at all; funded from the UAH salary it crosses a
    P2P spread. Without this field in the key, those two are one number, and the number is
    wrong for both.
    """

    route_id: str
    """Which declared route is taken.

    Route identity is ``(provider x currency path x venue)`` rather than provider alone
    (FR-023), because the number of conversions is usually the largest difference between
    two ways of doing the same thing -- so two routes from the same provider are genuinely
    two paths and must not share a cost.
    """
