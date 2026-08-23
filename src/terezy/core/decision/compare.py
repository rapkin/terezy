"""The comparison: every tuple over one horizon, with the hurdle among them as the benchmark.

This is where `SIMULATOR_SPEC.md` §8 question 1 -- *does anything beat 15.5% tax-free OVDP
after every other option's fees, taxes and access costs?* -- becomes a computed answer instead
of a chart that flatters the expensive options.

## The benchmark comes out of the same function as everything it benchmarks

:attr:`~terezy.core.results.tuple.Comparison.benchmark` is an **index** into the ranked
sequence, never a separately computed figure beside it (FR-012, research.md D3). The hurdle in
this comparison *is* the OVDP evaluated as a tuple through its declared domestic routes, by
:func:`terezy.core.decision.tuple_outcome.evaluate`, ranked with everything else -- so a test
asserts ``comparison.ranked[comparison.benchmark] is the_benchmark_outcome`` with ``is``,
which is a claim about shared origin rather than about two numbers agreeing today. A
benchmark computed by a privileged side channel would drift from what it benchmarks, and the
drift would be invisible because both figures would look reasonable.

002's ``Ranking.recommended`` set the precedent and its argument is unchanged. This module
adds nothing to it except the direction of the sort: a ranking of routes orders by *cost
ascending*, and a comparison of tuples orders by *return descending*.

## One horizon, stated once

Every tuple is evaluated over the same :class:`~terezy.core.instruments.interface.DateRange`
and under the same declared continuation assumption (FR-025). Comparing a two-year instrument
over two years against a twenty-year one over twenty answers two different questions, and
carrying an early instrument's proceeds forward at some rate would need a reinvestment
assumption nobody declared -- the invented number this feature is most likely to reach for.

## Three places a tuple can land, and every one of them is reported

* **Ranked** -- comparison-ready: an amount, and a rate to order it by.
* **Not comparable** -- computed in full, with no rate: a tuple funded in one currency and
  spent in another, whose amount is real and whose ratio is not available until the
  official-rate machinery exists. 002's ``Ranking.not_comparable``, unchanged.
* **Refused** -- no outcome at all, carrying the typed reason. Never dropped: a silent
  exclusion is how a comparison comes to recommend the only option left standing, and here the
  missing ones are exactly the options nobody has finished declaring.

A contract test counts them: every tuple offered lands in exactly one.

## Ties, and being able to say nothing beats the hurdle

Two outcomes within the single project tolerance are a **tie** and are reported as one
(FR-013), *including* a tie between a tuple and the hurdle itself. The tie rule is 002's,
anchored rather than chained for the reason ``routes.ranking._ties`` gives: tolerance equality
is not transitive, and chaining would let a band of arbitrary width become one tie.

:attr:`~terezy.core.results.tuple.Comparison.beats_benchmark` is a field rather than something
a reader derives from the ordering, because deriving it means re-implementing the tie rule at
every call site -- and the first implementation to get it wrong will report a winner by a
hair. Empty is the answer this product exists to be able to give plainly.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.instruments.interface import DateRange
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.tolerance import is_close
from terezy.core.results.tuple import (
    BenchmarkUnavailable,
    Comparison,
    ContinuationAssumption,
    RateNotComparable,
    RefusedTuple,
    Tuple,
    TupleOutcome,
)

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Sequence


def compare(
    tuples: Sequence[Tuple],
    *,
    benchmark: Tuple,
    amount: Money,
    horizon: DateRange,
    as_of: date,
    continuation: ContinuationAssumption,
    registries: Registries,
) -> Comparison | BenchmarkUnavailable:
    """Score every tuple over one horizon and rank them, with the benchmark among them.

    ``benchmark`` is a tuple like any other and is evaluated by the same call in the same loop.
    It is named separately only so the result can point at it; it is **not** costed, ranked or
    scored differently, and if the caller also lists it in ``tuples`` it is evaluated once.

    Pure, and every argument that could have been read from a clock is passed instead:
    ``horizon.start`` is when the money leaves, ``as_of`` is when the question is asked.
    ``continuation`` has no default anywhere in the stack, because FR-025 forbids defaulting
    what an instrument terminating before the horizon does with its proceeds.

    Returns a :class:`~terezy.core.results.tuple.BenchmarkUnavailable` -- a different type,
    not a weaker comparison -- where the benchmark itself produced no rate. FR-011 says the
    hurdle must always be scored and always shown, so ranking the rest against nothing would
    invite the head of the list to be read as a winner.
    """
    candidates = (benchmark, *(item for item in tuples if item != benchmark))
    scored: list[tuple[Tuple, TupleOutcome]] = []
    refused: list[RefusedTuple] = []
    for candidate in candidates:
        outcome = evaluate(
            candidate,
            amount=amount,
            horizon=horizon,
            as_of=as_of,
            continuation=continuation,
            registries=registries,
        )
        if isinstance(outcome, TupleOutcome):
            scored.append((candidate, outcome))
        else:
            refused.append(RefusedTuple(key=candidate, refusal=outcome))
    rated = [outcome for _, outcome in scored if isinstance(outcome.implied_rate, NominalRate)]
    unrated = tuple(
        outcome for _, outcome in scored if isinstance(outcome.implied_rate, RateNotComparable)
    )
    benchmarked = next((outcome for key, outcome in scored if key is candidates[0]), None)
    if benchmarked is None or benchmarked not in rated:
        return _no_benchmark(
            benchmark, benchmarked, scored=tuple(rated), unrated=unrated, refused=tuple(refused)
        )
    ranked = tuple(sorted(rated, key=_by_return))
    index = next(position for position, outcome in enumerate(ranked) if outcome is benchmarked)
    return Comparison(
        horizon=horizon,
        continuation=continuation,
        ranked=ranked,
        benchmark=index,
        ties=_ties(ranked),
        refused=tuple(refused),
        not_comparable=unrated,
        beats_benchmark=_beats(ranked, index),
    )


def _rate_of(outcome: TupleOutcome) -> float:
    """The outcome's rate, for an outcome already established to have one.

    A narrowing helper rather than a cast: the split in :func:`compare` established that this
    outcome's ``implied_rate`` is a figure, and this is where that knowledge survives into the
    sort key -- the same shape ``routes.ranking._Comparable`` takes for a round-trip cost.
    """
    rate = outcome.implied_rate
    if isinstance(rate, NominalRate):
        return rate.value
    raise TypeError(  # pragma: no cover -- `compare` filters these out before sorting
        f"an outcome for {outcome.key.instrument_id!r} reached the ranking with no rate. "
        "Outcomes carrying RateNotComparable belong in `not_comparable`, which is where "
        "`compare` puts them."
    )


def _by_return(outcome: TupleOutcome) -> float:
    """Best first: the negated rate, so the sort is ascending on a descending quantity.

    **One key, not three.** 002's ranking orders on ``(cost, ceiling, latency)`` because those
    were the three things FR-016 put in priority order; here the owner asked one question --
    what comes back, after everything -- and the amount and the span are already inside the
    rate. A second key would be a preference the owner did not state, and where two rates
    genuinely agree the answer is a tie rather than a tiebreak.

    Python's sort is stable, so tied outcomes keep the order the caller supplied them in and
    the sequence is deterministic; :func:`_ties` is what stops the head of a tied group being
    read as a winner.
    """
    return -_rate_of(outcome)


def _ties(ranked: Sequence[TupleOutcome]) -> tuple[tuple[int, ...], ...]:
    """Groups of indices whose rate is the same within the project tolerance (FR-013).

    002's ``routes.ranking._ties``, unchanged in rule and in reasoning: grouped **against each
    group's first member** rather than chained neighbour to neighbour, because tolerance
    equality is not transitive and chaining would let a band of arbitrary width become one tie
    as candidates accumulate -- the tolerance absorbing a real difference. Anchoring bounds
    every reported tie at one tolerance wide.

    The sequence is sorted, so tied entries are adjacent and one pass suffices. Groups of one
    are not ties and are not reported.
    """
    groups: list[tuple[int, ...]] = []
    current: list[int] = []
    anchor: float | None = None
    for index, outcome in enumerate(ranked):
        rate = _rate_of(outcome)
        if anchor is not None and is_close(rate, anchor):
            current.append(index)
            continue
        if len(current) > 1:
            groups.append(tuple(current))
        anchor = rate
        current = [index]
    if len(current) > 1:
        groups.append(tuple(current))
    return tuple(groups)


def _beats(ranked: Sequence[TupleOutcome], benchmark: int) -> tuple[int, ...]:
    """Which tuples beat the benchmark by more than the project tolerance (FR-011).

    Strictly more: an outcome within the tolerance of the hurdle is a **tie** and is not a
    winner, which is what makes "nothing beats the hurdle" sayable when it is true by a
    whisker in either direction. The benchmark never appears in its own list.
    """
    hurdle = _rate_of(ranked[benchmark])
    return tuple(
        index
        for index, outcome in enumerate(ranked)
        if index != benchmark
        and _rate_of(outcome) > hurdle
        and not is_close(_rate_of(outcome), hurdle)
    )


def _no_benchmark(
    benchmark: Tuple,
    outcome: TupleOutcome | None,
    *,
    scored: tuple[TupleOutcome, ...],
    unrated: tuple[TupleOutcome, ...],
    refused: tuple[RefusedTuple, ...],
) -> BenchmarkUnavailable:
    """There is no comparison, only its parts -- and the parts are carried, not discarded.

    Two ways to arrive here and they are different facts, so the reason says which: the
    benchmark tuple **refused** (a declaration is missing, a seam does not chain, its route is
    closed), or it produced a complete outcome with **no rate** to rank anything against.
    """
    if outcome is None:
        refusal = next(item.refusal for item in refused if item.key == benchmark)
        reason = (
            f"the benchmark tuple for {benchmark.instrument_id!r} produced no outcome, so "
            "there is nothing to compare against. The other tuples' figures are carried "
            "below rather than discarded, and they are deliberately not ranked: FR-011 says "
            "the hurdle is always scored and always shown, and a ranking with no benchmark "
            "invites its own head to be read as a winner."
        )
        return BenchmarkUnavailable(
            refusal=refusal,
            scored=scored,
            refused=refused,
            not_comparable=unrated,
            reason=reason,
        )
    rate = outcome.implied_rate
    if not isinstance(rate, RateNotComparable):  # pragma: no cover -- `compare` proves this
        raise TypeError(
            f"the benchmark for {benchmark.instrument_id!r} has a rate and should have been "
            "ranked. `compare` only reaches here when it has none."
        )
    return BenchmarkUnavailable(
        refusal=rate,
        scored=scored,
        refused=refused,
        not_comparable=unrated,
        reason=(
            f"the benchmark tuple for {benchmark.instrument_id!r} produced a complete outcome "
            f"and no rate: {rate.reason} Nothing can be ranked against a benchmark with no "
            "figure to compare, and ranking the rest without one would let the head of the "
            "list read as a winner."
        ),
    )
