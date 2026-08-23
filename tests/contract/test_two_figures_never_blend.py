"""FR-009, FR-010, FR-015: two figures, separately labelled, never mixed into one number.

The owner resolved this feature's one collision on 2026-08-22. 001's FR-022 forbade a real
figure computed from an assumed inflation rate; a hurdle projects into the future, where only
assumptions exist. The answer was **both figures, separately labelled, never mixed** -- which
refines the prohibition rather than repealing it. A real figure from an *implicit or invented*
rate is still forbidden; a *declared, dated, labelled* assumption entered as scenario data is
a different epistemic object and is permitted precisely because it is visible as an
assumption on every figure it touches.

This module is the compliance test for that resolution, and it has three jobs.

**Structural.** There is no field anywhere that could hold a blended number. Asserted by
walking the records rather than by naming the fields a test author remembered: a third field
on ``RealTerms``, or a "combined" convenience on ``HurdleRate``, would be the way a blend
arrives, and it would arrive in a change nobody read as introducing one.

**Epistemic.** A cited external forecast is still an assumption. The National Bank's number
has a citation, a retrieval date and a staleness kind, and it is a statement about a year
that has not happened -- so it carries ``basis="declared_assumption"`` exactly like the
owner's own belief, and no verification date can move it into the observed column. This is
the half of FR-010 that is easiest to get wrong, because everything about a cited forecast
*looks* like an observation.

**Per run.** Two runs differing only in their declared assumption are two results, each
naming the assumption it used, and the manifest records which declaration produced each
(FR-015, SC-008). A constant baked into the engine would pass every other test here.
"""

from __future__ import annotations

import ast
import dataclasses
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.rates import NominalRate, RealRate
from terezy.core.results import canonical, hurdle
from terezy.data import manifest
from terezy.data.declarations import loader, resolver
from tests import cpi_fixtures, source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
OWNER_ASSUMPTION_FILE = REPO_ROOT / "data" / "scenarios" / "inflation" / "owner-001.toml"

NOMINAL = NominalRate(0.155)
SERIES = cpi_fixtures.series(cpi_fixtures.run_of("2026-01", 12, 101.0))
WINDOW = cpi_fixtures.window("2026-01", "2026-12")


def _both(assumption: object) -> hurdle.RealTerms:
    return hurdle.real_terms(
        nominal=NOMINAL,
        nominal_provenance=prov.EMPTY,
        series=SERIES,
        window=WINDOW,
        assumption=assumption,  # type: ignore[arg-type]
    )


# --- structural: there is nowhere for a blend to live -----------------------------------


def test_the_slot_has_exactly_two_figures_and_no_third_field() -> None:
    """A blended number would need somewhere to live. There is nowhere."""
    fields = [field.name for field in dataclasses.fields(hurdle.RealTerms)]

    assert fields == ["realized", "assumed"]


def test_the_hurdle_rate_has_exactly_one_real_field() -> None:
    """FR-006's invariance and FR-009's separation are the same constraint from two sides."""
    fields = [field.name for field in dataclasses.fields(hurdle.HurdleRate)]

    assert [name for name in fields if "real" in name] == ["real"]


def test_the_two_figures_are_computed_independently_of_one_another() -> None:
    """Neither is derived from the other, which is how a blend gets in.

    Changing the assumption moves the assumed figure and leaves the realized one exactly
    where it was, to the last bit. If the realized figure were computed from a mixture, or
    the assumed one from the observations, this would not hold.
    """
    first = _both(cpi_fixtures.owner_assumption(0.10))
    second = _both(cpi_fixtures.owner_assumption(0.30))

    assert isinstance(first.realized, RealRate)
    assert isinstance(second.realized, RealRate)
    assert isinstance(first.assumed, RealRate)
    assert isinstance(second.assumed, RealRate)
    assert first.realized == second.realized
    assert first.assumed.value != second.assumed.value


def test_removing_the_observations_leaves_the_assumed_figure_untouched() -> None:
    """The other direction of independence: the deflators do not borrow from one another."""
    with_series = _both(cpi_fixtures.owner_assumption(0.10))
    without = hurdle.real_terms(
        nominal=NOMINAL,
        nominal_provenance=prov.EMPTY,
        series=None,
        window=WINDOW,
        assumption=cpi_fixtures.owner_assumption(0.10),
    )

    assert with_series.assumed == without.assumed


# --- labelling: each figure says what it rests on ---------------------------------------


def test_each_figure_carries_its_own_epistemic_basis() -> None:
    """FR-010: the two may never be indistinguishable."""
    both = _both(cpi_fixtures.owner_assumption(0.10))

    assert isinstance(both.realized, RealRate)
    assert isinstance(both.assumed, RealRate)
    assert both.realized.basis == "realized_cpi"
    assert both.assumed.basis == "declared_assumption"


def test_the_basis_travels_with_a_figure_lifted_out_of_the_slot() -> None:
    """A number gets quoted by being read out and passed on. It has to survive that.

    A design that inferred the basis from *which field* was holding the figure would stop
    answering the moment anything held it somewhere else -- which is exactly when it matters.
    """
    lifted = _both(cpi_fixtures.owner_assumption(0.10)).assumed
    assert isinstance(lifted, RealRate)

    assert lifted.basis == "declared_assumption"
    assert lifted.series_id == "synthetic_owner_inflation"


