"""The check that closes DNS rebinding, and the allowance this service deliberately does not make.

A page on ``evil.com`` can re-point its own hostname at ``127.0.0.1`` and fetch
``http://evil.com:8000/registry``. The browser treats that as same-origin and sends **no**
``Origin`` header, so an origin check never fires -- the request's ``Host`` is the one place the
shape is visible from inside the process (020 FR-032b, SC-016c).

No cross-origin allowance is declared at all: feature 021's client is same-origin with this
service in both its modes, so an allowance would widen the surface for nobody. The absence is
asserted here rather than left to be noticed.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from terezy.api.http import encode, middleware, tags
from terezy.api.http.bind import BindContext

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Receive, Scope, Send

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "terezy"

SERVED = b'{"served":true}'


async def _stub(scope: Scope, receive: Receive, send: Send) -> None:
    assert scope["type"] == "http"
    assert receive is not None
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": SERVED})


def _drive(app: ASGIApp, headers: list[tuple[bytes, bytes]]) -> tuple[int, bytes, dict[str, str]]:
    messages: list[dict[str, Any]] = []
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/registry",
        "raw_path": b"/registry",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 51234),
        "server": ("127.0.0.1", 8000),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        messages.append(dict(message))

    async def once() -> None:
        await app(scope, receive, send)

    asyncio.run(once())
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    emitted = {key.decode().lower(): value.decode() for key, value in start.get("headers", [])}
    return int(start["status"]), body, emitted


@pytest.mark.contract
@pytest.mark.parametrize("host", list(middleware.ALLOWED_HOSTS))
def test_every_declared_host_is_a_loopback_host(host: str) -> None:
    literal = host[1:-1] if host.startswith("[") else host
    assert host == "localhost" or ipaddress.ip_address(literal).is_loopback


@pytest.mark.contract
def test_the_declared_hosts_carry_no_wildcard_and_no_pattern() -> None:
    for host in middleware.ALLOWED_HOSTS:
        assert not set(host) & set("*?%$^|")


@pytest.mark.contract
@pytest.mark.parametrize(
    "header",
    [b"127.0.0.1:8000", b"127.0.0.1", b"localhost:8000", b"LOCALHOST", b"[::1]:8000", b"[::1]"],
)
def test_a_declared_host_is_served_with_or_without_a_port(header: bytes) -> None:
    guarded = middleware.host_allowlist(_stub)

    status, body, _ = _drive(guarded, [(b"host", header)])

    assert status == 200
    assert body == SERVED


@pytest.mark.contract
@pytest.mark.parametrize("header", [b"evil.com:8000", b"terezy.example", b"192.168.1.10:8000"])
def test_an_undeclared_host_carrying_no_origin_is_refused(header: bytes) -> None:
    """The DNS-rebinding shape exactly: an undeclared ``Host`` and no ``Origin`` at all."""
    guarded = middleware.host_allowlist(_stub)

    status, body, _ = _drive(guarded, [(b"host", header)])

    assert status == 400
    refusal = json.loads(body)
    assert refusal["tag"] == "middleware.HostNotDeclared"
    assert refusal["host"] == middleware.host_of(header.decode())
    assert set(refusal["declared"]) == set(middleware.ALLOWED_HOSTS)


@pytest.mark.contract
def test_a_request_with_no_host_header_is_refused() -> None:
    guarded = middleware.host_allowlist(_stub)

    status, body, _ = _drive(guarded, [])

    assert status == 400
    assert json.loads(body)["host"] is None


@pytest.mark.contract
@pytest.mark.parametrize("origin", [b"http://evil.com", b"http://localhost:5173", b"null"])
def test_no_cross_origin_header_is_ever_emitted(origin: bytes) -> None:
    """A CORS allowance withholds, it does not refuse. This service declares none, so the
    refusal above is the whole of the answer and no response carries the header."""
    inner = middleware.loopback_guard(_stub, context=BindContext.LOOPBACK)
    guarded = middleware.host_allowlist(inner)

    _, _, emitted = _drive(guarded, [(b"host", b"127.0.0.1:8000"), (b"origin", origin)])

    assert "access-control-allow-origin" not in emitted
    assert "access-control-allow-credentials" not in emitted


@pytest.mark.contract
def test_no_module_installs_a_cross_origin_middleware() -> None:
    """The absence is the decision (021 FR-033, FR-049: the client is same-origin in both
    modes), so it is asserted rather than left to be noticed when someone adds one."""
    offenders = [
        str(path.relative_to(SOURCE_ROOT))
        for path in sorted(SOURCE_ROOT.rglob("*.py"))
        if "CORSMiddleware" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, f"a cross-origin allowance appeared in {offenders}"


@pytest.mark.contract
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("127.0.0.1:8000", "127.0.0.1"),
        ("[::1]:8000", "[::1]"),
        ("[::1]", "[::1]"),
        ("Evil.COM", "evil.com"),
        ("  localhost:3000  ", "localhost"),
    ],
)
def test_the_port_is_stripped_and_a_bracketed_literal_survives(header: str, expected: str) -> None:
    """A bare IPv6 literal has colons of its own, so splitting on the first one would turn
    ``[::1]:8000`` into ``[``."""
    assert middleware.host_of(header) == expected


@pytest.mark.contract
def test_the_middleware_refusals_carry_the_derived_tag() -> None:
    """These two are serialised without the shape machinery, so their tags are literals. The
    claim that they follow the same scheme is asserted here rather than left as prose."""
    for record in (middleware.NotOnLoopback, middleware.HostNotDeclared):
        declared = next(field.default for field in fields(record) if field.name == encode.TAG_FIELD)
        assert declared == tags.tag_of(record)
