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
    """A scan over no passages passes for ever and protects nothing."""
    passages = _passages()
    files = {name for name, _ in passages}
    assert files == {"ua_fop_group_3.toml", "ua_personal_income.toml", "ua.toml"}
    assert len(passages) >= 20


def test_every_quoted_legal_passage_is_in_the_specification_that_read_it() -> None:
    spec = _normalised(SPEC.read_text(encoding="utf-8"))
    strays = sorted({(name, passage) for name, passage in _passages() if passage not in spec})
    assert not strays, (
        "these passages are quoted in curated tax data and appear nowhere in "
        f"specs/012-fop-group-3/spec.md: {strays}. Every legal value in these files was "
        "copied from that specification, which read the primary texts; one that is not "
        "there came from somewhere nobody reviewed."
    )


def test_the_scan_would_catch_an_invented_passage() -> None:
    """Falsifiability: the comparison is a real containment test, not a vacuous one."""
    spec = _normalised(SPEC.read_text(encoding="utf-8"))
    assert _normalised("5 відсотків доходу - у разі включення   податку**") in spec  # noqa: RUF001
    assert _normalised("ставка збору становить 47 відсотків") not in spec
