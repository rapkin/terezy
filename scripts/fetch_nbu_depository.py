#!/usr/bin/env python3
"""Fetch the National Bank's depository register of government securities as an observation.

**This script retrieves. It does not verify, and it does not declare.** The first half is
``fetch_cpi.py``'s rule -- every figure carries its ``source`` and its ``retrieved_on`` and an
**empty** ``verified_on``, because a number that was downloaded is not a number anyone has
checked. The second is ``fetch_inzhur.py``'s, and it binds harder here: the register states an
issue's terms so completely that transcribing one into a declaration looks mechanical, and it
is not. Fifteen of the twenty-four schedules a seller publishes for these same issues are one
day off this register and two are simply wrong; only a human comparing two published lists
finds that.

The source
----------
``https://bank.gov.ua/depo_securities?json&date=YYYYMMDD`` -- the depository record for
government securities, ``emit_name`` «Міністерство фінансів України» on every issue. It states
the currency, the nominal, the payment kinds and the whole schedule from placement to maturity.

**The ``date`` parameter selects nothing.** Measured 2026-08-31: ``date=20200101``,
``date=20260830``, ``date=20260831`` and the bare ``?json`` return byte-identical payloads. So
this writes what it retrieved on the day it retrieved it, and never "the register as of" some
other date. Nobody should build a historical query on that parameter.

**Terms of use.** Стаття 10¹ ч. 2 Закону України «Про доступ до публічної інформації»
(№ 2939-VI) permits free reuse, including commercial, «з обов'язковим посиланням на джерело
отримання такої інформації». Carrying the endpoint URL in every citation is that reference. The
hyperlink wording belongs to п. 17 Положення № 835, which prescribes a notice the *publisher*
displays, and is not a second duty on a reuser.

What is taken, and what is deliberately left
--------------------------------------------
Taken: the whole register, every issue and every payment row. Filtering to the issues somebody
happens to want would encode a judgement in a fetcher, and it would break the one check that
needs this file -- an issue a seller lists and the register does **not** can only be seen
against the register's whole membership.

Left: nothing. Every scalar the endpoint publishes per issue is written, so a later reading can
ask a question nobody has thought of yet without a re-fetch changing the answer.

Usage
-----
    uv run python scripts/fetch_nbu_depository.py --dry-run   # report and diff, write nothing
    uv run python scripts/fetch_nbu_depository.py             # write the observation

The file is built in memory, written to a temporary path and moved into place, so a failed run
leaves the previous observation exactly as it was.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any, Final

ENDPOINT: Final = "https://bank.gov.ua/depo_securities?json"
"""Without the ``date`` parameter, because it selects nothing (see the module docstring) and a
citation carrying an inert parameter invites a reader to believe it did something."""

USER_AGENT: Final = (
    "terezy/fetch_nbu_depository (single-user personal finance tool; contact via repository)"
)
TIMEOUT_SECONDS: Final = 60

OUTPUT: Final = pathlib.Path("data/observations/nbu_depository.toml")

SCALARS: Final = (
    "nominal",
    "auk_proc",
    "pay_period",
)
"""The numeric terms every issue states, written in the order the endpoint states them."""

OPTIONAL_SCALARS: Final = ("total_bonds",)
"""A number the endpoint sometimes publishes as ``null`` -- nine foreign-law issues, measured
2026-08-31. An absent count is written as an absent key rather than as zero: a register that
does not say how many were issued has not said none were."""

LABELS: Final = (
    "val_code",
    "cptype",
    "cpdescr",
    "cptype_nkcpfr",
    "cpcode_cfi",
    "emit_okpo",
    "emit_name",
)
"""The stated words. ``val_code`` is the one that ended a four-year-old inference: the currency
is published, not read off the issuer's nationality."""

DATES: Final = ("razm_date", "pgs_date")


class FetchError(RuntimeError):
    """The endpoint did not answer, or answered with something this script cannot read."""


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as error:
        raise FetchError(f"{url}: {error}") from error


def register(raw: bytes) -> list[dict[str, Any]]:
    """The register as a list of issues, or a loud refusal.

    Every shape fault stops the run rather than writing a thinner file: an observation missing
    issues reads exactly like a register that lost them.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise FetchError(f"{ENDPOINT}: response is not JSON: {error}") from error
    if not isinstance(payload, list) or not payload:
        raise FetchError(f"{ENDPOINT}: expected a non-empty list, got {type(payload).__name__}")
    seen: set[str] = set()
    for issue in payload:
        if not isinstance(issue, dict):
            raise FetchError(f"{ENDPOINT}: an entry is a {type(issue).__name__}, not an object")
        code = issue.get("cpcode")
        if not isinstance(code, str) or not code:
            raise FetchError(f"{ENDPOINT}: an entry has no cpcode; nothing names it")
        if code in seen:
            raise FetchError(
                f"{ENDPOINT}: two entries share the cpcode {code!r}. An ISIN is what a "
                "declaration is keyed by, so a duplicate makes every lookup ambiguous."
            )
        seen.add(code)
        payments = issue.get("payments")
        if not isinstance(payments, list) or not payments:
            raise FetchError(f"{ENDPOINT}: {code} publishes no payments")
        for row in payments:
            if not isinstance(row, dict):
                raise FetchError(f"{ENDPOINT}: {code} has a payment row that is not an object")
            for field in ("pay_date", "pay_type", "pay_val"):
                if row.get(field) is None:
                    raise FetchError(f"{ENDPOINT}: {code} has a payment row with no {field!r}")
    return payload


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _scalar(value: Any) -> str:
    """A number as TOML, keeping the endpoint's own integer-versus-float distinction."""
    if isinstance(value, bool):
        raise FetchError(f"a boolean where a number was expected: {value!r}")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    raise FetchError(f"a {type(value).__name__} where a number was expected: {value!r}")


