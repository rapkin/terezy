"""The two per-request refusals, written as closures over the app rather than as classes.

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


async def _refuse(send: Send, status: HTTPStatus, record: NotOnLoopback | HostNotDeclared) -> None:
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
