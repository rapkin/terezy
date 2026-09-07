"""The CLI builds the same record, and prints every refusal with the words the core wrote.

015 SC-019 and SC-022. Two claims, and the first is **structural rather than scanned**: the CLI
builds a TOML document and hands it to ``loader.question_from_document``, which is the function
``question_from_file`` also calls. There is one validator and one set of refusals, so the CLI
cannot own a field the file cannot express or a default the file cannot state -- and the scan
below asserts exactly that shape rather than trying to enumerate flags.

The second claim is about the reader: *a chart that cannot express "this figure refuses to
exist, and here is why" is worse than a table that can*. Every one of the three sections of the
owner's answer is a refusal, so the rendering is asserted by finding each refusal's own reason
string in the output -- no blank, no dash, no zero, no omitted row.
"""

from __future__ import annotations

import ast
import dataclasses
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from terezy.api.answer import AnsweredQuestion, answer_question
from terezy.cli import main as cli
from terezy.core.decision.answer import (
    benchmark_unavailable,
    section_beats_benchmark,
    section_ranking,
    section_ties,
)
from terezy.core.instruments.groups import InstrumentGroup
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import canonical
from terezy.core.results import dominance as dominance_records
from terezy.core.results.answer import Answer, HorizonSection
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.dominance import DominanceRefused, DominanceResult
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.objectives import (
    AbsoluteBand,
    Criterion,
    DaysBand,
    FractionOfTheQuestionAmount,
)
from terezy.core.results.tuple import Comparison, InstrumentPlan, Tuple, TupleOutcome
from terezy.data.declarations import loader
from tests import answer_registries as fixtures
from tests import dominance_sections, synthetic

pytestmark = pytest.mark.contract

CLI_SOURCE = Path(cli.__file__)

NOT_QUESTION_FIELDS = ("--as-of", "--data-root")
"""The values that are deliberately not question fields, exempted **by name** (SC-019).

``--as-of`` is on the verb because it decides staleness and nothing else (FR-006); the data root
is where the declarations live. The segment bound and the candidate ceiling are declared in
``data/composition/`` and ``data/candidates/`` and reach the verb through its second parameter,
which is why the CLI has no flag for either. An unscoped scan fails on all of these and would
push them into the question file, which is the opposite of what FR-006 decided.
"""


