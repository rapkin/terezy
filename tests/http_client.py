"""The in-process client every HTTP test uses, configured to get past both guards.

No test starts a server and no test opens a socket (020 FR-050). The base URL and the client
address are what the two per-request refusals check, so a helper that sets them is also the
place a reader learns that the guards are in the path of every test rather than bypassed by it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.testclient import TestClient

from terezy.api.http import bind, service

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from pathlib import Path

LOOPBACK = "http://127.0.0.1:8000"
CLIENT = ("127.0.0.1", 42424)


def served(root: Path, *, client_dist: Path | None = None) -> TestClient:
    """One client over one data root, through both guards under the default bind context."""
    application = service.create_app(root, client=client_dist)
    guarded = service.guarded(application, context=bind.BindContext.LOOPBACK)
    return TestClient(guarded, base_url=LOOPBACK, client=CLIENT)


def unguarded(root: Path, *, client_dist: Path | None = None) -> TestClient:
    """The routed application without the two guards, for tests about what it *returns*."""
    return TestClient(
        service.create_app(root, client=client_dist), base_url=LOOPBACK, client=CLIENT
    )
