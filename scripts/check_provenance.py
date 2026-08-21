#!/usr/bin/env python3
"""Provenance gate for curated data files.

Constitution Principle I: no legal or tax value may originate from an implementer's
or an agent's memory. Every value carries ``value``, ``source``, ``retrieved_on`` and
``verified_on``, and an empty ``verified_on`` marks the figure rather than blocking it.

This script enforces the *mechanical* half of that rule at commit time, so a rate
without a citation cannot reach main:

    error   -- a numeric leaf under a rate-bearing table with no ``source``
    error   -- a ``source``/``retrieved_on``/``verified_on`` of the wrong shape
    warning -- an empty ``verified_on`` (expected and permitted; it must render marked)

It is deliberately a standalone script rather than a test: it runs over data files,
which are reviewed in git like code, and it must be runnable by a non-developer
maintaining a NAV or a fee schedule by hand.

Exit status: 0 clean (warnings allowed), 1 on any error.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"

# Directories whose numeric values are legal, tax, fee or market observations and
# therefore require a citation. Scenarios and objectives are the owner's own stated
# assumptions, so they are exempt by design -- an assumption needs a label, not a source.
SOURCED_DIRS = ("tax", "instruments", "routes")

REQUIRED_WITH_SOURCE = ("source", "retrieved_on")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Keys that are structural rather than observed values.
STRUCTURAL_KEYS = frozenset(
    {
        "id",
        "name",
        "class",
        "kind",
        "currency",
        "income_currency",
        "status",
        "policy",
        "label",
        "notes",
        "note",
        "source",
        "retrieved_on",
        "verified_on",
        "effective_from",
        "effective_until",
        "available_from",
        "available_until",
        "from",
        "to",
        "from_ccy",
        "to_ccy",
        "tax_class",
        "tax_class_distribution",
        "tax_class_disposal",
        "probability",
        "frequency",
        "latency_days",
    }
)


class Finding:
    """One error or warning against a data file."""

    def __init__(self, path: Path, table: str, message: str, *, error: bool) -> None:
        self.path = path
        self.table = table
        self.message = message
        self.error = error

    def render(self) -> str:
        level = "error" if self.error else "warning"
        rel = self.path.relative_to(REPO_ROOT)
        where = f"{rel}: [{self.table}]" if self.table else f"{rel}"
        return f"{level}: {where} {self.message}"


def _is_numeric(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _has_observed_value(table: dict[str, Any]) -> bool:
    """True if this table carries at least one observed numeric value."""
    return any(_is_numeric(value) and key not in STRUCTURAL_KEYS for key, value in table.items())


def _check_date_field(
    table: dict[str, Any], key: str, path: Path, name: str, findings: list[Finding]
) -> None:
    raw = table.get(key)
    if raw in (None, ""):
        return
    text = raw.isoformat() if isinstance(raw, dt.date) else str(raw)
    if not DATE_RE.match(text):
        findings.append(
            Finding(
                path,
                name,
                f"{key!r} must be an ISO date (YYYY-MM-DD), got {raw!r}",
                error=True,
            )
        )


def check_table(table: dict[str, Any], path: Path, name: str, findings: list[Finding]) -> None:
    """Validate one table, then recurse into nested tables and arrays of tables."""
    if _has_observed_value(table):
        for field in REQUIRED_WITH_SOURCE:
            if not table.get(field):
                findings.append(
                    Finding(
                        path,
                        name,
                        f"carries observed values but has no {field!r}; "
                        "every rate, fee, yield and premium needs a citation "
                        "(constitution, Principle I)",
                        error=True,
                    )
                )
        if "verified_on" not in table:
            findings.append(
                Finding(
                    path,
                    name,
                    "has no 'verified_on' key; add it (empty is fine -- an unverified "
                    "value must render marked, not be omitted)",
                    error=True,
                )
            )
        elif not table.get("verified_on"):
            findings.append(
                Finding(path, name, "is unverified; it must render visibly marked", error=False)
            )

    for key in ("retrieved_on", "verified_on", "effective_from", "effective_until"):
        _check_date_field(table, key, path, name, findings)

    for key, value in table.items():
        child = f"{name}.{key}" if name else key
        if isinstance(value, dict):
            check_table(value, path, child, findings)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    check_table(item, path, f"{child}[{index}]", findings)


def check_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        # Principle II: a malformed data file fails loudly, naming the file.
        return [Finding(path, "", f"is not valid TOML: {exc}", error=True)]
    check_table(document, path, "", findings)
    return findings


def main() -> int:
    if not DATA_ROOT.is_dir():
        print(f"error: {DATA_ROOT} does not exist")  # noqa: T201
        return 1

    paths = sorted(path for subdir in SOURCED_DIRS for path in (DATA_ROOT / subdir).rglob("*.toml"))

    findings: list[Finding] = []
    for path in paths:
        findings.extend(check_file(path))

    for finding in findings:
        print(finding.render())  # noqa: T201

    errors = sum(1 for finding in findings if finding.error)
    warnings = len(findings) - errors

    print(  # noqa: T201
        f"\nchecked {len(paths)} data file(s) under {', '.join(SOURCED_DIRS)}: "
        f"{errors} error(s), {warnings} unverified value(s)"
    )
    if not paths:
        print(  # noqa: T201
            "note: no curated data files yet -- this gate becomes meaningful as "
            "data/tax, data/instruments and data/routes are populated"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
