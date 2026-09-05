"""What a client switches on: a distinct tag per record, and a discriminator on every union.

Everything here is **discovered by walking the response types**. A hand-written list of union
members or of record names would be the prose enumeration of things declared elsewhere the
constitution says is a check or is not written -- and here it can be the check (020 FR-011 to
FR-015, FR-017, FR-018, FR-052, SC-004, SC-005, SC-005a, SC-005b, SC-008, SC-008a).
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Any

import pytest

from terezy.api.answer import AnsweredQuestion
from terezy.api.http import categories, encode, envelopes, service, shapes, tags
from terezy.api.http.summary import RegistrySummary
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from tests.data_roots import SHIPPED

DATA_ROOT = SHIPPED


def _reachable() -> list[shapes.RecordShape]:
    seen: dict[type, shapes.RecordShape] = {}
    for root in _built():
        for node in shapes.walk(root):
            if isinstance(node, shapes.RecordShape):
                seen.setdefault(node.record, node)
    return list(seen.values())


def _built() -> list[shapes.Shape]:
    """The envelopes the application builds, planned from the category table.

    Read off the table rather than off the registered routes, because a route's
    `response_model` is the generated pydantic model and the walk is over the shapes those
    models were built from.
    """
    roots: list[shapes.Shape] = [
        shapes.plan_of(RegistrySummary),
        shapes.plan_of(envelopes.answer_of(AnsweredQuestion)),
    ]
    for category in categories.CATEGORIES:
        shape = category.shape
        match shape:
            case categories.Keyed(record=record):
                roots.append(shapes.plan_of(envelopes.listing_of(category.id, series=False)))
                roots.append(shapes.plan_of(envelopes.read_of(category.id, record)))
            case categories.Document(record=record):
                roots.append(shapes.plan_of(envelopes.document_of(category.id, record)))
            case categories.Collection(record=record):
                _, envelope = envelopes.collection_of(category.id, record)
                roots.append(shapes.plan_of(envelope))
    return roots


@pytest.mark.contract
def test_every_reachable_record_has_a_distinct_tag() -> None:
    reachable = _reachable()
    assert len(reachable) > 100, "the walk found suspiciously little to check"
    counted = Counter(node.tag for node in reachable)
    assert not [tag for tag, count in counted.items() if count > 1]
    names = Counter(node.model_name for node in reachable)
    assert not [name for name, count in names.items() if count > 1]


@pytest.mark.contract
def test_a_colliding_record_name_is_caught() -> None:
    """The mutation, performed: two same-leaf modules declaring one name collide."""

    @dataclasses.dataclass(frozen=True, slots=True)
    class Collider:
        held: str

    Collider.__module__ = "somewhere.provenance"
    assert tags.tag_of(Collider) == "provenance.Collider"
    Collider.__name__ = "SourceRef"
    assert tags.tag_of(Collider) == tags.tag_of(SourceRef)


@pytest.mark.contract
def test_the_override_table_is_empty_and_consulted_first() -> None:
    assert tags.OVERRIDES == {}
    stated = dict(tags.OVERRIDES)
    stated[Money] = "money.Restated"
    assert stated[Money] != tags.tag_of(Money)


@pytest.mark.contract
def test_every_union_of_records_is_discriminated() -> None:
    """`oneOf` with a `discriminator` mapping naming every member, in the document itself."""
    app = service.create_app(DATA_ROOT, client=None)
    schemas: dict[str, Any] = app.openapi()["components"]["schemas"]
    unions = [
        schema
        for held in schemas.values()
        for schema in _subschemas(held)
        if len(_refs(schema)) > 1
    ]
    assert unions, "no union reached the document, so this check would pass vacuously"
    of_records = [union for union in unions if _all_tagged(union, schemas)]
    undiscriminated = [union for union in of_records if "discriminator" not in union]
    assert not undiscriminated, (
        f"{len(undiscriminated)} union(s) of records carry no discriminator, so a client has to "
        "narrow by shape rather than by tag"
    )
    for union in of_records:
        assert len(union["discriminator"]["mapping"]) == len(_refs(union))
        assert union["discriminator"]["propertyName"] == encode.TAG_FIELD


@pytest.mark.contract
def test_the_unions_a_discriminator_cannot_reach_are_the_ones_pinned() -> None:
    """A union with a non-record arm cannot carry a discriminator; there is exactly one.

    `ExitChoice` mixes two records with two single-member enum sentinels, and an enum arm has no
    `tag` to switch on. Pinned so that a second such union is a deliberate edit -- a client
    narrowing by shape is what FR-013 exists to prevent, and this is where the exception lives.
    """
    schemas: dict[str, Any] = service.create_app(DATA_ROOT, client=None).openapi()["components"][
        "schemas"
    ]
    mixed = {
        union.get("title", "")
        for held in schemas.values()
        for union in _subschemas(held)
        if len(_refs(union)) > 1 and not _all_tagged(union, schemas)
    }
    assert mixed == {"Route Out"}


def _all_tagged(union: dict[str, Any], schemas: dict[str, Any]) -> bool:
    """Whether every member of this union is a record model rather than an enum."""
    return all(
        "tag" in schemas[ref.rsplit("/", 1)[-1]].get("properties", {}) for ref in _refs(union)
    )


def _refs(schema: dict[str, Any]) -> list[str]:
    """The member references of one union node, however the emitter spelled the union.

    `anyOf` as well as `oneOf`: pydantic emits the first for a plain union and the second only
    where a discriminator is set, so a check written over `oneOf` alone would look only at the
    unions that already pass.
    """
    members = schema.get("oneOf", schema.get("anyOf", []))
    return [member["$ref"] for member in members if isinstance(member, dict) and "$ref" in member]


def _subschemas(schema: object) -> list[dict[str, Any]]:
    if isinstance(schema, dict):
        return [schema, *[held for value in schema.values() for held in _subschemas(value)]]
    if isinstance(schema, list):
        return [held for value in schema for held in _subschemas(value)]
    return []


@pytest.mark.contract
def test_a_refusal_carries_its_own_fields_and_nothing_added() -> None:
    """Swept both ways, with the tag carved out because FR-011 requires exactly that addition."""
    for node in _reachable():
        declared = {field.name for field in dataclasses.fields(node.record)}
        served = {name for name, _ in node.fields} - {encode.TAG_FIELD}
        derived = {name for name, field in node.fields if isinstance(field, shapes.DerivedShape)}
        assert served - derived == declared, node.tag
        assert encode.TAG_FIELD not in declared, f"{node.tag} carries a field named `tag`"


@pytest.mark.contract
def test_the_union_members_with_no_reason_are_the_ones_pinned() -> None:
    """Discovered by the walk and split in two, so a tenth reason-less **refusal** is red.

    Pinning only the nine would not do it: the discovery cannot tell a refusal from a
    declaration by shape, so the ratchet has to account for every reason-less union member. A
    new declaration record joins the second set with a one-line edit; a new refusal that forgot
    its reason has nowhere to go that does not say so.
    """
    discovered = _union_members_without_a_reason()
    assert discovered == WITHOUT_A_REASON | DECLARATIONS_WITHOUT_A_REASON
    assert not WITHOUT_A_REASON & DECLARATIONS_WITHOUT_A_REASON


@pytest.mark.contract
def test_each_pinned_refusal_is_reachable_and_reason_less() -> None:
    by_tag = {node.tag: node for node in _reachable()}
    for tag in WITHOUT_A_REASON:
        assert tag in by_tag, f"{tag} is pinned as reason-less but reaches no response type"
        assert not _has_reason(by_tag[tag])


WITHOUT_A_REASON = frozenset(
    {
        "answer.NoHorizonDeclared",
        "answer.NoSubjectDeclared",
        "answer.AmountForAnUndeclaredStream",
        "answer.StreamWithNoAmount",
        "answer.BenchmarkOutsideTheSubjects",
        "answer.BenchmarkYieldsSeveralCandidates",
        "answer.TwoIdenticalHorizons",
        "answer.PlanForNothing",
        "answer.BenchmarkYieldsNoCandidate",
    }
)
"""The nine refusals that carry no `reason`.

