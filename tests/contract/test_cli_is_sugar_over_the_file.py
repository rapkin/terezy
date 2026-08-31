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
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from terezy.api.answer import answer_question
from terezy.cli import main as cli
from terezy.core.decision.answer import benchmark_unavailable, section_ranking
from terezy.core.instruments.groups import InstrumentGroup
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer, HorizonSection
from terezy.core.results.candidates import CandidateSurvey
from terezy.core.results.tuple import Comparison, TupleOutcome
from terezy.core.routes.path import candidate_id
from terezy.data.declarations import loader
from tests import answer_registries as fixtures

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
        fixtures.DATA_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
    return cli.render(answered), 0


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
    built = cli._from_flags(fixtures.DATA_ROOT, [document], as_of=fixtures.AS_OF)
    loaded = answer_question(
        fixtures.DATA_ROOT,
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
    answered = answer_question(
        fixtures.DATA_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
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
    lines, _ = _run()
    assert any("ranked: NOTHING" in line for line in lines)


def test_the_undeclared_subjects_are_named_by_the_words_he_wrote() -> None:
    lines, _ = _run()
    output = "\n".join(lines)
    for word in ("cash", "btc"):
        assert f"  {word}: NOTHING IS DECLARED BY THAT NAME" in output


def test_main_returns_zero_for_an_answer_and_one_for_a_refusal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An answer that ranks nothing is still an answer, and the exit status says so."""
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.DATA_ROOT),
                "--as-of",
                fixtures.AS_OF.isoformat(),
                "--question",
                fixtures.OWNERS_QUESTION,
            ]
        )
        == 0
    )
    assert capsys.readouterr().out

    broken = fixtures.QUESTION_FILE.read_text(encoding="utf-8").replace(
        'benchmark    = "ovdp_synthetic_a"', 'benchmark    = "enumerated_taxable_x"', 1
    )
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
    shutil.copytree(fixtures.DATA_ROOT, root)
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
                str(fixtures.DATA_ROOT),
                "--as-of",
                fixtures.AS_OF.isoformat(),
                "--set",
                "this is not toml",
            ]
        )
        == cli.LOAD_FAILED
    )
    printed = capsys.readouterr().out
    assert "could not be loaded" in printed
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
            fixtures.with_subjects(question, fixtures.OVDP, "unlabelled", "btc"),
            {fixtures.OVDP: question.plans[fixtures.OVDP]},
        ),
        widened,
    )
    printed = "\n".join(cli._subject_lines(result))
    assert "  unlabelled: 0 instrument(s) --" in printed
    assert "  btc: NOTHING IS DECLARED BY THAT NAME" in printed


def test_flags_answer_a_question_against_a_root_that_declares_none(tmp_path: Path) -> None:
    """The one place the file does not exist is the one place the flags path exists for."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    (root / "questions" / "fifty-thousand.toml").unlink()
    run = cli._from_flags(
        root, [fixtures.QUESTION_FILE.read_text(encoding="utf-8")], as_of=fixtures.AS_OF
    )
    assert isinstance(run.answer, Answer), run.answer
    assert not [ref for ref in run.manifest.inputs if ref.kind == "question"]


def test_a_malformed_as_of_is_not_blamed_on_a_declaration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing was loaded, so sending the reader to ``data/`` would be a false statement."""
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.DATA_ROOT),
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
    assert "declarations could not be loaded" not in printed


def test_the_flags_path_runs_the_checks_that_only_the_file_path_used_to_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The owner and the currency are checked against the streams, however the record was built.

    Two of ``resolver.check_question``'s three refusals are re-stated by the verb and two are
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
                    str(fixtures.DATA_ROOT),
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
    moved = comparison.ranked[-1]
    assert comparison.benchmark < len(comparison.ranked) - 1
    narrowed = replace(
        comparison,
        ranked=comparison.ranked[:-1],
        not_comparable=(moved,),
        ties=(),
        beats_benchmark=tuple(
            index for index in comparison.beats_benchmark if index < len(comparison.ranked) - 1
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
    what tell the reader which of them this row is.
    """
    section, _ = _ranked_section_with_an_unrankable_figure()
    outcome = section_ranking(section)[0]
    line = next(item for item in cli._figure_lines(outcome) if outcome.key.instrument_id in item)
    assert outcome.key.stream_id in line
    assert candidate_id(outcome.key.route_in) in line
    assert cli._exit_choice(outcome.key.route_out) in line
    assert type(outcome.key.exit_terms).__name__ in line


def test_a_question_naming_an_undeclared_stream_fails_to_load_rather_than_refusing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The consequence of running the file's checks on the flags path, pinned rather than left.

    ``AmountForAnUndeclaredStream`` is still what the **verb** returns to a caller holding a
    record it built itself; through the CLI the same question is a load failure, because FR-004
    says a file naming a stream nobody declared is a typo and the flags are sugar over the file.
    The two exit codes are what a reader and a script tell them apart by, so the choice is
    asserted here rather than discovered.
    """
    broken = fixtures.QUESTION_FILE.read_text(encoding="utf-8").replace(
        'stream   = "salary_uah"', 'stream   = "salary_eur"', 1
    )
    assert (
        cli.main(
            [
                "--data-root",
                str(fixtures.DATA_ROOT),
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
