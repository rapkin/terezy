"""What the registry holds, per category: how much, from which files, resting on what.

Digests are `terezy.data.manifest`'s own -- two functions hashing the same file is one fact in
two places, and the one that drifts is whichever a reader did not open. The merged mark folds
`terezy.core.primitives.provenance.merge` over every record in the category, so the monoid stays
the single definition of what a union of marks is (020 FR-009, FR-010).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.api.http import categories, shapes
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance
from terezy.data import citation_policy, manifest

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable
    from datetime import date
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileRef:
    """One declaring file and the digest of its bytes."""

    file: str
    version: str


@dataclass(frozen=True, slots=True)
class KeyedSummary:
    """A category a declared string selects from: how many ids, and what they rest on."""

    category: str
    directory: str
    citations: citation_policy.CitationsRequired | citation_policy.CitationsExempt
    declared_ids: int
    files: tuple[FileRef, ...]
    provenance: Provenance
    unverified_sources: int


@dataclass(frozen=True, slots=True)
class SingletonSummary:
    """A per-owner document: **whether it resolved**, which a count of zero cannot say.

    A singleton reported as a count would say `0` for a document that resolved fine, which is
    the same body a caller would get for one the loader found nothing for.
    """

    category: str
    directory: str
    citations: citation_policy.CitationsRequired | citation_policy.CitationsExempt
    resolved: bool
    files: tuple[FileRef, ...]
    provenance: Provenance
    unverified_sources: int


@dataclass(frozen=True, slots=True)
class RegistrySummary:
    as_of: date
    scenario_id: str | None
    categories: tuple[KeyedSummary | SingletonSummary, ...]


def of(ask: categories.Ask, *, as_of: date) -> RegistrySummary:
    """The whole registry, one row per category, in the category table's own order."""
    return RegistrySummary(
        as_of=as_of,
        scenario_id=ask.scenario_id,
        categories=tuple(_summary(category, ask) for category in categories.CATEGORIES),
    )


def _summary(category: categories.Category, ask: categories.Ask) -> KeyedSummary | SingletonSummary:
    citations = citation_policy.verdict_for(categories.directory_of(category))
    match category.shape:
        case categories.Keyed(resolve=resolve, record=record):
            resolved = resolve(ask)
            marks = _merged(record, resolved.records.values())
            files = (
                ()
                if isinstance(resolved.files, categories.NoFileMap)
                else _refs(resolved.files.values())
            )
            return KeyedSummary(
                category=category.id,
                directory=categories.directory_of(category),
                citations=citations,
                declared_ids=len(resolved.records),
                files=files,
                provenance=marks,
                unverified_sources=len(prov.unverified_sources(marks)),
            )
        case categories.Document(resolve=resolve, record=record):
            single = resolve(ask)
            marks = _merged(record, () if single.record is None else (single.record,))
            return SingletonSummary(
                category=category.id,
                directory=categories.directory_of(category),
                citations=citations,
                resolved=single.record is not None,
                files=() if single.file is None else _refs((single.file,)),
                provenance=marks,
                unverified_sources=len(prov.unverified_sources(marks)),
            )
        case categories.Collection(resolve=resolve, record=record):
            many = resolve(ask)
            marks = _merged(record, many.records)
            return SingletonSummary(
                category=category.id,
                directory=categories.directory_of(category),
                citations=citations,
                resolved=many.file is not None,
                files=() if many.file is None else _refs((many.file,)),
                provenance=marks,
                unverified_sources=len(prov.unverified_sources(marks)),
            )


def _merged(record: object, values: Iterable[object]) -> Provenance:
    """Every mark inside every record of the category, folded through the monoid."""
    shape = shapes.plan_of(record)
    return prov.merge_all(
        held
        for value in values
        for held in shapes.records_in(shape, value)
        if isinstance(held, Provenance)
    )


def _refs(paths: Iterable[Path]) -> tuple[FileRef, ...]:
    unique = {manifest.file_name(path): path for path in paths}
    return tuple(
        FileRef(file=name, version=manifest.file_version(path))
        for name, path in sorted(unique.items())
    )
