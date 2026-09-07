"""A thin client over ``terezy.api``: read a question, answer it, print what came back.

015 FR-020a. **It adds no fact to the record** -- no figure it computed, no verdict it inferred,
no field the record does not carry -- and a refusal reaches the reader **as a refusal with its
reason**, never as a blank, a dash, a zero or an omitted row: *a chart that cannot express "this
figure refuses to exist, and here is why" is worse than a table that can* (``docs/DIRECTION.md``).

**Flags are sugar over the file** (FR-005). ``--set`` builds the same TOML document a question
file holds and hands it to the same validator, so the CLI structurally cannot own a field the
file cannot express or a default the file cannot state: there is one loader and one set of
refusals. What is deliberately *not* a question field is ``--as-of``, which FR-006 puts on the
verb, and the segment bound and candidate ceiling, which are declared in ``data/composition/``
and ``data/candidates/`` and reach the verb through its second parameter.

``argparse`` rather than a dependency: this renders one record and builds one, and a library
installed for one subcommand is one more thing between a person and their answer.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_never

from terezy.api.answer import AnsweredQuestion, answer_declared, answer_question
from terezy.core.decision.answer import (
    benchmark_unavailable,
    key_agreement,
    section_beats_benchmark,
    section_evaluated,
    section_ranking,
    section_ties,
    subject_counts,
)
from terezy.core.decision.dominance import why_one_member
from terezy.core.instruments.cash import CashAssumptions
from terezy.core.instruments.interface import Assumptions
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.answer import (
    Answer,
    CoveredByThePlan,
    HorizonSection,
    SectionsDisagreeByKey,
    StatedExclusion,
    SubjectHeld,
    SubjectNotAssessed,
    SubjectReached,
    SubjectUndeclared,
    SubjectUnreached,
    UndeclaredSubject,
)
from terezy.core.results.candidates import (
    CandidateSurvey,
    NoCandidateReason,
    NothingConnects,
)
from terezy.core.results.dominance import (
    BenchmarkStanding,
    DeliveredInTwoCurrencies,
    DominanceResult,
    Dominated,
    EveryOtherIsDominated,
    EveryOtherIsNotPlaced,
    FigureMissing,
    HurdleIsDominated,
    IncomparablePair,
    Mixed,
    NoStatedAssumptionSeparatesThem,
    NothingDominatesTheHurdle,
    OnlyOneEvaluated,
    SeparatingAssumptions,
    TheSetDoesNotHaveOneMember,
    WhyOneMember,
)
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.held import HeldTax, InBaseCurrency, Valuation, Valued
from terezy.core.results.objectives import (
    AbsoluteBand,
    Band,
    DaysBand,
    FractionOfTheQuestionAmount,
)
from terezy.core.results.tuple import Comparison, InstrumentPlan, Tuple, TupleOutcome
from terezy.core.routes.path import (
    ComposedExit,
    DeclaredExit,
    ExitByIdentity,
    ExitChoice,
    FromTheDeclaration,
    entry_id,
)
from terezy.core.scenarios import quote_asset
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Sequence


REFUSED = 1
"""The question did not stand up. A **result**, and a different thing from a broken file."""

LOAD_FAILED = 2
"""Nothing was answered: a declaration would not load, or the question was refused before the
verb ever saw it. Distinct from :data:`REFUSED`, so a caller can tell a result from neither."""

FLAGS = Path("<flags>")
"""What a question built from the command line is named by when it refuses.