def test_each_figure_names_what_it_is_real_against_and_over_what_window() -> None:
    """FR-011. A bare real rate is not checkable: the same nominal deflated over two spans
    gives two answers and the number cannot say which question it answered."""
    both = _both(cpi_fixtures.owner_assumption(0.10))
    assert isinstance(both.realized, RealRate)
    assert isinstance(both.assumed, RealRate)

    assert both.realized.series_id == SERIES.id
    assert both.realized.window == WINDOW
    assert both.assumed.window == WINDOW


def test_two_figures_of_equal_value_still_digest_differently() -> None:
    """The rendering half: identical numbers on different bases are two claims.

    Constructed so the two values genuinely agree -- the assumption is set to exactly the
    annualised realized figure -- because that is the only case where a form that dropped the
    basis would report them as one.
    """
    realized = _both(cpi_fixtures.owner_assumption(0.10)).realized
    assert isinstance(realized, RealRate)
    twin = dataclasses.replace(realized, basis="declared_assumption")

    assert canonical.of_real_figure(realized) != canonical.of_real_figure(twin)


# --- a cited forecast is still an assumption --------------------------------------------


def test_a_cited_external_forecast_is_labelled_an_assumption() -> None:
    """FR-010's hardest half: everything about a cited forecast looks like an observation."""
    forecast = cpi_fixtures.forecast_assumption(0.12)
    figure = _both(forecast).assumed
    assert isinstance(figure, RealRate)

    assert forecast.provenance is not None
    assert figure.basis == "declared_assumption"


def test_a_verified_forecast_is_still_an_assumption() -> None:
    """No verification date moves a forecast into the observed column.

    There is no primary source for next year's prices, so "verified" here can only mean
    "somebody checked that the publisher really said this" -- which vouches for the quotation
    and not for the number.
    """
    figure = _both(cpi_fixtures.forecast_assumption(0.12, verified_on=date(2026, 8, 23))).assumed
    assert isinstance(figure, RealRate)

    assert figure.basis == "declared_assumption"


def test_the_forecasts_citation_reaches_the_figure_it_produced() -> None:
    """Being an assumption does not excuse it from provenance: it was read *somewhere*."""
    forecast = cpi_fixtures.forecast_assumption(0.12)
    figure = _both(forecast).assumed
    assert isinstance(figure, RealRate)
    assert forecast.provenance is not None

    assert forecast.provenance.sources <= figure.provenance.sources


def test_the_owners_own_belief_carries_no_citation_and_none_is_fabricated() -> None:
    """A belief has nothing to cite, and attaching a source to one would be the worst defect
    in Principle I's list: an invented citation on an invented number."""
    figure = _both(cpi_fixtures.owner_assumption(0.10)).assumed
    assert isinstance(figure, RealRate)

    assert cpi_fixtures.owner_assumption(0.10).provenance is None
    assert figure.provenance == prov.EMPTY


def test_no_observation_source_leaks_into_the_assumed_figure() -> None:
    """SC-008: neither figure's provenance trail leads to the other's inputs."""
    both = _both(cpi_fixtures.forecast_assumption(0.12))
    assert isinstance(both.realized, RealRate)
    assert isinstance(both.assumed, RealRate)

    observation_ids = {ref.id for ref in both.realized.provenance.sources}
    assumed_ids = {ref.id for ref in both.assumed.provenance.sources}

    assert observation_ids
    assert assumed_ids.isdisjoint(observation_ids)


# --- the declaration, and two runs that differ only in it -------------------------------


def test_the_declared_owner_assumption_loads_and_is_an_assumption() -> None:
    """FR-015: a per-run declaration, not a constant. The shipped one is the owner's own."""
    owner_id, assumption = loader.inflation_assumption_from_file(OWNER_ASSUMPTION_FILE)

    assert owner_id == "owner-001"
    assert assumption.is_assumption is True
    assert assumption.rationale.strip()
    assert assumption.provenance is None


def test_two_runs_differing_only_in_the_assumption_are_two_results() -> None:
    """SC-008. Each names the assumption it used, so the two are told apart by the output."""
    owners = (
        cpi_fixtures.owner_assumption(0.10, assumption_id="cautious"),
        cpi_fixtures.owner_assumption(0.25, assumption_id="pessimistic"),
    )
    first, second = (_both(assumption) for assumption in owners)
    assert isinstance(first.assumed, RealRate)
    assert isinstance(second.assumed, RealRate)

    assert first.assumed.series_id == "cautious"
    assert second.assumed.series_id == "pessimistic"
    assert canonical.of_real_terms(first) != canonical.of_real_terms(second)


def test_there_is_no_default_rate_anywhere_to_fall_back_on() -> None:
    """FR-015. A default would be a belief about the future the owner never stated."""
    without = hurdle.real_terms(
        nominal=NOMINAL,
        nominal_provenance=prov.EMPTY,
        series=SERIES,
        window=WINDOW,
        assumption=None,
    )

    assert not isinstance(without.assumed, RealRate)
    assert isinstance(without.realized, RealRate)


