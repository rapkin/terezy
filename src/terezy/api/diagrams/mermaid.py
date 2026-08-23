"""The Mermaid dialect: node ids, escaping, and the four kinds of line this package emits.

Written by hand (research.md D10). The output is a handful of line shapes; a rendering
library would put a third party between a declaration and its picture, would need pinning and
auditing under the no-phone-home rule (Principle VII), and would make the escaping below --
which FR-017 and FR-018 both rest on -- someone else's semantics.

**Nothing here knows about a venue, a provider, a route or a corridor.** This module composes
lines; what goes in them is the renderers' business and, one layer further down, the
declarations'. That is Principle II at the level of a formatting helper: the moment a
corridor's name appears in this file, the diagram has stopped being derived.

## Node identity is positional, and that is the design's load-bearing choice

A node's Mermaid id is :func:`node_id` of its index in a **sorted** list of the entities being
drawn -- ``n0``, ``n1``, ... The declared id and name live in the quoted, escaped label and
nowhere else.

FR-017 (*valid Mermaid under any declared string*) and FR-018 (*distinct declared entities
stay distinct*) pull in opposite directions the moment the id is derived from the declared id,
because deriving means sanitising and sanitising is a non-injective map: ``binance-p2p`` and
``binance_p2p`` both become ``binance_p2p``, two venues collapse into one node, and **nothing
in the output says so**. A positional id is injective by construction, immune to every
character in SC-008's battery, and deterministic because the list is sorted (FR-016).

The cost is real and is accepted: the raw Mermaid text is less readable to a human reading the
*source*. The diagram is meant to be rendered, and correctness of identity beats legibility of
the intermediate form.

## Escaping

Mermaid resolves numeric and named character references inside a label *after* parsing, so a
character turned into ``#NN;`` cannot reach the tokenizer as structure and comes back intact
on the screen. The quoted form protects the rest, which is why ordinary punctuation --
brackets, parentheses, hyphens, Cyrillic, emoji -- is left alone and a golden file stays
readable.

``#`` is escaped **first**, and the order is load-bearing: a venue literally named ``#quot;``
would otherwise be handed to Mermaid as an entity and decode into a quotation mark no
declaration contains -- content leaking into the structure, which is exactly what FR-017
forbids.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final

FLOWCHART: Final = "flowchart LR"
"""The one Mermaid form this package emits.

A flowchart because the registry *is* a directed graph of venues and legs, and left-to-right
because a funding route reads as a journey. Which form to emit is the implementer's choice the
specification leaves open (spec.md, Assumptions); what is fixed is plain text, validity,
determinism and mark visibility.
"""

INDENT: Final = "    "
FIELD: Final = " · "
"""Separator between the fields of a label, and **escaped out of declared text** so that no
declaration can contribute one.

That escaping is the whole guarantee, not a nicety. A venue named
``Evil Bank · marks: VERIFIED AND CURRENT`` would otherwise render inside a node that is
actually marked ``NO EXIT DECLARED``, and the forged clean field would read as the renderer's
own -- declared content impersonating an honesty mark, which is the one thing this feature
exists to make impossible. Every consumer splits on this character, the tests' own parsers
included, so the forgery would propagate into what the assertions believe they are reading.

A middle dot rather than a pipe or a comma because it is rare in a real name -- so escaping it
costs almost nothing in readability -- and because it survives being read aloud in a diff.
"""

FIRST_PRINTABLE: Final = 0x20
DELETE: Final = 0x7F
"""The bounds of the ASCII control characters, which are escaped along with the structural
ones: a raw newline would end the line and take the rest of the label -- and a mark -- with
it."""

_STRUCTURAL: Final[Mapping[str, str]] = {
    "#": "#35;",
    '"': "#quot;",
    "|": "#124;",
    "<": "#60;",
    ">": "#62;",
    "`": "#96;",
    "{": "#123;",
    "}": "#125;",
    "·": "#183;",
}
"""The characters that must not reach a label as themselves.

