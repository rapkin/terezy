"""What a lookup against a long series costs, asserted as a shape rather than as a duration.

018 SC-013. At zero observations a linear lookup is free, which is why the shipped series has
never made this visible; at one observation per calendar day and one lookup per taxable event
it is O(rows x events).

**Counted, not timed.** A timing assertion is a flake on a loaded machine and passes on a fast
one, so the series here counts how many of its own observations the lookup reaches. The claim
is then the one that distinguishes the two implementations rather than a threshold somebody
picked: an **eight times longer** series may cost at most **three more** reaches per lookup,
because that is what doubling three times costs a bisection and is a factor of eight short of
what it costs a scan.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Self

import pytest

from terezy.core.primitives.currency import Currency
from terezy.core.tax import official_rate
from tests import official_rates

FIRST = date(2020, 1, 1)

SMALL = 1_024
LARGE = 8_192
"""Eight times SMALL: three doublings, which is the whole of the bound asserted below."""

DOUBLINGS = 3

PROBES = 64
"""How many dates each series is asked about. Any number does; the comparison is between two
series asked the *same* number of times."""

READ_TO_ANSWER = 1
"""Reaches a bisection costs beyond the search itself: the element it lands on is read once
more, to compare its date against the one asked for."""


class _CountingObservations(tuple[official_rate.OfficialRateObservation, ...]):
    """The observations of a series, counting every element any lookup reaches.

    Both doors are counted: ``__getitem__`` is how a bisection reaches one, and ``__iter__``
    is how a scan or a dict rebuild reaches all of them. Counting only the first would let a
    linear implementation pass by using the other.
    """

    reached: int

    def __new__(cls, items: tuple[official_rate.OfficialRateObservation, ...]) -> Self:
        made = super().__new__(cls, items)
        made.reached = 0
        return made

    def __getitem__(self, index: Any) -> Any:
        self.reached += 1
        return super().__getitem__(index)

    def __iter__(self) -> Any:
        for item in super().__iter__():
            self.reached += 1
            yield item


def _series(count: int) -> tuple[official_rate.OfficialRateSeries, _CountingObservations]:
    """A synthetic series of ``count`` consecutive days, whose observations count reaches."""
    declared = official_rates.series(
        [(FIRST + timedelta(days=offset), 40.0 + offset / 1000.0) for offset in range(count)]
    )
    counting = _CountingObservations(declared.observations)
    return official_rate.OfficialRateSeries(
        id=declared.id,
        authority=declared.authority,
        pair=declared.pair,
        quotation_unit=declared.quotation_unit,
        rule=declared.rule,
        observations=counting,
    ), counting


def _reaches_per_probe(count: int) -> float:
    """Observations reached per lookup, over ``PROBES`` dates spread across the series."""
    series, counting = _series(count)
    step = count // PROBES
    for probe in range(PROBES):
        found = official_rate.observation_for(series, FIRST + timedelta(days=probe * step))
        assert found is not None, probe
    return counting.reached / PROBES


class TestALookupDoesNotReachEveryObservation:
    def test_a_series_eight_times_longer_costs_at_most_three_more_reaches_per_lookup(
        self,
    ) -> None:
        """The bisection claim, stated so a scan fails it by a factor of eight."""
        small = _reaches_per_probe(SMALL)
        large = _reaches_per_probe(LARGE)

        assert large <= small + DOUBLINGS, (small, large)

    @pytest.mark.parametrize("count", [SMALL, LARGE])
    def test_no_lookup_reaches_more_observations_than_the_series_has_doublings(
        self,
        count: int,
    ) -> None:
        """The absolute half, so the test above cannot pass by both sides being linear."""
        assert _reaches_per_probe(count) <= count.bit_length() + READ_TO_ANSWER


class TestTheAnswerIsUnchangedByHowItIsFound:
    """A faster lookup that returns a different observation is not a faster lookup."""

    def test_every_declared_date_returns_its_own_observation_and_no_rule(self) -> None:
        series, _ = _series(SMALL)
        for offset in (0, 1, SMALL // 2, SMALL - 2, SMALL - 1):
            wanted = FIRST + timedelta(days=offset)
            found = official_rate.observation_for(series, wanted)
            assert found is not None, offset
            observation, rule_id = found
            assert observation.on_date == wanted
            assert rule_id is None

    @pytest.mark.parametrize("offset", [-1, SMALL])
    def test_a_date_outside_the_declared_run_finds_nothing_rather_than_an_edge(
        self,
        offset: int,
    ) -> None:
        """A bisection that forgot to check the date it landed on would return the neighbour,
        which is the carry-forward FR-010 forbids arriving as an off-by-one."""
        series, _ = _series(SMALL)
        assert official_rate.observation_for(series, FIRST + timedelta(days=offset)) is None

    def test_a_gap_inside_the_run_finds_nothing_rather_than_the_nearest(self) -> None:
        missing = FIRST + timedelta(days=1)
        declared = official_rates.series(
            [(FIRST, 40.0), (FIRST + timedelta(days=2), 41.0)],
        )
        assert official_rate.observation_for(declared, missing) is None
        assert declared.pair == (Currency.UAH, Currency.USD)
