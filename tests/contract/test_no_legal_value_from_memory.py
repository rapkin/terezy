"""Every legal passage this feature's data quotes appears in the specification that read it.

Constitution Principle I: *no legal or tax value may originate from an implementer's or an
agent's memory — only from a cited source, entered as data.* That is the rule this project
is most exposed on, and until now it has been enforced by review.

For feature 012 it is mechanically checkable, because of how the feature was built: the
owner ended legal retrieval before implementation began, so **every** value in
``data/tax/schemes/`` and ``data/tax/destinations/`` was copied from
``specs/012-fop-group-3/spec.md``, which had already been through nine review rounds against
the primary texts. So a Ukrainian-language passage in those files that is **not** in that
specification came from somewhere nobody reviewed — which is exactly the defect, and the one
shape of it a test can see.

## What this does and does not prove

It proves the transcription. It does not, and cannot, prove that the specification read the
statute correctly — that is what the owner verification tasks are for, and what an empty
``verified_on`` says on every value here.

⚙ **The coupling is deliberate and it is narrow.** A data file is normally independent of any
one specification. These two are not: their values have a single provenance and it is that
document. When the owner verifies a value, the specification's source table moves with it,
which is the direction the coupling is meant to work in — and if a later feature changes a
rate here without changing the record of where it came from, this is what says so.

## Four holes in this scan, measured rather than assumed

Recorded because a check whose reach is not written down is one a reader over-trusts. None is
fixed here: each would be a larger piece of work than the feature this scan was written for,
and knowing where a guard stops is worth more than a guard that quietly stops somewhere else.

1. **Attribution is invisible.** The scan reads quoted spans anywhere in a file and never
   which ``source`` or which provision they sit under, so a passage moved under the **wrong
   citation** passes. That is the defect this feature's own history is about. It is covered
   for exactly one entry, by
   ``test_crediting_destination_loading.py::test_the_levy_entry_cites_each_law_for_the_half_it_supplies``,
   which partitions the citation at its own labels — and that is the pattern the other
   entries lack. ⚙ **The tool for closing it already exists**:
   ``test_declaration_loading.py::_provisions_behind`` extracts the dotted provision numbers a
   figure's citations name, precisely so a citation naming 165.1.52 cannot satisfy a check
   looking for 165.1.2. Pointing every entry's quotations at the provisions its own citation
   names is that function over these files; it is deliberately not built here.
2. **Containment is substring containment.** A truncated span of a longer passage passes
   under any provision: ``«від доходу, визначеного згідно із статтею 292»`` is 45 characters,
   is in the specification, and is quotable anywhere.
3. **Guillemets are the only trigger, and that one is checked** rather than claimed: a file
   quoting a provision in straight quotes would be invisible to the scan, so
   :func:`test_no_provision_is_quoted_in_straight_quotes_outside_guillemets` asserts that none
   does. It was a stated gap until 2026-08-30 and is a few lines over data the scan already
   reads, which is the trade this repository asks for wherever a claim can be made
   mechanical.
4. **The glob is directory-wide, not this feature's own files.** A scheme or destination file
   added by a later feature therefore lands in the scan and must have its quotations in *this*
   specification, which is almost certainly not what its author intended. The failure below
   says so in as many words rather than leaving them to work it out.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = REPO_ROOT / "specs" / "012-fop-group-3" / "spec.md"
DECLARED = (
    REPO_ROOT / "data" / "tax" / "schemes",
    REPO_ROOT / "data" / "tax" / "destinations",
)

QUOTED = re.compile(r"«([^»]+)»")
"""Ukrainian quotation marks, which is how every quoted provision in these files is written.

Straight quotes are not matched, and deliberately: they hold TOML keys, English prose and
URLs, none of which is a quoted legal passage.
"""

SHORT = 12
"""Passages shorter than this are skipped: «5 %» and «ФОП» carry no proposition, and a
containment test over them would pass on any document mentioning either."""

SUBSTANTIAL = 80
"""What counts as a quoted **provision** rather than a quoted word.

