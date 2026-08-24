"""FR-008: a cost attributed to a destination alone has no type to live in.

*Access cost MUST be reported per ``(destination x stream x route)``. A cost attributed to a
destination alone MUST NOT be representable -- not merely discouraged.*

**Why this is the most important test in the feature.** ``SIMULATOR_SPEC.md`` §4.3.1's
finding is that the same acquisition is nearly free funded from USD contract income and
5-10% expensive funded from a UAH salary. A helper named ``cost_of_reaching(venue)`` reads
perfectly reasonable, would pass review from anyone not holding that finding in mind, and
would silently blend the two into one figure -- destroying the entire result while leaving
every number plausible. Principle VI's rule is the one most likely to be broken by accident
rather than by intent.

**A convention cannot stop that; a missing type can.** ``FundingPath`` is a mandatory triple
with no partial form: no default, no optional variant, no ``stream_id: str | None``. "The
cost of reaching Binance" is therefore not a discouraged call but an expression that does not
typecheck. The alternatives were considered and rejected in research.md D2: a required
keyword argument is still satisfiable by passing a constant stream id, which is exactly what
a hurried caller does; and a naming convention plus review is the mechanism that already
failed once in this project, on ``nominal_ytm`` in feature 001.

**What this test adds on top of the type.** mypy enforces the triple at every call site that
exists. It cannot notice a *new* signature that reintroduces the per-destination shape, since
such a signature is perfectly well typed. So this module reads every public callable in
``terezy.core`` and fails on any that accepts a destination without also accepting a
stream and a route. It is a structural scan, and its own ability to fail is asserted at the
bottom -- a scan that silently matches nothing passes forever and protects nothing.

**Two deliberate boundaries, stated so neither is mistaken for an oversight.**

*A bare ``venue`` parameter is not treated as a destination.* ``venues.can_hold(venue,
currency)`` asks whether an account can hold a currency, which is a question about a venue
and not a cost of reaching one; banning the word outright would push such helpers into worse
shapes. The patterns below name the ways a *destination* is spelt, and the return-type scan
closes the gap from the other end.

*A declaration record may name a destination -- a computed cost may not.* ``Route`` is a
corridor from one venue to another; naming its ``destination`` is what a route **is**, and a
``Leg`` naming its ``to_venue`` likewise. What FR-008 forbids is a *cost figure* keyed by a
destination, so the parameter scan applies to functions, and records are held to a separate
rule: any record carrying a computed cost -- ``sent``, ``arrived``, ``fraction``,
``components`` -- must carry the whole triple. That split is the difference between
describing a corridor and pricing one, and it is the distinction FR-008 is actually about.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import re
from collections.abc import Iterator, Sequence
from typing import Any, get_type_hints

import pytest

import terezy.core
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.routes import cost
from terezy.core.routes.path import FundingPath
from tests.invariants import route_graphs

pytestmark = pytest.mark.contract

DESTINATION_NAMES = frozenset(
    {
        "destination",
        "destination_id",
        "destination_venue",
        "dest",
        "dest_id",
        "target",
        "target_venue",
        "to_venue",
        "venue_id",
    }
)
"""The ways a destination gets spelt. See the module docstring on why bare ``venue`` is not
here."""

STREAM_NAMES = frozenset({"stream", "stream_id", "streams", "path"})
"""What counts as naming the funding stream. ``path`` is a ``FundingPath``, which carries
all three terms and is the shape everything is supposed to use."""

ROUTE_NAMES = frozenset({"route", "route_id", "routes", "path"})
"""What counts as naming the route."""

COST_RETURNS = frozenset({"RampCost", "OneWayCost", "RoundTripCost", "Ranking", "WayOutCost"})
"""Return types that make a function a costing function, whatever it is called.

⚙ ``WayOutCost`` joined with feature 010. It is the third labelled cost record, produced by
``cost.cost_exit`` from what an instrument released rather than from what a ramp delivered, and
leaving it out would have meant the scan's reach was narrower than the requirement it guards --
which is the shape of gap that lets a guard pass while the rule is broken.
"""

PATH_NAMES = frozenset({"path", "paths"})
"""Parameters that can carry the triple.

