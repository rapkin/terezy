"""Architecture boundaries are executable, not conventional.

Compliance test for constitution Principle III (Pure Deterministic Core) and the
"Layering" clause under Architecture Constraints. Tracked as H4 in
``docs/REQUIRED_TESTS.md``.

The contracts themselves live in ``.importlinter`` so that a developer can run
``uv run lint-imports`` directly; this test makes the same contracts fail the test
suite, which is what makes them a gate rather than a linting suggestion.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


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
