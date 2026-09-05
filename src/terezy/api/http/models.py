"""The other fold over a :class:`~terezy.api.http.shapes.Shape`: the schema a client is generated
from.

Every record becomes a model whose first field is the literal tag, and every union of records
becomes a discriminated union on it -- ``oneOf`` with a ``discriminator`` mapping naming every
member, which is what lets a generated client narrow. ``extra="forbid"`` is load-bearing rather
than tidy: the encoder's output is validated against these models on the way out, so a field the
encoder invents or drops is a failed request rather than a body that disagrees with the document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, Literal, Union, cast

from pydantic import BaseModel, ConfigDict, Field, create_model

from terezy.api.http import encode, shapes

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping, Sequence

_MODELS: Final[dict[type, type[BaseModel]]] = {}
"""Keyed by the record, not by the model's name.

Two applications built in one process declare distinct envelope records that happen to share a
name; keyed by name, the second would be validated against the first one's model -- harmless
while their fields agree and silent when they stop.
"""

CONFIG: Final[ConfigDict] = ConfigDict(extra="forbid")


def annotation_of(shape: shapes.Shape) -> object:  # noqa: PLR0911 -- exhaustive match
    """The type annotation a field of this shape takes in a generated model."""
    match shape:
        case shapes.RecordShape():
            return model_of(shape)
        case shapes.ScalarShape(python_type=python_type):
            return python_type
        case shapes.LiteralShape(values=values):
            return Literal[values]
        case shapes.EnumShape(enum=enum):
            return enum
        case shapes.DerivedShape(inner=inner):
            return annotation_of(inner)
        case shapes.OptionalShape(inner=inner):
            return Union[annotation_of(inner), None]  # noqa: UP007
        case shapes.UnionShape(members=members):
            return _union(members)
        case shapes.SequenceShape(element=element) | shapes.SetShape(element=element):
            return list[annotation_of(element)]  # type: ignore[misc]
        case shapes.TupleShape(elements=elements):
            return tuple[tuple(annotation_of(part) for part in elements)]  # type: ignore[misc]
        case shapes.MappingShape(key=key, value=value):
            return dict[annotation_of(key), annotation_of(value)]  # type: ignore[misc]


def model_of(shape: shapes.RecordShape) -> type[BaseModel]:
    """The model one record serialises to, built once and reused wherever the record appears."""
    known = _MODELS.get(shape.record)
    if known is not None:
        return known
    fields = {
        name: (annotation_of(field), ...)
        for name, field in shape.fields
        if name != encode.TAG_FIELD
    }
    built = cast(
        "type[BaseModel]",
        create_model(
            shape.model_name,
            __config__=CONFIG,
            **{encode.TAG_FIELD: (Literal[shape.tag], ...), **fields},  # type: ignore[call-overload]
        ),
    )
    _MODELS[shape.record] = built
    return built


def envelope(name: str, tag: str, fields: Mapping[str, object]) -> type[BaseModel]:
    """A response envelope: a tag of its own, and the fields the endpoint resolved under.

    Built here rather than declared as a record because the payload type differs per category,
    and a generic record would need the shape algebra to substitute type parameters -- machinery
    for one shape of container that a factory expresses directly.
    """
    declared = {name_: (held, ...) for name_, held in fields.items()}
    return cast(
        "type[BaseModel]",
        create_model(
            name,
            __config__=CONFIG,
            **{encode.TAG_FIELD: (Literal[tag], ...), **declared},  # type: ignore[call-overload]
        ),
    )


def _union(members: Sequence[shapes.Shape]) -> object:
    annotations = tuple(annotation_of(member) for member in members)
    # A runtime tuple of annotations, which the `X | Y` form cannot take.
    united = Union[annotations]  # type: ignore[valid-type] # noqa: UP007
    if all(isinstance(member, shapes.RecordShape) for member in members):
        return Annotated[united, Field(discriminator=encode.TAG_FIELD)]
    return united
