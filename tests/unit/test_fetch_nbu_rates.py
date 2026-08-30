"""``scripts/fetch_nbu_rates.py``: what it refuses, what it drops, and what it never invents.

018 SC-004, SC-005, SC-007 and SC-020.

**Every rate in this module is invented**, and none of them is near a figure the National Bank
has published for any date. The responses are constructed here rather than captured, for two
reasons: a checked-in capture is a retrieval nobody can date, and its values would look exactly
like the real ones (spec.md, Assumptions). What is under test is the script's handling of
*shape* — a changed unit, a short range, a hole, a row for the day after — and shape needs no
real rates.

**No socket is opened.** ``_get`` is replaced with a function returning constructed bytes, which
is the seam the whole script hangs from; ``tests/conftest.py`` fails loudly if anything reaches
past it.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from terezy.data.declarations import loader

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "fetch_nbu_rates.py"
SHIPPED = REPO_ROOT / "data" / "official_rates" / "ua_nbu_usd.toml"


def _load() -> Any:
    """The script as a module. It lives outside the package, so it is loaded by path.

    Registered in ``sys.modules`` before execution because ``dataclasses`` resolves a field's
    annotations through the module it is defined in, and a module absent from the table has
    none to resolve through.
    """
    spec = importlib.util.spec_from_file_location("fetch_nbu_rates", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fetch_nbu_rates = _load()

FIRST = date(2019, 12, 28)
"""The first date the National Bank quotes USD per one unit, and the series' lower bound."""

TODAY = date(2020, 1, 5)
"""The retrieval date every test below pretends to run on. Nine days of window."""

INVENTED_FIRST = 11.1111
"""SYNTHETIC. Every value below is this plus a whole number of days, so a rate that escaped
into an output would be recognisable as arithmetic rather than as a quote."""

CALCDATE = "27.12.2019"
"""SYNTHETIC establishment date, carried through unchanged so the citation can be checked."""


def _value(day: date) -> float:
    return INVENTED_FIRST + (day - FIRST).days


def _row(day: date, **overrides: Any) -> dict[str, Any]:
    row = {
        "exchangedate": day.strftime("%d.%m.%Y"),
        "r030": 840,
        "cc": "USD",
        "txt": "SYNTHETIC",
        "enname": "SYNTHETIC",
        "rate": _value(day),
        "units": 1,
        "rate_per_unit": _value(day),
        "group": "1",
        "calcdate": CALCDATE,
        "special": "N",
    }
    row.update(overrides)
    return row


def _days(last: date = TODAY) -> list[date]:
    return [FIRST + timedelta(days=offset) for offset in range((last - FIRST).days + 1)]


def _payload(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows).encode("utf-8")


def _complete() -> bytes:
    """Every calendar day of the window, nothing else."""
    return _payload([_row(day) for day in _days()])


def _serving(payload: bytes) -> Any:
    return lambda url: payload  # noqa: ARG005 -- the URL is what the script builds, not input


def _fetched(payload: bytes, *, today: date = TODAY) -> Any:
    fetch_nbu_rates._get = _serving(payload)
    return fetch_nbu_rates.fetch(today=today)


def _rendered(
    payload: bytes = b"", *, verified: Mapping[date, tuple[float, str]] | None = None
) -> str:
    rendered: str = fetch_nbu_rates.render(
        _fetched(payload or _complete()), verified=verified or {}
    )
    return rendered


def _verifications_in(text: str) -> dict[date, str]:
    return {
        on_date: verified for on_date, _value_, verified in fetch_nbu_rates.observations_in(text)
    }


def _run(payload: bytes, out: Path, *, today: date = TODAY) -> int:
    fetch_nbu_rates._get = _serving(payload)
    code: int = fetch_nbu_rates.main(["--out", str(out)], today=today)
    return code


@pytest.fixture
def out(tmp_path: Path) -> Path:
    """A copy of the shipped declaration, so "writes nothing" can be checked byte for byte."""
    destination = tmp_path / "ua_nbu_usd.toml"
    shutil.copy(SHIPPED, destination)
    return destination


class TestTheSameResponseOnTheSameDayRendersTheSameBytes:
    """SC-004. The rendering takes the retrieval date as an argument and touches no disk."""

    def test_two_renderings_of_one_response_are_byte_identical(self) -> None:
        assert _rendered() == _rendered()

    def test_two_whole_runs_on_one_day_leave_byte_identical_files(self, out: Path) -> None:
        assert _run(_complete(), out) == 0
        first = out.read_bytes()
        assert _run(_complete(), out) == 0
        assert out.read_bytes() == first

    def test_a_different_retrieval_date_is_the_only_thing_that_moves_a_common_row(self) -> None:
        """The clock reaches the file through one field, so the rest is a function of the
        response alone -- which is what makes a diff after a re-fetch readable."""
        earlier = fetch_nbu_rates.render(
            _fetched(
                _payload([_row(day) for day in _days(TODAY - timedelta(days=1))]),
                today=TODAY - timedelta(days=1),
            ),
            verified={},
        )
        assert 'retrieved_on = "2020-01-04"' in earlier
        assert 'retrieved_on = "2020-01-05"' in _rendered()
        assert f"value        = {_value(FIRST)}" in earlier
        assert f"value        = {_value(FIRST)}" in _rendered()


