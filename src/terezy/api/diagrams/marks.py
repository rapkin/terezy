"""The honesty marks, as label text, and the one place they are derived from a record.

FR-012 through FR-015. Honesty marks are this project's identity (Principle I), and the
picture will travel further than the tables -- it gets pasted into reports and read by people
who never open the TOML. A reader who has learned to trust the engine's unverified and stale
marks must be able to extend exactly that trust to the diagram.

**Marks live in the label text; styling may add emphasis and may never carry meaning**
(research.md D4). :data:`STYLE_CLASS` exists and is used, but every mark it colours is already
a word in the label. A mark carried only by a colour is lost the moment the text is diffed,
re-themed, or read as source in a golden file -- and golden files are one of exactly two
places this output lands (FR-021). ``tests/contract/test_diagram_marks.py`` strips every style
declaration and every class application before it looks for a single mark, which is the test
that keeps this honest.

**One vocabulary rather than formatting at each site.** FR-015 requires marks to survive
rendering, and one vocabulary is what makes "strip all styling and assert the marks are still
there" a single testable claim instead of six similar ones. Formatting at each site guarantees
drift, and the drift is invisible until someone reads two diagrams side by side.

**The two states that are the absence of a mark are named, not left blank.** An empty marks
segment is indistinguishable from a renderer that forgot, which is the same ambiguity
``core.primitives.staleness.UNASSESSED`` exists to remove: "everything was checked and nothing
is wrong" and "nobody checked" must not be the same value. So a clean figure says
:data:`CLEAN` and a figure resting on no cited source says :data:`UNSOURCED` -- because
``provenance.EMPTY`` is not unverified, and it is not verified either.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
from typing import Final

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance


class Mark(Enum):
    """The states a diagram element can carry. A **closed** set of six.

    Closed for the reason every enumeration in this project is closed: a free-form mark
    vocabulary would let one call site invent a token, and "every state is pairwise
    distinguishable" -- the claim SC-004 makes -- would become unprovable. Adding a seventh is
    a code change reviewed against that claim.

    Deliberately not a ``str`` subclass, on the same reasoning as
    ``core.primitives.currency.Currency``: a string-valued enum compares equal to a bare
    string, which would let ``"STALE"`` occupy a position that should require a member.
    """

    UNVERIFIED = "unverified"
    """No source behind this figure has been checked against a primary source (FR-012)."""

    STALE = "stale"
    """Some source behind it aged past its kind's declared threshold (FR-013).

    A different claim from :attr:`UNVERIFIED`, and neither implies the other: a tariff
    verified two years ago is verified and stale; this morning's premium from a screenshot is
    unverified and fresh.
    """

    SYNTHETIC = "synthetic"
    """Built on a declared test fixture, so a picture of invented data can never pass as a
    picture of the owner's actual options (FR-014)."""

    CLOSED = "closed"
    """The route is declared closed. Present and marked, never omitted -- closed and
    nonexistent are different facts and must look different (FR-004)."""

    NO_EXIT_DECLARED = "no-exit"
    """Nothing is declared leaving this destination, so it is not comparison-ready (FR-005).
    Feature 002's FR-030 made visual: an explicitly absent edge, never an omission."""

    EXIT_COST_UNKNOWN = "exit-unknown"
    """A costed result whose round-trip slot is ``ExitCostUnknown``. Rendered in the place the
    exit would occupy, with no round-trip figure anywhere on the diagram (FR-010)."""


_TOKEN: Final[Mapping[Mark, str]] = {
    Mark.UNVERIFIED: "UNVERIFIED",
    Mark.STALE: "STALE",
    Mark.SYNTHETIC: "SYNTHETIC",
    Mark.CLOSED: "CLOSED",
    Mark.NO_EXIT_DECLARED: "NO EXIT DECLARED",
    Mark.EXIT_COST_UNKNOWN: "EXIT COST UNKNOWN",
}
"""What each mark says on the page. Upper case, and no token a substring of another, so
``token in label`` is a safe question to ask of a diagram's text."""

STYLE_CLASS: Final[Mapping[Mark, str]] = {
    Mark.UNVERIFIED: "unverified",
    Mark.STALE: "stale",
    Mark.SYNTHETIC: "synthetic",
    Mark.CLOSED: "closedRoute",
    Mark.NO_EXIT_DECLARED: "noExitDeclared",
    Mark.EXIT_COST_UNKNOWN: "exitCostUnknown",
}
"""The ``classDef`` name each mark may add. Emphasis only -- see the module docstring."""

CLASS_DEFS: Final[tuple[tuple[str, str], ...]] = (
    (STYLE_CLASS[Mark.UNVERIFIED], "stroke-dasharray: 4 2"),
    (STYLE_CLASS[Mark.STALE], "stroke-dasharray: 1 3"),
    (STYLE_CLASS[Mark.SYNTHETIC], "stroke-width: 1px"),
    (STYLE_CLASS[Mark.CLOSED], "stroke-dasharray: 8 4"),
    (STYLE_CLASS[Mark.NO_EXIT_DECLARED], "stroke-width: 3px"),
    (STYLE_CLASS[Mark.EXIT_COST_UNKNOWN], "stroke-width: 3px"),
)
"""The style declarations, in a fixed order (FR-016), stated as line and stroke rather than
as colour.

Deliberately no ``fill`` and no colour: a colour is the one form of emphasis a reader may not
have -- a monochrome print, a dark theme, a viewer with its own palette -- and choosing one
would suggest the diagram means something different without it. It does not; the words carry
the meaning and these only draw the eye.

**All six are declared on every diagram, and a given diagram will not carry all six.** Mermaid
applies a class to a *node*; an edge's emphasis is its line style, so a mark that only ever
lands on an edge -- ``CLOSED`` -- gets its emphasis from the dotted arrow instead and its
``classDef`` goes unused. Emitting the whole vocabulary anyway keeps it one thing rather than
two, costs a reader nothing, and makes the point D4 is about: the styling is never where the
meaning is, so which classes happen to be in play cannot change what a diagram says.
"""

