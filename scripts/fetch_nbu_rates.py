#!/usr/bin/env python3
"""Fetch the National Bank of Ukraine's official hryvnia/dollar rate and declare it.

**This script retrieves. It does not verify.** Every observation it writes carries its
``source``, its ``retrieved_on`` and an **empty** ``verified_on`` -- because a number that was
downloaded is not a number anyone has checked. Filling that field is an act the owner performs
against the publisher's own presentation of one date, and no automation may perform it
(``scripts/fetch_cpi.py`` says the same for the price index).

**It does declare**, where ``scripts/fetch_inzhur.py`` writes an observation for a human to
promote. Promoting one of Inzhur's is an act of judgement between two readings of one figure;
between the National Bank's register and this declaration there is no such judgement, because
the authority publishes exactly one value per date. The judgement that does exist here is the
quotation unit, and it is kept out of this script's hands by being a **refusal** rather than a
choice -- see :func:`_row`.

Why the range endpoint and not ``NBUStatService/v1/statdirectory/exchange``
--------------------------------------------------------------------------
The per-date endpoint does not state the quotation unit, so a script built on it could not
perform the refusal above at all -- it would have to assume the unit. This one gives ``units``
and ``rate_per_unit`` per row.

Why the requested window is one day wider than the required one
---------------------------------------------------------------
The publisher runs a day ahead: asked on a Sunday it returns Monday's rate. An observation dated
after its own ``retrieved_on`` is refused at load, so writing everything on offer produces a file
that does not load at all. This script therefore **asks** for the day ahead and **declines** it,
naming what it dropped -- rather than never asking, which would leave the drop a branch nothing
takes. The next run picks the day up as an ordinary observation.

The licence
-----------
Reuse is conditional on a reference to the source, and the reference is carried on **every row**
rather than once at the top: a row quoted anywhere then carries its own attribution. Which text
binds a reuser is a question of legal effect this script does not settle; the header names both
and says what each one does.

Usage
-----
    uv run python scripts/fetch_nbu_rates.py --dry-run   # report, write nothing
    uv run python scripts/fetch_nbu_rates.py             # write data/official_rates/ua_nbu_usd.toml

Nothing is written unless every step succeeded: the file is built in memory, written to a
temporary path and renamed, so an interrupted or failed run leaves the previous declaration
exactly as it was. A partially written legal series would be worse than none -- every date inside
the hole would refuse for a reason naming the series rather than the fetch.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
OUT_PATH: Final = REPO_ROOT / "data" / "official_rates" / "ua_nbu_usd.toml"

ENDPOINT: Final = "https://bank.gov.ua/NBU_Exchange/exchange_site"
VALCODE: Final = "usd"

SERIES_ID: Final = "ua_nbu_usd"
AUTHORITY: Final = "Національний банк України"
PRICE_CURRENCY: Final = "UAH"
UNIT_CURRENCY: Final = "USD"
QUOTATION_UNIT: Final = 1.0
OBSERVATION_KIND: Final = "official_rate"
"""Every constant above is what ``data/official_rates/ua_nbu_usd.toml`` declares. This script
writes that file, so it states them; it does not read them back from the file it replaces."""

FIRST_DATE: Final = date(2019, 12, 28)
"""The first date the publisher quotes USD per one unit.

Not a preference. A series carries one ``quotation_unit`` for the whole of itself, this one
declares 1.0, and an earlier date is a **second series** with its own id -- a data-only
addition -- rather than a longer one.
"""

ROW_FIELDS: Final = frozenset(
    {
        "exchangedate",
        "r030",
        "cc",
        "txt",
        "enname",
        "rate",
        "units",
        "rate_per_unit",
        "group",
        "calcdate",
        "special",
    }
)
"""Exactly the keys the publisher's rows carry. A key that appears or disappears is a change in
the publisher's shape, which is a thing to read about before trusting anything written here."""

TIMEOUT_SECONDS: Final = 180
USER_AGENT: Final = (
    "terezy/fetch_nbu_rates (single-user personal finance tool; contact via repository)"
)

PUBLISHED_FORMAT: Final = "%d.%m.%Y"
"""How the publisher spells a date. The declaration spells it ISO; nothing else is reformatted."""


