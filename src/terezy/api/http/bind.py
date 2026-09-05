"""Where the service may listen, and who it may answer -- decided, never defaulted.

Constitution Principle VII makes authentication a blocking gate before the application listens
on any interface other than loopback. This module is that gate in the form the process can
apply: a closed two-valued context, a claim about the container that is verified before it is
honoured, and two decisions returned as typed results rather than raised.

Every function here takes what it needs as an argument -- the context value, the filesystem
root, the marker -- so the whole module is decidable in a test without an environment, a
container or a socket. Reading the environment is :mod:`terezy.api.http.serve`'s job.

What a marker check buys is that publishing to a network stops being one environment variable
and becomes forging a container marker, which nobody does by accident. That is a smaller claim
than the one it is tempting to make, and 020 FR-027b requires the smaller one.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from pathlib import Path


class BindContext(Enum):
    """Where the process claims to be running. Exactly two values, and no value means anywhere."""

    LOOPBACK = "loopback"
    CONTAINER_PUBLISHED_TO_LOOPBACK = "container-published-to-loopback"


CONTEXT_VARIABLE: Final[str] = "TEREZY_BIND_CONTEXT"

DOCKER_MARKER: Final[str] = "/.dockerenv"

CGROUP_PATH: Final[str] = "/proc/1/cgroup"

CGROUP_RUNTIMES: Final[tuple[str, ...]] = (
    "docker",
    "containerd",
    "kubepods",
    "libpod",
    "podman",
    "lxc",
    "crio",
)

RELEASE_GATE: Final[str] = (
    "Constitution Principle VII: authentication must exist before the application listens on "
    "any interface other than loopback, and authentication is what lifts this refusal."
)


@dataclass(frozen=True)
class BindPermitted:
    """The address the caller checked, handed back so the server is given what was decided on."""

    address: str
    context: BindContext
    reason: str


@dataclass(frozen=True)
class BindRefused:
    address: str
    context: BindContext
    reason: str


@dataclass(frozen=True)
class ContextNotRecognised:
    """A value that is neither declared value. Never a fall-back to the default: the person who
    typed it believed they had asked for something."""

    value: str
    reason: str


@dataclass(frozen=True)
class ContainerClaimUnverified:
    """The container context was declared on a machine carrying no container marker.

    What the check buys is that publishing to a network stops being one environment variable and
    becomes forging a marker. That is a different property from impossibility.
    """

    value: str
    reason: str


ContextRefused = ContextNotRecognised | ContainerClaimUnverified


@dataclass(frozen=True)
class ClientPermitted:
    client_address: str | None
    reason: str


@dataclass(frozen=True)
class ClientRefused:
    client_address: str | None
    reason: str


def context_in_force(value: str | None, *, marker: str | None) -> BindContext | ContextRefused:
    """The context this process may act under, or the refusal that stops it acting at all.

    Both guards go through here, and that is the point: the marker verification used to live in
    the startup path alone, so a bare server command under the container context lifted the
    per-request check on a laptop -- one environment variable, which FR-030 forbids and FR-029
    lists as guaranteed against.
    """
    declared = context_of(value)
    match declared:
        case ContextNotRecognised():
            return declared
        case BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK if marker is None:
            return ContainerClaimUnverified(
                value=declared.value,
                reason=(
                    f"{CONTEXT_VARIABLE} declares {declared.value}, and this process is not "
                    f"inside a container: no {DOCKER_MARKER} and no container runtime named in "
                    f"{CGROUP_PATH}. {RELEASE_GATE}"
                ),
            )
        case _:
            return declared


def context_of(value: str | None) -> BindContext | ContextNotRecognised:
    """The declared context, with an unset variable meaning loopback. Says nothing about where
    the process is actually running: :func:`context_in_force` is what verifies the claim."""
    if value is None:
        return BindContext.LOOPBACK
    for member in BindContext:
        if member.value == value:
            return member
    declared = ", ".join(member.value for member in BindContext)
    return ContextNotRecognised(
        value=value,
        reason=(
            f"{CONTEXT_VARIABLE} is {value!r}, which is neither declared value. "
            f"The declared values are: {declared}. {RELEASE_GATE}"
        ),
    )


def container_marker(root: Path) -> str | None:
    """The container marker found under ``root``, or ``None``.

    ``root`` is the filesystem root rather than a hardcoded ``/`` so the search is decidable
    against a temporary directory; production passes ``Path("/")``.
    """
    if root.joinpath(*DOCKER_MARKER.strip("/").split("/")).exists():
        return DOCKER_MARKER
    cgroup = root.joinpath(*CGROUP_PATH.strip("/").split("/"))
    if not cgroup.is_file():
        return None
    text = cgroup.read_text(encoding="utf-8", errors="replace")
    for runtime in CGROUP_RUNTIMES:
        if runtime in text:
            return f"{CGROUP_PATH} names {runtime}"
    return None


def check_bind(address: str, *, context: BindContext) -> BindPermitted | BindRefused:
    """Whether the service may bind ``address`` under ``context``.

    Takes an address and never a hostname. Resolving a name is a network act, and a guard that
    resolved one would make the suite's no-network rule depend on the machine's resolver --
    green offline for the wrong reason and nondeterministic online (FR-026). A caller holding a
    name resolves it first and hands over what it resolved to.
    """
    parsed = _address_of(address)
    if parsed is None:
        return BindRefused(
            address=address,
            context=context,
            reason=(
                f"{address!r} is a hostname, not an address. This guard decides about an "
                f"address and performs no name resolution; resolve it and pass the result. "
                f"{RELEASE_GATE}"
            ),
        )

    match context:
        case BindContext.LOOPBACK:
            if parsed.is_loopback:
                return BindPermitted(
                    address=address,
                    context=context,
                    reason=f"{address} is a loopback address.",
                )
            return BindRefused(
                address=address,
                context=context,
                reason=(
                    f"{address} is not a loopback address and {CONTEXT_VARIABLE} declares "
                    f"{context.value}. {RELEASE_GATE}"
                ),
            )
        case BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK:
            if parsed.is_loopback or parsed.is_unspecified:
                return BindPermitted(
                    address=address,
                    context=context,
                    reason=(
                        f"{address} is the interface a container has to offer, and the container "
                        "claim was verified before this context was honoured."
                    ),
                )
            return BindRefused(
                address=address,
                context=context,
                reason=(
                    f"{address} is a routable address, which is not the interface the container "
                    f"context admits. {RELEASE_GATE}"
                ),
            )


def client_is_permitted(
    client_address: str | None, *, context: BindContext
) -> ClientPermitted | ClientRefused:
    """Whether a request from ``client_address`` is answered under ``context``.

    This is the half that holds when terezy did not start the process: a bare server command
    never reaches :func:`check_bind`, so under the default context the address of whoever is
    talking is checked per request instead (FR-026a).

    An **absent** address is refused. Both ASGI address fields are optional, so *no opinion* is
    a state the scope can actually be in, and reading it as loopback is the fail-open this
    function exists to avoid.
    """
    if context is BindContext.CONTAINER_PUBLISHED_TO_LOOPBACK:
        return ClientPermitted(
            client_address=client_address,
            reason=(
                f"{CONTEXT_VARIABLE} declares {context.value}: inside a container every client "
                f"address is the bridge, so no finer statement is available and what holds "
                f"instead is that the host publishes the port to loopback."
            ),
        )

    if client_address is None:
        return ClientRefused(
            client_address=None,
            reason=(
                "The request carries no client address. An absent address is not a loopback "
                f"address, and is refused rather than read as one. {RELEASE_GATE}"
            ),
        )

    parsed = _address_of(client_address)
    if parsed is None or not parsed.is_loopback:
        return ClientRefused(
            client_address=client_address,
            reason=(
                f"The client address {client_address!r} is not a loopback address. {RELEASE_GATE}"
            ),
        )
    return ClientPermitted(
        client_address=client_address,
        reason=f"{client_address} is a loopback address.",
    )


def _address_of(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return None
    return parsed
