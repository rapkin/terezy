"""Dominance: the relation, and the pass that reports three populations over one section.

019. *A* **dominates** *B* when, on every declared objective, *A* is **not worse than *B* by more
than the project comparison allows**, and on **at least one** it is **better by more than that
objective's declared indifference band** (FR-007). The definition lives here and nowhere else.

**Why the two halves use different rules.** The weak half goes through the project comparison so
a last-bit difference on one objective does not withdraw a verdict a five-thousand-hryvnia gap on
another earned, leaving a dominated candidate standing in the set; it goes through *that*
comparison rather than a fresh absolute one because a second rule for when two amounts are the
same money is a second tolerance policy, which Principle IV forbids. The band sits in the strict
half only: with the band in both halves the window in which a cycle is possible is *(p - 1)*
**bands** wide and scales with the band, so no floor on the band ever closes it, while with the
slack in the weak half it is *(p - 1)* **slacks** wide -- which FR-011c's floor does close.

**The relation is not transitive, and the claim is not made.** Slack does not compose, so
*A > B* and *B > C* leave *A > C* free to fail. Acyclicity is what the never-empty guarantee
needs; transitivity is not, which is why only one of them is asserted.

**No feasibility rule, no pre-screen, no early exit, no filter** (FR-010), and no weight, score
or priority anywhere (FR-005). Nothing is dropped: dominance is a reported relation over the
evaluated population, never applied to it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import TYPE_CHECKING, Final, assert_never

from terezy.core.decision import candidates as enumeration
from terezy.core.primitives import money, staleness
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import is_close, slack
from terezy.core.results.answer import (
    MoneyArrivesAfterHorizon,
    SectionOutcome,
    StatedExclusion,
)
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.dominance import (
    BandBelowTheAcyclicityFloor,
    BandInAnotherCurrency,
    BenchmarkWasWithheld,
    DateFigure,
    DayWidth,
    DeliveredInTwoCurrencies,
    DominanceRefused,
    DominanceResult,
    DominanceVerdict,
    Dominated,
    EveryOtherIsDominated,
    EveryOtherIsNotPlaced,
    Figure,
    FigureMissing,
    FigureUnavailable,
    HurdleIsDominated,
    Incomparable,
    IncomparablePair,
    Indistinguishable,
    LeftDominates,
    MemberRestsOn,
    Mixed,
    MoneyFigure,
    MoneyWidth,
    Neither,
    NoBenchmarkToStandAgainst,
    NoQuestionAmountInTheCurrencyCompared,
    NoStatedAssumptionSeparatesThem,
    NoSurveyToRunOver,
    NothingDominatesTheHurdle,
    NotPlaced,
    OnlyOneEvaluated,
    PairVerdict,
    ResolvedBand,
    RightDominates,
    SeparatingAssumptions,
    SeveralQuestionAmountsInTheCurrencyCompared,
    TheSetDoesNotHaveOneMember,
    TooCloseToCall,
    WhyOneMember,
    Width,
)
from terezy.core.results.objectives import (
    READS,
    AbsoluteBand,
    Criterion,
    DaysBand,
    FractionOfTheQuestionAmount,
    Objective,
    ObjectiveDirection,
    ObjectiveSet,
)
from terezy.core.results.tuple import BenchmarkUnavailable, Comparison, Tuple, TupleOutcome

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable, Mapping, Sequence

NO_ARRIVALS: Final = "TupleOutcome.arrivals"
"""What a criterion reading the last arrival finds when there is none: the record field that
carried nothing, named as an identifier rather than as a sentence (FR-028)."""


def relates(
    left: Sequence[Figure],
    right: Sequence[Figure],
    *,
    directions: Sequence[ObjectiveDirection],
    widths: Sequence[Width],
) -> PairVerdict:
    """FR-007's definition, over figure vectors, and **the only place it lives**.

    It takes vectors rather than outcomes, which is what lets a generated battery run at three
    to five objectives over a criterion set with two members (research D1) -- and what makes a
    non-transitive witness three vectors rather than three registries.

    Two figures of different kinds at one position is a programmer error and raises: it means a
    criterion and a reader disagree about what the criterion reads, which is not a business
    outcome. A **currency** mismatch is a business outcome and returns
    :class:`~terezy.core.results.dominance.Incomparable`.
    """
    unreadable = first_unreadable(left, right)
    if unreadable is not None:
        return unreadable
    decided = [_decide(one, other) for one, other in zip(left, right, strict=True)]
    advantages = [
        _towards(gap, direction) for (gap, _), direction in zip(decided, directions, strict=True)
    ]
    same = [agreed for _, agreed in decided]
    bands = [_width_of(width) for width in widths]
    forward = _dominates(advantages, same, bands)
    backward = _dominates([-value for value in advantages], same, bands)
    if forward is not None and backward is not None:
        raise AssertionError(
            "two candidates dominate each other, which is only possible where a declared band "
            "is narrower than the slack the weak half allows -- the first half of FR-011c's "
            "floor exists to make this unreachable, and the pass checks it before comparing"
        )
    if forward is not None:
        return LeftDominates(at_least_as_good_at=forward[0], strictly_better_at=forward[1])
    if backward is not None:
        return RightDominates(at_least_as_good_at=backward[0], strictly_better_at=backward[1])
    if all(abs(value) <= band for value, band in zip(advantages, bands, strict=True)):
        return TooCloseToCall()
    return Neither()


def _dominates(
    advantages: Sequence[float], same: Sequence[bool], bands: Sequence[float]
) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """The positions behind a verdict in one direction, or ``None`` where there is none.

    Returned rather than a bool so the verdict can name what decided it without the caller
    re-deriving the comparison and reaching a second answer.
    """
    weak = [value >= 0.0 or agreed for value, agreed in zip(advantages, same, strict=True)]
    if not all(weak):
        return None
    better = tuple(
        position
        for position, (value, band) in enumerate(zip(advantages, bands, strict=True))
        if value > band
    )
    if not better:
        return None
    return tuple(range(len(advantages))), better


def first_unreadable(left: Sequence[Figure], right: Sequence[Figure]) -> Incomparable | None:
    """The first position no verdict can be read at, or ``None`` where every one can.

    Exported because the pass needs the same answer *before* it looks up a width: a width is
    resolved per ``(criterion, currency)``, and a position whose two figures are in different
    currencies or missing altogether has no such pair to resolve one for. Two readings of *this
    pair cannot be read* would be the place they came to disagree.
    """
    for position, (one, other) in enumerate(zip(left, right, strict=True)):
        match (one, other):
            case (FigureUnavailable(), _):
                return Incomparable(position=position, why=FigureMissing(what=one.what))
            case (_, FigureUnavailable()):
                return Incomparable(position=position, why=FigureMissing(what=other.what))
            case (MoneyFigure(), MoneyFigure()) if one.amount.currency is not other.amount.currency:
                return Incomparable(
                    position=position,
                    why=DeliveredInTwoCurrencies(
                        left_currency=one.amount.currency,
                        right_currency=other.amount.currency,
                    ),
                )
            case (MoneyFigure(), MoneyFigure()) | (DateFigure(), DateFigure()):
                continue
            case _:
                raise AssertionError(
                    f"objective {position} was handed a {type(one).__name__} against a "
                    f"{type(other).__name__}. A criterion reads one kind of figure, so two kinds "
                    "at one position means a criterion and its reader disagree about what it reads"
                )
    return None


def _decide(left: Figure, right: Figure) -> tuple[float, bool]:
    """One readable position: the left figure's raw lead over the right, and whether they agree.

    *Raw* means before the objective's direction is applied -- a larger number is a positive
    lead here whether or not larger is better, and :func:`_towards` turns it into an advantage.
    Splitting the two is what keeps the direction out of the closeness rule.

    *Agree* is the project comparison on money and **exact equality** on a date: FR-011d fixes a
    date's slack at zero, and applying the float comparison to an ordinal near 740 000 would
    allow a slack of some 7e-4 days that no contract promises.
    """
    match (left, right):
        case (MoneyFigure(), MoneyFigure()):
            return (
                left.amount.amount - right.amount.amount,
                is_close(left.amount.amount, right.amount.amount),
            )
        case (DateFigure(), DateFigure()):
            return (float((left.on - right.on).days), left.on == right.on)
        case _:  # pragma: no cover -- first_unreadable has already refused every other pairing
            raise AssertionError("an unreadable position reached the comparison")


def _towards(gap: float, direction: ObjectiveDirection) -> float:
    """The raw lead as an advantage: positive where the left candidate is the better of the two."""
    match direction:
        case ObjectiveDirection.MORE_IS_BETTER:
            return gap
        case ObjectiveDirection.LESS_IS_BETTER:
            return -gap
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(direction)


def _width_of(width: Width) -> float:
    """One band as a number in the same units as its position's advantage."""
    match width:
        case MoneyWidth():
            return width.amount.amount
        case DayWidth():
            return float(width.days)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(width)


