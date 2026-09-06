"""The ``Provider`` interface: what a fetch returns, and what it refuses.

One of the four plugin interfaces Principle II permits, and under owner decision D-E an
interface is a function signature over frozen records rather than a hierarchy:
:data:`FetchFn` is the whole contract, and an implementation is a module-level function of
that shape.

**A refusal is a value, and the refusals are distinct types because their remedies are.**
Wait and re-run, stop and do not retry, read the publisher's documentation before touching
the parser, ask again once the window is complete, ask again once the day has closed: a
caller holding one reason string can tell a reader that something failed but not which of
those to do.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

type SeriesKind = Literal["daily_close"]
"""What a provider is asked for. One member because one is implemented; a second arrives
with the implementation that serves it, never ahead of it."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Quotation:
    """One closed day, at the price the venue published for it."""

    on_date: date
    close: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """A complete series and the provenance of the act that retrieved it."""

    kind: SeriesKind
    symbol: str
    """The venue's own symbol, as requested. A provider never splits it into a base and a
    quote asset: choosing where a symbol divides is a judgement, and the fetcher is the one
    party to this that may not make one."""
    as_of: date
    """The date the retrieval was performed as of. Every quotation is a day that closed
    before it."""
    endpoint: str
    quotations: tuple[Quotation, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Unreachable:
    """Nothing came back: the transport failed or the host did not answer."""

    url: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RateLimited:
    """The venue answered with a rate-limit or ban status.

    Never retried. Retrying into a rate limit is how it becomes a ban, and a client that
    keeps asking after being told to stop is the one thing a public endpoint offered without
    an account cannot afford.
    """

    url: str
    status: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Unrecognised:
    """The body is not the shape the endpoint documents.

    The remedy is to read what the venue now publishes, never to route around the row: a
    field nobody looked at is a value nobody checked.
    """

    url: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Incomplete:
    """What came back is not the window that was asked for -- a hole, or a short end."""

    url: str
    detail: str
    missing: tuple[date, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenCandle:
    """A row for a day that has not closed.

    Its close is the last trade so far rather than the day's, so writing it would put a
    figure in a file under a name the publisher has not finished earning.
    """

    url: str
    on_date: date
    as_of: date


Refused = Unreachable | RateLimited | Unrecognised | Incomplete | OpenCandle

FetchFn = Callable[[SeriesKind, str, date], Fetched | Refused]
"""``fetch(kind, symbol, as_of)`` -- the interface itself."""
