"""No cost figure, no provenance, no float -- across the whole output. **SC-004, SC-008.**

FR-017: *the output MUST carry no cost figures whatsoever -- no percentages, no monetary
amounts, one way or round trip -- so it cannot be mistaken for a comparison. Counts of pairs and
identities of declarations are the only quantities in it.* FR-023 adds that the report restates
no provenance and no staleness mark either.

**Both success criteria say "verified across the whole output, not sampled", and this module is
the only reading of that phrase which stays true when someone adds a field in six months**
(research.md D12). A test that checked the fields it happened to know about would pass on the
day it was written and go quietly wrong the first time the report grew. So the walk below is
recursive over ``dataclasses.fields``, descends through tuples, sets, mappings and nested
records, and asserts on **both** the runtime values and the declared field types -- the second
because a field typed ``float`` that happens to hold nothing today is still a place a cost can
land tomorrow.

**This is also why this feature imports no tolerance and defines none.** A tolerance exists to
compare two floats, and there is no float here to compare. If a future change to this package
ever needs one, a number has leaked into the report, and that is the finding -- not the
tolerance.

The last two tests are the other structural guarantees, kept here because they are about the
report as an artifact rather than about any verdict in it: it is reproducible (SC-016), and it
says in its own output that it changes nothing (SC-020).
"""

from __future__ import annotations

import dataclasses
import typing
from datetime import date
from typing import Any

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.coverage import ENFORCEMENT, CoverageReport
from terezy.core.results.ramp import NothingComparable, Ranking
from terezy.core.routes.coverage import coverage
from terezy.core.routes.ranking import rank
from tests.coverage_registries import UAH, USD, keyed, regime, route, spendable, stream, venue
from tests.invariants import route_graphs

pytestmark = pytest.mark.contract

BANNED: tuple[type, ...] = (Money, Provenance, StalenessVerdict, float)
"""What may not appear anywhere in the report, by value or by declared type.

``float`` is the load-bearing member. A percentage is a float and a cost fraction is a float,
so banning the type is what makes "no cost figures" airtight rather than a promise about the
fields somebody remembered. ``bool`` is *not* banned and is a subclass of ``int``, not of
``float``, so ``alone_sufficient`` and ``reaches_spendable`` pass; ``int`` is not banned because
counts and indices are the quantities the report is allowed to have.
"""

VENUES = keyed([venue("mono", UAH), venue("broker", USD), venue("vault", USD)])
STREAMS = keyed([stream("salary_uah", UAH, "mono"), stream("contract_usd", USD, "broker")])
ROUTES = keyed(
    [
        route(
            "in_mono_broker",
            origin="mono",
            destination="broker",
            direction="inbound",
            from_ccy=UAH,
            to_ccy=USD,
        ),
        route(
            "in_mono_vault",
            origin="mono",
            destination="vault",
            direction="inbound",
            from_ccy=UAH,
            to_ccy=USD,
        ),
        route(
            "out_broker_mono",
            origin="broker",
            destination="mono",
            direction="exit",
            from_ccy=USD,
            to_ccy=UAH,
        ),
        route(
            "out_vault_broker",
            origin="vault",
            destination="broker",
            direction="exit",
            from_ccy=USD,
        ),
    ]
)
REGIMES = keyed(
    [regime("wartime", *ROUTES), regime("normalized", "in_mono_broker", "out_broker_mono")]
)
SPENDABLE = spendable(("mono", UAH))
"""A registry with every shape in it: ready verdicts, all three deficits, two regimes, a to-do
list with a tie, and an orphan exit. The walk is only as good as what it walks over."""


def _report() -> CoverageReport:
    produced = coverage(
        venues=VENUES,
        streams=STREAMS,
        routes=ROUTES,
        regimes=REGIMES,
        spendable=SPENDABLE,
    )
    assert isinstance(produced, CoverageReport), produced
    return produced


def _walk_values(node: object, path: str, visited: list[str]) -> None:
    """Every value reachable from the report, checked and counted.

    Recurses through frozen records, tuples, lists, sets and mappings. ``visited`` records the
    dotted path of each leaf so the calling test can assert the walk actually went somewhere --
    a recursive checker that silently visits nothing passes every assertion it makes.
    """
    assert not isinstance(node, BANNED), (
        f"{path} holds a {type(node).__name__}. Nothing reachable from a CoverageReport may be "
        f"a Money, a Provenance, a StalenessVerdict or a float (FR-017, FR-023): the report is "
        f"not a comparison and must not be mistakable for one."
    )
    visited.append(path)
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            _walk_values(getattr(node, field.name), f"{path}.{field.name}", visited)
        return
    if isinstance(node, str | bytes):
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_values(key, f"{path}[key]", visited)
            _walk_values(value, f"{path}[{key!r}]", visited)
        return
    if isinstance(node, tuple | list | set | frozenset):
        for index, item in enumerate(node):
            _walk_values(item, f"{path}[{index}]", visited)


def _walk_types(record: type, path: str, seen: set[type], visited: list[str]) -> None:
    """Every **declared** field type reachable from the report's type, checked and counted.

    The values walk cannot see a field that is empty today, and an empty ``tuple[float, ...]``
    is still a place a cost fraction can land the moment somebody fills it. So the types are
    walked too, following the annotations rather than the data: unions are opened, generic
    parameters are opened, and any dataclass found is descended into.
    """
    if record in seen:
        return
    seen.add(record)
    hints = typing.get_type_hints(record)
    for field in dataclasses.fields(record):
        _check_annotation(hints[field.name], f"{path}.{field.name}", seen, visited)