class FetchError(RuntimeError):
    """Anything that stopped this run from producing a complete, trustworthy series."""


@dataclass(frozen=True, slots=True)
class Row:
    """One published row, after its shape has been checked and before it is a declaration."""

    on_date: date
    value: float
    units: int
    calcdate: str
    """The working day the publisher says the rate was established on. Carried into the
    citation, where it makes a weekend observation visibly the publisher's carry rather than
    this repository's."""


@dataclass(frozen=True, slots=True)
class Fetched:
    """A complete window and the provenance of the act that retrieved it."""

    rows: tuple[Row, ...]
    retrieved_on: date
    url: str
    declined: tuple[date, ...]
    """Dates the publisher offered that had not arrived yet. Named rather than absent, so a
    reader can see the day-ahead rate was refused rather than missed."""


def _url(*, start: date, end: date) -> str:
    return (
        f"{ENDPOINT}?start={start:%Y%m%d}&end={end:%Y%m%d}&valcode={VALCODE}"
        "&sort=exchangedate&order=asc&json"
    )


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc


def _published_date(raw: object, *, field: str) -> date:
    try:
        return datetime.strptime(str(raw), PUBLISHED_FORMAT).date()  # noqa: DTZ007
    except ValueError as exc:
        raise FetchError(
            f"{field} holds {raw!r}, which is not the DD.MM.YYYY the publisher writes. A date "
            "this script cannot read is a change in the response's shape, not a row to skip."
        ) from exc


def _row(entry: object, position: int) -> Row:
    """One response row, checked field by field. Every failure names what surprised it."""
    if not isinstance(entry, dict):
        raise FetchError(f"row {position} is {type(entry).__name__}, not an object")
    present = set(entry)
    if present != ROW_FIELDS:
        missing = sorted(ROW_FIELDS - present)
        extra = sorted(present - ROW_FIELDS)
        raise FetchError(
            f"row {position} does not carry the fields this script reads: missing {missing}, "
            f"unrecognised {extra}. The publisher changed the response's shape -- read it "
            "before changing this script, and do not route around a field nobody looked at."
        )
    if entry["cc"] != UNIT_CURRENCY:
        raise FetchError(
            f"row {position} is quoted for {entry['cc']!r} and this series declares "
            f"{UNIT_CURRENCY!r}. A second currency is a second series with its own id, never "
            "another row on this one."
        )
    on_date = _published_date(entry["exchangedate"], field=f"row {position} exchangedate")
    value = entry["rate"]
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise FetchError(
            f"row {position} ({on_date.isoformat()}) holds the rate {value!r}. An official rate "
            "is a strictly positive number, and anything else would produce a base that merely "
            "looks like money."
        )
    units = entry["units"]
    if units != QUOTATION_UNIT:
        raise FetchError(
            f"row {position} ({on_date.isoformat()}, published as {entry['exchangedate']}) is "
            f"quoted per {units} units and {SERIES_ID} declares quotation_unit = "
            f"{QUOTATION_UNIT}. The whole run is refused rather than the value normalised: a "
            "value divided to fit a declared unit is no longer what the published table says, "
            "and re-deriving a base by eye against the publisher's page -- the only check "
            "anyone will ever actually perform -- would stop working. An era quoted per "
            "another unit is a second series."
        )
    _published_date(entry["calcdate"], field=f"row {position} calcdate")
    return Row(
        on_date=on_date,
        value=float(value),
        units=int(units),
        calcdate=str(entry["calcdate"]),
    )


