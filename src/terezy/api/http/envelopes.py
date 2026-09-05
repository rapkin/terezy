"""The response containers, and the refusals they can carry instead of a record.

An envelope is built per category rather than declared once, because the payload type differs
per category and one record with a type parameter would need the shape algebra to substitute
type variables -- machinery for one kind of container. They are built as **frozen dataclasses**
so that they go through :func:`terezy.api.http.shapes.plan_of` like any core record: one tag
scheme, one encoder, one model builder, and no second serialisation path that could disagree
with the first.

Every envelope states the parameters its read resolved under -- the `as_of` and the scenario --
so an answer is never silently one of several (020 FR-007b).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date
from enum import Enum

from terezy.api.http import shapes

_MODULE = __name__


@dataclass(frozen=True, slots=True)
class CategoryHasNoSuchId:
    """A keyed read of an id the category does not declare.

    A well-formed question with a typed answer, and deliberately **not** a `DeclarationError`:
    the loader's error means a broken data root, which the CLI maps to a different exit code
    from a refusal, and reporting one for the other sends a reader to `data/` to look for a
    fault that is not there (020 FR-008).
    """

    category: str
    wanted_id: str
    declared_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class NothingDeclared:
    """A singleton category whose document the loader found nothing for.

    Distinct from a document that resolved and is empty, which is the B10 distinction this
    endpoint is the easiest place to lose.
    """

    category: str
    reason: str


@dataclass(frozen=True, slots=True)
class WindowOutsideCoverage:
    """A window a series does not declare every period of, named rather than truncated.

    Returning the rows that happen to fall inside is the fifth way of managing an uncovered
    date, beside interpolating, extrapolating, carrying forward and snapping -- and like those
    four it produces an answer indistinguishable from a correct one (020 FR-046).
    """

    series_id: str
    asked: tuple[str, str]
    covers: tuple[str, str] | None
    missing: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class WindowMalformed:
    """A window that is not a window: an end in the wrong shape, or one that ends before it
    begins. A fault in the request rather than a fact about the series, so it never reaches the
    coverage question -- an inverted window covers no period, and reporting that as *the series
    declares none of it* would name the series for the caller's typo."""

    series_id: str
    asked: tuple[str | None, str | None]
    reason: str


@dataclass(frozen=True, slots=True)
class ScenarioNotDeclared:
    """A request naming a scenario nobody declares.

    A typed refusal rather than the loader's error, which means *this data root is broken* and
    would send the reader to `data/` to look for a fault that is not there -- the trap FR-008
    names for a record id, arriving through a query parameter.
    """

    wanted_id: str
    declared_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class DeclarationFailed:
    """A malformed declaration, carrying the loader's own four fields and nothing added."""

    file: str
    field_path: str
    problem: str
    remedy: str | None


@dataclass(frozen=True, slots=True)
class FileNotRecorded:
    """A category whose resolver entry point does not say which file declared a record.

    A typed absence rather than a null, because *the loader does not expose this* and *nothing
    declared it* are different facts and a client showing a mark for one must not show it for
    the other (020 FR-053).
    """

    category: str
    reason: str


class FieldKind(Enum):
    """What a described field holds. A closed vocabulary, never a free string."""

    SCALAR = "scalar"
    DATE = "date"
    ENUM = "enum"
    LITERAL = "literal"
    RECORD = "record"
    LIST = "list"
    MAPPING = "mapping"
    UNION = "union"


@dataclass(frozen=True, slots=True)
class FieldDescription:
    """One field of the record a read returned: what it is called and what it holds.

    No label. A human label is presentation, and inventing one here would put a second
    vocabulary in a serialiser that is forbidden to add facts (020 FR-015, FR-052).
    """

    name: str
    kind: FieldKind
    of: tuple[str, ...]
    """Every record tag or enum name this field's values may be, at whatever depth the shape
    names one. A tuple because a union has several: naming only the first told a client that
    every instrument's `terms` were `BondTerms`, which is false for every enumerated one."""

    optional: bool


@dataclass(frozen=True, slots=True)
class EveryPeriodChecked:
    """Every period of the asked window was looked for, so an empty `outside` means complete."""


@dataclass(frozen=True, slots=True)
class OnlyTheEndsChecked:
    """Only the window's ends were compared against the series' declared bounds.

    An empty `outside` then means *the window lies inside the declared bounds*, which is a
    weaker statement than *every period asked for is declared*. Stated rather than left for a
    client to assume, because an absent refusal reads as full coverage.
    """

    reason: str


@dataclass(frozen=True, slots=True)
class SeriesCoverage:
    """The first and last period a series declares, so a client never has to guess a window."""

    first: str
    last: str


def container(name: str, fields: tuple[tuple[str, object], ...]) -> type:
    """One frozen record, built at import time, named for what it holds."""
    return dataclasses.make_dataclass(
        name,
        fields,
        frozen=True,
        slots=True,
        module=_MODULE,
    )


def _titled(category_id: str) -> str:
    return "".join(part.title() for part in category_id.split("-"))


def listing_of(category_id: str, *, series: bool) -> type:
    """What a keyed category's list read returns: the ids it declares, and nothing else.

    A series category also reports its declared coverage, because a mandatory two-ended window
    plus a refusal for one that reaches outside is a trap without somewhere to read the extent
    from (020 FR-045a).
    """
    coverage: tuple[tuple[str, object], ...] = (
        (("coverage", dict[str, SeriesCoverage]),) if series else ()
    )
    return container(
        f"ListingOf{_titled(category_id)}",
        (
            ("category", str),
            ("as_of", date),
            ("scenario_id", str | None),
            ("ids", tuple[str, ...]),
            *coverage,
        ),
    )