def render(issues: list[dict[str, Any]], *, today: datetime.date) -> str:
    stamp = today.isoformat()
    issue_source = (
        f"{ENDPOINT} — the National Bank of Ukraine's depository register of government "
        f"securities, retrieved {stamp} by scripts/fetch_nbu_depository.py. The ISSUER's own "
        "record through its depository: «Міністерство фінансів України» is named on every "
        "entry. Reused under ст. 10¹ ч. 2 Закону України «Про доступ до публічної інформації» "
        "(№ 2939-VI), whose condition is a reference to the source — this URL is that "
        "reference."
    )
    lines = [
        "# The NBU depository's register of government securities, as observed.",
        "# GENERATED — do not edit by hand.",
        "#",
        "# Written by scripts/fetch_nbu_depository.py. Re-run it instead of editing, and read",
        "# the diff: a term that moved is the point of keeping this file.",
        "#",
        "# THIS IS AN OBSERVATION FILE, NOT A DECLARATION. Nothing here is wired into the",
        "# engine. It exists so a declaration under data/instruments/ can be checked against",
        "# what the issuer's depository actually publishes, and so the check has a date on it.",
        "#",
        "# THE WHOLE REGISTER, not the issues anybody wanted. An issue a seller lists as active",
        "# and this register does not list is a refusal to declare, and only the whole",
        "# membership can witness an absence.",
        "#",
        "# Every verified_on is empty and must stay empty until a human compares the value",
        "# against the source. A downloaded number is not a checked number.",
        "",
        f'retrieved_on = "{stamp}"',
        f'endpoint     = "{ENDPOINT}"',
        "",
    ]
    for issue in issues:
        code = str(issue["cpcode"])
        lines.append("[[issue]]")
        lines.append(f'isin   = "{_escape(code)}"')
        for field in DATES:
            lines.append(f'{field:<6} = "{_escape(str(issue[field]))}"')
        for field in SCALARS:
            lines.append(f"{field:<12} = {_scalar(issue[field])}")
        for field in OPTIONAL_SCALARS:
            if issue.get(field) is not None:
                lines.append(f"{field:<12} = {_scalar(issue[field])}")
        for field in LABELS:
            lines.append(f'{field:<14} = "{_escape(str(issue[field]))}"')
        lines.append('kind         = "bond_terms"')
        lines.append(f'source       = "{_escape(issue_source)}"')
        lines.append(f'retrieved_on = "{stamp}"')
        lines.append('verified_on  = ""')
        for row in issue["payments"]:
            # Its own table because it carries its own observed amount, and the gate is right
            # to want a citation on each. `pay_type` is the ISSUER's label for the kind, which
            # is the whole reason a declaration need not read a kind off an amount or a date.
            lines.append("  [[issue.payment]]")
            lines.append(f'  pay_date     = "{_escape(str(row["pay_date"]))}"')
            lines.append(f'  pay_type     = "{_escape(str(row["pay_type"]))}"')
            lines.append(f"  pay_val      = {_scalar(row['pay_val'])}")
            lines.append('  kind         = "bond_terms"')
            lines.append(
                f'  source       = "{ENDPOINT} — payment row published for {_escape(code)}, '
                f'retrieved {stamp}. See the file header."'
            )
            lines.append(f'  retrieved_on = "{stamp}"')
            lines.append('  verified_on  = ""')
        lines.append("")
    return "\n".join(lines)


def _write(text: str, path: pathlib.Path) -> None:
    """Atomically, so a failed run never leaves half a file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(handle, "w", encoding="utf-8") as file:  # noqa: PTH123 -- an fd, not a path
            file.write(text)
        pathlib.Path(temporary).replace(path)
    except BaseException:
        pathlib.Path(temporary).unlink(missing_ok=True)
        raise


def report(issues: list[dict[str, Any]]) -> None:
    rows = sum(len(issue["payments"]) for issue in issues)
    currencies = sorted({str(issue["val_code"]) for issue in issues})
    print(  # noqa: T201
        f"{len(issues)} issue(s); {rows} payment row(s); currencies {', '.join(currencies)}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args(argv)
    try:
        issues = register(_get(ENDPOINT))
    except FetchError as error:
        print(f"fetch failed: {error}", file=sys.stderr)  # noqa: T201
        return 1
    report(issues)
    text = render(issues, today=datetime.date.today())  # noqa: DTZ011
    if args.dry_run:
        print(f"--dry-run: {len(text.splitlines())} line(s) not written", file=sys.stderr)  # noqa: T201
        return 0
    _write(text, OUTPUT)
    print(f"wrote {OUTPUT}", file=sys.stderr)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