# ---------------------------------------------------------------------------
# The pass over one section
# ---------------------------------------------------------------------------


def dominance(
    outcome: SectionOutcome,
    *,
    withheld: Sequence[MoneyArrivesAfterHorizon],
    excludes: Sequence[StatedExclusion],
    objectives: ObjectiveSet,
    amounts: Mapping[str, Money],
) -> DominanceResult | DominanceRefused:
    """One horizon section's non-dominated set, or the typed refusal that replaces it.

    Pure: no clock, no I/O, no randomness, no solver, no seed (FR-024). ``amounts`` is the
    question's own mapping of stream id to ``Money`` and is read for one thing only -- it is
    what a fraction band resolves against (FR-011d).

    **It takes the section's parts, not the section.** FR-027 puts the result *on* the frozen
    ``HorizonSection``, so a pass taking the finished record could not be called before the
    record exists; ``_section`` already computes ``withheld`` and ``excludes`` before it
    constructs anything, and passes the result into the constructor.
    """
    if not isinstance(outcome, CandidateSurvey):
        return NoSurveyToRunOver(refusal=outcome)
    comparison = outcome.comparison
    if isinstance(comparison, BenchmarkUnavailable):
        return NoBenchmarkToStandAgainst(reason=comparison.reason)
    late = {item.key: item for item in withheld}
    hurdle = comparison.ranked[comparison.benchmark].key
    if hurdle in late:
        return BenchmarkWasWithheld(key=hurdle, arrives_on=late[hurdle].arrives_on)
    population = _population(outcome, comparison, late)
    figures = {
        item.key: tuple(_figure(item, objective.criterion) for objective in objectives.objectives)
        for item in population
    }
    resolved = _resolve_widths(objectives, figures.values(), amounts)
    if not isinstance(resolved, _Widths):
        return resolved
    return _report(
        population=population,
        figures=figures,
        widths=resolved,
        objectives=objectives,
        hurdle=hurdle,
        excludes=excludes,
    )


