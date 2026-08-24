#!/usr/bin/env python3
"""Verify every METHODOLOGY heading reference resolves, in the file and from its neighbours.

Written after a merge renumbered `docs/METHODOLOGY.md`'s sections twice and left three
kinds of wreckage: references pointing at sections that no longer existed, subheadings
still carrying their pre-merge numbers and colliding with another feature's, and two of
another feature's own self-references swept up by a blanket search-and-replace.

Renumbering is mechanical, which is exactly why it needs checking afterwards rather than
reading. Not wired into CI: it is a tool for whoever next renumbers a section, and it is
here so they do not have to write it again.

⚙ **The cross-file scan reads every tree that cites a section, and it got there twice.**
Merging 009 into 010 collided two `## 28` sections; 010's moved to §29, and a `git checkout`
of one spec file quietly restored its `§28.6` -- which still *resolved*, to 009's "Two
questions the law does not answer", and read plausibly. Widening to `specs/` caught that and
a `§23.6` in 007 that had dangled since 007's own section moved. The widened scan then still
missed `tests/unit/test_cpi_staleness.py`, which carried the **same sentence** as the 007 line
and the same dead `§23.6`: one copy fixed, one live, because the scan stopped at markdown in
three directories. It now reads markdown and Python under `docs/`, `data/`, `specs/`,
`tests/`, `scripts/` and `src/` -- including this file, which the previous scope left as a
check that could not see itself.

A reference that *resolves to the wrong section* is the failure this exists to make
impossible, and a partial scope is what lets one survive. Two shapes it would report as
unresolved that are not defects, neither of them present today: a task line planning a section
that has not been written yet (`specs/009-tax-depth/tasks.md` has exactly that shape and
passes only because §28 now exists), and a reference quoted as history. Neither is worth a
suppression mechanism until one fires.

`SIMULATOR_SPEC.md`'s own section numbers appear in this prose too and collide numerically
with METHODOLOGY's, so they are listed rather than guessed at.
"""

import pathlib
import re
import sys

SPEC_REFS = {"4.3", "4.7", "4.8"}
text = pathlib.Path("docs/METHODOLOGY.md").read_text()
sections = {m.group(1) for m in re.finditer(r"^## (\d+)\.", text, re.M)}
subs = {m.group(1) for m in re.finditer(r"^### (\d+\.\d+)", text, re.M)}
known = sections | subs | SPEC_REFS
bad = sorted({m.group(1) for m in re.finditer(r"§(\d+(?:\.\d+)?)", text)} - known)
# Every file that cites a METHODOLOGY section: prose in `docs/` and `data/`, design and task
# records in `specs/`, and docstrings and comments in `tests/`, `scripts/` and `src/`. A
# directory list rather than anything cleverer -- it is the repository's own top level, minus
# what holds no prose.
#
# The `.md` and the backticks are all optional and the backticks come in ones and twos,
# because markdown writes `METHODOLOGY.md` and reStructuredText writes ``METHODOLOGY``; every
# one of those spellings is in the tree, which is why the pattern is loose rather than tidy.
CITED_IN = ("docs", "data", "specs", "tests", "scripts", "src")
REFERENCE = re.compile(r"`{0,2}METHODOLOGY(?:\.md)?`{0,2} §(\d+(?:\.\d+)?)")
CITING = sorted(
    path
    for directory in CITED_IN
    for suffix in ("*.md", "*.py")
    for path in pathlib.Path(directory).rglob(suffix)
    if path != pathlib.Path("docs/METHODOLOGY.md")
)
badx = []
for other in CITING:
    for m in REFERENCE.finditer(other.read_text()):
        if m.group(1) not in known:
            badx.append((str(other), m.group(1)))
dupes = [h for h in sorted(subs) if len(re.findall(rf"^### {re.escape(h)} ", text, re.M)) > 1]
dupsec = [h for h in sorted(sections, key=int) if len(re.findall(rf"^## {h}\. ", text, re.M)) > 1]
print(  # noqa: T201
    "unresolved in METHODOLOGY :", bad or "none"
)
print(  # noqa: T201
    f"unresolved cross-file     : {badx or 'none'}  (scanned {len(CITING)} file(s))"
)
print(  # noqa: T201
    "duplicate ## numbers      :", dupsec or "none"
)
print(  # noqa: T201
    "duplicate ### numbers     :", dupes or "none"
)
sys.exit(1 if (bad or badx or dupsec or dupes) else 0)
