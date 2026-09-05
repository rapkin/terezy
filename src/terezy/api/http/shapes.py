"""One description per annotated type, and the two folds that turn it into a schema and a body.

A ``Shape`` is derived once per type and consumed twice -- by :mod:`terezy.api.http.models` for
the OpenAPI document and by :mod:`terezy.api.http.encode` for the response. Hand-written response
models mirroring the core records would be the same fields in two places, in the one file a
second codebase is generated from; a single walk with two folds cannot disagree about a field's
presence, and the framework validating the encoder's output against the generated model turns any
remaining disagreement into a failed request rather than a wrong body.

A type this cannot describe is a loud failure naming the record and the field. Nothing is skipped
and nothing is serialised as the text of its ``repr``.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final, Literal

from terezy.api.http import tags
from terezy.core.instruments.access import InstrumentAccess
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.instruments.groups import InstrumentGroup
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Route
from terezy.core.streams.streams import IncomeStream
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.data.manifest import RunManifest


class UnserialisableAnnotationError(TypeError):
    """The algebra has no arm for this annotation, or a record refers to itself.

    A programmer error rather than a domain outcome: nothing downstream can proceed and no
    partial body exists to return, which is the same reasoning ``DeclarationError`` records for
    a malformed file.
    """


@dataclass(frozen=True, slots=True)
class ScalarShape:
    """A JSON primitive: ``str``, ``int``, ``float``, ``bool``, or a ``date`` as ISO text."""

    python_type: type


@dataclass(frozen=True, slots=True)
class LiteralShape:
    """A closed set of literal values, as the annotation spells them."""

    values: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class EnumShape:
    """An enum, serialised by its value."""

    enum: type[Enum]


@dataclass(frozen=True, slots=True)
class DerivedShape:
    """A field the serialiser computes rather than reads, and the function it computes it with.

    The one thing this layer adds to a record, and it is added because FR-018 requires it: a
    client that recomputed ``is_unverified`` from the source list would be free to get the
    one-taints-all asymmetry backwards, and the mark would then depend on which client was
    reading. Anything else derived here would be the serialiser deciding what happened, which
    FR-015 forbids.
    """

    inner: ScalarShape
    compute: Callable[[object], object]


@dataclass(frozen=True, slots=True)
class RecordShape:
    """A frozen dataclass: its tag, and its fields in declaration order."""

    record: type
    tag: str
    model_name: str
    fields: tuple[tuple[str, Shape], ...]


@dataclass(frozen=True, slots=True)
class OptionalShape:
    inner: Shape


@dataclass(frozen=True, slots=True)
class UnionShape:
    members: tuple[Shape, ...]


@dataclass(frozen=True, slots=True)
class SequenceShape:
    """A homogeneous ordered collection. Serialised in its own order."""

    element: Shape


@dataclass(frozen=True, slots=True)
class TupleShape:
    """A fixed-length tuple, such as a two-ended window. The arity is part of the contract."""

    elements: tuple[Shape, ...]


@dataclass(frozen=True, slots=True)
class SetShape:
    """An unordered collection, serialised in the declared total order (FR-019)."""

    element: Shape


@dataclass(frozen=True, slots=True)
class MappingShape:
    key: ScalarShape | EnumShape
    value: Shape


Shape = (
    ScalarShape
    | LiteralShape
    | EnumShape
    | DerivedShape
    | RecordShape
    | OptionalShape
    | UnionShape
    | SequenceShape
    | TupleShape
    | SetShape
    | MappingShape
)

IS_UNVERIFIED: Final[Callable[[object], object]] = lambda value: prov.is_unverified(  # noqa: E731
    typing.cast(Provenance, value)
)
"""``provenance.is_unverified``, named so :class:`DerivedShape` compares equal across calls."""

_DERIVED: Final[Mapping[type, tuple[tuple[str, DerivedShape], ...]]] = {
    Provenance: (("is_unverified", DerivedShape(ScalarShape(bool), IS_UNVERIFIED)),),
}
"""Fields this layer computes. One entry; :class:`DerivedShape` says why it is the only one."""

_SCALARS: Final[frozenset[type]] = frozenset({str, int, float, bool, date})

_FALLBACK: Final[Mapping[str, object]] = {
    "date": date,
    "Mapping": Mapping,
    "Sequence": Sequence,
    "Provenance": Provenance,
    "Currency": Currency,
    "Money": Money,
    "Route": Route,
    "InstrumentAccess": InstrumentAccess,
    "InstrumentDeclaration": InstrumentDeclaration,
    "FundDeclaration": FundDeclaration,
    "InstrumentGroup": InstrumentGroup,
    "FxChannel": FxChannel,
    "IncomeStream": IncomeStream,
    "TaxClass": TaxClass,
    "TaxableEventKind": TaxableEventKind,
    "RunManifest": RunManifest,
}
"""Names that appear in annotations under ``TYPE_CHECKING`` and so are absent at run time.

