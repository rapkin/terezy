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

from terezy.api.answer import AnsweredQuestion, answer_question, inputs_of
from terezy.core.decision.answer import answer as answer_of
from terezy.core.decision.answer import (
    benchmark_unavailable,
    key_agreement,
    section_evaluated,
    section_ranking,
    subject_counts,
)
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import (
    Answer,
    CoveredByThePlan,
    HorizonSection,
    SectionsDisagreeByKey,
    SubjectReached,
    SubjectUndeclared,
    SubjectUnreached,
)
from terezy.core.results.candidates import (
    CandidateSurvey,
    NoCandidateReason,
    NothingConnects,
    NothingNeedsToConnect,
)
from terezy.data import manifest as run_manifest
from terezy.data.declarations import loader, resolver

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
FLAGS = Path("<flags>")
"""What a question built from the command line is named by when it refuses.

Not a real path, and deliberately shaped so a reader cannot mistake it for one: the refusal
still has to say *where*, and *the flags you typed* is the honest answer.
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Answer one question and print it. Returns 0 for an answer, 1 for a refusal."""
    args = _parser().parse_args(argv)
    root = Path(args.data_root)
    as_of = date.fromisoformat(args.as_of)
    run = (
        answer_question(root, args.question, as_of=as_of, base_currency=Currency.UAH)
        if args.question is not None
        else _from_flags(root, args.set, as_of=as_of)
    )
    for line in render(run):
        print(line)
    return 0 if isinstance(run.answer, Answer) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="terezy", description=__doc__)
    parser.add_argument("--data-root", default=str(REPO_ROOT / "data"))
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
    """A question built from ``--set`` lines, answered over the same registry a file would be."""
    document: dict[str, Any] = tomllib.loads("\n".join(lines))
    question = loader.question_from_document(document, FLAGS)
    declarations = resolver.answer_from_data_root(
        root, base_currency=Currency.UAH, scenario_id=None
    )
    result = answer_of(question, inputs_of(declarations, on_date=question.horizons[0].start), as_of)
    return AnsweredQuestion(
        answer=result,
        manifest=run_manifest.of_answer(
            declarations=declarations,
            question=question,
            as_of=as_of,
            result=result if isinstance(result, Answer) else None,
        ),
    )


def render(run: AnsweredQuestion) -> list[str]:
    """The whole answer as lines. Every refusal appears with the words the core wrote."""
    result = run.answer
    if not isinstance(result, Answer):
        return [
            f"the question does not stand up: {type(result).__name__}",
            *(f"  {name} = {value!r}" for name, value in _fields_of(result)),
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


def _fields_of(record: object) -> list[tuple[str, object]]:
    slots = getattr(type(record), "__slots__", ())
    return [(name, getattr(record, name)) for name in slots]


def _subject_lines(result: Answer) -> list[str]:
    lines = []
    for item in result.subjects:
        ids = getattr(item, "ids", ())
        lines.append(
            f"  {item.named}: {len(ids)} instrument(s) -- {', '.join(ids)}"
            if ids
            else f"  {item.named}: NOTHING IS DECLARED BY THAT NAME"
        )
    return lines


def _section_lines(result: Answer, section: HorizonSection) -> list[str]:
    counts = subject_counts(result, section)
    lines = [
        f"{section.horizon.start.isoformat()} to {section.horizon.end.isoformat()}",
        f"  of {counts.reached + counts.declared_but_unreached + counts.undeclared} named "
        f"subject(s): {counts.reached} reached, {counts.declared_but_unreached} declared but "
        f"unreached, {counts.undeclared} undeclared "
        f"({counts.ids_considered} instrument id(s) considered)",
        *_standing_lines(section),
    ]
    if not isinstance(section.outcome, CandidateSurvey):
        lines.append(f"  NO COMPARISON: {type(section.outcome).__name__}")
        lines.extend(f"    {value}" for _, value in _fields_of(section.outcome))
        return lines
    lines.append(f"  {len(section.outcome.enumerated.candidates)} candidate(s) enumerated")
    ranked = section_ranking(section)
    lines.append(
        f"  ranked: {len(ranked)}"
        if ranked
        else "  ranked: NOTHING. Every candidate below refuses, is withheld, or has no rate."
    )
    for outcome in ranked:
        lines.append(f"    {outcome.key.instrument_id}  reaches {outcome.reaches.amount}")
    for outcome in section_evaluated(section):
        for claim in outcome.rests_on:
            lines.append(f"    rests on ({outcome.key.instrument_id}): {claim}")
    unavailable = benchmark_unavailable(section)
    if unavailable is not None:
        lines.append(f"  NO BENCHMARK: {unavailable.reason}")
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
    return lines


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
        "excludes:",
        *(
            f"  {item.what.value}"
            + (f" ({item.applies_to.instrument_id})" if item.applies_to is not None else "")
            + f" -- would be supplied by {item.supplied_by}"
            + (f"; errs {item.direction.value}" if item.direction is not None else "")
            for item in result.excludes
        ),
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