Eight are the whole of `Answer`'s own `Refused` union; the ninth is a refusal arm of
`SectionOutcome` reached through `Answer.sections`, so it belongs to no union whose name ends in
`Refused` and an audit enumerating the refusal unions finds eight and stops. The schema marks
`reason` optional and a client narrows on the tag (owner decision 2026-09-03, answer 3); closing
the gap in the core is the `a-reason-on-every-refusal` future entry.
"""

DECLARATIONS_WITHOUT_A_REASON = frozenset(
    {
        "access.InstrumentAccess",
        "answer.Answer",
        "answer.AnsweredQuestion",
        "answer.CoveredByThePlan",
        "answer.DeclaredSubject",
        "answer.PartialExitWouldBeNeeded",
        "answer.SubjectNotAssessed",
        "answer.SubjectReached",
        "answer.SubjectUndeclared",
        "answer.SubjectUnreached",
        "answer.UndeclaredSubject",
        "candidates.CandidateCeiling",
        "candidates.CandidateSurvey",
        "candidates.NothingNeedsToConnect",
        "channels.FxChannel",
        "citation_policy.CitationsRequired",
        "composed.SegmentBound",
        "early_exit.QuotationHolds",
        "envelopes.DeclaredSeeds",
        "envelopes.DeclaredSpendable",
        "envelopes.TaxPositions",
        "fund.FundAssumptions",
        "fund.FundDeclaration",
        "goal.Goal",
        "groups.InstrumentGroup",
        "interface.Assumptions",
        "interface.BondTerms",
        "interface.EnumeratedTerms",
        "interface.InstrumentDeclaration",
        "interface.TaxClass",
        "legs.Route",
        "loader.ScenarioDeclaration",
        "official_rate.OfficialRateSeries",
        "path.ComposedExit",
        "path.ComposedPath",
        "path.DeclaredExit",
        "path.FundingPath",
        "question.Question",
        "rates.NominalRate",
        "scheme.CreditingDestination",
        "scheme.TaxationScheme",
        "seeds.BasisKnown",
        "series.CpiSeries",
        "series.InflationAssumption",
        "staleness.ObservationKind",
        "streams.IncomeStream",
        "summary.KeyedSummary",
        "summary.SingletonSummary",
        "tuple.Comparison",
        "venues.Venue",
        "working_day.DeclaredHoliday",
        "working_day.DeclaredRestDay",
        "working_day.DeclaredWorkingDay",
        "working_day.WorkingDayCalendar",
        "year.AssessmentRules",
    }
)
"""Union members with no `reason` that are not refusals -- declarations, results and envelopes.

