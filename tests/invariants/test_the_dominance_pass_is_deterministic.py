"""SC-017: the same question and registry produce the same set, twice and under any file order.

019 FR-024. The pass is pure -- no clock, no I/O, no randomness, no solver, no seed -- so *the
answer I got last March* has to be reproducible from the artefacts alone. Two things can quietly
break that and neither shows up in a single run: an ordering that depends on a dictionary's
insertion order, and one that depends on the order the loader happened to glob a directory in.

**The manifest is excluded from the second comparison** (015 SC-006's rule): a renamed file has
a different name, so a manifest that recorded the same name would be wrong. What must not move
is the **computed** result.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.api.answer import answer_question
from terezy.core.primitives.currency import Currency
from terezy.core.results import canonical
from terezy.core.results.answer import Answer
from terezy.data import manifest as run_manifest
from tests import answer_registries as fixtures

pytestmark = pytest.mark.invariant

AS_OF = fixtures.AS_OF


def _answer(root: Path) -> Answer:
    run = answer_question(root, fixtures.OWNERS_QUESTION, as_of=AS_OF, base_currency=Currency.UAH)
    assert isinstance(run.answer, Answer), run.answer
    return run.answer


def test_answering_twice_produces_an_equal_result_field_for_field() -> None:
    first, second = _answer(fixtures.SHIPPED_ROOT), _answer(fixtures.SHIPPED_ROOT)
    assert [section.dominance for section in first.sections] == [
        section.dominance for section in second.sections
    ]


def test_answering_twice_produces_an_equal_canonical_digest() -> None:
    """And the digest covers the dominance result, so a set that moved would move it."""
    first, second = _answer(fixtures.SHIPPED_ROOT), _answer(fixtures.SHIPPED_ROOT)
    assert run_manifest.digest_of_answer(first) == run_manifest.digest_of_answer(second)
    assert canonical.of_section(first.sections[0]) == canonical.of_section(second.sections[0])


def test_the_canonical_form_reaches_the_dominance_result_at_all() -> None:
    """The control. A digest that ignored the section's newest field would pass the two above
    while saying nothing, which is the shape of the recorded
    ``the-answer-digest-is-blind-to-the-hurdle`` gap one field over."""
    section = _answer(fixtures.SHIPPED_ROOT).sections[0]
    encoded = canonical.of_section(section)
    assert any("money-and-when" in str(element) for element in encoded), (
        "the objective set does not reach the canonical form, so the digest is blind to it"
    )


def test_renaming_the_declaration_files_so_they_sort_differently_changes_nothing(
    tmp_path: Path,
) -> None:
    """No term of the order is a property of the walk (014 FR-016), so neither is the set.

    Every instrument declaration is renamed with a prefix that reverses its sort position. The
    ids inside are untouched, so the registry is the same registry read in a different order.

    Compared through the **canonical form**, which excludes provenance by construction: a
    ``SourceRef`` names the file it came from, so a renamed file genuinely does move the mark,
    and a comparison that failed on it would be asserting that the manifest is blind to the
    rename rather than that the result is.
    """
    root = tmp_path / "data"
    shutil.copytree(fixtures.SHIPPED_ROOT, root)
    declarations = sorted((root / "instruments").glob("*.toml"))
    assert len(declarations) > 2, "too few files to reorder, so this asserts nothing"
    for position, path in enumerate(declarations):
        path.rename(path.with_name(f"{len(declarations) - position:03d}_{path.name}"))
    assert sorted(p.name for p in (root / "instruments").glob("*.toml")) != [
        p.name for p in declarations
    ]
    assert [canonical.of_section(item) for item in _answer(root).sections] == [
        canonical.of_section(item) for item in _answer(fixtures.SHIPPED_ROOT).sections
    ]


def test_a_later_as_of_ages_the_sources_and_leaves_the_set_where_it_was() -> None:
    """``as_of`` decides staleness and nothing else (015 FR-006), so it must not move a set."""
    later = answer_question(
        fixtures.SHIPPED_ROOT,
        fixtures.OWNERS_QUESTION,
        as_of=date(2026, 12, 31),
        base_currency=Currency.UAH,
    )
    assert isinstance(later.answer, Answer)
    for aged, original in zip(
        later.answer.sections, _answer(fixtures.SHIPPED_ROOT).sections, strict=True
    ):
        assert aged.dominance.non_dominated == original.dominance.non_dominated  # type: ignore[union-attr]
