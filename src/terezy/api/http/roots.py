"""Where declarations are read from -- decided once at startup, never defaulted to the cwd.

The default used to be ``Path("data")``, which is relative to whatever directory the process was
started in. Started anywhere but the repository root the service came up healthy and answered
500 on every endpoint, including the one serving the client's own index -- a degraded outcome
reported once per request instead of once, at the only moment anything could act on it. An
absent root is also not a malformed declaration, so 020 FR-016's permission to answer a
malformed declaration with an error status never covered it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import terezy
from terezy.data.declarations import resolver

DATA_ROOT_VARIABLE: Final[str] = "TEREZY_DATA_ROOT"

SOURCE_DIRECTORY: Final[str] = "src"
"""The layout marker that says this package was imported from a checkout rather than installed."""


@dataclass(frozen=True)
class DataRootFound:
    """A directory declaring the venues every other declaration is checked against."""

    path: Path


@dataclass(frozen=True)
class DataRootMissing:
    """No root to read, named with the path that was tried and the variable that overrides it."""

    reason: str


def checkout_root() -> Path | None:
    """The checkout this package was imported from, or ``None`` when it was installed.

    Taken from the package's own location rather than from the working directory, so the answer
    is the same wherever the process was started -- which is the whole of this module's job.
    """
    here = Path(terezy.__file__).resolve().parent
    return None if here.parent.name != SOURCE_DIRECTORY else here.parents[1]


def packaged_default() -> Path | None:
    """``data/`` in that checkout. An installed distribution ships none, and guessing one for it
    is the defect this module exists for."""
    checkout = checkout_root()
    return None if checkout is None else checkout / "data"


def data_root_in_force(
    declared: str | None, *, packaged: Path | None
) -> DataRootFound | DataRootMissing:
    """The root this process reads declarations from, or the refusal that stops it starting."""
    if declared is not None:
        return _checked(Path(declared), named_by=f"{DATA_ROOT_VARIABLE}={declared}")
    if packaged is None:
        return DataRootMissing(
            reason=(
                f"no data root: {DATA_ROOT_VARIABLE} is unset and terezy is installed outside a "
                f"checkout, so there is no {resolver.VENUES_FILE} to fall back on. Set "
                f"{DATA_ROOT_VARIABLE} to the directory holding it."
            )
        )
    return _checked(packaged, named_by="the checkout this package was imported from")


def _checked(path: Path, *, named_by: str) -> DataRootFound | DataRootMissing:
    """One root, accepted only if it declares the venues.

    ``venues.toml`` rather than the directory's existence: an empty directory and a directory of
    something else both pass an existence check, and every route resolves through the venues, so
    a root without one answers nothing.
    """
    if not (path / resolver.VENUES_FILE).is_file():
        return DataRootMissing(
            reason=(
                f"the data root {path} ({named_by}) holds no {resolver.VENUES_FILE}, so nothing "
                f"is declared to read. Point {DATA_ROOT_VARIABLE} at the directory that holds it."
            )
        )
    return DataRootFound(path=path)