The plural is ``ranking.rank``'s: it takes a sequence of whole ``FundingPath`` triples and
costs them one at a time through ``cost_one``, which honours FR-008 exactly as the singular
does. ``STREAM_NAMES`` and ``ROUTE_NAMES`` above already admit their plurals for the same
reason; this set was written before any function took more than one path, and the omission was
a gap in the heuristic rather than a rule.

⚙ Naming a parameter is not enough -- :func:`_takes_the_triple` also requires the annotation to
mention ``FundingPath``, so ``def cost_via(path: str) -> RampCost`` no longer passes. That is
stricter than the first version of this scan, which matched on the name alone.
"""

COST_FIGURE_NAMES = frozenset({"sent", "arrived", "fraction", "components"})
"""Field names that make a record a *computed access cost* rather than a declaration.

A ``Route`` names a destination because a route is a corridor from one place to another. A
record holding what was **sent** and what **arrived**, with a fraction and an attribution, is
pricing that corridor -- and pricing is what FR-008 requires to be keyed by all three terms.

⚙ ``one_way``, ``round_trip`` and bare ``cost`` were removed when the scan widened from
``core.routes`` to all of ``core``, and the removal is a **narrowing of the heuristic, not of
the rule**:

* ``one_way`` / ``round_trip`` name *fields that hold* a cost. The record holding them is
  ``RampCost``, which carries the triple; requiring the holder to be keyed is right, and it is
  what :data:`COST_FIGURE_NAMES`\'s remaining members already catch on the held records
  themselves via :func:`_inherits_a_key`.
* bare ``cost`` matched ``Holding.cost`` from feature 001 -- an **acquisition** cost, the basis
  of a purchase. FR-008 is about **access** cost, what it costs to get money to where an
  instrument is. A purchase price is not a ramp, and demanding a funding triple on a cost
  basis would be enforcing the wrong requirement while looking like enforcement.

The distinction that survives: a record priced *by this feature* states what went in and what
came out. Nothing else does.
"""


def _modules() -> Iterator[Any]:
    """Every module under ``terezy.core``, recursively.

    Walked rather than listed. A hand-written list stops covering the package the moment
    someone adds a file, and it stops silently -- which is the failure mode this whole module
    exists to prevent one level up.

    **The reach was widened from ``terezy.core.routes`` to all of ``terezy.core``.** FR-008 is
    about *any* cost figure, and the narrower walk meant a costing function added under
    ``core/streams``, ``core/results`` or anywhere else escaped the scan entirely. Nothing was
    wrong when the gap was found -- ``streams.deployable`` returns capacity, not cost -- but a
    guard whose reach is narrower than the requirement it guards is a guard that will one day
    pass while the requirement is broken.
    """
    yield terezy.core
    for info in pkgutil.walk_packages(terezy.core.__path__, prefix="terezy.core."):
        yield importlib.import_module(info.name)


def _public_callables() -> Iterator[tuple[str, Any]]:
    for module in _modules():
        for name, value in vars(module).items():
            if name.startswith("_") or not callable(value):
                continue
            if getattr(value, "__module__", None) != module.__name__:
                continue  # imported from elsewhere; scanned where it is defined
            yield f"{module.__name__}.{name}", value


def _parameters(target: Any) -> frozenset[str]:
    return frozenset(inspect.signature(target).parameters)


def _takes_the_triple(target: Any) -> bool:
    """Whether this signature takes the whole ``(destination x stream x route)`` key.

    Checked on the *annotation* rather than on the parameter name, because the name is the
    heuristic and the type is the guarantee: a parameter called ``path`` carrying a bare venue
    id would satisfy a name check while reintroducing precisely the blended figure FR-008
    exists to forbid.

    ⚙ **``Candidate`` and ``Journey`` count too**, since feature 004. ``Candidate`` is
    ``FundingPath | ComposedPath`` and both members carry the destination **and** the stream --
    a ``ComposedPath`` names its whole chain of segments where a ``FundingPath`` names one
    route, which is more of the key rather than less. A ``Journey`` pairs a candidate with its
    way out, so it is the key plus the exit chain (FR-012). What the widening does *not* admit
    is a bare venue id: a ``str`` still fails, which is the property this function exists for.
    """
    signature = inspect.signature(target)
    names = frozenset(signature.parameters)
    if any(
        any(
            key in str(signature.parameters[name].annotation)
            for key in ("FundingPath", "Candidate", "Journey")
        )
        for name in names & PATH_NAMES
    ):
        return True
    return _names_a_way_out(signature)


WAY_OUT_NAMES = frozenset({"chain", "exit_path", "route_out"})
"""Parameters that can carry the way out. ``chain`` is ``cost.cost_exit``'s."""


