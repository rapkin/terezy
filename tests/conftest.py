"""Shared test fixtures and the no-network guard.

Constitution Principle V: tests never reach the network, and CI runs with networking
unavailable. The guard below makes that a local property of the suite too, so a
developer running tests on a connected machine gets the same failure CI would give.

Tracked as K4 in ``docs/REQUIRED_TESTS.md``.
"""

from __future__ import annotations

import socket
from typing import Any, NoReturn

import pytest


class NetworkAccessAttemptedError(RuntimeError):
    """Raised when a test tries to open a socket.

    A test that needs data uses the checked-in offline snapshot
    (``src/terezy/data/snapshot/``), never a live provider.
    """


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly on any attempt to open a network connection."""

    def guard(*args: Any, **kwargs: Any) -> NoReturn:
        raise NetworkAccessAttemptedError(
            "A test attempted network access. Tests must run against the offline "
            "snapshot in src/terezy/data/snapshot/ (constitution, Principle V)."
        )

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
