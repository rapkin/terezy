#!/usr/bin/env python3
"""Print one requested diagram to stdout. A printer, not a program.

FR-021, and owner decision D-B. The generated text lands in exactly two places: golden test
artifacts under ``tests/golden/``, and this script. There is no reports directory, no file
writing and no UI -- the delivery surface is deliberately minimal and recorded as such, and
choosing a real one remains deferred.

**Every decision lives in ``terezy.api.diagrams``**, which is what makes this file worth
almost nothing on its own: it parses arguments, loads the declarations through the same
resolver everything else uses, calls one function, and writes the bytes. If a diagram is
wrong, nothing here is the reason.

Usage::

    scripts/render_diagram.py graph --regime wartime --mode topology
    scripts/render_diagram.py graph --regime wartime --mode declared-figures
    scripts/render_diagram.py path --regime wartime --route monobank_to_binance_p2p \\
        --stream salary_uah --destination binance --amount 10000

**The only clock in this feature is ``--as-of``'s default, and the date it resolves to is
printed on the face of every diagram.** The library never reads a clock: ``as_of`` decides
staleness and is an input to the run (``core.primitives.staleness``), so a diagram rendered
today and the same diagram rendered next week differ exactly as their staleness marks differ,
and both say which day they were assessed against. Pass ``--as-of`` to pin it; the golden
suite always does, which is what makes SC-011's "the script prints byte-identically to what
the suite regenerates" a claim about the renderer rather than about the calendar.

**A refusal is not printed as a diagram.** ``NothingToDraw`` goes to stderr with its reason
and exits non-zero, so a shell pipeline cannot capture an empty picture and believe it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from terezy.api.diagrams import (  # noqa: E402
    Diagram,
    Mode,
    NothingToDraw,
    render_graph,
    render_path,
)
from terezy.core.primitives import provenance as prov  # noqa: E402
from terezy.core.primitives.currency import Currency  # noqa: E402
from terezy.core.primitives.money import Money  # noqa: E402
from terezy.core.routes import cost  # noqa: E402
from terezy.core.routes.path import FundingPath  # noqa: E402
from terezy.core.scenarios.regimes import Regime  # noqa: E402
from terezy.data.declarations import resolver  # noqa: E402

DATA_ROOT = REPO_ROOT / "data"

MODES = {"topology": Mode.TOPOLOGY, "declared-figures": Mode.DECLARED_FIGURES}
"""The command-line spelling of each mode. Short, because a reader types it; the diagram
itself carries the enum's own longer name (FR-006)."""

REFUSED = 2
"""Exit status for a typed refusal. Distinct from 1, which argparse uses for a bad argument:
"this route cannot carry your money" and "you mistyped a flag" are different outcomes."""


def _today() -> date:
    """The default as-of date.

    A clock, in a script, and nowhere else. The core is pure and the renderer takes ``as_of``
    as data; this is the one place a default has to come from, and the resolved value is
    printed on the diagram so no reader has to guess which day the marks were assessed on.
    """
    return datetime.now(UTC).date()


def _declarations(root: Path) -> resolver.RampDeclarations:
    return resolver.ramp_from_data_root(root, base_currency=Currency.UAH)


def _regime(declared: resolver.RampDeclarations, scenario_id: str | None, regime_id: str) -> Regime:
    """The named regime, or a loud failure naming what is declared.

    ``--scenario`` may be omitted while exactly one scenario is declared. With two, it is
    required: picking one would be choosing which of the owner's beliefs to draw.
    """
    if scenario_id is None:
        if len(declared.scenarios) != 1:
            raise SystemExit(
                f"--scenario is required: {len(declared.scenarios)} scenarios are declared "
                f"({sorted(declared.scenarios)})"
            )
        scenario_id = next(iter(declared.scenarios))
    if scenario_id not in declared.scenarios:
        raise SystemExit(
            f"no scenario {scenario_id!r} is declared. Known: {sorted(declared.scenarios)}"
        )
    scenario = declared.scenarios[scenario_id]
    for regime in scenario.regimes:
        if regime.id == regime_id:
            return regime
    raise SystemExit(
        f"scenario {scenario_id!r} declares no regime {regime_id!r}. "
        f"Known: {[regime.id for regime in scenario.regimes]}"
    )


def _graph(args: argparse.Namespace) -> Diagram | NothingToDraw:
    declared = _declarations(args.data_root)
    return render_graph(
        venues=declared.venues,
        routes=declared.routes,
        channels=declared.channels,
        regime=_regime(declared, args.scenario, args.regime),
        mode=MODES[args.mode],
        kinds=declared.kinds,
        as_of=args.as_of,
    )


def _path(args: argparse.Namespace) -> Diagram | NothingToDraw:
    declared = _declarations(args.data_root)
    result = cost.cost_one(
        FundingPath(destination_id=args.destination, stream_id=args.stream, route_id=args.route),
        Money(args.amount, Currency(args.currency), prov.EMPTY),
        routes=declared.routes,
        channels=declared.channels,
        streams=declared.streams,
        kinds=declared.kinds,
        on_date=args.on_date or args.as_of,
        as_of=args.as_of,
    )
    return render_path(
        result,
        routes=declared.routes,
        regime=_regime(declared, args.scenario, args.regime),
    )


def _common() -> argparse.ArgumentParser:
    """The options both subcommands take.

    Declared once and shared through ``parents=`` rather than added to the top-level parser,
    so that every option follows its subcommand -- ``graph --regime x --as-of y`` reads as one
    request, and a global flag before the subcommand would be a second place to look.
    """
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--data-root", type=Path, default=DATA_ROOT)
    shared.add_argument("--scenario", default=None)
    shared.add_argument("--regime", required=True)
    shared.add_argument("--as-of", type=date.fromisoformat, default=_today())
    return shared


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subcommands = parser.add_subparsers(dest="kind", required=True)
    shared = _common()

    graph = subcommands.add_parser(
        "graph", parents=[shared], help="the declared route graph for one regime"
    )
    graph.add_argument("--mode", choices=sorted(MODES), required=True)
    graph.set_defaults(render=_graph)

    path = subcommands.add_parser("path", parents=[shared], help="one costed ramp result")
    path.add_argument("--route", required=True)
    path.add_argument("--stream", required=True)
    path.add_argument("--destination", required=True)
    path.add_argument("--amount", type=float, required=True)
    path.add_argument("--currency", default=Currency.UAH.value, choices=[c.value for c in Currency])
    path.add_argument("--on-date", type=date.fromisoformat, default=None)
    path.set_defaults(render=_path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rendered = args.render(args)
    if isinstance(rendered, NothingToDraw):
        sys.stderr.write(f"NOTHING TO DRAW ({rendered.kind}): {rendered.reason}\n")
        return REFUSED
    sys.stdout.write(rendered.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