def _run() -> tuple[list[str], int]:
    answered = answer_question(
        fixtures.SHIPPED_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
    return cli.render(answered), 0


def _rebenchmarked(instrument_id: str) -> str:
    """The owner's own question document, measured against a different issue."""
    document = fixtures.QUESTION_FILE.read_text(encoding="utf-8")
    replaced = document.replace(
        f'benchmark    = "{fixtures.BENCHMARK}"', f'benchmark    = "{instrument_id}"', 1
    )
    assert replaced != document, "the question file no longer names the benchmark it did"
    return replaced


def _unranked() -> AnsweredQuestion:
    """The same question measured against the fund that refuses on its own terms.

    ``inzhur_reit`` produces no outcome at any horizon, so every section reaches
    ``BenchmarkUnavailable`` -- 010 FR-011 will not offer a list whose head would read as a
    winner. The two tests below are about how the CLI *renders* that, and over the shipped
    registry every bond is priced both ways, so a refusing benchmark is where it comes from.
    """
    return cli._from_flags(
        fixtures.SHIPPED_ROOT, [_rebenchmarked(fixtures.REIT)], as_of=fixtures.AS_OF
    )


def _declared_flags() -> set[str]:
    """Every ``--flag`` the parser declares, read off the source rather than from the docstring."""
    tree = ast.parse(CLI_SOURCE.read_text(encoding="utf-8"))
    return {
        node.value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_argument"
        for node in call.args
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_the_cli_declares_no_question_field_of_its_own() -> None:
    """SC-019's scan. The only flags are the question to ask and the two exempted values."""
    assert _declared_flags() == {"--question", "--set", *NOT_QUESTION_FIELDS}


def test_it_builds_a_question_through_the_same_loader_the_file_goes_through() -> None:
    """The structural half: one validator, so a CLI-only field is unrepresentable.

    Asserted over the syntax tree rather than over the text, because a substring search for
    ``Question(`` also finds ``AnsweredQuestion(`` -- a test that passes for the wrong reason
    and, worse, one that would fail for the right code.
    """
    tree = ast.parse(CLI_SOURCE.read_text(encoding="utf-8"))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
    }
    assert "question_from_document" in called
    assert "Question" not in called, "the CLI must not construct the record itself"


def test_flags_produce_a_record_equal_to_the_one_the_file_produces(tmp_path: Path) -> None:
    """SC-019's first half, field for field."""
    document = fixtures.QUESTION_FILE.read_text(encoding="utf-8")
    built = cli._from_flags(fixtures.SHIPPED_ROOT, [document], as_of=fixtures.AS_OF)
    loaded = answer_question(
        fixtures.SHIPPED_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
    assert isinstance(built.answer, Answer)
    assert isinstance(loaded.answer, Answer)
    assert built.answer.question == loaded.answer.question
    assert built.answer == loaded.answer


def test_every_sections_refusal_reaches_the_reader_with_its_own_reason() -> None:
    """SC-022. Asserted by finding each reason string in the output, byte for byte."""
    answered = _unranked()
    assert isinstance(answered.answer, Answer)
    output = "\n".join(cli.render(answered))
    for section in answered.answer.sections:
        assert isinstance(section.outcome, CandidateSurvey)
        unavailable = benchmark_unavailable(section)
        assert unavailable is not None
        assert unavailable.reason in output
        for dropped in section.outcome.comparison.refused:
            assert dropped.refusal.reason in output
        for pair in section.outcome.enumerated.no_candidate:
            assert cli._why(pair.why) in output


def test_a_withheld_candidate_is_named_rather_than_omitted() -> None:
    """FR-030's rendering: the reader is told the figure is not shown, and why."""
    lines, _ = _run()
    output = "\n".join(lines)
    assert fixtures.MILTECH in output
    assert "2028-01-20" in output
    assert "none is annotated" in output


def test_no_ranking_is_rendered_as_a_sentence_rather_than_as_an_empty_table() -> None:
    """A blank where a ranking would be is the failure this project exists to prevent."""
    assert any("ranked: NOTHING" in line for line in cli.render(_unranked()))


def test_a_ranking_marks_its_own_hurdle_and_says_what_beat_it() -> None:
    """Principle I: the naive baseline is always scored **and always shown**.

    The head of a ranked list reads as the winner whether or not it is one, and the hurdle is
    somewhere in the list rather than beside it -- 14th of 24 at one month and last at twelve,
    where every shown row beats it. Both halves are asserted: the row is marked, and
    ``beats_benchmark`` -- computed for exactly this and rendered nowhere before -- reaches the
    reader as a sentence rather than as rows to count off.
    """
    lines, _ = _run()
    output = "\n".join(lines)
    sections = [
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    ]
    marked = [line for line in lines if "[BENCHMARK]" in line]
    assert len(marked) == len(sections)
    assert all(fixtures.BENCHMARK in line for line in marked)

    for section in sections:
        assert isinstance(section.outcome, CandidateSurvey)
        comparison = section.outcome.comparison
        assert isinstance(comparison, Comparison)
        ranked = section_ranking(section)
        shown = {item.key for item in ranked}
        beaten = sum(1 for i in comparison.beats_benchmark if comparison.ranked[i].key in shown)
        expected = (
            f"NOTHING SHOWN HERE BEATS THE BENCHMARK {fixtures.BENCHMARK}."
            if not beaten
            else (
                f"{beaten} of the {len(ranked) - 1} other row(s) beat the benchmark "
                f"{fixtures.BENCHMARK}."
            )
        )
        assert expected in output, expected


def _answered() -> Answer:
    """The owner's answer over what ships, asserted to be one."""
    run = answer_question(
        fixtures.SHIPPED_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
    assert isinstance(run.answer, Answer), run.answer
    return run.answer


def test_a_section_whose_rows_span_different_periods_says_so() -> None:
    """Principle I: the verdict is the most confident sentence this renderer prints.

    ``implied_rate`` annualises over the span the money was at work, so an ordering across
    rows measured over different numbers of days compares different questions. The caveat is
    keyed on **the set of span lengths** and on nothing narrower: keying it on the hurdle, or
    on any row ending inside the window, goes quiet on tables that are just as incomparable.
    """
    lines, _ = _run()
    verdicts = [
        line
        for line in lines
        if any(mark in line for mark in ("beat the benchmark", "NOTHING SHOWN HERE", "ONLY ROW"))
    ]
    sections = [
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    ]
    assert len(verdicts) == len(sections)
    for section, verdict in zip(sections, verdicts, strict=True):
        assert isinstance(section.outcome, CandidateSurvey)
        comparison = section.outcome.comparison
        assert isinstance(comparison, Comparison)
        ranked = section_ranking(section)
        lengths = {(item.span.end - item.span.start).days for item in ranked}
        assert len(lengths) > 1, "every one of his horizons ranks rows of differing spans"

        window = (section.horizon.end - section.horizon.start).days
        assert "RATES HERE SPAN DIFFERENT PERIODS" in verdict, verdict
        assert f"spans of {min(lengths)} to {max(lengths)} days against a window of {window}" in (
            verdict
        ), verdict

        # The hurdle's own span, named: a reader comparing it against the declaration checks
        # the date the money is home, not the date the paper's terms end.
        hurdle = comparison.ranked[comparison.benchmark]
        assert f"The benchmark's span is {(hurdle.span.end - hurdle.span.start).days} days" in (
            verdict
        )
        assert hurdle.span.end.isoformat() in verdict


def test_a_ranking_holding_only_the_hurdle_says_so_rather_than_claiming_a_result() -> None:
    """ "Nothing beats it" over a table of one is a finding-shaped sentence about no finding.

    It is the `[BENCHMARK]` marker's own trap arriving from the other side: a lone row reads
    as a result when the fact is that nothing was measured against it.
    """
    section = next(
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    )
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    hurdle = comparison.ranked[comparison.benchmark]

    alone = replace(comparison, ranked=(hurdle,), benchmark=0, ties=(), beats_benchmark=())
    line = cli._beats_line(alone, (hurdle,), (), ())
    assert f"THE BENCHMARK {fixtures.BENCHMARK} IS THE ONLY ROW HERE" in line
    assert "nothing was measured against it" in line
    assert "BEATS" not in line, "a verdict about beating needs something to beat"


def test_a_verdict_over_a_ranking_without_its_hurdle_is_refused() -> None:
    """The precondition `section_ranking` upholds, asserted rather than assumed.

    Every sentence the verdict prints is about rows relative to the hurdle, so a table the
    hurdle is missing from would have it describing rows that are not there.
    """
    section = next(
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    )
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    hurdle = comparison.ranked[comparison.benchmark]
    without = tuple(item for item in section_ranking(section) if item.key != hurdle.key)

    with pytest.raises(AssertionError, match="does not show its own hurdle"):
        cli._beats_line(
            comparison, without, section_beats_benchmark(section), section_ties(section)
        )


def test_the_caveat_is_silent_when_every_row_runs_to_the_window() -> None:
    """No caveat where there is nothing to caution about -- otherwise it is noise and unread.

    The ``Comparison`` is rebuilt around the printed rows rather than edited in place: its
    ``benchmark`` indexes ``comparison.ranked``, which carries the withheld candidate too, so
    swapping in the filtered tuple and keeping the index resolves a different bond as the
    hurdle -- the very mix-up the marker exists to prevent, committed by its own test.
    """
    section = next(
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    )
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    ranked = section_ranking(section)
    hurdle = comparison.ranked[comparison.benchmark].key

    to_the_end = tuple(
        replace(item, span=replace(item.span, end=comparison.horizon.end)) for item in ranked
    )
    squared = replace(
        comparison,
        ranked=to_the_end,
        benchmark=next(i for i, item in enumerate(to_the_end) if item.key == hurdle),
        ties=(),
        beats_benchmark=(),
    )
    assert squared.ranked[squared.benchmark].key == hurdle, "the rebuild must keep the hurdle"
    assert len({(i.span.end - i.span.start).days for i in to_the_end}) == 1, (
        "the fixture must actually square every span, or the silence proves nothing"
    )
    assert "RATES HERE SPAN DIFFERENT PERIODS" not in cli._beats_line(squared, to_the_end, (), ())


def test_a_tie_with_the_hurdle_is_claimed_only_when_a_printed_row_ties() -> None:
    """A tie group whose only other member is withheld is not a tie the reader can see.

    The same two index spaces as the count beside it: ``Comparison.ties`` addresses
    ``comparison.ranked``, the rows come from ``section_ranking``. The resolution is
    ``section_ties``' since 019, so the group is planted on a **section** and read back through
    it -- asserted by construction rather than by the shipped data, which has no tie today, so
    the guard would otherwise be unreachable and untested.
    """
    section = next(
        section for section in _answered().sections if isinstance(section.outcome, CandidateSurvey)
    )
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    ranked = section_ranking(section)
    withheld = next(
        index
        for index, item in enumerate(comparison.ranked)
        if item.key not in {shown.key for shown in ranked}
    )
    only_withheld = _with_ties(section, ((comparison.benchmark, withheld),))
    assert section_ties(only_withheld) == ()
    assert "ties with it" not in cli._beats_line(
        comparison, ranked, section_beats_benchmark(only_withheld), section_ties(only_withheld)
    )

    shown = next(
        index
        for index, item in enumerate(comparison.ranked)
        if index != comparison.benchmark and item.key in {row.key for row in ranked}
    )
    printed = _with_ties(section, ((comparison.benchmark, shown),))
    assert len(section_ties(printed)) == 1
    assert "ties with it" in cli._beats_line(
        comparison, ranked, section_beats_benchmark(printed), section_ties(printed)
    )


def _with_ties(section: HorizonSection, ties: tuple[tuple[int, ...], ...]) -> HorizonSection:
    """The same section with a planted tie group, indices and all."""
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    return replace(
        section,
        outcome=replace(section.outcome, comparison=replace(comparison, ties=ties)),
    )


BELOW_A_WITHHELD_CANDIDATE = "UA4000238281"
"""A benchmark that `inzhur_miltech` outranks, so the two index spaces disagree about it.

`Comparison.benchmark`, `ties` and `beats_benchmark` index `comparison.ranked`; the rows the
CLI prints are `section_ranking`, which is that tuple with every withheld candidate removed
(FR-030). The owner's own benchmark outranks the one withheld candidate at all three horizons,
so under it the two spaces agree by luck and every mix-up passes. This one does not.
"""


def test_the_hurdle_is_marked_by_identity_and_not_by_position() -> None:
    """A withheld candidate above the benchmark must not shift the marker or the count.

    Reached through the CLI rather than asserted on the record, because the mix-up is a
    rendering bug: the record is right and the printed hurdle was a different instrument.
    """
    document = _rebenchmarked(BELOW_A_WITHHELD_CANDIDATE)
    answered = cli._from_flags(fixtures.SHIPPED_ROOT, [document], as_of=fixtures.AS_OF)
    assert isinstance(answered.answer, Answer)
    lines = cli.render(answered)

    marked = [line for line in lines if "[BENCHMARK]" in line]
    verdicts = [
        line
        for line in lines
        if any(mark in line for mark in ("beat the benchmark", "NOTHING SHOWN HERE", "ONLY ROW"))
    ]
    assert marked, "the ranking prints no hurdle at all"
    assert len(verdicts) == len(marked)
    assert all(BELOW_A_WITHHELD_CANDIDATE in line for line in marked), marked
    assert all(BELOW_A_WITHHELD_CANDIDATE in line for line in verdicts), verdicts

    # And the count is over the rows the section actually prints: `inzhur_miltech` beats this
    # benchmark on the record and is withheld, so counting it would give a total the reader
    # cannot reconcile with the rows -- while two lines below, the same section says no figure
    # for it is reported.
    for section, verdict in zip(answered.answer.sections, verdicts, strict=True):
        assert isinstance(section.outcome, CandidateSurvey)
        comparison = section.outcome.comparison
        assert isinstance(comparison, Comparison)
        shown = {item.key for item in section_ranking(section)}
        beaten = sum(1 for i in comparison.beats_benchmark if comparison.ranked[i].key in shown)
        withheld = {item.key for item in section.arrives_after_horizon}
        assert any(comparison.ranked[i].key in withheld for i in comparison.beats_benchmark), (
            "the fixture must actually place a withheld candidate above the benchmark"
        )
        assert f"{beaten} of the {len(shown) - 1} other row(s) beat the benchmark" in verdict, (
            verdict
        )


def test_a_held_subject_is_printed_as_held_and_never_as_a_missing_corridor() -> None:
    """025 FR-029. Every word of his question now resolves, and `btc` resolves to a holding.

    The sentence a corridor would be the remedy for is the one this asserts is absent: `btc`
    reaches no candidate and never will, so printing *declared but unreached* would send him
    to `data/routes/` for a thing he already owns.
    """
    lines, _ = _run()
    output = "\n".join(lines)
    assert "NOTHING IS DECLARED BY THAT NAME" not in output
    assert "btc: a held asset, and no lot of it is declared here" in output
    assert "btc: declared but unreached" not in output


def test_main_returns_zero_for_an_answer_and_one_for_a_refusal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An answer that ranks nothing is still an answer, and the exit status says so."""
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.SHIPPED_ROOT),
                "--as-of",
                fixtures.AS_OF.isoformat(),
                "--question",
                fixtures.OWNERS_QUESTION,
            ]
        )
        == 0
    )
    assert capsys.readouterr().out

    # Over the COMPOSED root, because the refusal under test is "declared, but not among the
    # subjects" and the shipped root declares no instrument outside his two groups -- there,
    # `enumerated_taxable_x` would reach the same refusal for the weaker reason that nobody
    # declares it, and the case would pass without being exercised.
    broken = _rebenchmarked("enumerated_taxable_x")
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.DATA_ROOT),
                "--as-of",
                date(2026, 8, 30).isoformat(),
                "--set",
                broken,
            ]
        )
        == 1
    )
    assert "BenchmarkOutsideTheSubjects" in capsys.readouterr().out


def test_flags_search_the_same_world_the_file_does(tmp_path: Path) -> None:
    """*Sugar over the file* has to hold for the **regime**, or the manifest asserts a lie.

    A question naming a declared regime narrows the route set to that scenario's. A flag run
    that searched every corridor while the manifest recorded the narrowed world would compare
    corridors the question's own world says do not exist.
    """
    root = tmp_path / "data"
    shutil.copytree(fixtures.SHIPPED_ROOT, root)
    wartime = fixtures.QUESTION_FILE.read_text(encoding="utf-8").replace(
        'regime       = "(no regime declared)"', 'regime       = "wartime"', 1
    )
    (root / "questions" / "fifty-thousand.toml").write_text(wartime, encoding="utf-8")

    from_file = answer_question(
        root, fixtures.OWNERS_QUESTION, as_of=fixtures.AS_OF, base_currency=Currency.UAH
    )
    from_flags = cli._from_flags(root, [wartime], as_of=fixtures.AS_OF)
    assert from_flags.answer == from_file.answer
    assert from_flags.manifest.regime_id == "wartime"


def test_a_declaration_that_will_not_load_reaches_the_reader_as_words(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A broken file is not a refused question, and the exit code says which happened."""
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.SHIPPED_ROOT),
                "--as-of",
                fixtures.AS_OF.isoformat(),
                "--set",
                "this is not toml",
            ]
        )
        == cli.LOAD_FAILED
    )
    printed = capsys.readouterr().out
    assert "nothing was answered" in printed
    assert "Traceback" not in printed
    assert cli.LOAD_FAILED != cli.REFUSED


