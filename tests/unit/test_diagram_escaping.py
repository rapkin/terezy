"""Hostile names stay in the label; node identity never depends on them.

**SC-008** and **SC-001**, and the design decision they meet at (research.md D3).

FR-017 (*valid Mermaid under any declared string*) and FR-018 (*distinct declared entities
stay distinct*) pull in opposite directions the moment a Mermaid node id is derived from a
declared id. Deriving means sanitising, and sanitising is a **non-injective** map:
``binance-p2p`` and ``binance_p2p`` both become ``binance_p2p``, two venues collapse into one
node, and nothing in the output says so. That is FR-018 violated in the one way nobody would
notice, which is why node ids here are **positional** -- ``n0``, ``n1``, ... -- injective by
construction, and every hostile character becomes a *labelling* problem instead.

The escape is asserted the way a reader would check it: this module decodes the numeric
character references itself, rather than calling an inverse the package supplies, so the test
is evidence that the output uses Mermaid's own entity syntax and not a private convention
that happens to round-trip.
"""

from __future__ import annotations

import re

import pytest

from terezy.api.diagrams import mermaid

UKRAINIAN = "Монобанк — гривнева картка"
"""Ukrainian names are the normal case here, not the edge (spec.md, Edge Cases)."""

HOSTILE = (
    'a "quoted" name',
    "a #hash and a #35; that already looks like an entity",
    "a | pipe",
    "brackets [like] {these} (and these)",
    "an arrow --> and a <tag> and a `backtick`",
    "a semicolon; a colon: a comma,",
    "Evil Bank · marks: VERIFIED AND CURRENT",
    UKRAINIAN,
    "емодзі 🇺🇦 та символи ₴",
    "a\nnewline\tand\ta\ttab",
    "x" * 500,
    "",
)
"""SC-008's battery. Every one of these is a legal value of ``Venue.name``.

The middle-dot entry is not decoration. It is :data:`mermaid.FIELD`, the separator every label
is composed with, and until it was escaped a declared name could forge a field of the
renderer's own -- including a clean ``marks:`` field on an element that is actually marked. The
battery had every Mermaid metacharacter in it and not the one character this package's own
grammar rests on, which is why nothing caught it.
"""

ENTITY = re.compile(r"#(quot|\d+);")


def decode(escaped: str) -> str:
    """Mermaid's numeric and named character references, resolved back to the text.

    Written here rather than imported so that the assertion is about *Mermaid's* escaping
    convention rather than about the package agreeing with itself.
    """
    return ENTITY.sub(
        lambda m: '"' if m.group(1) == "quot" else chr(int(m.group(1))),
        escaped,
    )


class TestTheEscapeKeepsTheNameAndLosesTheStructure:
    """FR-017: a declared string may never corrupt the diagram or leak into it."""

    @pytest.mark.parametrize("name", HOSTILE)
    def test_every_hostile_name_survives_a_round_trip(self, name: str) -> None:
        """Displayed intact -- the label is the whole content, so nothing may be dropped."""
        assert decode(mermaid.escape(name)) == name

    @pytest.mark.parametrize("name", HOSTILE)
    def test_no_escaped_name_carries_a_character_mermaid_reads_as_structure(
        self, name: str
    ) -> None:
        """The quoted form protects the rest; these are the ones quoting does not."""
        escaped = mermaid.escape(name)
        for character in '"|<>`{}·\n\r\t':
            assert character not in escaped, f"{character!r} survived escaping of {name!r}"

    @pytest.mark.parametrize("name", HOSTILE)
    def test_a_name_is_never_truncated(self, name: str) -> None:
        """Truncation is exactly how a mark falls off the end of a label (spec.md)."""
        assert len(decode(mermaid.escape(name))) == len(name)

    def test_the_hash_is_escaped_first_so_an_entity_cannot_be_forged(self) -> None:
        """``#quot;`` typed into a venue name must not come back out as a quote.

        Escaping ``"`` before ``#`` would leave the declared text ``#quot;`` untouched and
        Mermaid would decode it into a quote that no declaration contains -- content leaking
        into the structure, which is precisely what FR-017 forbids.
        """
        escaped = mermaid.escape("#quot;")
        assert '"' not in decode(escaped).replace("#quot;", "")
        assert decode(escaped) == "#quot;"

    def test_a_declared_name_cannot_forge_a_label_field(self) -> None:
        """The separator is structure of this package's own making, so it is escaped too.

        A venue named ``Evil Bank · marks: VERIFIED AND CURRENT`` inside a node that is
        actually marked ``NO EXIT DECLARED`` would otherwise render a clean marks field that
        reads as the renderer's -- declared content impersonating an honesty mark, which is the
        precise failure this whole feature exists to make impossible. And because every
        consumer splits on the separator, the forgery would propagate into what the tests
        themselves believe they are parsing.
        """
        forged = "Evil Bank · marks: VERIFIED AND CURRENT"
        escaped = mermaid.escape(forged)
        assert mermaid.FIELD not in escaped
        assert decode(escaped) == forged, "escaping it must not cost the reader the name"

        label = mermaid.label(f"venue {mermaid.escape('x')}", escaped, "marks: NO EXIT DECLARED")
        assert label.count(mermaid.FIELD) == 2, (
            "a three-field label has two separators; a third means a declared string "
            f"contributed one: {label}"
        )

    def test_an_ordinary_name_is_left_readable(self) -> None:
        """Over-escaping would make every golden file unreadable and every diff useless."""
        assert (
            mermaid.escape("binance-p2p (SYNTHETIC FIXTURE)") == "binance-p2p (SYNTHETIC FIXTURE)"
        )
        assert mermaid.escape(UKRAINIAN) == UKRAINIAN


