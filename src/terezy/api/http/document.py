"""The OpenAPI document: a published contract, generated on the fly and stored nowhere.

Byte-reproducible or the client generated from it drifts without a diff to read -- a fixed key
order, a fixed indentation, a trailing newline, and no value read from the clock, the environment
or the filesystem. :data:`VERSION` is a literal for that last reason: a package version is read at
run time from installed distribution metadata, so an editable install of a dirty tree and a built
wheel of the same source report different strings for one wire shape. It is also the wrong number
on its own terms -- the package version moves when the tax engine changes and a generated client
does not care (020 FR-039, FR-041).

The document is not a file in this repository (owner decision 2026-09-05,
`specs/decisions/2026-09-05-openapi-on-the-fly.toml`): a generated artefact checked in beside the
types it was generated from is a second copy of them.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from fastapi import FastAPI

VERSION: Final[str] = "1.0.0"
"""The version of **this wire contract**, bumped in the same commit as any change to the served
document that a generated client would have to react to."""

TITLE: Final[str] = "terezy"

PREFIX: Final[str] = "/api"
"""Where every endpoint is mounted, in one place.

The prefix is carried by the document, so a client generated from it is correct by
construction. The alternative -- the client's dev server rewriting paths -- would be this
feature's route table copied into a proxy configuration (021 FR-033).
"""


def rendered(app: FastAPI) -> str:
    """The document's bytes: sorted keys, two-space indent, trailing newline.

    The one renderer, so the endpoint and the generator that feeds the client build cannot
    produce the same *document* as different *bytes*.
    """
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