Not a real path, and deliberately shaped so a reader cannot mistake it for one: the refusal
still has to say *where*, and *the flags you typed* is the honest answer.
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Answer one question and print it.

    Returns :data:`REFUSED` where the question does not stand up, :data:`LOAD_FAILED` where
    nothing was answered at all, and zero otherwise.
    """
    args = _parser().parse_args(argv)
    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError as malformed:
        # Outside the block below, because nothing has been loaded and no declaration is at
        # fault: reporting it as a load failure would send the reader to `data/`.
        print(f"--as-of is not an ISO date: {malformed}")
        return LOAD_FAILED
    try:
        root = Path(args.data_root)
        run = (
            answer_question(root, args.question, as_of=as_of, base_currency=Currency.UAH)
            if args.question is not None
            else _from_flags(root, args.set, as_of=as_of)
        )
    except (DeclarationError, tomllib.TOMLDecodeError, ValueError) as broken:
        # A refusal reached before anything was answered, and the exit code says so: 1 is *the
        # question does not stand up as a question*, which is a result with a manifest behind
        # it. The word here is deliberately not "loaded": the same exception carries a file
        # that would not parse and a question, flags included, refused against the streams it
        # names, and telling a reader a declaration broke when none did is a false message.
        # Printing a traceback would be the one place this feature failed to reach them at all.
        print(f"nothing was answered: {broken}")
        return LOAD_FAILED
    for line in render(run):
        print(line)
    return 0 if isinstance(run.answer, Answer) else REFUSED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="terezy", description=__doc__)
    parser.add_argument(
        "--data-root",
        required=True,
        help=(
            "the directory the declarations live in. Required: the shipped data/ is not part "
            "of the installed package, so a default pointing at it would name a directory "
            "that exists only in a source checkout."
        ),
    )
    parser.add_argument(
        "--as-of",
        required=True,
        help="the date staleness is measured at. Not a question field (FR-006).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question", help="the id of a declared question under data/questions/")
    group.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="TOML",
        help=(
            "one line of the question, in the TOML a question file holds -- repeatable. "
            "Sugar over the file, validated by the same loader."
        ),
    )
    return parser


def _from_flags(root: Path, lines: Sequence[str], *, as_of: date) -> AnsweredQuestion:
    """A question built from ``--set`` lines, answered over the same registry a file would be.

    The scenario is resolved from the question's own regime, exactly as the file path does. A
    flag run that searched every corridor while the manifest recorded a narrowed world would
    assert a world the run did not search -- and *flags are sugar over the file* would be false
    in the one place it matters.
    """
    document: dict[str, Any] = tomllib.loads("\n".join(lines))
    question = loader.question_from_document(document, FLAGS)
    return answer_declared(
        question, root, as_of=as_of, base_currency=Currency.UAH, declared_in=FLAGS
    )


def render(run: AnsweredQuestion) -> list[str]:
    """The whole answer as lines. Every refusal appears with the words the core wrote."""
    result = run.answer
    if not isinstance(result, Answer):
        return [
            f"the question does not stand up: {type(result).__name__}",
            *_named_scalars(result),
            f"manifest: {run.manifest.result_digest}",
        ]
    lines = [
        f"question: {result.question.id}   as of {result.as_of.isoformat()}   "
        f"regime {result.question.regime_id}",
        "",
        "subjects:",
        *_subject_lines(result),
        "",
    ]
    for section in result.sections:
        lines.extend(_section_lines(result, section))
        lines.append("")
    lines.extend(_held_lines(result))
    lines.extend(_closing_lines(run, result))
    return lines


def _held_lines(result: Answer) -> list[str]:
    """The held section: what he already holds, beside the horizons rather than inside one.

    Empty when he has declared no lot of any held asset, and then nothing is printed -- the
    subject standing has already said he named one and declared no holding of it, and a
    section reading *held: nothing* would be a claim about his position rather than about the
    declarations (`data/README.md` rule 5).
    """
    if not result.held:
        return []
    lines = ["held (not candidates -- reported, never ranked):"]
    for position in result.held:
        lines.append(
            f"  {position.instrument_id}: {position.quantity:g} {position.quantity_unit} "
            f"at {position.venue_id}, over {len(position.lots)} lot(s)"
        )
        lines.append(f"    cost: {_readable(position.basis)}")
        lines.extend(_valuation_lines(position.valuation))
        lines.append(f"    tax: {_refusal(position.tax)}")
        lines.append(f"    yield: {position.yields.reason}")
        lines.append(f"    rank: {position.rank.reason}")
    return [*lines, ""]


def _valuation_lines(valuation: Valuation) -> list[str]:
    """What the position is worth today, or the refusal that replaced every figure at once."""
    if not isinstance(valuation, Valued):
        return [f"    value: REFUSED -- {valuation.reason}"]
    lines = [
        f"    price: {valuation.quotation.close:g} per unit, closed "
        f"{valuation.quotation.on_date.isoformat()}",
        f"    value: {_readable(valuation.value)}",
    ]
    if valuation.assumption is not None:
        lines.append(f"    assumes: {quote_asset.rests_on(valuation.assumption)}")
    if isinstance(valuation.in_base, InBaseCurrency):
        struck = valuation.in_base.struck
        lines.append(f"    value in base: {_readable(valuation.in_base.value)}")
        lines.append(f"    nominal change: {_readable(valuation.in_base.nominal_change)}")
        if struck is not None:
            lines.append(
                f"      struck at {struck.rate:g} / {struck.quotation_unit:g} "
                f"({struck.series_id}, {struck.rate_date.isoformat()})"
            )
    else:
        lines.append(f"    value in base: REFUSED -- {valuation.in_base.reason}")
    return lines


def _refusal(refused: HeldTax) -> str:
    """A held position's tax, which is always a reason and never a figure (025 FR-014)."""
    return refused.reason