def _population(
    outcome: CandidateSurvey,
    comparison: Comparison,
    late: Mapping[Tuple, MoneyArrivesAfterHorizon],
) -> tuple[TupleOutcome, ...]:
    """What the section evaluated, less what 015 FR-030 withheld, in 014 FR-016's order.

    The order is read off the enumerated set rather than rebuilt from the key's terms, because
    014 fixes it there and a second sort key here would be the place the two came to disagree.
    A candidate whose figure was withheld from the reader decides no other candidate's standing
    (FR-006).
    """
    order = {item.key: position for position, item in enumerate(outcome.enumerated.candidates)}
    return tuple(
        sorted(
            (item for item in enumeration.evaluated(comparison) if item.key not in late),
            key=lambda item: order[item.key],
        )
    )


def _figure(item: TupleOutcome, criterion: Criterion) -> Figure:
    """One candidate's reading on one criterion. A criterion is a reader and nothing more."""
    match criterion:
        case Criterion.MONEY_AT_THE_ENDPOINT:
            return MoneyFigure(amount=item.reaches)
        case Criterion.ALL_MONEY_BACK_ON:
            if not item.arrivals:
                return FigureUnavailable(what=NO_ARRIVALS)
            return DateFigure(on=item.arrivals[-1].arrived_on)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(criterion)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Widths:
    """The widths one section's pairs are compared at, and the fractions among them.

    Keyed by ``(position, currency)``, with ``None`` standing for a date objective, which has
    one width whatever the pair. A lookup rather than one width per objective, because a section
    comparing pairs in two currencies has two widths on one criterion.
    """

    by_position: Mapping[tuple[int, Currency | None], Width]
    reported: tuple[ResolvedBand, ...]