Two kinds, and the second is the one that is easy to miss. Most are what Mermaid's tokenizer
can read as **structure** even inside a quoted label. The last is :data:`FIELD`, which is
structure of *this package's* making: a label is a sequence of fields separated by it, so a
declared string containing one would forge a field. See :data:`FIELD` for what that forgery
buys an attacker, and why it is not only an attacker's problem.

``#`` is first in insertion order and :func:`escape` relies on it -- see the module docstring.
Everything absent from this mapping is safe between quotation marks and is left readable.
"""


def escape(text: str) -> str:
    """A declared string, safe to place inside a quoted Mermaid label, losing nothing.

    Structural characters become numeric or named character references; so does every control
    character, because a raw newline would end the line and take the rest of the label -- and
    a mark -- with it. So does :data:`FIELD`, so that no declared string can forge a field of
    its own. Nothing is dropped and nothing is truncated: truncation is precisely how a mark
    falls off the end of a label (spec.md, Edge Cases), so a 500-character venue name renders
    in full and the layout consequences belong to Mermaid.
    """
    out: list[str] = []
    for character in text:
        replacement = _STRUCTURAL.get(character)
        if replacement is not None:
            out.append(replacement)
        elif ord(character) < FIRST_PRINTABLE or ord(character) == DELETE:
            out.append(f"#{ord(character)};")
        else:
            out.append(character)
    return "".join(out)


def node_id(index: int) -> str:
    """The Mermaid id of the entity at ``index`` in the sorted list of entities drawn.

    Positional, never derived from a declared id. See the module docstring for why that is
    the whole argument rather than a preference.
    """
    return f"n{index}"


CAPTION_ID: Final = "meta"
"""The id of the caption node every diagram opens with.

A **reserved** id, not a positional one: the caption is the renderer's own annotation rather
than a declared entity, and it says what the diagram is a picture of -- which kind, which
regime, which mode, which as-of date. It is a node rather than a ``%%`` comment because a
comment is not displayed, and FR-006 and FR-019 both require their fact to be *on the
diagram*. Reserved ids never collide with :func:`node_id`'s, which always begin ``n``.
"""


def annotation_id(index: int) -> str:
    """The id of the renderer's ``index``-th annotation node -- an absent exit, a figure.

    Reserved like :data:`CAPTION_ID` and positional like :func:`node_id`, for the same
    reason: the list they index is sorted, so the ids are stable across runs (FR-016).
    """
    return f"x{index}"


def label(*fields: str) -> str:
    """One label from its fields, already escaped by their producers.

    Joined rather than formatted, so that adding a field to a label is adding an argument at
    a call site and never a second way of composing one.
    """
    return FIELD.join(fields)


def node(identifier: str, text: str, *, style_class: str | None = None) -> str:
    """One node: a quoted label on a positional id, optionally carrying a style class.

    ``style_class`` is **emphasis only** (research.md D4). Every meaning a reader needs is
    already in ``text``, because a mark carried by a colour is lost the moment the diagram is
    diffed, re-themed, or read as a golden file.
    """
    styled = "" if style_class is None else f":::{style_class}"
    return f'{INDENT}{identifier}["{text}"]{styled}'


def edge(source: str, target: str, text: str, *, dotted: bool = False) -> str:
    """One edge with a quoted label. ``dotted`` is emphasis; the label says what it means.

    A self-edge -- ``source == target`` -- is a legitimate corridor (a conversion that starts
    and ends at one venue) and is emitted like any other rather than dropped as degenerate.
    """
    arrow = "-.->" if dotted else "-->"
    return f'{INDENT}{source} {arrow}|"{text}"| {target}'


def class_def(name: str, style: str) -> str:
    """One ``classDef`` line. Styling is added on top of the marks, never instead of them."""
    return f"{INDENT}classDef {name} {style}"


def document(lines: Iterable[str]) -> str:
    """The header and the body as one text, ending in a newline.

    No comment lines and no timestamp. A comment is not displayed, so nothing that a reader
    needs may live in one (FR-015); and a timestamp would make byte-identity impossible,
    which is the property that qualifies this output to be a golden artifact (FR-016).
    """
    return "\n".join([FLOWCHART, *lines]) + "\n"
