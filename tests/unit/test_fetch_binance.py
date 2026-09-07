"""``scripts/fetch_binance.py``: what it writes, what it refuses, and what it never invents.

025 SC-007 and SC-009.

**Every price in this module is invented**, and the symbol is not one any venue lists. The
responses are constructed here rather than captured: a checked-in capture is a retrieval
nobody can date, and its values would look exactly like real quotations. What is under test is
the handling of *shape* -- a short window, a hole, a row for a day that has not closed -- and
shape needs no real prices. The owner's own holdings are not here, and a test may not pin them
(025, owner verification task 3).

**No socket is opened.** ``binance._get`` is the seam the whole fetch hangs from and every
test replaces it; the two tests that reach past it assert that what answers is
``tests/conftest.py``'s guard and that the request names nobody.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from terezy.data.providers import binance, interface
from tests.conftest import NetworkAccessAttemptedError

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "fetch_binance.py"
DATA_ROOT = REPO_ROOT / "data"


def _load(name: str, path: Path) -> Any:
    """A script as a module. It lives outside the package, so it is loaded by path.

    Registered in ``sys.modules`` before execution because ``dataclasses`` resolves a field's
    annotations through the module it is defined in, and a module absent from the table has
    none to resolve through.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fetch_binance = _load("fetch_binance", SCRIPT)

SYMBOL = "SYNTHUSDT"
"""SYNTHETIC, and deliberately not a pair anybody trades."""

FIRST = date(2020, 1, 1)
"""The first day the invented venue quotes this symbol. Nothing declares it: the fetch takes
the start of the series from the response, so this is the fixture's choice alone."""

AS_OF = date(2020, 1, 11)
"""The retrieval date every test below pretends to run on."""

LAST = AS_OF - timedelta(days=1)
"""The newest day that has closed on ``AS_OF``, and so the newest row a run may write."""

INVENTED_FIRST = 1111.11
"""SYNTHETIC. Every close below is this plus a whole number of days, so a price that escaped
into an output would be recognisable as arithmetic rather than as a quotation."""

PREVIOUS = b"# the declaration that was already there. A refused run must not touch it.\n"


def _close(day: date) -> float:
    return INVENTED_FIRST + (day - FIRST).days


def _row(day: date) -> list[Any]:
    """One row in the twelve-element shape the endpoint documents."""
    price = f"{_close(day):.2f}"
    opened = binance._midnight_ms(day)
    return [
        opened,
        price,
        price,
        price,
        price,
        "0.00100000",
        opened + binance.DAY_MS - 1,
        "1.11100000",
        7,
        "0.00050000",
        "0.55550000",
        "0",
    ]


def _days(*, first: date = FIRST, last: date = LAST) -> list[date]:
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _rows(days: list[date] | None = None) -> list[list[Any]]:
    return [_row(day) for day in (days if days is not None else _days())]


def _within(row: Any, start: int, end: int) -> bool:
    """Whether the invented venue would serve this row for this window.

    A row whose open time is not a number is served whatever the window, so that a malformed
    shape reaches the parser rather than being filtered out by the fixture.
    """
    if not isinstance(row, list) or not row or not isinstance(row[0], int):
        return True
    return start <= row[0] <= end


def _serving(
    rows: list[Any] | None = None,
    *,
    status: int = binance.OK,
    body: bytes | None = None,
    unreachable: bool = False,
) -> tuple[Any, list[str]]:
    """A replacement for the seam, and the log of what it was asked for.

    ``body`` serves fixed bytes whatever the query, which is how a venue that ignores its own
    ``startTime`` and ``endTime`` is modelled; otherwise the window is honoured, so the paging
    loop is exercised rather than assumed.
    """
    calls: list[str] = []

    def get(url: str) -> Any:
        calls.append(url)
        if unreachable:
            return interface.Unreachable(url=url, detail="the invented venue did not answer")
        if body is not None:
            return binance.Response(status=status, body=body)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        start, end = int(query["startTime"][0]), int(query["endTime"][0])
        page = [row for row in (rows or []) if _within(row, start, end)][: binance.PAGE_LIMIT]
        return binance.Response(status=status, body=json.dumps(page).encode())

    return get, calls


