"""Architecture boundaries are executable, not conventional.

Compliance test for constitution Principle III (Pure Deterministic Core) and the
"Layering" clause under Architecture Constraints. Tracked as H4 in
``docs/REQUIRED_TESTS.md``.

The contracts themselves live in ``.importlinter`` so that a developer can run
``uv run lint-imports`` directly; this test makes the same contracts fail the test
suite, which is what makes them a gate rather than a linting suggestion.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPO_ROOT / "src" / "terezy" / "core"
DIAGRAMS_ROOT = REPO_ROOT / "src" / "terezy" / "api" / "diagrams"


def _imported_modules(path: Path) -> set[str]:
    """Every module name this file imports, dotted and absolute.

    Read from the AST rather than by regex so a name inside a docstring -- and half the
    docstrings in this repository name a module -- is not mistaken for an import.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.contract
def test_import_contracts_hold() -> None:
    """Every contract in .importlinter passes.

    Failure means a layer reached upward, or the core acquired an I/O, network,
    nondeterminism or framework dependency. Both are top-severity per the
    constitution's "Defect severity" clause.
    """
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Architecture boundary violation.\n\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )


@pytest.mark.contract
def test_importlinter_config_is_present() -> None:
    """The contract file exists and declares the layered contract.

    Guards against the boundaries being silently disabled by deleting the config
    rather than by amending the constitution.
    """
    config = REPO_ROOT / ".importlinter"
    assert config.is_file(), ".importlinter is missing; boundaries cannot be enforced"

    text = config.read_text(encoding="utf-8")
    for required in (
        "[importlinter:contract:layers]",
        "[importlinter:contract:core-is-pure]",
        "[importlinter:contract:core-independent-of-frameworks]",
        "[importlinter:contract:data-below-api]",
    ):
        assert required in text, f"required contract {required} was removed from .importlinter"


@pytest.mark.contract
def test_the_diagram_renderer_sits_above_the_core_and_below_the_cli() -> None:
    """``api.diagrams`` may read the core; nothing in the core may read it back.

    Feature 005 is the first substantial inhabitant of ``api``, and it is there for exactly
    one reason: the core may not format (Principle III, FR-020). The failure mode is not a
    dramatic one -- it is a small formatting helper added to ``core`` because a figure was
    awkward to render, and from there the core can be asked to round. ``lint-imports``
    catches the general case; this states the specific one, so the message names the
    feature rather than a layer.
    """
    assert DIAGRAMS_ROOT.is_dir(), "the diagram package is missing"

    for path in sorted(DIAGRAMS_ROOT.rglob("*.py")):
        reached_up = {name for name in _imported_modules(path) if name.startswith("terezy.cli")}
        assert not reached_up, f"{path.name} reaches up into the CLI: {sorted(reached_up)}"

    for path in sorted(CORE_ROOT.rglob("*.py")):
        reached_down = {name for name in _imported_modules(path) if name.startswith("terezy.api")}
        assert not reached_down, (
            f"core/{path.name} imports the renderer: {sorted(reached_down)}. The core neither "
            "formats nor renders -- if a figure is awkward to render, the fix belongs in "
            "terezy.api.diagrams"
        )


@pytest.mark.contract
def test_the_diagram_renderer_brought_no_rendering_dependency() -> None:
    """The Mermaid text is written by hand (research.md D10).

    A rendering or templating library would put a third party between a declaration and its
    picture, would need pinning and auditing under the no-phone-home rule (Principle VII),
    and would make the escaping that FR-017 and FR-018 rest on someone else's semantics.
    """
    forbidden = ("mermaid", "graphviz", "pydot", "jinja2", "mako", "chevron", "matplotlib")
    for path in sorted(DIAGRAMS_ROOT.rglob("*.py")):
        for imported in sorted(_imported_modules(path)):
            root = imported.split(".")[0]
            assert root not in forbidden, f"{path.name} imports {imported}"
