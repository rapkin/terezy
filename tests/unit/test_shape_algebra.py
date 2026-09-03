"""The shape algebra: one description per annotated type, and two folds over it.

Everything this feature serves goes through `plan_of`. A record it cannot describe is a loud
failure naming the record and the field, never a field quietly dropped or serialised as the text
of its `repr` (020 FR-003, FR-011).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pytest

from terezy.api.http import shapes
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef


@dataclass(frozen=True, slots=True)
class _Leaf:
    name: str


@dataclass(frozen=True, slots=True)
class _Loop:
    inner: _Loop | None


@dataclass(frozen=True, slots=True)
class _Branch:
    leaf: _Leaf
    when: date
    count: int
    side: Literal["in", "out"]
    currency: Currency
    maybe: str | None
    many: tuple[_Leaf, ...]
    pair: tuple[date, date]
    keyed: dict[str, _Leaf]
    unique: frozenset[str]


def test_a_scalar_is_its_own_type() -> None:
    assert shapes.plan_of(str) == shapes.ScalarShape(str)
    assert shapes.plan_of(date) == shapes.ScalarShape(date)


def test_a_literal_carries_its_values() -> None:
    assert shapes.plan_of(Literal["in", "out"]) == shapes.LiteralShape(("in", "out"))


def test_an_enum_carries_its_class() -> None:
    assert shapes.plan_of(Currency) == shapes.EnumShape(Currency)


def test_a_record_carries_its_tag_and_its_fields() -> None:
    planned = shapes.plan_of(_Leaf)
    assert isinstance(planned, shapes.RecordShape)
    assert planned.record is _Leaf
    assert planned.tag.endswith("._Leaf")
    assert [name for name, _ in planned.fields] == ["name"]


def test_every_arm_is_reachable_from_one_record() -> None:
    planned = shapes.plan_of(_Branch)
    assert isinstance(planned, shapes.RecordShape)
    by_name = dict(planned.fields)
    assert isinstance(by_name["leaf"], shapes.RecordShape)
    assert by_name["when"] == shapes.ScalarShape(date)
    assert by_name["side"] == shapes.LiteralShape(("in", "out"))
    assert by_name["currency"] == shapes.EnumShape(Currency)
    assert by_name["maybe"] == shapes.OptionalShape(shapes.ScalarShape(str))
    assert isinstance(by_name["many"], shapes.SequenceShape)
    assert isinstance(by_name["pair"], shapes.TupleShape)
    assert len(by_name["pair"].elements) == 2
    assert isinstance(by_name["keyed"], shapes.MappingShape)
    assert by_name["unique"] == shapes.SetShape(shapes.ScalarShape(str))


def test_the_same_record_plans_to_the_same_shape() -> None:
    """Memoised by record, because `Provenance` appears under hundreds of fields."""
    assert shapes.plan_of(_Leaf) is shapes.plan_of(_Leaf)


def test_provenance_gains_the_derived_verdict() -> None:
    """FR-018: a client renders the mark without reimplementing the one-taints-all asymmetry."""
    planned = shapes.plan_of(Provenance)
    assert isinstance(planned, shapes.RecordShape)
    assert [name for name, _ in planned.fields] == ["sources", "is_unverified"]
    assert dict(planned.fields)["is_unverified"] == shapes.DerivedShape(
        shapes.ScalarShape(bool), shapes.IS_UNVERIFIED
    )


def test_money_needs_no_special_case() -> None:
    planned = shapes.plan_of(Money)
    assert isinstance(planned, shapes.RecordShape)
    assert [name for name, _ in planned.fields] == ["amount", "currency", "provenance"]


def test_a_union_of_records_is_a_union_shape() -> None:
    planned = shapes.plan_of(_Leaf | _Branch)
    assert isinstance(planned, shapes.UnionShape)
    assert all(isinstance(member, shapes.RecordShape) for member in planned.members)


def test_an_annotation_with_no_arm_fails_naming_it() -> None:
    @dataclass(frozen=True, slots=True)
    class _Callable:
        run: object

    with pytest.raises(shapes.UnserialisableAnnotationError) as raised:
        shapes.plan_of(_Callable)
    assert "_Callable" in str(raised.value)
    assert "run" in str(raised.value)


def test_a_cycle_fails_rather_than_recurring_for_ever() -> None:
    with pytest.raises(shapes.UnserialisableAnnotationError) as raised:
        shapes.plan_of(_Loop)
    assert "_Loop" in str(raised.value)


def test_a_records_hints_resolve_through_the_fallback_namespace() -> None:
    """The fifteen records whose annotations name a TYPE_CHECKING import (research R3).

    `FundDeclaration` is one of them and is a response type, so this is not a hypothetical.
    """
    planned = shapes.plan_of(FundDeclaration)
    assert isinstance(planned, shapes.RecordShape)
    assert planned.fields


def test_a_source_ref_keeps_the_five_fields_a_client_needs() -> None:
    planned = shapes.plan_of(SourceRef)
    assert isinstance(planned, shapes.RecordShape)
    assert [name for name, _ in planned.fields] == [
        "id",
        "citation",
        "retrieved_on",
        "verified_on",
        "kind",
    ]
