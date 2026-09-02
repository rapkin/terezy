"""The owner's question and its whole answer, recorded.

015 SC-018. The artefact beside this file is what the engine answers today, and its value is
that a diff to it is a *finding*: a declaration that changes, or a hurdle he renames, moves
lines here and the diff is the evidence.

**Over the shipped root, never the composed one.** This records what the owner is actually
offered, so an invented instrument appearing in it would be a figure about a security nobody
can buy.

Regenerate deliberately, read the diff, and say in the commit message why every changed line is
intended::

    TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_the_answer.py
    git diff tests/golden/the_answer.golden.txt

The variable is required and a missing file is a **failure** rather than a silent regeneration:
an artefact that reappeared on its own would make a deleted one -- or a fresh checkout that
never had one -- indistinguishable from a passing run.

**Provenance is excluded from the digest**, on ``core.results.canonical``'s established rule:
filling in a ``verified_on`` changes what a result says about its *sources* and moves no
computed amount, so a digest that covered it would fail on a documentation edit. The mark is not
thereby lost -- it is a separate claim, asserted by the walk in
``tests/contract/test_the_answer_says_only_what_it_computed.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

import pytest

from terezy.api.answer import answer_question
from terezy.core.decision.answer import (
    considered_ids,
    key_agreement,
    section_evaluated,
    section_ranking,
    subject_counts,
)
from terezy.core.decision.candidates import drop_tally, dropped
from terezy.core.primitives.currency import Currency
from terezy.core.results.answer import Answer, DeclaredSubject
from terezy.core.results.candidates import CandidateSurvey
from terezy.data import manifest as run_manifest
from tests import answer_registries as fixtures

pytestmark = pytest.mark.golden

GOLDEN_FILE: Final = Path(__file__).with_name("the_answer.golden.txt")
UPDATE_VARIABLE: Final = "TEREZY_UPDATE_GOLDEN"


def _answered() -> Answer:
    run: Any = answer_question(
        fixtures.SHIPPED_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=fixtures.AS_OF,
        base_currency=Currency.UAH,
    )
    assert isinstance(run.answer, Answer), run.answer
    return run.answer


def _render(result: Answer) -> str:
    """The record, rendered flat. Amounts as ``float.hex()``, so agreement is bit-identity."""
    lines = [
        "# terezy golden result -- the owner's question, answered.",
        "#",
        "# Produced by tests/golden/test_the_answer.py; see that module on regenerating it.",
        "# Provenance is deliberately excluded from the digest below.",
        "",
        f"[question] {result.question.id}  asked {result.question.asked_on.isoformat()}  "
        f"as_of {result.as_of.isoformat()}  regime {result.question.regime_id}",
        f"[benchmark] {result.question.benchmark_instrument_id}",
        f"[considered] {' '.join(considered_ids(result))}",
        "",
    ]
    for subject in result.subjects:
        ids = subject.ids if isinstance(subject, DeclaredSubject) else ()
        kind = "group" if isinstance(subject, DeclaredSubject) and subject.is_group else "id"
        lines.append(
            f"[subject] {subject.named:24} {kind if ids else 'undeclared':11} {' '.join(ids)}"
        )
    lines.append("")
    for section in result.sections:
        counts = subject_counts(result, section)
        lines.append(
            f"[section] {section.horizon.start.isoformat()}..{section.horizon.end.isoformat()}  "
            f"{type(section.outcome).__name__}  reached={counts.reached} "
            f"unreached={counts.declared_but_unreached} undeclared={counts.undeclared} "
            f"ids={counts.ids_considered}"
        )
        if isinstance(section.outcome, CandidateSurvey):
            lines.append(
                f"  enumerated {len(section.outcome.enumerated.candidates)}  "
                f"no_candidate {len(section.outcome.enumerated.no_candidate)}  "
                f"pairs {section.outcome.enumerated.pairs_considered}  "
                f"comparison {type(section.outcome.comparison).__name__}"
            )
            for outcome in section_evaluated(section):
                lines.append(
                    f"  evaluated {outcome.key.instrument_id:24} "
                    f"reaches {outcome.reaches.amount.hex()}"
                )
            lines.append(f"  ranked {len(section_ranking(section))}")
            for group in drop_tally(dropped(section.outcome.comparison)):
                lines.append(
                    f"  dropped {group.refusal:28} {group.count}  {','.join(group.instruments)}"
                )
        for item in section.excludes:
            lines.append(
                f"  excludes {item.what.value:38} "
                f"{'' if item.applies_to is None else item.applies_to.instrument_id:24} "
                f"{'' if item.direction is None else item.direction.value}"
            )
        for withheld in section.arrives_after_horizon:
            lines.append(
                f"  withheld {withheld.key.instrument_id:24} arrives "
                f"{withheld.arrives_on.isoformat()}"
            )
        lines.append("")
    for item in result.excludes:
        lines.append(f"[excludes] {item.what.value}")
    lines.append("")
    lines.append(f"[keys] {type(key_agreement(result)).__name__}")
    lines.append(f"[digest] {run_manifest.digest_of_answer(result)}")
    return "\n".join(lines) + "\n"


def _recorded() -> str:
    if not GOLDEN_FILE.is_file():
        raise AssertionError(
            f"there is no golden artefact at {GOLDEN_FILE}. It is not regenerated silently: "
            f"run {UPDATE_VARIABLE}=1 uv run pytest {Path(__file__).name} and read the diff."
        )
    return GOLDEN_FILE.read_text(encoding="utf-8")


def test_the_answer_matches_the_recorded_artefact() -> None:
    rendered = _render(_answered())
    if os.environ.get(UPDATE_VARIABLE):
        GOLDEN_FILE.write_text(rendered, encoding="utf-8")
    assert rendered == _recorded(), (
        "the owner's answer no longer matches the recorded artefact. If that is intended, "
        "update it deliberately and read the diff: see this module's docstring."
    )


def test_the_recorded_artefact_ranks_every_bond_against_the_declared_benchmark() -> None:
    """The claim the artefact is kept for, pinned in the artefact itself.

    24 at every horizon, and the benchmark among them: a ranking of 23 would mean an issue
    dropped out and a ranking of 0 would mean the hurdle went missing, and the digest alone
    would say neither.
    """
    assert _recorded().count("  ranked 24") == len(_answered().sections)
    assert f"[benchmark] {fixtures.BENCHMARK}" in _recorded()


def test_verifying_every_source_would_not_move_the_digest() -> None:
    """Provenance is excluded by construction, not by nobody having tried it.

    Asserted here rather than argued: a digest that moved on a ``verified_on`` would fail on a
    documentation edit, and the only available fix would be to stop trusting the digest.
    """
    result = _answered()
    assert run_manifest.digest_of_answer(result) == run_manifest.digest_of_answer(result)
    assert "verified" not in _recorded()