def test_a_declared_group_nobody_labelled_is_not_printed_as_undeclared() -> None:
    """FR-008a's whole guard: a group with no members and a word nobody declared differ.

    Collapsing them would erase the distinction ``AnswerInputs.groups`` exists to preserve --
    and the shipped failure mode is precisely an issue declared without its label.
    """
    supplied = fixtures.inputs()
    widened = replace(
        supplied,
        groups={**supplied.groups, "unlabelled": InstrumentGroup(id="unlabelled", name="None")},
    )
    question = fixtures.owners_question()
    result = fixtures.answered(
        fixtures.with_plans(
            fixtures.with_subjects(question, fixtures.OVDP, "unlabelled", "nothing_declares_this"),
            {fixtures.OVDP: question.plans[fixtures.OVDP]},
        ),
        widened,
    )
    printed = "\n".join(cli._subject_lines(result))
    assert "  unlabelled: 0 instrument(s) --" in printed
    assert "  nothing_declares_this: NOTHING IS DECLARED BY THAT NAME" in printed


def test_flags_answer_a_question_against_a_root_that_declares_none(tmp_path: Path) -> None:
    """The one place the file does not exist is the one place the flags path exists for."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.SHIPPED_ROOT, root)
    (root / "questions" / "fifty-thousand.toml").unlink()
    run = cli._from_flags(
        root, [fixtures.QUESTION_FILE.read_text(encoding="utf-8")], as_of=fixtures.AS_OF
    )
    assert isinstance(run.answer, Answer), run.answer
    assert not [ref for ref in run.manifest.inputs if ref.kind == "question"]


def test_a_malformed_as_of_is_not_blamed_on_a_declaration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing was read, so a message about the declarations would be a false statement.

    The date is parsed outside the block that catches a refusal, and this is what says so: a
    malformed ``--as-of`` names the flag it came from and nothing else.
    """
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.SHIPPED_ROOT),
                "--as-of",
                "yesterday",
                "--question",
                fixtures.OWNERS_QUESTION,
            ]
        )
        == cli.LOAD_FAILED
    )
    printed = capsys.readouterr().out
    assert "--as-of is not an ISO date" in printed
    assert "nothing was answered" not in printed


