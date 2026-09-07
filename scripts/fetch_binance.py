#!/usr/bin/env python3
"""Fetch a Binance daily-close series and write it as a declared observation file.

**This script retrieves. It does not verify.** Every observation it writes carries its
``source``, its ``retrieved_on`` and an **empty** ``verified_on``, because a number that was
downloaded is not a number anyone has checked. Filling that field is an act the owner performs
against the venue's own presentation of one day, and no automation may perform it.

The refusals, the window and the row shape are
``src/terezy/data/providers/binance.py``'s; this is the wrapper that reads a clock, names a
file and writes it.

OPEN QUESTION, and not one to answer from memory: whether Binance's terms of use permit this
use of the public market-data endpoint, and under what attribution. ``fetch_nbu_rates.py``
settles the equivalent question for the National Bank's licence in its own header and carries
the reference on every row; nobody has read Binance's terms, so nothing here states what they
require. It is recorded as an owner verification task in ``specs/025-btc-holdings/spec.md``.

Usage
-----
    uv run python scripts/fetch_binance.py --symbol BTCUSDT --dry-run   # report, write nothing
    uv run python scripts/fetch_binance.py --symbol BTCUSDT

Nothing is written unless every step succeeded: the file is built in memory, written to a
temporary path and renamed, so a failed run leaves the previous file byte-identical. A
partially written price series would be worse than none -- every date inside the hole would
refuse for a reason naming the series rather than the fetch.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Final

from terezy.data.providers import binance, interface

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
OUT_TEMPLATE: Final = REPO_ROOT / "data" / "observations" / "binance_{symbol}.toml"
"""FR-020's filename. One file per symbol, so a second symbol is a second file rather than
a collision, and the symbol is lowercased there and nowhere else -- what the file RECORDS is
the symbol as requested."""


def out_path(symbol: str) -> Path:
    return OUT_TEMPLATE.with_name(OUT_TEMPLATE.name.format(symbol=symbol.lower()))


def _refusal(refused: interface.Refused) -> str:
    """What went wrong, in the terms of the record that says so."""
    match refused:
        case interface.Unreachable(url=url, detail=detail):
            return f"nothing came back from {url}: {detail}"
        case interface.RateLimited(url=url, status=status):
            return (
                f"{url} answered {status}, which is the venue telling this client to stop. "
                "It is not retried: retrying into a rate limit is how it becomes a ban."
            )
        case interface.Unrecognised(url=url, detail=detail):
            return (
                f"{url} returned something this script does not recognise: {detail}. Read "
                "what the venue now publishes before changing the parser."
            )
        case interface.Incomplete(url=url, detail=detail, missing=missing):
            absent = ", ".join(day.isoformat() for day in missing[:3])
            return f"{url}: {detail}" + (f" First absent: {absent}." if absent else "")
        case interface.OpenCandle(on_date=on_date, as_of=as_of):
            return (
                f"the venue returned a row for {on_date.isoformat()}, which has not closed on "
                f"{as_of.isoformat()}: its close is the last trade so far, not the day's."
            )


def _write(text: str, path: Path) -> None:
    """Atomically, so a failed run never leaves half a price series behind."""
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
    """Retrieve and write. The clock is read here and nowhere else.

    ``today`` is the retrieval date. It is a parameter so the whole program is exercisable
    without a clock and without a socket; nothing on the command line sets it, because an
    operator choosing a retrieval date would be writing a provenance nobody performed.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="the venue's own symbol, e.g. BTCUSDT. Recorded as requested and never split",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help=f"output path (default: {OUT_TEMPLATE})"
    )
    arguments = parser.parse_args(argv)

    retrieved_on = today if today is not None else date.today()  # noqa: DTZ011 -- a script reads the clock; the pure core never does
    out = arguments.out if arguments.out is not None else out_path(arguments.symbol)

    fetched = binance.fetch(binance.KIND, arguments.symbol, retrieved_on)
    if not isinstance(fetched, interface.Fetched):
        print(f"error: {_refusal(fetched)}", file=sys.stderr)  # noqa: T201
        print("nothing was written.", file=sys.stderr)  # noqa: T201
        return 1
    text = binance.render(fetched)

    print(f"venue          {binance.HOST}")  # noqa: T201
    print(f"symbol         {fetched.symbol}  ({binance.INTERVAL} closes)")  # noqa: T201
    print(f"observations   {len(fetched.quotations)}")  # noqa: T201
    print(  # noqa: T201
        f"coverage       {fetched.quotations[0].on_date.isoformat()} .. "
        f"{fetched.quotations[-1].on_date.isoformat()}"
    )
    print(f"retrieved_on   {retrieved_on.isoformat()}")  # noqa: T201
    print(f"verified_on    {len(fetched.quotations)} empty (deliberately)")  # noqa: T201

    if arguments.dry_run:
        print("\n--dry-run: nothing written.")  # noqa: T201
        return 0

    _write(text, out)
    print(f"\nwrote {out} -- read the diff before committing it.")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
