#!/usr/bin/env python3
"""Fail when a source tree's comment-and-docstring share rises above its recorded ceiling.

A ratchet, not a cap. Deleting prose is never required; adding prose faster than code is.
Raising a ceiling is a one-line edit here, visible in review, which is the point: the
trade becomes explicit instead of accumulating unnoticed.

Each ceiling is **the measured share plus a 0.25-point band**, and the band is part of the
contract rather than slack nobody removed. A ceiling pinned to the measurement exactly is no
longer a ratchet: it is a cap, and it fires on whoever next adds an honest paragraph. That
lands hardest on ``tests``, where a worked example is *required* to carry its arithmetic
checked in beside the assertion -- one new worked-example file would turn the gate red on an
author who never lowered anything. The band absorbs a normal change and still fails a tree
whose prose is outgrowing its code. Whoever re-measures tightens it, and re-measuring is the
act that holds ground.

Measured with ``tokenize`` for comments and ``ast`` for docstrings, so a string used as a
value is not counted as prose and a comment inside a string is not counted twice.
"""

import ast
import io
import pathlib
import sys
import tokenize
from typing import Final

# The share measured on 2026-08-30, plus the 0.25-point band the docstring describes.
# Measured: src/terezy 32.30, tests 25.73, scripts 26.67.
CEILING: Final[dict[str, float]] = {
    "src/terezy": 32.55,
    "tests": 25.98,
    "scripts": 26.92,
}


def _prose_lines(path: pathlib.Path) -> tuple[int, int]:
    """(prose lines, non-blank lines) in one module."""
    text = path.read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    marked: set[int] = set()

    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type is tokenize.COMMENT:
            marked.add(token.start[0])

    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        doc = node.body[0] if node.body else None
        if (
            isinstance(doc, ast.Expr)
            and isinstance(doc.value, ast.Constant)
            and isinstance(doc.value.value, str)
            and doc.end_lineno is not None
        ):
            marked.update(range(doc.lineno, doc.end_lineno + 1))

    source = text.splitlines()
    prose = sum(1 for n in marked if 1 <= n <= len(source) and source[n - 1].strip())
    return prose, len(lines)


def measure(tree: str) -> tuple[int, int, float]:
    prose = total = 0
    for path in sorted(pathlib.Path(tree).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        p, t = _prose_lines(path)
        prose += p
        total += t
    return prose, total, 100.0 * prose / total if total else 0.0


def main() -> int:
    failed = False
    for tree, ceiling in CEILING.items():
        prose, total, share = measure(tree)
        over = share > ceiling + 0.005
        failed |= over
        mark = "OVER" if over else "ok"
        print(  # noqa: T201
            f"{tree:14} {prose:6} prose / {total:6} lines = {share:6.2f}%"
            f"  ceiling {ceiling:6.2f}%  {mark}"
        )
    if failed:
        print(  # noqa: T201
            "\nA tree is above its ceiling. Cut prose that restates the code, claims "
            "something about another module, or narrates a change -- or raise the ceiling "
            "here and say in the commit message what the added prose prevents."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