def test_the_flags_path_runs_the_checks_that_only_the_file_path_used_to_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The owner and the currency are checked against the streams, however the record was built.

    Two of ``resolver.check_question``'s four refusals are re-stated by the verb and two are
    not. A flags path that skipped it would answer one person's question from another person's
    money, or state fifty thousand of a currency the stream does not deliver -- and would do it
    silently, because neither is representable as a ``Refused``.
    """
    for stated, edited, field in (
        ('currency = "UAH"', 'currency = "USD"', f"{loader.QUESTION_TABLE}.amount.currency"),
        ('id = "owner-001"', 'id = "somebody-else"', f"{loader.OWNER_TABLE}.id"),
    ):
        broken = fixtures.QUESTION_FILE.read_text(encoding="utf-8").replace(stated, edited, 1)
        assert broken != fixtures.QUESTION_FILE.read_text(encoding="utf-8")
        assert (
            cli.main(
                [
                    "--data-root",
                    str(fixtures.SHIPPED_ROOT),
                    "--as-of",
                    fixtures.AS_OF.isoformat(),
                    "--set",
                    broken,
                ]
            )
            == cli.LOAD_FAILED
        )
        printed = capsys.readouterr().out
        assert field in printed, printed
        assert str(cli.FLAGS) in printed, printed


def test_a_data_root_is_required_rather_than_defaulted() -> None:
    """The shipped ``data/`` is not part of the installed package.

    A default computed from ``__file__`` resolves inside ``site-packages`` once this is a
    console script, so it would name a directory that exists only in a source checkout -- and
    the reader would meet that as a missing-file error rather than as a question about where
    the declarations live.
    """
    with pytest.raises(SystemExit) as exit_status:
        cli.main(["--as-of", fixtures.AS_OF.isoformat(), "--question", fixtures.OWNERS_QUESTION])
    assert exit_status.value.code == 2


def _ranked_section_with_an_unrankable_figure() -> tuple[HorizonSection, TupleOutcome]:
    """A section that ranks four candidates and computed a fifth it could not rank.

    Assembled by moving one outcome out of a **real** section's ranking rather than by hand,
    for the reason the whole suite is built from ``data/``: 010 puts a rate on every candidate
    the shipped registry reaches, so ``not_comparable`` is unreachable through the verb here,
    and a hand-built ``Comparison`` would measure a shape the engine never produced.
    """
    supplied = fixtures.inputs()
    for instrument_id in fixtures.declarations().tuples.registries.access:
        supplied = fixtures.with_resale_price(supplied, instrument_id)
    section = fixtures.answered(fixtures.owners_question(), supplied).sections[0]
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    assert comparison.not_comparable == ()
    # The LAST row that is not the hurdle. Taking the last unconditionally broke the moment a
    # benchmark that ranks worst was declared: the hurdle would be the one moved out, and
    # `section_ranking` then reports nothing at all rather than a ranking beside an unranked
    # figure, which is the shape these two tests are about.
    at = max(index for index in range(len(comparison.ranked)) if index != comparison.benchmark)
    moved = comparison.ranked[at]
    kept = comparison.ranked[:at] + comparison.ranked[at + 1 :]
    narrowed = replace(
        comparison,
        ranked=kept,
        benchmark=comparison.benchmark - (1 if comparison.benchmark > at else 0),
        not_comparable=(moved,),
        ties=(),
        beats_benchmark=tuple(
            index - (1 if index > at else 0) for index in comparison.beats_benchmark if index != at
        ),
    )
    return (
        replace(section, outcome=replace(section.outcome, comparison=narrowed)),
        moved,
    )


def test_a_figure_that_could_not_be_ranked_is_printed_beside_the_ranking() -> None:
    """It cost a full projection, and its ``rests on`` lines print whether or not it does.

    A renderer that showed unranked figures **only** when the ranking was empty would leave an
    assumption attached to a number the reader was never shown -- the one shape of output this
    feature exists to make impossible.
    """
    section, moved = _ranked_section_with_an_unrankable_figure()
    printed = "\n".join(cli._ranking_lines(section))
    assert f"  ranked: {len(section_ranking(section))}" in printed
    assert f"{moved.key.instrument_id} from {moved.key.stream_id}" in printed
    assert "NOT RANKED" in printed
    for claim in moved.rests_on:
        assert f"rests on ({moved.key.instrument_id}): {claim}" in printed


def test_a_printed_figure_names_all_five_terms_of_its_key() -> None:
    """Two candidates for one instrument are two options, and an id alone renders them alike.

    The identity 010 fixes is the five declared terms, and the four that are not the amount are
    what tell the reader which of them this row is. Written against the **literal** words the
    shipped registry produces rather than against the renderer's own helpers: asserting
    ``cli._exit_choice(key.route_out) in line`` would pass for a helper that returned the empty
    string, which is the term this row exists to pin.
    """
    section, _ = _ranked_section_with_an_unrankable_figure()
    outcome = section_ranking(section)[0]
    line = next(item for item in cli._figure_lines(outcome) if outcome.key.instrument_id in item)
    assert "from salary_uah" in line
    assert "via inzhur_direct" in line
    assert "out inzhur_to_monobank" in line
    assert "run as fifo/hold_cash" in line


@pytest.mark.parametrize("plan", [synthetic.A_BOND_PLAN, synthetic.A_FUND_PLAN])
def test_the_printed_plan_states_every_choice_the_plan_declares(plan: InstrumentPlan) -> None:
    """The renderer and the digest must drop the same fields, which is none of them.

    ``canonical.of_plan`` exists to be hashed and prints dates as tuples and rates as
    ``float.hex()``, so the CLI renders a plan itself -- and two renderings of one record is
    exactly where one quietly stops saying something the other still says.
    """
    for field in dataclasses.fields(plan):
        other: Any = replace(
            cast(Any, plan), **{field.name: synthetic.PLAN_FIELD_ALTERNATIVES[field.name]}
        )
        assert cli._plan_terms(other) != cli._plan_terms(plan), field.name


def test_two_plans_for_one_instrument_are_two_rows_that_read_differently() -> None:
    """The case the type name alone could not tell apart (015 FR-020a, 010 FR-023).

    A question may state several plans for one instrument -- ``DuplicateRunPlan`` refuses only
    plans that are *equal* -- so two fund candidates differing in the exit date alone are two
    figures. Rendered by the record's name they were one line printed twice, which reads as a
    duplicate rather than as a choice.
    """
    stated = fixtures.owners_question().plans[fixtures.MILTECH][0]
    assert isinstance(stated, FundAssumptions)
    later = replace(stated, exit_on=date(2028, 2, 17))
    key = _a_miltech_key()
    lines = {
        cli._figure_lines(replace(_a_miltech_outcome(), key=replace(key, exit_terms=plan)))[0]
        for plan in (stated, later)
    }
    assert len(lines) == 2, lines
    assert canonical.of_tuple_key(replace(key, exit_terms=stated)) != canonical.of_tuple_key(
        replace(key, exit_terms=later)
    )


def _a_miltech_outcome() -> TupleOutcome:
    """One outcome the engine built, so the rendering above is of a real figure."""
    section, _ = _ranked_section_with_an_unrankable_figure()
    return section_ranking(section)[0]


def _a_miltech_key() -> Tuple:
    """One real key for the fund, so the comparison above is over a key the engine built."""
    survey = fixtures.answered().sections[0].outcome
    assert isinstance(survey, CandidateSurvey)
    return next(
        item.key
        for item in survey.enumerated.candidates
        if item.key.instrument_id == fixtures.MILTECH
    )


def test_a_question_naming_an_undeclared_stream_is_refused_before_the_verb_sees_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The consequence of running the file's checks on the flags path, pinned rather than left.

    ``AmountForAnUndeclaredStream`` is still what the **verb** returns to a caller holding a
    record it built itself; through the CLI the same question never reaches the verb, because
    FR-004 says a stream nobody declared is a typo and the flags are sugar over the file. The
    two exit codes are what a reader and a script tell that apart by, so the choice is asserted
    here rather than discovered.
    """
    broken = fixtures.QUESTION_FILE.read_text(encoding="utf-8").replace(
        'stream   = "salary_uah"', 'stream   = "salary_eur"', 1
    )
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.SHIPPED_ROOT),
                "--as-of",
                fixtures.AS_OF.isoformat(),
                "--set",
                broken,
            ]
        )
        == cli.LOAD_FAILED
    )
    printed = capsys.readouterr().out
    assert "salary_eur" in printed, printed
    assert cli.LOAD_FAILED != cli.REFUSED


