"""What is exposed: one row per declared category, and the entry point behind each.

A mapping from category to a resolver entry point and a response type, never a hand-written
route function per category doing its own loading. The set is fail-closed against `data/` in
both directions -- every directory at any depth is covered by a row or named in
:data:`EXEMPT_DIRECTORIES` with its reason, and every `*_DIR`/`*_FILE` constant in the resolver
is named by a row -- and both directions are asserted, separately, so either can go red alone
(020 FR-005 to FR-007).

Each row resolves **records and their declaring files in one call**, because a read has to say
which file declared what it returned and two calls would load the same root twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from terezy.api.http import envelopes
from terezy.core.calendars.working_day import WorkingDayCalendar
from terezy.core.inflation.series import CpiSeries, InflationAssumption
from terezy.core.instruments.access import InstrumentAccess
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.instruments.groups import InstrumentGroup
from terezy.core.instruments.interface import InstrumentDeclaration
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.candidates import CandidateCeiling
from terezy.core.results.composed import SegmentBound
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.goal import Goal
from terezy.core.results.question import Question
from terezy.core.routes.channels import FxChannel
from terezy.core.routes.legs import Route
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.early_exit import SpreadHolds
from terezy.core.streams.streams import IncomeStream
from terezy.core.tax.interface import TaxClass
from terezy.core.tax.official_rate import OfficialRateSeries
from terezy.core.tax.scheme import CreditingDestination, TaxationScheme
from terezy.core.tax.year import AssessmentRules, FilingDecisions, UnsettledPositions
from terezy.data.declarations import loader, resolver

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from terezy.core.primitives.currency import Currency

DESTINATION_SEPARATOR: Final[str] = ":"
"""How a crediting destination's ``(scheme, venue)`` key becomes one path segment.

The resolver keys that category by a pair and a path segment is one string. A colon appears in
neither half of any declared key, and the list read publishes the encoded ids, so a client never
composes one itself.
"""

EXEMPT_DIRECTORIES: Final[Mapping[str, str]] = {
    "observations": (
        "no loader exists anywhere in src/terezy/. These are a fetch script's raw retrievals, "
        "read by a human promoting them into a declaration and by nothing at run time; serving "
        "them would make the API the first consumer of data the engine deliberately does not "
        "consume"
    ),
    "instruments/nav": (
        "deliberately not globbed by the resolver, which states at its own glob that a "
        "subdirectory holds a different shape of file. Empty today, and a category for it would "
        "be a second instrument shape this feature has no response type for"
    ),
    "objectives": "empty but for .gitkeep, and no loader exists",
    "strategies": "empty but for .gitkeep, and no loader exists",
}
"""Directories under `data/` no category serves, each with the reason it does not.