def _named_scalars(record: object) -> list[str]:
    """A refusal's own fields, named, and **only the ones a reader can read**.

    A record field is skipped rather than printed: ``BenchmarkYieldsNoCandidate`` carries the
    whole enumerated set, and a bare ``repr`` of it is thousands of characters where a sentence
    was intended. What the reader needs from a refusal is its ids, its counts and its reason.

    **An ``Enum`` and a ``Money`` are readable and were not read.** 019's refusals name a
    criterion and a currency and nothing else -- ``BandInAnotherCurrency`` carries three enum
    members -- so under the narrower test they rendered as their type name and no reason at
    all, which is the silent degradation Principle IV forbids. A tuple of them is rendered the
    same way, because ``SeveralQuestionAmountsInTheCurrencyCompared`` names the streams whose
    two amounts left a band with no single width, and *which two* is the whole of the remedy.

    **A candidate key and a declared band are rendered rather than skipped.** Both are records,
    so the narrower test dropped them: ``BenchmarkWasWithheld`` exists to name *which* hurdle
    was withheld, and FR-011c's refusal has to name the band that failed beside the slack it
    did not clear. A refusal missing either sends a reader to the wrong file.
    """
    return [
        f"    {name} = {_readable(getattr(record, name))}"
        for name in getattr(type(record), "__slots__", ())
        if _is_readable(getattr(record, name))
    ]


def _is_readable(value: object) -> bool:
    """Whether a field is a figure a reader can take in, or a structure that would flood them."""
    if isinstance(value, Tuple | AbsoluteBand | FractionOfTheQuestionAmount | DaysBand):
        return True
    if isinstance(value, tuple):
        return all(_is_readable(item) for item in value)
    return isinstance(value, str | int | float | date | Enum | Money)


def _readable(value: object) -> str:
    """One such field, in the words its own type carries."""
    if isinstance(value, Tuple):
        return _candidate(value)
    if isinstance(value, AbsoluteBand | FractionOfTheQuestionAmount | DaysBand):
        return _band_words(value)
    if isinstance(value, tuple):
        return ", ".join(_readable(item) for item in value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Money):
        return f"{value.amount} {value.currency.value}"
    return str(value)


def _subject_lines(result: Answer) -> list[str]:
    """What each named word turned out to be.

    Branched on the **type** and never on whether the id list is empty: a declared group nobody
    has labelled yet resolves to no ids and is not undeclared, and collapsing the two would
    erase the distinction the group vocabulary exists to preserve (FR-008a).
    """
    lines = []
    for item in result.subjects:
        if isinstance(item, UndeclaredSubject):
            lines.append(f"  {item.named}: NOTHING IS DECLARED BY THAT NAME")
        else:
            lines.append(f"  {item.named}: {len(item.ids)} instrument(s) -- {', '.join(item.ids)}")
    return lines


def _section_lines(result: Answer, section: HorizonSection) -> list[str]:
    counts = subject_counts(result, section)
    lines = [
        f"{section.horizon.start.isoformat()} to {section.horizon.end.isoformat()}",
        f"  of {len(section.standings)} named subject(s): {counts.reached} reached, "
        f"{counts.declared_but_unreached} declared but unreached, {counts.undeclared} "
        f"undeclared, {counts.not_assessed} not assessed, {counts.held} already held "
        f"({counts.ids_considered} instrument id(s) considered)",
        *_standing_lines(section),
    ]
    if not isinstance(section.outcome, CandidateSurvey):
        lines.append(f"  NO COMPARISON: {type(section.outcome).__name__}")
        lines.extend(_named_scalars(section.outcome))
        return lines
    lines.append(f"  {len(section.outcome.enumerated.candidates)} candidate(s) enumerated")
    lines.extend(_ranking_lines(section))
    for item in section.arrives_after_horizon:
        lines.append(
            f"  WITHHELD {item.key.instrument_id}: its money arrives "
            f"{item.arrives_on.isoformat()}, after this window ends. No figure is reported for "
            "it here, and none is annotated."
        )
    for dropped in section.outcome.comparison.refused:
        lines.append(f"  DROPPED {dropped.key.instrument_id}: {dropped.refusal.reason}")
    for pair in section.outcome.enumerated.no_candidate:
        lines.append(f"  NO CANDIDATE {pair.instrument_id} from {pair.stream_id}: {_why(pair.why)}")
    lines.extend(_reserve_lines(section))
    lines.extend(_dominance_lines(section))
    lines.extend(f"  {line}" for line in _exclusion_lines(section.excludes))
    return lines