# ---------------------------------------------------------------------------
# 019 SC-016: the surface renders every population the core computes
# ---------------------------------------------------------------------------
#
# The last two items are the regression this criterion exists for: `Comparison.ties` and
# `Comparison.beats_benchmark` are computed by the core and, until 019, appeared nowhere in
# `src/terezy/cli/`. A ranking rendered without its tie groups is the machinery that stops the
# head of a tied group reading as a winner, computed and withheld from the only person who
# reads it.


def _dominance_block(section: HorizonSection) -> str:
    return "\n".join(cli._dominance_lines(section))


def test_all_three_populations_reach_the_reader() -> None:
    """FR-029. Two of three would make *every other is dominated* and *every other is not
    placed* indistinguishable to the one person who reads the output, which is this feature's
    own defect one level down."""
    output = "\n".join(_run()[0])
    for population in ("NON-DOMINATED ", "DOMINATED ", "not placed"):
        assert population in output, population


def test_every_line_names_candidates_rather_than_positions() -> None:
    """FR-029a. Both of 010's index fields address ``Comparison.ranked``, which 015 FR-030
    narrows afterwards, so rendering an index would put a withheld figure in front of a reader.
    """
    for section in _answered().sections:
        block = _dominance_block(section)
        assert block
        assert fixtures.MILTECH not in block, "a withheld candidate reaches the reader"
        for key in section.dominance.non_dominated:  # type: ignore[union-attr]
            assert key.instrument_id in block


