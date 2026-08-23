"""FR-003 and SC-005: every broken CPI file fails at load, naming the file and the offence.

*"Loading CPI data MUST fail loudly -- naming the file and the offending field or period --
on a malformed value, an unrecognised field, a missing required field, a duplicate or
overlapping period, a period inconsistent with the declared periodicity, a period that has
not yet elapsed, or a duplicated series identity. A default MUST NOT be substituted for
anything absent."*

Written as a battery rather than a handful of cases, because SC-005 is a claim about *every*
way a file can be wrong and a sampled version of it would go stale the first time somebody
added a field. Each case below is one file on disk, written into a scratch data root, loaded,
and checked for a message that names the file and the specific thing that is wrong -- because
an error that says "invalid CPI file" sends a reader to read 411 rows by hand.

**Two cases are this feature's own and are worth reading twice.**

*A period that has not yet elapsed.* A published index for a month covers a month that has
**ended**; a value for a month still running is a forecast wearing an observation's clothes,
and it would chain into a real figure indistinguishable from a measured one. The check is
made against the observation's **own** ``retrieved_on`` rather than against a clock: a month
can only have been published after it finished, so an observation retrieved before its own
period ended cannot be an observation. That keeps the loader deterministic -- the same file
loads the same way in 2026 and in 2030 -- which a clock-based check would not.

*A duplicated series identity.* Two files declaring ``ua_cpi_monthly`` is not a merge and not
a preference: whichever loaded second would win by directory order, and every real figure
would silently rest on the other one.

And the last test loads the **shipped** ``data/cpi/ua.toml``, because a battery of broken
files proves nothing about the file the project actually uses.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
SHIPPED = DATA_ROOT / "cpi" / "ua.toml"

HEADER = """
[series]
id          = "xx_cpi_monthly"
country     = "XX"
index       = "SYNTHETIC FIXTURE -- invented price index"
periodicity = "monthly"
base        = "previous month = 100"
"""

OBSERVATION = """
[[observation]]
period       = "{period}"
value        = {value}
kind         = "cpi_index"
source       = "SYNTHETIC FIXTURE -- invented value."
retrieved_on = "{retrieved_on}"
verified_on  = ""
"""


def _file(tmp_path: Path, body: str, *, name: str = "xx.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _valid(tmp_path: Path, *, name: str = "xx.toml") -> Path:
    """A two-month series that loads cleanly, so each case below changes exactly one thing."""
    body = HEADER + OBSERVATION.format(period="2025-01", value=100.9, retrieved_on="2026-08-23")
    body += OBSERVATION.format(period="2025-02", value=101.2, retrieved_on="2026-08-23")
    return _file(tmp_path, body, name=name)


def _load_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.cpi_from_file(path)
    return caught.value


def test_the_control_case_loads_so_every_refusal_below_is_about_one_change(
    tmp_path: Path,
) -> None:
    """Without this, a battery of red cases could all be failing for a reason nobody chose."""
    series = loader.cpi_from_file(_valid(tmp_path))

    assert series.id == "xx_cpi_monthly"
    assert series.periodicity == "monthly"
    assert tuple(item.period for item in series.observations) == ("2025-01", "2025-02")
    assert all(item.kind == "cpi_index" for item in series.observations)


def test_a_malformed_value_is_refused_rather_than_coerced(tmp_path: Path) -> None:
    """``"100.9"`` is a string. Reading it as a number would make the file's type and the
    engine's type disagree while the answer still looked right."""
    body = HEADER + OBSERVATION.format(period="2025-01", value='"100.9"', retrieved_on="2026-08-23")
    error = _load_error(_file(tmp_path, body))

    assert "value" in str(error)
    assert "xx.toml" in str(error)


def test_a_negative_or_zero_index_value_is_refused(tmp_path: Path) -> None:
    """A factor of zero or below makes the chained product zero and the Fisher denominator
    unusable. The constraint on the declaration is what keeps the arithmetic total."""
    for bad in ("0.0", "-1.5"):
        body = HEADER + OBSERVATION.format(period="2025-01", value=bad, retrieved_on="2026-08-23")
        error = _load_error(_file(tmp_path, body))
        assert "value" in str(error), bad


def test_an_unrecognised_field_is_refused(tmp_path: Path) -> None:
    """A misspelled key sitting unread beside the real one is a declaration that does nothing."""
    body = _valid(tmp_path).read_text(encoding="utf-8") + "\nseasonally_adjusted = true\n"
    error = _load_error(_file(tmp_path, body, name="extra.toml"))

    assert "extra.toml" in str(error)