def _names_a_way_out(signature: inspect.Signature) -> bool:
    """Whether this signature spells the triple as a *way out* rather than as a way in.

    ⚙ **Feature 010's addition, and it admits three terms rather than relaxing to two.** A way
    out is not reached from a stream's venue, so there is no ``FundingPath`` to hand it: what
    names the journey is the declared exit chain (the route), ``departing_from`` (where the
    money actually is -- the anchor that makes it a journey rather than a wish), and
    ``stream_id`` (which income funded the holding it is leaving). All three are required
    below, so a way-out costing function that dropped the stream -- the term §4.3.1's finding
    lives in, and the one a hurried caller drops first -- still fails this scan.
    """
    names = frozenset(signature.parameters)
    return bool(
        names & STREAM_NAMES
        and "departing_from" in names
        and any(
            "ExitChain" in str(signature.parameters[name].annotation)
            for name in names & WAY_OUT_NAMES
        )
    )


def _accepts_a_bare_destination(target: Any) -> bool:
    """Whether this signature takes a destination without a stream and a route."""
    names = _parameters(target)
    if not names & DESTINATION_NAMES:
        return False
    return not (names & STREAM_NAMES and names & ROUTE_NAMES)


def test_no_public_function_in_core_accepts_a_destination_alone() -> None:
    """The scan FR-008 asks for, over every function in the package.

    A failure here is not a style problem. It is a signature in which the §4.3.1 finding
    can be hidden: one cost for "buying dollars", blending a stream that pays nothing with
    one that pays 5-10%.
    """
    offenders = [
        name
        for name, target in _public_callables()
        if not inspect.isclass(target) and _accepts_a_bare_destination(target)
    ]
    assert not offenders, (
        "these accept a destination without a stream and a route, so a per-destination "
        "cost is representable again (FR-008): " + ", ".join(sorted(offenders))
    )


def _is_keyed(target: type) -> bool:
    """Whether a record carries the whole triple, however it spells it."""
    fields = {field.name for field in dataclasses.fields(target)}
    return "path" in fields or {"destination_id", "stream_id", "route_id"} <= fields


def _records_nested_in_keyed_records() -> frozenset[str]:
    """Names of records that appear as a field of some record that IS keyed.

    **Computed, never listed.** A record nested inside a keyed one is keyed *by its parent*:
    ``OneWayCost`` sits on ``RampCost``, which carries the ``FundingPath``, so there is exactly
    one triple per result and reading either figure tells you which funding path it belongs to.

    Requiring the nested records to carry their own copy would put the same key in a result
    three times -- and duplicated facts disagree, which is the reason ``IncomeStream.currency``
    was removed one commit ago. The exemption is derived from the field graph rather than
    written down, so a new nested cost record inherits it automatically and a cost record that
    is *not* nested inside anything keyed does not.
    """
    records = {
        target.__name__: target
        for _, target in _public_callables()
        if inspect.isclass(target) and dataclasses.is_dataclass(target)
    }

    def held_by(record: Any) -> set[str]:
        names: set[str] = set()
        for field in dataclasses.fields(record):
            names.update(re.findall(r"[A-Z]\w+", str(field.type)))
        return names

    nested: set[str] = set()
    frontier = [target for target in records.values() if _is_keyed(target)]
    while frontier:
        held = held_by(frontier.pop())
        for name in held - nested:
            nested.add(name)
            if name in records:
                frontier.append(records[name])
    return frozenset(nested)


