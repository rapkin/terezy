"""The second context value is a claim about where the process is running, and it is checked.

Without the check the variable is exactly the off-switch FR-030 forbids: inside a container the
bind address *is* ``0.0.0.0``, so one environment variable on a laptop would publish one
person's finances to the LAN with no container anywhere near it (020 FR-027a, SC-012a).

What the check buys is that the wrong thing stops being the easy thing. A marker can be
created by someone who wants to, and FR-027b requires that to be said rather than dressed up.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from terezy.api.http import bind, serve, service
from terezy.api.http.bind import (
    CGROUP_PATH,
    CONTEXT_VARIABLE,
    DOCKER_MARKER,
    BindContext,
    BindPermitted,
    BindRefused,
    check_bind,
    container_marker,
)

CONTAINER = BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK


def _cgroup(root: Path, text: str) -> None:
    path = root.joinpath(*CGROUP_PATH.strip("/").split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_bare_filesystem_carries_no_marker(tmp_path: Path) -> None:
    assert container_marker(tmp_path) is None


def test_the_docker_marker_file_is_found(tmp_path: Path) -> None:
    (tmp_path / ".dockerenv").touch()

    assert container_marker(tmp_path) == DOCKER_MARKER


@pytest.mark.parametrize(
    "line",
    [
        "0::/docker/3fa1b2c3\n",
        "12:pids:/kubepods/burstable/pod1234\n",
        "0::/machine.slice/libpod-abc.scope\n",
        "1:name=systemd:/lxc/container-name\n",
    ],
)
def test_a_container_runtime_in_the_init_cgroup_is_found(tmp_path: Path, line: str) -> None:
    _cgroup(tmp_path, line)

    found = container_marker(tmp_path)

    assert found is not None
    assert CGROUP_PATH in found


def test_an_ordinary_init_cgroup_is_not_a_marker(tmp_path: Path) -> None:
    _cgroup(tmp_path, "0::/init.scope\n")

    assert container_marker(tmp_path) is None


def test_the_container_context_with_no_marker_is_never_in_force() -> None:
    """Decided once, before either guard acts on it: a claim nobody verified admits nothing."""
    outcome = bind.context_in_force(CONTAINER.value, marker=None)

    assert isinstance(outcome, bind.ContainerClaimUnverified)
    assert DOCKER_MARKER in outcome.reason
    assert CGROUP_PATH in outcome.reason
    assert "Principle VII" in outcome.reason


def test_the_context_is_in_force_once_a_marker_is_found() -> None:
    assert bind.context_in_force(CONTAINER.value, marker=DOCKER_MARKER) is CONTAINER


@pytest.mark.parametrize("address", ["0.0.0.0", "::", "127.0.0.1", "::1"])
def test_the_container_interface_passes_once_the_claim_is_verified(address: str) -> None:
    outcome = check_bind(address, context=CONTAINER)

    assert isinstance(outcome, BindPermitted)
    assert outcome.address == address


@pytest.mark.parametrize("address", ["192.168.1.10", "203.0.113.7"])
def test_a_named_lan_address_is_still_refused_inside_a_container(address: str) -> None:
    """The container context admits the interface a container actually has, not any address:
    binding a routable address inside a container is not something the runtime offers."""
    outcome = check_bind(address, context=CONTAINER)

    assert isinstance(outcome, BindRefused)


def test_the_entry_point_refuses_the_claim_on_a_machine_with_no_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(CONTEXT_VARIABLE, CONTAINER.value)
    started: list[tuple[str, int]] = []

    code = serve.main(
        ["--host", "0.0.0.0"],
        root=tmp_path,
        start=lambda a, p: started.append((a, p)),
    )

    assert code != 0
    assert not started
    refusal = capsys.readouterr().err
    assert DOCKER_MARKER in refusal
    assert CGROUP_PATH in refusal


def test_the_entry_point_starts_when_the_marker_is_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CONTEXT_VARIABLE, CONTAINER.value)
    _cgroup(tmp_path, "0::/docker/3fa1b2c3\n")
    started: list[tuple[str, int]] = []

    code = serve.main(
        ["--host", "0.0.0.0", "--port", "8000"],
        root=tmp_path,
        start=lambda a, p: started.append((a, p)),
    )

    assert code == 0
    assert started == [("0.0.0.0", 8000)]


def test_the_served_app_refuses_the_claim_on_a_machine_with_no_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`uvicorn terezy.api.http:app` never calls the entry point, so the module that builds the
    application verifies the claim itself. Without this, one environment variable on a laptop
    relaxes the per-request check and every LAN client is answered."""
    monkeypatch.setenv(CONTEXT_VARIABLE, CONTAINER.value)

    with pytest.raises(ValueError, match=DOCKER_MARKER):
        service.bind_context(root=tmp_path)


def test_the_served_app_honours_the_claim_where_a_marker_is_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CONTEXT_VARIABLE, CONTAINER.value)
    (tmp_path / ".dockerenv").touch()

    assert service.bind_context(root=tmp_path) is CONTAINER
