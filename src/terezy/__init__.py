"""terezy — decision support for a UAH-income investor.

The product specification is ``docs/reference/SIMULATOR_SPEC.md``; the engine
charter is ``docs/reference/REWRITE_BRIEF.md``; how they get built is governed by
``.specify/memory/constitution.md``.

Layering (enforced by ``.importlinter``)::

    cli  ->  api  ->  data  ->  core

The core is pure and deterministic. Nothing below a layer may import from above it.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