Exempt because *nothing loads them*, not because they are empty: the day one gains a resolver
entry point it gains a category, and its reason here is what stops that being forgotten.
"""


@dataclass(frozen=True, slots=True)
class Ask:
    """What a read resolves under: one data root, one base currency, at most one scenario."""

    root: Path
    base_currency: Currency
    scenario_id: str | None


@dataclass(frozen=True, slots=True)
class NoFileMap:
    """A category whose entry point does not say which file declared a record, and why."""

    reason: str


@dataclass(frozen=True, slots=True)
class KeyedRecords:
    records: Mapping[str, object]
    files: Mapping[str, Path] | NoFileMap


@dataclass(frozen=True, slots=True)
class SingleRecord:
    """One resolved document, or ``None`` where the loader found nothing to resolve."""

    record: object | None
    file: Path | None


@dataclass(frozen=True, slots=True)
class ManyRecords:
    """A document that is a collection. ``file`` absent means nothing declared it at all."""

    records: tuple[object, ...]
    file: Path | None


@dataclass(frozen=True, slots=True)
class Keyed:
    """A category resolving a collection a declared string selects from."""

    resolve: Callable[[Ask], KeyedRecords]
    record: object


@dataclass(frozen=True, slots=True)
class Document:
    """A per-owner category resolving to one record by an at-most-one rule."""

    resolve: Callable[[Ask], SingleRecord]
    record: object


@dataclass(frozen=True, slots=True)
class Collection:
    """A per-owner category whose one document is a collection of records."""

    resolve: Callable[[Ask], ManyRecords]
    record: object


@dataclass(frozen=True, slots=True)
class Category:
    """One row: what it is called, what covers it under `data/`, and how it resolves."""

    id: str
    constant: str
    """The name of the `resolver` constant this category covers, so the reverse check reads the
    resolver rather than a second copy of its paths."""

    scenario: bool
    shape: Keyed | Document | Collection


def _instruments(ask: Ask) -> KeyedRecords:
    declared = resolver.from_data_root(ask.root)
    return KeyedRecords(
        records={**declared.instruments, **declared.funds},
        files={**declared.instrument_files, **declared.fund_files},
    )


def _groups(ask: Ask) -> KeyedRecords:
    declared = resolver.from_data_root(ask.root)
    return KeyedRecords(
        records=declared.groups,
        files=dict.fromkeys(declared.groups, declared.groups_file),
    )


def _tax_classes(ask: Ask) -> KeyedRecords:
    declared = resolver.from_data_root(ask.root)
    return KeyedRecords(records=declared.tax_classes, files=declared.tax_class_files)


def _ramp(ask: Ask) -> resolver.RampDeclarations:
    return resolver.ramp_from_data_root(ask.root, base_currency=ask.base_currency)


def _kinds(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.kinds, files=ramp.kind_files)


def _venues(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.venues, files=ramp.venue_files)


def _channels(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.channels, files=ramp.channel_files)


def _routes(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.routes, files=ramp.route_files)


def _streams(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.streams, files=ramp.stream_files)


def _scenarios(ask: Ask) -> KeyedRecords:
    ramp = _ramp(ask)
    return KeyedRecords(records=ramp.scenarios, files=ramp.scenario_files)


def _spendable(ask: Ask) -> ManyRecords:
    coverage = resolver.coverage_from_data_root(
        ask.root, base_currency=ask.base_currency, scenario_id=ask.scenario_id
    )
    return ManyRecords(records=tuple(coverage.spendable), file=coverage.spendable_file)


def _composition(ask: Ask) -> SingleRecord:
    composition = resolver.composition_from_data_root(
        ask.root, base_currency=ask.base_currency, scenario_id=ask.scenario_id
    )
    return SingleRecord(record=composition.bound, file=composition.composition_file)


def _candidate_ceiling(ask: Ask) -> SingleRecord:
    candidates = resolver.candidates_from_data_root(
        ask.root, base_currency=ask.base_currency, scenario_id=ask.scenario_id
    )
    return SingleRecord(record=candidates.ceiling, file=candidates.candidates_file)


def _tuples(ask: Ask) -> resolver.TupleDeclarations:
    return resolver.tuple_from_data_root(
        ask.root, base_currency=ask.base_currency, scenario_id=ask.scenario_id
    )


def _access(ask: Ask) -> KeyedRecords:
    tuples = _tuples(ask)
    return KeyedRecords(records=tuples.access, files=tuples.access_files)


def _early_exit(ask: Ask) -> SingleRecord:
    tuples = _tuples(ask)
    return SingleRecord(
        record=tuples.registries.spread_holds,
        file=tuples.early_exit_file,
    )


def _seeds_and_goals(ask: Ask) -> resolver.SeedAndGoalDeclarations:
    return resolver.seeds_and_goals_from_data_root(ask.root, base_currency=ask.base_currency)


def _seeds(ask: Ask) -> ManyRecords:
    declared = _seeds_and_goals(ask)
    return ManyRecords(records=declared.seeds, file=declared.seed_file)


def _goals(ask: Ask) -> KeyedRecords:
    declared = _seeds_and_goals(ask)
    return KeyedRecords(
        records={goal.id: goal for goal in declared.goals},
        files=(
            {}
            if declared.goal_file is None
            else {goal.id: declared.goal_file for goal in declared.goals}
        ),
    )


def _cpi(ask: Ask) -> KeyedRecords:
    inflation = resolver.inflation_from_data_root(ask.root)
    return KeyedRecords(records=inflation.series, files=inflation.series_files)


def _inflation_assumption(ask: Ask) -> SingleRecord:
    inflation = resolver.inflation_from_data_root(ask.root)
    return SingleRecord(record=inflation.assumption, file=inflation.assumption_file)


def _official_rates(ask: Ask) -> KeyedRecords:
    rates = resolver.official_rates_from_data_root(ask.root, _ramp(ask).kinds)
    return KeyedRecords(records=rates.series, files=rates.files)


def _schemes(ask: Ask) -> KeyedRecords:
    schemes = resolver.schemes_from_data_root(ask.root, base_currency=ask.base_currency)
    return KeyedRecords(records=schemes.schemes, files=schemes.scheme_files)


def destination_id(key: tuple[str, str]) -> str:
    """The one path segment a `(scheme, venue)` key is addressed by."""
    return DESTINATION_SEPARATOR.join(key)


def _destinations(ask: Ask) -> KeyedRecords:
    schemes = resolver.schemes_from_data_root(ask.root, base_currency=ask.base_currency)
    return KeyedRecords(
        records={destination_id(key): held for key, held in schemes.destinations.items()},
        files={destination_id(key): path for key, path in schemes.destination_files.items()},
    )


def _tax_timing(ask: Ask) -> KeyedRecords:
    rules = resolver.tax_rules_from_data_root(ask.root, resolver.from_data_root(ask.root))
    return KeyedRecords(
        records=rules,
        files=NoFileMap(
            reason=(
                "tax_rules_from_data_root returns assessment rules by jurisdiction and no file "
                "map, so the file a jurisdiction's rules were read from is not recoverable "
                "without re-globbing the directory -- which would be a second copy of the "
                "loader's own naming rule"
            )
        ),
    )


TaxPositions = envelopes.container(
    "TaxPositions",
    (("filing", FilingDecisions), ("unsettled", UnsettledPositions)),
)
"""The two records `tax_positions_from_data_root` resolves together, in one document.