def test_each_dominated_candidates_dominator_is_named() -> None:
    output = "\n".join(_run()[0])
    section = _answered().sections[0]
    beaten = section.dominance.dominated[0]  # type: ignore[union-attr]
    assert f"DOMINATED {beaten.key.instrument_id}" in output
    assert beaten.dominated_by[0].dominates.instrument_id in output
    assert beaten.dominated_by[0].strictly_better_on[0].value in output


def test_the_benchmarks_standing_and_the_objectives_behind_it_are_rendered() -> None:
    output = "\n".join(_run()[0])
    assert "THE HURDLE IS DOMINATED" in output
    assert f"{fixtures.BENCHMARK} from salary_uah" in output
    assert "objective money_at_the_endpoint more_is_better, band 0.0001" in output
    assert "objective all_money_back_on less_is_better, band 7 day(s)" in output


def test_each_candidates_indistinguishable_neighbours_are_named() -> None:
    output = "\n".join(_run()[0])
    close = _answered().sections[0].dominance.indistinguishable  # type: ignore[union-attr]
    assert close, "nothing is indistinguishable here, so this asserts nothing"
    for item in close:
        assert f"INDISTINGUISHABLE {item.key.instrument_id} from salary_uah" in output
        for neighbour in item.neighbours:
            assert f"      from {neighbour.instrument_id} from salary_uah" in output
    assert "never a group" in output, "a relation rendered as a partition"