def _selects_rather_than_produces(target: Any) -> bool:
    """Whether a callable *picks out* an already-keyed cost instead of computing one.

    ``recommended_cost(ranking)`` returns a ``RampCost`` that ``cost_one`` already built and
    already keyed; it performs no arithmetic and has no path of its own to be keyed by.
    Demanding a ``FundingPath`` from it would be asking a projection to re-state a key its
    input carries -- and the honest signature, taking the container, is the one that makes
    "the winner is one of the alternatives" expressible at all (research.md D3).

    Recognised structurally: every parameter is annotated with a type that itself holds keyed
    costs. A function taking an amount and a route does not qualify, whatever it returns.
    """
    parameters = inspect.signature(target).parameters
    if not parameters:
        return False
    holders = {"Ranking"}
    return all(
        any(holder in str(parameter.annotation) for holder in holders)
        for parameter in parameters.values()
    )


def test_no_record_carrying_a_cost_figure_is_keyed_by_a_destination_alone() -> None:
    """The record half of the same rule. A declaration may name a venue; a price may not.

    The failure this catches is a result record that grew a ``destination_id`` beside its
    ``fraction`` and lost the stream -- at which point the type system is happily enforcing
    a key that no longer says which income paid for the trip.
    """
    offenders = []
    nested = _records_nested_in_keyed_records()
    for name, target in _public_callables():
        if not (inspect.isclass(target) and dataclasses.is_dataclass(target)):
            continue
        fields = {field.name for field in dataclasses.fields(target)}
        if not fields & COST_FIGURE_NAMES:
            continue
        if _is_keyed(target) or target.__name__ in nested:
            continue
        offenders.append(name)
    assert not offenders, (
        "these carry a computed cost without carrying the (destination x stream x route) "
        "key (FR-008): " + ", ".join(sorted(offenders))
    )


def test_every_cost_returning_function_takes_the_whole_triple() -> None:
    """The same rule from the other end, so a differently-named destination cannot slip past.

    The scan above matches on parameter *names*, which is a heuristic. This one matches on
    what a function *returns*: anything producing a cost must take the triple, whatever its
    parameters happen to be called. Between them, a costing function has nowhere to hide.
    """
    offenders = []
    for name, target in _public_callables():
        if inspect.isclass(target):
            continue
        annotation = str(inspect.signature(target).return_annotation)
        if not any(cost in annotation for cost in COST_RETURNS):
            continue
        if _takes_the_triple(target) or _selects_rather_than_produces(target):
            continue
        offenders.append(name)
    assert not offenders, (
        "these return a cost without taking a FundingPath, so the cost they produce is "
        "not keyed by (destination x stream x route) (FR-008): " + ", ".join(sorted(offenders))
    )