def _install(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> list[str]:
    if "rows" not in kwargs and "body" not in kwargs and not kwargs.get("unreachable"):
        kwargs["rows"] = _rows()
    get, calls = _serving(kwargs.pop("rows", None), **kwargs)
    monkeypatch.setattr(binance, "_get", get)
    return calls


def _run(out: Path, *, as_of: date = AS_OF, symbol: str = SYMBOL) -> int:
    code: int = fetch_binance.main(["--symbol", symbol, "--out", str(out)], today=as_of)
    return code


def _observations(out: Path) -> list[dict[str, Any]]:
    document = tomllib.loads(out.read_text(encoding="utf-8"))
    observations: list[dict[str, Any]] = document["observation"]
    return observations


@pytest.fixture
def out(tmp_path: Path) -> Path:
    """A target that already holds something, so "writes nothing" is checkable byte for byte."""
    destination = tmp_path / "binance_synthusdt.toml"
    destination.write_bytes(PREVIOUS)
    return destination


class TestWhatARunWrites:
    """SC-007's first half: the file the recorded response produces."""

    def test_one_dated_observation_per_closed_day(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        _install(monkeypatch)

        assert _run(out) == 0
        written = _observations(out)

        assert [entry["on_date"] for entry in written] == [d.isoformat() for d in _days()]
        assert [entry["close"] for entry in written] == [round(_close(day), 2) for day in _days()]

    def test_the_newest_row_is_the_day_before_the_retrieval_date(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        """FR-024. The candle for the retrieval date is still open, so the series stops short
        of it -- and the run does not refuse for stopping there, which is the whole point of
        asking for a window that ends the day before."""
        _install(monkeypatch)

        assert _run(out) == 0

        dated = [entry["on_date"] for entry in _observations(out)]

        assert dated[-1] == LAST.isoformat()
        assert AS_OF.isoformat() not in dated

    def test_it_carries_the_endpoint_the_symbol_the_interval_and_the_retrieval_date(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        _install(monkeypatch)

        assert _run(out) == 0
        document = tomllib.loads(out.read_text(encoding="utf-8"))

        assert document["endpoint"] == binance.ENDPOINT
        assert document["symbol"] == SYMBOL
        assert document["interval"] == binance.INTERVAL
        assert document["retrieved_on"] == AS_OF.isoformat()

    def test_every_observation_carries_the_endpoint_and_the_declared_kind(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        """A row quoted anywhere carries its own provenance, as every other series here does."""
        _install(monkeypatch)

        assert _run(out) == 0

        for entry in _observations(out):
            assert binance.ENDPOINT in entry["source"]
            assert SYMBOL in entry["source"]
            assert entry["kind"] == binance.OBSERVATION_KIND
            assert entry["retrieved_on"] == AS_OF.isoformat()

    def test_the_symbol_is_recorded_whole_and_never_split(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        """FR-023. A kline row publishes neither a base nor a quote asset, so a file naming
        one would be stating the fetcher's judgement as the venue's."""
        _install(monkeypatch)

        assert _run(out) == 0
        document = tomllib.loads(out.read_text(encoding="utf-8"))

        assert set(document) == {"retrieved_on", "endpoint", "symbol", "interval", "observation"}

    def test_the_default_path_is_the_symbol_lowercased(self) -> None:
        """FR-020's filename, so that a second symbol is a second file rather than a
        collision."""
        assert fetch_binance.out_path(SYMBOL) == (
            DATA_ROOT / "observations" / "binance_synthusdt.toml"
        )


class TestNoAutomationEverFillsAVerification:
    """FR-020. A downloaded number is not a checked number."""

    def test_every_verification_the_run_writes_is_empty(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        _install(monkeypatch)

        assert _run(out) == 0

        assert {entry["verified_on"] for entry in _observations(out)} == {""}

    def test_a_rerun_over_an_existing_file_writes_them_empty_again(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        """The rendering is a function of the response and the retrieval date alone: it reads
        nothing off the file it replaces, so nothing it reads could put a date in the field."""
        _install(monkeypatch)
        assert _run(out) == 0
        out.write_text(
            out.read_text(encoding="utf-8").replace(
                'verified_on  = ""', 'verified_on  = "2026-08-31"', 1
            ),
            encoding="utf-8",
        )

        assert _run(out) == 0

        assert {entry["verified_on"] for entry in _observations(out)} == {""}

    def test_two_runs_on_one_day_leave_byte_identical_files(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        _install(monkeypatch)
        assert _run(out) == 0
        first = out.read_bytes()

        assert _run(out) == 0

        assert out.read_bytes() == first


class TestTheHeaderSaysWhatTheFileIsAndWhatItDoesNotSay:
    """The header is taken as the text before the first observation, so a claim that had
    drifted into a row's citation would fail this."""

    @staticmethod
    def _header(monkeypatch: pytest.MonkeyPatch, out: Path) -> str:
        _install(monkeypatch)
        assert _run(out) == 0
        return out.read_text(encoding="utf-8").partition("[[observation]]")[0]

    def test_it_forbids_hand_editing_and_names_the_script(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        header = self._header(monkeypatch, out)

        assert "GENERATED" in header
        assert "fetch_binance.py" in header

    def test_it_says_every_verification_is_empty_and_stays_empty(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        header = self._header(monkeypatch, out)

        assert "RETRIEVED, NOT VERIFIED" in header
        assert "verified_on" in header

    def test_it_says_the_current_days_candle_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        header = self._header(monkeypatch, out)

        assert "CLOSED" in header
        assert "refused" in header

    def test_it_says_the_quote_asset_is_not_a_dollar(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        """Clarification 1. What one USDT is worth in dollars is a belief the owner declares,
        and a file that let it pass silently would put the exchange rate's worth of error
        under a straight face."""
        header = self._header(monkeypatch, out)

        assert "USDT" in header
        assert "NOT in USD" in header


class TestASurpriseInTheResponseWritesNothingAtAll:
    """SC-007's second half and FR-021. Each case names what surprised it and leaves the
    previous file byte-identical."""

    @staticmethod
    def _refused(
        monkeypatch: pytest.MonkeyPatch,
        out: Path,
        capsys: pytest.CaptureFixture[str],
        *,
        saying: tuple[str, ...],
        **served: Any,
    ) -> list[str]:
        before = out.read_bytes()
        calls = _install(monkeypatch, **served)

        assert _run(out) == 1

        assert out.read_bytes() == before
        reported = capsys.readouterr().err
        for fragment in saying:
            assert fragment in reported, (fragment, reported)
        assert "nothing was written." in reported
        return calls

    def test_a_row_that_is_not_twelve_elements_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = _rows()
        rows[3] = rows[3][:-1]
        self._refused(monkeypatch, out, capsys, rows=rows, saying=("row 3", "12-element"))

    def test_a_row_that_is_not_a_row_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows: list[Any] = list(_rows())
        rows[2] = {"openTime": 0, "close": "1.00"}
        self._refused(monkeypatch, out, capsys, rows=rows, saying=("row 2", "12-element"))

    def test_a_non_positive_close_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = _rows()
        rows[1][binance.CLOSE] = "0.00"
        self._refused(
            monkeypatch, out, capsys, rows=rows, saying=("2020-01-02", "strictly positive")
        )

    def test_a_close_that_is_not_a_number_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = _rows()
        rows[4][binance.CLOSE] = "unavailable"
        self._refused(monkeypatch, out, capsys, rows=rows, saying=("2020-01-05", "unavailable"))

    def test_a_hole_inside_the_window_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Not written with the hole in it: a daily candle exists for every calendar day, so
        a missing one is a broken retrieval and not a series with a gap."""
        rows = _rows([day for day in _days() if day != FIRST + timedelta(days=2)])
        self._refused(
            monkeypatch, out, capsys, rows=rows, saying=("one per calendar day", "2020-01-03")
        )

    def test_a_window_ending_short_of_what_was_asked_for_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = _rows(_days(last=LAST - timedelta(days=2)))
        self._refused(monkeypatch, out, capsys, rows=rows, saying=(LAST.isoformat(), "2020-01-09"))

    def test_a_day_served_twice_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rows = _rows()
        rows.insert(5, _row(FIRST + timedelta(days=4)))
        self._refused(monkeypatch, out, capsys, rows=rows, saying=("one per calendar day",))

    def test_a_body_that_is_not_a_list_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-021 forbids checking the symbol against the body, and this is the case that
        would have tempted one: the venue answers an unlisted symbol with an error object,
        which is refused for the shape it is rather than for a symbol no row carries."""
        self._refused(
            monkeypatch,
            out,
            capsys,
            body=b'{"code": -1121, "msg": "Invalid symbol."}',
            saying=("dict", "list of rows"),
        )

    def test_a_body_that_is_not_json_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._refused(monkeypatch, out, capsys, body=b"<html>maintenance</html>", saying=("JSON",))

    def test_a_candle_that_has_not_closed_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-024. The window asks for closed days only, so this is the venue overshooting its
        own ``endTime`` -- and the row is refused rather than dropped, because a close that is
        only the last trade so far would be a wrong number under a right name."""
        served = json.dumps(_rows(_days(last=AS_OF))).encode()
        self._refused(
            monkeypatch, out, capsys, body=served, saying=(AS_OF.isoformat(), "not closed")
        )

    def test_an_open_time_that_is_not_utc_midnight_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The one malformation every other check here would pass over: a candle offset by
        hours still yields consecutive distinct dates, each naming a day it does not cover."""
        rows = _rows()
        rows[6][binance.OPEN_TIME] += 3_600_000
        self._refused(monkeypatch, out, capsys, rows=rows, saying=("UTC midnight",))

    def test_an_unreachable_host_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._refused(monkeypatch, out, capsys, unreachable=True, saying=("nothing came back",))

    def test_a_status_the_endpoint_does_not_document_refuses(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._refused(monkeypatch, out, capsys, body=b"[]", status=503, saying=("503",))

    @pytest.mark.parametrize("status", sorted(binance.RATE_LIMIT_STATUSES))
    def test_a_rate_limit_refuses_once_and_is_never_retried(
        self,
        monkeypatch: pytest.MonkeyPatch,
        out: Path,
        capsys: pytest.CaptureFixture[str],
        status: int,
    ) -> None:
        """FR-018. Asking again after being told to stop is how a rate limit becomes a ban,
        so the count of requests is the assertion and not only the exit code."""
        calls = self._refused(
            monkeypatch, out, capsys, body=b"[]", status=status, saying=(str(status), "stop")
        )

        assert len(calls) == 1


class TestADryRunReportsAndWritesNothing:
    def test_the_file_is_byte_identical_after_a_dry_run(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        before = out.read_bytes()
        _install(monkeypatch)

        assert (
            fetch_binance.main(["--symbol", SYMBOL, "--out", str(out), "--dry-run"], today=AS_OF)
            == 0
        )

        assert out.read_bytes() == before


class TestPagingCoversTheWindowAndTerminates:
    def test_a_window_longer_than_the_documented_cap_is_paged(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        as_of = FIRST + timedelta(days=binance.PAGE_LIMIT + 500)
        last = as_of - timedelta(days=1)
        calls = _install(monkeypatch, rows=_rows(_days(last=last)))

        assert _run(out, as_of=as_of) == 0

        assert len(calls) > 1
        written = _observations(out)
        assert len(written) == binance.PAGE_LIMIT + 500
        assert written[0]["on_date"] == FIRST.isoformat()
        assert written[-1]["on_date"] == last.isoformat()

    def test_a_venue_that_ignores_the_cursor_refuses_instead_of_paging_for_ever(
        self, monkeypatch: pytest.MonkeyPatch, out: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A hung fetch is the one failure that never reports, so the loop refuses rather than
        trusting the venue to advance."""
        stuck = json.dumps(_rows(_days(last=FIRST + timedelta(days=2)))).encode()
        calls = _install(monkeypatch, body=stuck)

        assert _run(out) == 1

        assert len(calls) == 2
        assert "where the last began" in capsys.readouterr().err


class TestTheSeamIsTheOnlyThingThatTouchesTheNetwork:
    """SC-009."""

    def test_the_fetch_asks_the_replacement_and_asks_it_for_the_documented_endpoint(
        self, monkeypatch: pytest.MonkeyPatch, out: Path
    ) -> None:
        calls = _install(monkeypatch)

        assert _run(out) == 0

        assert calls
        assert all(url.startswith(f"{binance.ENDPOINT}?") for url in calls)

    def test_the_real_seam_is_stopped_by_the_suites_own_guard(self) -> None:
        """The backstop: if a fetch ever reached past the seam, this is what would answer."""
        with pytest.raises(NetworkAccessAttemptedError):
            binance._get(f"{binance.ENDPOINT}?symbol={SYMBOL}")

    def test_the_request_names_nobody_and_carries_no_credential(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-018 and Principle VII: no key, no signature, and no header identifying the owner
        to the venue. Asserted over what is handed to ``urlopen`` -- a bare URL string carries
        no headers at all, and the query is exactly the five documented parameters."""
        asked: list[Any] = []

        def spy(url: Any, **kwargs: Any) -> Any:
            asked.append(url)
            raise urllib.error.URLError("stopped before any socket")

        monkeypatch.setattr(urllib.request, "urlopen", spy)

        assert isinstance(
            binance._get(binance._page_url(symbol=SYMBOL, start_ms=0, end_ms=1)),
            interface.Unreachable,
        )

        (requested,) = asked
        assert isinstance(requested, str)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(requested).query)
        assert set(query) == {"symbol", "interval", "startTime", "endTime", "limit"}


class TestTheProvenanceGateAcceptsWhatItWrites:
    """T020a's guarantee, without a real observation file: the shipped tree gets none, because
    the owner runs the fetcher himself and his run is the only one whose figures are real."""

    def test_the_written_file_passes_the_gate_the_repository_runs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        root = tmp_path / "data"
        (root / "observations").mkdir(parents=True)
        (root / "observation_kinds.toml").write_text(
            (DATA_ROOT / "observation_kinds.toml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        written = root / "observations" / "binance_synthusdt.toml"
        _install(monkeypatch)
        assert _run(written) == 0

        gate = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_provenance.py"), str(root)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        assert gate.returncode == 0, gate.stdout
        assert "error:" not in gate.stdout
