#!/usr/bin/env python3
"""Fetch the Ukrainian consumer price index and write it as a declaration file.

**This script retrieves. It does not verify.** That distinction is the whole reason it
exists in this shape: every observation it writes carries its ``source`` and its
``retrieved_on``, and an **empty** ``verified_on`` -- because a number that was downloaded
is not a number anyone has checked. Filling ``verified_on`` is an act a human performs
after comparing the value against the publisher, and no automation may perform it. A
fetcher that stamped a verification date would destroy the one distinction the whole
project is built on.

**Why a script and not the ``Provider`` interface.** ``Provider`` is one of the four
plugin interfaces and it is deliberately unimplemented; ``features.toml`` records
``provider-automation`` as owner-requested future work covering fund terms, CPI and FX
rates together. One series is not enough to design an interface from. This is tooling in
the shape of ``check_provenance.py`` -- run by hand, outside the package, outside the
layered architecture -- and its output is an ordinary declaration file that gets read,
reviewed and committed like every other. When ``provider-automation`` is specified, this
script is its first input, not its competitor.

**Why it is not in ``src/``.** ``terezy.core`` may not import ``urllib`` and
``.importlinter`` enforces it; the suite blocks sockets outright (``tests/conftest.py``,
row K4). Network access lives here, is explicit, runs on demand, and never happens during
a test or an import.

The source
----------
``data.gov.ua``, the state open-data portal, dataset
``12f4fe34-0759-4271-b1f6-780995f0ec4a`` -- "Зміни цін (тарифів) на споживчі товари
(послуги)", published by Державна служба статистики України under Creative Commons
Attribution. Reached through CKAN's documented ``package_show`` action rather than a
hardcoded file URL, because resource URLs rot and the action does not.

The payload is SDMX-JSON. The series taken is the headline all-Ukraine monthly index
against the previous month:

    INDICATOR           INDEX_CONSUMPRICE
    BASE_PERIOD         PREV_MONTH
    REGION              UA00000000000000000   (Україна, all regions)
    GOODS_SERVICES_TYPE 0                     (all goods and services)
    FREQ                M

**The mirror lags.** At the time of writing the dataset's latest observation is
``2025-M10`` although its metadata claims monthly updates. That is a fact about the
source, not a defect here, and it is why this script prints its coverage window loudly
and why a deflation window running past the last observation must refuse rather than
extrapolate. Держстат's own SDMX API may be fresher and is the natural next source to
add; it is not used yet because its base URL is not documented on the page that announces
it.

Usage
-----
    uv run python scripts/fetch_cpi.py --dry-run     # report, write nothing
    uv run python scripts/fetch_cpi.py               # write data/cpi/ua.toml

Nothing is written unless every step succeeded: the file is built in memory, written to a
temporary path and moved into place, so an interrupted or failed run leaves the previous
declaration exactly as it was. A partially written series would be worse than none --
a gap that looks like data.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
OUT_PATH: Final = REPO_ROOT / "data" / "cpi" / "ua.toml"

CKAN_ACTION: Final = "https://data.gov.ua/api/3/action/package_show"
DATASET_ID: Final = "12f4fe34-0759-4271-b1f6-780995f0ec4a"
DATASET_PAGE: Final = f"https://data.gov.ua/dataset/{DATASET_ID}"

SERIES: Final[dict[str, str]] = {
    "INDICATOR": "INDEX_CONSUMPRICE",
    "BASE_PERIOD": "PREV_MONTH",
    "REGION": "UA00000000000000000",
    "GOODS_SERVICES_TYPE": "0",
    "FREQ": "M",
}
"""The one series this script reads, by dimension code.

Named rather than positional: SDMX series keys are colon-joined *indices* into each
dimension's value list, so a key that is correct today silently addresses a different
series the day the publisher inserts a code. Resolving the indices from these ids on every
run means a changed structure is a loud failure instead of a wrong number.
"""

TIMEOUT_SECONDS: Final = 120

MONTHS_PER_YEAR: Final = 12

SHOWN_CODES: Final = 12
"""How many codelist entries a failure message quotes before trailing off."""

STALE_AFTER_MONTHS: Final = 2
"""Beyond this the script says the series is behind. Two months, because the publisher
adds one a month and one late month is ordinary; two is a pattern worth naming."""
USER_AGENT: Final = "terezy/fetch_cpi (single-user personal finance tool; contact via repository)"


class FetchError(RuntimeError):
    """Anything that stopped this run from producing a complete, trustworthy series."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One published index value for one month."""

    period: str
    """``YYYY-MM``, normalised from SDMX's ``YYYY-Mnn``."""

    value: float
    """The index against the previous month. 100.9 means prices rose 0.9% that month."""


@dataclass(frozen=True, slots=True)
class Fetched:
    """A complete series and the provenance of the act that retrieved it."""

    observations: tuple[Observation, ...]
    dataset_title: str
    publisher: str
    licence: str
    resource_url: str
    metadata_modified: str
    retrieved_on: date


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc


