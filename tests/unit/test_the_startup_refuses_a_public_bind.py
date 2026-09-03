"""The early, legible half: terezy's own entry point refuses the address before it binds.

This is not the guarantee -- a bare server command never reaches it, which is why
``test_the_client_must_be_on_loopback.py`` exists -- but a message at boot beats a service
that starts and then refuses everything (020 FR-026, FR-026b, SC-012).
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any, NoReturn

import pytest

from terezy.api.http import serve
from terezy.api.http.bind import (
    CONTEXT_VARIABLE,
    BindContext,
    BindPermitted,
    BindRefused,
    check_bind,
)

if TYPE_CHECKING:
    from pathlib import Path

PUBLIC = ["0.0.0.0", "::", "192.168.1.10", "10.0.0.4", "203.0.113.7"]
LOOPBACK = ["127.0.0.1", "::1", "127.0.0.53"]


@pytest.fixture(autouse=True)
def _no_name_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard that resolved a name would make the suite's no-network rule depend on the
    machine's resolver -- green offline for the wrong reason (FR-026). The suite's own guard
    covers ``connect``; resolution is a separate call and is blocked here."""

    def refuse(*args: Any, **kwargs: Any) -> NoReturn:
        message = "the bind guard must never resolve a name"
        raise AssertionError(message)

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "gethostbyname", refuse)


def _run(address: str, *, root: Path, started: list[tuple[str, int]]) -> int:
    return serve.main(["--host", address], root=root, start=lambda a, p: started.append((a, p)))


@pytest.mark.parametrize("address", PUBLIC)
def test_a_public_address_exits_non_zero_naming_the_release_gate(
    address: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    started: list[tuple[str, int]] = []

    code = _run(address, root=tmp_path, started=started)

    assert code != 0
    assert not started
    refusal = capsys.readouterr().err
    assert "Principle VII" in refusal
    assert "authentication" in refusal.lower()
    assert address in refusal


@pytest.mark.parametrize("address", LOOPBACK)
def test_a_loopback_address_starts_the_server_on_the_address_that_was_checked(
    address: str, tmp_path: Path
) -> None:
    started: list[tuple[str, int]] = []

    code = _run(address, root=tmp_path, started=started)

    assert code == 0
    assert started == [(address, 8000)]


def test_the_default_address_and_port_are_loopback(tmp_path: Path) -> None:
    started: list[tuple[str, int]] = []

    code = serve.main([], root=tmp_path, start=lambda a, p: started.append((a, p)))

    assert code == 0
    assert started == [("127.0.0.1", 8000)]


@pytest.mark.parametrize("name", ["localhost", "terezy.local", "evil.example", "example.com"])
def test_a_hostname_is_refused_as_a_hostname(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The caller resolves the name and hands over what it resolved to; the guard decides
    about an address, and is testable precisely because that is all it does."""
    started: list[tuple[str, int]] = []

    code = _run(name, root=tmp_path, started=started)

    assert code != 0
    assert not started
    refusal = capsys.readouterr().err
    assert "hostname" in refusal.lower()
    assert name in refusal


@pytest.mark.parametrize("address", LOOPBACK)
def test_the_guard_itself_permits_only_loopback_under_the_default_context(address: str) -> None:
    outcome = check_bind(address, context=BindContext.LOOPBACK, marker=None)

    assert isinstance(outcome, BindPermitted)
    assert outcome.address == address


@pytest.mark.parametrize("address", PUBLIC)
def test_the_guard_itself_refuses_a_public_address_under_the_default_context(
    address: str,
) -> None:
    outcome = check_bind(address, context=BindContext.LOOPBACK, marker=None)

    assert isinstance(outcome, BindRefused)
    assert "Principle VII" in outcome.reason


def test_a_marker_does_not_widen_the_default_context() -> None:
    """The context is what admits the container interface; being inside a container is not."""
    outcome = check_bind("0.0.0.0", context=BindContext.LOOPBACK, marker="/.dockerenv")

    assert isinstance(outcome, BindRefused)


def test_the_environment_variable_is_read_by_the_entry_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The declared context reaches the guard; without that this module's other cases would
    pass against an entry point that ignored the variable entirely."""
    (tmp_path / ".dockerenv").touch()
    monkeypatch.setenv(CONTEXT_VARIABLE, BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK.value)
    started: list[tuple[str, int]] = []

    code = _run("0.0.0.0", root=tmp_path, started=started)

    assert code == 0
    assert started == [("0.0.0.0", 8000)]
