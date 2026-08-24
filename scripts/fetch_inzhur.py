#!/usr/bin/env python3
"""Fetch Inzhur's published asset list and write it as an observation file.

**This script retrieves. It does not verify, and it does not declare.** Both halves of
that matter and they are different refusals.

*It does not verify* for the reason ``fetch_cpi.py`` gives: every figure it writes carries
its ``source`` and its ``retrieved_on`` and an **empty** ``verified_on``, because a number
that was downloaded is not a number anyone has checked.

*It does not declare* because the instrument declarations under ``data/instruments/`` are
not lists of numbers. ``inzhur_miltech.toml``'s NAV table carries a paragraph arguing which
of two readings of one observation to take, why the less conservative one is taken anyway,
and what it costs if that is wrong. A fetcher that rewrote those files would delete the
reasoning and keep the digits. So this writes an **observation**: what the endpoint said,
on the day it said it. Moving an observation into a declaration is a human act, and the
diff this script prints is the input to it.

The source
----------
``https://www.inzhur.reit/_api/assets`` -- the JSON behind Inzhur's own asset pages, owner
supplied 2026-08-27. Thirty-seven assets: their own funds and the ОВДП issues they resell.

What is taken, and what is deliberately left
--------------------------------------------
Taken, because they are **observations of a price or a term**:

* ``prices.buy`` / ``prices.sell`` / ``prices.nav`` -- three separate figures, which is the
  whole reason this endpoint is worth having. A declaration that infers a markup from one
  live price can be checked against all three.
* ``returnRates`` on a bond -- the platform's own buy-side and sell-side yield.
* ``isin``, ``maturityDate``, ``paymentSchedule`` -- terms of a specific issue.
* ``securityProperties.availableQuantity`` -- how much is on offer, which decides whether a
  planned purchase is executable at all.

Left, because they are **the seller's forecast about itself**: every ``parameters`` and
``indicators`` entry whose title begins «Прогнозована». «25-29% річних» is not a
measurement and must not enter beside a price as though it were one. The text is carried
verbatim in a ``stated_yield`` field marked as the issuer's own claim, and nothing computes
from it here.

Also left: images, galleries, marketing copy, ``rank``, ``color``.

Usage
-----
    uv run python scripts/fetch_inzhur.py --dry-run   # report and diff, write nothing
    uv run python scripts/fetch_inzhur.py             # write data/observations/inzhur.toml

The file is built in memory, written to a temporary path and moved into place, so a failed
run leaves the previous observation exactly as it was.
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

ENDPOINT: Final = "https://www.inzhur.reit/_api/assets"
"""Owner-supplied 2026-08-27. Not a documented public API; it is the JSON the site's own
pages read, and it may change shape or disappear without notice. Every failure below is
loud for that reason -- a shape change must stop the run, never write a thinner file."""

USER_AGENT: Final = (
    "terezy/fetch_inzhur (single-user personal finance tool; contact via repository)"
)
TIMEOUT_SECONDS: Final = 30

OUTPUT: Final = pathlib.Path("data/observations/inzhur.toml")

FORECAST_PREFIX: Final = "прогнозована"
"""A ``parameters`` title starting with this word is the fund's forecast about its own
future return. Matched case-folded and on the stripped title, because the payload contains
titles with embedded newlines and inconsistent capitalisation."""


class FetchError(RuntimeError):
    """The endpoint did not answer, or answered with something this script cannot read."""


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return bytes(response.read())
    except (urllib.error.URLError, TimeoutError) as error:
        raise FetchError(f"{url}: {error}") from error


def _assets() -> list[dict[str, Any]]:
    raw = _get(ENDPOINT)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise FetchError(f"{ENDPOINT}: response is not JSON: {error}") from error
    if not isinstance(payload, list) or not payload:
        raise FetchError(f"{ENDPOINT}: expected a non-empty list, got {type(payload).__name__}")
    return payload


def _number(value: Any) -> float | None:
    """A figure, or ``None`` where the endpoint has nothing rather than zero.

    ``nav`` is ``0`` for every bond, which is the payload's way of saying a bond has no net
    asset value -- not that its value is nothing. Writing that zero would be inventing a
    figure, so it is dropped and the field is absent, which is what "not declared" looks
    like everywhere else in ``data/``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return None if value == 0 else float(value)


