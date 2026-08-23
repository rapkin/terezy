"""Route diagrams: the declared graph, and any costed path, as Mermaid text.

Feature ``005-route-diagrams``. The registry that feature 002 declared is a **graph** --
venues are nodes, routes and their legs are edges -- and everyone who debugs it currently
reconstructs that graph in their head from TOML tables. This package does that rendering
once, mechanically, and identically for everyone.

**Why it lives in ``api`` and not in ``core``** (research.md D1). The core neither formats
nor rounds, and ``.importlinter`` enforces it: a core that can render is a core that can be
asked to round. Rendering is presentation, one layer up, consuming the *same* declared
records and result types everything else consumes -- no parallel data model and no second
reading of the declaration files, which is the half of FR-020 that would otherwise let a
diagram drift from the numbers it depicts. When a figure is awkward to render, the fix is
here; a helper in ``core`` is refused by the layer contract, and rightly.

**The three decisions that do the real work**, each of them a way the picture could have
been less honest than the tables:

* **One number rule** (:mod:`terezy.api.diagrams.numbers`, FR-022). Results carry floats and
  the project's canonical float form is hexadecimal, so "the diagram shows the result's
  figure" was undefined until a human-readable rule existed. There is exactly one, on the
  model of the single project tolerance, and a contract test greps for a second.
* **Marks live in label text** (:mod:`terezy.api.diagrams.marks`, FR-015). A mark carried by
  a colour is lost the moment the text is diffed, re-themed, or read as a golden file -- and
  golden files are one of the two places this output lands. ``classDef`` styling may add
  emphasis on top; it may never be the only carrier.
* **Node ids are positional** (:mod:`terezy.api.diagrams.mermaid`, FR-018). Deriving a
  Mermaid id from a declared id means sanitising, and sanitising maps ``binance-p2p`` and
  ``binance_p2p`` onto one identifier -- two venues silently merged into one node, with
  nothing in the output to say so.

**No new dependency.** The Mermaid text is a few kinds of line, written by hand
(research.md D10). A rendering library would put a third party between a declaration and
its picture and make the escaping someone else's semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

DiagramKind = Literal["route_graph", "costed_path"]
"""The two kinds of diagram this feature renders, and there are no others (FR-001).

A ``Literal`` rather than a ``str`` so a third kind is a type error rather than a diagram
nobody specified. The per-regime side-by-side pair is deferred, not forgotten (owner decision,
2026-08-22); every diagram shows exactly one named regime (FR-019).
"""


class Mode(Enum):
    """How much of a registry graph's declared data is shown. A closed set of two (FR-006).

    Rendered **by name into the diagram itself**, which is the point of having the enum at all:
    a numberless picture that did not say it was numberless would be read as "zero fees", the
    same class of error as an unlabelled one-way figure.

    In **either** mode a computed ramp cost never appears on a registry graph. Such a figure
    exists only per ``(destination x stream x route)`` -- which a registry graph does not name
    -- so putting one here would be feature 002's FR-008 violated in picture form. That is why
    it is forbidden in the mode that shows numbers too, and not only in the other one.
    """

    TOPOLOGY = "topology-only"
    """No figures at all: a pure picture of what connects to what."""

    DECLARED_FIGURES = "with-declared-figures"
    """Declared per-leg figures -- fees -- on the edges, each carrying its provenance state.
    Declared, never computed: the difference is the whole of FR-006's second half."""


@dataclass(frozen=True, slots=True)
class Diagram:
    """A rendered diagram: the text, and enough about it to say what it is a picture of."""

    text: str
    """Valid Mermaid, byte-identical for identical inputs (FR-016, FR-017).

    Ends in a newline, so the string is a file: the golden artifacts under ``tests/golden/``
    and the bytes ``scripts/render_diagram.py`` writes to stdout are this value and nothing
    added to it.
    """

    kind: DiagramKind
    """Which of the two kinds this is."""

    regime_id: str
    """The one regime this diagram shows (FR-019). Also on the face of the diagram -- this
    field is for a caller that has the record, not a second place the fact lives."""

    mode: Mode | None
    """The registry graph's mode, and ``None`` for a costed path, which has no modes.

    A costed path shows what one result costed; there is no version of it without figures,
    because the figures are the reason it exists.
    """


@dataclass(frozen=True, slots=True)
class NothingToDraw:
    """Returned **instead of** a :class:`Diagram`, carrying the refusal's own reason.

    Never an empty diagram (FR-011, SC-010, predecessor defect B10). An empty picture is
    indistinguishable from a graph that genuinely has nothing in it, and the caller's next
    move is different in the two cases. The reason the caller needs is already in the input --
    ``RouteUnusable.reason``, ``ExitCostUnknown.reason``, ``NothingComparable.reason`` -- so
    discarding it at the render step would lose the one piece of information the render was
    asked about.

    Unrelated to :class:`Diagram` by design, on the precedent of
    ``RoundTripCost | ExitCostUnknown``: the two share no base and no protocol, so a caller
    that forgot this case is a mypy error rather than an attribute error in front of the owner.
    A ``Diagram`` with an ``ok`` flag is the shape this deliberately is not (owner decision
    D-E).
    """

    reason: str
    """The refusal's own reason, carried verbatim. Never reworded: the words the engine chose
    are the words the owner has already learned to read."""

    kind: DiagramKind
    """What was asked for, so a caller can say which render refused."""


from terezy.api.diagrams.graph import render_graph  # noqa: E402

__all__ = [
    "Diagram",
    "DiagramKind",
    "Mode",
    "NothingToDraw",
    "render_graph",
]
