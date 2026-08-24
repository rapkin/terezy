"""FR-005 and G12: CPI is its own staleness kind, and a stale month marks the figure.

*"CPI MUST be a staleness kind of its own, with a threshold declared alongside the kind,
following 002's FR-028 pattern: per kind of value, no permissive default, and a kind with no
declared threshold fails at load. Staleness is measured from the later of an observation's
verification and retrieval dates, and once exceeded, every figure derived from the stale
observation reports the staleness."*

**What ages here is the retrieval, not the value.** A published index for a month that has
ended is a historical fact: October 2025's figure will not be different next year. What goes
out of date is the *series*, because the publisher adds a month roughly every month and a
series fetched long ago is a series missing its recent end. Forty-five days is the re-fetch
prompt, and ``data/observation_kinds.toml`` says so in its own note.

**And it is a different question from coverage** (research.md D7), which is why the last
tests here are about telling them apart. *"Is this observation stale?"* is the threshold.
*"Does the series reach the end of my window?"* is the coverage check. Both can fire on one
run, they mean different things, and merging them would make a re-fetch look like a data gap
or the reverse -- sending the owner to the wrong fix.

**No clock.** ``as_of`` is an input to the run and is recorded in the manifest, so the same
inputs give the same verdict for ever.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from terezy.core.inflation import series as cpi
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.rates import NominalRate, RealRate
from terezy.core.results import hurdle, project
from terezy.core.results.project import Projection
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError
from tests import cpi_fixtures, synthetic

REPO_ROOT = Path(__file__).resolve().parents[2]
KINDS_FILE = REPO_ROOT / "data" / "observation_kinds.toml"

RETRIEVED = date(2026, 1, 10)
"""When the fixture series was read from its publisher."""


def _kinds() -> dict[str, staleness.ObservationKind]:
    return {kind.id: kind for kind in loader.observation_kinds_from_file(KINDS_FILE)}


def _series(*, verified_on: date | None = None) -> cpi.CpiSeries:
    return cpi_fixtures.series(
        cpi_fixtures.run_of("2025-09", 3, 100.9),
        verified_on=verified_on,
        retrieved_on=RETRIEVED,
    )


def test_cpi_is_a_declared_kind_with_its_own_threshold() -> None:
    """G12. Declared beside the other kinds, with the reason for the number written down."""
    kind = _kinds()["cpi_index"]

    assert kind.staleness_days == 45
    assert "retrieval" in kind.note.lower()


def test_observations_past_the_threshold_are_reported_stale_naming_the_value() -> None:
    """The verdict names the source and the threshold, so the report is actionable."""
    verdict = cpi.staleness_of_observations(
        _series().observations, _kinds(), as_of=date(2026, 4, 1)
    )

    assert staleness.any_stale(verdict)
    assert {entry.source_id for entry in verdict.stale} == {
        "synthetic:cpi:2025-09",
        "synthetic:cpi:2025-10",
        "synthetic:cpi:2025-11",
    }
    assert all(entry.kind_id == "cpi_index" for entry in verdict.stale)
    assert all(entry.threshold_days == 45 for entry in verdict.stale)


def test_the_overdue_arithmetic_is_shown_rather_than_left_to_be_derived() -> None:
    """81 days old against a 45-day threshold is 36 days overdue, and the record says so."""
    verdict = cpi.staleness_of_observations(
        _series().observations, _kinds(), as_of=date(2026, 4, 1)
    )
    entry = next(iter(verdict.stale))

    assert entry.age_days == 81
    assert entry.overdue_days == 36


def test_fresh_observations_produce_no_warning_at_all() -> None:
    """A warning that fires on fresh data is a warning that gets ignored (US3 scenario 3)."""
    verdict = cpi.staleness_of_observations(
        _series().observations, _kinds(), as_of=date(2026, 2, 1)
    )

    assert not staleness.any_stale(verdict)
    assert verdict.assessed


def test_the_boundary_day_is_still_current() -> None:
    """Strictly past the threshold. A value exactly 45 days old has not aged past 45 days."""
    on_the_line = cpi.staleness_of_observations(
        _series().observations, _kinds(), as_of=RETRIEVED + timedelta(days=45)
    )
    a_day_later = cpi.staleness_of_observations(
        _series().observations, _kinds(), as_of=RETRIEVED + timedelta(days=46)
    )

    assert not staleness.any_stale(on_the_line)
    assert staleness.any_stale(a_day_later)


def test_verification_refreshes_the_age_because_it_is_the_later_look() -> None:
    """002's FR-025 rule: the age runs from the **later** of verification and retrieval.

    A series retrieved in January and verified in March is weeks old in April, not months.
    Reporting it as stale would tell the owner to re-check the one thing he has checked.
    """
    stale = cpi.staleness_of_observations(_series().observations, _kinds(), as_of=date(2026, 4, 1))
    refreshed = cpi.staleness_of_observations(
        _series(verified_on=date(2026, 3, 20)).observations, _kinds(), as_of=date(2026, 4, 1)
    )

    assert staleness.any_stale(stale)
    assert not staleness.any_stale(refreshed)


def test_one_stale_month_taints_the_whole_series() -> None:
    """A figure is only as current as its least current input, and a long window has many."""
    mixed = (
        cpi_fixtures.observation("2025-09", 100.9, retrieved_on=RETRIEVED),
        cpi_fixtures.observation("2025-10", 100.9, retrieved_on=date(2026, 3, 30)),
    )

    verdict = cpi.staleness_of_observations(mixed, _kinds(), as_of=date(2026, 4, 1))

    assert staleness.any_stale(verdict)
    assert [entry.source_id for entry in verdict.stale] == ["synthetic:cpi:2025-09"]


def test_the_owners_own_belief_is_not_assessed_rather_than_declared_fresh() -> None:
    """A belief has no retrieval date, so nothing was aged and nothing is claimed.

    Distinct from a clean bill of health, and it has to be: a green freshness tick on a
    statement nobody checked would be exactly the permissive default FR-028 forbids.
    """
    verdict = cpi.staleness_of_assumption(
        cpi_fixtures.owner_assumption(0.10), _kinds(), as_of=date(2030, 1, 1)
    )

    assert verdict is staleness.UNASSESSED


def test_a_retrieved_forecast_ages_exactly_as_an_observation_does() -> None:
    """It was read on a date and the publisher issues a new one; that is what a threshold is for."""
    verdict = cpi.staleness_of_assumption(
        cpi_fixtures.forecast_assumption(0.12), _kinds(), as_of=date(2027, 1, 1)
    )

    assert staleness.any_stale(verdict)


# --- the load-time half ------------------------------------------------------------------


def test_a_kind_declared_without_a_threshold_fails_at_load_naming_the_kind(
    tmp_path: Path,
) -> None:
    """US3 scenario 2. No permissive default: the omission cannot be papered over."""
    path = tmp_path / "observation_kinds.toml"
    path.write_text(
        '[[kind]]\nid = "cpi_index"\nstaleness_days = 0\nnote = "no threshold really"\n',
        encoding="utf-8",
    )

    with pytest.raises(DeclarationError) as caught:
        loader.observation_kinds_from_file(path)

    assert "cpi_index" in str(caught.value)
    assert "staleness_days" in str(caught.value)


# --- staleness and coverage are different questions ----------------------------------------


def test_a_fresh_series_can_still_fail_to_cover_a_window() -> None:
    """Fetched this morning and still ending before the window: a gap, not a staleness."""
    fresh = _series()
    verdict = cpi.staleness_of_observations(fresh.observations, _kinds(), as_of=date(2026, 2, 1))
    covered = cpi.coverage(fresh, cpi_fixtures.window("2025-09", "2026-01"))

    assert not staleness.any_stale(verdict)
    assert isinstance(covered, cpi.NotCovered)
    assert covered.missing == ("2025-12", "2026-01")


def test_a_stale_series_can_still_cover_a_window_completely() -> None:
    """Fetched long ago and covering every month asked about: stale, and complete.

    The two verdicts point at different fixes -- re-fetch the series, or declare the missing
    months -- and reporting either as the other sends the owner to the wrong one.
    """
    stale = _series()
    verdict = cpi.staleness_of_observations(stale.observations, _kinds(), as_of=date(2026, 6, 1))
    covered = cpi.coverage(stale, cpi_fixtures.window("2025-09", "2025-11"))

    assert staleness.any_stale(verdict)
    assert isinstance(covered, cpi.Covered)


# --- and the verdict reaches the figure -----------------------------------------------
#
# Everything above tests the verdict *functions*. None of it said the verdict reaches a real
# figure, and for one review round it did not: `staleness_of_observations` and
# `staleness_of_assumption` had zero production call sites, `real_terms` took no `as_of`, and
# `RealRate` had no field to carry a verdict -- while US3 scenario 1, `contracts/deflation.md`
# G10 and `METHODOLOGY` §27.6 all said it worked. A requirement unmet while three documents
# assert it is met is worse than the gap.
#
# So these derive an actual figure and look at what it carries, at both levels: straight
# through `real_terms`, and end to end through `project`, which is the only path a run takes.


def _deflated(*, as_of: date | None, verified_on: date | None = None) -> RealRate:
    """One realized figure over a fully covered window, aged (or not) at ``as_of``."""
    declared = _series(verified_on=verified_on)
    figure = hurdle.real_terms(
        nominal=NominalRate(0.155),
        nominal_provenance=prov.EMPTY,
        nominal_staleness=staleness.UNASSESSED,
        deflation=cpi_fixtures.deflation(
            window=cpi_fixtures.window("2025-09", "2025-11"),
            series=declared,
            ageing=None if as_of is None else cpi_fixtures.ageing_at(as_of, _kinds()),
        ),
    )
    assert isinstance(figure.realized, RealRate), figure.realized
    return figure.realized


def test_a_real_figure_derived_from_stale_observations_reports_the_staleness() -> None:
    """US3 scenario 1, on the figure rather than on the helper that computes the verdict.

    The verdict names the value that aged, the kind whose threshold was applied and the
    threshold itself, so the report says what to re-fetch and why.
    """
    figure = _deflated(as_of=date(2026, 4, 1))

    assert staleness.any_stale(figure.staleness)
    assert {entry.source_id for entry in figure.staleness.stale} == {
        "synthetic:cpi:2025-09",
        "synthetic:cpi:2025-10",
        "synthetic:cpi:2025-11",
    }
    assert {entry.kind_id for entry in figure.staleness.stale} == {"cpi_index"}
    assert {entry.threshold_days for entry in figure.staleness.stale} == {45}


def test_a_real_figure_derived_from_fresh_observations_reports_no_staleness() -> None:
    """Falsifier: a verdict that is always stale carries no information.

    ``assessed`` is non-empty, which is what distinguishes *checked and clean* from
    *nobody checked* -- the same distinction ``UNASSESSED`` exists to preserve.
    """
    figure = _deflated(as_of=date(2026, 2, 1))

    assert not staleness.any_stale(figure.staleness)
    assert figure.staleness.assessed


def test_a_run_that_gave_no_as_of_leaves_the_figure_unassessed_rather_than_fresh() -> None:
    """No clock, and no pretending. Nothing was aged, so nothing is claimed."""
    figure = _deflated(as_of=None)

    # Equality, not identity: the figure's verdict is the *merge* of the nominal side and the
    # CPI side, and merging two unassessed verdicts builds a new equal value rather than
    # returning the constant. The claim is the value -- nothing assessed, nothing stale.
    assert figure.staleness == staleness.UNASSESSED
    assert not figure.staleness.assessed


def test_verifying_the_observations_refreshes_the_figures_verdict_too() -> None:
    """The 002 FR-025 rule propagating all the way to the real figure, not just to the helper."""
    stale = _deflated(as_of=date(2026, 4, 1))
    refreshed = _deflated(as_of=date(2026, 4, 1), verified_on=date(2026, 3, 20))

    assert staleness.any_stale(stale.staleness)
    assert not staleness.any_stale(refreshed.staleness)


def test_the_assumed_figure_carries_a_verdict_when_the_belief_was_retrieved() -> None:
    """A cited forecast ages; the owner's own belief does not, and the two differ on one figure.

    Both run through the same call with the same ``as_of``, so the difference is the
    *declaration* rather than the code path.
    """

    def _assumed(assumption: object) -> RealRate:
        figure = hurdle.real_terms(
            nominal=NominalRate(0.155),
            nominal_provenance=prov.EMPTY,
            nominal_staleness=staleness.UNASSESSED,
            deflation=cpi_fixtures.deflation(
                window=cpi_fixtures.window("2025-09", "2025-11"),
                assumption=assumption,  # type: ignore[arg-type]
                ageing=cpi_fixtures.ageing_at(date(2027, 1, 1), _kinds()),
            ),
        ).assumed
        assert isinstance(figure, RealRate)
        return figure

    assert staleness.any_stale(_assumed(cpi_fixtures.forecast_assumption(0.12)).staleness)
    assert _assumed(cpi_fixtures.owner_assumption(0.10)).staleness == staleness.UNASSESSED


def test_the_nominal_sides_verdict_is_merged_into_the_real_figure() -> None:
    """FR-013's other half: a staleness report on an *input of the nominal figure* reaches here.

    Feature 001's records do not carry the kind they age under, so ``project`` passes
    ``UNASSESSED`` today. The merge point is asserted directly rather than through a caller
    that cannot yet exercise it, because otherwise the day those records gain their kind there
    would be nothing saying this side was ever wired.
    """
    aged_nominal = staleness.StalenessVerdict(
        assessed=("instruments/ovdp_synthetic_a.toml#instrument.terms",),
        stale=(
            staleness.StaleSource(
                source_id="instruments/ovdp_synthetic_a.toml#instrument.terms",
                kind_id="bond_terms",
                retrieved_on=date(2024, 1, 1),
                age_days=800,
                threshold_days=365,
                overdue_days=435,
            ),
        ),
    )
    figure = hurdle.real_terms(
        nominal=NominalRate(0.155),
        nominal_provenance=prov.EMPTY,
        nominal_staleness=aged_nominal,
        deflation=cpi_fixtures.deflation(
            window=cpi_fixtures.window("2025-09", "2025-11"),
            series=_series(),
            ageing=cpi_fixtures.ageing_at(date(2026, 2, 1), _kinds()),
        ),
    ).realized
    assert isinstance(figure, RealRate)

    # The CPI side is fresh at this as-of date, so a stale verdict here can only have come
    # from the nominal side -- which is the propagation being asserted.
    assert staleness.any_stale(figure.staleness)
    assert {entry.kind_id for entry in figure.staleness.stale} == {"bond_terms"}


def test_a_projection_carries_the_staleness_all_the_way_to_the_hurdle_rate() -> None:
    """End to end through ``project``, which is the only path a real run takes.

    The window ``project`` derives runs from the month after the purchase to the maturity
    month, so the fixture series is declared to cover exactly that -- proving the verdict
    survives the wiring, not merely the arithmetic.
    """
    purchased_on = date(2026, 1, 15)
    declared = cpi_fixtures.series(
        cpi_fixtures.run_of("2026-02", 24, 100.5), retrieved_on=date(2026, 1, 10)
    )
    outcome = project.project(
        synthetic.declaration(),
        synthetic.holding(purchased_on=purchased_on),
        synthetic.horizon(start=purchased_on),
        synthetic.assumptions(),
        tax_classes=synthetic.TAX_PACK,
        cpi_series=declared,
        ageing=cpi_fixtures.ageing_at(date(2026, 6, 1), _kinds()),
    )
    assert isinstance(outcome, Projection)
    realized = outcome.hurdle.real.realized
    assert isinstance(realized, RealRate), realized

    assert staleness.any_stale(realized.staleness)
    assert len(realized.staleness.stale) == 24
