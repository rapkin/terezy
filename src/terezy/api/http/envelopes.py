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
from typing import TYPE_CHECKING, Final

from terezy.api.http import shapes

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable, Mapping

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


@dataclass(frozen=True, slots=True)
class ParameterMalformed:
    """One request parameter the route could not read, as the validator reported it.

    ``location`` verbatim rather than a name lifted out of it: which parameter and where it was
    looked for are one fact, and splitting them would let a query parameter and a path parameter
    of the same name arrive indistinguishable.
    """

    location: tuple[str, ...]
    given: str | None
    problem: str


@dataclass(frozen=True, slots=True)
class RequestMalformed:
    """A well-formed request whose parameters could not be read, as a tagged body.

    The framework's own validation body carries no tag, so a client generated from the document
    has nothing to narrow on and 021 FR-004's exhaustive switch cannot reach it -- the same
    prohibition 020 FR-016 puts on a refusal expressed by a status code alone. Every reported
    parameter is carried: one alone would send a caller round the loop once per fault.
    """

    parameters: tuple[ParameterMalformed, ...]
    reason: str


MALFORMED_REASON: Final[str] = (
    "a parameter of this request could not be read. No default is substituted for one that is "
    "missing or malformed: a read as of a date nobody asked for answers a question nobody asked."
)


def malformed_from(reported: Iterable[Mapping[str, object]]) -> RequestMalformed:
    """The validator's own findings as a refusal record, with nothing added and nothing dropped.

    ``input`` is absent from the request rather than the string ``"None"`` when it is ``None``: a
    query parameter is either a string or not there, and the two are what a caller has to tell
    apart to fix the URL.
    """
    return RequestMalformed(
        parameters=tuple(
            ParameterMalformed(
                location=tuple(str(part) for part in _sequence(fault.get("loc"))),
                given=None if (given := fault.get("input")) is None else str(given),
                problem=str(fault.get("msg", "")),
            )
            for fault in reported
        ),
        reason=MALFORMED_REASON,
    )


def _sequence(location: object) -> tuple[object, ...]:
    return tuple(location) if isinstance(location, tuple | list) else ()


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
class NoWindowAsked:
    """Every declared observation is returned, and nothing was checked for absence.

    A read with no window asks about no period, so there is nothing a refusal could name -- and
    saying every period was checked would be the stronger claim, false for a series whose
    declaration is allowed to have a gap in it.
    """


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


_CONTAINERS: Final[dict[tuple[str, tuple[tuple[str, object], ...]], type]] = {}
"""Both folds over a container -- :func:`terezy.api.http.shapes.plan_of` and
:func:`terezy.api.http.models.model_of` -- memoise by the record's **identity** and evict nothing,
so a record minted per call missed both caches and grew them instead. The field set is in the key
rather than the name alone: a category whose record changed would otherwise be served under the
first application's shape.
"""


def container(name: str, fields: tuple[tuple[str, object], ...]) -> type:
    """One frozen record, named for what it holds."""
    known = _CONTAINERS.get((name, fields))
    if known is not None:
        return known
    built = dataclasses.make_dataclass(
        name,
        fields,
        frozen=True,
        slots=True,
        module=_MODULE,
    )
    _CONTAINERS[(name, fields)] = built
    return built


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
            ("checked", NoWindowAsked | EveryPeriodChecked | OnlyTheEndsChecked),
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


def projection_of(projected: object, no_such: object) -> type:
    """What the candidate endpoint returns: one candidate's projection, or one of two refusals.

    Two and no third (027 FR-011): the **question** is not declared, which is a wrong URL, and
    the **key** names no evaluated candidate of this answer, which is a stale client. They are
    separate records because the remedies are. A candidate whose projection could not be produced
    never became an outcome, so it carries no key and has no address here -- what the card meets
    instead is a bar the arm states no flow for, which lives in the body.
    """
    return container(
        "TheCandidateProjection",
        (
            ("question_id", str),
            ("candidate_key", str),
            ("as_of", date),
            ("result", projected | no_such | CategoryHasNoSuchId),  # type: ignore[operator]
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
