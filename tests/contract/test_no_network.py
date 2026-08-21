"""The no-network guard is proven to work, not merely installed.

Constitution Principle V: tests never reach the network, and CI runs with networking
unavailable. Tracked as K4 in ``docs/REQUIRED_TESTS.md``.

A guard that silently stopped working would let a live provider call sneak into the
suite and make it nondeterministic -- exactly the failure mode that made the
predecessor's cache poisoning (REWRITE_BRIEF.md D2) invisible for so long. So the
guard gets its own test.
"""

from __future__ import annotations

import socket

import pytest

from tests.conftest import NetworkAccessAttemptedError


@pytest.mark.contract
def test_socket_connect_is_blocked() -> None:
    """Opening a socket raises rather than reaching the network."""
    with (
        pytest.raises(NetworkAccessAttemptedError, match="offline snapshot"),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
    ):
        sock.connect(("example.invalid", 80))


@pytest.mark.contract
def test_create_connection_is_blocked() -> None:
    """The convenience helper is blocked too, not just the method."""
    with pytest.raises(NetworkAccessAttemptedError):
        socket.create_connection(("example.invalid", 80), timeout=0.01)
