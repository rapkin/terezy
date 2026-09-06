"""Binance's public daily klines, as an observation file.

The host is the venue's documented market-data-only base endpoint. The request carries no
API key, no signature, no account and no header naming anybody: nothing here tells the venue
whose position it is pricing (Principle VII).

**The window ends the day before the retrieval date.** ``scripts/fetch_nbu_rates.py`` asks
its publisher for the day ahead and declines what arrives, so that the drop is a branch
something takes; the opposite is right here, because FR-024 makes an unclosed day a refusal
rather than a drop and a window that asked for today would refuse on every run. :func:`_row`
still refuses a row dated at or past the retrieval date, which is what a venue overshooting
its own ``endTime`` would look like.

**The series starts where the response starts.** The date a symbol was first quoted is a fact
about the venue that this repository does not hold, so the completeness check is anchored to
the first row that came back rather than to a date written here -- which would be a market
value from memory. What the check does catch is the shape of a broken retrieval: a hole, a
short end, or a day served twice.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from terezy.data.providers import interface

HOST: Final = "https://data-api.binance.vision"
"""The base endpoint the venue documents for clients that send only public market data."""

ENDPOINT: Final = f"{HOST}/api/v3/klines"
INTERVAL: Final = "1d"
KIND: Final[interface.SeriesKind] = "daily_close"

PAGE_LIMIT: Final = 1000
"""The endpoint's documented maximum number of rows in one response."""

TIMEOUT_SECONDS: Final = 180

OK: Final = 200
RATE_LIMIT_STATUSES: Final = frozenset({429, 418})
"""429 is the venue saying stop, 418 the ban that follows a client that did not."""

ROW_LENGTH: Final = 12
OPEN_TIME: Final = 0
CLOSE: Final = 4
"""Where the two values this reads sit in the documented row: the close is element 4, and its
date element 0 -- the open time, in milliseconds since the epoch, UTC."""

EPOCH: Final = date.fromisoformat("1970-01-01")
DAY_MS: Final = 86_400_000

OBSERVATION_KIND: Final = "market_quotation"
"""The staleness kind every row declares. ``data/observation_kinds.toml`` records its
threshold as inert and says why."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Response:
    """What the venue answered."""

    status: int
    body: bytes


def _midnight_ms(day: date) -> int:
    return (day - EPOCH).days * DAY_MS


def _page_url(*, symbol: str, start_ms: int, end_ms: int) -> str:
    query = urllib.parse.urlencode(
        {
            "symbol": symbol,
            "interval": INTERVAL,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": PAGE_LIMIT,
        }
    )
    return f"{ENDPOINT}?{query}"


def _get(url: str) -> Response | interface.Unreachable:
    """The only function in this package that opens a socket. Tests replace it."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return Response(status=int(response.status), body=bytes(response.read()))
    except urllib.error.HTTPError as error:
        return Response(status=int(error.code), body=bytes(error.read()))
    except (urllib.error.URLError, TimeoutError) as exc:
        return interface.Unreachable(url=url, detail=str(exc))


