"""The data root is decided at startup, and an absent one is refused there rather than served.

An absent root is not a malformed declaration, so 020 FR-016's permission to answer a malformed
declaration with an error status does not reach it: before this, the root defaulted to ``data``
relative to the process's own directory, so ``python -m terezy.api.http`` started from anywhere
but the repository root answered 500 to *every* read, and said so once per request instead of
once at boot. The client half is asserted below rather than described: located the same way, it
left ``/`` answering a JSON 404 beside those 500s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from terezy.api.http import bind, roots, serve, service
from terezy.data.declarations import resolver
from tests.data_roots import SHIPPED

if TYPE_CHECKING:
    from pathlib import Path


def _run(
    data_root: Path, *, marker_root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, list[tuple[str, int]]]:
    """The entry point with the environment it actually reads, and no socket to open.

    ``marker_root`` is the filesystem root the container claim is checked against, which is a
    different question from where declarations are read; both are injected so the whole entry
    point is decidable without a container.
    """
    started: list[tuple[str, int]] = []
    monkeypatch.setenv(roots.DATA_ROOT_VARIABLE, str(data_root))
    monkeypatch.delenv(bind.CONTEXT_VARIABLE, raising=False)
    code = serve.main([], root=marker_root, start=lambda a, p: started.append((a, p)))
    return code, started


def test_a_root_without_the_declared_venues_refuses_before_binding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, started = _run(tmp_path, marker_root=tmp_path, monkeypatch=monkeypatch)

    assert code != 0
    assert not started, "the server was started over a data root that holds no declarations"
    refusal = capsys.readouterr().err
    assert str(tmp_path) in refusal, "the refusal must name the path it resolved"
    assert roots.DATA_ROOT_VARIABLE in refusal, "the refusal must name how to set the root"


def test_the_shipped_root_starts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal above would pass vacuously if nothing ever started."""
    code, started = _run(SHIPPED, marker_root=tmp_path, monkeypatch=monkeypatch)

    assert code == 0
    assert started == [(serve.DEFAULT_HOST, serve.DEFAULT_PORT)]


def test_the_default_root_does_not_depend_on_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect this file exists for: the default used to be ``Path("data")``."""
    monkeypatch.chdir(tmp_path)

    resolved = roots.data_root_in_force(None, packaged=roots.packaged_default())

    assert isinstance(resolved, roots.DataRootFound)
    assert (resolved.path / resolver.VENUES_FILE).is_file()


def test_the_built_client_is_found_from_the_same_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same defect at ``/``: a client looked for relative to the cwd is a page that is there
    from one directory and a JSON refusal from another."""
    monkeypatch.delenv(service.CLIENT_VARIABLE, raising=False)
    monkeypatch.chdir(tmp_path)

    located = service.client_root()

    assert located is not None
    assert located.is_absolute()
    assert located.parent.parent == SHIPPED.parent


def test_a_root_the_variable_names_and_that_does_not_exist_is_named(tmp_path: Path) -> None:
    absent = tmp_path / "nowhere"

    resolved = roots.data_root_in_force(str(absent), packaged=roots.packaged_default())

    assert isinstance(resolved, roots.DataRootMissing)
    assert str(absent) in resolved.reason
    assert resolver.VENUES_FILE in resolved.reason


def test_an_installation_outside_a_checkout_has_no_default() -> None:
    """With no packaged checkout to fall back on there is no root to guess at, and guessing is
    what produced a 500 per request instead of a refusal at boot."""
    resolved = roots.data_root_in_force(None, packaged=None)

    assert isinstance(resolved, roots.DataRootMissing)
    assert roots.DATA_ROOT_VARIABLE in resolved.reason