Here so that the discovery above can be complete. A record joining this set is a new thing a
response can hold; a record that belongs in the set above and is put here instead is a refusal
declared to be a declaration, which is the one mistake this split cannot catch and a review can.
"""


def _union_members_without_a_reason() -> frozenset[str]:
    return frozenset(
        member.tag
        for root in _built()
        for node in shapes.walk(root)
        if isinstance(node, shapes.UnionShape)
        for member in node.members
        if isinstance(member, shapes.RecordShape) and not _has_reason(member)
    )


def _has_reason(member: shapes.RecordShape) -> bool:
    return "reason" in {name for name, _ in member.fields}


@pytest.mark.contract
def test_every_money_field_carries_its_provenance() -> None:
    """Swept off the response types rather than sampled, so a field added later is inside it."""
    money = [node for node in _reachable() if node.record is Money]
    assert money, "no money reached a response type, so this check would pass vacuously"
    for node in money:
        assert "provenance" in {name for name, _ in node.fields}


@pytest.mark.contract
def test_every_source_carries_the_five_fields_and_the_derived_verdict() -> None:
    marks = [node for node in _reachable() if node.record is Provenance]
    assert marks
    for node in marks:
        names = [name for name, _ in node.fields]
        assert names == ["sources", "is_unverified"]
    source = next(node for node in _reachable() if node.tag == "provenance.SourceRef")
    assert [name for name, _ in source.fields] == [
        "id",
        "citation",
        "retrieved_on",
        "verified_on",
        "kind",
    ]


@pytest.mark.contract
def test_a_field_descriptor_matches_the_record_it_describes() -> None:
    """Swept in both directions: no descriptor omits a field and none names one that is absent."""
    for node in _reachable():
        described = envelopes.describe(node.record)
        assert [held.name for held in described] == [
            name for name, _ in node.fields if name != encode.TAG_FIELD
        ]
        assert not any(hasattr(held, "label") for held in described)
