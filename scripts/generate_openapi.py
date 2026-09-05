"""Write the OpenAPI document the application serves.

The document is generated, never stored (owner decision 2026-09-05). This is the same renderer
the `/openapi.json` endpoint uses, exposed as a command so a build can pipe it into a generator
without starting a server -- which is how the web client gets its types (021 FR-003).

The application is built over a literal data root rather than the configured one: the document is
a function of the response types and of nothing on the machine that generated it, and reading an
environment variable here would make that claim untestable (020 FR-039).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from terezy.api.http import document
from terezy.api.http.service import create_app

DATA_ROOT = Path("data")


def main(argv: list[str] | None = None) -> int:
    """Write the document to the named path, or to standard output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="where to write the document. Standard output when absent.",
    )
    arguments = parser.parse_args(argv)
    rendered = document.rendered(create_app(DATA_ROOT, client=None))
    encoded = rendered.encode("utf-8")
    if arguments.out is None:
        # Bytes both ways: the caller pipes this into a generator, and `sys.stdout` would encode
        # with the locale's codec and translate newlines -- either of which makes the document a
        # different file from the one the endpoint serves.
        sys.stdout.buffer.write(encoded)
    else:
        arguments.out.write_bytes(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
