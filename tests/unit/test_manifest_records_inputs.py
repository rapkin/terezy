"""A result without a manifest is not a result -- and a manifest names what fed the run.

Constitution Principle III: *"Every run emits a manifest: scenario hash, code version,
objective, seed, and the version and provenance of every input series and data file. **A
result without a manifest is not a result.**"* FR-012 adds the reproducibility half: *"each
result MUST record the inputs and their versions."*

That is a claim about completeness, so this module checks completeness in the only two ways
a test can:

* **Nothing can be omitted.** ``RunManifest`` carries no field default anywhere, asserted
  reflectively rather than by reading the source, so a manifest cannot be built by leaving
  out the awkward half of it. Every argument to :func:`terezy.data.manifest.of_run` is
  required and keyword-only for the same reason.
* **Every declaration is named, with a version that tracks the file.** The version is the
  digest of the file's bytes, recomputed independently here from ``hashlib`` rather than
  compared against the manifest's own arithmetic, and a run against a modified copy of the
  data root is shown to produce a different version. A version that did not move when the
  file did would answer the only question a manifest is ever asked -- *was the run fed this
  file, or a different one?* -- wrongly.

**Why the manifest lists the whole declaration set** rather than only the instrument that
was projected: resolution depended on the set. A second file declaring the same id would
have been a load-time failure, and the tax class the run charged under is as load-bearing as
the instrument itself. The instrument actually projected is a separate field, so nothing has
to be inferred from the list.

Closes FR-012 alongside ``tests/invariants/test_determinism.py``, which asserts the digest
the manifest carries.
"""

from __future__ import annotations

import dataclasses
import hashlib
import shutil
from datetime import date
from pathlib import Path

import pytest

from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.data import manifest
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from tests import declared_terms, synthetic

UAH = Currency.UAH

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"

ISSUE_A = "ovdp_synthetic_a"
ISSUE_B = "ovdp_synthetic_b"
EXEMPT_CLASS = "ua_government_bond"
DISTRIBUTION_CLASS = "ua_ci_fund_distribution"
DISPOSAL_CLASS = "ua_investment_profit"
REIT = "inzhur_reit"
MILTECH = "inzhur_miltech"
FUND_C = "synthetic_fund_c"
ENUMERATED_A = "ovdp_enumerated_a"
ENUMERATED_MIRROR = "ovdp_enumerated_mirror"
ENUMERATED_OUT_OF_ORDER = "enumerated_out_of_order"
FIXTURE_PAYOUT_CLASS = "synthetic_fund_payout"
FIXTURE_DISPOSAL_CLASS = "synthetic_fund_disposal"
"""⚙ Features 006 and 013 added declarations to the shipped data root: two fund files
and two tax classes, then a bond declared as the payments it will make.

They are named here rather than the set being loosened to "whatever is on disk", because
the claim under test is that the manifest records **every** declaration a run was given:
a set computed from the directory would agree with the manifest by construction and
assert nothing.
"""

CPI_SERIES = "ua_cpi_monthly"
"""The declared price series this data root holds (007)."""

INFLATION_BELIEF = "owner_placeholder_inflation"
"""The declared future-inflation belief this data root holds (007). A placeholder, and the
manifest records it by id and by file version so a run made before the owner replaces it is
distinguishable from one made after."""

HORIZON_END = date(2028, 1, 31)


def _holding(declarations: resolver.Declarations, instrument_id: str = ISSUE_A) -> Holding:
    declaration = declarations.instruments[instrument_id]
    return Holding(
        owner_id="owner-1",
        instrument_id=instrument_id,
        quantity=10.0,
        purchased_on=declared_terms.contractual(declaration).issue_date,
        cost=Money(10_000.0, UAH, prov.EMPTY),
    )