def _dominance_lines(section: HorizonSection) -> list[str]:
    """All three of FR-008's populations, and everything the core computes about them.

    019 FR-029. **All three**, because FR-014 requires *every other candidate is dominated* and
    *every other is not placed* to be distinguishable on the record, and a surface rendering two
    of three makes them indistinguishable to the one person who reads it -- which is this
    feature's own defect one level down.

    Every candidate is named by its instrument id and never by a position (FR-029a).
    """
    result = section.dominance
    if not isinstance(result, DominanceResult):
        return [
            f"  NO DOMINANCE SET: {type(result).__name__}",
            *_named_scalars(result),
        ]
    lines = [
        f"  dominance under {result.objectives.id}: {len(result.non_dominated)} "
        f"non-dominated, {len(result.dominated)} dominated, {len(result.not_placed)} not "
        f"placed, {len(result.incomparable)} incomparable pair(s)",
        *(f"    {line}" for line in _objective_lines(result)),
    ]
    lines.extend(f"    NON-DOMINATED {_candidate(key)}" for key in result.non_dominated)
    for beaten in result.dominated:
        lines.append(f"    DOMINATED {_candidate(beaten.key)}")
        lines.extend(f"      {line}" for line in _dominators(beaten))
    for unplaced in result.not_placed:
        lines.append(f"    NOT PLACED {_candidate(unplaced.key)}")
        lines.append(
            f"      every one of its {len(unplaced.every_pair)} pair(s) is incomparable, "
            "each listed below"
        )
    for pair in result.incomparable:
        lines.append(f"    INCOMPARABLE on {pair.criterion.value}: {_why_incomparable(pair)}")
        lines.append(f"      {_candidate(pair.left)}")
        lines.append(f"      {_candidate(pair.right)}")
    for close in result.indistinguishable:
        lines.append(f"    INDISTINGUISHABLE {_candidate(close.key)}")
        lines.extend(f"      from {_candidate(key)}" for key in close.neighbours)
    if result.indistinguishable:
        lines.append(
            "      -- a relation between pairs and never a group: closeness within a band "
            "does not chain, so no partition of them exists"
        )
    lines.append(f"    {_hurdle_line(result.benchmark_standing)}")
    if isinstance(result.benchmark_standing, HurdleIsDominated):
        lines.extend(
            f"      by {_candidate(verdict.dominates)}" for verdict in result.benchmark_standing.by
        )
    if result.non_dominated:
        # An empty set has no members to be separated by anything, and the record's
        # *they rest on the same stated assumptions* is a claim about a population that is not
        # there. The line below says the set is empty instead.
        lines.extend(f"    {line}" for line in _separating_lines(result.separating))
    lines.append(f"    {_one_member_line(why_one_member(result))}")
    return lines


def _objective_lines(result: DominanceResult) -> list[str]:
    """The whole declared set beside every population it counts (FR-023).

    A fraction is printed with **the width it resolved to**, because a fraction reported without
    its width is a band nobody can check against a figure.
    """
    widths = {(band.criterion, band.currency): band for band in result.resolved_bands}
    lines = []
    for objective in result.objectives.objectives:
        resolved = [
            f"{band.width.amount} {band.currency.value} of {band.from_amount.amount} "
            f"{band.currency.value}"
            for (criterion, _), band in sorted(widths.items(), key=lambda item: item[0][1].value)
            if criterion is objective.criterion
        ]
        lines.append(
            f"objective {objective.criterion.value} {objective.direction.value}, band "
            f"{_band_words(objective.band)}" + (f" = {'; '.join(resolved)}" if resolved else "")
        )
    return lines


def _band_words(band: Band) -> str:
    """One declared band in the shape it was declared in, never converted into another."""
    match band:
        case AbsoluteBand():
            return f"{band.amount.amount} {band.amount.currency.value}"
        case FractionOfTheQuestionAmount():
            return f"{band.proportion} of the question's amount"
        case DaysBand():
            return f"{band.days} day(s)"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(band)


