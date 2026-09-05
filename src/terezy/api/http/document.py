"""The OpenAPI document: a published contract, checked in and byte-gated.

Byte-reproducible or it cannot be gated -- a fixed key order, a fixed indentation, a trailing
newline, and no value read from the clock, the environment or the filesystem. :data:`VERSION` is
a literal for that last reason: a package version is read at run time from installed
distribution metadata, so an editable install of a dirty tree and a built wheel of the same
source can report different strings and the gate would be red on one machine and green on
another with no source change. It is also the wrong number on its own terms -- the package
version moves when the tax engine changes and a generated client does not care (020 FR-039,
FR-041).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from fastapi import FastAPI

VERSION: Final[str] = "1.0.0"
"""The version of **this wire contract**, bumped in the same commit as any change to the
committed document that a generated client would have to react to."""

TITLE: Final[str] = "terezy"

PREFIX: Final[str] = "/api"
"""Where every endpoint is mounted, in one place.

The prefix is carried by the document, so a client generated from it is correct by
construction. The alternative -- the client's dev server rewriting paths -- would be this
feature's route table copied into a proxy configuration (021 FR-033).
"""

PATH: Final[Path] = Path(__file__).with_name("openapi.json")
"""The committed artefact. Inside the package because it changes when and only when this
module's response types do, and because it then ships in the wheel, so a consumer resolves it by
package path rather than by a relative path into a source checkout."""


def rendered(app: FastAPI) -> str:
    """The document as its committed bytes: sorted keys, two-space indent, trailing newline."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def committed() -> str:
    """The bytes on disk, which is what `/openapi.json` serves.

    Serving the artefact rather than re-serialising the generated document is what makes the
    endpoint and the file the same *bytes* and not merely the same *document*: the framework's
    JSON response writes compact separators and no trailing newline, and a client told the file
    is its source of truth would fetch the endpoint and find it did not match.
    """
    return PATH.read_text(encoding="utf-8")
