"""FR-023 and SC-013: one regime per set, and the key that lets two sets be compared.

A candidate set is enumerated for **one** named regime, and the regime id travels with it. The
**key** carries no regime -- the five declared terms and nothing else -- and that is what makes
two per-regime sets alignable at all: a candidate present in one and absent from the other is a
**finding about that regime**, in its rawest form the deciding belief a later shortlist will
have to name, rather than a missing row somebody reconciles by hand.

What is asserted here is the property, not a declared scenario: the composed data root resolves no
regimes (`scenario_id=None`), so the two worlds below are two route sets stated by this module,
which is the only way to reach the case.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from terezy.core.results.candidates import CandidateSet
from terezy.core.routes.path import candidate_id
from tests import candidate_registries as fixtures
from tests import tuple_registries as tuples

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

    from terezy.core.decision.tuple_outcome import Registries
    from terezy.core.routes.legs import Route

WARTIME = "wartime"
NORMALIZED = "normalized"
SECOND_WAY_IN = "test_second_corridor_to_inzhur"


def _believed(registries: Registries, regime_id: str, routes: Mapping[str, Route]) -> CandidateSet:
    result = fixtures.enumerated(
        registries,
        question_=fixtures.question(registries, regime_id=regime_id),
        routes=routes,
    )
    assert isinstance(result, CandidateSet), result
    return result


def _worlds() -> tuple[Registries, Mapping[str, Route], Mapping[str, Route]]:
    """One registry, two beliefs about which of its corridors exist.

    The wider world believes in a second declared way in to the buying venue, so every
    instrument has two candidates there and one in the narrower world. Both route sets are
    subsets of the registry's own declarations, which is what a regime is: a belief about which
    declared corridors are open, never a declaration of its own.
    """
    registries = fixtures.declared()
    second = tuples.route(
        SECOND_WAY_IN,
        origin="monobank_uah",
        destination="inzhur",
        direction="inbound",
        fee_pct=0.01,
    )
    wide = {**registries.routes, SECOND_WAY_IN: second}
    return (
        tuples.with_new_route(registries, second),
        wide,
        registries.routes,
    )


def test_the_regime_travels_with_the_set() -> None:
    registries, wide, narrow = _worlds()
    assert _believed(registries, WARTIME, narrow).question.regime_id == WARTIME
    assert _believed(registries, NORMALIZED, wide).question.regime_id == NORMALIZED


def test_a_candidate_present_in_both_compares_equal_by_key() -> None:
    """The key carries no regime, so equality is what alignment costs -- not a normalisation
    pass a caller writes and gets subtly wrong."""
    registries, wide, narrow = _worlds()
    lean = {item.key for item in _believed(registries, WARTIME, narrow).candidates}
    rich = {item.key for item in _believed(registries, NORMALIZED, wide).candidates}
    assert lean
    assert lean <= rich


def test_the_symmetric_difference_is_a_finding_about_the_regime_that_lacks_it() -> None:
    registries, wide, narrow = _worlds()
    lean = {item.key for item in _believed(registries, WARTIME, narrow).candidates}
    rich = {item.key for item in _believed(registries, NORMALIZED, wide).candidates}
    only_when_believed = rich - lean
    assert only_when_believed
    assert {candidate_id(key.route_in) for key in only_when_believed} == {SECOND_WAY_IN}


def test_neither_set_carries_the_other_regimes_corridor() -> None:
    """FR-017 one layer up: handing a wider mapping than the regime's is how the belief leaks,
    and a set that quietly contained a corridor its own regime disbelieves would make every
    figure in it rest on a world nobody stated."""
    registries, _, narrow = _worlds()
    lean = _believed(registries, WARTIME, narrow)
    assert SECOND_WAY_IN not in {candidate_id(item.key.route_in) for item in lean.candidates}
