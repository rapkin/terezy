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
three directories. It now reads markdown and Python under `docs/`, `data/`,
`specs/`, `tests/`, `scripts/` and `src/`.

A reference that *resolves to the wrong section* is the failure this exists to make
impossible, and a partial scope is what lets one survive. So the scope's own limits, measured
2026-08-24 rather than assumed:

- **Under `data/`, only the markdown is read** -- the curated legal prose lives in TOML
  `source` and `note` strings, none of which cites a section today, which is why the suffix
  list is not widened. The tree is covered in name only. (The count of TOML files was
  written out here as 31 and was 37 four features later; a number nobody re-measures is
  worse than the shape of the gap, which does not change.)
- **This file is in the walk and matches nothing** -- zero, measured. Its own section
  references, the dead `§23.6` it quotes as history included, are never preceded by the word
  METHODOLOGY, so the pattern does not see them. It reads itself in the sense that costs
  nothing and catches nothing; do not mistake that for the check being self-checking.
- **Two shapes would be reported that are not defects**, neither present today: a task line
  planning a section not yet written (`specs/009-tax-depth/tasks.md` has exactly that shape
  and passes only because §28 now exists), and a reference quoted as history. Not worth a
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
# A directory list, not anything cleverer: the repository's top level minus what holds no
# prose. Measured 2026-08-24 -- every one of the 20 citing files in the tree is a `.md` or a
# `.py` under one of these six.
CITED_IN = ("docs", "data", "specs", "tests", "scripts", "src")

# Six spellings, counted in the tree on 2026-08-24 -- 29 references in 20 files:
#
#     `docs/METHODOLOGY.md` §   12     ``docs/METHODOLOGY.md`` §    1
#     ``METHODOLOGY`` §          6     METHODOLOGY §                6
#     `METHODOLOGY` §            2     docs/METHODOLOGY.md §        2
#
# So the backticks are **optional**, which is the part that earns the looseness: eight
# references carry none, and requiring at least one drops the count to 21. They come in ones
# and twos because markdown writes them singly and reStructuredText doubles them. Requiring
# the two sides to *match* would cost nothing today -- also 29 -- and is not imposed only
# because nothing would be gained by it.
REFERENCE = re.compile(r"`{0,2}METHODOLOGY(?:\.md)?`{0,2} §(\d+(?:\.\d+)?)")

# `docs/reference/` is read-only input material (`CLAUDE.md`), and it holds the predecessor's
# own `METHODOLOGY.md`. A reference added there would be checked against this document's
# numbering rather than that one's, and could not be fixed if it fired. It cites no section
# today; it is excluded so that stays true by construction rather than by luck.
SKIP = (pathlib.Path("docs/METHODOLOGY.md"), pathlib.Path("docs/reference"))
CITING = sorted(
    path
    for directory in CITED_IN
    for suffix in ("*.md", "*.py")
    for path in pathlib.Path(directory).rglob(suffix)
    if not any(path == skip or skip in path.parents for skip in SKIP)
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