class TestASurpriseInTheResponseWritesNothingAtAll:
    """SC-005 and FR-004. Each case names what surprised it and leaves the file untouched."""

    @staticmethod
    def _refused(payload: bytes, out: Path, *, saying: tuple[str, ...]) -> None:
        before = out.read_bytes()
        assert _run(payload, out) == 1
        assert out.read_bytes() == before

        with pytest.raises(fetch_nbu_rates.FetchError) as caught:
            _fetched(payload)
        for fragment in saying:
            assert fragment in str(caught.value), (fragment, str(caught.value))

    def test_a_row_quoted_per_a_hundred_units_refuses_the_whole_run(self, out: Path) -> None:
        """FR-008. Not normalised and not skipped: a value silently divided by 100 to fit the
        declared unit is wrong by two orders of magnitude while every figure stays plausible."""
        rows = [_row(day) for day in _days()]
        rows[3] = _row(_days()[3], units=100, rate=_value(_days()[3]) * 100)
        self._refused(_payload(rows), out, saying=("31.12.2019", "100", "1.0", "quotation_unit"))

    def test_a_range_shorter_than_the_required_window_refuses(self, out: Path) -> None:
        """A short range is a shape surprise, not a set of gaps: writing it would turn one
        failed retrieval into a permanent, plausible hole in a legal series."""
        short = _payload([_row(day) for day in _days(TODAY - timedelta(days=2))])
        self._refused(short, out, saying=("2020-01-05", "2020-01-04"))

    def test_a_hole_inside_the_window_refuses(self, out: Path) -> None:
        rows = [_row(day) for day in _days() if day != FIRST + timedelta(days=2)]
        self._refused(_payload(rows), out, saying=("2019-12-30",))

    def test_a_range_starting_after_the_lower_bound_refuses(self, out: Path) -> None:
        rows = [_row(day) for day in _days()[1:]]
        self._refused(_payload(rows), out, saying=("2019-12-28",))

    def test_an_unrecognised_field_refuses(self, out: Path) -> None:
        """The publisher changing its shape is a thing to read about, not to route around."""
        rows = [_row(day) for day in _days()]
        rows[0] = _row(_days()[0], surprise=1)
        self._refused(_payload(rows), out, saying=("surprise",))

    def test_a_missing_field_refuses(self, out: Path) -> None:
        rows = [_row(day) for day in _days()]
        del rows[0]["calcdate"]
        self._refused(_payload(rows), out, saying=("calcdate",))

    def test_a_row_for_another_currency_refuses(self, out: Path) -> None:
        rows = [_row(day) for day in _days()]
        rows[2] = _row(_days()[2], cc="EUR")
        self._refused(_payload(rows), out, saying=("EUR", "USD"))

    def test_a_non_positive_rate_refuses(self, out: Path) -> None:
        rows = [_row(day) for day in _days()]
        rows[1] = _row(_days()[1], rate=0.0)
        self._refused(_payload(rows), out, saying=("2019-12-29",))

    def test_a_response_that_is_not_a_list_of_rows_refuses(self, out: Path) -> None:
        self._refused(b'{"error": "nope"}', out, saying=("list",))

    def test_an_empty_response_refuses(self, out: Path) -> None:
        self._refused(b"[]", out, saying=("no rows",))


class TestThePublishersDayAheadRateIsDeclined:
    """SC-020 and FR-010. The publisher runs a day ahead; the schema refuses a rate dated
    after its own retrieval, so writing everything on offer produces a file that does not
    load at all."""

    def _with_tomorrow(self) -> bytes:
        return _payload([_row(day) for day in _days(TODAY + timedelta(days=1))])

    def test_the_row_after_the_retrieval_date_is_dropped_and_named(self) -> None:
        fetched = _fetched(self._with_tomorrow())

        assert fetched.declined == (TODAY + timedelta(days=1),)
        assert fetched.rows[-1].on_date == TODAY

    def test_the_rendered_file_ends_on_the_retrieval_date(self) -> None:
        rendered = fetch_nbu_rates.render(_fetched(self._with_tomorrow()), verified={})

        assert 'on_date      = "2020-01-05"' in rendered
        assert 'on_date      = "2020-01-06"' not in rendered

    def test_no_rendered_observation_is_dated_after_its_own_retrieval(self) -> None:
        rendered = fetch_nbu_rates.render(_fetched(self._with_tomorrow()), verified={})

        assert max(_verifications_in(rendered)) == TODAY


