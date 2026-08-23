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
  official-rate machinery exists.
* **Refused** -- no outcome at all, carrying the typed reason. Never dropped: a silent
  exclusion is how a comparison comes to recommend the only option left standing, and here the
  missing ones are exactly the options nobody has finished declaring.

A contract test counts them: every tuple offered lands in exactly one.

## Ties, and being able to say nothing beats the hurdle

Two outcomes within the single project tolerance are a **tie** and are reported as one
(FR-013), *including* a tie between a tuple and the hurdle itself. The grouping rule lives
once, in :func:`terezy.core.primitives.tolerance.tied_groups`.

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
from terezy.core.primitives.tolerance import is_close, tied_groups
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
    rated: list[tuple[float, TupleOutcome]] = []
    unrated: list[TupleOutcome] = []
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
        if not isinstance(outcome, TupleOutcome):
            refused.append(RefusedTuple(key=candidate, refusal=outcome))
        elif isinstance(rate := outcome.implied_rate, NominalRate):
            rated.append((rate.value, outcome))
        else:
            unrated.append(outcome)
    # Descending, and the sort is stable, so tied outcomes keep the order the caller supplied
    # them in. `_ties` is what stops the head of a tied group being read as a winner.
    ordered = sorted(rated, key=lambda pair: -pair[0])
    ranked = tuple(outcome for _, outcome in ordered)
    index = next(
        (position for position, outcome in enumerate(ranked) if outcome.key == benchmark), None
    )
    if index is None:
        return _no_benchmark(
            benchmark,
            scored=ranked,
            unrated=tuple(unrated),
            refused=tuple(refused),
        )
    rates = [rate for rate, _ in ordered]
    return Comparison(
        horizon=horizon,
        continuation=continuation,
        ranked=ranked,
        benchmark=index,
        ties=tied_groups(rates),
        refused=tuple(refused),
        not_comparable=tuple(unrated),
        beats_benchmark=_beats(rates, index),
    )


def _beats(rates: Sequence[float], benchmark: int) -> tuple[int, ...]:
    """Which tuples beat the benchmark by more than the project tolerance (FR-011).

    Strictly more: an outcome within the tolerance of the hurdle is a **tie** and is not a
    winner, which is what makes "nothing beats the hurdle" sayable when it is true by a
    whisker in either direction. The benchmark never appears in its own list.
    """
    hurdle = rates[benchmark]
    return tuple(
        index
        for index, rate in enumerate(rates)
        if index != benchmark and rate > hurdle and not is_close(rate, hurdle)
    )


def _no_benchmark(
    benchmark: Tuple,
    *,
    scored: tuple[TupleOutcome, ...],
    unrated: tuple[TupleOutcome, ...],
    refused: tuple[RefusedTuple, ...],
) -> BenchmarkUnavailable:
    """There is no comparison, only its parts -- and the parts are carried, not discarded.

    Two ways to arrive here and they are different facts, so the reason says which: the
    benchmark tuple **refused** outright, or it produced a complete outcome with **no rate** to
    rank anything against.
    """
    unavailable = next(
        (outcome.implied_rate for outcome in unrated if outcome.key == benchmark), None
    )
    if isinstance(unavailable, RateNotComparable):
        return BenchmarkUnavailable(
            refusal=unavailable,
            scored=scored,
            refused=refused,
            not_comparable=unrated,
            reason=(
                f"the benchmark tuple for {benchmark.instrument_id!r} produced a complete "
                f"outcome and no rate: {unavailable.reason} Nothing can be ranked against a "
                "benchmark with no figure to compare, and ranking the rest without one would "
                "let the head of the list read as a winner."
            ),
        )
    return BenchmarkUnavailable(
        refusal=next(item.refusal for item in refused if item.key == benchmark),
        scored=scored,
        refused=refused,
        not_comparable=unrated,
        reason=(
            f"the benchmark tuple for {benchmark.instrument_id!r} produced no outcome, so "
            "there is nothing to compare against. The other tuples' figures are carried below "
            "rather than discarded, and they are deliberately not ranked: FR-011 says the "
            "hurdle is always scored and always shown, and a ranking with no benchmark invites "
            "its own head to be read as a winner."
        ),
    )