def _projection(declarations: resolver.Declarations, holding: Holding) -> Projection:
    outcome = project.project(
        declarations.instruments[holding.instrument_id],
        holding,
        DateRange(start=holding.purchased_on, end=HORIZON_END),
        synthetic.assumptions(),
        tax_classes=declarations.tax_classes,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _manifest(root: Path = DATA_ROOT) -> manifest.RunManifest:
    declarations = resolver.from_data_root(root)
    holding = _holding(declarations)
    return manifest.of_run(
        result=_projection(declarations, holding),
        declarations=declarations,
        holding=holding,
        horizon=DateRange(start=holding.purchased_on, end=HORIZON_END),
        assumptions=synthetic.assumptions(),
        seed=None,
        inflation=resolver.inflation_from_data_root(root),
    )


class TestNothingAboutAManifestCanBeOmitted:
    """The executable form of "a result without a manifest is not a result"."""

    def test_no_field_of_the_manifest_has_a_default(self) -> None:
        """A default would make the omitted half of a manifest the normal case.

        Checked reflectively rather than by reading the source, because the failure this
        guards against is somebody adding a twelfth field *with* a default -- and a source
        review catches that only if somebody performs one.
        """
        defaulted = [
            field.name
            for field in dataclasses.fields(manifest.RunManifest)
            if field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        ]
        assert not defaulted, f"these manifest fields can be omitted: {defaulted}"

    def test_no_field_of_an_input_reference_has_a_default(self) -> None:
        defaulted = [
            field.name
            for field in dataclasses.fields(manifest.InputRef)
            if field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        ]
        assert not defaulted, f"these input-reference fields can be omitted: {defaulted}"

    def test_the_manifest_records_the_run_itself_and_not_only_its_output(self) -> None:
        record = _manifest()
        assert record.code_version
        assert record.encoding == manifest.ENCODING
        assert record.owner_id == "owner-1"
        assert record.projected_instrument_id == ISSUE_A
        assert record.holding.quantity == 10.0
        assert record.horizon.end == HORIZON_END
        assert record.assumptions.consumption_method == "fifo"
        assert record.seed is None

    def test_the_seed_is_recorded_as_absent_rather_than_left_unset(self) -> None:
        """``None`` is a statement, not an unset field.

        Feature 001 has no stochastic path at all -- the core may not import ``random`` --
        so there is no seed to record, and the field says so explicitly rather than
        existing as a hole a later feature might not notice.
        """
        assert "seed" in {field.name for field in dataclasses.fields(manifest.RunManifest)}
        assert _manifest().seed is None

    def test_the_digest_in_the_manifest_is_the_digest_of_the_result(self) -> None:
        declarations = resolver.from_data_root(DATA_ROOT)
        holding = _holding(declarations)
        result = _projection(declarations, holding)
        record = manifest.of_run(
            result=result,
            declarations=declarations,
            holding=holding,
            horizon=DateRange(start=holding.purchased_on, end=HORIZON_END),
            assumptions=synthetic.assumptions(),
            seed=None,
        )
        assert record.result_digest == manifest.digest_of_projection(result)
        assert record.result_digest.startswith(f"{manifest.ALGORITHM}:")


class TestEveryDeclarationAndVersionThatFedTheRun:
    """FR-012's "the inputs and their versions", one assertion per word."""

    def test_every_declaration_in_the_set_is_named(self) -> None:
        record = _manifest()
        assert {(ref.kind, ref.id) for ref in record.inputs} == {
            # ⚙ The last two joined in 007. FR-015 requires the record to say which price
            # series and which declared belief were in force, because two runs differing only
            # in the belief are two results and nothing else in the manifest tells them apart.
            ("cpi_series", CPI_SERIES),
            ("inflation_assumption", INFLATION_BELIEF),
            ("instrument", ISSUE_A),
            ("instrument", ISSUE_B),
            ("instrument", ENUMERATED_A),
            ("instrument", ENUMERATED_MIRROR),
            ("instrument", ENUMERATED_OUT_OF_ORDER),
            ("fund", REIT),
            ("fund", MILTECH),
            ("fund", FUND_C),
            ("tax_class", EXEMPT_CLASS),
            ("tax_class", DISTRIBUTION_CLASS),
            ("tax_class", DISPOSAL_CLASS),
            ("tax_class", FIXTURE_PAYOUT_CLASS),
            ("tax_class", FIXTURE_DISPOSAL_CLASS),
        }

    def test_the_second_issue_is_named_although_this_run_did_not_project_it(self) -> None:
        """The whole input set, because resolution depended on the whole input set.

        Another file declaring the same id would have been a load-time failure, so which
        files were present is part of what the run's answer rested on.
        """
        record = _manifest()
        assert record.projected_instrument_id == ISSUE_A
        assert ISSUE_B in {ref.id for ref in record.inputs}

    def test_the_inputs_are_ordered_by_kind_and_id_and_not_by_the_filesystem(self) -> None:
        """Load order is directory order, which is a fact about the machine, not the run."""
        record = _manifest()
        assert list(record.inputs) == sorted(record.inputs, key=lambda ref: (ref.kind, ref.id))

    def test_each_input_names_its_file_relative_to_the_data_root(self) -> None:
        """Never an absolute path: it would embed one machine's directory layout.

        The parent directory is kept, because ``instruments/ua.toml`` and ``tax/ua.toml``
        are different files and the bare name would collide -- the same reasoning
        ``loader.source_id`` uses for a source id.
        """
        files = {ref.id: ref.file for ref in _manifest().inputs}
        assert files == {
            CPI_SERIES: "cpi/ua.toml",
            INFLATION_BELIEF: "inflation/owner-001.toml",
            ISSUE_A: f"instruments/{ISSUE_A}.toml",
            ISSUE_B: f"instruments/{ISSUE_B}.toml",
            ENUMERATED_A: f"instruments/{ENUMERATED_A}.toml",
            ENUMERATED_MIRROR: f"instruments/{ENUMERATED_MIRROR}.toml",
            ENUMERATED_OUT_OF_ORDER: f"instruments/{ENUMERATED_OUT_OF_ORDER}.toml",
            REIT: f"instruments/{REIT}.toml",
            MILTECH: f"instruments/{MILTECH}.toml",
            FUND_C: f"instruments/{FUND_C}.toml",
            EXEMPT_CLASS: "tax/ua.toml",
            DISTRIBUTION_CLASS: "tax/ua.toml",
            DISPOSAL_CLASS: "tax/ua.toml",
            FIXTURE_PAYOUT_CLASS: "tax/synthetic_fixture.toml",
            FIXTURE_DISPOSAL_CLASS: "tax/synthetic_fixture.toml",
        }
        for name in files.values():
            assert not Path(name).is_absolute()

    def test_each_version_is_the_digest_of_the_files_own_bytes(self) -> None:
        """Recomputed here from ``hashlib``, not compared against the manifest's own sum.

        A test that asked the manifest to check itself would pass over any consistent
        mistake. This one states the independent claim: the recorded version is the SHA-256
        of exactly the bytes on disk.
        """
        expected = {
            CPI_SERIES: DATA_ROOT / "cpi" / "ua.toml",
            INFLATION_BELIEF: DATA_ROOT / "scenarios" / "inflation" / "owner-001.toml",
            ISSUE_A: DATA_ROOT / "instruments" / f"{ISSUE_A}.toml",
            ISSUE_B: DATA_ROOT / "instruments" / f"{ISSUE_B}.toml",
            ENUMERATED_A: DATA_ROOT / "instruments" / f"{ENUMERATED_A}.toml",
            ENUMERATED_MIRROR: DATA_ROOT / "instruments" / f"{ENUMERATED_MIRROR}.toml",
            ENUMERATED_OUT_OF_ORDER: (
                DATA_ROOT / "instruments" / f"{ENUMERATED_OUT_OF_ORDER}.toml"
            ),
            REIT: DATA_ROOT / "instruments" / f"{REIT}.toml",
            MILTECH: DATA_ROOT / "instruments" / f"{MILTECH}.toml",
            FUND_C: DATA_ROOT / "instruments" / f"{FUND_C}.toml",
            EXEMPT_CLASS: DATA_ROOT / "tax" / "ua.toml",
            DISTRIBUTION_CLASS: DATA_ROOT / "tax" / "ua.toml",
            DISPOSAL_CLASS: DATA_ROOT / "tax" / "ua.toml",
            FIXTURE_PAYOUT_CLASS: DATA_ROOT / "tax" / "synthetic_fixture.toml",
            FIXTURE_DISPOSAL_CLASS: DATA_ROOT / "tax" / "synthetic_fixture.toml",
        }
        recorded = _manifest().inputs
        assert {ref.id for ref in recorded} == set(expected), (
            "every input must be checked here; an id this map does not know would otherwise "
            "skip the loop's assertion entirely"
        )
        for ref in recorded:
            digest = hashlib.sha256(expected[ref.id].read_bytes()).hexdigest()
            assert ref.version == f"{manifest.ALGORITHM}:{digest}"

    def test_editing_a_declaration_changes_its_recorded_version(self, tmp_path: Path) -> None:
        """The version tracks the file, which is the only property that makes it a version.

        A comment is edited rather than a rate: the run's numbers are unchanged, and the
        version must move anyway. A version that only noticed changes to values would let a
        file be silently swapped for one that documents itself differently -- and the
        citation *is* part of what a declaration says.
        """
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        before = {ref.id: ref.version for ref in _manifest(root).inputs}

        target = root / "tax" / "ua.toml"
        target.write_text(
            target.read_text(encoding="utf-8") + "\n# an edited comment\n",
            encoding="utf-8",
        )
        after = {ref.id: ref.version for ref in _manifest(root).inputs}

        assert before[EXEMPT_CLASS] != after[EXEMPT_CLASS]
        assert before[ISSUE_A] == after[ISSUE_A]
        assert before[ISSUE_B] == after[ISSUE_B]

    def test_a_copied_data_root_produces_the_same_versions_and_the_same_digest(
        self, tmp_path: Path
    ) -> None:
        """A version is a fact about content, so it must not depend on where the files are.

        This is what makes two manifests of the same run comparable across machines --
        exactly the property an absolute path would destroy.
        """
        root = tmp_path / "data"
        shutil.copytree(DATA_ROOT, root)
        here, there = _manifest(), _manifest(root)
        assert [ref.version for ref in here.inputs] == [ref.version for ref in there.inputs]
        assert [ref.file for ref in here.inputs] == [ref.file for ref in there.inputs]
        assert here.result_digest == there.result_digest


class TestTheManifestCarriesTheProvenanceOfWhatFedIt:
    """Principle III asks for *"the version and provenance of every input"* -- both."""

    def test_every_sourced_declaration_reports_which_of_its_sources_are_unverified(self) -> None:
        """Every ``verified_on`` in ``data/`` is empty, so every *cited* input is marked.

        Per input rather than only in the roll-up, so a reader can see *which file* is the
        one still to check against a primary source.

        ⚙ **The declared inflation belief is excluded, and its empty list is the honest one**
        (007). It carries no citation at all -- a belief about next year's prices has no
        publisher -- so there is nothing that *could* be verified and nothing to mark. That is
        a different claim from "checked and clean", and what distinguishes the two here is the
        input's ``kind``, not an empty tuple.
        """
        for ref in _manifest().inputs:
            if ref.kind == "inflation_assumption":
                assert ref.unverified_sources == (), (
                    f"{ref.id} is a belief and cites nothing; a source here would be invented"
                )
                continue
            assert ref.unverified_sources, f"{ref.id} claims to be fully verified"
            assert all(name.startswith(f"{ref.file}#") for name in ref.unverified_sources), (
                f"{ref.id} reports sources that do not belong to {ref.file}: "
                f"{ref.unverified_sources}"
            )

    def test_the_cpi_series_reports_all_four_hundred_and_eleven_unverified_months(self) -> None:
        """The count, because a per-file mark that collapsed to one would look identical.

        One ``SourceRef`` per observation is what makes a real figure able to name every month
        it chained (007 research.md D6); a shared ref would report a single unverified value
        here and the number would look reassuring.
        """
        series = next(ref for ref in _manifest().inputs if ref.kind == "cpi_series")

        assert len(series.unverified_sources) == 411

    def test_an_instrument_reports_the_sources_of_its_terms_and_its_constraints(self) -> None:
        """Two tables, two observations, two sources -- and both are recorded.

        Recording only the terms would let a verified minimum ticket vouch for an
        unverified yield, which is the merge the loader deliberately does not perform.
        """
        (issue,) = [ref for ref in _manifest().inputs if ref.id == ISSUE_A]
        assert set(issue.unverified_sources) == {
            f"instruments/{ISSUE_A}.toml#instrument.terms",
            f"instruments/{ISSUE_A}.toml#instrument.constraints",
        }

    def test_the_roll_up_names_every_unverified_source_behind_the_headline_figure(self) -> None:
        record = _manifest()
        assert f"instruments/{ISSUE_A}.toml#instrument.terms" in record.unverified_sources
        assert (
            "tax/ua.toml#jurisdiction.tax_class[ua_government_bond].rate[0]"
            in record.unverified_sources
        )
        assert list(record.unverified_sources) == sorted(record.unverified_sources)

    def test_the_roll_up_describes_the_result_rather_than_the_directory(self) -> None:
        """Issue B was loaded and did not feed the figure, so it is not behind it.

        The distinction matters: :attr:`inputs` says what the run was given, the roll-up
        says what the *answer* rests on, and collapsing the two would mark a figure with a
        file it never read.
        """
        record = _manifest()
        assert not any(ISSUE_B in name for name in record.unverified_sources)
        assert ISSUE_B in {ref.id for ref in record.inputs}


class TestAManifestCannotDescribeARunThatDidNotHappen:
    """Failures, because a false record is worse than a missing one."""

    def test_a_holding_naming_an_undeclared_instrument_is_refused(self) -> None:
        declarations = resolver.from_data_root(DATA_ROOT)
        holding = _holding(declarations)
        result = _projection(declarations, holding)
        with pytest.raises(ValueError, match="did not feed the run"):
            manifest.of_run(
                result=result,
                declarations=declarations,
                holding=Holding(
                    owner_id="owner-1",
                    instrument_id="an_issue_nobody_declared",
                    quantity=10.0,
                    purchased_on=holding.purchased_on,
                    cost=holding.cost,
                ),
                horizon=DateRange(start=holding.purchased_on, end=HORIZON_END),
                assumptions=synthetic.assumptions(),
                seed=None,
            )

    def test_a_file_that_cannot_be_read_names_itself(self, tmp_path: Path) -> None:
        """A vanished input is reported, not skipped.

        A manifest that quietly omitted a file would claim the run rested on inputs nobody
        can identify, which is the same as having no manifest at all.
        """
        missing = tmp_path / "instruments" / "gone.toml"
        with pytest.raises(DeclarationError) as caught:
            manifest.file_version(missing)
        assert caught.value.file == missing
        assert "manifest" in caught.value.problem


class TestTheDigestOfTheSameResultIsTheSame:
    """A sanity check that this module's helpers agree with the C4 suite's.

    Cheap, and it catches the one mistake that would make every assertion above vacuous:
    two calls to :func:`_manifest` describing different runs.
    """

    def test_two_manifests_of_the_same_run_agree_completely(self) -> None:
        assert _manifest() == _manifest()