A container rather than two categories: they are resolved by one at-most-one rule over one
file, and splitting them would make two endpoints that can disagree about whether that file
exists.
"""


def _tax_positions(ask: Ask) -> SingleRecord:
    resolved = resolver.tax_positions_from_data_root(ask.root)
    if resolved is None:
        return SingleRecord(record=None, file=None)
    filing, unsettled, path = resolved
    return SingleRecord(record=TaxPositions(filing=filing, unsettled=unsettled), file=path)


def _questions(ask: Ask) -> KeyedRecords:
    answers = resolver.answer_from_data_root(
        ask.root, base_currency=ask.base_currency, scenario_id=ask.scenario_id
    )
    return KeyedRecords(records=answers.questions, files=answers.question_files)


def _calendars(ask: Ask) -> KeyedRecords:
    calendars = resolver.working_day_calendars_from_data_root(ask.root, _ramp(ask).kinds)
    return KeyedRecords(records=calendars.calendars, files=calendars.files)


CATEGORIES: Final[tuple[Category, ...]] = (
    Category(
        "instruments",
        "INSTRUMENTS_DIR",
        False,
        Keyed(_instruments, InstrumentDeclaration | FundDeclaration),
    ),
    Category("groups", "GROUPS_FILE", False, Keyed(_groups, InstrumentGroup)),
    Category("tax-classes", "TAX_DIR", False, Keyed(_tax_classes, TaxClass)),
    Category("observation-kinds", "KINDS_FILE", False, Keyed(_kinds, ObservationKind)),
    Category("venues", "VENUES_FILE", False, Keyed(_venues, Venue)),
    Category("channels", "CHANNELS_DIR", False, Keyed(_channels, FxChannel)),
    Category("routes", "ROUTES_DIR", False, Keyed(_routes, Route)),
    Category("streams", "STREAMS_DIR", False, Keyed(_streams, IncomeStream)),
    Category("scenarios", "SCENARIOS_DIR", False, Keyed(_scenarios, loader.ScenarioDeclaration)),
    Category("spendable", "SPENDABLE_DIR", True, Collection(_spendable, SpendableEndpoint)),
    Category("composition", "COMPOSITION_DIR", True, Document(_composition, SegmentBound)),
    Category(
        "candidate-ceiling", "CANDIDATES_DIR", True, Document(_candidate_ceiling, CandidateCeiling)
    ),
    Category("access", "ACCESS_DIR", True, Keyed(_access, InstrumentAccess)),
    Category("seeds", "SEEDS_DIR", False, Collection(_seeds, SeedLot)),
    Category("goals", "GOALS_DIR", False, Keyed(_goals, Goal)),
    Category("cpi", "CPI_DIR", False, Keyed(_cpi, CpiSeries)),
    Category(
        "inflation-assumption",
        "INFLATION_ASSUMPTION_DIR",
        False,
        Document(_inflation_assumption, InflationAssumption),
    ),
    Category(
        "official-rates", "OFFICIAL_RATES_DIR", False, Keyed(_official_rates, OfficialRateSeries)
    ),
    Category("tax-schemes", "SCHEMES_DIR", False, Keyed(_schemes, TaxationScheme)),
    Category(
        "crediting-destinations",
        "DESTINATIONS_DIR",
        False,
        Keyed(_destinations, CreditingDestination),
    ),
    Category("tax-timing", "TAX_TIMING_DIR", False, Keyed(_tax_timing, AssessmentRules)),
    Category("tax-positions", "TAX_POSITIONS_DIR", False, Document(_tax_positions, TaxPositions)),
    Category("early-exit-belief", "EARLY_EXIT_DIR", True, Document(_early_exit, SpreadHolds)),
    Category("questions", "QUESTIONS_DIR", True, Keyed(_questions, Question)),
    Category("calendars", "CALENDARS_DIR", False, Keyed(_calendars, WorkingDayCalendar)),
)

BY_ID: Final[Mapping[str, Category]] = {category.id: category for category in CATEGORIES}


def directory_of(category: Category) -> str:
    """The path under `data/` this category covers, read off the resolver's own constant."""
    return str(getattr(resolver, category.constant))


def is_keyed(category: Category) -> bool:
    """Whether the category offers a list and a read of one id, rather than one document."""
    return isinstance(category.shape, Keyed)
