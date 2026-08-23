"""FR-020 and research.md D8: the guess is labelled, and it cannot be filed as an observation.

FR-020: *a transition date MUST be presented as a stated assumption, never as a known fact.*
D8: *a leg's ``available_from``/``available_until`` is a **fact**; a regime transition is an
**assumption**.* Both statements are about the same hazard, from two sides.

**The hazard.** A regime transition and a leg availability window can produce the identical
route set on a given date. "Only the P2P corridor exists until 2027-07-01" is expressible as a
regime, and equally expressible by writing ``available_until = 2027-07-01`` on the P2P legs and
``available_from = 2027-07-01`` on the bank ones. The arithmetic would agree to the last float.
Every figure in ``tests/worked_examples/test_regime_transition.py`` would still be right.

What would be lost is the only thing that mattered. A leg window carries a source, a retrieval
date and a verification date, and every other value in that field is something somebody
observed: "this corridor closed in March 2025". A transition date is a belief about the future
that nobody can source. Collapsed into one field, the output reports both in the same shape --
a ``RouteUnusable`` whose ``binding_constraint`` names a declared field -- and no reader can
tell "this route is closed because it closed" from "this route is closed because I guessed a
date". That distinction is the content of ``SIMULATOR_SPEC.md`` §1.3, and Principle I is the
rule it comes from: a tool must never present a number with more confidence than its inputs
support, and an assumption filed as an observation is exactly that.

So this module asserts the *shapes*, which is where the guarantee actually lives:

* the marker admits one value and cannot be omitted, and the rationale cannot be omitted;
* a regime carries no date-window field, and a leg carries no assumption marker;
* an assumed exclusion and an observed one arrive by different routes and in different records,
  demonstrated side by side on the same corridor and the same date;
* the costing engine has never heard of a regime, so a regime cannot reach a leg field by
  being passed into it.

The last class covers the refusals, which belong here for the same reason: a scenario whose
transitions do not describe one chain of regimes leaves some date with no stated belief, and
supplying one would be inventing the assumption rather than labelling it.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
from datetime import date
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results.ramp import RampCost, RouteUnusable
from terezy.core.routes import cost
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.path import FundingPath, candidate_id
from terezy.core.scenarios import regimes
from tests.invariants import route_graphs

TRANSITION_DATE = date(2027, 7, 1)
"""The assumed war-end date, as in the worked example. **Nobody knows this.**"""

BEFORE = date(2027, 6, 30)
AFTER = date(2027, 8, 15)

RATIONALE = (
    "The owner assumes wartime capital controls are relaxed around the middle of 2027. This is "
    "a belief about the future, not an observation: no source states it."
)

TRANSITION = regimes.RegimeTransition(
    on_date=TRANSITION_DATE,
    before="wartime",
    after="normalized",
    is_assumption=True,
    rationale=RATIONALE,
)

WARTIME = regimes.Regime(
    id="wartime", route_ids=frozenset({"monobank_to_binance_p2p", "binance_p2p_to_monobank"})
)
NORMALIZED = regimes.Regime(
    id="normalized", route_ids=frozenset({"bank_uah_to_broker", "broker_to_bank"})
)
REGIMES = {WARTIME.id: WARTIME, NORMALIZED.id: NORMALIZED}

ROUTES_ROOT = Path(inspect.getfile(cost)).parent
"""``src/terezy/core/routes/`` -- the costing engine, scanned by the boundary test below."""

REGIME_AWARE = frozenset({"coverage.py"})
"""The only module in ``core.routes`` allowed to import the scenarios package, and why.