class TestWhatARerunDoesToAVerificationSomebodyPerformed:
    """SC-007 and FR-006. ``verified_on`` is per observation and attests to *that* value."""

    def test_the_script_writes_an_empty_verification_on_every_row_it_creates(self) -> None:
        """FR-005. A downloaded number is not a checked number, and no automation may say
        otherwise."""
        rendered = _rendered()
        rows = list(fetch_nbu_rates.observations_in(rendered))

        assert len(rows) == len(_days())
        assert {verified for _d, _v, verified in rows} == {""}

    def test_a_verification_survives_a_rerun_whose_published_value_is_unchanged(self) -> None:
        checked = {FIRST: (_value(FIRST), "2026-08-31")}
        rendered = _rendered(verified=checked)

        assert _verifications_in(rendered)[FIRST] == "2026-08-31"

    def test_a_verification_is_cleared_when_the_published_value_has_changed(self) -> None:
        """The attestation was about a different number, so it says nothing about this one."""
        checked = {FIRST: (_value(FIRST) + 0.5, "2026-08-31")}
        rendered = _rendered(verified=checked)

        assert _verifications_in(rendered)[FIRST] == ""

    def test_a_verification_of_a_date_no_longer_published_simply_does_not_appear(self) -> None:
        rendered = _rendered(verified={date(1999, 1, 1): (1.0, "2026-08-31")})

        assert "1999-01-01" not in rendered

    def test_a_rerun_reads_the_verifications_off_the_file_it_is_about_to_replace(
        self, out: Path
    ) -> None:
        """The round trip, because the carry-forward is worth nothing if nothing reads it."""
        assert _run(_complete(), out) == 0
        head, marker, tail = out.read_text(encoding="utf-8").partition(
            'on_date      = "2019-12-28"'
        )
        out.write_text(
            head + marker + tail.replace('verified_on  = ""', 'verified_on  = "2026-08-31"', 1),
            encoding="utf-8",
        )
        assert fetch_nbu_rates.verifications(out)[FIRST] == (_value(FIRST), "2026-08-31")

        assert _run(_complete(), out) == 0

        assert _verifications_in(out.read_text(encoding="utf-8"))[FIRST] == "2026-08-31"


class TestWhatItWritesIsADeclarationTheLoaderAccepts:
    """The strongest check available: the real loader reads what the script wrote."""

    def test_the_rendered_file_loads_as_the_declared_series(self, out: Path) -> None:
        assert _run(_complete(), out) == 0
        series = loader.official_rate_from_file(out)

        assert series.id == "ua_nbu_usd"
        assert series.quotation_unit == 1.0
        assert series.rule is None
        assert len(series.observations) == len(_days())
        assert series.observations[0].on_date == FIRST
        assert series.observations[-1].on_date == TODAY

    def test_every_observation_carries_the_url_the_units_and_the_establishment_date(
        self, out: Path
    ) -> None:
        """FR-009 and FR-025: the row's own citation is what makes the unit refusal auditable
        after the fact, and what carries the attribution the licence conditions reuse on."""
        assert _run(_complete(), out) == 0
        for observation in loader.official_rate_from_file(out).observations:
            (source,) = observation.provenance.sources
            assert fetch_nbu_rates.ENDPOINT in source.citation
            assert "valcode=usd" in source.citation
            assert "units = 1" in source.citation
            assert CALCDATE in source.citation
            assert source.verified_on is None
            assert source.kind == "official_rate"

    def test_the_header_names_both_provisions_and_says_what_each_one_does(self, out: Path) -> None:
        """FR-025. The operative term is addressed to a reuser; the hyperlink wording is the
        text of a notice the publisher displays. Neither is asserted to be the other.

        The header is taken as the text before ``[series]``, which is the first thing the file
        declares -- so a provision that had drifted into a row's citation would fail this.
        """
        assert _run(_complete(), out) == 0
        header, marker = out.read_text(encoding="utf-8").partition("[series]")[:2]
        assert marker, "the declaration must have a [series] table for this to be its header"

        assert "2939-VI" in header
        assert "835" in header
        assert "10-1" in header
        assert "будь-яка" in header
        assert "гіперпосилання" in header
        assert "NOTICE" in header

    def test_the_header_states_the_coverage_window_and_forbids_hand_editing(
        self, out: Path
    ) -> None:
        """FR-024."""
        assert _run(_complete(), out) == 0
        header = out.read_text(encoding="utf-8").partition("[[observation]]")[0]

        assert "2019-12-28" in header
        assert TODAY.isoformat() in header
        assert "fetch_nbu_rates.py" in header
        assert "hand-edit" in header


class TestADryRunReportsAndWritesNothing:
    def test_the_file_is_byte_identical_after_a_dry_run(self, out: Path) -> None:
        before = out.read_bytes()
        fetch_nbu_rates._get = _serving(_complete())

        assert fetch_nbu_rates.main(["--out", str(out), "--dry-run"], today=TODAY) == 0
        assert out.read_bytes() == before
