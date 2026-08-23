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
# therefore require a citation.
#
# `channels` joined in feature 002: a two-sided rate is the most decision-relevant
# observation in the ramp model, and an uncited premium is exactly the figure that gets
# believed without checking.
SOURCED_DIRS = ("tax", "instruments", "routes", "channels")

# The directories exempt from the citation requirement, each BY NAME and WITH ITS REASON.
# Together with SOURCED_DIRS this list is exhaustive: a directory under data/ that appears
# in neither is an **error**, never a blind spot. The gate used to be an allowlist, which
# is fail-open -- the place a future rate was most likely to land (a new directory) was
# exactly the place the gate could not see.
EXEMPT_DIRS: dict[str, str] = {
    "scenarios": (
        "the owner's own stated beliefs -- regimes, transitions, event probabilities. An "
        "assumption needs a label and a visible consequence, not a source (data/README.md)"
    ),
    "objectives": (
        "the owner's own objective and constraint sets -- stated preferences, not "
        "observations (data/README.md)"
    ),
    "strategies": (
        "the owner's own named allocations -- decisions, not observations. A strategy "
        "file that ever carries a market observation must move that value into a sourced "
        "directory rather than widen this exemption"
    ),
    "streams": (
        "an owner's own salary is a statement of fact by the only person who can make it, "
        "income_tax_rate_pct included: the tool takes net-of-income-tax amounts as input "
        "and the field exists only so the deployable figure is not overstated. A rate the "
        "engine applies to a taxable event needs a source; a rate the owner states about "
        "his own payslip does not (contracts/declaration-schema.md, data/README.md)"
    ),
    "composition": (
        "the owner's own policy on how far a search may run -- how many declared routes may "
        "be chained into one candidate. Nothing here describes the world, so there is nothing "
        "for a source to vouch for: it is the same exemption `objectives` and `strategies` "
        "carry, and for the same reason. Every *number* that describes a corridor lives on a "
        "leg, in data/routes/, cited (004 research.md D8)"
    ),
    "spendable": (
        "the owner's own statement of where he spends -- a venue id and a currency code, "
        "and nothing a source could vouch for. It is the same exemption `streams` has and "
        "for the same reason: where a person's money counts as having come back out is a "
        "fact about his life rather than an observation of the world. Every *number* "
        "attached to a venue lives on a leg, in data/routes/, cited (003 research.md D4)"
    ),
    "user": (
        "gitignored per-user data -- what a *run produces* rather than what a person declares: "
        "results, caches, scratch output. Never curated, never committed, and outside this gate "
        "by the Principle VII boundary. The owner's own declarations are committed and live in "
        "the per-owner directories above (008 research.md D2)"
    ),
    # --- feature 008: the owner's own holdings and targets ---
    "seeds": (
        "the owner's own opening lots -- what he already holds, what he paid, and whether he "
        "knows the price or is stating it from memory. What a person paid for a lot is his own "
        "record rather than an observation of the world, so there is nothing for a source to "
        "vouch for: the same exemption `objectives`, `strategies`, `streams` and `spendable` "
        'carry. A cost he is unsure of is not uncited, it is *marked* -- `basis = "estimated"` '
        "puts a propagating mark on the gain and on the tax charged on it, which is the honest "
        "answer where a citation is not available to anybody (008 research.md D2). If a market "
        "*value* ever has to live here it moves to a sourced directory rather than this "
        "exemption widening to cover it"
    ),
    "goals": (
        "the owner's own targets -- a sum, a date, a contribution. A target is a decision, not "
        "an observation, so there is nothing for a source to vouch for: the same exemption "
        "`objectives` and `strategies` carry, and for the same reason. The growth assumption a "
        "goal is evaluated against is deliberately *not* declared here (008 FR-012); it is an "
        "input carrying its own provenance, so no rate this gate would want to check ever "
        "lands in this directory"
    ),
}

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
        try:
            rel: Path | str = self.path.relative_to(REPO_ROOT)
        except ValueError:
            # A data root outside the repository -- a test's scratch copy. The absolute
            # path is the honest rendering there.
            rel = self.path
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


def unknown_directories(data_root: Path) -> list[Finding]:
    """Every directory under the data root that is neither scanned nor exempted by name.

    The fail-closed rule. An allowlist alone is fail-open: a new directory holding an
    uncited rate would pass clean until somebody remembered to list it, and a gate that
    passes over what it never looked at is the silent default the constitution puts at top
    severity -- in the script whose job is to prevent exactly that.
    """
    return [
        Finding(
            entry,
            "",
            "is a directory this gate does not know. Every directory under data/ must be "
            "named: in SOURCED_DIRS if its numeric values are observations needing a "
            "citation, or in EXEMPT_DIRS with the reason they do not. An unlisted "
            "directory is an error, never a blind spot -- a gate that passes over what it "
            "never looked at is fail-open.",
            error=True,
        )
        for entry in sorted(data_root.iterdir())
        if entry.is_dir() and entry.name not in SOURCED_DIRS and entry.name not in EXEMPT_DIRS
    ]


def main(argv: list[str] | None = None) -> int:
    """Check a data root -- the repository's by default, or the one argv names.

    The optional argument exists so the gate itself is testable against a scratch copy
    (``tests/contract/test_provenance_gate.py``); CI and the docs invoke it bare.
    """
    args = sys.argv[1:] if argv is None else argv
    data_root = Path(args[0]).resolve() if args else DATA_ROOT
    if not data_root.is_dir():
        print(f"error: {data_root} does not exist")  # noqa: T201
        return 1

    # Root-level files are scanned too, fail-closed: venues.toml lives at the root and
    # carries no observed numeric value today -- and it has to be *looked at* for that to
    # mean anything. The kinds file is excluded here because declared_kinds below is its
    # own, stricter validator (its numeric leaf is a threshold policy, not an observation).
    root_files = sorted(path for path in data_root.glob("*.toml") if path.name != KINDS_FILE)
    paths = (
        sorted(path for subdir in SOURCED_DIRS for path in (data_root / subdir).rglob("*.toml"))
        + root_files
    )

    kinds, findings = declared_kinds(data_root / KINDS_FILE)
    findings.extend(unknown_directories(data_root))
    for path in paths:
        findings.extend(check_file(path, kinds))

    for finding in findings:
        print(finding.render())  # noqa: T201

    errors = sum(1 for finding in findings if finding.error)
    warnings = len(findings) - errors

    print(  # noqa: T201
        f"\nchecked {len(paths)} data file(s) under {', '.join(SOURCED_DIRS)} "
        f"and the data root: {errors} error(s), {warnings} unverified value(s)"
    )
    if not paths:
        print(  # noqa: T201
            "note: no curated data files yet -- this gate becomes meaningful as "
            "data/tax, data/instruments and data/routes are populated"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