Not a second filter -- every passage above :data:`SHORT` is checked. This is the length the
count below measures, so the scan's strength is a stated number instead of an impression, and
the floor is set near what is actually there (63 passages, 37 of them substantial, measured
2026-08-30) rather than far enough below it that most of them could vanish first.
"""


def _normalised(text: str) -> str:
    """Whitespace collapsed, TOML escapes undone, markdown emphasis stripped.

    The two files write the same sentence differently -- one wraps at eighty columns and
    marks emphasis, the other escapes an inner quote for the parser -- and neither difference
    is about the passage.
    """
    unescaped = text.replace('\\"', '"').replace("**", "")
    unquoted = re.sub(r"^\s*>\s?", "", unescaped, flags=re.M)
    return re.sub(r"\s+", " ", unquoted).strip()


def _passages() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for directory in DECLARED:
        for path in sorted(directory.glob("*.toml")):
            text = path.read_text(encoding="utf-8")
            found.extend(
                (path.name, _normalised(match))
                for match in QUOTED.findall(text)
                if len(_normalised(match)) >= SHORT
            )
    return found


def test_the_scan_reaches_both_declaration_directories_and_finds_passages() -> None:
    """A scan over no passages passes for ever and protects nothing.

    The **substantial** count is asserted beside the total, because a containment test over
    ``«неправомірний»`` establishes that one word is somewhere in a long document and nothing
    more. What carries the check is the long passages -- the quoted provisions -- and this
    says how many of those the scan is actually holding.
    """
    passages = _passages()
    files = {name for name, _ in passages}
    assert files == {"ua_fop_group_3.toml", "ua_personal_income.toml", "ua.toml"}, (
        f"the scan found quoted passages in {sorted(files)}. It reads whole directories, not "
        "this feature's three files — so a scheme or destination file added by a LATER "
        "feature lands in it, and its quotations would have to be in feature 012's "
        "specification to pass, which is almost certainly not what its author meant. Scope "
        "the scan to that feature's own record, or widen this set deliberately."
    )
    assert len(passages) >= 60
    substantial = [passage for _, passage in passages if len(passage) >= SUBSTANTIAL]
    assert len(substantial) >= 35


def test_every_quoted_legal_passage_is_in_the_specification_that_read_it() -> None:
    spec = _normalised(SPEC.read_text(encoding="utf-8"))
    strays = sorted({(name, passage) for name, passage in _passages() if passage not in spec})
    assert not strays, (
        "these passages are quoted in curated tax data and appear nowhere in "
        f"specs/012-fop-group-3/spec.md: {strays}. Every legal value in these files was "
        "copied from that specification, which read the primary texts; one that is not "
        "there came from somewhere nobody reviewed. If this is a later feature's file, the "
        "scan's scope is the problem rather than the passage — see hole 4 above."
    )


def test_the_scan_would_catch_an_invented_passage() -> None:
    """Falsifiability: the comparison is a real containment test, not a vacuous one."""
    spec = _normalised(SPEC.read_text(encoding="utf-8"))
    assert _normalised("5 відсотків доходу - у разі включення   податку**") in spec  # noqa: RUF001
    assert _normalised("ставка збору становить 47 відсотків") not in spec


STRAIGHT_QUOTED = re.compile(r'\\"([^"]{20,})\\"')
"""A span in TOML's own escaped straight quotes, long enough to be a provision rather than a
key. This is the shape a quoted passage takes if somebody does not reach for guillemets."""


def test_no_provision_is_quoted_in_straight_quotes_outside_guillemets() -> None:
    """Hole 3, closed: the scan's one trigger is checked rather than claimed.

    A provision quoted in straight quotes is invisible to the scan above, and *every quoted
    provision in these files is written in guillemets* is a claim about the files that nothing
    else would catch going false. Guillemet spans -- inside which escaped straight quotes are
    ordinary, because a statute quotes the words it replaces -- are removed first, and what is
    left is searched for an escaped-quote span carrying Cyrillic.
    """
    strays: list[tuple[str, str]] = []
    for directory in DECLARED:
        for path in sorted(directory.glob("*.toml")):
            outside = QUOTED.sub(" ", path.read_text(encoding="utf-8"))
            strays.extend(
                (path.name, span[:60])
                for span in STRAIGHT_QUOTED.findall(outside)
                if any("\u0400" <= character <= "\u04ff" for character in span)
            )
    assert not strays, (
        "these are passages quoted in straight quotes, outside the guillemets the scan above "
        f"reads: {strays}. Quote a provision in « » or the check that it came from the "
        "specification does not reach it."
    )


def test_that_check_would_see_a_provision_quoted_the_other_way() -> None:
    """Falsifiability, and the reason the guillemet strip comes first.

    Inside a quoted provision an escaped straight quote is ordinary — a statute quotes the
    words it replaces — so a scan that did not strip guillemet spans would report every one of
    those and never fire on the case it is for.
    """
    inside = QUOTED.sub(" ", 'x = "«… слова \\"з 1 жовтня 2024 року\\" замінити …»"')
    assert not STRAIGHT_QUOTED.findall(inside)
    outside = QUOTED.sub(" ", 'note = "the levy runs \\"по 31 грудня року, у якому\\" and stops"')  # noqa: RUF001
    assert STRAIGHT_QUOTED.findall(outside)
