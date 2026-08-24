#!/usr/bin/env python3
"""Verify every METHODOLOGY heading reference resolves, in the file and from its neighbours.

Written after a merge renumbered `docs/METHODOLOGY.md`'s sections twice and left three
kinds of wreckage: references pointing at sections that no longer existed, subheadings
still carrying their pre-merge numbers and colliding with another feature's, and two of
another feature's own self-references swept up by a blanket search-and-replace.

Renumbering is mechanical, which is exactly why it needs checking afterwards rather than
reading. Not wired into CI: it is a tool for whoever next renumbers a section, and it is
here so they do not have to write it again.

⚙ **It scans `specs/` too, since 2026-08-24, and that widening has a live example behind
it.** Merging 009 into 010 collided two `## 28` sections; 010's moved to §29, and a later
`git checkout` of one spec file quietly restored its `§28.6` -- which still *resolved*, to
009's "Two questions the law does not answer", and read plausibly. Review caught it and this
script could not, because it read three files while the stale reference lived in a fourth. A
reference that resolves to the wrong section is the failure this exists to make impossible,
so the scan follows the references rather than a directory list.

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
# Every markdown file that cites a METHODOLOGY section, wherever it lives. `docs/` and
# `data/` hold the prose a reader follows; `specs/` holds the task and design records, which
# is where a renumbering's last stale reference hides. The backtick around the filename is
# optional and so is the `.md`, because all four spellings are in the tree.
CITING = sorted(
    path
    for directory in ("docs", "data", "specs")
    for path in pathlib.Path(directory).rglob("*.md")
    if path != pathlib.Path("docs/METHODOLOGY.md")
)
badx = []
for other in CITING:
    for m in re.finditer(r"METHODOLOGY(?:\.md)?`? §(\d+(?:\.\d+)?)", other.read_text()):
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