def test_a_missing_required_field_is_refused_and_nothing_is_defaulted(tmp_path: Path) -> None:
    """Each of the observation's six keys, removed one at a time.

    Looped rather than spot-checked, because "no default is substituted" is a claim about
    every field and a test naming two of them would let the next one arrive with a default.
    """
    lines = (
        (HEADER + OBSERVATION.format(period="2025-01", value=100.9, retrieved_on="2026-08-23"))
        .strip()
        .splitlines()
    )
    for dropped in ("period", "value", "kind", "source", "retrieved_on", "verified_on"):
        body = "\n".join(line for line in lines if not line.startswith(dropped))
        error = _load_error(_file(tmp_path, body, name=f"missing_{dropped}.toml"))
        assert f"missing_{dropped}.toml" in str(error), dropped
        assert dropped in str(error), dropped


def test_a_missing_series_field_is_refused(tmp_path: Path) -> None:
    """The identity half: a series that does not say what it measures is not addressable."""
    for dropped in ("id", "country", "index", "periodicity", "base"):
        lines = _valid(tmp_path).read_text(encoding="utf-8").splitlines()
        body = "\n".join(line for line in lines if not line.startswith(dropped))
        error = _load_error(_file(tmp_path, body, name=f"series_{dropped}.toml"))
        assert f"series_{dropped}.toml" in str(error), dropped


def test_an_empty_identity_field_is_refused_separately_from_a_missing_one(
    tmp_path: Path,
) -> None:
    """``id = ""`` is not a missing key, which is why it is checked in the loader."""
    body = _valid(tmp_path).read_text(encoding="utf-8").replace('"xx_cpi_monthly"', '""')
    error = _load_error(_file(tmp_path, body, name="blank.toml"))

    assert "blank.toml" in str(error)
    assert "id" in str(error)


def test_a_blank_citation_is_refused(tmp_path: Path) -> None:
    """An observed value with no source is the thing Principle I exists to forbid."""
    body = (
        _valid(tmp_path)
        .read_text(encoding="utf-8")
        .replace('source       = "SYNTHETIC FIXTURE -- invented value."', 'source       = ""')
    )
    error = _load_error(_file(tmp_path, body, name="uncited.toml"))

    assert "source" in str(error)


def test_an_empty_verification_date_loads_and_marks_the_observation(tmp_path: Path) -> None:
    """The expected state of every shipped value: present, empty, and marked (FR-001)."""
    series = loader.cpi_from_file(_valid(tmp_path))

    assert all(
        ref.verified_on is None for item in series.observations for ref in item.provenance.sources
    )


def test_a_duplicate_period_is_refused_and_neither_copy_wins(tmp_path: Path) -> None:
    """Two rows for one month is a file that was edited twice, not a value with two readings."""
    body = HEADER
    body += OBSERVATION.format(period="2025-01", value=100.9, retrieved_on="2026-08-23")
    body += OBSERVATION.format(period="2025-01", value=101.5, retrieved_on="2026-08-23")
    error = _load_error(_file(tmp_path, body, name="dupe.toml"))

    assert "2025-01" in str(error)
    assert "dupe.toml" in str(error)


def test_periods_running_backwards_are_refused(tmp_path: Path) -> None:
    """Strictly ascending, which is what "overlapping" means for a series of whole months."""
    body = HEADER
    body += OBSERVATION.format(period="2025-03", value=100.9, retrieved_on="2026-08-23")
    body += OBSERVATION.format(period="2025-02", value=101.2, retrieved_on="2026-08-23")
    error = _load_error(_file(tmp_path, body, name="backwards.toml"))

    assert "2025-02" in str(error)


def test_a_gap_between_declared_months_still_loads(tmp_path: Path) -> None:
    """A gap is a *fact* about what the publisher published, and FR-004 forbids inventing one.

    The refusal for a gap belongs to the deflation, not to the load: ``coverage`` reports it
    naming the missing month, for the window actually asked about. Refusing the file instead
    would make an unusable series indistinguishable from an incomplete one, and would stop the
    owner declaring what he genuinely has.
    """
    body = HEADER
    body += OBSERVATION.format(period="2025-01", value=100.9, retrieved_on="2026-08-23")
    body += OBSERVATION.format(period="2025-04", value=101.2, retrieved_on="2026-08-23")
    series = loader.cpi_from_file(_file(tmp_path, body, name="gapped.toml"))

    assert tuple(item.period for item in series.observations) == ("2025-01", "2025-04")


def test_a_period_inconsistent_with_the_declared_periodicity_is_refused(
    tmp_path: Path,
) -> None:
    """A monthly series declares whole months. ``2025-01-15`` and ``2025-Q1`` are not months."""
    for bad in ("2025-01-15", "2025-Q1", "2025", "2025-13"):
        body = HEADER + OBSERVATION.format(period=bad, value=100.9, retrieved_on="2026-08-23")
        error = _load_error(_file(tmp_path, body, name="periodicity.toml"))
        assert bad in str(error), bad
        assert "monthly" in str(error), bad


def test_an_unknown_periodicity_is_refused_and_the_known_ones_are_listed(
    tmp_path: Path,
) -> None:
    """No fallback: annualising a quarterly series as monthly is wrong by a factor of three."""
    body = _valid(tmp_path).read_text(encoding="utf-8").replace('"monthly"', '"quarterly"')
    error = _load_error(_file(tmp_path, body, name="quarterly.toml"))

    assert "quarterly" in str(error)
    assert "monthly" in str(error)


