#!/usr/bin/env python3
"""Fail when prose lists the members of a set and the set has more members than that.

The constitution deletes a prose enumeration of things declared elsewhere unless a count
catches a named defect nothing cheaper catches. This is that count: two modules enumerated
the observation kinds as five and as six while the data declared eleven, and disagreed with
each other; nothing saw it.

Canonical sets come from the places that define them: `id` columns in `data/*.toml`,
`Enum` members, and `Literal[...]` alternatives. A prose run of three or more
comma-separated ``literals`` that lie wholly inside one canonical set is read as claiming
to be that set, and fails when it omits a member. A run introduced by a hedge -- "such
as", "for example" -- claims to be a sample instead, and is exempt.
"""

import ast
import io
import pathlib
import re
import sys
import tokenize
from typing import Final

LITERAL: Final = re.compile(r"``([a-z][a-z0-9_]{2,})``")
_TOKEN: Final = r"``[a-z][a-z0-9_]{2,}``"
RUN: Final = re.compile(_TOKEN + r"(?:\s*,\s*(?:and\s+|or\s+)?" + _TOKEN + r"){2,}")
HEDGE: Final = re.compile(r"\b(such as|for example|e\.g\.|including|among them|like|say)\b", re.I)
TREES: Final = ("src", "tests", "scripts")
MIN_MEMBERS: Final = 3


def canonical() -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {}
    for toml in sorted(pathlib.Path("data").rglob("*.toml")):
        ids = re.findall(r'^id\s*=\s*"([^"]+)"', toml.read_text(), re.M)
        if len(ids) >= MIN_MEMBERS:
            sets[f"{toml} id column"] = set(ids)
    for py in sorted(pathlib.Path("src").rglob("*.py")):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id.endswith("Enum") for b in node.bases
            ):
                members = {
                    s.value.value
                    for s in node.body
                    if isinstance(s, ast.Assign)
                    and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str)
                }
                if len(members) >= MIN_MEMBERS:
                    sets[f"{py}::{node.name}"] = members
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Literal"
            ):
                members = {
                    e.value
                    for e in ast.walk(node.slice)
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
                if len(members) >= MIN_MEMBERS:
                    sets.setdefault(f"{py}::Literal at line {node.lineno}", members)
    return sets


def prose(path: pathlib.Path) -> list[tuple[int, str]]:
    """(first line, joined text) for every docstring and own-line comment block."""
    raw = path.read_bytes()
    lines = raw.decode().splitlines()
    label: list[str | None] = [None] * (len(lines) + 1)
    try:
        tree = ast.parse(raw.decode())
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            seq = getattr(node, field, None)
            if not isinstance(seq, list):
                continue
            for stmt in seq:
                if (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                    and stmt.end_lineno is not None
                ):
                    for n in range(stmt.lineno, min(stmt.end_lineno, len(lines)) + 1):
                        label[n] = "doc"
    with io.BytesIO(raw) as handle:
        for token in tokenize.tokenize(handle.readline):
            n = token.start[0]
            if (
                token.type is tokenize.COMMENT
                and label[n] is None
                and not lines[n - 1][: token.start[1]].strip()
            ):
                label[n] = "comment"
    blocks: list[tuple[int, str]] = []
    n = 1
    while n <= len(lines):
        if label[n] is None:
            n += 1
            continue
        end = n
        while end + 1 <= len(lines) and label[end + 1] == label[n]:
            end += 1
        text = " ".join(lines[i - 1].strip().lstrip("#").strip() for i in range(n, end + 1))
        blocks.append((n, text))
        n = end + 1
    return blocks


def main() -> int:
    sets = canonical()
    stale: list[tuple[str, str, int, list[str]]] = []
    for tree in TREES:
        for path in sorted(pathlib.Path(tree).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for line, text in prose(path):
                run = RUN.search(text)
                if run is None or HEDGE.search(text):
                    continue
                listed = set(LITERAL.findall(run.group(0)))
                for name, members in sets.items():
                    missing = members - listed
                    if listed <= members and len(listed) >= MIN_MEMBERS and missing:
                        stale.append((f"{path}:{line}", name, len(listed), sorted(missing)))
    print(f"canonical sets   : {len(sets)}")  # noqa: T201
    print(f"stale in prose   : {len(stale) or 'none'}")  # noqa: T201
    for where, name, listed, missing in stale:
        print(f"\n  {where}")  # noqa: T201
        print(f"      lists {listed} of {len(missing) + listed} in {name}")  # noqa: T201
        print(f"      omits {', '.join(missing)}")  # noqa: T201
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