def read_of(category_id: str, record: object) -> type:
    """What a keyed category's read of one id returns: that record, or the typed refusal.

    Beside it, the field descriptors of whichever record came back and the file that declared
    it, so a client can render a category it has never heard of without knowing its schema.
    """
    return container(
        f"ReadOf{_titled(category_id)}",
        (
            ("category", str),
            ("as_of", date),
            ("scenario_id", str | None),
            ("declared_in", str | FileNotRecorded | None),
            ("fields", tuple[FieldDescription, ...]),
            ("result", record | CategoryHasNoSuchId),
        ),
    )


def document_of(category_id: str, record: object) -> type:
    """What a singleton category holding one record returns."""
    return container(
        f"DocumentOf{_titled(category_id)}",
        (
            ("category", str),
            ("as_of", date),
            ("scenario_id", str | None),
            ("declared_in", str | FileNotRecorded | None),
            ("fields", tuple[FieldDescription, ...]),
            ("result", record | NothingDeclared),
        ),
    )


def collection_of(category_id: str, record: object) -> tuple[type, type]:
    """A singleton whose document is a collection: the container, and the envelope around it.

    The container exists so the absent case stays a *tagged* refusal rather than an empty list:
    a union of a bare list and a record has no discriminator, and FR-013 requires every union in
    the document to have one.
    """
    declared = container(
        f"Declared{_titled(category_id)}",
        (("documents", tuple[record, ...]),),  # type: ignore[valid-type]
    )
    return declared, container(
        f"DocumentOf{_titled(category_id)}",
        (
            ("category", str),
            ("as_of", date),
            ("scenario_id", str | None),
            ("declared_in", str | FileNotRecorded | None),
            ("fields", tuple[FieldDescription, ...]),
            ("result", declared | NothingDeclared),
        ),
    )


def observations_of(category_id: str, observation: object) -> tuple[type, type]:
    """A windowed read of one series: the observations it covers, and what it does not.

    Both in one body. Refusing the whole window would leave a client to trim the window to what
    exists, which is a computation 021 FR-001 forbids it; returning the short list alone is the
    silent truncation FR-046 forbids. The pair is what neither is.
    """
    declared = container(
        f"Observations{_titled(category_id)}",
        (
            ("series_id", str),
            ("window", tuple[str, str] | None),
            ("covers", SeriesCoverage | None),
            ("checked", EveryPeriodChecked | OnlyTheEndsChecked),
            ("observations", tuple[observation, ...]),  # type: ignore[valid-type]
            ("outside", WindowOutsideCoverage | None),
        ),
    )
    return declared, container(
        f"WindowOf{_titled(category_id)}",
        (
            ("category", str),
            ("as_of", date),
            ("result", declared | CategoryHasNoSuchId | WindowMalformed),
        ),
    )


def answer_of(answered: object) -> type:
    """What the answer endpoint returns: the answer and its manifest, or the typed refusal."""
    return container(
        "TheAnswer",
        (
            ("question_id", str),
            ("as_of", date),
            ("result", answered | CategoryHasNoSuchId),
        ),
    )


def describe(record: type) -> tuple[FieldDescription, ...]:
    """The ordered field descriptors of one record, derived from the shape its body is encoded
    from rather than written out per category (020 FR-052)."""
    return tuple(_described(name, field) for name, field in shapes.record_of(record).fields)


def _described(name: str, field: shapes.Shape) -> FieldDescription:
    inner, optional = (
        (field.inner, True) if isinstance(field, shapes.OptionalShape) else (field, False)
    )
    return FieldDescription(name=name, kind=_kind(inner), of=_named(inner), optional=optional)


def _kind(shape: shapes.Shape) -> FieldKind:  # noqa: PLR0911 -- exhaustive match
    match shape:
        case shapes.RecordShape():
            return FieldKind.RECORD
        case shapes.EnumShape():
            return FieldKind.ENUM
        case shapes.LiteralShape():
            return FieldKind.LITERAL
        case shapes.UnionShape():
            return FieldKind.UNION
        case shapes.SequenceShape() | shapes.SetShape() | shapes.TupleShape():
            return FieldKind.LIST
        case shapes.MappingShape():
            return FieldKind.MAPPING
        case shapes.ScalarShape(python_type=python_type):
            return FieldKind.DATE if python_type is date else FieldKind.SCALAR
        case shapes.DerivedShape(inner=inner) | shapes.OptionalShape(inner=inner):
            return _kind(inner)


def _named(shape: shapes.Shape) -> tuple[str, ...]:
    """Every record tag or enum name this field's **values** may be.

    A mapping is descended by its value alone: the generic walk visits the key first, so an
    enum-keyed mapping to a record would otherwise be described by the type of its keys.
    """
    match shape:
        case shapes.RecordShape(tag=tag):
            return (tag,)
        case shapes.EnumShape(enum=enum):
            return (enum.__name__,)
        case shapes.MappingShape(value=value):
            return _named(value)
        case _:
            return tuple(
                dict.fromkeys(name for child in shapes.children_of(shape) for name in _named(child))
            )
