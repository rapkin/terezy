"""``scripts/check_provenance.py`` is fail-closed over the data tree.

The gate is the mechanical half of Principle I -- no legal, tax or fee value without a
citation -- and a gate is only as good as its coverage. Its directory list was an
*allowlist*: a directory under ``data/`` that nobody added to ``SOURCED_DIRS`` was silently
never scanned, so the place a future rate was most likely to land -- a new directory -- was
exactly the place the gate could not see. Fail-open is the defect class the constitution
puts at top severity, in a script whose whole job is to prevent it.

So the rule under test: **every directory under ``data/`` is either scanned or exempted by
name with a recorded reason, and an unknown directory is an error.** The exemptions are the
argued ones (``data/README.md``): scenarios, objectives and strategies hold the owner's own
stated beliefs and decisions, streams his own statement of where money lands, and ``user/``
is the gitignored per-user boundary of Principle VII.

Run through a subprocess, against the script itself, because the script is the gate CI
runs: importing pieces of it would test a different program.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from terezy.data.declarations.loader import INFERENCE_MARKER, INFERENCES
from tests import data_roots

pytestmark = pytest.mark.contract

SCRIPT = data_roots.REPO_ROOT / "scripts" / "check_provenance.py"

DATA_ROOT = data_roots.with_fixtures()
"""**The fixture overlay is scanned, and this is where.** CI runs the script bare, over
``data/`` alone, so the invented declarations in ``tests/fixtures/data/`` would otherwise sit
outside the one gate that reads a citation -- and they carry the same four keys every shipped
table does. Scanning them here rather than teaching the script a second default root keeps the
gate CI runs identical to the gate a reader runs by hand.
"""


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _scratch_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)
    return root


def test_the_shipped_data_root_is_clean() -> None:
    """What CI checks, checked here too: the tree the script scans by default passes."""
    outcome = _run(data_roots.SHIPPED)
    assert outcome.returncode == 0, outcome.stdout


def test_the_fixture_overlay_is_clean_too(tmp_path: Path) -> None:
    """The baseline the cases below mutate, and the only scan the fixtures ever get."""
    outcome = _run(_scratch_root(tmp_path))
    assert outcome.returncode == 0, outcome.stdout


def test_an_unknown_directory_under_data_is_an_error_not_a_blind_spot(
    tmp_path: Path,
) -> None:
    """The fail-closed rule itself.

    A new directory carrying an uncited rate must fail the gate *because the directory is
    unknown* -- before anyone remembers to add it to the scanned set. The rate inside it is
    deliberately uncited: under the old allowlist this tree passed clean.
    """
    root = _scratch_root(tmp_path)
    lending = root / "lending"
    lending.mkdir()
    (lending / "rates.toml").write_text(
        '[[rate]]\nid = "usd_lending"\napr_pct = 9.5\n', encoding="utf-8"
    )
    outcome = _run(root)
    assert outcome.returncode == 1
    assert "lending" in outcome.stdout
    assert "SOURCED_DIRS" in outcome.stdout
    assert "EXEMPT_DIRS" in outcome.stdout


def test_the_argued_exemptions_are_by_name_with_a_reason(tmp_path: Path) -> None:
    """streams and scenarios (and the README's other argued cases) stay exempt -- but only
    because they are named, so removing a name makes the gate red rather than blind."""
    root = _scratch_root(tmp_path)
    outcome = _run(root)
    assert outcome.returncode == 0
    # The shipped tree contains the exempt directories; a fail-closed gate that passed
    # while not knowing them would be fail-open with extra steps.
    for exempt in ("streams", "scenarios"):
        assert (root / exempt).is_dir()


def test_a_root_level_file_is_scanned_rather_than_invisible(tmp_path: Path) -> None:
    """``venues.toml`` sits at the data root, outside every directory.

    It carries no observed value today, so it passes -- and it must be *scanned*
    to pass, not skipped: an observed value added to it without a citation is an error, which
    is the difference between "checked and clean" and "never looked at".
    """
    root = _scratch_root(tmp_path)
    clean = _run(root)
    assert clean.returncode == 0

    venues = root / "venues.toml"
    venues.write_text(
        venues.read_text(encoding="utf-8").replace(
            'currencies = ["UAH", "USD"]',
            'currencies = ["UAH", "USD"]\ndaily_limit = 100000.0',
            1,
        ),
        encoding="utf-8",
    )
    dirty = _run(root)
    assert dirty.returncode == 1
    assert "venues.toml" in dirty.stdout


# ---------------------------------------------------------------------------
# 013-enumerated-schedule: the gate's first relation
# ---------------------------------------------------------------------------
#
# Everything above is shape -- a table carrying an observed value needs a citation. SC-013 asks
# for a *relation*: an inferred value must have a source saying it is an inference and a
# task saying what would settle it. The two halves fail separately because the fixes
# differ.

ENUMERATED = "instruments/ovdp_enumerated_a.toml"


def _mutated(tmp_path: Path, old: str, new: str) -> subprocess.CompletedProcess[str]:
    root = _scratch_root(tmp_path)
    declaration = root / ENUMERATED
    text = declaration.read_text(encoding="utf-8")
    assert old in text, f"the fixture no longer contains {old!r}"
    declaration.write_text(text.replace(old, new, 1), encoding="utf-8")
    return _run(root)


def test_an_inferred_value_whose_source_does_not_say_so_is_an_error(tmp_path: Path) -> None:
    outcome = _mutated(tmp_path, 'source       = "INFERENCE:', 'source       = "')
    assert outcome.returncode == 1, outcome.stdout
    assert ENUMERATED in outcome.stdout
    assert "instrument.schedule" in outcome.stdout


def test_an_inferred_value_carrying_a_verification_date_is_an_error(tmp_path: Path) -> None:
    """An inference is unverified by construction. What a later reading verifies is the
    source it rests on, and that is a different table."""
    outcome = _mutated(
        tmp_path,
        'verified_on  = ""\n\n  [[instrument.schedule.payment]]',
        'verified_on  = "2026-08-29"\n\n  [[instrument.schedule.payment]]',
    )
    assert outcome.returncode == 1, outcome.stdout
    assert "verification date on an inferred value" in outcome.stdout


def test_an_inference_with_no_verification_task_is_an_error(tmp_path: Path) -> None:
    outcome = _mutated(tmp_path, 'settles     = "coverage"', 'settles     = "face_value"')
    assert outcome.returncode == 1, outcome.stdout
    assert ENUMERATED in outcome.stdout
    assert "coverage" in outcome.stdout


def test_the_checks_run_on_no_other_declaration_kind(tmp_path: Path) -> None:
    """A bond declared by its terms infers none of this, and a fund's verification tasks
    answer a different question. The shipped tree contains both and stays clean."""
    root = _scratch_root(tmp_path)
    (root / ENUMERATED).unlink()
    assert _run(root).returncode == 0


def test_the_gate_and_the_loader_agree_on_what_is_inferred() -> None:
    """The gate copies the loader's list, because a script that imported the engine would
    stop being runnable by someone who has not installed it. A copy nothing checks is the
    copy that goes stale, so this checks it."""
    gate: dict[str, object] = {}
    exec(
        compile(
            "\n".join(
                line
                for line in SCRIPT.read_text(encoding="utf-8").splitlines()
                if line.startswith(("INFERRED =", "INFERENCE_MARKER ="))
            ),
            str(SCRIPT),
            "exec",
        ),
        gate,
    )
    assert set(gate["INFERRED"]) == set(INFERENCES)  # type: ignore[call-overload]
    assert gate["INFERENCE_MARKER"] == INFERENCE_MARKER


def test_a_malformed_schedule_does_not_hide_a_missing_verification_task(
    tmp_path: Path,
) -> None:
    """The fail-open shape this gate exists to prevent, in the gate itself.

    A file whose `[instrument.schedule]` is broken *and* which records no verification task
    used to pass clean: the check returned early on the shape fault, on the reading that the
    loader reports that one and names the field — which is true, and skipped the relation
    this check exists for. The loader and the gate answer different questions, and a file
    that fails one is not thereby excused the other.
    """
    root = _scratch_root(tmp_path)
    declaration = root / ENUMERATED
    lines = declaration.read_text(encoding="utf-8").splitlines(keepends=True)
    first_task = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("[[instrument.verification_task]]")
    )
    declaration.write_text(
        "".join(lines[:first_task]).replace(
            "\n[instrument.schedule]\n", "\n[instrument.schedule_typo]\n"
        ),
        encoding="utf-8",
    )

    outcome = _run(root)
    assert outcome.returncode == 1, outcome.stdout
    for inference in sorted(INFERENCES):
        assert inference in outcome.stdout


# ---------------------------------------------------------------------------
# 017 FR-006: an observation is not always a number
# ---------------------------------------------------------------------------
#
# ``check_table`` gates the citation loop **and** the observation-kind check on one predicate,
# so a table that predicate does not recognise passes uncited *and* with an unvalidated kind
# at once. A working-day classification is a date and a label and holds no number at all,
# which is why both halves are asserted below rather than only the citation.

PLANTED = "observations/planted_classification.toml"

PLANTED_ROW = """[[classification]]
on           = "2026-01-01"
label        = "a date, a label, and no number anywhere"
kind         = "tax_rule"
source       = "planted by tests/contract/test_provenance_gate.py"
retrieved_on = "2026-08-30"
verified_on  = ""
"""


def _planted(tmp_path: Path, row: str) -> subprocess.CompletedProcess[str]:
    root = _scratch_root(tmp_path)
    (root / PLANTED).write_text(row, encoding="utf-8")
    return _run(root)


def test_a_numberless_table_is_reached_by_the_gate(tmp_path: Path) -> None:
    """Cited and correctly kinded, the row passes -- and the gate says so by naming it
    unverified, which is the two failures below being the gate reading the row rather than
    the gate never opening the file."""
    outcome = _planted(tmp_path, PLANTED_ROW)
    assert outcome.returncode == 0, outcome.stdout
    assert "planted_classification.toml: 1 unverified" in outcome.stdout


def test_a_numberless_table_without_a_citation_is_an_error(tmp_path: Path) -> None:
    outcome = _planted(
        tmp_path,
        PLANTED_ROW.replace(
            'source       = "planted by tests/contract/test_provenance_gate.py"\n', ""
        ),
    )
    assert outcome.returncode == 1, outcome.stdout
    assert "carries observed values but has no 'source'" in outcome.stdout


def test_a_bare_toml_date_literal_is_an_observation_too(tmp_path: Path) -> None:
    """The other half of `_is_dated`, which no shipped file reaches: every date under `data/`
    is a quoted string today, so the literal spelling is only ever exercised here."""
    outcome = _planted(
        tmp_path,
        PLANTED_ROW.replace('on           = "2026-01-01"', "on           = 2026-01-01").replace(
            'source       = "planted by tests/contract/test_provenance_gate.py"\n', ""
        ),
    )
    assert outcome.returncode == 1, outcome.stdout
    assert "carries observed values but has no 'source'" in outcome.stdout


def test_a_numberless_table_naming_an_undeclared_kind_is_an_error(tmp_path: Path) -> None:
    """The other half of the same predicate. A citation vouches for the value; the kind is
    what decides when it goes stale, and neither is asked for without the other."""
    outcome = _planted(
        tmp_path, PLANTED_ROW.replace('kind         = "tax_rule"', 'kind         = "no_such_kind"')
    )
    assert outcome.returncode == 1, outcome.stdout
    assert "names the observation kind 'no_such_kind'" in outcome.stdout


# ---------------------------------------------------------------------------
# 018-nbu-rate-series: a gate whose output nobody reads is a gate that is off


def _lines(outcome: subprocess.CompletedProcess[str], level: str) -> list[str]:
    return [line for line in outcome.stdout.splitlines() if line.startswith(f"{level}:")]


def test_each_file_reports_its_unverified_values_as_one_line(tmp_path: Path) -> None:
    """018 FR-023. One warning per value put 3,143 lines in front of a reader after the NBU
    series landed, burying the 704 that were there to be read. Runtime was never the problem
    and never becomes one: the gate walks the whole tree in under a second either way.
    """
    outcome = _run(_scratch_root(tmp_path))
    warnings = _lines(outcome, "warning")

    named = [line.split(":")[1].strip() for line in warnings]
    assert len(named) == len(set(named)), f"a file is reported twice: {sorted(named)}"


def test_the_line_for_a_file_states_how_many_of_its_values_are_unverified(
    tmp_path: Path,
) -> None:
    """The count is what the summary must not lose: a per-file mark that collapsed to
    "this file has some" would read identically for one value and for two thousand.
    """
    root = _scratch_root(tmp_path)
    rates = root / "official_rates" / "ua_nbu_usd.toml"
    declared = tomllib.loads(rates.read_text(encoding="utf-8"))
    expected = sum(1 for entry in declared["observation"] if not entry["verified_on"])
    assert expected > 1_000, "this assertion is about a long series; the shipped one is short"

    (line,) = [
        text for text in _lines(_run(root), "warning") if "official_rates/ua_nbu_usd.toml" in text
    ]

    assert f"{expected} unverified" in line


def test_the_whole_output_grows_by_one_line_for_a_file_however_long_it_is(
    tmp_path: Path,
) -> None:
    """The claim FR-023 actually makes, and it is about lines rather than about values."""
    root = _scratch_root(tmp_path)
    with_series = len(_run(root).stdout.splitlines())
    (root / "official_rates" / "ua_nbu_usd.toml").unlink()
    without = len(_run(root).stdout.splitlines())

    assert with_series - without == 1


def test_errors_stay_one_line_per_value(tmp_path: Path) -> None:
    """An error is a thing to be fixed, and there are none; a summary would hide which."""
    root = _scratch_root(tmp_path)
    (root / PLANTED).write_text(
        PLANTED_ROW.replace(
            'source       = "planted by tests/contract/test_provenance_gate.py"\n', ""
        )
        + PLANTED_ROW.replace(
            'source       = "planted by tests/contract/test_provenance_gate.py"\n', ""
        ).replace("2026-01-01", "2026-01-02"),
        encoding="utf-8",
    )
    outcome = _run(root)

    assert outcome.returncode == 1
    planted = [line for line in _lines(outcome, "error") if PLANTED in line]
    assert len(planted) == 2, outcome.stdout


# ---------------------------------------------------------------------------
# 017 SC-005: the same demonstration on a real calendar file, measured as a delta
# ---------------------------------------------------------------------------
#
# The planted rows above establish the predicate. What SC-005 adds is the measurement FR-006a
# asks for: the gate's **complete finding set** before and after, because a widening would be
# caught by CI and a narrowing would not — and a narrowing in the gate whose job is preventing
# blind spots is the worst available outcome. Asserting only that one deleted `source` now
# fails does not see a narrowing at all.

PLANTED_CALENDAR = "calendars/planted_extra.toml"

PLANTED_CALENDAR_FILE = """[calendar]
id           = "planted_civil"
jurisdiction = "XX"
authority    = "planted by tests/contract/test_provenance_gate.py"
scope        = "civil"

[calendar.coverage]
first        = "2026-03-01"
last         = "2026-03-31"
kind         = "tax_rule"
source       = "planted by tests/contract/test_provenance_gate.py"
retrieved_on = "2026-08-31"
verified_on  = ""

[calendar.week]
rest_days    = ["sunday"]
starts_on    = "monday"
kind         = "tax_rule"
source       = "planted by tests/contract/test_provenance_gate.py"
retrieved_on = "2026-08-31"
verified_on  = ""
"""

PLANTED_CALENDAR_ROW = """[[day]]
on_date        = "2026-03-05"
classification = "public_holiday"
pre_holiday    = false
kind           = "tax_rule"
source         = "planted by tests/contract/test_provenance_gate.py"
retrieved_on   = "2026-08-31"
verified_on    = ""
"""


def _with_calendar(tmp_path: Path, text: str, under: str) -> subprocess.CompletedProcess[str]:
    """A fresh scratch root carrying one planted calendar. ``under`` keeps two calls in one
    test from copying the tree over each other."""
    root = _scratch_root(tmp_path / under)
    (root / PLANTED_CALENDAR).write_text(text, encoding="utf-8")
    return _run(root)


def _findings(outcome: subprocess.CompletedProcess[str], root: Path) -> set[str]:
    """The gate's whole finding set, with the scratch root stripped off the front of each line.

    Stripped because a `tmp_path` differs between two runs, and a set difference over
    unstripped lines would report every file as both added and removed.
    """
    return {
        line.replace(f"{root}/", "")
        for line in outcome.stdout.splitlines()
        if line.startswith(("error:", "warning:"))
    }


def test_adding_a_calendar_row_moves_the_gates_finding_set_by_exactly_that_file(
    tmp_path: Path,
) -> None:
    """FR-006a's delta, on a real calendar file rather than a planted table.

    The predicate `_has_observed_value` is shared by **every** entry in `SOURCED_DIRS`, so what
    has to be shown is that reaching a calendar's rows did not stop the gate reaching anything
    else. The set difference is what shows it; a single new assertion would not.
    """
    root = _scratch_root(tmp_path)
    baseline = _findings(_run(root), root)
    (root / PLANTED_CALENDAR).write_text(
        PLANTED_CALENDAR_FILE + PLANTED_CALENDAR_ROW, encoding="utf-8"
    )
    withrow = _findings(_run(root), root)
    added = withrow - baseline
    assert added == {
        "warning: calendars/planted_extra.toml: 2 unverified value(s); "
        "each must render visibly marked"
    }
    assert not baseline - withrow, "the gate stopped reaching something it used to reach"


def test_deleting_a_calendar_rows_citation_fails_the_gate(tmp_path: Path) -> None:
    """SC-005: FR-006's fix bites on a real calendar row, shown by counting.

    Two unverified values before -- the window and the row -- and after the deletion the row's
    warning is replaced by an **error** naming it. The count is asserted
    rather than the mere presence of a failure, because a gate that errored on the whole file
    and a gate that errored on the row are different gates and only one of them is useful.
    """
    cited = _with_calendar(tmp_path, PLANTED_CALENDAR_FILE + PLANTED_CALENDAR_ROW, "cited")
    assert cited.returncode == 0, cited.stdout
    assert not _lines(cited, "error")

    uncited = _with_calendar(
        tmp_path,
        PLANTED_CALENDAR_FILE
        + PLANTED_CALENDAR_ROW.replace(
            'source         = "planted by tests/contract/test_provenance_gate.py"\n', ""
        ),
        "uncited",
    )
    assert uncited.returncode == 1, uncited.stdout
    errors = _lines(uncited, "error")
    assert len(errors) == 1, errors
    assert "calendars/planted_extra.toml" in errors[0]
    assert "day[0]" in errors[0]
    assert "has no 'source'" in errors[0]
