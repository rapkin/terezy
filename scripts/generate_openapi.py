"""Regenerate the committed OpenAPI document.

Here rather than in the package because the response to a red byte-gate is *run this and read
the diff*, never *edit JSON by hand* -- and this is the repository's own place for a command a
person runs and reads the diff of, beside `check_provenance.py` and `fetch_cpi.py` (020 FR-040).

The application is built over a literal data root rather than the configured one: the document
is a function of the response types and of nothing on the machine that generated it, and reading
an environment variable here would make that claim untestable (FR-039).
"""

from __future__ import annotations

import sys
from pathlib import Path

from terezy.api.http import document
from terezy.api.http.service import create_app

DATA_ROOT = Path("data")


def main() -> int:
    """Write the document, and say whether the file moved."""
    rendered = document.rendered(create_app(DATA_ROOT, client=None))
    before = document.PATH.read_text(encoding="utf-8") if document.PATH.is_file() else ""
    document.PATH.write_text(rendered, encoding="utf-8")
    moved = rendered != before
    print(  # noqa: T201
        f"{'wrote' if moved else 'unchanged'} {document.PATH} ({len(rendered)} characters)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
