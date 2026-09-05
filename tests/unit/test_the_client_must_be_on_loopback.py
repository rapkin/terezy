"""The half of the bind guard that holds when terezy did not start the process.

``uvicorn terezy.api.http:app --host 0.0.0.0`` never reaches the startup check, so the
per-request check is the one that carries the default context (020 FR-026a, SC-012b). It is
driven here by handing the middleware an ASGI scope directly rather than by starting a server,
which is what makes the claim independent of how the process was started -- and is the only
form of the test the suite's no-socket rule permits.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from terezy.api.http import middleware
from terezy.api.http.bind import BindContext, ClientPermitted, ClientRefused, client_is_permitted

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Receive, Scope, Send

SERVED = b'{"served":true}'


async def _stub(scope: Scope, receive: Receive, send: Send) -> None:
    """An inner app that answers everything, so a 200 means the guard let the request through."""
    assert scope["type"] in {"http", "lifespan"}
    assert receive is not None
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": SERVED})


def _scope(client: tuple[str, int] | None) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/registry",
        "raw_path": b"/registry",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"127.0.0.1:8000")],
        "client": client,
        "server": ("127.0.0.1", 8000),
    }


def _drive(app: ASGIApp, scope: dict[str, Any]) -> tuple[int, bytes]:
    """Run one request through an ASGI app in this process and collect the response."""
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        messages.append(dict(message))

    async def once() -> None:
        await app(scope, receive, send)

    asyncio.run(once())
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return int(start["status"]), body


@pytest.mark.parametrize("address", ["192.168.1.10", "10.0.0.4", "203.0.113.7", "::ffff:8.8.8.8"])
def test_a_non_loopback_client_is_refused_under_the_default_context(address: str) -> None:
    guarded = middleware.loopback_guard(_stub, context=BindContext.LOOPBACK)
    status, body = _drive(guarded, _scope((address, 51234)))

    assert status == 403
    refusal = json.loads(body)
    assert refusal["tag"] == "middleware.NotOnLoopback"
    assert refusal["client_address"] == address
    assert "Principle VII" in refusal["reason"]
    assert "authentication" in refusal["reason"].lower()


def test_an_absent_client_address_is_refused_too() -> None:
    """*No opinion* and *loopback* are different facts, and reading the first as the second is
    the fail-open FR-026a exists for. Both ASGI address fields are optional."""
    guarded = middleware.loopback_guard(_stub, context=BindContext.LOOPBACK)
    status, body = _drive(guarded, _scope(None))

    assert status == 403
    assert json.loads(body)["client_address"] is None


@pytest.mark.parametrize("address", ["127.0.0.1", "127.0.0.53", "::1"])
def test_a_loopback_client_is_served(address: str) -> None:
    guarded = middleware.loopback_guard(_stub, context=BindContext.LOOPBACK)
    status, body = _drive(guarded, _scope((address, 51234)))

    assert status == 200
    assert body == SERVED


@pytest.mark.parametrize("client", [("172.17.0.1", 51234), None])
def test_the_check_is_relaxed_inside_a_container(client: tuple[str, int] | None) -> None:
    """Inside a container every client address is the bridge, so no finer statement is
    available and the port publication is what holds instead (FR-027, FR-029 row 4)."""
    guarded = middleware.loopback_guard(_stub, context=BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK)
    status, body = _drive(guarded, _scope(client))

    assert status == 200
    assert body == SERVED


def test_a_client_address_that_is_not_an_address_is_refused() -> None:
    guarded = middleware.loopback_guard(_stub, context=BindContext.LOOPBACK)
    status, _ = _drive(guarded, _scope(("evil.example", 51234)))

    assert status == 403


def test_a_lifespan_message_passes_through_the_guard() -> None:
    """A lifespan scope carries no client, and refusing it would stop the app from starting."""
    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        assert receive is not None
        assert send is not None
        seen.append(str(scope["type"]))

    guarded = middleware.loopback_guard(inner, context=BindContext.LOOPBACK)

    async def receive() -> dict[str, Any]:
        return {"type": "lifespan.startup"}

    async def send(message: MutableMapping[str, Any]) -> None:
        seen.append(str(message))

    async def once() -> None:
        await guarded({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)

    asyncio.run(once())
    assert seen == ["lifespan"]


@pytest.mark.parametrize(
    ("address", "context", "permitted"),
    [
        ("127.0.0.1", BindContext.LOOPBACK, True),
        ("::1", BindContext.LOOPBACK, True),
        ("192.168.1.10", BindContext.LOOPBACK, False),
        (None, BindContext.LOOPBACK, False),
        ("192.168.1.10", BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK, True),
        (None, BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK, True),
    ],
)
def test_the_decision_itself_is_a_typed_result(
    address: str | None, context: BindContext, permitted: bool
) -> None:
    outcome = client_is_permitted(address, context=context)

    assert isinstance(outcome, ClientPermitted if permitted else ClientRefused)
    assert outcome.reason