class TestTheTripleHasNoPartialForm:
    """research.md D2: the shape is the mechanism, so the shape is asserted."""

    def test_the_path_is_exactly_the_three_terms(self) -> None:
        assert [field.name for field in dataclasses.fields(FundingPath)] == [
            "destination_id",
            "stream_id",
            "route_id",
        ]

    def test_no_term_has_a_default(self) -> None:
        # A default on any one of the three is the whole hole: ``stream_id: str = ""``
        # would make a per-destination cost representable again, and it would look like a
        # convenience.
        for field in dataclasses.fields(FundingPath):
            assert field.default is dataclasses.MISSING, field.name
            assert field.default_factory is dataclasses.MISSING, field.name

    def test_a_missing_term_is_a_construction_failure(self) -> None:
        # mypy rejects this at every call site; this is the runtime half, for a path built
        # dynamically. Two terms are not a funding path -- they are half a question.
        with pytest.raises(TypeError):
            FundingPath(destination_id="binance", route_id="monobank_to_binance_p2p")  # type: ignore[call-arg]

    def test_the_terms_must_be_named(self) -> None:
        # Keyword-only, because all three are strings: a positional triple lets a caller
        # transpose the route id and the destination id and get a wrong answer with no
        # type error at all.
        with pytest.raises(TypeError):
            FundingPath("binance", "salary_uah", "monobank_to_binance_p2p")  # type: ignore[call-arg]

    def test_the_path_does_not_carry_an_amount(self) -> None:
        # A path is *which way*; an amount is *how much*. Folding the amount in would make
        # a cost's key include the cost's own input, so two amounts through one route would
        # look like two paths -- and the monthly-capacity accumulator, which is keyed by
        # route, would stop working (plan.md, post-Phase-1 note).
        names = {field.name for field in dataclasses.fields(FundingPath)}
        assert not names & {"amount", "money", "sent", "quantity"}

    def test_the_path_is_a_frozen_hashable_record_with_no_behaviour(self) -> None:
        # Hashable because costs are keyed by it. Frozen and method-free because it is
        # data (owner decision D-E) -- a method here would be the natural home for exactly
        # the ``cost_of_reaching`` helper this module exists to prevent.
        path = FundingPath(
            destination_id="binance", stream_id="salary_uah", route_id="monobank_to_binance_p2p"
        )
        assert hash(path) == hash(
            FundingPath(
                destination_id="binance",
                stream_id="salary_uah",
                route_id="monobank_to_binance_p2p",
            )
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            path.stream_id = "contract_usd"  # type: ignore[misc]
        assert [
            name
            for name, value in vars(FundingPath).items()
            if callable(value) and not name.startswith("__")
        ] == []

    def test_two_streams_through_one_route_are_two_different_paths(self) -> None:
        # The property the whole feature turns on: the stream is part of the key, so the
        # same route funded from two streams cannot collapse into one cached figure.
        salary = FundingPath(
            destination_id="binance", stream_id="salary_uah", route_id="monobank_to_binance_p2p"
        )
        contract = FundingPath(
            destination_id="binance", stream_id="contract_usd", route_id="monobank_to_binance_p2p"
        )
        assert salary != contract
        assert len({salary, contract}) == 2


class TestTheScanWouldActuallyCatchAViolation:
    """A structural scan is only worth having if it can fail. These are the decoys."""

    def test_the_tempting_signature_is_caught(self) -> None:
        def cost_of_reaching(destination_id: str, amount: object) -> object:
            """The exact function FR-008 exists to make unwritable."""
            raise NotImplementedError

        assert _accepts_a_bare_destination(cost_of_reaching)

    def test_a_destination_with_a_route_but_no_stream_is_still_caught(self) -> None:
        # The half-measure: naming the route makes it look properly keyed, and it is still
        # the blended figure, because the stream is the term that carries the finding.
        def cost_via(destination_id: str, route_id: str) -> object:
            raise NotImplementedError

        assert _accepts_a_bare_destination(cost_via)

    def test_a_record_pricing_a_destination_alone_is_caught(self) -> None:
        # The record decoy: a cost figure keyed by where the money went and nothing about
        # where it came from. Written out to prove the record scan can fail.
        @dataclasses.dataclass(frozen=True)
        class CostOfReaching:
            destination_id: str
            fraction: float

        fields = {field.name for field in dataclasses.fields(CostOfReaching)}
        assert fields & COST_FIGURE_NAMES
        assert "path" not in fields
        assert not {"destination_id", "stream_id", "route_id"} <= fields

    def test_a_signature_carrying_the_whole_triple_passes(self) -> None:
        def cost_one(path: FundingPath, amount: object) -> object:
            raise NotImplementedError

        assert not _accepts_a_bare_destination(cost_one)
        assert _takes_the_triple(cost_one)

    def test_the_transitive_closure_walks_out_from_keyed_records_and_not_over_everything(
        self,
    ) -> None:
        """The boundary of the widened exemption, asserted where it can actually fail.

        ⚙ **The obvious decoy here is vacuous, and saying so is the point.** A throwaway record
        declared inside a test body can never enter the closure, because ``held_by`` collects
        names by reading the *annotations of reachable records* -- a name no annotation mentions
        is unreachable under any closure, one level or twenty. An assertion that cannot fail is
        worse than none: it reads as coverage.

        What *is* falsifiable is the closure's **root set**. It walks out from the keyed records
        only, so a declaration record like ``Route`` or ``Leg`` -- carrying no cost figure, and
        held by no result record -- must stay outside it. A closure that walked every dataclass
        instead of following the field graph from the keys would sweep both in, and every
        unkeyed cost record with them.
        """
        nested = _records_nested_in_keyed_records()
        assert "Route" not in nested
        assert "Leg" not in nested

    def test_the_transitive_exemption_does_reach_the_record_it_was_widened_for(self) -> None:
        """The other half: ``SegmentAttribution`` is two hops from the key and **is** exempt.

        Without this the decoy above would pass against a closure that had been reverted to one
        level, and the widening would look untested in the direction it actually changed.
        """
        nested = _records_nested_in_keyed_records()
        assert "OneWayCost" in nested, "the direct hop is missing; this test is stale"
        assert "SegmentAttribution" in nested

    def test_a_sequence_of_triples_is_the_triple_too(self) -> None:
        # ``rank``'s shape. Many whole keys is not a partial key, and refusing the plural
        # would push a ranking function into taking three parallel lists -- which is the
        # partial form with extra steps.
        def rank(paths: Sequence[FundingPath], amount: object) -> object:
            raise NotImplementedError

        assert _takes_the_triple(rank)

    def test_a_parameter_merely_named_path_does_not_count(self) -> None:
        # The decoy the name-only version of this scan would have accepted: a bare venue id
        # under a reassuring parameter name, producing the one blended access cost for
        # "buying dollars" that hides the whole §4.3.1 finding.
        def cost_via(path: str) -> object:
            raise NotImplementedError

        assert not _takes_the_triple(cost_via)

    def test_the_walk_actually_finds_the_modules(self) -> None:
        # If the package walk returned nothing, every scan above would pass vacuously.
        found = {name for name, _ in _public_callables()}
        assert found, "the package walk found no public callables, so the scans prove nothing"
        assert any(name.endswith(".can_hold") for name in found)

    def test_the_hints_of_the_path_are_readable(self) -> None:
        # ``from __future__ import annotations`` makes annotations strings; if resolution
        # ever broke, the return-type scan would quietly stop matching anything.
        assert get_type_hints(FundingPath) == {
            "destination_id": str,
            "stream_id": str,
            "route_id": str,
        }


class TestTheTripleMustBeCoherentAndNotMerelyPresent:
    """Three ids that do not describe one journey are not a funding path.

    The type stops a *missing* term. It cannot stop three well-typed strings that disagree
    with each other -- a route id that was never declared, or a destination that is not
    where the named route ends. Both are construction errors rather than facts about the
    money: a path is built *from* a route, so a disagreement means the caller assembled it
    from parts of two different journeys. Reporting either as a typed cost failure would
    invite callers to build mismatched paths and read the answer as a cost.
    """

    def _cost(self, path: FundingPath) -> object:
        graph = route_graphs.zero_cost_graph()
        return cost.cost_one(
            path,
            Money(1_000.0, Currency.UAH, prov.EMPTY),
            routes=graph.routes,
            channels=graph.channels,
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=route_graphs.ON_DATE,
            as_of=route_graphs.AS_OF,
            spendable=frozenset(),
        )

    def test_a_path_naming_an_undeclared_route_fails_naming_the_known_ones(self) -> None:
        with pytest.raises(KeyError, match="unknown route") as raised:
            self._cost(
                FundingPath(
                    destination_id="venue_2", stream_id="salary", route_id="wishful_thinking"
                )
            )
        assert "inzhur_direct" in str(raised.value)

    def test_a_path_whose_destination_is_not_the_routes_destination_is_refused(self) -> None:
        # The subtle one: every term is present, every term is a real id, and together they
        # describe a journey nobody declared. Silently trusting the route would report the
        # cost of arriving somewhere else.
        with pytest.raises(ValueError, match="ends at"):
            self._cost(
                FundingPath(destination_id="binance", stream_id="salary", route_id="inzhur_direct")
            )