def _rows(payload: object, *, first: date, last: date) -> tuple[tuple[Row, ...], tuple[date, ...]]:
    """Every row of the window, and the dates declined for not having arrived.

    The completeness check is against ``first .. last`` and **not** against what came back, so
    a short retrieval fails instead of silently narrowing the window it was asked for.

    Rows are sorted rather than required to arrive in order: every row is self-dated, so the
    order carries no information, and the check above is over the *set* -- which a reordering
    cannot satisfy wrongly.
    """
    if not isinstance(payload, list):
        raise FetchError(
            f"the response is a {type(payload).__name__}, not a list of rows. The publisher "
            "returns a JSON array; anything else is an error page or a changed contract."
        )
    if not payload:
        raise FetchError(
            f"the response carries no rows at all for {first.isoformat()} .. {last.isoformat()}"
        )
    kept: list[Row] = []
    declined: list[date] = []
    seen: set[date] = set()
    for position, entry in enumerate(payload):
        row = _row(entry, position)
        if row.on_date in seen:
            raise FetchError(f"the response declares {row.on_date.isoformat()} twice")
        seen.add(row.on_date)
        if row.on_date > last:
            declined.append(row.on_date)
            continue
        kept.append(row)
    kept.sort(key=lambda item: item.on_date)
    wanted = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
    if [row.on_date for row in kept] != wanted:
        got = {row.on_date for row in kept}
        absent = sorted(day for day in wanted if day not in got)
        beyond = sorted(day for day in got if day not in set(wanted))
        raise FetchError(
            f"the response does not cover {first.isoformat()} .. {last.isoformat()} one row per "
            f"calendar day: {len(absent)} missing (first {absent[0].isoformat() if absent else '-'}"
            f"), {len(beyond)} outside the window. The publisher returns a row for every "
            "calendar day, so this is a short or broken retrieval and not a set of gaps -- "
            "nothing is written."
        )
    return tuple(kept), tuple(declined)


def fetch(*, today: date) -> Fetched:
    """Retrieve the window. Raises :class:`FetchError` rather than returning a partial one."""
    url = _url(start=FIRST_DATE, end=today + timedelta(days=1))
    raw = _get(url)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(f"the response from {url} is not JSON: {exc}") from exc
    rows, declined = _rows(payload, first=FIRST_DATE, last=today)
    return Fetched(rows=rows, retrieved_on=today, url=url, declined=declined)


def observations_in(text: str) -> Iterator[tuple[date, float, str]]:
    """Every observation a rendered declaration carries: its date, value and verification."""
    document = tomllib.loads(text)
    for entry in document.get("observation", []):
        yield (
            date.fromisoformat(str(entry["on_date"])),
            float(entry["value"]),
            str(entry["verified_on"]),
        )


