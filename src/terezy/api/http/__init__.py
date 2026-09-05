"""The HTTP surface: the one module tree the delivery framework may be imported in.

What this layer does is select, serialise and refuse. It computes no financial figure --
FR-003 has no exception, since the owner deferred the display switch on 2026-09-03 -- so no
module under here constructs a ``Money``, ages a source, or reads the clock.

The schema is the contract (constitution, Architecture Constraints). Every record in every
body carries a tag naming which record it is, derived here from the record's own identity and
never stored on a core record; every union is discriminated on that tag; and the OpenAPI
document generated from these types is checked in and byte-gated, because a client is
generated from it and a published copy that is not gated is a second schema going quietly out
of step with the first.
"""

from terezy.api.http import service
from terezy.api.http.service import create_app

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> object:
    """``terezy.api.http:app`` is what a server command addresses, and it is resolved on demand:
    importing this package must not build an application or read the environment."""
    if name == "app":
        return service.app
    raise AttributeError(name)
