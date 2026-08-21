"""Provenance is a commutative monoid, so evaluation order can never change a mark.

Part of **E5** in ``docs/REQUIRED_TESTS.md`` and of FR-015. This is the algebraic
foundation the whole propagation mechanism rests on, and it is worth asserting directly
rather than inferring from the money tests.

Why it matters concretely: every combining function in
``terezy.core.primitives.money`` merges its operands' provenance, and sums are built by
folding. If ``merge`` were not associative, ``add(add(a, b), c)`` and
``add(a, add(b, c))`` could disagree about whether the total rests on an unverified
input -- making the unverified mark a fact about the order the code happened to
accumulate in, rather than a fact about the data. If it were not commutative, reversing
a list of cash flows could clear a mark. Both would be silent, and both are the
top-severity defect class the constitution names.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.primitives import provenance
from terezy.core.primitives.provenance import Provenance, SourceRef

_ids = st.text(min_size=1, max_size=8)
_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))

_source_refs = st.builds(
    SourceRef,
    id=_ids,
    citation=st.text(min_size=1, max_size=12),
    retrieved_on=_dates,
    verified_on=st.one_of(st.none(), _dates),
)

_provenances = st.builds(Provenance, sources=st.frozensets(_source_refs, max_size=4))


@given(left=_provenances, middle=_provenances, right=_provenances)
def test_merge_is_associative(left: Provenance, middle: Provenance, right: Provenance) -> None:
    assert provenance.merge(provenance.merge(left, middle), right) == provenance.merge(
        left, provenance.merge(middle, right)
    )


@given(left=_provenances, right=_provenances)
def test_merge_is_commutative(left: Provenance, right: Provenance) -> None:
    assert provenance.merge(left, right) == provenance.merge(right, left)


@given(prov=_provenances)
def test_empty_is_the_identity(prov: Provenance) -> None:
    assert provenance.merge(prov, provenance.EMPTY) == prov
    assert provenance.merge(provenance.EMPTY, prov) == prov


@given(prov=_provenances)
def test_merge_is_idempotent(prov: Provenance) -> None:
    """Union, not concatenation: the same source contributing twice adds nothing.

    This is what stops the mark depending on the *shape* of the arithmetic -- a figure
    that used one source three times is no less trustworthy than one that used it once.
    """
    assert provenance.merge(prov, prov) == prov


@given(items=st.lists(_provenances, max_size=5))
def test_merge_all_is_order_independent(items: list[Provenance]) -> None:
    assert provenance.merge_all(items) == provenance.merge_all(list(reversed(items)))


@given(items=st.lists(_provenances, max_size=5))
def test_merge_all_of_nothing_is_empty(items: list[Provenance]) -> None:
    assert provenance.merge_all([]) == provenance.EMPTY
    assert provenance.merge_all(items) == provenance.merge_all([*items, provenance.EMPTY])


@given(left=_provenances, right=_provenances)
def test_the_mark_survives_every_merge(left: Provenance, right: Provenance) -> None:
    """One unverified source anywhere in the union marks the union.

    The propagation property itself, stated over the algebra: a merge can never *clear*
    a mark, in either direction.
    """
    merged = provenance.merge(left, right)
    if provenance.is_unverified(left) or provenance.is_unverified(right):
        assert provenance.is_unverified(merged)
    else:
        assert not provenance.is_unverified(merged)


@given(left=_provenances, right=_provenances)
def test_the_mark_names_the_sources_responsible(left: Provenance, right: Provenance) -> None:
    merged = provenance.merge(left, right)
    responsible = provenance.unverified_sources(merged)
    assert responsible == provenance.unverified_sources(left) | provenance.unverified_sources(right)
    assert all(ref.verified_on is None for ref in responsible)
    assert provenance.is_unverified(merged) == bool(responsible)


def test_empty_is_not_unverified() -> None:
    """A figure resting on nothing is not resting on an unverified observation.

    If ``EMPTY`` were unverified, every figure would be marked forever and the mark
    would stop meaning anything -- the run-scoped taint flag rejected in research.md D2.
    """
    assert not provenance.is_unverified(provenance.EMPTY)
    assert provenance.unverified_sources(provenance.EMPTY) == frozenset()


@pytest.mark.parametrize("verified_on", [None, date(2026, 8, 21)])
def test_is_verified_is_exactly_the_presence_of_a_date(verified_on: date | None) -> None:
    ref = SourceRef(
        id="test/is_verified",
        citation="synthetic",
        retrieved_on=date(2026, 8, 1),
        verified_on=verified_on,
    )
    assert provenance.is_verified(ref) is (verified_on is not None)
    assert provenance.is_unverified(provenance.of([ref])) is (verified_on is None)
