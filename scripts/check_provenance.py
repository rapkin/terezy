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
#
# `channels` joined in feature 002: a two-sided rate is the most decision-relevant
# observation in the ramp model, and an uncited premium is exactly the figure that gets
# believed without checking.
#
# `streams` deliberately did **not** join, and the omission is argued rather than
# accidental (contracts/declaration-schema.md, research.md D9): an owner's own salary is
# not an observation needing a citation, it is a statement of fact by the only person who
# can make it -- the same exemption `scenarios` has. That covers `income_tax_rate_pct`
# too: it looks like a tax rate, and it is exempt because it is not a *modelled* rate.
# The tool takes net-of-income-tax amounts as input, and the field exists only so the
# deployable figure is not overstated; a rate the engine applies to a taxable event would
# need a source, and a rate the owner states about his own payslip does not.
SOURCED_DIRS = ("tax", "instruments", "routes", "channels")

REQUIRED_WITH_SOURCE = ("source", "retrieved_on")

# Where the staleness thresholds live, relative to the data root. Every sourced table must
# name a kind declared here (FR-028), and a kind with no threshold is an error: this is the
# mechanical half of "no permissive default". The script still cannot evaluate staleness --
# it has no as-of date and must not invent one -- so it checks that the *declaration* is
# complete and leaves the verdict to the engine.
KINDS_FILE = "observation_kinds.toml"

# The key naming a table's observation kind. A route leg declares `kind_of_observation`,
# because `kind` on a leg is already the *leg* kind (`transfer`, `fx`); every other sourced
# table declares `kind`.
#
# The two cannot simply be tried in order: a leg always has a `kind`, so a leg that forgot
# `kind_of_observation` would be reported as naming the undeclared observation kind
# `transfer` -- a true statement about the wrong field, sending the reader to fix a line
# that is correct. So a leg table is recognised by its *name* and is required to declare
# `kind_of_observation` and nothing else.
KIND_KEY = "kind"
LEG_KIND_KEY = "kind_of_observation"
LEG_TABLE_RE = re.compile(r"\.leg\[\d+\]$")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Keys that are structural rather than observed values.
STRUCTURAL_KEYS = frozenset(
    {
        "id",
        "name",
        "class",
        "kind",
        "kind_of_observation",
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
        # --- feature 002: identifiers and references, not observations ---
        # They must not trip the "this table carries observed values" heuristic, which
        # counts numeric leaves. `index` is the only numeric one, and it is a position in a
        # chain rather than a measurement; the rest are here because the contract names them
        # and because a reader scanning this set should see the whole declaration surface.
        "direction",
        "provider",
        "partner_route",
        "channel",
        "capacity_pool",
        "from_venue",
        "to_venue",
        "cadence",
        "arrives_at",
        "owner_id",
        "index",
        "pair",
        "route_ids",
        "before",
        "after",
        "is_assumption",
        "rationale",
        "redirect_to",
        "observed_on",
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


def declared_kinds(path: Path) -> tuple[frozenset[str], list[Finding]]:
    """The observation kinds `data/observation_kinds.toml` declares, and what is wrong with it.

    Returned as data rather than raised, so a missing or malformed kinds file is one finding
    naming that file instead of one finding per sourced table naming the wrong one.

    A kind with no positive `staleness_days` is an **error**, which is the mechanical half of
    FR-028's "no permissive default": a kind whose threshold nobody set would let every value
    of that kind pass as fresh forever, and a staleness rule that never fires is the silently
    stale value the requirement exists to forbid.
    """
    findings: list[Finding] = []
    if not path.is_file():
        return frozenset(), [
            Finding(
                path,
                "",
                "does not exist, so no sourced table can name a declared observation kind. "
                "It is reported rather than treated as 'nothing ages': every rate in the "
                "repository would then age under a threshold nobody set (FR-028)",
                error=True,
            )
        ]
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        return frozenset(), [Finding(path, "", f"is not valid TOML: {exc}", error=True)]

    kinds: set[str] = set()
    entries = document.get("kind")
    if not isinstance(entries, list) or not entries:
        return frozenset(), [
            Finding(
                path,
                "kind",
                "declares no [[kind]] entries; every sourced table in the repository names "
                "a kind, and none of them could resolve",
                error=True,
            )
        ]
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            findings.append(Finding(path, f"kind[{index}]", "is not a table", error=True))
            continue
        identifier = entry.get("id")
        threshold = entry.get("staleness_days")
        note = entry.get("note")
        if not isinstance(identifier, str) or not identifier.strip():
            findings.append(Finding(path, f"kind[{index}]", "has no 'id'", error=True))
            continue
        kinds.add(identifier)
        if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
            findings.append(
                Finding(
                    path,
                    f"kind[{identifier}]",
                    f"declares staleness_days = {threshold!r}; it must be a positive whole "
                    "number of days. There is no permissive default (FR-028): a kind with "
                    "no threshold would make every value of that kind fresh forever",
                    error=True,
                )
            )
        if not isinstance(note, str) or not note.strip():
            findings.append(
                Finding(
                    path,
                    f"kind[{identifier}]",
                    "has no 'note'; a threshold nobody explained is a number nobody can argue with",
                    error=True,
                )
            )
    return frozenset(kinds), findings


def _check_kind_field(
    table: dict[str, Any],
    path: Path,
    name: str,
    kinds: frozenset[str],
    findings: list[Finding],
) -> None:
    """A sourced table must name a kind, and the kind must be declared (FR-028).

    The two halves are reported separately because the fixes differ: a table with no kind
    needs a line added, and a table naming an undeclared kind is almost always a typo, so the
    message lists what exists.
    """
    key = LEG_KIND_KEY if LEG_TABLE_RE.search(name) else KIND_KEY
    declared = table.get(key)
    named = declared if isinstance(declared, str) and declared.strip() else None
    if named is None:
        findings.append(
            Finding(
                path,
                name,
                f"carries observed values but names no observation kind; add {key!r}. "
                "There is no default staleness threshold: a value ageing under a threshold "
                "nobody set could never be reported stale (FR-028)",
                error=True,
            )
        )
        return
    if named not in kinds:
        findings.append(
            Finding(
                path,
                name,
                f"names the observation kind {named!r}, which data/{KINDS_FILE} does not "
                f"declare. Declared kinds: {sorted(kinds)}",
                error=True,
            )
        )


def check_table(
    table: dict[str, Any],
    path: Path,
    name: str,
    findings: list[Finding],
    kinds: frozenset[str],
) -> None:
    """Validate one table, then recurse into nested tables and arrays of tables."""
    if _has_observed_value(table):
        _check_kind_field(table, path, name, kinds, findings)
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
            check_table(value, path, child, findings, kinds)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    check_table(item, path, f"{child}[{index}]", findings, kinds)


def check_file(path: Path, kinds: frozenset[str]) -> list[Finding]:
    findings: list[Finding] = []
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        # Principle II: a malformed data file fails loudly, naming the file.
        return [Finding(path, "", f"is not valid TOML: {exc}", error=True)]
    check_table(document, path, "", findings, kinds)
    return findings


def main() -> int:
    if not DATA_ROOT.is_dir():
        print(f"error: {DATA_ROOT} does not exist")  # noqa: T201
        return 1

    paths = sorted(path for subdir in SOURCED_DIRS for path in (DATA_ROOT / subdir).rglob("*.toml"))

    kinds, findings = declared_kinds(DATA_ROOT / KINDS_FILE)
    for path in paths:
        findings.extend(check_file(path, kinds))

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
