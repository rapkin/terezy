"""The shipped artefacts, parsed as text: no daemon, no build, no container (020 FR-035, SC-023b).

The port assertion is the one that carries FR-029's row 4 -- under the shipped deployment the
per-request check is relaxed, so the publication rule is what holds. It is written over **every**
service and every profile, because feature 021 adds a second service to this file and a check
that named ``api`` would go green on the commit that publishes the other one (FR-028, SC-014).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]  # no stubs in the dev group

ROOT = Path(__file__).resolve().parents[2]

COMPOSE = ROOT / "docker-compose.yml"
DOCKERFILE = ROOT / "Dockerfile"

PUBLICATION = re.compile(r"^127\.0\.0\.1:(?P<published>\d+):(?P<container>\d+)(?:/\w+)?$")

OFFICIAL_PYTHON = re.compile(r"^python:[\w.-]+$")

OFFICIAL_NODE = re.compile(r"^node:[\w.-]+$")

CONTEXT_VARIABLE = "TEREZY_BIND_CONTEXT"
DATA_ROOT_VARIABLE = "TEREZY_DATA_ROOT"
CONTAINER_CONTEXT = "container-published-to-loopback"

ENTRY_POINT = "terezy.api.http"


def _compose() -> dict[str, Any]:
    loaded = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _services() -> dict[str, dict[str, Any]]:
    services = _compose()["services"]
    assert isinstance(services, dict)
    return services


def _environment(service: dict[str, Any]) -> dict[str, str]:
    declared = service.get("environment", {})
    if isinstance(declared, list):
        return dict(entry.split("=", 1) for entry in declared)
    return {str(key): str(value) for key, value in declared.items()}


def _words(value: Any) -> list[str]:
    if isinstance(value, str):
        return value.split()
    return [str(part) for part in value]


def _dockerfile_directive(name: str) -> list[str]:
    """The last value of a Dockerfile directive, as words. Exec form or shell form."""
    found: list[str] = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith(f"{name} "):
            continue
        value = stripped[len(name) :].strip()
        found = (
            [str(part) for part in yaml.safe_load(value)]
            if value.startswith("[")
            else value.split()
        )
    return found


@pytest.mark.contract
def test_the_compose_file_and_the_dockerfile_are_shipped() -> None:
    assert COMPOSE.is_file()
    assert DOCKERFILE.is_file()


@pytest.mark.contract
def test_every_published_port_on_every_service_names_loopback() -> None:
    """A bare ``8000:8000`` publishes on every interface, which is the edit this catches in
    the same commit that makes the service reachable."""
    offenders: list[str] = []
    published = 0
    for name, service in _services().items():
        for entry in service.get("ports", []):
            published += 1
            match = PUBLICATION.match(str(entry))
            if match is None or match["published"] != match["container"]:
                offenders.append(f"{name}: {entry}")

    assert published >= 1
    assert not offenders, f"published off loopback: {offenders}"


@pytest.mark.contract
def test_no_service_takes_the_host_network() -> None:
    """`network_mode: host` publishes every port on every interface while declaring none, so a
    check that reads `ports` alone would go green on the one edit that needs it most."""
    on_the_host = sorted(
        name for name, service in _services().items() if service.get("network_mode") == "host"
    )
    assert not on_the_host, f"these services bypass port publication entirely: {on_the_host}"


@pytest.mark.contract
def test_the_port_check_would_actually_catch_a_publication() -> None:
    assert PUBLICATION.match("127.0.0.1:8000:8000")
    assert not PUBLICATION.match("8000:8000")
    assert not PUBLICATION.match("0.0.0.0:8000:8000")
    assert not PUBLICATION.match("::8000:8000")
    assert not PUBLICATION.match("127.0.0.1:8000")


@pytest.mark.contract
def test_the_api_service_publishes_the_port_feature_021_is_told_about() -> None:
    assert _services()["api"]["ports"] == ["127.0.0.1:8000:8000"]


@pytest.mark.contract
def test_the_api_service_mounts_the_data_directory_read_only() -> None:
    """A read-only API whose data directory is writable is read-only by intention; read-only
    by mount is read-only by construction (FR-033)."""
    api = _services()["api"]
    mounts = [str(entry) for entry in api["volumes"]]
    data = [entry for entry in mounts if entry.split(":")[0] == "./data"]

    assert len(data) == 1
    source, target, *options = data[0].split(":")
    assert source == "./data"
    assert "ro" in options
    assert _environment(api)[DATA_ROOT_VARIABLE] == target


@pytest.mark.contract
def test_the_api_service_declares_the_container_bind_context() -> None:
    assert _environment(_services()["api"])[CONTEXT_VARIABLE] == CONTAINER_CONTEXT


@pytest.mark.contract
def test_the_api_service_starts_through_the_entry_point_and_not_a_bare_server() -> None:
    """FR-026b: the supported path is the one that refuses early, so the compose file may not
    reach past it to the server's own command."""
    api = _services()["api"]
    entry = (
        _words(api["entrypoint"]) if "entrypoint" in api else _dockerfile_directive("ENTRYPOINT")
    )
    invocation = entry + _words(api.get("command", []))

    assert invocation, "the api service names no command"
    assert ENTRY_POINT in invocation
    assert invocation[invocation.index(ENTRY_POINT) - 1] == "-m"
    assert "uvicorn" not in invocation


