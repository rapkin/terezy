"""SC-014 and FR-024: a candidate set never looks cleaner than the registry behind it.

Walked rather than sampled: a sampled assertion passes while one sourced family is silently
dropped, and a dropped mark is this project's top-severity defect.

What these do not cover is the per-drop half -- 010's refusal records carry no provenance --
which is the `provenance-on-a-refusal` future entry.
"""

from __future__ import annotations

from datetime import date, timedelta

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.results.candidates import CandidateSet
from terezy.core.routes.path import exit_segments_of, segments_of
from tests import candidate_registries as fixtures


def _set(as_of: date = fixtures.AS_OF) -> CandidateSet:
    registries = fixtures.shipped()
    result = enumerate_candidates(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries, as_of=as_of),
        ceiling=fixtures.ceiling(10_000),
    )
    assert isinstance(result, CandidateSet), result
    return result


def test_every_source_behind_every_route_and_quote_the_walk_read_is_on_the_set() -> None:
    registries = fixtures.shipped()
    enumerated = _set()
    expected: set[object] = set()
    for candidate in enumerated.candidates:
        route_ids = [
            *segments_of(candidate.key.route_in),
            *exit_segments_of(candidate.key.route_out),  # type: ignore[arg-type]
        ]
        for route_id in route_ids:
            for leg in registries.routes[route_id].legs:
                expected |= set(leg.provenance.sources)
    for instrument_id in {item.key.instrument_id for item in enumerated.candidates}:
        quote = registries.access[instrument_id].quote
        if quote is not None:
            expected |= set(quote.price.provenance.sources)
    assert expected
    assert expected <= set(enumerated.provenance.sources)


def test_the_shipped_registry_marks_its_set_unverified() -> None:
    """A set that came back clean would claim a verification nobody performed."""
    assert prov.is_unverified(_set().provenance)


def test_a_value_aged_past_its_kinds_threshold_reports_stale() -> None:
    """Asked far enough ahead that every declared threshold is passed, so the assertion does
    not rest on which kind expires first -- a fact the declarations own and may change."""
    fresh = _set()
    aged = _set(as_of=fixtures.AS_OF + timedelta(days=20 * 365))
    assert not staleness.any_stale(fresh.staleness)
    assert staleness.any_stale(aged.staleness)
    assert aged.staleness.assessed == fresh.staleness.assessed


def test_the_verdict_assesses_the_sources_the_provenance_carries() -> None:
    """A verdict narrower than the mark would report *fresh* for a source nobody aged."""
    enumerated = _set()
    assessed = set(enumerated.staleness.assessed)
    carried = {source.id for source in enumerated.provenance.sources if source.kind}
    assert assessed == carried
