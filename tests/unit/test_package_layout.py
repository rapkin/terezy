"""Foundation smoke test: the package installs and every layer is importable.

This is the cheapest possible proof that packaging, the src layout and the layer
skeleton all agree with each other. It exists so a broken ``pyproject.toml`` or a
missing ``__init__.py`` fails here rather than three steps later inside a feature.
"""

from __future__ import annotations

import importlib

import pytest

import terezy

LAYER_MODULES = (
    "terezy.core",
    "terezy.core.instruments",
    "terezy.core.routes",
    "terezy.core.ledger",
    "terezy.core.tax",
    "terezy.core.metrics",
    "terezy.core.analysis",
    "terezy.core.decision",
    "terezy.data",
    "terezy.data.providers",
    "terezy.data.snapshot",
    "terezy.api",
    "terezy.cli",
)


def test_version_is_exposed() -> None:
    assert terezy.__version__


@pytest.mark.parametrize("name", LAYER_MODULES)
def test_layer_is_importable(name: str) -> None:
    assert importlib.import_module(name) is not None


@pytest.mark.parametrize("name", LAYER_MODULES)
def test_layer_documents_its_charter(name: str) -> None:
    """Every layer carries a docstring stating what it is and is not allowed to do.

    The architecture is only enforceable if it is written down where the code lives,
    not only in the constitution.
    """
    module = importlib.import_module(name)
    assert module.__doc__, f"{name} has no docstring stating its charter"