def verifications(path: Path) -> dict[date, tuple[float, str]]:
    """What the file about to be replaced already attests to, by date.

    ``verified_on`` on an official-rate observation means: the owner compared **this
    observation's** value to the National Bank's own published presentation of that date, on
    that day. It is per observation and says nothing about any other -- at one row per calendar
    day, "the series is verified" is a claim nobody could ever have made, and per-row is the only
    reading under which the field can be honestly filled at all.
    """
    if not path.is_file():
        return {}
    return {
        on_date: (value, verified)
        for on_date, value, verified in observations_in(path.read_text(encoding="utf-8"))
        if verified
    }


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _header(fetched: Fetched) -> list[str]:
    first = fetched.rows[0].on_date.isoformat()
    last = fetched.rows[-1].on_date.isoformat()
    return [
        "# The National Bank of Ukraine's official hryvnia/dollar rate: the tax-currency series.",
        "#",
        "# RETRIEVED, NOT VERIFIED. Every observation below carries its source and the date it",
        "# was retrieved, and an EMPTY `verified_on` -- because a number that was downloaded is",
        "# not a number anyone has checked. Filling that field is an act the owner performs",
        "# against the publisher, one observation at a time, and `scripts/fetch_nbu_rates.py`",
        "# must never perform it. Every tax figure struck from these values renders marked",
        "# until he does.",
        "#",
        f"# Generated by scripts/fetch_nbu_rates.py on {fetched.retrieved_on.isoformat()}."
        " Do not hand-edit,",
        "# except to fill a `verified_on` you have actually checked: re-run the script and read",
        "# the diff. A value corrected by hand loses the one thing that makes it checkable --",
        "# the ability to reproduce it from the cited source. A re-run keeps a `verified_on`",
        "# whose value is unchanged and CLEARS one whose value the publisher has restated,",
        "# because the attestation was about a different number.",
        "#",
        f"# COVERAGE: {first} .. {last}, one observation per calendar day, no gaps.",
        "#",
        "# ---------------------------------------------------------------------------",
        "# WHY THE SERIES STARTS ON 2019-12-28 AND NOT EARLIER",
        "# ---------------------------------------------------------------------------",
        "#",
        "# The publisher's own `units` field. USD is published per 100 units through",
        "# 2019-12-27 and per 1 from 2019-12-28, and `quotation_unit` is one value for the",
        "# whole series. An earlier date cannot be carried here without either a lie about the",
        "# unit or a value that is not the published one, so it is a SECOND SERIES with its own",
        "# id and `quotation_unit = 100.0` -- a data-only addition -- and none is declared.",
        "#",
        "# The fetch script reads `units` on every row and REFUSES THE WHOLE RUN on a mismatch",
        "# rather than normalising. That closes the gap `scripts/check_provenance.py` records at",
        "# its `quotation_unit` exemption: nothing else verifies this unit, and a value read as",
        "# 1 where the publisher quotes per 100 is wrong by two orders of magnitude while every",
        "# figure stays plausible.",
        "#",
        "# ---------------------------------------------------------------------------",
        "# A DATE OUTSIDE THE WINDOW REFUSES. IT IS NOT INTERPOLATED",
        "# ---------------------------------------------------------------------------",
        "#",
        "# Before the first observation, after the last, or on a date that has not arrived: the",
        "# request refuses, naming the series, the pair, the date and the window above. Nothing",
        "# interpolates, extrapolates, carries a previous date's value forward, or snaps to the",
        "# nearest -- each of those produces a number that looks exactly like a correct number,",
        "# and every tax figure downstream would inherit the invention with no mark on it.",
        "#",
        '# In particular the encoding "the latest observation on or before the event date"',
        "# MUST NOT be adopted. It cannot tell a weekend from a gap in the series, so it would",
        "# make the refusal unreachable for exactly the dates the refusal exists for.",
        "#",
        "# ---------------------------------------------------------------------------",
        "# NO NON-PUBLICATION-DAY RULE IS DECLARED, AND THERE IS NOTHING FOR ONE TO SAY",
        "# ---------------------------------------------------------------------------",
        "#",
        "# The National Bank returns an official rate for EVERY calendar day, dated that day.",
        "# A rule is a statement of which declared observation governs a date the publisher does",
        "# not publish for; where the publisher publishes for every date, there is no such date.",
        "# The value against a Sunday is RETRIEVED FROM THE AUTHORITY against that Sunday --",
        "# declaring it is entering a published fact, where deriving it would be inventing one --",
        "# and each row's citation carries the `calcdate` the publisher gives it, which is the",
        "# working day whose establishment produced it.",
        "#",
        "# Whether the value dated a non-working day is the rate IN FORCE on that day in the",
        "# sense the Tax Code means is a question about legal effect, not about publication, and",
        "# it is recorded UNREAD as an owner verification task in `specs/018-nbu-rate-series`,",
        "# with the two provisions that close it named there.",
        "#",
        "# ---------------------------------------------------------------------------",
        "# THE TERMS THIS DATA COMES UNDER",
        "# ---------------------------------------------------------------------------",
        "#",
        "# Attribution is a TERM OF REUSE, not a courtesy, and every observation below carries",
        "# the URL it was retrieved from for that reason. Two texts bear on it and they do not",
        "# say the same thing:",
        "#",
        "#   ст. 10-1 ч. 2 абз. 2 ЗУ № 2939-VI «Про доступ до публічної інформації» -- the",
        "#   operative term, addressed to «будь-яка особа»: free copying, publication,",
        "#   distribution and use «у тому числі в комерційних цілях», conditional on",
        "#   «обов'язкове посилання на джерело отримання такої інформації». The word",
        "#   «гіперпосилання» does not appear anywhere in that act.",
        "#",
        "#   п. 17 Положення, затвердженого постановою КМУ від 21.10.2015 № 835 -- where the",
        "#   hyperlink wording lives, and it is the text of a NOTICE the розпорядник displays on",
        "#   each dataset page rather than a term addressed to a reuser: «... обов'язкове",
        "#   посилання на джерело їх отримання (у тому числі гіперпосилання ...)». Note the",
        "#   form: «у тому числі» names a hyperlink as one way of referring to the source, not",
        "#   as a second requirement.",
        "#",
        "# A citation carrying the retrieval URL satisfies both readings, so this file does not",
        "# have to decide which text binds a reuser -- a question of legal effect it has no",
        "# standing to settle.",
        "#",
    ]


