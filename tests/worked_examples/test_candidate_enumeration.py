"""SC-001: what the shipped declarations actually connect, counted rather than described.

**Every number here is derived from the registry the test loads.** Nothing is hard-coded, and
that is the point rather than a style: a literal 9 would keep passing after a tenth instrument
was declared, and the count it agreed with would be the code's rather than the declarations'.

The arithmetic a reader can check, re-measured on the shipped registry on 2026-08-31 after
feature 016 declared 24 real ОВДП issues:

   33 instruments with an access declaration
  x 2 declared income streams
  = 66 (instrument, stream) pairs considered

    salary_uah  arrives as UAH at monobank_uah, and inzhur_direct carries UAH
                monobank_uah -> inzhur:  1 way in
    contract_usd arrives as USD at deel, and no INBOUND route turns dollars into
                hryvnia at inzhur:       0 ways in

    every instrument's proceeds land as UAH at inzhur, and inzhur_to_monobank
    carries UAH inzhur -> monobank_uah, which is the one declared spendable
    endpoint:                            1 way out

    1 run plan supplied per instrument

  candidates = 33 x (1 x 1 x 1)  +  33 x (0 x 1 x 1)  =  33
  pairs yielding none = 66 - 33 = 33, every one of them contract_usd

The half that yields nothing is a finding about the registry rather than about the
instruments: its two USD-to-UAH corridors are declared in the `exit` direction, and an inbound
enumeration cannot see them. The remedy is feature 003's audit to answer; what must not happen
is a comparison quietly holding one stream's options with nothing saying the other stream was
never asked.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.candidates import enumerate_candidates
from terezy.core.results.candidates import CandidateSet, NothingConnects
from terezy.core.routes.path import candidate_id, exit_segments_of
from terezy.core.routes.path import segments_of as segments
from tests import candidate_registries as fixtures

pytestmark = pytest.mark.worked_example


def _set() -> CandidateSet:
    registries = fixtures.declared()
    result = enumerate_candidates(
        registries=registries,
        routes=registries.routes,
        question=fixtures.question(registries),
        ceiling=fixtures.declarations().ceiling,
    )
    assert isinstance(result, CandidateSet), result
    return result


class TestTheShippedRegistryYieldsWhatItsDeclarationsConnect:
    def test_every_declared_pair_is_considered(self) -> None:
        registries = fixtures.declared()
        declared = [
            instrument_id
            for instrument_id in registries.access
            if instrument_id in registries.instruments or instrument_id in registries.funds
        ]
        assert _set().pairs_considered == len(declared) * len(registries.streams)

    def test_one_candidate_per_instrument_and_all_of_them_from_the_hryvnia_salary(self) -> None:
        registries = fixtures.declared()
        produced = _set().candidates
        assert {candidate.key.stream_id for candidate in produced} == {fixtures.SALARY}
        assert sorted(candidate.key.instrument_id for candidate in produced) == sorted(
            instrument_id
            for instrument_id in registries.access
            if instrument_id in registries.instruments or instrument_id in registries.funds
        )

    def test_the_dollar_stream_contributes_nothing_and_says_why(self) -> None:
        """Asserted by record: an absent corridor, whose remedy is a declaration, and not
        money already where it was wanted, whose remedy is nothing at all."""
        pairs = _set().no_candidate
        assert {pair.stream_id for pair in pairs} == {fixtures.CONTRACT}
        assert all(isinstance(pair.why, NothingConnects) for pair in pairs), pairs
        assert {pair.why.side for pair in pairs if isinstance(pair.why, NothingConnects)} == {
            "route_in"
        }

    def test_the_two_populations_partition_the_pairs(self) -> None:
        enumerated = _set()
        pairs_with_a_candidate = {
            (candidate.key.instrument_id, candidate.key.stream_id)
            for candidate in enumerated.candidates
        }
        assert len(pairs_with_a_candidate) + len(enumerated.no_candidate) == (
            enumerated.pairs_considered
        )


class TestTheFiveTermsNameDeclaredThings:
    def test_every_route_id_in_every_candidate_resolves(self) -> None:
        registries = fixtures.declared()
        for candidate in _set().candidates:
            for route_id in segments(candidate.key.route_in):
                assert route_id in registries.routes
            assert not isinstance(candidate.key.route_out, tuple)
            for route_id in exit_segments_of(candidate.key.route_out):  # type: ignore[arg-type]
                assert route_id in registries.routes

    def test_the_shipped_way_in_and_way_out_are_the_declared_domestic_pair(self) -> None:
        """Named rather than counted, so a registry that grew a second corridor fails here."""
        produced = _set().candidates
        assert {candidate_id(candidate.key.route_in) for candidate in produced} == {"inzhur_direct"}
        assert {
            exit_segments_of(candidate.key.route_out)  # type: ignore[arg-type]
            for candidate in produced
        } == {("inzhur_to_monobank",)}

    def test_each_candidate_carries_the_position_of_the_plan_it_was_built_from(self) -> None:
        assert {candidate.plan_position for candidate in _set().candidates} == {0}