CLEAN: Final = "VERIFIED AND CURRENT"
"""What a figure says when no mark applies: cited, checked, and inside its kind's threshold."""

UNSOURCED: Final = "NO SOURCE CITED"
"""What a figure resting on ``provenance.EMPTY`` says.

Not :data:`CLEAN`, because a figure that cites nothing has not been verified -- claiming it
had would be exactly the laundering ``core.primitives.provenance`` was built to prevent. Not
:attr:`Mark.UNVERIFIED` either, because that mark means *a source exists and nobody checked
it*, and here there is no source to check.
"""

UNASSESSED: Final = "AGE NOT ASSESSED"
"""What a figure says when nothing aged its sources against a threshold.

The third state that is the absence of a mark, and it exists for exactly the reason
``core.primitives.staleness.UNASSESSED`` does: "everything was checked and nothing is stale"
and "nobody checked" must not be the same value, or the second one wears the first one's green
tick. A costed path reads staleness out of the verdict its result carries, and a source that
verdict never assessed cannot be called current.

The wording avoids the word *stale* on purpose: ``"STALENESS NOT ASSESSED"`` contains the
``STALE`` token as a substring, so ``token(Mark.STALE) in label`` -- the question every mark
assertion asks of a diagram -- would answer yes for a label saying the opposite.
"""

PREFIX: Final = "marks: "
"""How a marks segment begins, so a reader and a test can find it in a label."""

JOIN: Final = " + "

SYNTHETIC_CITATION_TOKEN: Final = "SYNTHETIC FIXTURE"
"""The phrase a declaration uses to say it is invented.

Read here and nowhere else. FR-014's assumption is explicit that the fixtures *already declare
themselves synthetic in their provenance fields* and that the diagram surfaces that
declaration rather than inventing a detection mechanism -- so this is the declaration's own
wording, used verbatim by every file in ``data/routes/``, by ``data/venues.toml`` and by the
test registries. A real, cited corridor does not say it, and its diagram is not marked.
"""


def token(mark: Mark) -> str:
    """What a mark says on the page."""
    return _TOKEN[mark]


def segment(applicable: Iterable[Mark], *, unsourced: bool = False, assessed: bool = True) -> str:
    """The marks field of a label: every mark that applies, or the named absence of one.

    The order is the enum's, never the caller's and never a ``set``'s, because byte-identity
    for identical input (FR-016) reaches all the way down to this. The two "no mark applies"
    states come first when they apply, since each frames everything after it: "there is no
    source" and "nobody aged the sources there are".

    ``assessed=False`` is what stops :data:`CLEAN` being a claim nobody made. A label may only
    say ``VERIFIED AND CURRENT`` when something actually aged its sources against a declared
    threshold. It is suppressed under ``unsourced``, where there was nothing to age: two
    tokens saying the same absence twice would read as two separate problems.
    """
    named = set(applicable)
    tokens = [UNSOURCED] if unsourced else []
    if not assessed and not unsourced:
        tokens.append(UNASSESSED)
    tokens.extend(_TOKEN[mark] for mark in Mark if mark in named)
    return PREFIX + JOIN.join(tokens or [CLEAN])


def style_class_for(applicable: Iterable[Mark]) -> str | None:
    """The one style class to apply, or ``None`` when nothing applies.

    One rather than several: Mermaid's inline ``:::`` takes a single class, and since styling
    is emphasis the choice of which mark to emphasise changes nothing a reader needs. Enum
    order decides, so the same marks always draw the same emphasis.
    """
    named = set(applicable)
    for mark in Mark:
        if mark in named:
            return STYLE_CLASS[mark]
    return None


def is_unsourced(provenance: Provenance) -> bool:
    """Whether a figure rests on no cited source at all. See :data:`UNSOURCED`."""
    return not provenance.sources


def is_synthetic(provenance: Provenance) -> bool:
    """Whether any source behind a figure declares itself a synthetic fixture.

    One synthetic input marks the whole figure, the same asymmetry
    ``provenance.is_unverified`` uses: a picture is only as real as its least real input, and
    marking only when *every* input is synthetic would let one invented premium hide behind a
    crowd of cited fee schedules.
    """
    return any(
        SYNTHETIC_CITATION_TOKEN.casefold() in ref.citation.casefold() for ref in provenance.sources
    )


def epistemic(provenance: Provenance, *, stale: bool) -> tuple[Mark, ...]:
    """The marks a figure's provenance and staleness verdict earn it, in enum order.

    The single place a record becomes marks, which is what makes SC-005 -- *100% of the
    elements depicting figures derived from an unverified input carry the mark* -- a property
    of one function rather than a habit at several call sites.

    ``stale`` is passed in rather than computed: staleness is ``as_of - retrieved_on`` against
    a *declared* per-kind threshold, and both the as-of date and the kind registry belong to
    the caller. On a registry graph the caller asks ``core.primitives.staleness`` under each
    leg's own declared kind; on a costed path it reads the verdict the result already carries.
    Either way the threshold is feature 002's, never one invented here (FR-013).
    """
    found = []
    if prov.is_unverified(provenance):
        found.append(Mark.UNVERIFIED)
    if stale:
        found.append(Mark.STALE)
    if is_synthetic(provenance):
        found.append(Mark.SYNTHETIC)
    return tuple(mark for mark in Mark if mark in set(found))
