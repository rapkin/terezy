"""The dollar stream, made live by a corridor the shipped registry does not declare.

015 SC-011 and SC-016. The shipped registry connects nothing inbound from ``contract_usd``, so
every candidate is funded from ``salary_uah`` and the whole cross-currency half of the model is
unreachable. Declaring **one fx corridor** makes it live -- and what comes back is not a figure
but a refusal about the *question*: every instrument in the registry is bought at one venue, so
the corridor gives the named benchmark a second candidate, and a benchmark that yields two is
one whose figure everything else would be ranked against by accident of file order.

**This is why FR-022's ``MoreThanOneStreamInTheSet`` is not reachable through the verb over
this registry**, and the reason is structural rather than an omission: the benchmark check is
about the question and fires first, and any registry where the corridor makes a *set* span two
streams also makes the *benchmark* span them. 014's own suite reaches that record directly, and
this file records why the layer above cannot.

**Nothing here converts anything.** The corridor crosses at the shipped p2p channel's declared
two-sided quote, so no rate is derived and none is read from a series (FR-021).
"""

from __future__ import annotations

from dataclasses import replace

from terezy.core.results.answer import BenchmarkYieldsSeveralCandidates
from terezy.core.results.candidates import CandidateSurvey
from tests import answer_registries as fixtures
from tests import tuple_registries as routes

CORRIDOR = "test_deel_to_inzhur_fx"
SALARY = "salary_uah"
CONTRACT = "contract_usd"


def _with_the_corridor() -> object:
    supplied = fixtures.inputs()
    widened = routes.with_new_route(
        supplied.registries,
        routes.fx_route(CORRIDOR, origin="deel", destination="inzhur"),
    )
    return fixtures.refused(
        fixtures.owners_question(),
        replace(supplied, registries=widened, routes=widened.routes),
    )


def test_the_shipped_registry_reaches_nothing_from_the_dollar_stream() -> None:
    """The baseline the fixture is a difference from, read off the sections themselves."""
    for section in fixtures.answered().sections:
        assert isinstance(section.outcome, CandidateSurvey)
        funded = {item.key.stream_id for item in section.outcome.enumerated.candidates}
        assert funded == {SALARY}
        empty = {pair.stream_id for pair in section.outcome.enumerated.no_candidate}
        assert empty == {CONTRACT}


def test_declaring_the_corridor_gives_the_benchmark_a_second_candidate() -> None:
    """SC-011's second case. Picking the first would settle by file order what is the hurdle."""
    refusal = _with_the_corridor()
    assert isinstance(refusal, BenchmarkYieldsSeveralCandidates), refusal
    assert refusal.instrument_id == fixtures.BENCHMARK
    assert refusal.occurrences == 2


def test_the_corridor_is_the_only_change_and_it_is_a_declaration() -> None:
    """The gap the shipped registry has is a route nobody declared, not a rule nobody wrote."""
    supplied = fixtures.inputs()
    widened = routes.with_new_route(
        supplied.registries,
        routes.fx_route(CORRIDOR, origin="deel", destination="inzhur"),
    )
    assert set(widened.routes) - set(supplied.registries.routes) == {CORRIDOR}
    assert widened.instruments == supplied.registries.instruments
