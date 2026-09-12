"""A regime nobody declared is the question's fault, whatever declared the question.

029 FR-015. Both refusals were rooted at `data/scenarios/`, which is the directory that would
have to declare the regime -- so the first typo a caller makes was reported as a broken
installation, and the reader was sent to a data root that is fine. Two near-identical refusals,
so both cases are provoked here: `_scenario_of`'s runs before the cross-checks because it is
evaluated to build their argument, and `inputs_of`'s runs after them.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from terezy.api import answer as verb
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import answer_registries as fixtures

AS_OF = fixtures.AS_OF
BODY = Path("<request>")


def _refusal(root: Path, *, regime_id: str, declared_in: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        verb.answer_declared(
            replace(fixtures.owners_question(), regime_id=regime_id),
            root,
            as_of=AS_OF,
            base_currency=Currency.UAH,
            declared_in=declared_in,
            question_version=None,
        )
    return raised.value


def test_a_file_declared_question_is_blamed_for_its_own_regime() -> None:
    refused = _refusal(
        fixtures.SHIPPED_ROOT,
        regime_id="nothing-declares-this",
        declared_in=fixtures.QUESTION_FILE,
    )

    assert refused.file == fixtures.QUESTION_FILE
    assert refused.field_path == verb.REGIME_FIELD


def test_a_caller_built_record_is_blamed_for_its_own_regime() -> None:
    """The sentinel a request body's refusals name, so no filesystem path reaches the caller."""
    refused = _refusal(fixtures.SHIPPED_ROOT, regime_id="nothing-declares-this", declared_in=BODY)

    assert refused.file == BODY
    assert refused.field_path == verb.REGIME_FIELD


def test_the_second_regime_refusal_blames_the_question_too(tmp_path: Path) -> None:
    """`inputs_of`'s copy, reached only where a scenario *is* in force: `_scenario_of` returns
    that scenario's id, the load succeeds, and the narrowing then finds no such regime in it."""
    root = tmp_path / "data"
    shutil.copytree(fixtures.DATA_ROOT, root)
    declarations = resolver.answer_from_data_root(
        root, base_currency=Currency.UAH, scenario_id="war_end"
    )

    with pytest.raises(DeclarationError) as raised:
        verb.inputs_of(
            declarations,
            regime_id="nothing-declares-this",
            objective_set_id=fixtures.OBJECTIVE_SET,
            declared_in=BODY,
        )

    assert raised.value.file == BODY
    assert raised.value.field_path == verb.REGIME_FIELD