def _dated(opened: object, *, position: int, url: str) -> date | interface.Unrecognised:
    """The day element 0 names, or why it names none."""
    if not isinstance(opened, int) or isinstance(opened, bool) or opened < 0:
        return interface.Unrecognised(
            url=url,
            detail=f"row {position} opens at {opened!r}, not a millisecond count",
        )
    if opened % DAY_MS:
        return interface.Unrecognised(
            url=url,
            detail=(
                f"row {position} opens at {opened!r}, which is not UTC midnight. A daily "
                "candle that begins mid-day covers a day this file would date wrongly, and "
                "every other check here would pass over it."
            ),
        )
    return EPOCH + timedelta(days=opened // DAY_MS)


def _priced(
    close: object, *, position: int, url: str, on_date: date
) -> float | interface.Unrecognised:
    """The price element 4 states, or why it states none."""
    if isinstance(close, bool) or not isinstance(close, str | int | float):
        return interface.Unrecognised(
            url=url,
            detail=f"row {position} ({on_date.isoformat()}) closes at {close!r}, not a price",
        )
    try:
        price = float(close)
    except ValueError:
        price = math.nan
    if not math.isfinite(price) or price <= 0:
        return interface.Unrecognised(
            url=url,
            detail=(
                f"row {position} ({on_date.isoformat()}) closes at {close!r}. A price is a "
                "strictly positive finite number, and anything else would produce a value "
                "that merely looks like money."
            ),
        )
    return price


def _row(
    entry: object, *, position: int, url: str, as_of: date
) -> interface.Quotation | interface.Refused:
    """One response row, checked element by element. Every refusal names what surprised it."""
    if not isinstance(entry, list) or len(entry) != ROW_LENGTH:
        return interface.Unrecognised(
            url=url,
            detail=(
                f"row {position} is not the {ROW_LENGTH}-element kline the endpoint "
                f"documents: {entry!r}"
            ),
        )
    on_date = _dated(entry[OPEN_TIME], position=position, url=url)
    if not isinstance(on_date, date):
        return on_date
    if on_date >= as_of:
        return interface.OpenCandle(url=url, on_date=on_date, as_of=as_of)
    close = _priced(entry[CLOSE], position=position, url=url, on_date=on_date)
    if not isinstance(close, float):
        return close
    return interface.Quotation(on_date=on_date, close=close)


def _body(url: str) -> bytes | interface.Refused:
    """What the venue answered with, once the status says the body is a series at all."""
    response = _get(url)
    if isinstance(response, interface.Unreachable):
        return response
    if response.status in RATE_LIMIT_STATUSES:
        return interface.RateLimited(url=url, status=response.status)
    if response.status != OK:
        return interface.Unrecognised(url=url, detail=f"the venue answered {response.status}")
    return response.body


def _page(url: str, *, as_of: date) -> tuple[interface.Quotation, ...] | interface.Refused:
    body = _body(url)
    if not isinstance(body, bytes):
        return body
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return interface.Unrecognised(url=url, detail=f"the response is not JSON: {exc}")
    if not isinstance(payload, list):
        return interface.Unrecognised(
            url=url,
            detail=(
                f"the response is a {type(payload).__name__}, not the list of rows the "
                "endpoint documents"
            ),
        )
    rows: list[interface.Quotation] = []
    for position, entry in enumerate(payload):
        row = _row(entry, position=position, url=url, as_of=as_of)
        if not isinstance(row, interface.Quotation):
            return row
        rows.append(row)
    return tuple(rows)


def _complete(
    quotations: tuple[interface.Quotation, ...], *, url: str, symbol: str, last: date
) -> interface.Incomplete | None:
    """Whether the days that came back are one per calendar day, ending where asked."""
    if not quotations:
        return interface.Incomplete(
            url=url,
            detail=f"the venue published no closed day for {symbol} up to {last.isoformat()}",
            missing=(),
        )
    first = quotations[0].on_date
    wanted = tuple(first + timedelta(days=offset) for offset in range((last - first).days + 1))
    got = tuple(quotation.on_date for quotation in quotations)
    if got == wanted:
        return None
    missing = tuple(day for day in wanted if day not in set(got))
    return interface.Incomplete(
        url=url,
        detail=(
            f"the venue's rows for {symbol} are not one per calendar day from "
            f"{first.isoformat()} to {last.isoformat()}: {len(got)} rows back, "
            f"{len(missing)} of those days absent. A daily candle exists for every calendar "
            "day, so this is a short or broken retrieval rather than a series with holes -- "
            "and nothing is written."
        ),
        missing=missing,
    )


def fetch(
    kind: interface.SeriesKind, symbol: str, as_of: date
) -> interface.Fetched | interface.Refused:
    """Every closed day the venue publishes for ``symbol``, up to the day before ``as_of``."""
    last = as_of - timedelta(days=1)
    end_ms = _midnight_ms(as_of) - 1
    quotations: list[interface.Quotation] = []
    cursor = 0
    url = _page_url(symbol=symbol, start_ms=cursor, end_ms=end_ms)
    while cursor <= end_ms:
        page = _page(url, as_of=as_of)
        if not isinstance(page, tuple):
            return page
        if not page:
            break
        quotations.extend(page)
        # Termination, not shape: a venue serving the same page for a cursor it ignores would
        # otherwise page for ever, and a hung fetch is the one failure that never reports.
        following = _midnight_ms(page[-1].on_date) + DAY_MS
        if following <= cursor:
            return interface.Unrecognised(
                url=url,
                detail=f"the page ends at {page[-1].on_date.isoformat()}, where the last began",
            )
        cursor = following
        url = _page_url(symbol=symbol, start_ms=cursor, end_ms=end_ms)
    incomplete = _complete(tuple(quotations), url=url, symbol=symbol, last=last)
    if incomplete is not None:
        return incomplete
    return interface.Fetched(
        kind=kind,
        symbol=symbol,
        as_of=as_of,
        endpoint=ENDPOINT,
        quotations=tuple(quotations),
    )


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _header(fetched: interface.Fetched) -> list[str]:
    return [
        f"# {fetched.symbol} daily closing prices, as {HOST} publishes them.",
        "# GENERATED -- do not edit by hand.",
        "#",
        "# Written by scripts/fetch_binance.py. Re-run it instead of editing, and read the",
        "# diff: a figure that moved is the point of keeping this file.",
        "#",
        "# RETRIEVED, NOT VERIFIED. Every `verified_on` below is empty and must stay empty",
        "# until a human has compared that row's close against the venue's own presentation of",
        "# that day. A downloaded number is not a checked number, and no automation may fill",
        "# the field -- this script never does, and a re-run rewrites the file in full, so a",
        "# verification filled by hand does not survive one.",
        "#",
        "# EVERY ROW IS A DAY THAT HAS CLOSED. The candle for `retrieved_on` itself is still",
        "# open: its close is the last trade so far rather than the day's, so it is refused",
        "# rather than written and the newest row here is the day before. A run asking for a",
        "# price on the retrieval date finds no row and refuses by name.",
        "#",
        "# THE SYMBOL IS RECORDED AS REQUESTED AND IS NEVER SPLIT. A kline row publishes",
        "# neither a base nor a quote asset, so nothing here says what `close` is quoted in",
        "# beyond the symbol itself. Where that symbol ends in USDT the quotation is in a",
        "# dollar-referenced token and NOT in USD: what one of those is worth in dollars is a",
        "# belief the owner declares, marked an assumption on every figure struck through it,",
        "# and it is never this file's business.",
        "#",
    ]


def _citation(fetched: interface.Fetched) -> str:
    return (
        f"{HOST} -- Binance public market data, {fetched.symbol} {INTERVAL} kline. The value "
        f"is element 4 of the venue's twelve-element row, the close, and its date is element "
        f"0, the UTC open time. Retrieved from {fetched.endpoint} on "
        f"{fetched.as_of.isoformat()} by scripts/fetch_binance.py. The symbol is the one "
        f"requested and is not split into a base and a quote asset. A venue's own quotation "
        f"of what it trades, not an independent valuation."
    )


def render(fetched: interface.Fetched) -> str:
    """The observation file, in full. Pure -- takes no clock and touches no disk."""
    citation = _escape(_citation(fetched))
    lines = _header(fetched)
    lines.extend(
        [
            f'retrieved_on = "{fetched.as_of.isoformat()}"',
            f'endpoint     = "{fetched.endpoint}"',
            f'symbol       = "{_escape(fetched.symbol)}"',
            f'interval     = "{INTERVAL}"',
            "",
        ]
    )
    lines.extend(
        "[[observation]]\n"
        f'on_date      = "{quotation.on_date.isoformat()}"\n'
        f"close        = {quotation.close}\n"
        f'kind         = "{OBSERVATION_KIND}"\n'
        f'source       = "{citation}"\n'
        f'retrieved_on = "{fetched.as_of.isoformat()}"\n'
        'verified_on  = ""\n'
        for quotation in fetched.quotations
    )
    return "\n".join(lines)


_IMPLEMENTS: Final[interface.FetchFn] = fetch
"""Checked by mypy rather than stated: an implementation that drifts from the interface it
claims is a defect no test of this module's behaviour would see."""
