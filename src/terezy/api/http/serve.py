"""The process entry point: check the address, then hand the server the address that was checked.

FR-026b requires terezy to own this, so the supported way to start the service is the one that
refuses early -- a message at boot beats a service that starts and then refuses every request.
It is the *early and legible* half and not the guarantee: a bare server command never calls
this, which is why :func:`terezy.api.http.middleware.loopback_guard` exists.

``--host`` and ``--port`` are the only options, and ``TEREZY_BIND_CONTEXT`` the only variable
read. FR-030 forbids a second input that lets a refused address through, and
``tests/unit/test_the_bind_context_is_closed.py`` scans this module for one rather than
trusting the sentence.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from terezy.api.http import bind

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Callable, Sequence

    Starter = Callable[[str, int], None]

DEFAULT_HOST: Final[str] = "127.0.0.1"

DEFAULT_PORT: Final[int] = 8000

FILESYSTEM_ROOT: Final[Path] = Path("/")

REFUSED: Final[int] = 1

APP: Final[str] = f"{__package__}:app"
"""The application, named for the server to import rather than imported here.

Derived from this module's own package so moving the tree cannot leave the name behind. An
import string also keeps the app's own import -- which reads a data root -- off the refusal
path, so a missing data root cannot turn a legible bind refusal into a traceback.
"""


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path = FILESYSTEM_ROOT,
    start: Starter | None = None,
) -> int:
    """Parse the address, apply the bind guard, and serve on the address that passed it.

    ``root`` and ``start`` are injected so the whole entry point is decidable without a
    container and without opening a socket; both defaults are the production ones.
    """
    parser = argparse.ArgumentParser(
        prog="python -m terezy.api.http",
        description="Serve the terezy HTTP API on loopback.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args(argv)

    context = bind.context_of(os.environ.get(bind.CONTEXT_VARIABLE))
    if isinstance(context, bind.ContextNotRecognised):
        return _refuse(context.reason)

    outcome = bind.check_bind(arguments.host, context=context, marker=bind.container_marker(root))
    match outcome:
        case bind.BindRefused(reason=reason):
            return _refuse(reason)
        case bind.BindPermitted(address=address):
            (start or _start)(address, int(arguments.port))
            return 0


def _refuse(reason: str) -> int:
    sys.stderr.write(f"{reason}\n")
    return REFUSED


def _start(address: str, port: int) -> None:
    """Hand the checked address to the server."""
    import uvicorn  # noqa: PLC0415

    uvicorn.run(APP, host=address, port=port)
