"""The body is reproducible, and the mark is on every figure that has one.

`frozenset` iteration order varies with `PYTHONHASHSEED`, so an unordered collection serialised
in its own order gives one body in one process and a different one in the next -- green in a test
session and different on a colleague's machine. Eleven fields in the core are `frozenset`-typed
and ten of them are not provenance, so the rule is the serialiser's rather than each call site's
(020 FR-019).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import Enum

import pytest

from terezy.api.http import encode, shapes
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.ramp import CostComponent, OneWayCost, RoundTripCost


class _Side(Enum):
    OUT = "out"
    IN = "in"


@dataclass(frozen=True, slots=True)
class _Sets:
    words: frozenset[str]
    numbers: frozenset[int]
    sides: frozenset[_Side]
    by_side: dict[_Side, int]
    by_year: dict[int, str]


def _encoded(value: object) -> dict[str, encode.Json]:
    return _obj(encode.encode(shapes.plan_of(type(value)), value))


def _obj(value: encode.Json) -> dict[str, encode.Json]:
    assert isinstance(value, dict)
    return value


def _rows(value: encode.Json) -> list[encode.Json]:
    assert isinstance(value, list)
    return value


def test_a_set_of_strings_is_sorted() -> None:
    body = _encoded(
        _Sets(
            words=frozenset({"zulu", "alpha", "mike"}),
            numbers=frozenset({3, 1, 2}),
            sides=frozenset({_Side.OUT, _Side.IN}),
            by_side={_Side.OUT: 2, _Side.IN: 1},
            by_year={2027: "b", 2026: "a"},
        )
    )
    assert body["words"] == ["alpha", "mike", "zulu"]
    assert body["numbers"] == [1, 2, 3]
    assert body["sides"] == ["in", "out"]
    assert list(_obj(body["by_side"])) == ["in", "out"]
    assert list(_obj(body["by_year"])) == ["2026", "2027"]


def test_a_set_of_records_is_sorted_by_its_encoded_form() -> None:
    """One rule for every element type, so there is no per-record key table to go stale."""
    sources = prov.of(
        [
            SourceRef("zulu", "https://z", date(2026, 1, 1), None, "cpi"),
            SourceRef("alpha", "https://a", date(2026, 1, 1), date(2026, 2, 1), "cpi"),
        ]
    )
    body = _encoded(sources)
    assert [_obj(source)["id"] for source in _rows(body["sources"])] == ["alpha", "zulu"]


def test_provenance_carries_the_five_fields_and_the_derived_verdict() -> None:
    sources = prov.of([SourceRef("a", "https://a", date(2026, 1, 1), None, "cpi")])
    body = _encoded(sources)
    assert body["tag"] == "provenance.Provenance"
    assert body["is_unverified"] is True
    assert _rows(body["sources"])[0] == {
        "tag": "provenance.SourceRef",
        "id": "a",
        "citation": "https://a",
        "retrieved_on": "2026-01-01",
        "verified_on": None,
        "kind": "cpi",
    }


def test_one_verified_source_among_unverified_still_marks_the_figure() -> None:
    sources = prov.of(
        [
            SourceRef("a", "https://a", date(2026, 1, 1), date(2026, 2, 1), ""),
            SourceRef("b", "https://b", date(2026, 1, 1), None, ""),
        ]
    )
    body = _encoded(sources)
    assert body["is_unverified"] is prov.is_unverified(sources)
    assert body["is_unverified"] is True


def test_money_carries_its_amount_currency_and_mark() -> None:
    amount = Money(1234.5, Currency.UAH, prov.EMPTY)
    body = _encoded(amount)
    assert body["amount"] == 1234.5
    assert body["currency"] == "UAH"
    assert _obj(body["provenance"])["is_unverified"] is False


def test_a_figure_that_is_not_a_number_is_refused_rather_than_written() -> None:
    """`NaN` and `Infinity` are not JSON, and a body carrying one is a body a client cannot read."""
    with pytest.raises(encode.UnencodableValueError):
        _encoded(Money(float("nan"), Currency.UAH, prov.EMPTY))


@pytest.mark.contract
def test_two_records_with_one_field_set_serialise_differently() -> None:
    """Principle VI's prohibition at the wire: a one-way figure is never a round-trip one.

    `OneWayCost` and `RoundTripCost` have the same nine fields in the same order, and mypy is
    what has kept them apart since feature 002. Serialised without a tag they are one shape.
    """
    one_way_shape = shapes.record_of(OneWayCost)
    round_trip_shape = shapes.record_of(RoundTripCost)
    assert [name for name, _ in one_way_shape.fields] == [
        name for name, _ in round_trip_shape.fields
    ]

    amount = Money(10.0, Currency.UAH, prov.EMPTY)
    one_way = OneWayCost(
        sent=amount,
        arrived=amount,
        components={CostComponent.FIXED_FEE: amount},
        fraction=0.0,
        spreads_over_reference=(),
        channels_applied=(),
        provenance=prov.EMPTY,
        staleness=StalenessVerdict(assessed=(), stale=()),
        by_segment=(),
    )
    round_trip = RoundTripCost(
        sent=amount,
        arrived=amount,
        components={CostComponent.FIXED_FEE: amount},
        fraction=0.0,
        spreads_over_reference=(),
        channels_applied=(),
        provenance=prov.EMPTY,
        staleness=StalenessVerdict(assessed=(), stale=()),
        by_segment=(),
    )
    one_way_body = _obj(encode.encode(one_way_shape, one_way))
    round_trip_body = _obj(encode.encode(round_trip_shape, round_trip))

    assert one_way_body != round_trip_body
    assert one_way_body["tag"] == "ramp.OneWayCost"
    assert round_trip_body["tag"] == "ramp.RoundTripCost"
    assert {key: value for key, value in one_way_body.items() if key != "tag"} == {
        key: value for key, value in round_trip_body.items() if key != "tag"
    }


def test_the_encoding_is_json() -> None:
    """Whatever the encoder returns is what `json.dumps` will accept, with no custom encoder."""
    json.dumps(_encoded(prov.of([SourceRef("a", "https://a", date(2026, 1, 1), None, "")])))
