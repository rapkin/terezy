"""What the registry holds, per category: how much, from which files, resting on what.

Digests are `terezy.data.manifest`'s own -- two functions hashing the same file is one fact in
two places, and the one that drifts is whichever a reader did not open. The merged mark folds
`terezy.core.primitives.provenance.merge` over every record in the category, so the monoid stays
the single definition of what a union of marks is (020 FR-009, FR-010).

The index carries the *verdict* of that fold and the whole list is read at a second endpoint.
Serialising every `SourceRef` behind every category put a ~300-character citation on each of the
19 500 observation rows the official-rate series declares, and the index page that reads counts
and dates paid 2.6 MB for them.
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
class NoSourceCited:
    """A category resting on no cited source at all.

    Not a mark: :data:`terezy.core.primitives.provenance.EMPTY` is the identity of the merge, and
    reading it as unverified would make the mark universal and therefore meaningless.
    """


@dataclass(frozen=True, slots=True)
class SourcesUnverified:
    """At least one source carries no verification date, so the whole category is marked.

    One unverified source taints the fold, which is the asymmetry the monoid states; the count is
    how many are responsible and `/registry/sources` is which.
    """

    sources: int
    unverified: int
    latest_retrieved_on: date


@dataclass(frozen=True, slots=True)
class EverySourceVerified:
    """Every source carries a verification date. The earliest is the weakest claim the category
    makes about itself, and the one a reader acts on."""

    sources: int
    earliest_verified_on: date
    latest_retrieved_on: date


CategoryMark = NoSourceCited | SourcesUnverified | EverySourceVerified


@dataclass(frozen=True, slots=True)
class KeyedSummary:
    """A category a declared string selects from: how many ids, and what they rest on."""

    category: str
    directory: str
    citations: citation_policy.CitationsRequired | citation_policy.CitationsExempt
    declared_ids: int
    files: tuple[FileRef, ...]
    mark: CategoryMark


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
    mark: CategoryMark


@dataclass(frozen=True, slots=True)
class RegistrySummary:
    as_of: date
    scenario_id: str | None
    categories: tuple[KeyedSummary | SingletonSummary, ...]


@dataclass(frozen=True, slots=True)
class CategorySources:
    """Every cited source one category rests on, folded through the monoid and not trimmed."""

    category: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class RegistrySources:
    as_of: date
    scenario_id: str | None
    categories: tuple[CategorySources, ...]


def of(ask: categories.Ask, *, as_of: date) -> RegistrySummary:
    """The whole registry, one row per category, in the category table's own order."""
    return RegistrySummary(
        as_of=as_of,
        scenario_id=ask.scenario_id,
        categories=tuple(row for row, _ in _rows(ask)),
    )


def sources_of(ask: categories.Ask, *, as_of: date) -> RegistrySources:
    """The same fold, unsummarised. A second route rather than a `detail` parameter on the first:
    one operation answering two body types has no discriminator for a generated client to narrow
    on, which is what FR-013 forbids of every union in the document."""
    return RegistrySources(
        as_of=as_of,
        scenario_id=ask.scenario_id,
        categories=tuple(
            CategorySources(category=row.category, provenance=marks) for row, marks in _rows(ask)
        ),
    )


def _rows(
    ask: categories.Ask,
) -> Iterable[tuple[KeyedSummary | SingletonSummary, Provenance]]:
    """One pass, so the summarised mark and the served source list cannot disagree about the
    fold and no category is resolved twice to produce them."""
    return [_row(category, ask) for category in categories.CATEGORIES]


def _row(
    category: categories.Category, ask: categories.Ask
) -> tuple[KeyedSummary | SingletonSummary, Provenance]:
    citations = citation_policy.verdict_for(categories.directory_of(category))
    match category.shape:
        case categories.Keyed(resolve=resolve, record=record):
            resolved = resolve(ask)
            marks = _merged(record, resolved.records.values())
            files = (
                ()
                if isinstance(resolved.files, categories.NoFileMap)
                else _refs(resolved.files.values(), root=ask.root)
            )
            return (
                KeyedSummary(
                    category=category.id,
                    directory=categories.directory_of(category),
                    citations=citations,
                    declared_ids=len(resolved.records),
                    files=files,
                    mark=_mark(marks),
                ),
                marks,
            )
        case categories.Document(resolve=resolve, record=record):
            single = resolve(ask)
            marks = _merged(record, () if single.record is None else (single.record,))
            return (
                SingletonSummary(
                    category=category.id,
                    directory=categories.directory_of(category),
                    citations=citations,
                    resolved=single.record is not None,
                    files=() if single.file is None else _refs((single.file,), root=ask.root),
                    mark=_mark(marks),
                ),
                marks,
            )
        case categories.Collection(resolve=resolve, record=record):
            many = resolve(ask)
            marks = _merged(record, many.records)
            return (
                SingletonSummary(
                    category=category.id,
                    directory=categories.directory_of(category),
                    citations=citations,
                    resolved=many.file is not None,
                    files=() if many.file is None else _refs((many.file,), root=ask.root),
                    mark=_mark(marks),
                ),
                marks,
            )


def _mark(merged: Provenance) -> CategoryMark:
    """The fold's verdict, in the three states a reader acts on differently."""
    if not merged.sources:
        return NoSourceCited()
    latest = max(ref.retrieved_on for ref in merged.sources)
    unverified = prov.unverified_sources(merged)
    if unverified:
        return SourcesUnverified(
            sources=len(merged.sources),
            unverified=len(unverified),
            latest_retrieved_on=latest,
        )
    return EverySourceVerified(
        sources=len(merged.sources),
        earliest_verified_on=min(
            ref.verified_on for ref in merged.sources if ref.verified_on is not None
        ),
        latest_retrieved_on=latest,
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


def _refs(paths: Iterable[Path], *, root: Path) -> tuple[FileRef, ...]:
    """Named the way the manifest names them, root-level files included.

    A file at the data root is named by its bare name: keeping the parent would name it after
    the data root's own directory, which is one machine's layout, so two checkouts would
    describe one declaration two ways.
    """
    unique = {
        (path.name if path.parent == root else manifest.file_name(path)): path for path in paths
    }
    return tuple(
        FileRef(file=name, version=manifest.file_version(path))
        for name, path in sorted(unique.items())
    )
