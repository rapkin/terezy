"""The candidate set the shipped declarations produce, recorded so a refactor is checkable.

The counterpart of ``test_ramp_comparison.py`` for feature 014: what the registry offers, what
each option was scored at, what was dropped and why, and which pairs became nothing at all.

**Why an artefact as well as assertions.** ``tests/worked_examples/test_candidate_enumeration.py``
derives every count from the registry it loads, which is what stops the numbers being the code's
opinion. This file is the other guarantee: today's output against a recorded one, so a refactor
that quietly moved a figure fails here even when every derivation still passes on its own terms.

**A golden is evidence, never a freeze** (constitution 1.2.0). A declaration that changes
*should* move the recorded input digests, and correcting one is the right response rather than
a thing to avoid. What must be justified in a commit message is a moved **result**.

**Deliberately excluded**: provenance. Filling in a ``verified_on`` must not move the artefact,
or the test would fail on a documentation edit. The mark itself is asserted separately, in
``tests/unit/test_candidate_marks.py``.

**How to update it deliberately**::

    TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_candidate_set.py
    git diff tests/golden/candidate_set.golden.txt

then read the diff and justify each changed line. A **missing** file is a failure, never a
silent regeneration: an artefact that reappeared on its own would make a deleted one
indistinguishable from a passing run.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Final, assert_never

import pytest

from terezy.core.decision.candidates import drop_tally, dropped, evaluated, survey
from terezy.core.primitives.rates import NominalRate
from terezy.core.results.candidates import (
    CandidateSet,
    CandidateSurvey,
    NoCandidateReason,
    NothingConnects,
    NothingNeedsToConnect,
)
from terezy.core.results.tuple import Comparison
from terezy.core.routes.path import ExitChain, candidate_id, exit_segments_of
from tests import candidate_registries as fixtures
from tests import data_roots

pytestmark = pytest.mark.golden

GOLDEN_FILE: Final = Path(__file__).with_name("candidate_set.golden.txt")
UPDATE_VARIABLE: Final = "TEREZY_UPDATE_GOLDEN"
BENCHMARK: Final = "UA4000235865"
"""The issue the owner named in his own question file, so one artefact is measured once."""


def _surveyed() -> CandidateSurvey:
    registries = fixtures.declared(data_roots.SHIPPED)
    question = fixtures.question(registries)
    result = survey(
        registries=registries,
        routes=registries.routes,
        question=question,
        ceiling=fixtures.declarations(data_roots.SHIPPED).ceiling,
        benchmark=fixtures.benchmark_key(registries, BENCHMARK, question_=question),
    )
    assert isinstance(result, CandidateSurvey), result
    return result


def _way_out(candidate: object) -> str:
    chain = candidate.key.route_out  # type: ignore[attr-defined]
    assert isinstance(chain, ExitChain)
    return "+".join(exit_segments_of(chain)) or "(identity exit)"


def _render(result: CandidateSurvey) -> str:
    enumerated: CandidateSet = result.enumerated
    lines = [
        "# The candidate set the shipped declarations offer, for one stated question.",
        "# Regenerate deliberately: TEREZY_UPDATE_GOLDEN=1 uv run pytest"
        " tests/golden/test_candidate_set.py",
        "",
        "[question]",
        f"horizon        {enumerated.question.horizon.start} .. {enumerated.question.horizon.end}",
        f"as_of          {enumerated.question.as_of}",
        f"continuation   {enumerated.question.continuation.value}",
        f"segment_bound  {enumerated.question.bound.max_segments}",
        f"regime         {enumerated.question.regime_id}",
    ]
    lines += [
        f"amount         {stream} {enumerated.question.amounts[stream].currency.value} "
        f"{enumerated.question.amounts[stream].amount!r}"
        for stream in sorted(enumerated.question.amounts)
    ]
    lines += [
        f"plans          {instrument} x{len(enumerated.question.plans[instrument])}"
        for instrument in sorted(enumerated.question.plans)
    ]

    lines += ["", "[accounting]", f"pairs_considered  {enumerated.pairs_considered}"]
    lines += [
        f"enumerated        {len(enumerated.candidates)}",
        f"no_candidate      {len(enumerated.no_candidate)}",
        f"evaluated         {len(evaluated(result.comparison))}",
        f"dropped           {len(dropped(result.comparison))}",
    ]

    lines += ["", "[candidates]  instrument | stream | way in | way out | plan"]
    lines += [
        f"{candidate.key.instrument_id} | {candidate.key.stream_id} | "
        f"{candidate_id(candidate.key.route_in)} | {_way_out(candidate)} | "
        f"{candidate.plan_position}"
        for candidate in enumerated.candidates
    ]

    lines += ["", "[scored]  instrument | reaches | rate"]
    for outcome in sorted(evaluated(result.comparison), key=lambda item: item.key.instrument_id):
        rate = (
            repr(outcome.implied_rate.value)
            if isinstance(outcome.implied_rate, NominalRate)
            else "(not comparable)"
        )
        lines.append(
            f"{outcome.key.instrument_id} | {outcome.reaches.currency.value} "
            f"{outcome.reaches.amount!r} | {rate}"
        )

    lines += ["", "[dropped]  reason | count | instruments"]
    lines += [
        f"{group.refusal} | {group.count} | {', '.join(group.instruments)}"
        for group in drop_tally(dropped(result.comparison))
    ]

    lines += ["", "[no candidate]  instrument | stream | reason"]
    lines += [
        f"{pair.instrument_id} | {pair.stream_id} | {_why(pair.why)}"
        for pair in enumerated.no_candidate
    ]

    lines += ["", f"[digest]  {_digest(result)}", ""]
    return "\n".join(lines)


def _why(reason: NoCandidateReason) -> str:
    """The typed reason as one rendered word, matched exhaustively so a third member shows up
    here as a type error rather than as a blank cell."""
    match reason:
        case NothingConnects():
            return f"nothing connects ({reason.side})"
        case NothingNeedsToConnect():
            return "nothing needs to connect"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(reason)


def _digest(result: CandidateSurvey) -> str:
    """Bit-identity over the keys and the figures, with provenance deliberately excluded.

    Amounts as ``float.hex()``, so agreement means bit-identity rather than agreement to the
    precision the rendering happens to show.
    """
    shape: list[str] = []
    for candidate in result.enumerated.candidates:
        shape.append(
            f"{candidate.key.instrument_id}|{candidate.key.stream_id}|"
            f"{candidate_id(candidate.key.route_in)}|{_way_out(candidate)}|"
            f"{candidate.plan_position}"
        )
    for outcome in sorted(evaluated(result.comparison), key=lambda item: item.key.instrument_id):
        rate = (
            outcome.implied_rate.value.hex()
            if isinstance(outcome.implied_rate, NominalRate)
            else "none"
        )
        shape.append(f"{outcome.key.instrument_id}|{outcome.reaches.amount.hex()}|{rate}")
    for group in drop_tally(dropped(result.comparison)):
        shape.append(f"{group.refusal}|{group.count}|{','.join(group.instruments)}")
    return hashlib.sha256("\n".join(shape).encode()).hexdigest()[:32]


def _recorded() -> str:
    if not GOLDEN_FILE.is_file():
        raise AssertionError(
            f"{GOLDEN_FILE.name} does not exist. A golden file is never regenerated silently "
            f"-- produce it deliberately with {UPDATE_VARIABLE}=1 uv run pytest "
            "tests/golden/test_candidate_set.py, then read the diff."
        )
    return GOLDEN_FILE.read_text(encoding="utf-8")


def _today() -> str:
    rendered = _render(_surveyed())
    if os.environ.get(UPDATE_VARIABLE):
        GOLDEN_FILE.write_text(rendered, encoding="utf-8")
    return rendered


class TestTheRecordedSetIsStillTheSet:
    def test_the_whole_set_matches_the_checked_in_artefact(self) -> None:
        assert _today() == _recorded()

    def test_the_recorded_digest_is_the_digest_of_todays_run(self) -> None:
        """The assertion inside the assertion, so a rendering drift cannot hide a figure."""
        assert _digest(_surveyed()) in _recorded()

    def test_no_rendered_line_ends_in_whitespace(self) -> None:
        assert all(line == line.rstrip() for line in _today().splitlines())


class TestTheArtefactCannotBeGreenAndWrong:
    """An artefact recorded from a broken run agrees with itself forever, so the counts are
    re-derived from the registry here rather than read out of the file."""

    def test_the_recorded_counts_are_the_counts_the_declarations_imply(self) -> None:
        registries = fixtures.declared(data_roots.SHIPPED)
        declared = [
            instrument_id
            for instrument_id in registries.access
            if instrument_id in registries.instruments or instrument_id in registries.funds
        ]
        result = _surveyed()
        assert result.enumerated.pairs_considered == len(declared) * len(registries.streams)
        # Over PAIRS, not candidates. One candidate per connecting pair is a property of this
        # registry, not of the accounting -- a second corridor or a second run plan makes the
        # two counts differ while FR-009 still holds.
        enumerated_pairs = {
            (candidate.key.instrument_id, candidate.key.stream_id)
            for candidate in result.enumerated.candidates
        }
        assert len(enumerated_pairs) + len(result.enumerated.no_candidate) == (
            result.enumerated.pairs_considered
        )

    def test_the_benchmark_is_a_member_of_the_recorded_set(self) -> None:
        result = _surveyed()
        assert isinstance(result.comparison, Comparison)
        pointed = result.comparison.ranked[result.comparison.benchmark].key
        assert pointed.instrument_id == BENCHMARK
        assert pointed in {item.key for item in result.enumerated.candidates}

    def test_provenance_is_excluded_so_a_citation_edit_cannot_move_the_artefact(self) -> None:
        assert "verified_on" not in _today()
        assert "source" not in _today()
