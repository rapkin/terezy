"""Read a module's *behaviour* without its prose, so a scan can be honest about what it saw.

Not a test module -- ``pytest`` collects only ``test_*.py``. It exists because three of this
feature's contract tests are greps over source, and a grep over source is only as trustworthy
as its treatment of documentation. Half the docstrings in this repository name the very thing
the scan is looking for: ``terezy.api.diagrams.graph``'s docstring explains at length that it
does **not** import ``core.routes.coverage``, and ``numbers.py``'s explains what ``:.2f``
means. Prose describing a rule is not a violation of it, so the scans strip prose first and
look at what is left.

Comments disappear on their own -- ``ast`` never records them. Docstrings are removed
explicitly, including the attribute docstrings that follow a field, which is why this is
broader than :func:`ast.get_docstring`. A string literal the code actually *uses* survives,
and ``tests/contract/test_diagram_one_number_rule.py`` proves both halves of that.

The same reading as ``tests/contract/test_data_only_extensibility.py``, which does this for
Principle II; kept here so the diagram suites share one implementation rather than three.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _is_prose(statement: ast.stmt) -> bool:
    """Whether a statement is a bare string expression -- a docstring, and never code."""
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def strip_prose(source: str) -> str:
    """Source with comments and docstrings removed, leaving only behaviour."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and any(isinstance(item, ast.stmt) for item in block):
                kept = [item for item in block if not _is_prose(item)]
                setattr(node, field, kept or [ast.Pass()])
    return ast.unparse(tree)


def executable_source(path: Path) -> str:
    """One module's behaviour, as text, ready to be searched."""
    return strip_prose(path.read_text(encoding="utf-8"))