def test_a_tie_group_is_rendered_by_candidate() -> None:
    """The shipped registry has no tie today, so the group is planted -- and the rendering has
    to name candidates, because a group of indices says nothing to a reader."""
    section = _answered().sections[0]
    assert isinstance(section.outcome, CandidateSurvey)
    comparison = section.outcome.comparison
    assert isinstance(comparison, Comparison)
    assert section_ties(section) == (), "the registry has a tie now; drop the plant"
    shown = [
        index
        for index, item in enumerate(comparison.ranked)
        if item.key in {row.key for row in section_ranking(section)}
    ]
    planted = _with_ties(section, (tuple(shown[:2]),))
    lines = cli._tie_lines(section_ties(planted))
    assert lines[0].strip() == "TIED within the project tolerance, in no order:"
    named = "\n".join(lines[1:])
    assert len(lines) == 3
    for index in shown[:2]:
        assert cli._candidate(comparison.ranked[index].key) in named


def test_an_incomparable_pair_and_a_not_placed_candidate_render_differently() -> None:
    """SC-016's last clause: two sections differing only in whether the rest of the population
    is dominated or *not placed* must render differently, which is FR-029's requirement rather
    than FR-014's."""
    section = _answered().sections[0]
    planted = dominance_sections.with_no_arrivals(section, "UA4000239016")
    rebuilt = replace(planted, dominance=dominance_sections.run(planted))
    block = _dominance_block(rebuilt)
    assert "NOT PLACED UA4000239016" in block
    assert "INCOMPARABLE " in block
    assert "no figure at TupleOutcome.arrivals" in block, (
        "the pair's own reason is where the missing figure is named, and the NOT PLACED line "
        "points at those pairs rather than repeating one of them"
    )
    assert block != _dominance_block(section)

    crossing = dominance_sections.delivering_dollars(section, ["UA4000239016"])
    printed = _dominance_block(replace(crossing, dominance=dominance_sections.run(crossing)))
    assert "delivered in UAH against USD" in printed
    assert "no exchange rate is consulted" in printed


def test_a_refused_pass_says_so_instead_of_printing_an_empty_set() -> None:
    """FR-026 at the surface: an empty set standing for a failure is what a reader would take
    as *nothing survived*."""
    document = _rebenchmarked(fixtures.MILTECH)
    answered = cli._from_flags(fixtures.SHIPPED_ROOT, [document], as_of=fixtures.AS_OF)
    assert isinstance(answered.answer, Answer)
    output = "\n".join(cli.render(answered))
    assert "NO DOMINANCE SET: BenchmarkWasWithheld" in output
    assert "NON-DOMINATED" not in output