def _json(url: str, *, what: str) -> Any:
    try:
        return json.loads(_get(url))
    except json.JSONDecodeError as exc:
        raise FetchError(f"{what} at {url} is not JSON: {exc}") from exc


def _resource_url(package: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The SDMX-JSON resource, found by format rather than by remembered id."""
    result = package.get("result")
    if not isinstance(result, dict):
        raise FetchError("CKAN package_show returned no result object")
    resources = result.get("resources")
    if not isinstance(resources, list) or not resources:
        raise FetchError(f"dataset {DATASET_ID} lists no resources")
    for resource in resources:
        name = str(resource.get("name", ""))
        if str(resource.get("format", "")).upper() == "JSON" and name.endswith(".json"):
            url = resource.get("url")
            if not isinstance(url, str):
                raise FetchError(f"resource {resource.get('id')} has no url")
            return url, result
    formats = sorted({str(r.get("format")) for r in resources})
    raise FetchError(
        f"dataset {DATASET_ID} no longer publishes a JSON resource; it offers {formats}. "
        "The publisher changed the dataset's shape -- read the dataset page before "
        "changing this script, and do not fall back to a format nobody checked."
    )


def _dimension_index(
    structure: dict[str, Any], dimension_id: str, value_id: str
) -> tuple[int, int]:
    """Position of a dimension in the series key, and of a value within that dimension."""
    dimensions = structure.get("dimensions", {}).get("series")
    if not isinstance(dimensions, list):
        raise FetchError("SDMX structure declares no series dimensions")
    for position, dimension in enumerate(dimensions):
        if dimension.get("id") != dimension_id:
            continue
        ids = [value.get("id") for value in dimension.get("values", [])]
        if value_id not in ids:
            raise FetchError(
                f"dimension {dimension_id} no longer declares the code {value_id!r}; "
                f"it declares {ids[:SHOWN_CODES]}"
                f"{' ...' if len(ids) > SHOWN_CODES else ''}. The publisher "
                "changed its codelist -- pick the new code deliberately rather than "
                "letting this script guess."
            )
        return position, ids.index(value_id)
    raise FetchError(f"SDMX structure has no series dimension {dimension_id!r}")


def _periods(structure: dict[str, Any]) -> list[str]:
    observation_dimensions = structure.get("dimensions", {}).get("observation")
    if not isinstance(observation_dimensions, list) or not observation_dimensions:
        raise FetchError("SDMX structure declares no observation dimension")
    values = observation_dimensions[0].get("values", [])
    return [str(value.get("value")) for value in values]


def _normalised(period: str) -> str:
    """``2025-M10`` -> ``2025-10``. Anything else is refused rather than reshaped."""
    year, separator, month = period.partition("-M")
    if not separator or not year.isdigit() or not month.isdigit():
        raise FetchError(
            f"period {period!r} is not the monthly form this script reads. The series was "
            "selected as FREQ=M; a different period shape means a different series."
        )
    return f"{year}-{int(month):02d}"


def _observations(payload: dict[str, Any]) -> Iterator[Observation]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FetchError("SDMX payload has no data object")
    structures = data.get("structures")
    if not isinstance(structures, list) or not structures:
        raise FetchError("SDMX payload declares no structures")
    structure = structures[0]

    wanted: dict[int, int] = {}
    for dimension_id, value_id in SERIES.items():
        position, index = _dimension_index(structure, dimension_id, value_id)
        wanted[position] = index

    periods = _periods(structure)
    datasets = data.get("dataSets")
    if not isinstance(datasets, list) or not datasets:
        raise FetchError("SDMX payload carries no dataSets")
    series = datasets[0].get("series")
    if not isinstance(series, dict):
        raise FetchError("SDMX dataSet carries no series")

    matches = [
        key
        for key in series
        if all(
            int(part) == wanted[position]
            for position, part in enumerate(key.split(":"))
            if position in wanted
        )
    ]
    if len(matches) != 1:
        raise FetchError(
            f"expected exactly one series matching {SERIES}, found {len(matches)}. "
            "The publisher changed the structure -- resolve which series is the headline "
            "index before trusting anything this script writes."
        )

    found = 0
    for raw_index, cell in series[matches[0]]["observations"].items():
        raw_value = cell[0] if cell else None
        if raw_value is None:
            continue  # A gap. Not interpolated, not carried forward, simply absent.
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            message = f"observation {raw_index} holds {raw_value!r}, which is not a number"
            raise FetchError(message) from exc
        found += 1
        yield Observation(period=_normalised(periods[int(raw_index)]), value=value)

    if found == 0:
        raise FetchError("the series matched but carries no observations at all")


def fetch(*, today: date) -> Fetched:
    """Retrieve the series. Raises :class:`FetchError` rather than returning a partial one."""
    package = _json(f"{CKAN_ACTION}?id={DATASET_ID}", what="CKAN package_show")
    resource_url, result = _resource_url(package)
    payload = _json(resource_url, what="the SDMX-JSON resource")
    observations = tuple(sorted(_observations(payload), key=lambda o: o.period))
    return Fetched(
        observations=observations,
        dataset_title=" ".join(str(result.get("title", "")).split()),
        publisher=str(result.get("organization", {}).get("title", "")),
        licence=str(result.get("license_title", "")),
        resource_url=resource_url,
        metadata_modified=str(result.get("metadata_modified", "")),
        retrieved_on=today,
    )


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def render(fetched: Fetched) -> str:
    """The declaration file, in full. Pure -- takes no clock and touches no disk."""
    first = fetched.observations[0].period
    last = fetched.observations[-1].period
    citation = (
        f"{fetched.publisher} — «{fetched.dataset_title}», dataset {DATASET_ID} on data.gov.ua "
        f"({fetched.licence}); series "
        "INDEX_CONSUMPRICE / PREV_MONTH / UA00000000000000000 / 0 / M; "
        f"dataset metadata_modified {fetched.metadata_modified}"
    )
    lines = [
        "# Ukrainian consumer price index, month on month.",
        "#",
        "# RETRIEVED, NOT VERIFIED. Every observation below carries its source and the date it",
        "# was retrieved, and an EMPTY `verified_on` -- because a number that was downloaded is",
        "# not a number anyone has checked. Filling that field is an act the owner performs",
        "# against the publisher, and `scripts/fetch_cpi.py` must never perform it. Every figure",
        "# derived from these values renders marked until he does.",
        "#",
        f"# Generated by scripts/fetch_cpi.py on {fetched.retrieved_on.isoformat()}."
        " Do not hand-edit:",
        "# re-run the script and read the diff. A value corrected by hand loses the one thing",
        "# that makes it checkable -- the ability to reproduce it from the cited source.",
        "#",
        f"# COVERAGE: {first} .. {last}. The open-data mirror lags its own stated monthly cadence.",
        "# A deflation window running past the last observation has no data and must refuse --",
        "# never extrapolate, never carry the last value forward (007 FR-004).",
        "#",
        f"# {DATASET_PAGE}",
        "",
        "[series]",
        'id          = "ua_cpi_monthly"',
        'country     = "UA"',
        'index       = "consumer price index, all goods and services"',
        'periodicity = "monthly"',
        'base        = "previous month = 100"',
        "",
        "# One line per published month. `value` is the index against the previous month:",
        "# 100.9 means prices rose 0.9% that month. Months the publisher does not publish are",
        "# absent rather than zero -- a gap is a fact, and 007 FR-004 forbids inventing one.",
        "",
    ]
    for observation in fetched.observations:
        lines.append(
            "[[observation]]\n"
            f'period       = "{observation.period}"\n'
            f"value        = {observation.value}\n"
            f'kind         = "cpi_index"\n'
            f'source       = "{_escape(citation)}"\n'
            f'retrieved_on = "{fetched.retrieved_on.isoformat()}"\n'
            'verified_on  = ""\n'
        )
    return "\n".join(lines)


def _write(text: str, path: Path) -> None:
    """Atomically, so a failed run never leaves half a series behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(handle, "w", encoding="utf-8") as file:  # noqa: PTH123 -- an fd, not a path
            file.write(text)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be written, write nothing"
    )
    parser.add_argument(
        "--out", type=Path, default=OUT_PATH, help=f"output path (default: {OUT_PATH})"
    )
    arguments = parser.parse_args(argv)

    try:
        today = date.today()  # noqa: DTZ011 -- a script reads the clock; the pure core never does
        fetched = fetch(today=today)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        print("nothing was written.", file=sys.stderr)  # noqa: T201
        return 1

    first = fetched.observations[0].period
    last = fetched.observations[-1].period
    print(f"publisher      {fetched.publisher}")  # noqa: T201
    print(f"licence        {fetched.licence}")  # noqa: T201
    print(f"observations   {len(fetched.observations)}")  # noqa: T201
    print(f"coverage       {first} .. {last}")  # noqa: T201
    print(f"latest value   {fetched.observations[-1].value} (index, previous month = 100)")  # noqa: T201
    print(  # noqa: T201
        f"retrieved_on   {fetched.retrieved_on.isoformat()}   verified_on   (empty, deliberately)"
    )

    stale_months = (today.year - int(last[:4])) * MONTHS_PER_YEAR + today.month - int(last[5:])
    if stale_months > STALE_AFTER_MONTHS:
        print(  # noqa: T201
            f"note: the newest observation is {stale_months} months old. That is the source's "
            "cadence, not a failure here -- but any window past it must refuse rather than "
            "extrapolate.",
        )

    if arguments.dry_run:
        print("\n--dry-run: nothing written.")  # noqa: T201
        return 0

    _write(render(fetched), arguments.out)
    print(f"\nwrote {arguments.out.relative_to(REPO_ROOT)} -- read the diff before committing it.")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