def test_a_period_that_had_not_elapsed_when_it_was_retrieved_is_refused(
    tmp_path: Path,
) -> None:
    """A value for a month still running is a forecast wearing an observation's clothes.

    Aged against the observation's own ``retrieved_on`` rather than a clock, so the same file
    loads the same way for ever. A month can only be published after it has ended.
    """
    body = HEADER + OBSERVATION.format(period="2026-08", value=100.9, retrieved_on="2026-08-23")
    error = _load_error(_file(tmp_path, body, name="future.toml"))

    assert "2026-08" in str(error)
    assert "future.toml" in str(error)


def test_the_month_before_the_retrieval_month_is_accepted(tmp_path: Path) -> None:
    """The boundary, from the other side: July's index retrieved in August is an observation."""
    body = HEADER + OBSERVATION.format(period="2026-07", value=100.9, retrieved_on="2026-08-23")
    series = loader.cpi_from_file(_file(tmp_path, body, name="july.toml"))

    assert series.observations[0].period == "2026-07"


def test_a_series_with_no_observations_is_refused(tmp_path: Path) -> None:
    """An empty series would make every window uncovered for a reason naming the window."""
    error = _load_error(_file(tmp_path, HEADER, name="empty.toml"))

    assert "empty.toml" in str(error)


def test_a_missing_file_is_reported_rather_than_read_as_an_empty_series(
    tmp_path: Path,
) -> None:
    error = _load_error(tmp_path / "nowhere.toml")

    assert "nowhere.toml" in str(error)


# --- the cross-file check -------------------------------------------------------------


@pytest.fixture
def scratch_root(tmp_path: Path) -> Path:
    """A data root holding only ``cpi/``, so the resolver's own glob is what is under test."""
    root = tmp_path / "data"
    (root / "cpi").mkdir(parents=True)
    return root


def test_two_files_declaring_one_series_identity_are_refused_naming_both(
    scratch_root: Path,
) -> None:
    """Whichever loaded second would win by directory order, and nothing would say so."""
    for name in ("a.toml", "b.toml"):
        _valid(scratch_root / "cpi", name=name)

    with pytest.raises(DeclarationError) as caught:
        resolver.inflation_from_data_root(scratch_root)

    assert "a.toml" in str(caught.value)
    assert "b.toml" in str(caught.value)
    assert "xx_cpi_monthly" in str(caught.value)


# --- the file the project actually uses ------------------------------------------------


def test_the_shipped_ukrainian_series_loads_and_is_what_the_header_claims() -> None:
    """A battery of broken fixtures proves nothing about the file in ``data/``.

    411 monthly observations, 1991-08 to 2025-10, from Держстат via data.gov.ua. Every one of
    them unverified, which is the honest state: they were downloaded, and nobody has checked
    them against the publisher.
    """
    series = loader.cpi_from_file(SHIPPED)

    assert series.id == "ua_cpi_monthly"
    assert series.country == "UA"
    assert series.periodicity == "monthly"
    assert len(series.observations) == 411
    assert series.observations[0].period == "1991-08"
    assert series.observations[-1].period == "2025-10"
    assert all(item.value > 0.0 for item in series.observations)


def test_every_shipped_observation_is_cited_unverified_and_ages_under_the_cpi_kind() -> None:
    """FR-001 and FR-005 on the real file: a citation on every month, a kind on every month."""
    series = loader.cpi_from_file(SHIPPED)
    sources = [ref for item in series.observations for ref in item.provenance.sources]

    assert len(sources) == 411
    assert all(ref.citation.strip() for ref in sources)
    assert all(ref.verified_on is None for ref in sources)
    assert {item.kind for item in series.observations} == {"cpi_index"}


def test_every_shipped_observation_has_its_own_source_id() -> None:
    """One ref per month, so a figure over a long window names every month it chained.

    A shared ref would collapse 411 sources into one in a frozenset and make the provenance
    count in ``test_provenance_propagation.py`` pass for the wrong reason (research.md D6).
    """
    series = loader.cpi_from_file(SHIPPED)
    ids = {ref.id for item in series.observations for ref in item.provenance.sources}

    assert len(ids) == 411


def test_the_shipped_series_is_reachable_from_the_data_root_by_its_declared_id() -> None:
    """The resolver keys by declared identity, not by file name (FR-002)."""
    declarations = resolver.inflation_from_data_root(DATA_ROOT)

    assert "ua_cpi_monthly" in declarations.series
    assert declarations.series_files["ua_cpi_monthly"] == SHIPPED


def test_a_scratch_copy_of_the_shipped_file_still_loads(tmp_path: Path) -> None:
    """Guards the shipped-file tests against passing because of something in the repo root."""
    copied = tmp_path / "ua.toml"
    shutil.copy(SHIPPED, copied)

    assert len(loader.cpi_from_file(copied).observations) == 411