def _carried(row: Row, verified: Mapping[date, tuple[float, str]]) -> str:
    """The verification this row keeps: the stored one where the value is unchanged, else none.

    An attestation was about a number, so a restated number clears it -- see
    :func:`verifications` for what the field means.
    """
    attested = verified.get(row.on_date)
    return attested[1] if attested is not None and attested[0] == row.value else ""


def render(fetched: Fetched, *, verified: Mapping[date, tuple[float, str]]) -> str:
    """The declaration file, in full. Pure -- takes no clock and touches no disk."""
    lines = _header(fetched)
    lines.extend(
        [
            "[series]",
            f'id             = "{SERIES_ID}"',
            f'authority      = "{AUTHORITY}"',
            f'pair           = ["{PRICE_CURRENCY}", "{UNIT_CURRENCY}"]',
            f"quotation_unit = {QUOTATION_UNIT}",
            "",
        ]
    )
    for row in fetched.rows:
        citation = (
            f"{AUTHORITY} — офіційний курс {PRICE_CURRENCY} за {UNIT_CURRENCY}; retrieved from "
            f"{fetched.url}; units = {row.units}; calcdate = {row.calcdate}"
        )
        lines.append(
            "[[observation]]\n"
            f'on_date      = "{row.on_date.isoformat()}"\n'
            f"value        = {row.value}\n"
            f'kind         = "{OBSERVATION_KIND}"\n'
            f'source       = "{_escape(citation)}"\n'
            f'retrieved_on = "{fetched.retrieved_on.isoformat()}"\n'
            f'verified_on  = "{_carried(row, verified)}"\n'
        )
    return "\n".join(lines)


def _write(text: str, path: Path) -> None:
    """Atomically, so a failed run never leaves half a legal series behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(handle, "w", encoding="utf-8") as file:  # noqa: PTH123 -- an fd, not a path
            file.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None, *, today: date | None = None) -> int:
    """Retrieve and declare. The clock is read here and nowhere else.

    ``today`` is the retrieval date. It is a parameter so the whole program is exercisable
    without a clock and without a socket; nothing on the command line sets it, because an
    operator choosing a retrieval date would be writing a provenance nobody performed.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    parser.add_argument(
        "--out", type=Path, default=OUT_PATH, help=f"output path (default: {OUT_PATH})"
    )
    arguments = parser.parse_args(argv)

    retrieved_on = today if today is not None else date.today()  # noqa: DTZ011 -- a script reads the clock; the pure core never does
    try:
        fetched = fetch(today=retrieved_on)
        kept = verifications(arguments.out)
        text = render(fetched, verified=kept)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        print("nothing was written.", file=sys.stderr)  # noqa: T201
        return 1

    print(f"publisher      {AUTHORITY}")  # noqa: T201
    print(f"series         {SERIES_ID}  {PRICE_CURRENCY} per {QUOTATION_UNIT} {UNIT_CURRENCY}")  # noqa: T201
    print(f"observations   {len(fetched.rows)}")  # noqa: T201
    print(  # noqa: T201
        f"coverage       {fetched.rows[0].on_date.isoformat()} .. "
        f"{fetched.rows[-1].on_date.isoformat()}"
    )
    print(f"retrieved_on   {fetched.retrieved_on.isoformat()}")  # noqa: T201
    carried = sum(1 for row in fetched.rows if _carried(row, kept))
    print(  # noqa: T201
        f"verified_on    {carried} carried forward, "
        f"{len(fetched.rows) - carried} empty (deliberately)"
    )
    if fetched.declined:
        print(  # noqa: T201
            "declined       "
            + ", ".join(day.isoformat() for day in fetched.declined)
            + " -- published ahead of the retrieval date, so not yet an observation"
        )

    if arguments.dry_run:
        print("\n--dry-run: nothing written.")  # noqa: T201
        return 0

    _write(text, arguments.out)
    print(f"\nwrote {arguments.out} -- read the diff before committing it.")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