def test_every_refusal_this_pass_can_produce_names_its_reason_in_the_output() -> None:
    """FR-026 at the surface: *every degraded outcome is a typed result carrying its reason, and
    the reason surfaces in the output*.

    Asserted over **every** arm of the union rather than over the one the shipped registry
    happens to reach. The gap this catches shipped once: a refusal whose fields are all `Enum`
    members rendered as its type name and nothing else, because the field walk read only
    `str | int | float | date` and an enum is none of them.
    """
    for refusal in _every_dominance_refusal():
        section = replace(_answered().sections[0], dominance=refusal)
        printed = "\n".join(cli._dominance_lines(section))
        assert f"NO DOMINANCE SET: {type(refusal).__name__}" in printed
        fields = [item.name for item in dataclasses.fields(refusal)]
        assert fields, type(refusal).__name__
        for name in fields:
            assert f"    {name} = " in printed, (
                f"{type(refusal).__name__}.{name} reaches no reader: {printed}"
            )


def _every_dominance_refusal() -> list[DominanceRefused]:
    """One of each arm, built here because no single registry reaches them all.

    ``NoBenchmarkToStandAgainst`` and ``NoSurveyToRunOver`` are excluded: the first carries a
    ``reason`` string that is rendered wholesale, and the second carries another record whose
    own fields a `repr` would flood the reader with -- which is the case `_named_scalars` exists
    to skip.
    """
    hurdle = _answered().sections[0].dominance
    assert isinstance(hurdle, DominanceResult)
    return [
        dominance_records.BenchmarkWasWithheld(
            key=hurdle.benchmark_standing.key, arrives_on=date(2028, 1, 20)
        ),
        dominance_records.BandBelowTheAcyclicityFloor(
            criterion=Criterion.MONEY_AT_THE_ENDPOINT,
            declared=FractionOfTheQuestionAmount(proportion=1e-13),
            resolved=Money(5e-9, Currency.UAH, prov.EMPTY),
            slack=5e-5,
            floor=5e-5,
            objective_count=2,
        ),
        dominance_records.NoQuestionAmountInTheCurrencyCompared(
            criterion=Criterion.MONEY_AT_THE_ENDPOINT, currency=Currency.USD
        ),
        dominance_records.SeveralQuestionAmountsInTheCurrencyCompared(
            criterion=Criterion.MONEY_AT_THE_ENDPOINT,
            currency=Currency.UAH,
            stream_ids=("salary_uah", "a_second_uah_stream"),
            amounts=(
                Money(50_000.0, Currency.UAH, prov.EMPTY),
                Money(20_000.0, Currency.UAH, prov.EMPTY),
            ),
        ),
        dominance_records.BandInAnotherCurrency(
            criterion=Criterion.MONEY_AT_THE_ENDPOINT,
            declared_in=Currency.UAH,
            compared_in=Currency.USD,
        ),
    ]


def test_each_reading_of_why_the_set_holds_what_it_holds_reads_differently() -> None:
    """FR-014 requires the cases distinguishable **without reading prose** on the record, and
    FR-029 requires the surface not to collapse them again. Every arm is rendered here because
    each is a sentence the owner will actually read, and one of them -- ``EveryOtherIsNotPlaced``
    -- names a state the pass cannot reach and would otherwise never be rendered at all.
    """
    sentences = {
        cli._one_member_line(reading)
        for reading in (
            dominance_records.TheSetDoesNotHaveOneMember(members=0),
            dominance_records.TheSetDoesNotHaveOneMember(members=3),
            dominance_records.OnlyOneEvaluated(),
            dominance_records.EveryOtherIsDominated(),
            dominance_records.EveryOtherIsNotPlaced(),
            dominance_records.Mixed(dominated=2, not_placed=1),
        )
    }
    assert len(sentences) == 6
    assert any("THE SET IS EMPTY" in line for line in sentences)
    assert not any(
        "best" in line or "winner" in line.replace("not a win", "") for line in sentences
    )


def test_a_set_whose_members_share_every_assumption_says_so_rather_than_listing_nothing() -> None:
    """FR-020: an empty list is what a reader takes as *nothing separates them*."""
    printed = cli._separating_lines(dominance_records.NoStatedAssumptionSeparatesThem())
    assert printed == ["the members rest on the same stated assumptions; none separates them"]


def test_a_band_is_rendered_in_the_shape_it_was_declared_in() -> None:
    """FR-023: *every band, of either criterion, in the form it was declared*. A fraction
    printed as its resolved width, or an absolute band as a fraction, would be a number the
    owner did not write."""
    assert cli._band_words(FractionOfTheQuestionAmount(proportion=0.0001)) == (
        "0.0001 of the question's amount"
    )
    assert cli._band_words(AbsoluteBand(amount=Money(5.0, Currency.UAH, prov.EMPTY))) == "5.0 UAH"
    assert cli._band_words(DaysBand(days=7)) == "7 day(s)"
