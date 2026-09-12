"""Every field of the question schema is a type JSON carries (029 FR-002, SC-003).

A scan over the **schema** rather than over a list of field names, and a scan at all because the
type checker is content with a `datetime.date` field that JSON cannot spell: the day one is
added, the file keeps loading, the body stops round-tripping, and nothing else in this suite is
red. It pins the schema's shape rather than its behaviour, which is the price.
"""

from __future__ import annotations

import datetime
import types
import typing
from typing import Final

import pytest
from pydantic import BaseModel

from terezy.data.declarations import schema

CARRIED: Final = (str, float, int, bool, type(None))
"""What a JSON document holds. A nested model and a list of either are walked into."""


def _fields(model: type[BaseModel], prefix: str) -> list[tuple[str, object]]:
    return [(f"{prefix}.{name}", field.annotation) for name, field in model.model_fields.items()]


def _unsupported(annotation: object, path: str) -> list[str]:
    """Every leaf under one annotation that JSON cannot carry, named by its field path."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType, list, tuple, set, frozenset, dict):
        return [
            fault
            for argument in typing.get_args(annotation)
            for fault in _unsupported(argument, path)
        ]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [
            fault for name, held in _fields(annotation, path) for fault in _unsupported(held, name)
        ]
    if annotation in CARRIED:
        return []
    return [f"{path}: {annotation!r}"]


@pytest.mark.contract
def test_every_field_of_the_question_schema_is_json_expressible() -> None:
    walked = _unsupported(schema.QuestionFile, "question_file")
    assert not walked, f"these fields cannot be carried by a request body: {walked}"


@pytest.mark.contract
def test_the_scan_finds_a_field_json_cannot_carry() -> None:
    """The mutation, performed, so the sweep above cannot pass by walking into nothing."""

    class WithADate(BaseModel):
        asked_on: datetime.date

    class Holding(BaseModel):
        inner: list[WithADate]

    assert _unsupported(Holding, "holding") == ["holding.inner.asked_on: <class 'datetime.date'>"]
