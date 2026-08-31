"""Orchestration: load the declarations, call the verb once, attach the run manifest.

Principle III puts orchestration here, never in the core and never in the CLI. The core's
:func:`terezy.core.decision.answer.answer` is a pure function of records; this is the layer that
reads files, narrows the route set to the regime the question names, and records what the run
rested on.

**The manifest is here rather than on the ``Answer`` for a reason the constitution states.** A
manifest holds SHA-256 digests, and ``hashlib`` sits in the core's forbidden imports beside
``json`` and ``tomllib``. So the core returns an answer and this layer returns
:class:`AnsweredQuestion`, which is an answer and its manifest -- and no answer a caller can
obtain from ``api/`` lacks one (FR-025).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.core.decision.answer import AnswerInputs, answer
from terezy.core.results.answer import Answer, Refused
from terezy.core.results.coverage import IMPLICIT_REGIME_ID
from terezy.data import manifest as run_manifest
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping
    from datetime import date
    from pathlib import Path

    from terezy.core.primitives.currency import Currency
    from terezy.core.results.question import Question
    from terezy.core.routes.legs import Route
    from terezy.data.manifest import RunManifest


@dataclass(frozen=True, slots=True, kw_only=True)
class AnsweredQuestion:
    """One answer and the manifest of the run that produced it.

    A record beside the answer rather than a field inside it: *a result without a manifest is
    not a result* (Principle III) is satisfied at the layer entitled to take a digest.
    """

    answer: Answer | Refused
    manifest: RunManifest


def inputs_of(declarations: resolver.AnswerDeclarations, *, regime_id: str) -> AnswerInputs:
    """The verb's second parameter, built from a resolved data root.

    **The route set is the one the question's regime declares**, never the one a transition
    happens to put in force on some date. 014 FR-023 makes the regime *the* record of which
    world was searched, and ``RunManifest.regime_id`` records the same string -- so selecting a
    different regime's routes and printing the named one would make the manifest assert a world
    the run did not search. Measured 2026-08-31: over the shipped ``war_end`` scenario a
    question naming ``normalized`` with horizons starting 2026-09-01 was answered over
    ``wartime``'s eight routes, two corridors short, under the label ``normalized``.
    """
    coverage = declarations.candidates.composition.coverage
    routes = coverage.ramp.routes
    if not coverage.regimes:
        return _inputs(declarations, routes)
    named = coverage.regimes.get(regime_id)
    if named is None:
        raise DeclarationError(
            coverage.spendable_file.parent.parent / resolver.SCENARIOS_DIR,
            "",
            f"the question asks under the regime {regime_id!r}, and the scenario resolved for "
            f"this run declares {sorted(coverage.regimes)}. A regime nobody declared would "
            "leave the route set unnarrowed, and the answer would compare corridors the "
            "question's own world says do not exist.",
            f"name one of {sorted(coverage.regimes)}",
        )
    return _inputs(declarations, {name: routes[name] for name in sorted(named.route_ids)})


def _inputs(declarations: resolver.AnswerDeclarations, routes: Mapping[str, Route]) -> AnswerInputs:
    """The bundle, over whichever route set the regime settled on."""
    return AnswerInputs(
        registries=declarations.tuples.registries,
        routes=routes,
        groups=declarations.tuples.instruments.groups,
        bound=declarations.candidates.composition.bound,
        ceiling=declarations.candidates.ceiling,
    )


def answer_declared(
    question: Question,
    root: Path,
    *,
    as_of: date,
    base_currency: Currency,
    declared_in: Path,
) -> AnsweredQuestion:
    """Answer a question record over one data root, and record what it rested on.

    The scenario the run loads is decided by the **question's** regime: one naming
    ``IMPLICIT_REGIME_ID`` is asked of the registry with no scenario in force, and one naming a
    declared regime is asked under the scenario that declares it. Both entry points go through
    here, so a question built from flags searches the same world a file does.

    **A question with no file contributes no input reference**, which is the honest record for
    one typed on a command line: there is nothing to digest. The file is canonical precisely so
    that the reproducible case is the one with an artefact behind it -- and ``declared_in`` is
    what a refusal names instead, so *where* is answered either way.

    **The cross-file checks run here as well as at load**, so a record built by a caller goes
    through them too: two of the four -- the owner and the amount's currency -- are stated
    nowhere else, and skipping them would answer one person's question from another person's
    money (015 FR-005, Principle VII). A question that came from a file is checked twice with
    the same path, because this call cannot know which kind it got.

    The price is that the other two are *unreachable through this function*: a question naming
    a stream nobody declares refuses here rather than returning ``AmountForAnUndeclaredStream``.
    That is FR-004's own rule -- in an artefact under review an unknown stream is a typo -- and
    it is why *flags are sugar over the file* has to mean the refusal too. The typed members
    stay the form the **verb** returns to a caller holding a record it built itself.
    """
    declarations = resolver.answer_from_data_root(
        root,
        base_currency=base_currency,
        scenario_id=_scenario_of(root, question.regime_id, base_currency=base_currency),
    )
    resolver.check_question(question, declarations.tuples.registries.streams, path=declared_in)
    result = answer(question, inputs_of(declarations, regime_id=question.regime_id), as_of)
    return AnsweredQuestion(
        answer=result,
        manifest=run_manifest.of_answer(
            declarations=declarations,
            question=question,
            as_of=as_of,
            result=result if isinstance(result, Answer) else None,
            refusal=None if isinstance(result, Answer) else result,
        ),
    )


def answer_question(
    root: Path,
    question_id: str,
    *,
    as_of: date,
    base_currency: Currency,
) -> AnsweredQuestion:
    """Load one data root, answer one **declared** question, and record what it rested on."""
    declared, path = _declared_question(root, question_id)
    return answer_declared(
        declared,
        root,
        as_of=as_of,
        base_currency=base_currency,
        declared_in=path,
    )


def _declared_question(root: Path, question_id: str) -> tuple[Question, Path]:
    """The declared question with that id, read from the question files and nothing else.

    Deliberately **not** a full resolution of the data root: the regime it names decides which
    scenario the real load runs under, so resolving everything twice to read one string would
    parse and cross-check the whole registry for nothing.
    """
    for path in sorted((root / resolver.QUESTIONS_DIR).glob("*.toml")):
        declared = loader.question_from_file(path)
        if declared.id == question_id:
            return declared, path
    ids = sorted(
        loader.question_from_file(path).id
        for path in sorted((root / resolver.QUESTIONS_DIR).glob("*.toml"))
    )
    raise DeclarationError(
        root / resolver.QUESTIONS_DIR,
        "",
        f"declares no question with the id {question_id!r}. The declared ids are {ids}.",
        "name a declared question, or declare the one you meant to ask",
    )


def _scenario_of(root: Path, regime_id: str, *, base_currency: Currency) -> str | None:
    """The declared scenario whose regimes include ``regime_id``, or ``None`` for the implicit.

    Resolved rather than declared beside the regime in the question file: which scenario a
    regime belongs to is a fact about ``data/scenarios/``, and a question restating it would be
    one fact in two places that disagree the day a regime moves.
    """
    if regime_id == IMPLICIT_REGIME_ID:
        return None
    ramp = resolver.ramp_from_data_root(root, base_currency=base_currency)
    for scenario_id, scenario in sorted(ramp.scenarios.items()):
        if any(regime.id == regime_id for regime in scenario.regimes):
            return scenario_id
    raise DeclarationError(
        root / resolver.SCENARIOS_DIR,
        "",
        f"declares no regime {regime_id!r}, which a question asks under. A regime nobody "
        "declared would leave the route set unnarrowed, and the answer would compare corridors "
        "the question's own world says do not exist.",
        f"declare {regime_id!r} in a scenario, or name a declared regime in the question",
    )


__all__ = ["AnsweredQuestion", "answer_declared", "answer_question", "inputs_of"]