@pytest.mark.contract
def test_the_api_service_builds_here_and_names_no_foreign_image() -> None:
    api = _services()["api"]

    assert "build" in api
    named = api.get("image")
    assert named is None or "/" not in str(named)


@pytest.mark.contract
def test_every_base_image_in_the_dockerfile_is_an_official_one() -> None:
    """FR-034 in the form it takes now that 021 builds the client here: the service runs on the
    official ``python`` image and the client is built on the official ``node`` one, and no other
    registry is read from."""
    stages: set[str] = set()
    bases: list[str] = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        words = line.split()
        if not words or words[0].upper() != "FROM":
            continue
        base = words[1]
        if len(words) >= 4 and words[2].upper() == "AS":
            stages.add(words[3])
        bases.append(base)

    assert bases
    for base in bases:
        assert base in stages or OFFICIAL_PYTHON.match(base) or OFFICIAL_NODE.match(base), base


@pytest.mark.contract
def test_the_build_copies_from_no_second_image() -> None:
    """``COPY --from=<image>`` pulls an image the FROM lines never name, which is the other way
    a foreign image reaches the build (FR-034)."""
    stages = {
        words[3]
        for words in (line.split() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines())
        if len(words) >= 4 and words[0].upper() == "FROM" and words[2].upper() == "AS"
    }
    foreign = [
        word
        for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()
        for word in line.split()
        if word.startswith("--from=") and word.removeprefix("--from=") not in stages
    ]

    assert not foreign, f"the build copies from an image this repository does not build: {foreign}"


@pytest.mark.contract
def test_the_dockerfile_check_would_actually_catch_a_foreign_image() -> None:
    assert OFFICIAL_PYTHON.match("python:3.13-slim")
    assert OFFICIAL_NODE.match("node:22-slim")
    assert not OFFICIAL_PYTHON.match("ghcr.io/someone/python:3.13")
    assert not OFFICIAL_PYTHON.match("docker.io/library/python:3.13-slim")
    assert not OFFICIAL_NODE.match("ghcr.io/someone/node:22")


@pytest.mark.contract
def test_the_file_declares_the_api_service_and_the_development_only_web_one() -> None:
    """Feature 021 added its own service to this file (FR-032) without moving ``api``. The set is
    closed so a third service is a decision rather than a file somebody adds."""
    compose = _compose()

    assert set(compose) <= {"services", "name", "volumes", "networks", "configs", "secrets"}
    assert set(_services()) == {"api", "web"}


@pytest.mark.contract
def test_the_web_service_starts_only_under_a_profile_and_the_api_service_always() -> None:
    """021 FR-051: bringing the stack up without a profile starts no ``web`` service, because in
    production the api image serves the built client from the same origin (021 FR-049)."""
    services = _services()

    assert services["web"]["profiles"] == ["dev"]
    assert "profiles" not in services["api"]


@pytest.mark.contract
def test_the_web_service_command_reaches_the_shell_as_one_string() -> None:
    """A scalar `command` beside a `sh -c` entry point is split on whitespace, so the shell is
    handed the first word alone and the service starts nothing. It fails at run time and looks
    like a slow start, which is why it is asserted here rather than found by bringing it up."""
    web = _services()["web"]

    assert _words(web["entrypoint"]) == ["/bin/sh", "-c"]
    assert isinstance(web["command"], list)
    assert len(web["command"]) == 1
    assert "vite" in str(web["command"][0])


@pytest.mark.contract
def test_the_web_service_keeps_its_own_installed_packages() -> None:
    """The source tree is bind-mounted, so an install inside the container writes into the
    checkout: Linux binaries into the tree the host's own gates run out of, and a 250 MB package
    store beside them. Measured 2026-09-05: the store's default put 19,182 files under `web/`."""
    web = _services()["web"]
    mounts = [str(entry) for entry in web["volumes"]]

    assert "./web:/web" in mounts
    assert any(entry.endswith("/web/node_modules") and ":" not in entry for entry in mounts)

    # And the package store, which is 250 MB and lands in the checkout when left at its default.
    store = [entry for entry in mounts if entry.endswith(":/pnpm-store")]
    assert len(store) == 1
    assert store[0].split(":")[0] in _compose()["volumes"]
    assert "--store-dir /pnpm-store" in str(web["command"][0])


@pytest.mark.contract
def test_the_final_image_carries_no_node_toolchain() -> None:
    """021 FR-053, SC-015: the stage that ships carries the built assets, the Python application
    and its runtime, and nothing that produced the assets."""
    stages = DOCKERFILE.read_text(encoding="utf-8").split("\nFROM ")
    final = stages[-1]

    assert final.startswith("python:"), final.splitlines()[0]
    assert "corepack" not in final
    assert "pnpm" not in final
    assert "npm" not in final
    for line in final.splitlines():
        if line.upper().startswith("COPY --FROM=CLIENT"):
            assert line.split()[2].endswith("/dist"), line
