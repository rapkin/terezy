"""Enumeration considers the ids the question named, and no others.

015 FR-008, made in feature 014 because it is 014's type. Before this, ``_considered`` walked
every instrument with an access entry, so a question about two of nine was answered about nine.
The subject set is **resolved ids** and never a group word: what a group is belongs to 015, and
014 has no business knowing.
"""

from __future__ import annotations

from terezy.core.results.candidates import CandidateSet
from tests import candidate_registries as fixtures


def _set(subjects: frozenset[str]) -> CandidateSet:
    registries = fixtures.declared()
    result = fixtures.enumerated(
        registries, question_=fixtures.question(registries, subjects=subjects)
    )
    assert isinstance(result, CandidateSet), result
    return result


def test_only_the_named_ids_are_considered() -> None:
    """Two of the registry's instruments, and the other seven appear in no population."""
    registries = fixtures.declared()
    named = frozenset({"ovdp_synthetic_a", "inzhur_miltech"})
    narrowed = _set(named)

    reached = {candidate.key.instrument_id for candidate in narrowed.candidates}
    empty = {pair.instrument_id for pair in narrowed.no_candidate}
    assert reached | empty <= named
    assert set(registries.access) - named, "the fixture must leave something out to narrow"


def test_pairs_considered_counts_the_narrowed_set() -> None:
    """The identity FR-009 rests on is over the *considered* pairs, not the declared ones."""
    registries = fixtures.declared()
    named = frozenset({"ovdp_synthetic_a", "inzhur_miltech"})
    assert _set(named).pairs_considered == len(named) * len(registries.streams)


def test_naming_one_id_yields_fewer_pairs_than_naming_two() -> None:
    """A discrimination the previous assertion cannot make on its own.

    ``pairs_considered`` computed from ``len(registries.access)`` would satisfy the arithmetic
    above for any *fixed* registry; only a second set size proves the count follows the question.
    """
    one = _set(frozenset({"ovdp_synthetic_a"})).pairs_considered
    two = _set(frozenset({"ovdp_synthetic_a", "inzhur_miltech"})).pairs_considered
    assert one * 2 == two


def test_an_id_the_registry_does_not_declare_is_not_a_candidate() -> None:
    """It yields nothing and raises nothing: 015 FR-009 reports it one layer up, by name."""
    narrowed = _set(frozenset({"ovdp_synthetic_a", "btc"}))
    assert all(candidate.key.instrument_id != "btc" for candidate in narrowed.candidates)
    assert all(pair.instrument_id != "btc" for pair in narrowed.no_candidate)


def test_naming_every_declared_id_reproduces_the_unnarrowed_enumeration() -> None:
    """The narrowing is a filter and not a different walk."""
    registries = fixtures.declared()
    whole = _set(frozenset(registries.access))
    assert [candidate.key for candidate in whole.candidates] == [
        candidate.key
        for candidate in _set(frozenset(registries.access) | {"undeclared_x"}).candidates
    ]
    assert whole.pairs_considered == len(registries.access) * len(registries.streams)