Feature 003's coverage audit is a fold over route declarations that FR-013 requires to state
every verdict **per regime**, so it has to be handed the regimes -- and it belongs beside the
other route folds (003 research.md D1). It is not on the costing path: it computes no figure,
consults no leg window and produces no ``RouteUnusable``, which is the whole hazard the scan
above exists to close. The test immediately after the scan holds it to exactly that, which is a
stricter bar than the import ban it is exempt from. **Nothing else goes in this set** without
the same argument written out beside it.
"""

_IMPORTS_REGIME = re.compile(r"^\s*(?:from\s+[\w.]+\s+)?import\s+.*\bRegime\b")
"""An import statement that binds the name ``Regime`` in the importing module."""

_EXPORTS_REGIME = re.compile(r"""^\s*(?:__all__\b.*["']Regime["']|["']Regime["']\s*,?\s*$)""")
"""An ``__all__`` entry re-exporting ``Regime``, on its own line or in a one-line list."""


def _regime_side_doors(source: str) -> list[tuple[int, str]]:
    """Every line of a module that would let *another* module reach ``Regime`` through it.

    Two shapes, and deliberately only two: an **import** that binds the name, and an
    ``__all__`` entry that re-exports it. Those are the ways a costing module could get hold of
    the record; nothing else in a file makes it reachable.

    ⚙ **Shapes, not the bare word** (correction, 2026-08-23). This scan read raw text for
    ``Regime`` anywhere, comments included -- so ``cost.py`` explaining that *a regime is not a
    leg window*, which is the subject of the enclosing test class and the most natural sentence
    to write there, would have failed it, with a message about a re-export that does not exist.
    The sibling scan above already strips comments and states the docstring trade-off out loud;
    this one did neither. It now matches the two shapes that actually open the door, so prose --
    in a comment or a docstring -- is free to name the record it is warning about.

    The limits are ``test_money_construction_guard``'s, unchanged: an alias
    (``import Regime as R``, or a ``getattr``) is not caught. What is caught is the obvious
    version, which is the one that gets written.
    """
    return [
        (number, line.strip())
        for number, line in enumerate(source.splitlines(), 1)
        if not line.lstrip().startswith("#")
        and (_IMPORTS_REGIME.match(line) or _EXPORTS_REGIME.match(line))
    ]


def _world() -> dict[str, Route]:
    """Every declared route in both corridors, exactly as the worked example declares them."""
    return {**route_graphs.p2p_graph().routes, **route_graphs.bank_corridor_graph().routes}


def _requires(field_name: str, record: type) -> None:
    """Assert a dataclass field has no default of any kind, so it cannot be omitted."""
    field = next(f for f in dataclasses.fields(record) if f.name == field_name)
    assert field.default is dataclasses.MISSING, field_name
    assert field.default_factory is dataclasses.MISSING, field_name


class TestTheMarkerAdmitsOneValueAndCannotBeOmitted:
    """FR-020's first half, structurally: the claim cannot be switched off or left out."""

    def test_the_annotation_admits_only_true(self) -> None:
        # A ``bool`` would admit ``False`` -- a transition asserting it is *not* an
        # assumption, which is precisely the sentence this feature exists to prevent anyone
        # writing. ``Literal[True]`` has one inhabitant, so ``is_assumption=False`` is a mypy
        # error at the construction site rather than a runtime check nobody runs.
        assert get_args(get_type_hints(regimes.RegimeTransition)["is_assumption"]) == (True,)

    def test_it_has_no_default_so_every_construction_site_states_it(self) -> None:
        # A default would make the claim true and invisible. Required, it is written out at
        # every construction site, which is what "presented as a stated assumption" means for
        # the person writing the scenario as well as the person reading the output.
        _requires("is_assumption", regimes.RegimeTransition)

    def test_the_rationale_is_required_too(self) -> None:
        # A date with no reasoning is indistinguishable from a typo, and a marker alone does
        # not *state* an assumption -- it only classifies one.
        _requires("rationale", regimes.RegimeTransition)

    def test_a_transition_cannot_be_built_without_saying_what_it_is(self) -> None:
        # The runtime half of the same guarantee: the fields are positional-less and
        # defaultless, so omitting either is a TypeError rather than a quiet True.
        with pytest.raises(TypeError):
            regimes.RegimeTransition(  # type: ignore[call-arg]
                on_date=TRANSITION_DATE, before="wartime", after="normalized"
            )


class TestTheDateIsReportedAsAnAssumptionAndNeverAsAFact:
    """FR-020's second half: what an output actually says."""

    def test_the_statement_names_the_date_the_regimes_and_the_rationale(self) -> None:
        said = regimes.stated_assumption(TRANSITION)
        assert TRANSITION_DATE.isoformat() in said
        assert "wartime" in said
        assert "normalized" in said
        assert RATIONALE in said

    def test_the_statement_calls_itself_an_assumption_and_denies_being_an_observation(
        self,
    ) -> None:
        # The wording is asserted because the wording is the deliverable. A sentence reading
        # "the regime changes on 2027-07-01" would be a false statement of fact, and it is the
        # sentence a formatter writes if nothing here pins one.
        said = regimes.stated_assumption(TRANSITION)
        assert "ASSUMPTION" in said
        assert "not an observation" in said
        assert "Nobody knows this date" in said

    def test_the_selection_carries_the_transition_so_the_statement_is_always_reachable(
        self,
    ) -> None:
        # A number produced under a regime must be able to name the belief it rests on, or the
        # belief is stated somewhere the figure cannot reach.
        in_force = regimes.routes_in_force(
            REGIMES, _world(), transitions=(TRANSITION,), on_date=AFTER
        )
        assert in_force.decided_by is TRANSITION
        assert in_force.decided_by.is_assumption is True
        assert RATIONALE in regimes.stated_assumption(in_force.decided_by)


class TestARegimeCannotBeExpressedAsALegWindow:
    """research.md D8, as the field shapes that make the collapse unwritable."""

    def test_a_regime_carries_no_date_at_all(self) -> None:
        # The exact field set, asserted rather than described: a regime is a name and a set of
        # route ids. Adding an ``available_from`` here is how the collapse would begin, and it
        # would begin by failing this assertion.
        assert {f.name for f in dataclasses.fields(regimes.Regime)} == {"id", "route_ids"}
        assert all(
            f.type not in ("date", "date | None") for f in dataclasses.fields(regimes.Regime)
        )

    def test_the_only_date_in_the_scenario_records_is_marked_as_an_assumption(self) -> None:
        # One date, on the one record that also carries the marker and the rationale. There is
        # nowhere in this package to put an unmarked date.
        hints = get_type_hints(regimes.RegimeTransition)
        dated = {name for name, annotation in hints.items() if annotation is date}
        assert dated == {"on_date"}
        assert "is_assumption" in hints
        assert "rationale" in hints

    def test_a_leg_carries_no_assumption_marker_and_no_rationale(self) -> None:
        # The other direction of the same prohibition: a leg's window cannot be relabelled as
        # a guess in place. Its fields are observations, and the record has nowhere to say
        # otherwise -- which is why an assumption has to live in its own record.
        leg_fields = {f.name for f in dataclasses.fields(Leg)}
        assert leg_fields.isdisjoint({"is_assumption", "rationale", "assumption", "regime"})
        assert "provenance" in leg_fields
        assert {"available_from", "available_until"} <= leg_fields

    def test_a_regime_record_carries_no_provenance_because_a_belief_has_no_source(self) -> None:
        # The mirror image, and not an oversight: a fabricated source on an assumption is the
        # top-severity defect Principle I names. ``is_assumption`` is what a belief carries
        # where an observation carries a mark.
        for record in (regimes.Regime, regimes.RegimeTransition):
            assert "provenance" not in {f.name for f in dataclasses.fields(record)}

    def test_an_excluded_route_cannot_be_reported_as_a_binding_constraint(self) -> None:
        # ``RouteUnusable`` is the record an *observed* refusal arrives in, and it has no field
        # in which an assumption could be marked. So a regime exclusion routed through it would
        # be silently indistinguishable from an observation -- which is why the regime narrows
        # the candidates instead, and reports what it left out under its own name.
        unusable_fields = {f.name for f in dataclasses.fields(RouteUnusable)}
        assert unusable_fields.isdisjoint({"is_assumption", "rationale", "regime"})
        in_force_fields = {f.name for f in dataclasses.fields(regimes.RoutesInForce)}
        assert "excluded" in in_force_fields
        assert get_type_hints(regimes.RoutesInForce)["excluded"] == tuple[str, ...]

    def test_the_two_kinds_of_exclusion_arrive_in_different_records(self) -> None:
        # The whole distinction, demonstrated on one corridor and one date, side by side.
        #
        # Observed: the P2P legs are declared closed from 2027-06-01 -- a fact, with a source
        # behind the field. Costing on 2027-08-15 returns a ``RouteUnusable`` naming
        # ``leg.available_until``, and the owner reads "this corridor closed".
        routes = _world()
        closed = dataclasses.replace(
            routes["monobank_to_binance_p2p"],
            legs=tuple(
                dataclasses.replace(leg, available_until=date(2027, 6, 1))
                for leg in routes["monobank_to_binance_p2p"].legs
            ),
        )
        observed = cost.cost_one(
            FundingPath(
                destination_id="venue_1",
                stream_id="salary_uah",
                route_id="monobank_to_binance_p2p",
            ),
            Money(10_000.0, Currency.UAH, prov.EMPTY),
            routes={**routes, "monobank_to_binance_p2p": closed},
            channels={
                **route_graphs.p2p_graph().channels,
                **route_graphs.bank_corridor_graph().channels,
            },
            streams=route_graphs.STREAMS,
            kinds=route_graphs.KINDS,
            on_date=AFTER,
            as_of=route_graphs.AS_OF,
            spendable=route_graphs.p2p_graph().spendable,
        )
        assert isinstance(observed, RouteUnusable), observed
        assert observed.binding_constraint == "leg.available_until"

        # Assumed: the same corridor, the same date, nothing touched in the route data. The
        # regime leaves it out, so it appears in ``excluded`` beside a transition that says in
        # words that the date is a guess -- and never as a binding constraint.
        assumed = regimes.routes_in_force(REGIMES, routes, transitions=(TRANSITION,), on_date=AFTER)
        assert "monobank_to_binance_p2p" in assumed.excluded
        assert "monobank_to_binance_p2p" not in assumed.routes
        assert assumed.decided_by.is_assumption is True

        # And the corridor the regime ruled out is still perfectly costable, which is what
        # makes the exclusion an assumption: nothing about the route says it cannot carry
        # money on this date.
        assert isinstance(
            cost.cost_one(
                FundingPath(
                    destination_id="venue_1",
                    stream_id="salary_uah",
                    route_id="monobank_to_binance_p2p",
                ),
                Money(10_000.0, Currency.UAH, prov.EMPTY),
                routes=routes,
                channels={
                    **route_graphs.p2p_graph().channels,
                    **route_graphs.bank_corridor_graph().channels,
                },
                streams=route_graphs.STREAMS,
                kinds=route_graphs.KINDS,
                on_date=AFTER,
                as_of=route_graphs.AS_OF,
                spendable=route_graphs.p2p_graph().spendable,
            ),
            RampCost,
        )

    def test_the_costing_engine_has_never_heard_of_a_regime(self) -> None:
        # The boundary that makes the collapse unreachable rather than merely discouraged: no
        # module on the costing path imports the scenarios package or names either record, so
        # there is no function a regime could be handed to that could turn it into a leg field.
        # A textual scan, with the same limits as ``test_money_construction_guard``: it would
        # not catch an alias. What it does catch is the obvious version, which is the one that
        # gets written.
        offenders: list[tuple[str, int, str]] = []
        for path in sorted(ROUTES_ROOT.glob("*.py")):
            if path.name in REGIME_AWARE:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith(("import ", "from ")) and "scenarios" in line:
                    offenders.append((path.name, number, line.strip()))
        assert offenders == []

    def test_the_one_regime_aware_route_module_still_cannot_reach_a_leg_window(self) -> None:
        # ``coverage.py`` is exempt from the scan above and this is what it is held to instead
        # -- a stricter test than the one it is exempt from, applied to the one module that
        # needs a regime.
        #
        # Feature 003's FR-013 requires every coverage verdict to be stated **per regime**: a
        # corridor present in wartime and absent from the normalized regime is exactly the fact
        # the audit exists to surface, and a report that blended the two would be the
        # confident-but-wrong summary this project refuses. So the audit has to be handed the
        # regimes, and it lives in ``core/routes/`` because it is a fold over route
        # declarations (003 research.md D1).
        #
        # That is a widening of the scan's *rule* and not of its *reason*. The reason is the
        # hazard named in this module's docstring: a regime reaching a leg's window field, so
        # that an assumption and an observation arrive in the same shape. ``coverage.py`` cannot
        # cause it -- it computes no cost, it consults no window, and it produces no
        # ``RouteUnusable`` -- and the three assertions below are what keep that true rather
        # than merely true today.
        source = (ROUTES_ROOT / "coverage.py").read_text(encoding="utf-8")
        # Comment lines are stripped; **docstrings are not**, and that is intended rather than
        # overlooked. The most natural sentence to write in that module is "this module never
        # reads ``available_until``", and it would fail this test. That is the right trade: the
        # scan is cheap and blunt, and a prose mention is the one false positive it can have.
        # Say it another way if it ever bites -- "no leg availability window is consulted here"
        # -- rather than weakening the scan to allow the field name back into the file.
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
        # It never reads a leg's availability window, so no regime it holds can become one.
        assert "available_from" not in code
        assert "available_until" not in code
        # It never sees a transition -- the dated guess itself -- only the regimes' route sets.
        assert "RegimeTransition" not in code
        # And it never costs anything, so there is no figure for a belief to reach.
        assert "cost_one" not in code
        assert "RouteUnusable" not in code

    def test_the_exempt_module_cannot_become_a_side_door_to_the_scenarios_package(self) -> None:
        # The scan's stated limit -- "it would not catch an alias" -- stopped being
        # hypothetical the moment ``coverage.py`` became a module *inside the scanned
        # directory* that names ``Regime``. ``from terezy.core.routes.coverage import Regime``
        # in ``cost.py`` would satisfy both tests above: the line does not contain
        # "scenarios", and it is not in ``coverage.py``.
        #
        # It fails at runtime today for two accidental reasons -- the import is inside
        # ``if TYPE_CHECKING`` so the name does not exist at run time, and it is absent from
        # ``__all__``. Accidental is not a guarantee, so both are asserted here, and so is the
        # thing that actually matters: no *other* module in the directory names the record.
        source = (ROUTES_ROOT / "coverage.py").read_text(encoding="utf-8")
        before, _, after = source.partition("if TYPE_CHECKING:")
        assert "from terezy.core.scenarios" in after, (
            "coverage.py's scenarios import must stay inside `if TYPE_CHECKING`, so the name "
            "it introduces does not exist at run time for another module to reach through"
        )
        assert "from terezy.core.scenarios" not in before
        exported = [
            (number, line)
            for number, line in _regime_side_doors(source)
            if not line.startswith(("import ", "from "))
        ]
        assert exported == [], (
            f"coverage.py re-exports Regime at {exported}. Its own import is permitted -- the "
            "audit needs the record -- but naming it in __all__ turns this module into the "
            "package's front door to it."
        )

        offenders = [
            (path.name, number, line)
            for path in sorted(ROUTES_ROOT.glob("*.py"))
            if path.name != "coverage.py"
            for number, line in _regime_side_doors(path.read_text(encoding="utf-8"))
        ]
        assert offenders == [], (
            f"these lines bind or re-export Regime outside coverage.py: {offenders}. The import "
            "scan above only looks for the word 'scenarios', so a module reaching the record "
            "through coverage.py -- `from terezy.core.routes.coverage import Regime` -- would "
            "pass it. This is the assertion that closes that door. **Prose is not a side "
            "door**: a comment or a docstring naming the record is not matched, so say what "
            "you need to say about regimes here."
        )

    def test_the_dependency_points_one_way_and_the_selection_needs_no_as_of(self) -> None:
        # Scenarios depend on routes; routes do not depend on scenarios. And the selection
        # takes ``on_date`` only: ``as_of`` decides staleness, and a regime that changed with
        # when the question was asked would not be a regime.
        parameters = inspect.signature(regimes.routes_in_force).parameters
        assert "on_date" in parameters
        assert "as_of" not in parameters


class TestTheSideDoorScanMatchesShapesRatherThanProse:
    """What the scan above is allowed to fail on -- pinned, because it fired on prose once.

    The scan guards a real boundary and its failure message accuses a module of re-exporting a
    record. Both are worth keeping, and both are worthless if the scan cannot tell an import
    from a sentence: the first false positive it can produce is a module explaining the very
    hazard this file is about, and the fix a reader would reach for is deleting the sentence.
    """

    def test_a_docstring_naming_the_record_is_not_a_side_door(self) -> None:
        # The exact sentence the old scan would have failed on, in the module whose subject it
        # is. Nothing here binds the name; a reader of ``cost.py`` cannot reach ``Regime``
        # through a docstring.
        source = '''"""Costing. A ``Regime`` is not a leg window -- see scenarios/regimes.py."""'''
        assert _regime_side_doors(source) == []

    def test_a_comment_naming_the_record_is_not_a_side_door(self) -> None:
        assert _regime_side_doors("# never turn a Regime into a leg's available_until\n") == []

    def test_an_import_binding_the_name_is_a_side_door(self) -> None:
        source = "from terezy.core.routes.coverage import Regime\n"
        assert _regime_side_doors(source) == [(1, "from terezy.core.routes.coverage import Regime")]

    def test_an_all_entry_re_exporting_the_name_is_a_side_door(self) -> None:
        # Both spellings a re-export is written in: the one-line list, and the entry on its own
        # line in a multi-line one.
        assert _regime_side_doors('__all__ = ["Regime", "cost_one"]\n') == [
            (1, '__all__ = ["Regime", "cost_one"]')
        ]
        assert _regime_side_doors('__all__ = [\n    "Regime",\n]\n') == [(2, '"Regime",')]

    def test_the_scan_reports_where_it_found_what_it_found(self) -> None:
        # The failure message quotes these pairs, so a reader is sent to a line rather than to
        # a claim about a re-export that may not be what happened.
        source = "import os\nfrom terezy.core.scenarios.regimes import Regime\n"
        assert _regime_side_doors(source) == [
            (2, "from terezy.core.scenarios.regimes import Regime")
        ]


class TestTheSelectionRefusesAScenarioThatStatesNoBelief:
    """Every refusal leaves some date with no stated regime; supplying one would invent it."""

    def test_no_transitions_at_all(self) -> None:
        with pytest.raises(ValueError, match="no default regime"):
            regimes.routes_in_force(REGIMES, _world(), transitions=(), on_date=AFTER)

    def test_a_transition_naming_an_undeclared_regime(self) -> None:
        broken = dataclasses.replace(TRANSITION, after="postwar_miracle")
        with pytest.raises(KeyError, match="postwar_miracle"):
            regimes.routes_in_force(REGIMES, _world(), transitions=(broken,), on_date=AFTER)

    def test_two_transitions_claiming_the_same_date(self) -> None:
        # Not deduplicated and not reordered: two regimes claiming one date is a contradiction
        # in the scenario, and choosing between them would be choosing the owner's belief.
        second = dataclasses.replace(TRANSITION, before="normalized", after="wartime")
        with pytest.raises(ValueError, match="strictly ascending date order"):
            regimes.routes_in_force(
                REGIMES, _world(), transitions=(TRANSITION, second), on_date=AFTER
            )

    def test_transitions_declared_out_of_order(self) -> None:
        earlier = dataclasses.replace(
            TRANSITION, on_date=date(2027, 1, 1), before="normalized", after="wartime"
        )
        with pytest.raises(ValueError, match="strictly ascending date order"):
            regimes.routes_in_force(
                REGIMES, _world(), transitions=(TRANSITION, earlier), on_date=AFTER
            )

    def test_a_chain_whose_regimes_do_not_join_up(self) -> None:
        # wartime -> normalized, then wartime -> normalized again: the dates between the two
        # transitions belong to ``normalized`` by the first and to ``wartime`` by the second.
        second = dataclasses.replace(TRANSITION, on_date=date(2028, 1, 1))
        with pytest.raises(ValueError, match="regime nobody declared"):
            regimes.routes_in_force(
                REGIMES, _world(), transitions=(TRANSITION, second), on_date=AFTER
            )

    def test_a_regime_naming_a_route_nobody_declared(self) -> None:
        invented = {
            **REGIMES,
            "normalized": regimes.Regime(
                id="normalized", route_ids=frozenset({"bank_uah_to_broker", "hyperloop_to_zurich"})
            ),
        }
        with pytest.raises(KeyError, match="hyperloop_to_zurich"):
            regimes.routes_in_force(invented, _world(), transitions=(TRANSITION,), on_date=AFTER)

    def test_a_regime_that_includes_a_route_but_excludes_its_declared_exit(self) -> None:
        # Refused rather than costed, because costing it would raise on the dangling partner
        # and the message would blame the loader for a scenario's belief. "There is a way in
        # and none out" is a fact about a corridor -- a route declaring ``partner_route =
        # null`` -- not half of a regime.
        one_way = {
            **REGIMES,
            "normalized": regimes.Regime(
                id="normalized", route_ids=frozenset({"bank_uah_to_broker"})
            ),
        }
        with pytest.raises(ValueError, match="cannot make money one-way"):
            regimes.routes_in_force(one_way, _world(), transitions=(TRANSITION,), on_date=AFTER)


class TestACandidateSetIsNarrowedRatherThanRefused:
    """``paths_in_force``: the regime filters candidates, and the filtering is not silent."""

    def _paths(self) -> tuple[FundingPath, ...]:
        return tuple(
            FundingPath(destination_id="venue_1", stream_id="salary_uah", route_id=route_id)
            for route_id in ("monobank_to_binance_p2p", "bank_uah_to_broker")
        )

    def test_only_the_paths_whose_route_the_regime_includes_survive(self) -> None:
        before = regimes.routes_in_force(
            REGIMES, _world(), transitions=(TRANSITION,), on_date=BEFORE
        )
        after = regimes.routes_in_force(REGIMES, _world(), transitions=(TRANSITION,), on_date=AFTER)
        assert [candidate_id(p) for p in regimes.paths_in_force(self._paths(), before)] == [
            "monobank_to_binance_p2p"
        ]
        assert [candidate_id(p) for p in regimes.paths_in_force(self._paths(), after)] == [
            "bank_uah_to_broker"
        ]

    def test_what_was_filtered_out_is_named_on_the_selection(self) -> None:
        # The filtering is not silent, and this is where that claim is cashed: every path
        # dropped names a route the selection already reported as excluded.
        after = regimes.routes_in_force(REGIMES, _world(), transitions=(TRANSITION,), on_date=AFTER)
        kept = {candidate_id(p) for p in regimes.paths_in_force(self._paths(), after)}
        dropped = {candidate_id(p) for p in self._paths()} - kept
        assert dropped <= set(after.excluded)

    def test_the_order_the_caller_gave_is_preserved(self) -> None:
        # A ranking is deterministic partly because its input order is, so the filter must not
        # reorder. Asserted rather than assumed: a set comprehension here would have been the
        # obvious way to write it and would have destroyed the property silently.
        both = regimes.Regime(
            id="normalized",
            route_ids=frozenset({"bank_uah_to_broker", "broker_to_bank"})
            | frozenset({"monobank_to_binance_p2p", "binance_p2p_to_monobank"}),
        )
        in_force = regimes.routes_in_force(
            {**REGIMES, "normalized": both}, _world(), transitions=(TRANSITION,), on_date=AFTER
        )
        given = self._paths()
        assert regimes.paths_in_force(given, in_force) == given
        assert regimes.paths_in_force(tuple(reversed(given)), in_force) == tuple(reversed(given))


class TestASequenceOfTransitionsFoldsToOneRegime:
    """The selection takes a whole sequence, and a valid chain of them joins up.

    ``data-model.md`` records that this feature *declares* one transition, because a second
    needs a second assumption the owner has not stated -- and no declaration file here states
    one. The selection function nonetheless takes a sequence, so the chain arithmetic exists
    and is asserted rather than assumed: a validation loop that has never run to completion on
    a well-formed chain is validation nobody has tested.

    Each link is still an assumption in its own right. Two of them do not average into a
    forecast; they compound into a longer conditional, and the output states both.
    """

    def _chain(self) -> tuple[regimes.RegimeTransition, ...]:
        # wartime -> normalized (mid-2027) -> wartime again (2029), the second link being the
        # belief that normalization could reverse. Invented, like the first.
        return (
            TRANSITION,
            dataclasses.replace(
                TRANSITION,
                on_date=date(2029, 1, 1),
                before="normalized",
                after="wartime",
                rationale="The owner assumes normalization could reverse. Also a belief.",
            ),
        )

    @pytest.mark.parametrize(
        ("on_date", "expected"),
        [
            (date(2026, 1, 1), "wartime"),
            (date(2027, 7, 1), "normalized"),
            (date(2028, 12, 31), "normalized"),
            (date(2029, 1, 1), "wartime"),
            (date(2030, 6, 1), "wartime"),
        ],
    )
    def test_each_segment_of_the_chain_selects_its_own_regime(
        self, on_date: date, expected: str
    ) -> None:
        in_force = regimes.routes_in_force(
            REGIMES, _world(), transitions=self._chain(), on_date=on_date
        )
        assert in_force.regime.id == expected

    def test_the_transition_reported_is_the_one_that_decided_the_date(self) -> None:
        # Not the first, and not the last: the one whose date the movement fell after. An
        # output naming the wrong link would attach the wrong rationale to the figure.
        chain = self._chain()
        assert (
            regimes.routes_in_force(
                REGIMES, _world(), transitions=chain, on_date=date(2028, 6, 1)
            ).decided_by
            is chain[0]
        )
        assert (
            regimes.routes_in_force(
                REGIMES, _world(), transitions=chain, on_date=date(2029, 6, 1)
            ).decided_by
            is chain[1]
        )