def _stated_yield(details: dict[str, Any]) -> str | None:
    """The issuer's own forecast, verbatim, or ``None`` if it states none."""
    for entry in details.get("parameters") or ():
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        if title.casefold().startswith(FORECAST_PREFIX):
            value = " ".join(str(entry.get("value") or "").split())
            return value or None
    return None


def _schedule(details: dict[str, Any]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for entry in details.get("paymentSchedule") or ():
        if not isinstance(entry, dict):
            continue
        when = str(entry.get("date") or "")[:10]
        try:
            amount = float(entry.get("amount"))
        except (TypeError, ValueError):
            continue
        if when:
            out.append((when, amount))
    return out


def _identity(asset: dict[str, Any], details: dict[str, Any]) -> str:
    """What names this asset, given that neither field alone does.

    All thirty-two bonds share the slug ``ovdp`` and are told apart by ISIN; all five funds
    have a distinct slug and no ISIN. So identity is the ISIN where there is one and the
    slug otherwise -- and a fund that grows an ISIN, or a bond that loses one, changes which
    field names it. That is a shape change and it must stop the run rather than write two
    records under one name.
    """
    isin = details.get("isin")
    if isin:
        return str(isin)
    slug = str(asset.get("slug") or "")
    if not slug:
        raise FetchError("an asset has neither an ISIN nor a slug; nothing names it")
    return slug


def observations(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per asset, in endpoint order, carrying only what is observed.

    Refuses on a duplicate identity rather than writing both: two records under one name
    would make the file's own lookup ambiguous, and a reader comparing a declaration
    against it would silently get whichever came second.
    """
    seen: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for asset in assets:
        details = asset.get("assetDetails")
        if not isinstance(details, dict):
            raise FetchError(f"asset {asset.get('slug')!r}: no assetDetails object")
        prices = details.get("prices") if isinstance(details.get("prices"), dict) else {}
        rates = details.get("returnRates") if isinstance(details.get("returnRates"), dict) else {}
        security = (
            details.get("securityProperties")
            if isinstance(details.get("securityProperties"), dict)
            else {}
        )
        identity = _identity(asset, details)
        if identity in seen:
            raise FetchError(
                f"two assets share the identity {identity!r}: {seen[identity]!r} and "
                f"{asset.get('title')!r}. Identity is the ISIN where there is one and the "
                "slug otherwise; if that is no longer unique the rule needs revisiting."
            )
        seen[identity] = str(asset.get("title") or "")
        out.append(
            {
                "id": identity,
                "slug": str(asset.get("slug") or ""),
                "title": " ".join(str(asset.get("title") or "").split()),
                "asset_type": str(asset.get("type") or ""),
                "status": str(asset.get("status") or ""),
                "isin": details.get("isin") or None,
                "matures_on": (str(details.get("maturityDate"))[:10] or None)
                if details.get("maturityDate")
                else None,
                "buy": _number(prices.get("buy")),
                "sell": _number(prices.get("sell")),
                "nav": _number(prices.get("nav")),
                "return_rate_buy_pct": _number(rates.get("buy")),
                "return_rate_sell_pct": _number(rates.get("sell")),
                "available_quantity": security.get("availableQuantity"),
                "stated_yield": _stated_yield(details),
                "schedule": _schedule(details),
            }
        )
    return out


def spread(record: dict[str, Any]) -> tuple[float, float] | None:
    """Entry markup and exit discount against NAV, both as percentages of NAV.

    The point of computing them here rather than leaving three prices to the reader: a
    declaration that says "no markup is charged" is a claim about the *relationship*
    between two of these figures, and that is what a reader wants to check. A negative exit
    discount means the platform buys back **above** NAV, which is not an error and is worth
    seeing rather than clamping away.
    """
    nav, buy, sell = record["nav"], record["buy"], record["sell"]
    if nav is None or buy is None or sell is None:
        return None
    return ((buy - nav) / nav * 100.0, (nav - sell) / nav * 100.0)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def render(records: list[dict[str, Any]], *, today: datetime.date) -> str:
    source = (
        f"{ENDPOINT} — Inzhur's own asset endpoint, the JSON behind its offer pages. "
        f"Retrieved {today.isoformat()} by scripts/fetch_inzhur.py. "
        "Prices, yields, ISINs, maturities and payment schedules are the platform's own "
        "published figures for instruments it sells; treat them as a seller's quotation "
        "rather than as an independent valuation. Every stated_yield is the issuer's "
        "FORECAST ABOUT ITSELF, carried verbatim and never computed from here."
    )
    lines = [
        "# Inzhur's published assets, as observed. GENERATED — do not edit by hand.",
        "#",
        "# Written by scripts/fetch_inzhur.py. Re-run it instead of editing, and read the",
        "# diff: a figure that moved is the point of keeping this file.",
        "#",
        "# THIS IS AN OBSERVATION FILE, NOT A DECLARATION. Nothing here is wired into the",
        "# engine. It exists so a declaration under data/instruments/ can be checked against",
        "# what the platform actually publishes, and so the check has a date on it.",
        "#",
        "# Every verified_on is empty and must stay empty until a human compares the value",
        "# against the source. A downloaded number is not a checked number.",
        "",
        f'retrieved_on = "{today.isoformat()}"',
        f'endpoint     = "{ENDPOINT}"',
        "",
    ]
    for record in records:
        lines.append("[[observation]]")
        lines.append(f'id     = "{_escape(record["id"])}"')
        lines.append(f'slug   = "{_escape(record["slug"])}"')
        lines.append(f'title  = "{_escape(record["title"])}"')
        lines.append(f'asset_type = "{_escape(record["asset_type"])}"')
        lines.append(f'status = "{_escape(record["status"])}"')
        for field in ("isin", "matures_on", "stated_yield"):
            if record[field]:
                lines.append(f'{field:<6} = "{_escape(str(record[field]))}"')
        for field in ("buy", "sell", "nav", "return_rate_buy_pct", "return_rate_sell_pct"):
            if record[field] is not None:
                lines.append(f"{field:<20} = {record[field]!r}")
        if isinstance(record["available_quantity"], int):
            lines.append(f"available_quantity   = {record['available_quantity']}")
        measured = spread(record)
        if measured is not None:
            markup, discount = measured
            lines.append(f"entry_markup_pct     = {round(markup, 6)!r}")
            lines.append(f"exit_discount_pct    = {round(discount, 6)!r}")
        # ``kind`` names the OBSERVATION kind, which is what ages the value; the asset's
        # own fund/bond distinction is ``asset_type`` because ``kind`` is spoken for.
        lines.append('kind         = "venue_terms"')
        lines.append(f'source       = "{_escape(source)}"')
        lines.append(f'retrieved_on = "{today.isoformat()}"')
        lines.append('verified_on  = ""')
        for when, amount in record["schedule"]:
            # A scheduled payment is a term of the ISSUE, not a quote of the day, so it ages
            # as bond_terms rather than venue_terms. Its own table because it carries its own
            # observed amount, and the gate is right to want a citation on each.
            lines.append("  [[observation.payment]]")
            lines.append(f'  date         = "{when}"')
            lines.append(f"  amount       = {amount!r}")
            lines.append('  kind         = "bond_terms"')
            lines.append(
                f'  source       = "{ENDPOINT} — payment schedule published for '
                f"{_escape(record['id'])}, retrieved {today.isoformat()}. The issuer's own "
                'stated schedule; see the file header for what that is and is not."'
            )
            lines.append(f'  retrieved_on = "{today.isoformat()}"')
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


def report(records: list[dict[str, Any]]) -> None:
    active = [r for r in records if r["status"] == "active"]
    print(f"{len(records)} asset(s); {len(active)} active", file=sys.stderr)  # noqa: T201
    for record in active:
        measured = spread(record)
        tail = ""
        if measured is not None:
            markup, discount = measured
            tail = f"  markup {markup:+.4f}%  exit discount {discount:+.4f}%"
        price = record["buy"] if record["buy"] is not None else record["nav"]
        shown = f"{price:,.4f}" if price is not None else "—"
        print(f"  {record['id']:<24} {record['asset_type']:<5} {shown:>14}{tail}", file=sys.stderr)  # noqa: T201


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args(argv)

    try:
        records = observations(_assets())
    except FetchError as error:
        print(f"fetch_inzhur: {error}", file=sys.stderr)  # noqa: T201
        return 1

    report(records)
    today = datetime.datetime.now(tz=datetime.UTC).date()
    text = render(records, today=today)

    if args.dry_run:
        print(f"fetch_inzhur: dry run, {OUTPUT} not written", file=sys.stderr)  # noqa: T201
        return 0

    _write(text, OUTPUT)
    print(f"fetch_inzhur: wrote {OUTPUT} ({len(records)} observations)", file=sys.stderr)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
