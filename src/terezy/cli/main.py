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
from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_never

from terezy.api.answer import AnsweredQuestion, answer_declared, answer_question
from terezy.core.decision.answer import (
    benchmark_unavailable,
    key_agreement,
    section_evaluated,
    section_ranking,
    subject_counts,
)
from terezy.core.instruments.interface import Assumptions
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.answer import (
    Answer,
    CoveredByThePlan,
    HorizonSection,
    SectionsDisagreeByKey,
    StatedExclusion,
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
    NothingNeedsToConnect,
)
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.tuple import Comparison, InstrumentPlan, TupleOutcome
from terezy.core.routes.path import (
    ComposedExit,
    DeclaredExit,
    ExitByIdentity,
    ExitChoice,
    FromTheDeclaration,
    candidate_id,
)
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
    lines.extend(_closing_lines(run, result))
    return lines


def _named_scalars(record: object) -> list[str]:
    """A refusal's own fields, named, and **only the ones a reader can read**.

    A record field is skipped rather than printed: ``BenchmarkYieldsNoCandidate`` carries the
    whole enumerated set, and a bare ``repr`` of it is thousands of characters where a sentence
    was intended. What the reader needs from a refusal is its ids, its counts and its reason.
    """
    return [
        f"    {name} = {value}"
        for name in getattr(type(record), "__slots__", ())
        if isinstance(value := getattr(record, name), str | int | float | date)
    ]


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
        f"undeclared, {counts.not_assessed} not assessed "
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
    lines.extend(f"  {line}" for line in _exclusion_lines(section.excludes))
    return lines


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
    if compared is not None:
        lines.append(_beats_line(compared, ranked))
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


def _beats_line(comparison: Comparison, ranked: tuple[TupleOutcome, ...]) -> str:
    """How the ranking stands against its hurdle, in words, above the rows.

    **``beats_benchmark`` is computed for this and was rendered nowhere.** Constitution
    Principle I requires the naive baseline to be always scored *and always shown*, and an
    empty tuple is the sentence the product exists to be able to say plainly -- *nothing beats
    the hurdle*. Derived nowhere else either: `Comparison.beats_benchmark` applies the tie
    tolerance, and a reader counting rows above the marked one would report a winner by a hair.

    **Two index spaces meet here, and mixing them is silent.** Every index on ``comparison`` --
    ``benchmark``, ``ties``, ``beats_benchmark`` -- addresses ``comparison.ranked``, while
    ``ranked`` is what ``section_ranking`` reports: the same order with every withheld
    candidate removed (010 FR-030). So each index is resolved to a *key* against
    ``comparison.ranked`` and then matched by identity, and a candidate this section refuses to
    show is not counted as having beaten anything.
    """
    hurdle = comparison.ranked[comparison.benchmark]
    reported = frozenset(item.key for item in ranked)
    beaten = sum(
        1 for index in comparison.beats_benchmark if comparison.ranked[index].key in reported
    )
    verdict = (
        f"NOTHING SHOWN HERE BEATS THE BENCHMARK {hurdle.key.instrument_id}"
        if not beaten
        else f"{beaten} of {len(ranked) - 1} beat the benchmark {hurdle.key.instrument_id}"
    )
    if any(
        hurdle.key in {comparison.ranked[index].key for index in group}
        and len({comparison.ranked[index].key for index in group} & reported) > 1
        for group in comparison.ties
    ):
        verdict += ", and at least one candidate ties with it within the project tolerance"
    return f"  {verdict}.{_span_caveat(comparison, hurdle, ranked)}"


def _span_caveat(
    comparison: Comparison, hurdle: TupleOutcome, ranked: tuple[TupleOutcome, ...]
) -> str:
    """What the verdict above is silent about when the ranked rows span different periods.

    ``implied_rate`` is an IRR over the span the money was **at work**, so a row whose own
    terms end inside the window is annualised over that shorter span rather than over the
    window. An ordering across periods of different length is a comparison of different
    questions, and the verdict above is the most confident sentence this renderer prints --
    Principle I forbids emitting one more confident than its inputs.

    **Keyed on the set, not on the hurdle.** Incomparability is a property of the spans in the
    list: a hurdle that runs to the window's end tells the reader nothing about the eleven rows
    that did not, and gating the caveat on the hurdle alone printed the bare verdict over
    exactly that table. So the rows are counted and the hurdle is named only when it is one of
    them -- and where **every** row ends inside the window there is no "rest" to contrast with,
    which is a different sentence rather than the same one read loosely.

    Stated rather than suppressed: the figures are real and the owner chose the hurdle, so
    withholding the verdict would hide work he asked for. What he cannot be left to infer is
    that the numbers span different periods. Recorded as
    ``the-hurdle-undershoots-every-horizon`` in ``specs/features.toml``; the remedy -- a
    different benchmark, or a declared rule for a candidate that undershoots -- is his.
    """
    short = [item for item in ranked if item.span.end < comparison.horizon.end]
    if not short:
        return ""
    window = comparison.horizon.end.isoformat()
    hurdle_note = (
        f" The benchmark is one of them: {hurdle.key.instrument_id}'s own terms end "
        f"{hurdle.span.end.isoformat()}."
        if hurdle in short
        else f" The benchmark is not one of them; its rate does span the window to {window}."
    )
    every = len(short) == len(ranked)
    rest = (
        " and NONE runs to it, so there is no row here measured over the window at all"
        if every
        else ", so each is annualised over its own shorter span while the rest are annualised "
        "over the window"
    )
    return (
        f" RATES HERE SPAN DIFFERENT PERIODS: {len(short)} of {len(ranked)} ranked row(s) end "
        f"before {window}{rest}. Rates measured over periods of different length are not "
        f"comparable, and the ordering above is across them.{hurdle_note}"
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
        f"    {'[BENCHMARK] ' if hurdle else ''}{outcome.key.instrument_id} "
        f"from {outcome.key.stream_id} "
        f"via {candidate_id(outcome.key.route_in)} "
        f"out {_exit_choice(outcome.key.route_out)} "
        f"run as {_plan_terms(outcome.key.exit_terms)}",
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
        case NothingNeedsToConnect():
            return reason.refusal.reason
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