def _dominators(item: Dominated) -> list[str]:
    """Every candidate that dominates this one, with the objectives each was strictly better on.

    The **weak** half is not printed per dominator, and its absence is deliberate: by FR-007's
    definition it holds on every declared objective, so printing it beside each of twenty
    dominators is one sentence repeated twenty times. It is on the verdict record, where a
    reader of one verdict finds it without the rule in hand.

    One dominator per line, because a candidate is five terms and a run of them on one line is
    a row nobody can read to its end.
    """
    return [
        f"by {_candidate(verdict.dominates)}, strictly better on "
        + ", ".join(criterion.value for criterion in verdict.strictly_better_on)
        for verdict in item.dominated_by
    ]


def _why_incomparable(pair: IncomparablePair) -> str:
    """What made one pair undecidable, in the terms the record carries."""
    match pair.why:
        case FigureMissing():
            return f"no figure at {pair.why.what}"
        case DeliveredInTwoCurrencies():
            return (
                f"delivered in {pair.why.left_currency.value} against "
                f"{pair.why.right_currency.value}, and no exchange rate is consulted"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(pair.why)


def _hurdle_line(standing: BenchmarkStanding) -> str:
    """Where the hurdle sits in the partial order.

    *Nothing dominates the hurdle* is never rendered as *the hurdle is best*: other members may
    sit beside it in the set, and a hurdle that dominates everything is a stronger fact.
    """
    match standing:
        case NothingDominatesTheHurdle():
            return f"NOTHING DOMINATES THE HURDLE {_candidate(standing.key)}"
        case HurdleIsDominated():
            return (
                f"THE HURDLE IS DOMINATED, by {len(standing.by)} of them: "
                f"{_candidate(standing.key)}"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(standing)


def _separating_lines(
    separating: SeparatingAssumptions | NoStatedAssumptionSeparatesThem,
) -> list[str]:
    """What the members of the set do not share, in the words the core records carry.

    It does **not** say which assumption decides between them: that needs a re-evaluation under
    a changed assumption, which this feature deliberately does not perform.
    """
    if isinstance(separating, NoStatedAssumptionSeparatesThem):
        return ["the members rest on the same stated assumptions; none separates them"]
    lines = ["what the members do not share (which of them decides is NOT tested):"]
    for member in separating.per_member:
        carried = [*member.rests_on, *(item.what.value for item in member.excludes)]
        lines.append(f"  {_candidate(member.key)}")
        lines.extend(
            f"    {claim}" for claim in (carried or ["nothing the others do not also carry"])
        )
    return lines


def _one_member_line(reading: WhyOneMember) -> str:
    """FR-014: where the set has one member, why -- and only one of the cases is a finding."""
    match reading:
        case TheSetDoesNotHaveOneMember() if not reading.members:
            return (
                "THE SET IS EMPTY: no candidate is non-dominated, because none of them could "
                "be placed at all -- see the NOT PLACED rows above"
            )
        case TheSetDoesNotHaveOneMember():
            return f"{reading.members} candidate(s) in the set; none is presented ahead of another"
        case OnlyOneEvaluated():
            return "one member because this section evaluated ONE candidate, which is not a win"
        case EveryOtherIsDominated():
            return "one member because every other evaluated candidate is dominated"
        case EveryOtherIsNotPlaced():
            return "one member because every other evaluated candidate is NOT PLACED"
        case Mixed():
            return (
                f"one member: {reading.dominated} other(s) dominated and "
                f"{reading.not_placed} not placed"
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(reading)


def _ranking_lines(section: HorizonSection) -> list[str]:
    """The figures this section computed, ordered where there was a hurdle to order them by.

    **Every scored candidate is printed, ranked or not.** A candidate that produced a complete
    outcome carrying no rate still cost the run a full projection, and its ``rests on`` lines
    print below regardless; dropping its figure would leave an assumption attached to a number
    the reader was never shown.
    """
    ranked = section_ranking(section)
    scored = section_evaluated(section)
    survey = section.outcome
    comparison = survey.comparison if isinstance(survey, CandidateSurvey) else None
    compared = comparison if isinstance(comparison, Comparison) and ranked else None
    lines = [
        f"  ranked: {len(ranked)}"
        if ranked
        else "  ranked: NOTHING. There is no benchmark to rank against, so the figures below "
        "are reported unranked rather than ordered."
    ]
    hurdle = None if compared is None else compared.ranked[compared.benchmark].key
    ties = section_ties(section)
    if compared is not None:
        lines.append(_beats_line(compared, ranked, section_beats_benchmark(section), ties))
        # Inside the guard, not beside it: the tie groups are read off the very ranking the
        # branch above refuses to show when there is no hurdle to rank against, and printing
        # them there would put the ordering back in front of a reader one line later.
        lines.extend(_tie_lines(ties))
    for outcome in ranked:
        lines.extend(_figure_lines(outcome, hurdle=outcome.key == hurdle))
    for outcome in scored:
        if outcome not in ranked:
            lines.extend([*_figure_lines(outcome), "      NOT RANKED"])
    for outcome in scored:
        lines.extend(
            f"    rests on ({outcome.key.instrument_id}): {claim}" for claim in outcome.rests_on
        )
    unavailable = benchmark_unavailable(section)
    if unavailable is not None:
        lines.append(f"  NO BENCHMARK: {unavailable.reason}")
    elif not ranked and scored:
        lines.append(
            "  NO BENCHMARK: the named benchmark's own money arrives after this window, so it "
            "is withheld like any other candidate -- and a ranking with no hurdle in it "
            "invites its own head to be read as a winner."
        )
    return lines


ONE_SPAN = 1
"""How many distinct span lengths a ranking must have for its rates to be comparable."""


def _beats_line(
    comparison: Comparison,
    ranked: tuple[TupleOutcome, ...],
    beats: Sequence[Tuple],
    ties: Sequence[Sequence[Tuple]],
) -> str:
    """How the ranking stands against its hurdle, in words, above the rows.

    **``beats_benchmark`` is computed for this and was rendered nowhere.** Constitution
    Principle I requires the naive baseline to be always scored *and always shown*, and an
    empty tuple is the sentence the product exists to be able to say plainly -- *nothing beats
    the hurdle*. Derived nowhere else either: `Comparison.beats_benchmark` applies the tie
    tolerance, and a reader counting rows above the marked one would report a winner by a hair.

    **Two index spaces meet here, and mixing them is silent.** Every index on ``comparison`` --
    ``benchmark``, ``ties``, ``beats_benchmark`` -- addresses ``comparison.ranked``, while
    ``ranked`` is what ``section_ranking`` reports: the same order with every withheld candidate
    removed (010 FR-030). ``section_beats_benchmark`` and ``section_ties`` do that resolution,
    in the core, and this takes their output rather than an index (019 FR-029a).

    ``ranked`` must hold the hurdle, which is the caller's to guarantee: ``section_ranking``
    returns ``()`` when the benchmark is withheld, so a verdict is never asked for over a table
    the hurdle is missing from. Violating it is a programmer error and raises, because every
    sentence below asserts something about rows that would not be there.
    """
    hurdle = comparison.ranked[comparison.benchmark]
    reported = frozenset(item.key for item in ranked)
    if hurdle.key not in reported:
        raise AssertionError(
            f"a verdict was asked for over a ranking that does not show its own hurdle "
            f"{hurdle.key.instrument_id!r}; section_ranking returns () in that case"
        )
    beaten = len(beats)
    others = len(ranked) - 1
    if not others:
        verdict = (
            f"THE BENCHMARK {hurdle.key.instrument_id} IS THE ONLY ROW HERE, so nothing was "
            "measured against it"
        )
    elif not beaten:
        verdict = f"NOTHING SHOWN HERE BEATS THE BENCHMARK {hurdle.key.instrument_id}"
    else:
        verdict = (
            f"{beaten} of the {others} other row(s) beat the benchmark {hurdle.key.instrument_id}"
        )
    if any(hurdle.key in group for group in ties):
        verdict += ", and at least one candidate ties with it within the project tolerance"
    return f"  {verdict}.{_span_caveat(comparison, hurdle, ranked)}"


def _tie_lines(ties: Sequence[Sequence[Tuple]]) -> list[str]:
    """Which candidates tie with which, by id.

    **Computed by the core since 010 and rendered nowhere until now** (019 FR-029). A ranking
    printed without its tie groups is the machinery that keeps the head of a tied group from
    reading as a winner, computed and withheld from the only person who reads it.
    """
    lines = []
    for group in ties:
        lines.append("  TIED within the project tolerance, in no order:")
        lines.extend(f"    {_candidate(key)}" for key in group)
    return lines


def _span_caveat(
    comparison: Comparison, hurdle: TupleOutcome, ranked: tuple[TupleOutcome, ...]
) -> str:
    """What the verdict above is silent about when the ranked rows span different periods.

    ``implied_rate`` is an IRR over the span the money was **at work**, and that span is not
    the window: a row whose own terms end inside it is measured over less, and one sold at the
    window's end is measured over the window plus the way out's latency, because waiting is
    inside the span (010 FR-015). An ordering across spans of different length compares
    different questions, and the verdict above is the most confident sentence this renderer
    prints -- Principle I forbids emitting one more confident than its inputs.

    **Keyed on whether the spans differ, and on nothing narrower.** Two earlier versions of
    this guard keyed on the hurdle undershooting and then on any row undershooting; both went
    quiet on tables that are just as incomparable -- a same-day corridor beside a three-day one
    puts two span lengths in one ranking with nothing ending inside the window at all. The
    comparable claim is that every row was measured over the same number of days, so that is
    what is tested.

    **``span.end`` is when the money is home, not when the paper's terms end.** It carries the
    exit route's latency, so naming it as the issue's own last payment date puts the reader
    three days out against the declaration they would check it against.

    Stated rather than suppressed: the figures are real and the owner chose the hurdle, so
    withholding the verdict would hide work he asked for. What he cannot be left to infer is
    that the numbers span different periods. Recorded as
    ``rates-in-one-ranking-span-different-periods`` in ``specs/features.toml``; the remedy -- a
    different benchmark, or a declared rule for a candidate that undershoots -- is his.
    """
    lengths = {(item.span.end - item.span.start).days for item in ranked}
    if len(lengths) == ONE_SPAN:
        return ""
    window = (comparison.horizon.end - comparison.horizon.start).days
    hurdle_days = (hurdle.span.end - hurdle.span.start).days
    return (
        f" RATES HERE SPAN DIFFERENT PERIODS: these {len(ranked)} rows were measured over "
        f"spans of {min(lengths)} to {max(lengths)} days against a window of {window}, and "
        "each rate is annualised over its own span. Rates measured over periods of different "
        "length are not comparable, and the ordering below is across them. The benchmark's "
        f"span is {hurdle_days} days, its money home {hurdle.span.end.isoformat()}."
    )


def _candidate(key: Tuple) -> str:
    """One candidate, by **all five** of 010's declared terms.

    That is what makes two rows different rows, and an id alone renders them identically: one
    instrument bought over two ways in, funded from two streams, or run to maturity against sold
    at the window's end is two options. A question may also state several plans for one
    instrument -- the shipped one states two that differ in their exit date -- so the plan's own
    choices are printed rather than the name of its record.
    """
    return (
        f"{key.instrument_id} from {key.stream_id} "
        f"via {entry_id(key.route_in)} "
        f"out {_exit_choice(key.route_out)} "
        f"run as {_plan_terms(key.exit_terms)}"
    )


def _figure_lines(outcome: TupleOutcome, *, hurdle: bool = False) -> list[str]:
    """One candidate's figures, with the currency, the rate and the terms that identify it.

    ``hurdle`` marks the benchmark's own row. Unmarked, the head of the list reads as the
    winner even when it is the thing everything else is measured against -- which is the trap
    the empty-ranking branch above already names, and it does not stop being a trap because
    the ranking is non-empty.

    All **five** terms of 010's key, because that is what makes two rows different rows: one
    instrument bought over two ways in, or run to maturity against sold at the window's end, is
    two options, and printing an id alone renders them identically. The currency, because the
    owner has two streams and a bare number in an ordered list is the Principle VI conflation
    ``Money`` exists to prevent.

    ``exit_terms`` prints every choice the plan states, not the name of its record: a question
    may state several plans for one instrument, and two that differ only in the exit date would
    otherwise be two figures under one identical line.
    """
    rate = outcome.implied_rate
    return [
        f"    {'[BENCHMARK] ' if hurdle else ''}{_candidate(outcome.key)}",
        f"      reaches {outcome.reaches.amount} {outcome.reaches.currency.value}"
        + (
            f"; rate {rate.value}" if isinstance(rate, NominalRate) else f"; NO RATE: {rate.reason}"
        ),
    ]


def _plan_terms(plan: InstrumentPlan) -> str:
    """How the holding is run, in the words the question stated it in.

    Rendered here rather than through ``canonical.of_plan``, which exists to be **hashed**: it
    states every choice this does, but it renders a date as a tuple and a rate as
    ``float.hex()``, and nobody reads ``0x1.0000000000000p-2`` as a quarter. Each rendering has
    a per-field walk of its own
    -- this one's in ``tests/contract/test_cli_is_sugar_over_the_file.py``, the digest's in
    ``tests/unit/test_results_canonical.py`` -- because one walk can only see the function it
    calls, and the failure to catch is either of them quietly dropping a field.
    """
    match plan:
        case Assumptions():
            return f"{plan.consumption_method}/{plan.coupon_policy}"
        case FundAssumptions():
            point, rate = plan.yield_point, plan.exchange_rate
            return "/".join(
                [
                    plan.consumption_method,
                    plan.liquidity_mode,
                    f"buyback {plan.buyback}",
                    "no exit date" if plan.exit_on is None else f"exit {plan.exit_on.isoformat()}",
                    "no yield point" if point is None else f"yield {point.rate}",
                    "no stated rate" if rate is None else f"rate {rate.uah_per_unit}",
                ]
            )
        case CashAssumptions():
            return "nothing to choose"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(plan)


def _exit_choice(choice: ExitChoice) -> str:
    """The way out of the venue: its declared ids, or the instruction standing in for one.

    Matched on the member rather than on the segments being empty. *The destination is already
    spendable* and *a chain that charged nothing* are the distinction ``ExitByIdentity`` exists
    to make, and only the value itself says which; a truthiness fallback would print one under
    the other's name.
    """
    match choice:
        case FromTheDeclaration():
            return choice.value
        case ExitByIdentity():
            return choice.value
        case DeclaredExit():
            return choice.route_id
        case ComposedExit():
            return "+".join(choice.segments)
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(choice)


def _standing_lines(section: HorizonSection) -> list[str]:
    lines = []
    for standing in section.standings:
        match standing:
            case SubjectReached():
                lines.append(
                    f"    {standing.named}: reached "
                    f"({len(standing.with_candidates)} of {len(standing.ids)})"
                )
            case SubjectUnreached():
                lines.append(
                    f"    {standing.named}: declared but unreached. The remedy is a corridor."
                )
            case SubjectUndeclared():
                lines.append(f"    {standing.named}: undeclared. The remedy is a declaration.")
            case SubjectNotAssessed():
                lines.append(
                    f"    {standing.named}: not assessed -- this section refused before it "
                    "enumerated anything."
                )
            case SubjectHeld():
                lines.append(
                    f"    {standing.named}: already held ({len(standing.held)} of "
                    f"{len(standing.ids)}). Reported below, never ranked."
                    if standing.held
                    else f"    {standing.named}: a held asset, and no lot of it is declared "
                    "here. The remedy is a lot under the private overlay."
                )
    return lines


def _reserve_lines(section: HorizonSection) -> list[str]:
    lines = []
    for verdict in section.reserves:
        if isinstance(verdict, CoveredByThePlan):
            lines.append(
                f"  RESERVE {verdict.key.instrument_id}: covered by the plan on "
                f"{verdict.covered_on.isoformat()}"
            )
        else:
            lines.append(
                f"  RESERVE {verdict.key.instrument_id}: a partial exit would be needed, and a "
                f"partly-liquidated holding is not projected. Short by "
                f"{verdict.short_by.amount} {verdict.short_by.currency.value}."
            )
    return lines


def _exclusion_lines(excludes: Sequence[StatedExclusion]) -> list[str]:
    """One line per stated exclusion, saying what would supply it and which way it errs."""
    return [
        f"EXCLUDES {item.what.value}"
        + (f" ({item.applies_to.instrument_id})" if item.applies_to is not None else "")
        + f" -- would be supplied by {item.supplied_by}"
        + (f"; errs {item.direction.value}" if item.direction is not None else "")
        for item in excludes
    ]


def _why(reason: NoCandidateReason) -> str:
    """A no-candidate pair's reason, in compose's own words, carried verbatim (FR-011)."""
    match reason:
        case NothingConnects():
            return reason.reason
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(reason)


def _closing_lines(run: AnsweredQuestion, result: Answer) -> list[str]:
    agreement = key_agreement(result)
    return [
        "excludes (every figure above):",
        *(f"  {line}" for line in _exclusion_lines(result.excludes)),
        "",
        (
            f"the sections enumerated different candidates: {sorted(agreement.only_in)}"
            if isinstance(agreement, SectionsDisagreeByKey)
            else "every section enumerated the same candidates"
        ),
        f"manifest: {len(run.manifest.inputs)} input file(s), digest {run.manifest.result_digest}",
        f"unverified sources behind the figures: {len(run.manifest.unverified_sources)}",
    ]


if __name__ == "__main__":  # pragma: no cover -- the console script calls main()
    sys.exit(main())