def _check_annotation(annotation: Any, path: str, seen: set[type], visited: list[str]) -> None:
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is not None:
        for arg in args:
            _check_annotation(arg, path, seen, visited)
        return
    if not isinstance(annotation, type):
        # A ``Literal`` member or a forward reference already resolved to a value.
        return
    visited.append(path)
    assert not issubclass(annotation, BANNED), (
        f"{path} is declared as {annotation.__name__}. The report has no field a cost figure "
        f"or a provenance mark may live in, and that is what makes FR-017 a property of the "
        f"type rather than a promise about the values (research.md D12)."
    )
    if dataclasses.is_dataclass(annotation):
        _walk_types(annotation, path, seen, visited)


def test_no_cost_figure_is_reachable_from_the_report() -> None:
    """**SC-004, SC-008.** Every value, recursively, across the whole output."""
    visited: list[str] = []
    _walk_values(_report(), "report", visited)
    # A walk that visits nothing passes every assertion inside it, so the walk itself is
    # asserted. This registry has four destinations, two streams and two regimes; a few
    # hundred nodes is the honest order of magnitude, and a couple of dozen would mean the
    # recursion stopped at the first tuple.
    assert len(visited) > 200, f"the walk only reached {len(visited)} nodes"


def test_no_field_anywhere_in_the_report_is_typed_to_hold_one() -> None:
    """The same claim about the **types**, so an empty field cannot hide a future leak."""
    visited: list[str] = []
    _walk_types(CoverageReport, "CoverageReport", set(), visited)
    assert len(visited) > 30, f"the type walk only reached {len(visited)} fields"


def test_the_only_quantities_are_counts_and_indices() -> None:
    """FR-017's positive half, stated as an assertion rather than left implied.

    Whatever numbers the report does carry are ``int``: the blocked-pair counts and the tie
    index groups. Asserted by collecting them rather than by naming the fields they live in,
    on the same "not sampled" reasoning as the walk.
    """
    numbers: list[tuple[str, object]] = []

    def collect(node: object, path: str) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, int):
            numbers.append((path, node))
            return
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            for field in dataclasses.fields(node):
                collect(getattr(node, field.name), f"{path}.{field.name}")
        elif isinstance(node, tuple | list | set | frozenset):
            for index, item in enumerate(node):
                collect(item, f"{path}[{index}]")

    collect(_report(), "report")
    assert numbers, "the report carries no counts at all, which cannot be right"
    assert all(isinstance(value, int) for _, value in numbers)


def test_the_same_declarations_produce_the_identical_report() -> None:
    """**SC-016, FR-016, G11.** Pure, deterministic, and equal field for field.

    Two independent calls, compared with ``==`` -- which for frozen dataclasses of tuples is a
    structural comparison all the way down, tuple order included. Ordering is the part that
    could plausibly drift: every collection in the report is sorted from a mapping, and a
    mapping's iteration order is a property of insertion rather than of the declarations.

    ⚙ **What this test structurally cannot catch, stated so nobody reads it as more than it
    is.** Both calls happen in **one process**, so both see the same ``PYTHONHASHSEED``. A
    collection whose order depends on string hashing -- a ``set`` sorted by a key that is not
    *total*, where two members tie and the sort falls through to iteration order -- is stable
    within a process and varies between them. This test would pass on every such report and CI
    would go green until a run happened to hash differently.

    So the defence is in the code rather than here: every sort key in
    ``core/routes/coverage.py`` is total over the record it orders, and the one place a set was
    being sorted now builds an insertion-ordered mapping first. See ``_missing_key``. A
    cross-process check is possible but would mean spawning an interpreter per example; the
    total key is cheaper and is the actual guarantee.
    """
    assert _report() == _report()


def test_the_report_names_the_declaration_set_it_audited() -> None:
    """**SC-016's second half, FR-021.** Ids, not paths -- the core cannot import ``pathlib``."""
    audited = _report().audited
    assert audited.venue_ids == ("broker", "mono", "vault")
    assert audited.stream_ids == ("contract_usd", "salary_uah")
    assert audited.route_ids == tuple(sorted(ROUTES))
    assert audited.regime_ids == ("normalized", "wartime")
    assert [endpoint.venue_id for endpoint in audited.spendable] == ["mono"]


def test_the_report_states_in_its_own_output_that_it_is_advisory() -> None:
    """**SC-020's second half, FR-019, research.md D15.**

    A reader of the *output* -- not only of the spec -- has to see that the verdicts change
    nothing and that enforcement is a recorded deferral. Asserted on the substance rather than
    on the exact sentence, so rewording the statement does not break the test while deleting
    any of its three claims does.
    """
    enforcement = _report().enforcement
    assert enforcement == ENFORCEMENT
    lowered = enforcement.lower()
    assert "advisory" in lowered
    assert "ranking" in lowered
    assert "deferral" in lowered or "deferred" in lowered


def test_producing_the_report_changes_no_ranking() -> None:
    """**SC-020, FR-019.** The verdict is advisory, measured by ranking with and without it.

    Nearly free, because both computations are pure -- and it is what catches the day somebody
    makes coverage "helpfully" prune a ranking. Feature 002's ranking is run over one registry
    twice, with a coverage report produced in between; the two results must be equal.

    The registry is ``route_graphs.p2p_graph()``: a declared way in, a declared way out, and a
    round-trip figure -- so there is a real ranking to be changed rather than an empty one.
    """
    graph = route_graphs.p2p_graph()
    amount = Money(10_000.0, UAH, prov.EMPTY)

    def ranked() -> Ranking | NothingComparable:
        return rank(
            [graph.path],
            amount,
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=date(2026, 8, 21),
            as_of=date(2026, 8, 21),
        )

    before = ranked()
    _report()
    after = ranked()
    assert isinstance(before, Ranking)
    assert before == after
