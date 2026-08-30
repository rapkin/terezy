#!/usr/bin/env python3
"""Fail when a source tree's comment-and-docstring share rises above its recorded ceiling.

A ratchet, not a cap. Deleting prose is never required; adding prose faster than code is.
Raising a ceiling is a one-line edit here, visible in review, which is the point: the
trade becomes explicit instead of accumulating unnoticed.

Measured with ``tokenize`` for comments and ``ast`` for docstrings, so a string used as a
value is not counted as prose and a comment inside a string is not counted twice.
"""

import ast
import io
import pathlib
import sys
import tokenize
from typing import Final

# The share measured on 2026-08-30, to the hundredth of a point. A tree may sit below its
# ceiling and may not rise above it.
CEILING: Final[dict[str, float]] = {
    "src/terezy": 32.37,
    "tests": 25.95,
    "scripts": 26.44,
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
