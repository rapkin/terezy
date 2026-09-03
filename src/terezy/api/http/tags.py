"""The tag a client switches on, derived here and never stored on a core record.

``<module leaf>.<ClassName>``. The bare class name is not available -- two class names occur
twice in the core, and one of them is a refusal, so a bare-name scheme would collide on a member
a client has to narrow on. The fully-qualified path was rejected for the opposite reason: it puts
the package layout in a wire contract, so moving a module renames a tag every client switches on
(020 FR-012).

:data:`OVERRIDES` is the tie-break. Injectivity today is luck -- ten module leaves are duplicated
inside ``terezy.core``, so ``leaf.ClassName`` is injective only because no two same-leaf modules
declare a same-named class. When ``tests/contract/test_tags_are_injective.py`` goes red the remedy
is one line here, never a rename in ``terezy.core``: renaming a core record to satisfy a
serialiser is the inversion this layer exists to prevent, and renaming a module is what the
fully-qualified scheme was rejected for (020 FR-012a).
"""

from __future__ import annotations

from typing import Final

OVERRIDES: Final[dict[type, str]] = {}
"""Records whose tag is stated rather than derived. Empty, and see the module docstring."""


def tag_of(record: type) -> str:
    """The wire tag for one record type."""
    stated = OVERRIDES.get(record)
    if stated is not None:
        return stated
    return f"{leaf_of(record)}.{record.__name__}"


def model_name_of(record: type) -> str:
    """What the record's schema is filed under in the OpenAPI document's components.

    The tag with an underscore for the dot: an OpenAPI component name is what a generated
    client turns into a type name, and a dot in one is a needless thing for every generator to
    have to escape. Injectivity of both is asserted together, because the substitution could in
    principle collide where the tag does not.
    """
    return f"{leaf_of(record)}_{record.__name__}"


def leaf_of(record: type) -> str:
    """The last segment of the record's module path."""
    return record.__module__.rsplit(".", 1)[-1]
