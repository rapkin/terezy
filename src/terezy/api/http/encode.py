"""One fold over a :class:`~terezy.api.http.shapes.Shape`: a record becomes a JSON body.

Two properties this fold owns. **Every record carries its tag**, so a client narrows on a field
rather than on a shape -- three groups of core records share an identical field set, and one of
those pairs is a constitutional prohibition (Principle VI on one-way against round-trip cost).
And **every unordered collection comes out in a declared total order**: encode the elements, then
sort by the canonical JSON text of each. One rule for strings, ints, enums and records alike, so
there is no per-type key table to go stale (020 FR-011, FR-014, FR-019).
"""

from __future__ import annotations

import json
import math
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from terezy.api.http import shapes

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable, Mapping, Sequence

Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]

TAG_FIELD = "tag"
"""The injected field's name.

`tag` collides with no field of any core record, and the obvious alternative does:
`SourceRef.kind` is one of several a `kind` tag would have shadowed. The absence is asserted
over every reachable record rather than stated here.
"""


class UnencodableValueError(ValueError):
    """A value the body cannot carry: a non-finite figure, or a union member nothing matches.

    A programmer error rather than a domain outcome. `NaN` and `Infinity` are not JSON, so a
    body carrying one is a body a client cannot parse -- and writing `null` instead would be the
    silent clamp Principle IV forbids.
    """


def encode(shape: shapes.Shape, value: object) -> Json:  # noqa: PLR0911
    """One value, described by one shape, as JSON.

    One arm per shape, exhaustively: mypy checks the match covers the union, which is the
    property worth having here and the reason the return-count rule is waived rather than
    satisfied by folding arms into a lookup that hides the exhaustiveness.
    """
    match shape:
        case shapes.RecordShape():
            return _record(shape, value)
        case shapes.ScalarShape():
            return _scalar(value)
        case shapes.LiteralShape():
            return _scalar(value)
        case shapes.EnumShape():
            return _scalar(_as_enum(value).value)
        case shapes.DerivedShape(inner=inner, compute=compute):
            return encode(inner, compute(value))
        case shapes.OptionalShape(inner=inner):
            return None if value is None else encode(inner, value)
        case shapes.UnionShape(members=members):
            return encode(_member_for(members, value), value)
        case shapes.SequenceShape(element=element):
            return [encode(element, item) for item in _as_iterable(value)]
        case shapes.TupleShape(elements=elements):
            parts = zip(elements, _as_iterable(value), strict=True)
            return [encode(part, item) for part, item in parts]
        case shapes.SetShape(element=element):
            return _sorted([encode(element, item) for item in _as_iterable(value)])
        case shapes.MappingShape(key=key, value=inner):
            return _mapping(key, inner, value)


def canonical_text(body: Json) -> str:
    """The text an encoded value is ordered by, and the one the document is written in."""
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def _record(shape: shapes.RecordShape, value: object) -> dict[str, Json]:
    body: dict[str, Json] = {TAG_FIELD: shape.tag}
    for name, field in shape.fields:
        # A derived field is computed from the record itself; every other one is read off it.
        held = value if isinstance(field, shapes.DerivedShape) else getattr(value, name)
        body[name] = encode(field, held)
    return body


def _scalar(value: object) -> Json:
    if isinstance(value, bool | int | str) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnencodableValueError(
                f"{value!r} is not a number JSON can carry, so no body may hold it. A figure that "
                "came out non-finite is a defect upstream, not something to write as null."
            )
        return value
    if isinstance(value, date):
        return value.isoformat()
    raise UnencodableValueError(f"no scalar encoding for {value!r}")


def _as_enum(value: object) -> Enum:
    if isinstance(value, Enum):
        return value
    raise UnencodableValueError(f"{value!r} is not a member of the enum its shape names")


def _as_iterable(value: object) -> Iterable[object]:
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise UnencodableValueError(f"{value!r} is not a collection")
    return list(value)


def _member_for(members: Sequence[shapes.Shape], value: object) -> shapes.Shape:
    chosen = shapes.member_for(members, value)
    if chosen is not None:
        return chosen
    raise UnencodableValueError(
        f"{type(value).__name__} is not a member of the union its shape names. A body cannot "
        "carry a value the schema does not describe, and guessing the nearest member is how a "
        "client comes to narrow on the wrong one."
    )


def _mapping(
    key: shapes.ScalarShape | shapes.EnumShape, inner: shapes.Shape, value: object
) -> dict[str, Json]:
    if not isinstance(value, dict) and not hasattr(value, "items"):
        raise UnencodableValueError(f"{value!r} is not a mapping")
    items: Mapping[object, object] = value  # type: ignore[assignment]
    encoded = {_key(key, name): encode(inner, held) for name, held in items.items()}
    return {name: encoded[name] for name in sorted(encoded)}


def _key(key: shapes.ScalarShape | shapes.EnumShape, name: object) -> str:
    """A JSON object key is a string, so an enum key is its value and an int key its digits."""
    if isinstance(key, shapes.EnumShape):
        return str(_as_enum(name).value)
    return str(name)


def _sorted(items: list[Json]) -> list[Json]:
    return sorted(items, key=canonical_text)