def _resolve_widths(
    objectives: ObjectiveSet,
    readings: Iterable[tuple[Figure, ...]],
    amounts: Mapping[str, Money],
) -> _Widths | DominanceRefused:
    """A width per ``(objective, currency some pair is actually compared in)``.

    **Lazily**: a currency no two candidates both deliver is never resolved, never floored and
    never reported, so the token amount a question states to make an empty stream visible cannot
    produce a width nobody reads (research D6).

    **And floored where it is resolved**: FR-011c's check needs the magnitudes of the figures
    being compared, which a declaration file does not carry, so it happens here rather than at
    load. It is checked once per objective against the **widest** slack in the section, which
    bounds every pair -- stricter than necessary for most pairs, and the strictness is the point.
    """
    vectors = list(readings)
    widths: dict[tuple[int, Currency | None], Width] = {}
    reported: list[ResolvedBand] = []
    for position, objective in enumerate(objectives.objectives):
        kind = READS[objective.criterion]
        if kind == "date":
            widths[(position, None)] = _day_width(objective)
            continue
        for currency in _currencies_with_a_pair(vectors, position):
            resolved = _money_width(objective, currency, amounts)
            if not isinstance(resolved, tuple):
                return resolved
            width, band = resolved
            floor = _below_the_floor(
                objective,
                width,
                currency=currency,
                vectors=vectors,
                position=position,
                objectives=objectives,
            )
            if floor is not None:
                return floor
            widths[(position, currency)] = width
            if band is not None:
                reported.append(band)
    return _Widths(
        by_position=widths,
        reported=tuple(
            sorted(reported, key=lambda item: (item.criterion.value, item.currency.value))
        ),
    )


def _currencies_with_a_pair(
    vectors: Sequence[tuple[Figure, ...]], position: int
) -> tuple[Currency, ...]:
    """The currencies in which at least two candidates carry a figure on this objective.

    At least two, because a currency only one candidate delivers is in no pair, and a width
    resolved for it would be one nothing reads -- which is where a band nobody chose gets
    computed from a token amount.
    """
    counted: dict[Currency, int] = {}
    for vector in vectors:
        figure = vector[position]
        if isinstance(figure, MoneyFigure):
            counted[figure.amount.currency] = counted.get(figure.amount.currency, 0) + 1
    return tuple(
        sorted(
            (currency for currency, count in counted.items() if count > 1),
            key=lambda currency: currency.value,
        )
    )


def _day_width(objective: Objective) -> DayWidth:
    """A date objective's band. The loader admits only a day count on one."""
    if not isinstance(objective.band, DaysBand):
        raise TypeError(
            f"{objective.criterion.value!r} reads a date and carries a "
            f"{type(objective.band).__name__}; the loader refuses that shape, so a record "
            "reaching here with one was built by hand against its own criterion"
        )
    return DayWidth(days=objective.band.days)