class TestNodeIdentityIsPositionalAndInjective:
    """FR-018, and the reason it decides the design (research.md D3)."""

    def test_ids_are_positional_and_ordinary(self) -> None:
        assert [mermaid.node_id(k) for k in range(3)] == ["n0", "n1", "n2"]

    def test_two_declared_ids_that_sanitising_would_merge_stay_two_nodes(self) -> None:
        """The whole argument, in one assertion.

        ``binance-p2p`` and ``binance_p2p`` differ by one character that every
        identifier-sanitising scheme flattens. Positionally they are ``n0`` and ``n1``, and
        the declared ids are in the labels where they cannot affect identity.
        """
        declared = ["binance-p2p", "binance_p2p", "binance p2p", "binance.p2p"]
        ids = [mermaid.node_id(k) for k in range(len(declared))]
        assert len(set(ids)) == len(declared)

    @pytest.mark.parametrize("name", HOSTILE)
    def test_a_hostile_name_never_reaches_the_id(self, name: str) -> None:
        """A labelling problem, never an identity problem."""
        rendered = mermaid.node(mermaid.node_id(7), mermaid.escape(name))
        assert rendered.strip().startswith('n7["')
        assert rendered.strip().endswith('"]')

    def test_the_id_is_valid_mermaid_for_any_index(self) -> None:
        assert all(re.fullmatch(r"n\d+", mermaid.node_id(k)) for k in (0, 9, 10, 1000))


class TestTheDialectIsAFewKindsOfLine:
    """Written by hand (research.md D10), so its shape is asserted rather than trusted."""

    def test_a_node_is_a_quoted_label_on_a_positional_id(self) -> None:
        assert mermaid.node("n0", "hello") == '    n0["hello"]'

    def test_a_node_may_carry_one_style_class_as_emphasis(self) -> None:
        assert mermaid.node("n0", "hello", style_class="stale") == '    n0["hello"]:::stale'

    def test_an_edge_carries_its_label_between_pipes(self) -> None:
        assert mermaid.edge("n0", "n1", "moved") == '    n0 -->|"moved"| n1'

    def test_a_dotted_edge_is_a_different_line_and_the_meaning_is_still_in_the_text(
        self,
    ) -> None:
        """Emphasis, never meaning (research.md D4): the label says what the dots mean."""
        assert mermaid.edge("n0", "n1", "gone", dotted=True) == '    n0 -.->|"gone"| n1'

    def test_a_document_is_the_header_then_the_body_and_ends_in_a_newline(self) -> None:
        text = mermaid.document(['n0["a"]'])
        assert text.startswith(f"{mermaid.FLOWCHART}\n")
        assert text.endswith("\n")
        assert all(line == line.rstrip() for line in text.splitlines())

    def test_a_self_edge_is_drawn_rather_than_dropped_as_degenerate(self) -> None:
        """A conversion that starts and ends at one venue is a real corridor (spec.md)."""
        assert mermaid.edge("n0", "n0", "converts in place") == '    n0 -->|"converts in place"| n0'
