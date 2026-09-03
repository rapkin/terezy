"""Two declared values, no third, and nothing else that widens the set of addresses.

The set is read off the closed type rather than listed here, because a list in a test is a
second copy of the enum and would stay green when the enum grew (020 FR-027, SC-013). FR-030 is
asserted the same way: a scan over the guard modules, not a reviewer's sentence.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from terezy.api.http import serve
from terezy.api.http.bind import CONTEXT_VARIABLE, BindContext, ContextNotRecognised, context_of

MODULE_ROOT = Path(__file__).resolve().parents[2] / "src" / "terezy" / "api" / "http"

GUARD_MODULES = ("bind.py", "middleware.py", "serve.py", "__main__.py")

DECLARED_FLAGS = frozenset({"--host", "--port"})


def _environment_keys(tree: ast.AST) -> list[str]:
    """Every expression this module uses as an environment-variable key, as source text."""
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
            reads_environment = (
                node.func.attr == "get"
                and isinstance(base, ast.Attribute)
                and base.attr == "environ"
            ) or (node.func.attr == "getenv" and isinstance(base, ast.Name) and base.id == "os")
            if reads_environment and node.args:
                keys.append(ast.unparse(node.args[0]))
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
        ):
            keys.append(ast.unparse(node.slice))
    return keys


def _flags(tree: ast.AST) -> list[str]:
    """Every command-line option string the module declares."""
    return [
        argument.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        for argument in node.args
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    ]


def _tree(name: str) -> ast.AST:
    return ast.parse((MODULE_ROOT / name).read_text(encoding="utf-8"))


def test_the_context_type_has_exactly_two_members() -> None:
    assert len(BindContext) == 2
    assert {member.value for member in BindContext} == {
        "loopback",
        "container-published-to-loopback",
    }


def test_an_unset_variable_means_loopback() -> None:
    assert context_of(None) is BindContext.LOOPBACK


@pytest.mark.parametrize("member", list(BindContext))
def test_each_declared_value_parses_to_its_member(member: BindContext) -> None:
    assert context_of(member.value) is member


@pytest.mark.parametrize("typo", ["containr", "LOOPBACK", "container", "0.0.0.0", ""])
def test_an_unrecognised_value_refuses_naming_both_declared_values(typo: str) -> None:
    """Parsing into the closed type and defaulting on failure is the obvious implementation
    and it is a silent default for a malformed field: the person who typed it believed they
    had asked for something (FR-027)."""
    outcome = context_of(typo)

    assert isinstance(outcome, ContextNotRecognised)
    assert outcome.value == typo
    for member in BindContext:
        assert member.value in outcome.reason


def test_an_unrecognised_value_exits_non_zero_from_the_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(CONTEXT_VARIABLE, "containr")
    started: list[tuple[str, int]] = []

    code = serve.main(["--host", "127.0.0.1"], start=lambda a, p: started.append((a, p)))

    assert code != 0
    assert not started
    assert "containr" in capsys.readouterr().err


def test_the_only_environment_key_the_guard_reads_is_the_context() -> None:
    """FR-030 forbids a second input that lets a refused address through. An environment key
    is the cheapest such input, so the modules are scanned rather than reviewed."""
    read = {name: _environment_keys(_tree(name)) for name in GUARD_MODULES}

    assert read["serve.py"] == ["bind.CONTEXT_VARIABLE"]
    assert read["bind.py"] == []
    assert read["middleware.py"] == []
    assert read["__main__.py"] == []


def test_the_entry_point_declares_no_flag_beyond_the_address_it_checks() -> None:
    """*Widens*, not *changes*: taking an address and refusing most of them is the mechanism,
    so the check is on what else could be declared, not on the address flag itself."""
    assert set(_flags(_tree("serve.py"))) == DECLARED_FLAGS
    for name in GUARD_MODULES:
        if name != "serve.py":
            assert _flags(_tree(name)) == []


def test_the_scans_would_actually_catch_a_widening() -> None:
    """A scan that silently matches nothing passes forever. Prove both patterns fire."""
    widened = ast.parse(
        "import os\n"
        "anywhere = os.environ.get('TEREZY_BIND_ANYWHERE')\n"
        "also = os.getenv('TEREZY_ALLOW_LAN')\n"
        "third = os.environ['TEREZY_PUBLIC']\n"
        "parser.add_argument('--bind-anywhere')\n"
    )

    assert _environment_keys(widened) == [
        "'TEREZY_BIND_ANYWHERE'",
        "'TEREZY_ALLOW_LAN'",
        "'TEREZY_PUBLIC'",
    ]
    assert _flags(widened) == ["--bind-anywhere"]
