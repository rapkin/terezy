"""Shared test fixtures, the no-network guard, and the Hypothesis profile.

Constitution Principle V: tests never reach the network, and CI runs with networking
unavailable. The guard below makes that a local property of the suite too, so a
developer running tests on a connected machine gets the same failure CI would give.

Tracked as K4 in ``docs/REQUIRED_TESTS.md``.
"""

from __future__ import annotations

import socket
from typing import Any, NoReturn

import pytest
from hypothesis import settings

settings.register_profile("terezy", deadline=None)
settings.load_profile("terezy")
"""No per-example wall-clock deadline anywhere in the suite.

**A deadline is a timing assertion, and this suite has no timing claim to make.** Every
property here is about a figure, an invariant or a refusal; none of them is about how long
an example took. Under ``pytest --cov`` the instrumentation alone can push a single example
past Hypothesis's 200 ms default, and the result is a red compliance suite that goes green on
the next run -- which teaches a reader to rerun a red ``invariant`` rather than read it. That
is a worse failure than the one the deadline was meant to catch, and it is the reason
``test_determinism.py`` and the 003 property modules already turned it off one module at a
time. This is the same decision made once, in one place, for the same reason.

What this does **not** do: relax any correctness bound. Hypothesis still shrinks and still
reports; ``max_examples`` stays wherever each module set it. A genuine performance regression
is not something this suite was ever measuring, and pretending otherwise with a 200 ms
per-example timeout would be a number more confident than its input.
"""


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
