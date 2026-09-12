"""The per-request refusals, written as closures over the app rather than as classes.

:func:`loopback_guard` is the load-bearing half of the bind restriction: it holds however the
process was started, which :mod:`terezy.api.http.serve` cannot (020 FR-026a).
:func:`host_allowlist` closes DNS rebinding, where a page re-points its own hostname at
``127.0.0.1``, the browser calls the request same-origin and therefore sends no ``Origin``
header, and the ``Host`` is the only place the shape is visible from inside the process
(FR-032b).

No cross-origin allowance is declared anywhere: feature 021's client is same-origin with this
service in both of its modes, so an allowance would widen the surface for nobody.

Each refusal is a JSON body carrying a tag of the form ``<module leaf>.<ClassName>``, the same
scheme every other record in this layer is serialised under, so a client narrows on these the
way it narrows on everything else. A bare status code would leave it nothing to switch on.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, Literal

from terezy.api.http import bind

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Iterable

    from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_HOSTS: Final[tuple[str, ...]] = ("localhost", "127.0.0.1", "[::1]")
"""The closed list of hosts a request may name. Host part only; a port is stripped."""

BODY_LIMIT: Final[int] = 64 * 1024
"""What a request body may be, in bytes (029 FR-024).

A service limit rather than domain knowledge, so it is declared here and not in `data/`: nothing
about the owner's money decides it. About thirty times the canonical JSON of the question this
repository ships, which is the real thing it is measured against.
"""

BODYLESS_METHODS: Final[tuple[str, ...]] = ("GET", "HEAD", "OPTIONS")
"""The methods that carry no body, and are therefore not asked to declare a length.

Without this the cap would refuse every read on this surface -- each is a GET that legitimately
declares no `Content-Length` -- and would do it wearing a message about a question document.
"""


@dataclass(frozen=True, kw_only=True)
class NotOnLoopback:
    tag: Literal["middleware.NotOnLoopback"] = "middleware.NotOnLoopback"
    client_address: str | None
    reason: str


@dataclass(frozen=True, kw_only=True)
class HostNotDeclared:
    tag: Literal["middleware.HostNotDeclared"] = "middleware.HostNotDeclared"
    host: str | None
    declared: tuple[str, ...]
    reason: str


@dataclass(frozen=True, kw_only=True)
class BodyTooLarge:
    tag: Literal["middleware.BodyTooLarge"] = "middleware.BodyTooLarge"
    limit_bytes: int
    declared_bytes: int
    reason: str


@dataclass(frozen=True, kw_only=True)
class BodyLengthNotDeclared:
    tag: Literal["middleware.BodyLengthNotDeclared"] = "middleware.BodyLengthNotDeclared"
    method: str
    limit_bytes: int
    reason: str


def body_cap(app: ASGIApp, *, limit: int = BODY_LIMIT) -> ASGIApp:
    """Refuse a request whose declared body exceeds the cap, before anything is parsed.

    In the guard chain rather than in the route, because the body is read and parsed before a
    handler runs -- a cap checked there has already paid for the parse it exists to prevent.

    A body-bearing request that declares **no** length is refused rather than streamed and
    counted: counting as it arrives is the machinery the cap exists to avoid.
    """

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "") in BODYLESS_METHODS:
            await app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is None:
            await _refuse(
                send,
                HTTPStatus.LENGTH_REQUIRED,
                BodyLengthNotDeclared(
                    method=str(scope.get("method", "")),
                    limit_bytes=limit,
                    reason=(
                        "this request carries a body and declares no readable Content-Length, "
                        "so the cap could only be applied by counting the bytes as they "
                        "arrive -- which is the machinery the cap exists to avoid."
                    ),
                ),
            )
            return
        if declared > limit:
            await _refuse(
                send,
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                BodyTooLarge(
                    limit_bytes=limit,
                    declared_bytes=declared,
                    reason=(
                        f"the body declares {declared} bytes and the cap is {limit}. Nothing "
                        "was parsed and nothing was truncated: a document read in part is a "
                        "question nobody asked."
                    ),
                ),
            )
            return
        await app(scope, receive, send)

    return guarded


def _content_length(scope: Scope) -> int | None:
    """The declared body length, or ``None`` where none is declared or it is not a number."""
    headers: Iterable[tuple[bytes, bytes]] = scope.get("headers", [])
    for key, value in headers:
        if key.lower() == b"content-length":
            try:
                return int(value.decode("latin-1"))
            except ValueError:
                return None
    return None


def loopback_guard(app: ASGIApp, *, context: bind.BindContext) -> ASGIApp:
    """Refuse a request whose client is not on loopback, under the default context."""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        client = scope.get("client")
        address = str(client[0]) if client else None
        match bind.client_is_permitted(address, context=context):
            case bind.ClientRefused(reason=reason):
                await _refuse(
                    send,
                    HTTPStatus.FORBIDDEN,
                    NotOnLoopback(client_address=address, reason=reason),
                )
            case bind.ClientPermitted():
                await app(scope, receive, send)

    return guarded


def host_allowlist(app: ASGIApp, *, hosts: tuple[str, ...] = ALLOWED_HOSTS) -> ASGIApp:
    """Refuse a request whose ``Host`` header names a host this service does not declare."""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        header = _host_header(scope)
        if header is None or host_of(header) not in hosts:
            await _refuse(
                send,
                HTTPStatus.BAD_REQUEST,
                HostNotDeclared(
                    host=host_of(header) if header is not None else None,
                    declared=hosts,
                    reason=(
                        "The Host header names a host this service does not declare. A page "
                        "that re-points its own hostname at a loopback address sends no Origin "
                        "header, so this is where such a request is visible."
                    ),
                ),
            )
            return
        await app(scope, receive, send)

    return guarded


def host_of(header: str) -> str:
    """The host part of a ``Host`` header, lowercased, with any port removed.

    A bracketed IPv6 literal keeps its brackets and its colons: splitting on the first colon
    would turn ``[::1]:8000`` into ``[``.
    """
    value = header.strip().lower()
    if value.startswith("["):
        closed = value.find("]")
        return value if closed == -1 else value[: closed + 1]
    return value.split(":", 1)[0]


def _host_header(scope: Scope) -> str | None:
    headers: Iterable[tuple[bytes, bytes]] = scope.get("headers", [])
    for key, value in headers:
        if key.lower() == b"host":
            return value.decode("latin-1")
    return None


async def _refuse(
    send: Send,
    status: HTTPStatus,
    record: NotOnLoopback | HostNotDeclared | BodyTooLarge | BodyLengthNotDeclared,
) -> None:
    body = json.dumps(asdict(record), ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