Layered *under* each record's own module globals, never over them, so a module's own name always
wins and this cannot shadow a ``date`` or a ``Mapping`` with something else's. The first attempt
supplied one flat namespace built from every core module instead, and it was worse than useless:
it shadowed those two and failed on records that resolve perfectly well on their own.
"""

_MEMO: Final[dict[type, RecordShape]] = {}
_IN_PROGRESS: Final[set[type]] = set()


def plan_of(annotation: object) -> Shape:
    """The shape of one annotated type."""
    if isinstance(annotation, typing.TypeAliasType):
        # A `type X = ...` alias resolves to itself rather than to what it names, so a field
        # annotated with one would otherwise have no arm.
        return plan_of(annotation.__value__)
    if isinstance(annotation, type):
        if dataclasses.is_dataclass(annotation):
            return _record(annotation)
        if issubclass(annotation, Enum):
            return EnumShape(annotation)
        if annotation in _SCALARS:
            return ScalarShape(annotation)
    build = _BY_ORIGIN.get(typing.get_origin(annotation))
    if build is None:
        raise UnserialisableAnnotationError(
            f"no shape for the annotation {annotation!r}. Every field of every response type has "
            "to be describable; add an arm to terezy.api.http.shapes, or keep the type out of a "
            "response."
        )
    return build(typing.get_args(annotation))


def walk(shape: Shape) -> Iterator[Shape]:
    """Every shape reachable from this one, each yielded once.

    The walk FR-013 and FR-017 are written in terms of: a test discovers the unions, the records
    and the money-valued fields from the response types rather than holding a list of them, which
    the constitution requires of any enumeration of things declared elsewhere.
    """
    seen: set[int] = set()

    def visit(node: Shape) -> Iterator[Shape]:
        if id(node) in seen:
            return
        seen.add(id(node))
        yield node
        for child in _children(node):
            yield from visit(child)

    return visit(shape)


def _children(shape: Shape) -> tuple[Shape, ...]:  # noqa: PLR0911 -- exhaustive match
    match shape:
        case RecordShape(fields=fields):
            return tuple(field for _, field in fields)
        case UnionShape(members=members):
            return members
        case TupleShape(elements=elements):
            return elements
        case OptionalShape(inner=inner) | DerivedShape(inner=inner):
            return (inner,)
        case SequenceShape(element=element) | SetShape(element=element):
            return (element,)
        case MappingShape(key=key, value=value):
            return (key, value)
        case _:
            return ()


def records_in(shape: Shape, value: object) -> Iterator[object]:  # noqa: PLR0912 -- exhaustive match
    """Every record *value* reachable from one value, described by its shape.

    The value-side companion of :func:`walk`, and the reason a category's merged mark does not
    rest on a per-record list of which fields carry provenance -- a list which would be one more
    enumeration of things declared elsewhere.
    """
    match shape:
        case RecordShape(fields=fields):
            yield value
            for name, field in fields:
                if not isinstance(field, DerivedShape):
                    yield from records_in(field, getattr(value, name))
        case OptionalShape(inner=inner):
            if value is not None:
                yield from records_in(inner, value)
        case UnionShape(members=members):
            for member in members:
                if isinstance(member, RecordShape) and type(value) is member.record:
                    yield from records_in(member, value)
        case SequenceShape(element=element) | SetShape(element=element):
            for item in typing.cast("Iterable[object]", value):
                yield from records_in(element, item)
        case TupleShape(elements=elements):
            for part, item in zip(elements, typing.cast("Iterable[object]", value), strict=True):
                yield from records_in(part, item)
        case MappingShape(value=inner):
            for item in typing.cast("Mapping[object, object]", value).values():
                yield from records_in(inner, item)
        case _:
            return


def record_of(record: type) -> RecordShape:
    """The shape of a type that must be a record, for callers that need its fields."""
    planned = plan_of(record)
    if not isinstance(planned, RecordShape):
        raise UnserialisableAnnotationError(f"{record!r} is not a frozen record")
    return planned


def _record(record: type) -> RecordShape:
    known = _MEMO.get(record)
    if known is not None:
        return known
    if record in _IN_PROGRESS:
        raise UnserialisableAnnotationError(
            f"{record.__name__} refers to itself. A response type has to be a finite tree: a "
            "cyclic one has no terminating encoding and no schema a generated client can name."
        )
    _IN_PROGRESS.add(record)
    try:
        hints = _hints(record)
        fields = tuple(
            (field.name, _field(record, field.name, hints[field.name]))
            for field in dataclasses.fields(record)
        )
        planned = RecordShape(
            record=record,
            tag=tags.tag_of(record),
            model_name=tags.model_name_of(record),
            fields=fields + _DERIVED.get(record, ()),
        )
    finally:
        _IN_PROGRESS.discard(record)
    _MEMO[record] = planned
    return planned


def _field(record: type, name: str, annotation: object) -> Shape:
    try:
        return plan_of(annotation)
    except UnserialisableAnnotationError as unserialisable:
        raise UnserialisableAnnotationError(
            f"{record.__name__}.{name}: {unserialisable}"
        ) from unserialisable


def _hints(record: type) -> Mapping[str, object]:
    module = __import__("sys").modules.get(record.__module__)
    namespace = {**_FALLBACK, **(vars(module) if module is not None else {})}
    try:
        return typing.get_type_hints(record, globalns=namespace)
    except NameError as unresolved:
        raise UnserialisableAnnotationError(
            f"{record.__name__}: {unresolved}. The name is imported under TYPE_CHECKING and is "
            "not in terezy.api.http.shapes._FALLBACK, so the annotation cannot be resolved."
        ) from unresolved


def _union(args: tuple[object, ...]) -> Shape:
    """One flat union, whatever nesting the annotation reached it through.

    ``Answer | Refused`` is a union whose second arm is itself a union alias, and a nested
    ``UnionShape`` would leave the outer one with a member that is not a record -- which is
    exactly the test the discriminator rule applies, so the document would come out with an
    undiscriminated ``anyOf`` and a client with nothing to narrow on.
    """
    members = tuple(
        flattened for arg in args if arg is not type(None) for flattened in _flattened(plan_of(arg))
    )
    inner: Shape = members[0] if len(members) == 1 else UnionShape(members)
    return OptionalShape(inner) if any(arg is type(None) for arg in args) else inner


def _flattened(shape: Shape) -> tuple[Shape, ...]:
    return shape.members if isinstance(shape, UnionShape) else (shape,)


def _tuple(args: tuple[object, ...]) -> Shape:
    if args[1:] == (Ellipsis,):
        return SequenceShape(plan_of(args[0]))
    return TupleShape(tuple(plan_of(arg) for arg in args))


def _sequence(args: tuple[object, ...]) -> SequenceShape:
    return SequenceShape(plan_of(args[0]))


def _set(args: tuple[object, ...]) -> SetShape:
    return SetShape(plan_of(args[0]))


def _mapping(args: tuple[object, ...]) -> MappingShape:
    key = plan_of(args[0])
    if not isinstance(key, ScalarShape | EnumShape):
        raise UnserialisableAnnotationError(
            f"a mapping key of {args[0]!r} has no JSON object key form. Keys are strings, so a "
            "key type must be a scalar or an enum."
        )
    return MappingShape(key, plan_of(args[1]))


_BY_ORIGIN: Final[Mapping[object, Callable[[tuple[object, ...]], Shape]]] = {
    Literal: LiteralShape,
    types.UnionType: _union,
    typing.Union: _union,
    tuple: _tuple,
    list: _sequence,
    Sequence: _sequence,
    frozenset: _set,
    set: _set,
    dict: _mapping,
    Mapping: _mapping,
}
"""Which arm an annotation's origin takes: a registry of functions, not a chain of branches."""