def _money_width(
    objective: Objective, currency: Currency, amounts: Mapping[str, Money]
) -> tuple[Width, ResolvedBand | None] | DominanceRefused:
    """One money objective's width in one currency, and the band record where it resolved.

    A fraction resolves against the **one** amount the question states in that currency, never
    against a candidate's own figure -- which would make the width for *A* against *B* differ
    from the width for *B* against *A* and break FR-011's symmetry. An absolute band is its own
    width and is reported in its declared form, so it produces no record here.
    """
    match objective.band:
        case AbsoluteBand():
            if objective.band.amount.currency is not currency:
                return BandInAnotherCurrency(
                    criterion=objective.criterion,
                    declared_in=objective.band.amount.currency,
                    compared_in=currency,
                )
            return MoneyWidth(amount=objective.band.amount), None
        case FractionOfTheQuestionAmount():
            stated = [
                (stream_id, amount)
                for stream_id, amount in sorted(amounts.items())
                if amount.currency is currency
            ]
            if not stated:
                return NoQuestionAmountInTheCurrencyCompared(
                    criterion=objective.criterion, currency=currency
                )
            if len(stated) > 1:
                return SeveralQuestionAmountsInTheCurrencyCompared(
                    criterion=objective.criterion,
                    currency=currency,
                    stream_ids=tuple(stream_id for stream_id, _ in stated),
                    amounts=tuple(amount for _, amount in stated),
                )
            of_amount = stated[0][1]
            width = money.scale(of_amount, objective.band.proportion)
            return (
                MoneyWidth(amount=width),
                ResolvedBand(
                    criterion=objective.criterion,
                    currency=currency,
                    from_amount=of_amount,
                    width=width,
                ),
            )
        case DaysBand():
            raise TypeError(
                f"{objective.criterion.value!r} reads money and carries a day band; the loader "
                "refuses that shape, so a record reaching here with one was built by hand "
                "against its own criterion"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(objective.band)


def _below_the_floor(
    objective: Objective,
    width: Width,
    *,
    currency: Currency,
    vectors: Sequence[tuple[Figure, ...]],
    position: int,
    objectives: ObjectiveSet,
) -> BandBelowTheAcyclicityFloor | None:
    """FR-011c, both conditions: ``band > slack`` **and** ``band >= (p - 1) * slack``.

    The second looks redundant at two objectives, where the first implies it, and is the whole
    guarantee above them: at three objectives a band of one and a half slacks admits a
    three-cycle with every candidate placed and the set empty. It is stated in the objectives'
    own count because a cycle's length runs to the size of the population and bounds nothing.
    """
    magnitudes = [
        abs(figure.amount.amount)
        for vector in vectors
        if isinstance(figure := vector[position], MoneyFigure)
        and figure.amount.currency is currency
    ]
    largest = max(magnitudes, default=0.0)
    allowed = slack(largest, -largest)
    declared = _width_of(width)
    floor = allowed * (len(objectives.objectives) - 1)
    if declared > allowed and declared >= floor:
        return None
    if not isinstance(width, MoneyWidth):
        raise TypeError(
            f"the acyclicity floor was measured on {objective.criterion.value!r} with a "
            f"{type(width).__name__}; a date objective's slack is zero and no floor runs there"
        )
    return BandBelowTheAcyclicityFloor(
        criterion=objective.criterion,
        declared=objective.band,
        resolved=width.amount,
        slack=allowed,
        floor=floor,
        objective_count=len(objectives.objectives),
    )


def _report(
    *,
    population: Sequence[TupleOutcome],
    figures: Mapping[Tuple, tuple[Figure, ...]],
    widths: _Widths,
    objectives: ObjectiveSet,
    hurdle: Tuple,
    excludes: Sequence[StatedExclusion],
) -> DominanceResult:
    """Every pair, sorted into the three populations and the two relations beside them.

    Every sequence is in 014 FR-016's candidate order and in **no** objective's order (FR-025):
    an order by an objective is the ranking this feature exists to refuse to present.
    """
    directions = tuple(objective.direction for objective in objectives.objectives)
    criteria = tuple(objective.criterion for objective in objectives.objectives)
    marks = {item.key: (item.provenance, item.staleness) for item in population}
    incomparable: list[IncomparablePair] = []
    neighbours: dict[Tuple, list[Tuple]] = {item.key: [] for item in population}
    against: dict[Tuple, list[DominanceVerdict]] = {item.key: [] for item in population}
    pairs_of: dict[Tuple, list[IncomparablePair]] = {item.key: [] for item in population}
    for left, right in combinations(population, 2):
        match _verdict_for(
            left.key,
            right.key,
            figures=figures,
            widths=widths,
            directions=directions,
            criteria=criteria,
        ):
            case IncomparablePair() as pair:
                incomparable.append(pair)
                pairs_of[pair.left].append(pair)
                pairs_of[pair.right].append(pair)
            case DominanceVerdict() as verdict:
                against[verdict.over].append(_marked(verdict, marks))
            case TooCloseToCall():
                neighbours[left.key].append(right.key)
                neighbours[right.key].append(left.key)
            case Neither():
                continue
    decided = len(population) - 1
    not_placed = tuple(
        NotPlaced(key=item.key, every_pair=tuple(pairs_of[item.key]))
        for item in population
        if decided > 0 and len(pairs_of[item.key]) == decided
    )
    unplaced = {item.key for item in not_placed}
    dominated = tuple(
        Dominated(key=item.key, dominated_by=tuple(against[item.key]))
        for item in population
        if against[item.key]
    )
    beaten = {item.key for item in dominated}
    non_dominated = tuple(
        item.key for item in population if item.key not in beaten and item.key not in unplaced
    )
    _check_the_populations_partition(population, non_dominated, dominated, not_placed)
    return DominanceResult(
        objectives=objectives,
        resolved_bands=widths.reported,
        non_dominated=non_dominated,
        dominated=dominated,
        not_placed=not_placed,
        incomparable=tuple(incomparable),
        indistinguishable=tuple(
            Indistinguishable(key=item.key, neighbours=tuple(neighbours[item.key]))
            for item in population
            if neighbours[item.key]
        ),
        benchmark_standing=(
            HurdleIsDominated(key=hurdle, by=tuple(against[hurdle]))
            if against[hurdle]
            else NothingDominatesTheHurdle(key=hurdle)
        ),
        separating=_separating(non_dominated, population, excludes),
    )


def _verdict_for(
    left: Tuple,
    right: Tuple,
    *,
    figures: Mapping[Tuple, tuple[Figure, ...]],
    widths: _Widths,
    directions: Sequence[ObjectiveDirection],
    criteria: Sequence[Criterion],
) -> IncomparablePair | DominanceVerdict | TooCloseToCall | Neither:
    """One pair, lifted from ``relates``' positions to the criteria that occupy them.

    The two verdicts that carry nothing are passed through as themselves rather than reduced to
    a flag: indistinguishability is reported per candidate rather than per pair, and *each is
    better at something* is the ordinary state of a partial order, so neither has a record of
    its own on the result -- but the caller still has to tell them apart.
    """
    unreadable = first_unreadable(figures[left], figures[right])
    if unreadable is not None:
        return IncomparablePair(
            left=left,
            right=right,
            criterion=criteria[unreadable.position],
            why=unreadable.why,
        )
    verdict = relates(
        figures[left],
        figures[right],
        directions=directions,
        widths=_widths_for(figures[left], widths),
    )
    match verdict:
        case LeftDominates():
            return _verdict(
                left, right, verdict.at_least_as_good_at, verdict.strictly_better_at, criteria
            )
        case RightDominates():
            return _verdict(
                right, left, verdict.at_least_as_good_at, verdict.strictly_better_at, criteria
            )
        case TooCloseToCall() | Neither() as decided:
            return decided
        case _:  # pragma: no cover -- the incomparable arm is taken above
            raise AssertionError("relates returned a verdict its caller does not handle")


def _widths_for(vector: Sequence[Figure], widths: _Widths) -> tuple[Width, ...]:
    """The widths one readable pair is compared at, keyed by the currency it is compared in.

    Read off one of the two vectors, which is sound only because the caller has already
    established that every position is readable: a readable money position has both figures in
    one currency, so either vector names it.
    """
    return tuple(
        widths.by_position[
            (position, figure.amount.currency if isinstance(figure, MoneyFigure) else None)
        ]
        for position, figure in enumerate(vector)
    )


def _verdict(
    winner: Tuple,
    loser: Tuple,
    weak: Sequence[int],
    strict: Sequence[int],
    criteria: Sequence[Criterion],
) -> DominanceVerdict:
    """One ordered pair, with the marks left for :func:`_marked` to merge."""
    return DominanceVerdict(
        dominates=winner,
        over=loser,
        at_least_as_good_on=tuple(criteria[position] for position in weak),
        strictly_better_on=tuple(criteria[position] for position in strict),
        provenance=prov.EMPTY,
        staleness=staleness.UNASSESSED,
    )


def _marked(
    verdict: DominanceVerdict,
    marks: Mapping[Tuple, tuple[prov.Provenance, staleness.StalenessVerdict]],
) -> DominanceVerdict:
    """FR-022: the union of **both** candidates' marks, and their merged staleness verdict.

    Principle I's propagation rule applies to a comparison exactly as it applies to a figure:
    *A dominates B* computed from two unverified figures is an unverified claim, and a verdict
    that looked cleaner than either figure behind it would be a lost mark.
    """
    left_prov, left_stale = marks[verdict.dominates]
    right_prov, right_stale = marks[verdict.over]
    return replace(
        verdict,
        provenance=prov.merge(left_prov, right_prov),
        staleness=staleness.merge(left_stale, right_stale),
    )


def _check_the_populations_partition(
    population: Sequence[TupleOutcome],
    non_dominated: Sequence[Tuple],
    dominated: Sequence[Dominated],
    not_placed: Sequence[NotPlaced],
) -> None:
    """FR-008's identity, asserted rather than claimed in prose (014 FR-009's rule).

    ``evaluated = non_dominated + dominated + not placed``, and no candidate in two of them. It
    raises rather than returning a verdict because a population that does not partition is a
    broken pass rather than a fact about the money.
    """
    counted = len(non_dominated) + len(dominated) + len(not_placed)
    placed = {*non_dominated} | {item.key for item in dominated} | {item.key for item in not_placed}
    if counted != len(population) or len(placed) != len(population):
        raise AssertionError(
            f"{len(population)} evaluated candidate(s) sorted into {counted} place(s) across "
            f"{len(placed)} distinct key(s); the three populations must be disjoint and cover "
            "the evaluated set exactly"
        )


def _separating(
    members: Sequence[Tuple],
    population: Sequence[TupleOutcome],
    excludes: Sequence[StatedExclusion],
) -> SeparatingAssumptions | NoStatedAssumptionSeparatesThem:
    """What the set's members do not share, verbatim (FR-015, FR-019, FR-020).

    Read from ``TupleOutcome.rests_on`` and from the **section's** own exclusion records rather
    than from ``TupleOutcome.excludes``: measured, the latter is identical across every
    candidate of the owner's question while the section's differ per candidate, so a comparison
    over the outcome's fixed set would report *nothing separates them* for every set there is.

    An exclusion is compared on what it says and what would supply it, never on the candidate it
    applies to -- which is what makes two members' records comparable at all.
    """
    rests_on = {item.key: frozenset(item.rests_on) for item in population}
    stated = {
        item.key: tuple(excluded for excluded in excludes if excluded.applies_to == item.key)
        for item in population
    }
    shared_claims = _shared(members, rests_on)
    shared_exclusions = _shared(
        members, {key: frozenset(_said(item) for item in stated[key]) for key in stated}
    )
    per_member = tuple(
        MemberRestsOn(
            key=key,
            rests_on=tuple(sorted(rests_on[key] - shared_claims)),
            excludes=tuple(item for item in stated[key] if _said(item) not in shared_exclusions),
        )
        for key in members
    )
    if all(not item.rests_on and not item.excludes for item in per_member):
        return NoStatedAssumptionSeparatesThem()
    return SeparatingAssumptions(per_member=per_member)


def _shared[T](members: Sequence[Tuple], carried: Mapping[Tuple, frozenset[T]]) -> frozenset[T]:
    """What every member carries. Its complement per member is what separates them."""
    if not members:
        return frozenset()
    return frozenset.intersection(*[carried[key] for key in members])


def _said(excluded: StatedExclusion) -> tuple[str, str, str | None]:
    """One exclusion as what it says, so two members' records can be compared at all.

    ``applies_to`` is deliberately excluded: it is the candidate, and comparing on it would make
    every member's exclusions unique and report every set as separated by all of them.
    """
    return (
        excluded.what.value,
        excluded.supplied_by,
        None if excluded.direction is None else excluded.direction.value,
    )


def why_one_member(result: DominanceResult) -> WhyOneMember:
    """FR-014: why the reported set holds what it holds, against FR-008's counts.

    Derived rather than stored, on ``subject_counts``'s precedent: a count beside the list it
    counts is where the two come to disagree. Only *every other is dominated* is a finding, and
    the four cases are distinguishable without reading prose.
    """
    if len(result.non_dominated) != 1:
        return TheSetDoesNotHaveOneMember(members=len(result.non_dominated))
    dominated, not_placed = len(result.dominated), len(result.not_placed)
    if not dominated and not not_placed:
        return OnlyOneEvaluated()
    if dominated and not not_placed:
        return EveryOtherIsDominated()
    if not_placed and not dominated:  # pragma: no cover -- see below
        # **Unreachable through this pass**, measured 2026-09-06, and kept because FR-014
        # enumerates it and because the `not placed` rule is where it would become reachable.
        # It needs exactly one PLACED candidate beside a population of unplaced ones -- and a
        # candidate is placed only by a pair some objective decided, which places the other
        # member of that pair too. So one placed candidate implies a second, and the second is
        # then either dominated (a mixture) or non-dominated (a set of two).
        return EveryOtherIsNotPlaced()
    return Mixed(dominated=dominated, not_placed=not_placed)


__all__ = ["NO_ARRIVALS", "dominance", "first_unreadable", "relates", "why_one_member"]