# --- the manifest records which declaration produced the result -------------------------


def test_the_manifest_records_the_series_and_the_belief_that_were_in_force() -> None:
    """FR-015's last clause. Two runs are two results only if the record says which was which.

    Recorded by id **and** by file version, so "which belief" survives the file being edited:
    a manifest naming ``owner_placeholder_inflation`` and nothing else would agree between a
    10% run and a 30% run made the day after somebody changed the number.
    """
    declarations = resolver.inflation_from_data_root(REPO_ROOT / "data")

    refs = manifest.inflation_input_refs(declarations)
    by_kind = {ref.kind: ref for ref in refs}

    assert set(by_kind) == {"cpi_series", "inflation_assumption"}
    assert by_kind["cpi_series"].id == "ua_cpi_monthly"
    assert by_kind["cpi_series"].file == "cpi/ua.toml"
    # ``directory/name``, the project-wide convention (``manifest.file_name``): an absolute
    # path would embed one machine's layout and two checkouts would describe one file twice.
    assert by_kind["inflation_assumption"].file == "inflation/owner-001.toml"
    assert all(ref.version.startswith(f"{manifest.ALGORITHM}:") for ref in refs)


def test_the_series_records_its_own_unverified_sources_in_the_manifest() -> None:
    """411 downloaded, none checked. The manifest says so per file, not only in the roll-up."""
    declarations = resolver.inflation_from_data_root(REPO_ROOT / "data")
    series_ref = next(
        ref for ref in manifest.inflation_input_refs(declarations) if ref.kind == "cpi_series"
    )

    assert len(series_ref.unverified_sources) == 411


def test_the_owners_own_belief_records_no_unverified_source_rather_than_a_fabricated_one() -> None:
    """An empty list here says "there was nothing to verify", which is the truth about a belief.

    Not the same claim as "everything was checked": the record's *kind* is what says this is an
    assumption, and no citation is invented to fill the column.
    """
    declarations = resolver.inflation_from_data_root(REPO_ROOT / "data")
    belief = next(
        ref
        for ref in manifest.inflation_input_refs(declarations)
        if ref.kind == "inflation_assumption"
    )

    assert belief.unverified_sources == ()


def test_a_run_given_no_inflation_declarations_records_none_rather_than_a_default(
    tmp_path: Path,
) -> None:
    """The absence is recorded as an absence. There is no default belief to log."""
    root = tmp_path / "data"
    (root / "cpi").mkdir(parents=True)

    assert manifest.inflation_input_refs(resolver.inflation_from_data_root(root)) == ()


# --- and there is exactly one place each of these things is built -----------------------
#
# Every test above pins the behaviour of `real_terms`. None of them says anything about a
# *second* function that also builds a real figure -- a convenience helper, a summary line, a
# later feature deflating something else -- and a second one is how the labelling rules get
# quietly bypassed: it would satisfy the type checker, produce a `RealRate`, and be free to
# put whatever it liked in `basis`.
#
# So the construction sites are counted. Today there are exactly two `RealRate` calls, one per
# basis, in one module, and every one of them is exercised above. A third is not forbidden
# forever -- it is made *visible*, and this is where the reviewer is asked whether the new one
# labels itself honestly. Prose is stripped first, on the same reading as the AST scan for the
# subtraction approximation.


def _construction_sites(name: str) -> dict[str, int]:
    """Where in ``src/`` something of this name is called, and how often, prose excluded."""
    found: dict[str, int] = {}
    for path in sorted((REPO_ROOT / "src" / "terezy").rglob("*.py")):
        tree = ast.parse(source_scan.executable_source(path))
        calls = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        )
        if calls:
            found[str(path.relative_to(REPO_ROOT))] = calls
    return found


def test_a_real_rate_is_built_in_exactly_two_places_one_per_basis() -> None:
    """Both are in ``real_terms``, both are tested above, and a third would show up here."""
    assert _construction_sites("RealRate") == {"src/terezy/core/results/hurdle.py": 2}, (
        "a real figure is now built somewhere this suite does not check. Every RealRate must "
        "carry an honest `basis`, its series and its window (FR-010, FR-011); a second "
        "construction site is a second chance to get that wrong. Test the new one, then widen "
        "this count deliberately."
    )


def test_the_fisher_relation_is_called_in_exactly_two_places() -> None:
    """One call per figure. A third caller is a third rate nobody has labelled."""
    assert _construction_sites("deflate") == {"src/terezy/core/results/hurdle.py": 2}


def test_the_slot_is_built_in_exactly_two_places() -> None:
    """``real_terms`` and the ``NOT_DEFLATED`` constant, and nothing else assembles the pair."""
    assert _construction_sites("RealTerms") == {"src/terezy/core/results/hurdle.py": 2}


def test_the_scan_is_falsifiable() -> None:
    """It must be able to see a construction, or the three tests above are green by accident."""
    assert _construction_sites("NominalRate")
    assert _construction_sites("nothing_is_called_this") == {}
