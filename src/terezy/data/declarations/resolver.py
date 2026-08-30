"""The cross-file pass: the checks a per-file validator structurally cannot make.

``schema.py`` validates one document at a time, which is all pydantic can see. Two of
feature 001's FR-016 rules span files and are therefore impossible there -- and feature 002
added nine more of the same kind, enumerated in their own section further down:

* **A duplicate identifier.** Each file is individually valid; together they declare two
  different things with one name, and whichever loaded second would win by accident of
  directory ordering. The error names **both** files, because knowing only one of them
  leaves the reader to find the other by hand.
* **A reference to an undeclared tax class.** An instrument's ``tax_classes`` table holds
  references; whether they resolve depends on the tax files. Unresolved is reported and
  **never read as an exemption** -- a missing rule and a declared zero are opposite
  claims, and only one of them is cited (Principle I). This is the single most expensive
  silent default available in this domain: it would make every after-tax figure flattering
  by exactly the tax that was not charged.

So the order is fixed and is the whole design: **parse every file individually first,
then resolve.** A resolver that loaded lazily could not report a duplicate at all, since
it would never hold both declarations at once.

A third check lives here for the same reason -- it needs both sides. An instrument may
reference a class that exists but whose ``applies_to`` does not cover the income kind it
was referenced for. The tax rule refuses such a charge at run time (*"the rule does not
cover this"* and *"the rule applied and the answer was zero"* are opposite claims), and
catching it here turns a refusal mid-projection into a message about the file that caused
it.

**No caching, no global registry.** :func:`resolve` takes the files it is to read and
returns a value. A module-level cache would make the second call in a process depend on
the first, which is exactly the hidden state that makes a determinism claim (C4)
unverifiable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from terezy.core.decision.tuple_outcome import Registries
from terezy.core.instruments import registry as instrument_registry
from terezy.core.primitives import money
from terezy.core.routes.venues import can_hold
from terezy.core.tax.scheme import Verdict
from terezy.core.tax.year import AssessmentRules
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping, Sequence

    from terezy.core.inflation.series import CpiSeries, InflationAssumption
    from terezy.core.instruments.access import InstrumentAccess
    from terezy.core.instruments.fund import FundDeclaration
    from terezy.core.instruments.groups import InstrumentGroup
    from terezy.core.instruments.interface import InstrumentDeclaration
    from terezy.core.ledger.seeds import SeedLot
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.money import Money
    from terezy.core.primitives.staleness import ObservationKind
    from terezy.core.results.candidates import CandidateCeiling
    from terezy.core.results.composed import SegmentBound
    from terezy.core.results.coverage import SpendableEndpoint
    from terezy.core.results.goal import Goal
    from terezy.core.results.question import Question
    from terezy.core.routes.channels import FxChannel
    from terezy.core.routes.legs import Leg, Route
    from terezy.core.routes.venues import Venue
    from terezy.core.scenarios.early_exit import SpreadHolds
    from terezy.core.scenarios.regimes import Regime
    from terezy.core.streams.streams import IncomeStream
    from terezy.core.tax import year as tax_year
    from terezy.core.tax.interface import TaxClass
    from terezy.core.tax.official_rate import OfficialRateSeries
    from terezy.core.tax.scheme import CreditingDestination, TaxationScheme
    from terezy.data.declarations.loader import ScenarioDeclaration

INSTRUMENTS_DIR = "instruments"
"""Where instrument declarations live under a data root."""

TAX_DIR = "tax"
"""Where jurisdiction rule packs live under a data root."""

GROUPS_FILE = "groups.toml"
"""The group vocabulary, at the data root beside ``venues.toml`` (015 FR-007a).

Curated and root-level rather than per-owner, because the *label* is on the curated instrument
declaration: a per-owner vocabulary would make an instrument file fail to load because somebody
else's directory was absent.
"""


@dataclass(frozen=True, slots=True)
class Declarations:
    """Every declaration one run was given, resolved and keyed by id.

    A frozen record carrying only data, like everything else in the project. The two file
    maps are not decoration: they are what lets a *later* failure -- a manifest entry
    (FR-012), an unresolved reference discovered downstream -- still name the file a
    declaration came from, after the TOML has long since been discarded.
    """

    instruments: Mapping[str, InstrumentDeclaration]
    """Declared instruments by id. Every ``tax_classes`` reference in here resolves
    against :attr:`tax_classes`; that is checked before this record exists."""

    tax_classes: Mapping[str, TaxClass]
    """Declared tax classes by id, ready to pass to ``results.project`` as the tax pack."""

    instrument_files: Mapping[str, Path]
    """Which file declared each instrument."""

    tax_class_files: Mapping[str, Path]
    """Which file declared each tax class."""

    funds: Mapping[str, FundDeclaration]
    """⚙ **Added by feature 006.** Declared collective-investment funds by id.

    A separate map rather than a wider :attr:`instruments`, because a fund and a bond have
    almost nothing in common beyond an id: no coupon, no maturity, no face value. One map
    of a union type would make every consumer narrow before it could read a field, and the
    two are consumed by different projections anyway.

    The **id space is shared**, though: a fund and a bond declaring the same id is a
    duplicate and is refused, because a holding names an instrument by id and would
    otherwise resolve to whichever map was searched first.
    """

    fund_files: Mapping[str, Path]
    """Which file declared each fund."""

    groups: Mapping[str, InstrumentGroup]
    """The declared group vocabulary by id (015 FR-007a).

    Every ``groups`` label on every instrument and fund above resolves against this; that is
    checked before this record exists.
    """

    groups_file: Path
    """Which file declared the vocabulary, so the manifest can name it after the TOML is gone."""


def _refuse_duplicate(
    kind: str,
    identifier: str,
    field_path: str,
    already: Path,
    now: Path,
) -> DeclarationError:
    """The duplicate-id error, naming both files. Built here so both callers agree.

    Returned rather than raised so the raise stays at the call site, where the reader can
    see which loop found the collision.
    """
    return DeclarationError(
        now,
        field_path,
        f"declares the {kind} id {identifier!r}, which is already declared by "
        f"{already}. Two declarations with one id are not merged and neither is "
        "preferred: whichever loaded last would win by accident of directory ordering, "
        "and every figure would silently describe the wrong one.",
        f"rename one of the two {kind}s, or delete the file that is a duplicate",
    )


def resolve(
    *,
    instrument_files: Sequence[Path],
    tax_files: Sequence[Path],
    groups_file: Path,
) -> Declarations:
    """Parse every file, then check what only the whole set can show.

    Files are read in the order given and the caller is expected to have sorted them
    (:func:`from_data_root` does), so that a duplicate is always reported against the same
    one of the two files rather than depending on filesystem iteration order.
    """
    tax_classes: dict[str, TaxClass] = {}
    tax_class_files: dict[str, Path] = {}
    for path in tax_files:
        for declared in loader.tax_classes_from_file(path):
            if declared.id in tax_classes:
                raise _refuse_duplicate(
                    "tax class",
                    declared.id,
                    f"jurisdiction.tax_class[{declared.id}].id",
                    tax_class_files[declared.id],
                    path,
                )
            tax_classes[declared.id] = declared
            tax_class_files[declared.id] = path

    instruments: dict[str, InstrumentDeclaration] = {}
    instrument_files_by_id: dict[str, Path] = {}
    funds: dict[str, FundDeclaration] = {}
    fund_files_by_id: dict[str, Path] = {}
    files_by_id: dict[str, Path] = {}
    for path in instrument_files:
        # ⚙ feature 006: one directory, several kinds of declaration, told apart by the one
        # key they share and dispatched through a declared mapping rather than a branch
        # naming a class. See ``loader.declared_class_of`` and ``LOADERS_BY_KIND``.
        read = LOADERS_BY_KIND[_kind_of(path)]
        if read is loader.fund_from_file:
            declared_fund = loader.fund_from_file(path)
            if declared_fund.id in files_by_id:
                raise _refuse_duplicate(
                    "instrument",
                    declared_fund.id,
                    "instrument.id",
                    files_by_id[declared_fund.id],
                    path,
                )
            funds[declared_fund.id] = declared_fund
            fund_files_by_id[declared_fund.id] = path
            files_by_id[declared_fund.id] = path
            continue
        # ⚙ feature 013: both bond forms produce an ``InstrumentDeclaration``, so the id
        # space, the duplicate check and the tax-class resolution below are shared. A
        # duplicate id therefore collides across the forms as well as within one.
        declaration = (
            loader.enumerated_instrument_from_file(path)
            if read is loader.enumerated_instrument_from_file
            else loader.instrument_from_file(path)
        )
        if declaration.id in files_by_id:
            raise _refuse_duplicate(
                "instrument",
                declaration.id,
                "instrument.id",
                files_by_id[declaration.id],
                path,
            )
        instruments[declaration.id] = declaration
        instrument_files_by_id[declaration.id] = path
        files_by_id[declaration.id] = path

    groups = {group.id: group for group in loader.groups_from_file(groups_file)}
    for identifier, declaration in instruments.items():
        _check_references(
            declaration,
            tax_classes,
            path=instrument_files_by_id[identifier],
        )
        _check_groups(declaration.groups, groups, path=instrument_files_by_id[identifier])
    for identifier, declared_fund in funds.items():
        _check_fund_references(
            declared_fund,
            tax_classes,
            path=fund_files_by_id[identifier],
        )
        _check_groups(declared_fund.groups, groups, path=fund_files_by_id[identifier])

    return Declarations(
        instruments=instruments,
        tax_classes=tax_classes,
        instrument_files=instrument_files_by_id,
        tax_class_files=tax_class_files,
        funds=funds,
        fund_files=fund_files_by_id,
        groups=groups,
        groups_file=groups_file,
    )


def _check_groups(
    labels: Sequence[str],
    groups: Mapping[str, InstrumentGroup],
    *,
    path: Path,
) -> None:
    """Every group an instrument declares itself into must be declared (015 FR-007a).

    Refused rather than reported, and the asymmetry with a *question* naming an unknown word is
    deliberate: an instrument is curated data and its typos are defects, while a question is the
    owner's own vocabulary and its gaps are the answer's content (FR-009).
    """
    for position, label in enumerate(labels):
        if label not in groups:
            raise DeclarationError(
                path,
                f"{loader.INSTRUMENT_TABLE}.groups[{position}]",
                f"names the group {label!r}, which {GROUPS_FILE} does not declare. Membership "
                "is a declared label and never a rule, so there is nothing to infer it from: a "
                "label nobody declared would silently put this instrument in no group, and a "
                "question asking about that group would answer without it.",
                f"declare {label!r} in {GROUPS_FILE}, or name one of {sorted(groups)}",
            )


def _check_references(
    declaration: InstrumentDeclaration,
    tax_classes: Mapping[str, TaxClass],
    *,
    path: Path,
) -> None:
    """Every tax class an instrument names must exist **and** cover the kind named.

    Both halves matter, and the second is the easier one to get wrong. A class that exists
    but does not apply to the income kind it was referenced for would pass a naive
    existence check and then be refused by the tax rule mid-projection -- reported against
    an event rather than against the file that declared the reference.
    """
    for kind, class_id in declaration.tax_classes.items():
        field_path = f"instrument.tax_classes.{kind.value}"
        declared = tax_classes.get(class_id)
        if declared is None:
            raise DeclarationError(
                path,
                field_path,
                f"{declaration.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which no tax file declares. The reference is reported "
                "rather than treated as untaxed: an exemption is a cited claim and a "
                "missing rule is not, and reading the second as the first would flatter "
                "every figure derived from this instrument by exactly the tax that was "
                "never charged.",
                f"declare {class_id!r} in a data/tax file, or reference a class that exists"
                f" ({', '.join(sorted(tax_classes)) or 'none are declared'})",
            )
        if kind not in declared.applies_to:
            raise DeclarationError(
                path,
                field_path,
                f"{declaration.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which declares that it applies to "
                f"{', '.join(sorted(applies.value for applies in declared.applies_to))} "
                "and not to that kind. A class asked to charge a kind outside its own "
                "scope refuses rather than charging zero, so the reference would fail "
                "mid-projection instead of here.",
                f"add {kind.value!r} to that class's applies_to if the rule covers it, or "
                "reference the class that does",
            )


def from_data_root(root: Path) -> Declarations:
    """Every declaration under a data root: ``instruments/*.toml`` and ``tax/*.toml``.

    Sorted, so a run is reproducible: an unsorted directory listing would make the order
    of two files -- and therefore which one a duplicate-id error names -- depend on the
    filesystem.

    Only the top level of each directory is read. ``instruments/nav/`` holds dated NAV and
    distribution series, which are a different shape and a different feature; globbing
    recursively would try to validate them as declarations and report a confusing failure
    about a file that is perfectly correct.

    An empty directory is an **error**, not an empty world. Silently returning no
    declarations would make a mistyped path indistinguishable from a repository with no
    data, and every downstream reference would then fail for a reason that names the
    wrong thing.
    """
    instruments = sorted((root / INSTRUMENTS_DIR).glob("*.toml"))
    tax = sorted((root / TAX_DIR).glob("*.toml"))
    for directory, found in ((INSTRUMENTS_DIR, instruments), (TAX_DIR, tax)):
        if not found:
            raise DeclarationError(
                root / directory,
                "",
                f"contains no *.toml declarations. An empty {directory} directory is "
                "reported rather than read as 'nothing is declared': the two are "
                "indistinguishable to everything downstream, and one of them is a "
                "mistyped path.",
                "check the data root, or add a declaration file",
            )
    groups_file = root / GROUPS_FILE
    if not groups_file.is_file():
        raise DeclarationError(
            groups_file,
            "",
            "does not exist, so no group an instrument declares itself into can be resolved. "
            "It is reported rather than read as an empty vocabulary: every label would then be "
            "unresolvable and every question naming a group would answer about nothing.",
            "check the data root, or declare the groups the instruments name",
        )
    return resolve(instrument_files=instruments, tax_files=tax, groups_file=groups_file)


# ---------------------------------------------------------------------------
# 002-ramp-cost: the ramp's cross-file pass
# ---------------------------------------------------------------------------
#
# Everything below answers a question one file cannot: does the thing this file *names*
# exist, and do two files agree about it. The division is the same one the module docstring
# argues -- shape in ``schema``, meaning in ``loader``, **relations here** -- and the reason
# is the same: pydantic validates a document, and by the time it fails the other documents
# have not been read.
#
# Nine relations, and each one is a row of the enforced-rules table in
# ``contracts/declaration-schema.md``:
#
# 1. **Duplicate ids** across files, for every kind of declaration. The error names both
#    files, because knowing one of the two leaves the reader to find the other by hand.
# 2. **Duplicate ``(provider x currency path x venue)``** triples (FR-023). Identity is the
#    triple and not the provider, because conversion count is usually the largest difference
#    between two ways of doing the same thing -- and two entries that collide on the triple
#    are two descriptions of one corridor, of which at most one can be right.
# 3. **Kind resolution.** Every ``kind`` and ``kind_of_observation`` names a declared
#    ``ObservationKind`` (FR-028), so no observed value ages under a threshold nobody set.
# 4. **Venue and channel references**, including whether the venue can *hold* the currency
#    the leg moves through it -- the check ``Venue.currencies`` exists for.
# 5. **Leg chaining** (research.md D6): leg *n* ends where leg *n+1* begins, the first leg
#    starts at the route's ``origin``, the last ends at its ``destination``.
# 6. **``partner_route`` resolution** (FR-027): the id exists, names an ``exit`` route,
#    starts where the inbound route ends -- at that venue **and in the currency the inbound
#    delivers there** -- and finishes holding the base currency.
# 7. **``capacity_pool`` cap agreement** across *files* (research.md D10). Two legs naming
#    one rail must declare one cap.
# 8. **A regime's ``route_ids``** resolve, and a regime is **partner-closed**.
# 9. **A stream's ``arrives_at``** names a declared venue.
#
# ⚙ **Every declared kind resolves here, and the rule has been learned twice.** An earlier
# revision validated a channel *side's* kind at load and then dropped it, so the core aged
# every side under ``FxChannel.kind`` -- a 7-day premium under a 365-day schedule threshold,
# reported fresh. Feature 010 then shipped ``[access.price].kind`` carried into the record and
# resolved nowhere: a typo loaded clean, resolved clean, and raised ``KeyError`` out of the
# pure core, whose message calls that a programmer error. A data-file typo is not one.
#
# Because the same shape appeared twice, the third guard is a **scan rather than a field**:
# ``tests/contract/test_access_declaration_loading.py`` walks every ``SourceRef`` reachable
# from the resolved registries and requires each to carry a kind that this file's registry
# declares. A new declaration kind whose citation nobody resolves fails there, whether or not
# anybody remembered to add a line to the list above.

BASE_CURRENCY_ROLE = (
    "the base currency is the currency the owner earns and spends -- the ledger's home "
    "currency (Principle VI). It is passed in rather than read off the tax pack's "
    "base_currency, because the tax role of currency is a different role from the base "
    "role and conflating two of the three is itself a defect."
)
"""Why the base currency is an argument. Quoted in the error that uses it, so the reason
travels with the refusal rather than living only in a docstring."""

KINDS_FILE = "observation_kinds.toml"
"""Where staleness thresholds are declared, relative to a data root."""

VENUES_FILE = "venues.toml"
"""Where venues are declared, relative to a data root."""

CHANNELS_DIR = "channels"
"""Where two-sided rate declarations live under a data root."""

ROUTES_DIR = "routes"
"""Where route declarations live under a data root."""

STREAMS_DIR = "streams"
"""Where per-owner income streams live under a data root. **Per-owner, not curated** --
the Principle VII boundary, made structural."""

SCENARIOS_DIR = "scenarios"
"""Where regimes and their transitions live under a data root."""


@dataclass(frozen=True, slots=True)
class RampDeclarations:
    """Every declaration a ramp comparison needs, resolved and keyed by id.

    ⚙ **A second record beside :class:`Declarations` rather than more fields on it.** The
    two describe different runs: a projection needs instruments and tax classes, a ramp
    comparison needs routes, channels, streams, kinds and scenarios, and neither needs the
    other's inputs. Merging them would make ``from_data_root`` require six directories
    before it could load a bond, which would break every caller that has one -- and would
    mean a data root with no routes could not project an instrument, which is not a fact
    about the world.

    The file maps are not decoration: they are what lets a *later* failure still name the
    file a declaration came from, after the TOML has been discarded.
    """

    kinds: Mapping[str, ObservationKind]
    """Declared observation kinds by id -- the ``kinds`` argument of ``cost_one`` and
    ``rank``."""

    venues: Mapping[str, Venue]
    """Declared venues by id. Consumed by this pass rather than by the core: the core's
    costing takes routes and channels, and the venue's currency set exists so a leg moving a
    currency its endpoint cannot hold fails *here*, naming the file and the leg index."""

    channels: Mapping[str, FxChannel]
    """Declared channels by id -- the ``channels`` argument of ``cost_one`` and ``rank``."""

    routes: Mapping[str, Route]
    """Declared routes by id -- the ``routes`` argument. Every ``partner_route`` in here
    resolves, and every chain is continuous; that is checked before this record exists."""

    streams: Mapping[str, IncomeStream]
    """Declared income streams by id -- the ``streams`` argument."""

    scenarios: Mapping[str, ScenarioDeclaration]
    """Declared scenarios by id. Each one's regimes name only declared routes and are
    partner-closed."""

    base_currency: Currency
    """The base currency this set was resolved against.

    Carried so a later reader can see which currency the exit routes were required to end
    in. A record that had been checked against one base currency and was read as though it
    had been checked against another would make the round-trip guarantee meaningless.
    """

    kind_files: Mapping[str, Path]
    """Which file declared each observation kind."""

    venue_files: Mapping[str, Path]
    """Which file declared each venue."""

    channel_files: Mapping[str, Path]
    """Which file declared each channel."""

    route_files: Mapping[str, Path]
    """Which file declared each route."""

    stream_files: Mapping[str, Path]
    """Which file declared each stream."""

    scenario_files: Mapping[str, Path]
    """Which file declared each scenario."""


def _identity(route: Route) -> tuple[str, tuple[str, ...], str, str]:
    """A route's registry identity: ``(provider, currency path, origin, destination)``.

    FR-023 says an entry is per ``(provider x currency path x venue)`` and **not** per
    provider. The currency path is the sequence of currencies the money is actually in --
    the first leg's ``from_ccy`` followed by every leg's ``to_ccy`` -- so two routes that
    differ only in how many times they cross a currency have different identities. That is
    the point of the rule: conversion count is usually the largest difference between two
    ways of doing the same thing, and collapsing the two into one entry would hide the
    expensive one.

    "Venue" is read as the pair of endpoints. One venue would not distinguish a corridor
    from where it starts, and the endpoints are what a funding path names.
    """
    currencies = (route.legs[0].from_ccy.value, *(leg.to_ccy.value for leg in route.legs))
    return route.provider, currencies, route.origin, route.destination


def _refuse_identity_collision(route: Route, already: Path, now: Path) -> DeclarationError:
    """The duplicate-triple error (FR-023), naming both files and the triple they share."""
    provider, currencies, origin, destination = _identity(route)
    return DeclarationError(
        now,
        "route.provider",
        f"declares the same registry identity as {already}: provider {provider!r} carrying "
        f"{' -> '.join(currencies)} from {origin!r} to {destination!r}. A route registry "
        "entry is per (provider x currency path x venue), so two entries sharing all three "
        "are two descriptions of one corridor and at most one of them can be right -- and "
        "whichever loaded second would win by accident of directory ordering.",
        "delete the duplicate, or state what actually differs: a different provider, a "
        "different number of conversions, or different endpoints",
    )


def _check_kind(
    named: str,
    kinds: Mapping[str, ObservationKind],
    *,
    path: Path,
    field_path: str,
) -> None:
    """Every observed value ages under a **declared** threshold (FR-028).

    No permissive default, and no silent pass for a kind nobody declared: a value whose
    threshold does not exist could never be reported stale, which is the failure mode
    FR-028 exists to close -- a stale route cost invalidates every comparison built on it,
    silently.
    """
    if named not in kinds:
        raise DeclarationError(
            path,
            field_path,
            f"names the observation kind {named!r}, which {KINDS_FILE} does not declare. "
            "There is no default staleness threshold: a value ageing under a threshold "
            "nobody set could never be reported stale, and a stale route cost invalidates "
            f"every comparison built on it. Declared kinds: {sorted(kinds)}.",
            f"declare {named!r} in data/{KINDS_FILE} with its staleness_days and a note, or "
            "name one that exists",
        )


def _check_venue(
    named: str,
    currency: Currency,
    venues: Mapping[str, Venue],
    *,
    path: Path,
    field_path: str,
) -> None:
    """A venue a leg names must exist **and** be able to hold the currency moved through it.

    Both halves, and the second is the one ``Venue.currencies`` exists for: a leg moving
    dollars into a hryvnia-only card account is a declaration nobody can satisfy, and
    inferring the venue's capabilities from its legs would make the mistake
    self-justifying -- the leg declaring the impossible movement would be the evidence that
    it was possible.
    """
    venue = venues.get(named)
    if venue is None:
        raise DeclarationError(
            path,
            field_path,
            f"names the venue {named!r}, which {VENUES_FILE} does not declare. A venue is a "
            "named place with stated capabilities rather than a free string, so a typo is a "
            f"load-time failure instead of an endpoint nothing ever matches. Declared "
            f"venues: {sorted(venues)}.",
            f"declare {named!r} in data/{VENUES_FILE}, or name a venue that exists",
        )
    if not can_hold(venue, currency):
        raise DeclarationError(
            path,
            field_path,
            f"moves {currency.value} through venue {named!r}, which declares that it holds "
            f"{sorted(held.value for held in venue.currencies)}. The movement is refused "
            "rather than assumed possible: money cannot sit in an account that does not "
            "hold its currency, and the arriving amount would be a figure describing a "
            "balance that cannot exist.",
            f"add {currency.value} to that venue's currencies if the account really holds "
            "it, or route the movement through a venue that does",
        )


def _check_channel(
    leg: Leg,
    channels: Mapping[str, FxChannel],
    *,
    path: Path,
) -> None:
    """An ``fx`` leg's channel must exist and must quote the pair the leg converts.

    A channel quotes **one ordered pair**, and applying it to another would be inventing a
    rate -- which no amount of convenience justifies (FR-010). Checked here rather than left
    to ``channels.side_for``'s raise, because here the message can name the file and the leg
    index; reaching that raise means this check was bypassed.
    """
    if leg.channel is None:
        return
    field_path = f"route.leg[{leg.index}].channel"
    channel = channels.get(leg.channel)
    if channel is None:
        raise DeclarationError(
            path,
            field_path,
            f"names the channel {leg.channel!r}, which no file in data/{CHANNELS_DIR} "
            "declares. There is no default channel: substituting 'the official rate' for a "
            "misspelt id would reprice the leg at a rate nobody declared and delete the "
            f"entire spread this feature exists to measure. Declared channels: "
            f"{sorted(channels)}.",
            f"declare {leg.channel!r} in data/{CHANNELS_DIR}, or name a channel that exists",
        )
    price_currency, unit_currency = channel.pair
    quoted = {(price_currency, unit_currency), (unit_currency, price_currency)}
    if (leg.from_ccy, leg.to_ccy) not in quoted:
        raise DeclarationError(
            path,
            field_path,
            f"converts {leg.from_ccy.value} -> {leg.to_ccy.value} through channel "
            f"{channel.id!r}, which quotes {price_currency.value} per {unit_currency.value}. "
            "No rate is inferred for any other pair: a channel is a two-sided quote for one "
            "ordered pair, and using it for another would be inventing the number that does "
            "the converting.",
            "name a channel that quotes this pair, or correct the leg's currencies",
        )


def _check_chain(route: Route, *, path: Path) -> None:
    """Leg *n* must end where leg *n+1* begins, and the chain must span the route (D6).

    Continuity is a structural property of the declaration, knowable with no amount and no
    date, so it is checked where the error can name the file and the leg index. Deferring it
    to cost time would mean the same broken route produced an error per call site rather
    than one message naming the file -- and the core, which may then assume a chained route,
    raises instead of returning a typed failure, because by then the caller is the problem.
    """
    first = route.legs[0]
    last = route.legs[-1]
    if first.from_venue != route.origin:
        raise DeclarationError(
            path,
            "route.leg[0].from_venue",
            f"starts at {first.from_venue!r} while the route declares its origin as "
            f"{route.origin!r}. Neither is preferred: the origin is what a stream's arrival "
            "venue is checked against, and the first leg is where the money actually starts, "
            "so a disagreement means one of the two is wrong about where the journey begins.",
            f"make the first leg start at {route.origin!r}, or correct the route's origin",
        )
    if last.to_venue != route.destination:
        raise DeclarationError(
            path,
            f"route.leg[{last.index}].to_venue",
            f"ends at {last.to_venue!r} while the route declares its destination as "
            f"{route.destination!r}. The destination is what a funding path names, so a "
            "disagreement means the cost of reaching one place would be reported as the cost "
            "of reaching another.",
            f"make the last leg end at {route.destination!r}, or correct the route's destination",
        )
    for position in range(1, len(route.legs)):
        earlier = route.legs[position - 1]
        later = route.legs[position]
        if earlier.to_venue != later.from_venue:
            raise DeclarationError(
                path,
                f"route.leg[{later.index}].from_venue",
                f"starts at {later.from_venue!r}, but leg {earlier.index} ends at "
                f"{earlier.to_venue!r}. The chain is broken: money would have to appear at a "
                "venue nothing moved it to, and every leg after the gap would be costing an "
                "amount that never arrived.",
                f"start this leg at {earlier.to_venue!r}, or add the leg that moves the money",
            )
        if earlier.to_ccy is not later.from_ccy:
            raise DeclarationError(
                path,
                f"route.leg[{later.index}].from_ccy",
                f"takes in {later.from_ccy.value}, but leg {earlier.index} hands out "
                f"{earlier.to_ccy.value}. The only way to satisfy that is a conversion "
                "nobody declared, at a rate nobody chose -- which is exactly the implicit "
                "mid-rate FR-010 forbids.",
                f"declare an fx leg between the two, or make this leg take in "
                f"{earlier.to_ccy.value}",
            )


def _check_partner(
    route: Route,
    routes: Mapping[str, Route],
    files: Mapping[str, Path],
    *,
    base_currency: Currency,
) -> None:
    """The five things a declared exit route must be (FR-027), each refused by name.

    ``partner_route`` absent is **legal and expected**: it means nobody has costed the way
    out, and it produces ``ExitCostUnknown`` rather than a reversal or a promoted one-way
    figure (FR-030). What is refused is a partner that *looks* declared and is not usable:

    * **A dangling id.** ``cost._round_trip`` raises on it, blaming the loader -- correctly,
      since the whole reason the absence is expressible is that a typo must not become it.
    * **A partner whose direction is not ``exit``.** An inbound route is not an exit; pairing
      two ways *in* would produce a round trip that never comes back.
    * **A partner that does not start where this route ends.** This is the sharpest of the
      five: a pair that does not meet would load and produce a *confident round-trip figure
      for two unrelated journeys*, which is the exact class of number FR-030 exists to
      refuse.
    * **A partner whose first leg does not take in the currency this route delivers.** The
      seam is a currency as well as a venue: a pair meeting at the venue but not in the
      currency could only be walked through a conversion nobody declared, at a rate nobody
      chose -- the implicit mid-rate FR-010 forbids -- and without this check it loads and
      then dies mid-costing as a raw currency mismatch naming neither file.
    * **A partner that does not end holding the base currency.** §4.3.3 asks for money back
      in **spendable** base currency; an exit that stops in dollars at an exchange has not
      got the money out, and an asset that cannot be liquidated into spendable base currency
      is not worth its stated value (Principle VI).
    """
    if route.partner_route is None:
        return
    path = files[route.id]
    field_path = "route.partner_route"
    partner = routes.get(route.partner_route)
    if partner is None:
        raise DeclarationError(
            path,
            field_path,
            f"names the exit route {route.partner_route!r}, which no file in "
            f"data/{ROUTES_DIR} declares. A dangling partner is refused here precisely so it "
            "cannot become a missing round trip later: omitting the key is how a route says "
            "nobody has costed the exit, and a typo must not be read as that statement. "
            f"Declared routes: {sorted(routes)}.",
            f"declare {route.partner_route!r}, or delete the partner_route to state that the "
            "way out has not been costed",
        )
    if partner.direction != "exit":
        raise DeclarationError(
            path,
            field_path,
            f"names {partner.id!r} as its exit route, but that route declares direction "
            f"{partner.direction!r}. An inbound route is not an exit (FR-027): pairing two "
            "ways in would produce a round-trip figure for a journey that never comes back.",
            f"declare {partner.id!r} with direction = 'exit', or name the route that does",
        )
    if partner.origin != route.destination:
        raise DeclarationError(
            path,
            field_path,
            f"names {partner.id!r} as its exit route, but that route starts at "
            f"{partner.origin!r} while this one ends at {route.destination!r}. The two do "
            "not meet, so the round trip would be two unrelated journeys reported as one "
            "figure -- a confident number for a path nobody can walk, which is the class of "
            "figure FR-030 exists to refuse.",
            f"declare an exit route starting at {route.destination!r}, or correct one of the "
            "two endpoints",
        )
    arrives_in = route.legs[-1].to_ccy
    starts_in = partner.legs[0].from_ccy
    if starts_in is not arrives_in:
        raise DeclarationError(
            path,
            field_path,
            f"names {partner.id!r} as its exit route, but leg 0 of that route (declared in "
            f"{files[partner.id]}) takes in {starts_in.value} while this route delivers "
            f"{arrives_in.value} at {route.destination!r}. The seam is a currency as well as "
            "a venue: the only way to walk this pair would be a conversion nobody declared, "
            "at a rate nobody chose -- exactly the implicit mid-rate FR-010 forbids -- and "
            "costing it would otherwise fail mid-walk as a currency mismatch naming neither "
            "file.",
            f"make the exit route's first leg take in {arrives_in.value} (an fx leg with a "
            "declared channel, where the conversion really happens), or pair this route "
            "with an exit that starts in it",
        )
    ends_in = partner.legs[-1].to_ccy
    if ends_in is not base_currency:
        raise DeclarationError(
            path,
            field_path,
            f"names {partner.id!r} as its exit route, but that route ends holding "
            f"{ends_in.value} rather than the base currency {base_currency.value}. Getting "
            "money back into *spendable* base currency is what a round trip measures "
            "(§4.3.3): an exit that stops in another currency at an exchange has not got the "
            f"money out, and reporting it as a round trip would value the asset as though it "
            f"had. Here, {BASE_CURRENCY_ROLE}",
            f"extend the exit route until it delivers {base_currency.value}, or pair this "
            "route with the exit that does",
        )


def _check_pools(
    routes: Mapping[str, Route],
    files: Mapping[str, Path],
) -> None:
    """Two legs naming one rail must declare one cap (research.md D10).

    Across files, which is the case that matters: the whole point of a pool is that two
    *different routes* through the owner's Monobank card consume one limit. Two numbers for
    one real limit means at least one of them is wrong, and picking either silently would be
    a guess -- so the error names both files and both legs.

    **One currency, checked before the amounts.** A pool whose caps disagree about the
    currency is a sharper defect than one whose caps disagree about the number: nothing can
    accumulate consumption across two currencies without inventing a rate, and the amount
    comparison itself would raise a currency mismatch naming neither file. So the currency
    rule is its own refusal, first.

    ``core.routes.capacity.caps_of`` refuses the same disagreement within one route and
    raises, because reaching it means this check was bypassed.
    """
    declared: dict[str, tuple[str, int, Money]] = {}
    for route_id in sorted(routes):
        route = routes[route_id]
        for leg in route.legs:
            if leg.capacity_pool is None or leg.monthly_cap is None:
                continue
            seen = declared.get(leg.capacity_pool)
            if seen is None:
                declared[leg.capacity_pool] = (route_id, leg.index, leg.monthly_cap)
                continue
            first_route, first_index, first_cap = seen
            if first_cap.currency is not leg.monthly_cap.currency:
                raise DeclarationError(
                    files[route_id],
                    f"route.leg[{leg.index}].monthly_cap",
                    f"declares its cap on capacity pool {leg.capacity_pool!r} in "
                    f"{leg.monthly_cap.currency.value}, while leg {first_index} of route "
                    f"{first_route!r} in {files[first_route]} declares the same pool's cap "
                    f"in {first_cap.currency.value}. One rail has one limit in one "
                    "currency: consumption cannot accumulate across two currencies without "
                    "inventing a rate, and even comparing the two caps would raise a "
                    "currency mismatch naming neither file.",
                    "declare every leg naming this pool with its cap in one currency, or "
                    "give the legs different pools if they really consume different limits",
                )
            if money.compare(first_cap, leg.monthly_cap) != 0:
                raise DeclarationError(
                    files[route_id],
                    f"route.leg[{leg.index}].monthly_cap",
                    f"declares {leg.monthly_cap.amount!r} "
                    f"{leg.monthly_cap.currency.value} on capacity pool "
                    f"{leg.capacity_pool!r}, while leg {first_index} of route "
                    f"{first_route!r} in {files[first_route]} declares "
                    f"{first_cap.amount!r} {first_cap.currency.value} on the same pool. A "
                    "monthly limit belongs to the rail, not to the route, so two numbers for "
                    "one real limit means at least one of them is wrong -- and choosing "
                    "either would be a guess.",
                    "make the two declarations agree, or give the two legs different pools "
                    "if they really consume different limits",
                )


def _check_regimes(
    scenario: ScenarioDeclaration,
    routes: Mapping[str, Route],
    *,
    path: Path,
) -> None:
    """A regime selects from the declared routes, and it must select a **closed** set.

    Two checks, both of which the core also refuses -- by raising, because by then the
    scenario has already been handed to a comparison:

    * **Every ``route_ids`` member resolves.** A regime does not declare routes of its own;
      it states which of the declared ones it believes in, so a name that resolves to
      nothing is a belief about a corridor that does not exist.
    * **Partner closure.** Including an inbound route while excluding the exit route it
      names would make money one-way, and costing it would raise on a dangling partner and
      blame the loader for a scenario's belief. "There is a way in and none out" is a
      *route* declaring no ``partner_route`` -- a fact about the corridor, with a source --
      so a regime with only one direction of a corridor is expressed as a separately
      declared pair rather than as half of this one (FR-027).
    """
    for regime in scenario.regimes:
        field_path = f"scenario.regime[{regime.id}].route_ids"
        missing = sorted(regime.route_ids - set(routes))
        if missing:
            raise DeclarationError(
                path,
                field_path,
                f"names route(s) {missing}, which no file in data/{ROUTES_DIR} declares. A "
                "regime selects from the declared routes; it does not declare any of its "
                f"own, so a name that resolves to nothing is a belief about a corridor that "
                f"does not exist. Declared routes: {sorted(routes)}.",
                "name only declared routes, or declare the missing ones",
            )
        orphaned = sorted(
            f"{route_id} -> {routes[route_id].partner_route}"
            for route_id in regime.route_ids
            if routes[route_id].partner_route is not None
            and routes[route_id].partner_route not in regime.route_ids
        )
        if orphaned:
            raise DeclarationError(
                path,
                field_path,
                f"includes route(s) whose declared exit route it excludes: {orphaned}. "
                "Costing one would raise on the dangling partner and blame the loader for a "
                "belief. A regime cannot make money one-way: 'there is a way in and none "
                "out' is a route declaring no partner_route, which is a fact about the "
                "corridor with a source, so a regime holding one direction of a corridor is "
                "expressed as a separately declared pair instead.",
                "include the exit route as well, or exclude both halves of the pair",
            )


def _resolved_kinds(path: Path) -> tuple[dict[str, ObservationKind], dict[str, Path]]:
    """Declared observation kinds by id, refusing a duplicate.

    One helper per family of declaration, and the split is not cosmetic: :func:`resolve_ramp`
    is the *order* the families are resolved in, and a reader checking that order should not
    have to read six duplicate-detection loops to find it.
    """
    kinds: dict[str, ObservationKind] = {}
    files: dict[str, Path] = {}
    for declared in loader.observation_kinds_from_file(path):
        if declared.id in kinds:
            raise _refuse_duplicate(
                "observation kind", declared.id, f"kind[{declared.id}].id", files[declared.id], path
            )
        kinds[declared.id] = declared
        files[declared.id] = path
    return kinds, files


def _resolved_venues(path: Path) -> tuple[dict[str, Venue], dict[str, Path]]:
    """Declared venues by id, refusing a duplicate."""
    venues: dict[str, Venue] = {}
    files: dict[str, Path] = {}
    for venue in loader.venues_from_file(path):
        if venue.id in venues:
            raise _refuse_duplicate(
                "venue", venue.id, f"venue[{venue.id}].id", files[venue.id], path
            )
        venues[venue.id] = venue
        files[venue.id] = path
    return venues, files


def _resolved_channels(
    paths: Sequence[Path], kinds: Mapping[str, ObservationKind]
) -> tuple[dict[str, FxChannel], dict[str, Path]]:
    """Declared channels by id, with every kind resolved and every duplicate refused."""
    channels: dict[str, FxChannel] = {}
    files: dict[str, Path] = {}
    for path in paths:
        for channel in loader.channels_from_file(path):
            if channel.id in channels:
                raise _refuse_duplicate(
                    "channel",
                    channel.id,
                    f"channel[{channel.id}].id",
                    files[channel.id],
                    path,
                )
            _check_kind(channel.kind, kinds, path=path, field_path=f"channel[{channel.id}].kind")
            for side_name, side in (
                ("buy_side", channel.buy_side),
                ("sell_side", channel.sell_side),
            ):
                _check_kind(
                    side.kind,
                    kinds,
                    path=path,
                    field_path=f"channel[{channel.id}].{side_name}.kind",
                )
            channels[channel.id] = channel
            files[channel.id] = path
    return channels, files


def _resolved_routes(
    paths: Sequence[Path],
    *,
    venues: Mapping[str, Venue],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    base_currency: Currency,
) -> tuple[dict[str, Route], dict[str, Path]]:
    """Declared routes by id, with every relation checked (FR-023, FR-024, FR-027, FR-015).

    Three passes, in this order, because each needs the one before it: per-route references
    and continuity while the file is in hand; then ``partner_route``, which needs every route
    parsed; then ``capacity_pool`` agreement, which needs every leg of every route.
    """
    routes: dict[str, Route] = {}
    files: dict[str, Path] = {}
    identities: dict[tuple[str, tuple[str, ...], str, str], Path] = {}
    for path in paths:
        route = loader.route_from_file(path)
        if route.id in routes:
            raise _refuse_duplicate("route", route.id, "route.id", files[route.id], path)
        identity = _identity(route)
        if identity in identities:
            raise _refuse_identity_collision(route, identities[identity], path)
        _check_route(route, venues=venues, channels=channels, kinds=kinds, path=path)
        routes[route.id] = route
        files[route.id] = path
        identities[identity] = path

    for route in routes.values():
        _check_partner(route, routes, files, base_currency=base_currency)
    _check_pools(routes, files)
    return routes, files


def _resolved_streams(
    paths: Sequence[Path], venues: Mapping[str, Venue]
) -> tuple[dict[str, IncomeStream], dict[str, Path]]:
    """Declared income streams by id, each naming venues that can hold the stream's currency.

    **Both venues are checked and neither is derived from the other** (012 FR-024a). They
    answer different questions -- where a funding route starts, and where the income is
    credited for tax -- and for the owner's contract income they hold different values.
    """
    streams: dict[str, IncomeStream] = {}
    files: dict[str, Path] = {}
    for path in paths:
        for stream in loader.streams_from_file(path):
            if stream.id in streams:
                raise _refuse_duplicate(
                    "income stream",
                    stream.id,
                    f"stream[{stream.id}].id",
                    files[stream.id],
                    path,
                )
            _check_venue(
                stream.arrives_at,
                stream.amount.currency,
                venues,
                path=path,
                field_path=f"stream[{stream.id}].arrives_at",
            )
            _check_venue(
                stream.credited_to,
                stream.amount.currency,
                venues,
                path=path,
                field_path=f"stream[{stream.id}].credited_to",
            )
            streams[stream.id] = stream
            files[stream.id] = path
    return streams, files


def _resolved_scenarios(
    paths: Sequence[Path], routes: Mapping[str, Route]
) -> tuple[dict[str, ScenarioDeclaration], dict[str, Path]]:
    """Declared scenarios by id, each naming only declared routes and partner-closed."""
    scenarios: dict[str, ScenarioDeclaration] = {}
    files: dict[str, Path] = {}
    for path in paths:
        scenario = loader.scenario_from_file(path)
        if scenario.id in scenarios:
            raise _refuse_duplicate(
                "scenario", scenario.id, "scenario.id", files[scenario.id], path
            )
        _check_regimes(scenario, routes, path=path)
        scenarios[scenario.id] = scenario
        files[scenario.id] = path
    return scenarios, files


def resolve_ramp(
    *,
    kinds_file: Path,
    venues_file: Path,
    channel_files: Sequence[Path],
    route_files: Sequence[Path],
    stream_files: Sequence[Path],
    scenario_files: Sequence[Path],
    base_currency: Currency,
) -> RampDeclarations:
    """Parse every ramp declaration, then check what only the whole set can show.

    The order is the design, exactly as it is for :func:`resolve`: **every file is parsed
    individually first, then the relations are checked.** A resolver that loaded lazily could
    not report a duplicate at all, since it would never hold both declarations at once -- and
    it could not check a chain against the venues, or a partner against the routes, because
    the file naming them would have been read before the file declaring them.

    Within that, kinds and venues come first because everything else refers to them, then
    channels, then routes (which refer to all three), then streams, then scenarios (which
    refer to routes). Files are read in the order given and the caller is expected to have
    sorted them (:func:`ramp_from_data_root` does), so a duplicate is always reported against
    the same one of the two files rather than depending on filesystem order.

    ``base_currency`` is required and keyword-only, and there is nothing here to guess it
    from. It is what the exit routes are checked against: ``base_currency`` is the currency
    the owner earns and spends, the ledger's home currency (Principle VI), and it is passed in
    rather than read off the tax pack's ``base_currency`` because the *tax* role of currency is
    a different role from the *base* role -- conflating two of the three is itself a defect,
    and a data layer that quietly took one for the other would be the place it happened.
    """
    kinds, kind_files = _resolved_kinds(kinds_file)
    venues, venue_files = _resolved_venues(venues_file)
    channels, channel_files_by_id = _resolved_channels(channel_files, kinds)
    routes, route_files_by_id = _resolved_routes(
        route_files,
        venues=venues,
        channels=channels,
        kinds=kinds,
        base_currency=base_currency,
    )
    streams, stream_files_by_id = _resolved_streams(stream_files, venues)
    scenarios, scenario_files_by_id = _resolved_scenarios(scenario_files, routes)
    return RampDeclarations(
        kinds=kinds,
        venues=venues,
        channels=channels,
        routes=routes,
        streams=streams,
        scenarios=scenarios,
        base_currency=base_currency,
        kind_files=kind_files,
        venue_files=venue_files,
        channel_files=channel_files_by_id,
        route_files=route_files_by_id,
        stream_files=stream_files_by_id,
        scenario_files=scenario_files_by_id,
    )


def _check_route(
    route: Route,
    *,
    venues: Mapping[str, Venue],
    channels: Mapping[str, FxChannel],
    kinds: Mapping[str, ObservationKind],
    path: Path,
) -> None:
    """Everything about one route that needs the other files: references, then continuity.

    References first and the chain second, deliberately. A leg naming a venue that does not
    exist would otherwise be reported as a broken chain -- true, and not the reason -- and
    the owner would go looking for a missing leg instead of a misspelt id.
    """
    for leg in route.legs:
        _check_kind(
            leg.kind_of_observation,
            kinds,
            path=path,
            field_path=f"route.leg[{leg.index}].kind_of_observation",
        )
        _check_venue(
            leg.from_venue,
            leg.from_ccy,
            venues,
            path=path,
            field_path=f"route.leg[{leg.index}].from_venue",
        )
        _check_venue(
            leg.to_venue,
            leg.to_ccy,
            venues,
            path=path,
            field_path=f"route.leg[{leg.index}].to_venue",
        )
        _check_channel(leg, channels, path=path)
    _check_venue(
        route.origin,
        route.legs[0].from_ccy,
        venues,
        path=path,
        field_path="route.origin",
    )
    _check_venue(
        route.destination,
        route.legs[-1].to_ccy,
        venues,
        path=path,
        field_path="route.destination",
    )
    _check_chain(route, path=path)


def ramp_from_data_root(root: Path, *, base_currency: Currency) -> RampDeclarations:
    """Every ramp declaration under a data root, resolved together.

    ``observation_kinds.toml`` and ``venues.toml`` at the root, then ``channels/*.toml``,
    ``routes/*.toml``, ``streams/*.toml`` and ``scenarios/*.toml``. Sorted, so a run is
    reproducible: an unsorted directory listing would make the order of two files -- and
    therefore which one a duplicate-id error names -- depend on the filesystem.

    Only the top level of each directory is read, on the precedent
    ``instruments/nav/`` set: a subdirectory holds a different shape of file, and globbing
    recursively would try to validate it as a declaration and report a confusing failure
    about a file that is perfectly correct.

    An empty directory is an **error**, not an empty world. Silently returning no routes
    would make a mistyped path indistinguishable from a repository with no data, and every
    downstream reference would then fail for a reason that names the wrong thing.

    ``base_currency`` is required and keyword-only, for the reason
    :func:`resolve_ramp` gives.
    """
    channels = sorted((root / CHANNELS_DIR).glob("*.toml"))
    routes = sorted((root / ROUTES_DIR).glob("*.toml"))
    streams = sorted((root / STREAMS_DIR).glob("*.toml"))
    scenarios = sorted((root / SCENARIOS_DIR).glob("*.toml"))
    for directory, found in (
        (CHANNELS_DIR, channels),
        (ROUTES_DIR, routes),
        (STREAMS_DIR, streams),
        (SCENARIOS_DIR, scenarios),
    ):
        if not found:
            raise DeclarationError(
                root / directory,
                "",
                f"contains no *.toml declarations. An empty {directory} directory is "
                "reported rather than read as 'nothing is declared': the two are "
                "indistinguishable to everything downstream, and one of them is a "
                "mistyped path.",
                "check the data root, or add a declaration file",
            )
    return resolve_ramp(
        kinds_file=root / KINDS_FILE,
        venues_file=root / VENUES_FILE,
        channel_files=channels,
        route_files=routes,
        stream_files=streams,
        scenario_files=scenarios,
        base_currency=base_currency,
    )


# ---------------------------------------------------------------------------
# 003-route-coverage: the coverage report's cross-file pass
# ---------------------------------------------------------------------------
#
# One new declaration and four relations, each of which needs a file the spendable list has
# never opened:
#
# 1. **The venue exists**, on the loader's existing `_known` path -- a spendable endpoint at a
#    venue nobody declared cannot be checked against anything.
# 2. **The venue can hold the currency.** `Venue.currencies` already exists for this class of
#    contradiction and `_check_venue` already owns it for legs; a place that cannot hold
#    hryvnia is not a place the owner spends hryvnia from.
# 3. **The currency is the run's base currency** (FR-004). Accepting a foreign one would make
#    the report decide that foreign cash counts as spent.
# 4. **The owner owns the streams** the list is resolved with. Where a person spends is a fact
#    about *that* person, and one owner's spendable venues deciding another's verdicts would
#    put two people's facts in one report (Principle VII).

SPENDABLE_DIR = "spendable"
"""Where the per-owner spendable-endpoint list lives under a data root.

**Per-owner, beside `streams/`, not at the root beside curated `venues.toml`** -- the same
Principle VII boundary, made structural (research.md D3). A corridor is a public fact about the
world; where this person spends is not.
"""


@dataclass(frozen=True, slots=True)
class CoverageDeclarations:
    """Every declaration a coverage report needs: the ramp's, plus the spendable list.

    ⚙ **A record beside :class:`RampDeclarations` rather than more fields on it**, on the
    precedent `RampDeclarations` itself sets against :class:`Declarations`. The two describe
    different runs: a data root with no spendable file must still be able to cost a ramp, and
    folding the list into the ramp record would make every existing caller require a file this
    feature invented.
    """

    ramp: RampDeclarations
    """The venues, streams, routes, channels, kinds and scenarios the report audits -- the same
    registry a ramp comparison costs, which is what makes FR-018's agreement checkable at all
    rather than a claim about two different worlds."""

    spendable: frozenset[SpendableEndpoint]
    """Where money counts as having come back out (FR-004). A ``frozenset`` because membership
    is the whole question and order means nothing; the report sorts it where it reports it."""

    spendable_file: Path
    """Which file declared the list. Not decoration: it is what lets a later failure still name
    the file after the TOML has been discarded."""

    scenario_id: str | None
    """Which declared scenario's belief this set was resolved for, or ``None`` for FR-015's
    single implicit regime. Carried beside the regimes it produced so a reader can see *whose*
    belief the audit ran under -- a report is only reproducible if the world it assumed is
    recorded, and "every route at once" is itself an assumption worth naming."""

    regimes: Mapping[str, Regime]
    """The named scenario's regimes, keyed by id -- the ``regimes`` argument of ``coverage``.

    Empty when :attr:`scenario_id` is ``None``, which is what the audit reads as FR-015's
    implicit regime. **Exactly one scenario's regimes**, never a merge of two: see
    :func:`_regimes_of_scenario`.
    """


def _check_spendable(
    endpoint: SpendableEndpoint,
    *,
    position: int,
    venues: Mapping[str, Venue],
    base_currency: Currency,
    path: Path,
) -> None:
    """One spendable endpoint against the venues and the base currency (FR-004).

    The venue check is ``_check_venue``'s, unchanged, so "this venue cannot hold that currency"
    is asked in the same words wherever it is asked. The base-currency check is separate and is
    this feature's own: FR-004 says base currency only, and it is refused rather than converted,
    because the alternative -- accepting dollars at an exchange as somewhere money has "come
    back out" -- is the report quietly deciding that foreign cash counts as spent, which is the
    single most flattering possible error it could make about the registry.
    """
    field_path = f"{loader.SPENDABLE_TABLE}[{position}].venue"
    _check_venue(endpoint.venue_id, endpoint.currency, venues, path=path, field_path=field_path)
    if endpoint.currency is not base_currency:
        raise DeclarationError(
            path,
            f"{loader.SPENDABLE_TABLE}[{position}].currency",
            f"declares {endpoint.currency.value} as spendable at venue "
            f"{endpoint.venue_id!r}, but this run's base currency is {base_currency.value}. A "
            "spendable endpoint is where money counts as having come **back out**, and money "
            "sitting in a foreign currency has not come out -- an asset that cannot be "
            "liquidated into spendable base currency is not worth its stated value (Principle "
            f"VI). Here, {BASE_CURRENCY_ROLE}",
            f"declare the endpoint in {base_currency.value}, or delete it: a venue holding "
            "foreign cash is a destination in this report, not a place to spend from",
        )


def _check_spendable_owner(
    owner_id: str,
    streams: Mapping[str, IncomeStream],
    *,
    path: Path,
    stream_files: Mapping[str, Path],
) -> None:
    """The list must belong to the owner whose streams it is resolved with (Principle VII).

    Checked against the *streams* rather than against a configured owner id, because the streams
    are the other per-owner declaration in the run and the report pairs the two on every line:
    every verdict is a `(destination x stream)`, and the spendable list is what decides half of
    it. A list belonging to somebody else would answer this owner's question with that owner's
    life.

    ⚙ **The run must hold exactly one owner's streams, not merely include his** (correction,
    2026-08-23). Asking only ``owner_id in owners`` was the leak: ``ramp_from_data_root`` globs
    every ``streams/*.toml``, so a second owner's file loads beside the first, his streams are
    paired with *this* owner's spendable list, and his destinations come out marked ready on
    somebody else's definition of where money can be spent. That is exactly what
    :func:`coverage_from_data_root` refuses in as many words on the spendable side -- "merging
    two lists would let one owner's spendable venues decide the other's verdicts" -- and a guard
    whose stated claim is false is worse than no guard.

    **Refused here rather than in `ramp_from_data_root`, and against the foreign stream file.**
    A ramp comparison costs one named `(destination x stream x route)` at a time and blends
    nothing across owners, so multi-owner streams are not a defect there; a coverage run folds
    over *every* stream at once, which is what makes the second owner's presence a wrong answer
    rather than an unused file. The offending declaration is the stream file that does not
    belong in this run -- the spendable list is correct about itself -- so that is the file the
    error names, with both owner ids and every foreign stream in the message.
    """
    owners = sorted({stream.owner_id for stream in streams.values()})
    if owner_id not in owners:
        raise DeclarationError(
            path,
            f"{loader.OWNER_TABLE}.id",
            f"declares owner {owner_id!r}, but the income streams this list is resolved with "
            f"belong to {owners}. The spendable list decides half of every verdict in the "
            "coverage report -- where money counts as having come back out -- so a list "
            "belonging to somebody else would answer this owner's question with another "
            "person's life.",
            f"name one of {owners}, or resolve this list against that owner's streams",
        )
    foreign = sorted(
        (stream.owner_id, stream.id) for stream in streams.values() if stream.owner_id != owner_id
    )
    if foreign:
        first_owner, first_stream = foreign[0]
        raise DeclarationError(
            stream_files[first_stream],
            "stream.owner_id",
            f"declares stream {first_stream!r} for owner {first_owner!r}, and this coverage run "
            f"resolves the spendable list of owner {owner_id!r}. The streams loaded together "
            f"belong to {owners}, and the foreign ones are "
            f"{[f'{stream} ({owner})' for owner, stream in foreign]}. A coverage report folds "
            "over every stream at once against one spendable list, so a second owner's streams "
            "would have their verdicts decided by this owner's spendable venues -- the same "
            "blend the second-spendable-file refusal says cannot happen, arriving through the "
            "streams instead.",
            f"resolve one owner's registry at a time: keep only owner {owner_id!r}'s streams in "
            "this data root, or resolve this run against the matching spendable list",
        )


def _regimes_of_scenario(
    scenario_id: str | None,
    scenarios: Mapping[str, ScenarioDeclaration],
    *,
    scenario_files: Mapping[str, Path],
) -> Mapping[str, Regime]:
    """One named scenario's regimes, keyed by id -- or none at all, said out loud.

    ⚙ **The audit is scoped to one scenario, and two scenarios are never blended**
    (research.md D17, owner decision 2026-08-23). A scenario is the unit of belief: it declares
    its regimes *and* the transition between them, so its regimes are alternatives to each
    other. Two scenarios are alternatives to *one another*, and pooling their regimes into one
    ``regimes`` mapping would produce a report about a world nobody declared -- four blocks
    where the owner holds two beliefs of two regimes each, each block honestly labelled and the
    set of them meaningless. There is therefore no way to ask for two, and no merge to get
    wrong.

    **An unknown ``scenario_id`` is refused, never quietly read as "no regime declared".** The
    fallback would audit every declared route under the implicit regime and say so in the
    ``source`` field, which is the flattering reading of a typo: a full-coverage-looking report
    over a route set no belief in the registry supports. The refusal names the files that were
    read and lists what they declare, so the caller can correct the name from the message.

    ``None`` is FR-015's implicit regime and returns an empty mapping, which is what
    ``coverage`` reads as "audit every declared route under one implicit regime".

    Duplicate regime ids **within** a scenario are already refused by the loader
    (``loader._regimes``), which is why keying by id here cannot silently drop one.
    """
    if scenario_id is None:
        return {}
    if scenario_id not in scenarios:
        declared = sorted(scenarios)
        files = sorted({path.name for path in scenario_files.values()})
        # The directory rather than a file: no file declares the name that was asked for, so
        # there is nothing more specific to point at. With no scenario file at all there is not
        # even a directory to name, and the constant is what the message can honestly give.
        where = (
            sorted({path.parent for path in scenario_files.values()})[0]
            if scenario_files
            else Path(SCENARIOS_DIR)
        )
        raise DeclarationError(
            where,
            "",
            f"was asked to audit coverage under scenario {scenario_id!r}, which is declared by "
            f"none of the {len(files)} scenario file(s) read here ({', '.join(files) or 'none'})."
            f" Declared scenario ids: {declared}. The audit runs against one scenario's regimes "
            "-- a scenario is the unit of belief, and its regimes are alternatives to each "
            "other -- so an unrecognised name is refused rather than read as 'no regime "
            "declared': that fallback would audit every declared route under a belief nobody "
            "stated and report it as coverage.",
            f"name one of {declared}, or pass scenario_id=None to audit every declared route "
            "under the single implicit regime (FR-015)",
        )
    return {regime.id: regime for regime in scenarios[scenario_id].regimes}


def resolve_coverage(
    *,
    ramp: RampDeclarations,
    spendable_file: Path,
    scenario_id: str | None,
) -> CoverageDeclarations:
    """The ramp declarations plus a resolved spendable list, checked against them.

    Takes the resolved :class:`RampDeclarations` rather than the paths that produced them: the
    spendable list is checked against the *venues*, the *base currency* and the *streams*, all
    three of which are already resolved by then, and re-resolving them here would give a data
    root two chances to disagree with itself.

    ⚙ **``scenario_id`` is required and nullable, rather than defaulted to ``None``.** The two
    would behave identically until the day somebody forgets the argument, and then they differ
    by exactly the thing this feature exists to prevent: a report that audits every declared
    route under an implicit regime, while the registry declares regimes that believe in a
    subset of them, is confident about a world nobody stated. FR-015's implicit regime is a
    legitimate answer to *"audit everything"* and an illegitimate one to *"audit my scenario"*,
    and only the caller knows which was asked. Making it required forces that sentence to be
    written down at every call site; making it nullable keeps FR-015 reachable without a second
    entry point. See :func:`_regimes_of_scenario` for what each value resolves to.
    """
    owner_id, endpoints = loader.spendable_from_file(spendable_file)
    _check_spendable_owner(
        owner_id, ramp.streams, path=spendable_file, stream_files=ramp.stream_files
    )
    for position, endpoint in enumerate(endpoints):
        _check_spendable(
            endpoint,
            position=position,
            venues=ramp.venues,
            base_currency=ramp.base_currency,
            path=spendable_file,
        )
    return CoverageDeclarations(
        ramp=ramp,
        spendable=frozenset(endpoints),
        spendable_file=spendable_file,
        scenario_id=scenario_id,
        regimes=_regimes_of_scenario(
            scenario_id, ramp.scenarios, scenario_files=ramp.scenario_files
        ),
    )


def coverage_from_data_root(
    root: Path, *, base_currency: Currency, scenario_id: str | None
) -> CoverageDeclarations:
    """Every declaration a coverage report needs, under one data root.

    :func:`ramp_from_data_root`'s six families, plus ``spendable/*.toml``. An empty
    ``spendable/`` directory is an **error** for the reason that function already gives: a
    mistyped path and an empty world are indistinguishable downstream, and one of them is a
    mistake -- and here the mistake would be the loudest possible one, since a report with no
    spendable endpoints marks every destination in the registry deficit 3.

    ⚙ **Exactly one file, and a second is refused by name.** ``contracts/spendable-schema.md``
    gives :class:`CoverageDeclarations` one ``spendable_file``, and the spec assumes one owner.
    A second file is refused rather than merged, on the precedent of the ``deposit`` fallback
    policy: a real thing that is not built yet and an unrecognised thing are different facts,
    and the owner acts differently on each. Merging two owners' lists silently would let one
    person's spendable venues decide the other person's verdicts -- and this file is per-owner
    precisely so that cannot happen.

    **The same blend arrives through ``streams/`` and is refused there too.** This directory
    holds one file, but ``ramp_from_data_root`` globs every ``streams/*.toml``, so the claim
    above is only true because :func:`_check_spendable_owner` requires the streams loaded
    beside the list to be *this* owner's and no one else's. Without that half, the sentence
    here would be false in the one direction nobody was looking.
    """
    declared = sorted((root / SPENDABLE_DIR).glob("*.toml"))
    if not declared:
        raise DeclarationError(
            root / SPENDABLE_DIR,
            "",
            f"contains no *.toml declarations. An empty {SPENDABLE_DIR} directory is reported "
            "rather than read as 'money can never come back out': every declared exit would "
            "fail the spendable test at once, and the report would name a deficit for every "
            "destination in the registry while the real fault was a mistyped path.",
            "check the data root, or declare the venues you actually spend from",
        )
    if len(declared) > 1:
        raise DeclarationError(
            root / SPENDABLE_DIR,
            "",
            f"holds {len(declared)} spendable declarations "
            f"({', '.join(path.name for path in declared)}), and this engine resolves one. "
            "There is exactly one owner today (spec Assumptions), and a coverage run audits one "
            "person's registry: merging two lists would let one owner's spendable venues decide "
            "the other's verdicts. Multi-owner resolution is a later feature, not a defect "
            "here.",
            "keep one file per data root until multi-owner support lands",
        )
    return resolve_coverage(
        ramp=ramp_from_data_root(root, base_currency=base_currency),
        spendable_file=declared[0],
        scenario_id=scenario_id,
    )


# ---------------------------------------------------------------------------
# 006-inzhur-instruments: fund reference resolution
# ---------------------------------------------------------------------------
#
# The same cross-file pass a bond declaration gets, over the same tax pack. It lives here
# rather than in the loader for the reason every check in this module does: whether a class
# id resolves depends on files ``fund_from_file`` has never opened.


def _check_fund_references(
    declared: FundDeclaration,
    tax_classes: Mapping[str, TaxClass],
    *,
    path: Path,
) -> None:
    """Every tax class a fund names must exist **and** cover the kind named.

    Both halves, exactly as for a bond -- and the second matters more here than anywhere
    else in the project, because a fund is the first instrument to name *two different*
    classes. A distribution class that quietly did not cover ``distribution`` would be
    refused mid-projection, against an event, rather than here against the file that
    declared the reference.
    """
    for kind, class_id in declared.tax_classes.items():
        field_path = f"instrument.tax_classes.{kind.value}"
        found = tax_classes.get(class_id)
        if found is None:
            raise DeclarationError(
                path,
                field_path,
                f"{declared.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which no tax file declares. The reference is reported "
                "rather than treated as untaxed: an exemption is a cited claim and a "
                "missing rule is not, and reading the second as the first would flatter "
                "every figure derived from this fund by exactly the tax never charged.",
                f"declare {class_id!r} in a data/tax file, or reference a class that exists"
                f" ({', '.join(sorted(tax_classes)) or 'none are declared'})",
            )
        if kind not in found.applies_to:
            raise DeclarationError(
                path,
                field_path,
                f"{declared.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which declares that it applies to "
                f"{', '.join(sorted(applies.value for applies in found.applies_to))} and "
                "not to that kind. A fund is taxed one way on a payout and another on an "
                "exit, so a class pointed at the wrong kind is the single easiest mistake "
                "to make in a fund declaration — and it is caught here rather than "
                "mid-projection.",
                f"add {kind.value!r} to that class's applies_to if the rule covers it, or "
                "reference the class that does",
            )


# 004-composed-paths: the segment bound's cross-file pass
# ---------------------------------------------------------------------------
#
# One new declaration and one relation the file cannot check about itself: **the owner owns the
# streams the bound is resolved with**. How far a search may run is a fact about *this* person
# (Principle VII), and one owner's policy deciding another's reach would put two people's facts
# in one comparison -- feature 003's argument about the spendable list, applied to the one knob
# feature 004 adds.

COMPOSITION_DIR = "composition"
"""Where the per-owner segment bound lives under a data root.

**Per-owner, beside `streams/` and `spendable/`, not at the root beside curated `venues.toml`**
-- the same Principle VII boundary, made structural (004 research.md D8).
"""


@dataclass(frozen=True, slots=True)
class CompositionDeclarations:
    """Every declaration composed candidates need: the coverage set, plus the segment bound.

    ⚙ **A record beside :class:`CoverageDeclarations` rather than more fields on it**, on the
    precedent that record itself sets against :class:`RampDeclarations`. The three describe
    different runs: a data root with no composition file must still be able to cost a ramp and
    audit a registry, and folding the bound into either would make every existing caller require
    a file this feature invented.

    **It builds on the coverage set rather than on the ramp set, and that is a dependency on
    declarations rather than on a report** (004 research.md D13). Composition needs the
    *spendable list*, because a composed exit chain has to end somewhere the owner calls
    spendable (FR-022), and it needs the regimes, because every segment of a candidate belongs to
    one regime's route set (FR-017). Both are already resolved and checked by
    :func:`resolve_coverage`. What composition does **not** consult is the coverage *report*:
    using the declarations is not using the audit, and a ranking that depended on a report would
    invert the direction feature 003's FR-019 fixed.
    """

    coverage: CoverageDeclarations
    """The venues, streams, routes, channels, kinds, scenarios, regimes and spendable endpoints
    -- one owner's registry, already checked against itself."""

    bound: SegmentBound
    """The declared maximum number of segments in a candidate (FR-006). Recorded with every
    enumeration it bounds, so a corridor's absence is attributable to the bound rather than
    mistaken for a gap in the registry."""

    composition_file: Path
    """Which file declared the bound. Not decoration: it is what lets a later failure still name
    the file after the TOML has been discarded."""


def _check_composition_owner(
    owner_id: str,
    streams: Mapping[str, IncomeStream],
    *,
    path: Path,
) -> None:
    """The bound must belong to the owner whose streams it is resolved with (Principle VII).

    A composed candidate is keyed by its stream, so a bound resolved beside somebody else's
    streams would decide how far *his* money is allowed to travel -- one person's stated
    preference silently applied to another person's registry.

    ⚙ **Only one half of :func:`_check_spendable_owner`'s check is here, and the other half is
    not missing.** That function also refuses a run holding a *second* owner's streams beside the
    first's, and :func:`resolve_composition` takes an already-resolved
    :class:`CoverageDeclarations` -- which has been through exactly that refusal. Repeating it
    here was unreachable code: no input can arrive with a foreign stream still in it. A guard
    that cannot fire is worse than no guard, because it reads as protection.
    """
    owners = sorted({stream.owner_id for stream in streams.values()})
    if owner_id not in owners:
        raise DeclarationError(
            path,
            f"{loader.OWNER_TABLE}.id",
            f"declares owner {owner_id!r}, but the income streams this bound is resolved with "
            f"belong to {owners}. How far a search may run is one person's stated policy, so a "
            "bound belonging to somebody else would decide this owner's reach -- and which "
            "corridors he is shown at all.",
            f"name one of {owners}, or resolve this bound against that owner's streams",
        )


def resolve_composition(
    *, coverage: CoverageDeclarations, composition_file: Path
) -> CompositionDeclarations:
    """The coverage declarations plus a resolved segment bound, checked against their owner.

    Takes the resolved :class:`CoverageDeclarations` rather than the paths that produced them,
    on :func:`resolve_coverage`'s own reasoning: the bound is checked against the *streams*,
    which are already resolved by then, and re-resolving them here would give a data root two
    chances to disagree with itself.
    """
    owner_id, bound = loader.composition_from_file(composition_file)
    _check_composition_owner(owner_id, coverage.ramp.streams, path=composition_file)
    return CompositionDeclarations(
        coverage=coverage, bound=bound, composition_file=composition_file
    )


def composition_from_data_root(
    root: Path, *, base_currency: Currency, scenario_id: str | None
) -> CompositionDeclarations:
    """Every declaration composed candidates need, under one data root.

    :func:`coverage_from_data_root`'s families, plus ``composition/*.toml``.

    **An empty directory is an error, not a policy of "do not compose".** FR-006 refuses a
    permissive default, and the absence of the file is the absence of the policy: a mistyped
    path and an unstated bound are indistinguishable downstream, and reading the absence as a
    bound of 1 would silently turn the feature off in a run that asked for it.

    ⚙ **Exactly one file, and a second is refused by name**, on feature 003's precedent for the
    spendable list. Two owners' policies cannot both be in force, and merging them silently --
    by taking either one, or the smaller, or the larger -- would let one person decide the
    other's reach. Multi-owner resolution is a later feature, not a defect here.
    """
    declared = sorted((root / COMPOSITION_DIR).glob("*.toml"))
    if not declared:
        raise DeclarationError(
            root / COMPOSITION_DIR,
            "",
            f"contains no *.toml declarations. An empty {COMPOSITION_DIR} directory is reported "
            "rather than read as a bound of 1: FR-006 refuses a permissive default, and the "
            "absence of the file is the absence of the policy. A run that quietly considered "
            "only declared routes would hide every composable corridor while the real fault was "
            "a mistyped path.",
            "check the data root, or declare how many segments a candidate may chain",
        )
    if len(declared) > 1:
        raise DeclarationError(
            root / COMPOSITION_DIR,
            "",
            f"holds {len(declared)} composition declarations "
            f"({', '.join(path.name for path in declared)}), and this engine resolves one. "
            "There is exactly one owner today (spec Assumptions), and two owners' policies "
            "cannot both be in force: merging them would let one person decide the other's "
            "reach, which is what a per-owner file exists to prevent.",
            "keep one file per data root until multi-owner support lands",
        )
    return resolve_composition(
        coverage=coverage_from_data_root(
            root, base_currency=base_currency, scenario_id=scenario_id
        ),
        composition_file=declared[0],
    )


# ---------------------------------------------------------------------------
# 014-candidates: how many candidates one enumeration may produce
# ---------------------------------------------------------------------------
#
# One new declaration and the same relation `composition` cannot check about itself: **the
# owner owns the streams the ceiling is resolved with**. How many options this person is shown
# is a fact about *this* person (Principle VII), and because exceeding the ceiling refuses
# rather than truncates, somebody else's number would decide whether he is shown any at all.

CANDIDATES_DIR = "candidates"
"""Where the per-owner candidate ceiling lives under a data root.

**Per-owner, beside `composition/`**, for that directory's reason unchanged (014 research D9).
"""


@dataclass(frozen=True, slots=True)
class CandidateDeclarations:
    """Every declaration an enumeration needs: the composition set, plus the candidate ceiling.

    A record beside :class:`CompositionDeclarations` rather than more fields on it: a data root
    with no ceiling must still be able to compose candidates, and folding the ceiling in would
    make every existing caller require a file this feature invented.
    """

    composition: CompositionDeclarations
    """The routes, venues, streams, spendable endpoints, regimes and the segment bound -- one
    owner's registry, already checked against itself."""

    ceiling: CandidateCeiling
    """The declared maximum number of candidates one enumeration may produce (FR-019)."""

    candidates_file: Path
    """Which file declared the ceiling. Not decoration: it is what lets a later failure still
    name the file after the TOML has been discarded."""


def _check_candidates_owner(
    owner_id: str,
    streams: Mapping[str, IncomeStream],
    *,
    path: Path,
) -> None:
    """The ceiling must belong to the owner whose streams it is resolved with (Principle VII).

    Only one half of :func:`_check_spendable_owner`'s check, and the other half is not missing:
    the input is an already-resolved :class:`CompositionDeclarations`, so no run holding a
    second owner's streams can reach here. A guard that cannot fire reads as protection.
    """
    owners = sorted({stream.owner_id for stream in streams.values()})
    if owner_id not in owners:
        raise DeclarationError(
            path,
            f"{loader.OWNER_TABLE}.id",
            f"declares owner {owner_id!r}, but the income streams this ceiling is resolved "
            f"with belong to {owners}. How many options a search may produce is one person's "
            "stated policy, and exceeding the ceiling refuses rather than truncates -- so a "
            "ceiling belonging to somebody else would decide whether this owner is shown any "
            "options at all.",
            f"name one of {owners}, or resolve this ceiling against that owner's streams",
        )


def resolve_candidates(
    *, composition: CompositionDeclarations, candidates_file: Path
) -> CandidateDeclarations:
    """The composition declarations plus a resolved ceiling, checked against their owner.

    Takes the resolved :class:`CompositionDeclarations` rather than the paths that produced
    them, on :func:`resolve_composition`'s own reasoning: the ceiling is checked against the
    *streams*, which are already resolved by then, and re-resolving them here would give a data
    root two chances to disagree with itself.
    """
    owner_id, ceiling = loader.candidates_from_file(candidates_file)
    _check_candidates_owner(owner_id, composition.coverage.ramp.streams, path=candidates_file)
    return CandidateDeclarations(
        composition=composition, ceiling=ceiling, candidates_file=candidates_file
    )


def candidates_from_data_root(
    root: Path, *, base_currency: Currency, scenario_id: str | None
) -> CandidateDeclarations:
    """Every declaration an enumeration needs, under one data root.

    :func:`composition_from_data_root`'s families, plus ``candidates/*.toml``.

    **An empty directory is an error, not an absent ceiling.** FR-019 refuses a default, and the
    absence of the file is the absence of the policy: reading it as *no limit* would let a
    registry that has outgrown enumeration keep enumerating, which is the one thing the ceiling
    exists to report.

    Exactly one file: two ceilings cannot both be in force, and merging them -- by taking
    either, or the smaller, or the larger -- would let one person decide whether the other is
    shown any options at all.
    """
    declared = sorted((root / CANDIDATES_DIR).glob("*.toml"))
    if not declared:
        raise DeclarationError(
            root / CANDIDATES_DIR,
            "",
            f"contains no *.toml declarations. An empty {CANDIDATES_DIR} directory is reported "
            "rather than read as 'enumerate as many as it takes': FR-019 refuses a default, and "
            "the absence of the file is the absence of the policy. A run that quietly enumerated "
            "without limit would hide exactly the finding the ceiling exists to deliver.",
            "check the data root, or declare how many candidates one enumeration may produce",
        )
    if len(declared) > 1:
        raise DeclarationError(
            root / CANDIDATES_DIR,
            "",
            f"holds {len(declared)} candidate-ceiling declarations "
            f"({', '.join(path.name for path in declared)}), and this engine resolves one. "
            "There is exactly one owner today (spec Assumptions), and two ceilings cannot both "
            "be in force: merging them would let one person decide whether the other is shown "
            "any options at all.",
            "keep one file per data root until multi-owner support lands",
        )
    return resolve_candidates(
        composition=composition_from_data_root(
            root, base_currency=base_currency, scenario_id=scenario_id
        ),
        candidates_file=declared[0],
    )


LOADERS_BY_KIND: Mapping[str, Callable[[Path], object]] = {
    instrument_registry.FIXED_INCOME: loader.instrument_from_file,
    instrument_registry.ENUMERATED_SCHEDULE: loader.enumerated_instrument_from_file,
    instrument_registry.COLLECTIVE_INVESTMENT_FUND: loader.fund_from_file,
}
"""Which loader parses each declared ``[instrument] class``.

⚙ **Feature 006.** The *vocabulary* of declaration kinds is domain knowledge and lives in
``core.instruments.registry``; which function reads each file is the data layer's business
and lives here, beside the loaders. Keeping them apart is what stops ``core`` needing to
know that a file exists.

A mapping rather than a branch, on ``core``'s own precedent -- *"registries are mappings of
functions, not subclass dispatch"* (owner decision D-E). Not every entry returns the same record
type, so this is typed at ``object`` and the caller narrows immediately; that is honest
about what the loaders have in common, which is a path in and a declaration out and
nothing else.

⚙ **Feature 013 added a second entry returning an ``InstrumentDeclaration``.** The two
forms of bond declaration are one record and one downstream, and they differ only in which
loader reads the file -- which is exactly what this mapping is for.

:func:`_kind_of` refuses a kind the vocabulary does not contain, naming the
file, so an unrecognised class never reaches a ``KeyError`` here.
"""


def _kind_of(path: Path) -> str:
    """The declaration kind a file names, checked against the vocabulary ``core`` declares.

    Two failures with different remedies, so they are reported separately: a file with no
    ``class`` at all is :func:`loader.declared_class_of`'s error, and a file naming a class
    this engine does not implement is this one -- which lists what would have worked,
    because an unrecognised kind is almost always a typo.
    """
    declared = loader.declared_class_of(path)
    if declared not in instrument_registry.DECLARATION_KINDS:
        raise DeclarationError(
            path,
            "instrument.class",
            f"declares {declared!r}, which is not a declaration kind this engine "
            "implements. There is no fallback: reading an unknown kind as a bond would "
            "fail later, against a field the author never wrote.",
            f"one of: {', '.join(sorted(instrument_registry.DECLARATION_KINDS))}",
        )
    return declared


# ---------------------------------------------------------------------------
# 008-seed-and-goals: the owner's opening lots and targets, resolved as one life
# ---------------------------------------------------------------------------
#
# Two new declarations and three relations no single file can check about itself:
#
# * **a seed's instrument must be declared** (FR-005) -- the reference resolves only against
#   the whole curated set, which is what this module exists to hold;
# * **a goal's currency must be the run's base currency** (FR-016) -- a base currency is a
#   property of the run rather than of the file, the same reading `_check_spendable` already
#   applies to a spendable endpoint;
# * **the two files must name the same owner** -- one run holds one person's life
#   (Principle VII), and resolving somebody's holdings beside somebody else's target would
#   produce a report whose every figure was arithmetically correct and about nobody.
#
# ⚙ **An absent or empty directory is *not* an error here**, and this is the only declaration
# family in the project of which that is true (008 FR-024, research.md D9). `composition`
# refuses the same shape and the contrast is deliberate: the absence of a segment bound is the
# absence of a policy a search cannot proceed without, while the absence of a holding is a
# perfectly ordinary financial position. Refuse emptiness where it cannot be told from an
# error; accept it where it can.
#
# What is deliberately **not** checked here: whether a lot was acquired before its instrument
# existed. That is a well-formed declaration of an impossible history and it is the engine's
# typed `InconsistentTerms`, on the precedent of a maturity on or before its issue date --
# `core.ledger.seeds.opening_events` reports it.

SEEDS_DIR = "seeds"
"""Where the owner's declared opening lots live under a data root.

**Per-owner, beside `streams/`, `spendable/` and `composition/`**, and not at the root beside
curated `venues.toml` -- the Principle VII boundary made structural (008 research.md D2).
"""

GOALS_DIR = "goals"
"""Where the owner's declared targets live under a data root."""


@dataclass(frozen=True, slots=True)
class SeedAndGoalDeclarations:
    """One owner's holdings and targets, resolved against the curated declarations.

    A record beside :class:`Declarations` rather than more fields on it, on the precedent
    :class:`CoverageDeclarations` and :class:`CompositionDeclarations` set: the three describe
    different runs, and folding seeds into the instrument set would make every existing caller
    require files this feature invented.
    """

    owner_id: str | None
    """Whose declarations these are, or ``None`` when neither file exists.

    ``None`` is a real state and not a missing value: it says *nobody declared anything*, which
    is what a data root with no per-owner holdings and no per-owner goals means. It is not a
    default owner and it is not an error (FR-024).
    """

    seeds: tuple[SeedLot, ...]
    """The declared opening lots, in file order. Empty is ordinary."""

    goals: tuple[Goal, ...]
    """The declared targets, in file order. Empty is ordinary."""

    seed_file: Path | None
    """Which file declared the lots, or ``None`` if none did.

    Not decoration: it is what lets a later failure name the file after the TOML has been
    discarded -- and what a test asserting the Principle VII boundary points at.
    """

    goal_file: Path | None
    """Which file declared the targets, or ``None`` if none did."""


def _check_seed_instruments(
    declared: Sequence[SeedLot],
    instruments: Mapping[str, InstrumentDeclaration],
    *,
    path: Path,
) -> None:
    """FR-005: every seed names a curated instrument, or the load fails naming both.

    ``core.ledger.seeds.opening_events`` refuses the same thing as a typed
    ``SeedInstrumentUndeclared``, for a caller that assembles lots without a file. Both exist
    on :class:`UnresolvedTaxClass`'s precedent, and for its reason: the core cannot name a file
    it never saw, and FR-005 asks for the file.
    """
    for position, lot in enumerate(declared):
        if lot.instrument_id in instruments:
            continue
        raise DeclarationError(
            path,
            f"{loader.SEED_TABLE}[{position}].instrument_id",
            f"names the instrument {lot.instrument_id!r}, which no curated declaration "
            f"defines. Declared instruments: {sorted(instruments)}. No placeholder is created "
            "for it: every figure derived from a holding of an invented instrument would be a "
            "confident answer about something that does not exist.",
            "correct the id, or declare the instrument under data/instruments/",
        )


def _check_goal_currencies(
    declared: Sequence[Goal], *, base_currency: Currency, path: Path
) -> None:
    """FR-016: a non-base target is refused as **not yet modelled**, never as invalid.

    The distinction is the requirement rather than a nicety. USD is a currency this engine
    models perfectly well; what is missing is the dated-rate machinery that would make a dollar
    target comparable with a hryvnia one, and §4.7 is explicit that under devaluation the two
    are different goals rather than one goal in two denominations. A reader told "invalid
    currency" would go and edit a file that is correct.
    """
    for position, goal in enumerate(declared):
        if goal.currency is base_currency:
            continue
        raise DeclarationError(
            path,
            f"{loader.GOAL_TABLE}[{position}].currency",
            f"declares the target {goal.id!r} in {goal.currency.value}, which is **not yet "
            f"modelled**. The base currency of this run is {base_currency.value}, and "
            f"restating a {goal.currency.value} target in it needs a dated exchange rate this "
            "feature does not model -- so the goal is refused rather than converted at a rate "
            "nobody declared. A target in one currency and the same number in another are "
            "different goals under devaluation, which is why the field exists at all.",
            f"declare the target in {base_currency.value} until multi-currency goals land "
            "(specs/features.toml records them as future work)",
        )


def _check_one_owner(
    seed_owner: str | None,
    goal_owner: str | None,
    *,
    goal_path: Path | None,
) -> str | None:
    """One run holds one person's life (Principle VII), or none at all.

    The error is raised against the *goal* file because the seed file is resolved first and is
    therefore the one already in force; naming the second file is what sends the reader to the
    line they are most likely to have just written.
    """
    if seed_owner is None:
        return goal_owner
    if goal_owner is None or goal_owner == seed_owner:
        return seed_owner
    if goal_path is None:  # pragma: no cover -- a goal owner implies a goal file
        raise AssertionError("a goal owner was resolved without a goal file")
    raise DeclarationError(
        goal_path,
        f"{loader.OWNER_TABLE}.id",
        f"declares owner {goal_owner!r}, but the holdings resolved in this run belong to "
        f"{seed_owner!r}. Measuring one person's portfolio against another person's target "
        "would produce a report in which every figure was arithmetically correct and none of "
        "it was about anybody.",
        f"name {seed_owner!r}, or resolve this goal against that owner's holdings",
    )


def resolve_seeds_and_goals(
    *,
    seed_file: Path | None,
    goal_file: Path | None,
    instruments: Mapping[str, InstrumentDeclaration],
    base_currency: Currency,
) -> SeedAndGoalDeclarations:
    """The owner's declared holdings and targets, checked against the curated set and the run.

    Either file may be ``None``, and both may be: that is a person who holds nothing and wants
    nothing in particular, which is an ordinary state rather than a refusal (FR-024).
    """
    seed_owner: str | None = None
    goal_owner: str | None = None
    declared_seeds: tuple[SeedLot, ...] = ()
    declared_goals: tuple[Goal, ...] = ()

    if seed_file is not None:
        seed_owner, declared_seeds = loader.seeds_from_file(seed_file, base_currency=base_currency)
        _check_seed_instruments(declared_seeds, instruments, path=seed_file)
    if goal_file is not None:
        goal_owner, declared_goals = loader.goals_from_file(goal_file)
        _check_goal_currencies(declared_goals, base_currency=base_currency, path=goal_file)

    return SeedAndGoalDeclarations(
        owner_id=_check_one_owner(seed_owner, goal_owner, goal_path=goal_file),
        seeds=declared_seeds,
        goals=declared_goals,
        seed_file=seed_file,
        goal_file=goal_file,
    )


def _at_most_one(root: Path, directory: str) -> Path | None:
    """The single declaration in a per-owner directory, or ``None`` if there is none.

    **Zero is ordinary and two is refused**, which is the same split every other per-owner
    directory makes at the top end and the opposite of what they make at the bottom. Two
    owners' declarations cannot both be in force -- merging them would put two people's
    holdings in one ledger -- while nobody's declarations being present is simply a person who
    has not declared any.
    """
    declared = sorted((root / directory).glob("*.toml"))
    if not declared:
        return None
    if len(declared) > 1:
        raise DeclarationError(
            root / directory,
            "",
            f"holds {len(declared)} declarations "
            f"({', '.join(path.name for path in declared)}), and this engine resolves one. "
            "There is exactly one owner today (spec Assumptions), and two owners' holdings or "
            "targets cannot both be in force: merging them would put two people's money in one "
            "ledger, and every figure would describe a portfolio nobody has.",
            "keep one file per data root until multi-owner support lands",
        )
    return declared[0]


def seeds_and_goals_from_data_root(
    root: Path, *, base_currency: Currency
) -> SeedAndGoalDeclarations:
    """One owner's holdings and targets under a data root, resolved against its instruments.

    The instrument set comes from :func:`from_data_root`, so a seed is checked against exactly
    the declarations a projection would run with rather than against a set assembled twice.

    **A missing ``seeds/`` or ``goals/`` directory is not an error** (FR-024), unlike every
    other family. See this section's banner for why the two cases are different rather than
    inconsistent.
    """
    return resolve_seeds_and_goals(
        seed_file=_at_most_one(root, SEEDS_DIR),
        goal_file=_at_most_one(root, GOALS_DIR),
        instruments=from_data_root(root).instruments,
        base_currency=base_currency,
    )


# ---------------------------------------------------------------------------
# 007-cpi-real-terms: the CPI series and the inflation assumption
# ---------------------------------------------------------------------------
#
# One relation a per-file validator structurally cannot check: **two files declaring one
# series identity**. Each is individually valid; together they declare two different things
# with one name, whichever loaded second would win by directory order, and every real figure
# would silently rest on the other one. The error names both files, on this module's own
# precedent, because knowing one of them leaves the reader to find the other by hand.
#
# ⚙ **An absent series and an absent assumption are reported states, not load failures**, and
# this is the one place this feature departs from `composition`'s precedent deliberately. An
# empty `composition/` directory is an error because the absence of the bound would silently
# turn a search off -- nothing in the output would say a corridor had been skipped. An absent
# CPI series is the opposite: every figure that wanted it comes back typed-unavailable naming
# the absence (FR-012), in words, where the owner reads it. Refusing to load would move an
# honest message from the result into a stack trace.

CPI_DIR = "cpi"
"""Where declared price-index series live under a data root. Cited; in `SOURCED_DIRS`."""

INFLATION_ASSUMPTION_DIR = "scenarios/inflation"
"""Where the declared future-inflation belief lives under a data root.

**A subdirectory of `scenarios/`, and the nesting is load-bearing.** `ramp_from_data_root`
globs `scenarios/*.toml` and validates every match as a scenario document, and `glob` does not
recurse -- so a belief declared here keeps the citation exemption `data/scenarios/` carries
(it is a belief, there is nothing to cite) without pretending to be a scenario. The same
reading `data/instruments/nav/` already has: a subdirectory holds a different shape of file.
"""


@dataclass(frozen=True, slots=True)
class InflationDeclarations:
    """Every declaration the real-terms slot needs: the price series, and the belief.

    ⚙ **A record beside the others rather than more fields on `Declarations`**, on
    `CompositionDeclarations`' own precedent. The sets describe different runs: a projection
    with no CPI declared is a legitimate run that produces a shape-identical result, and
    folding these fields into `Declarations` would make every existing caller require files
    this feature invented.
    """

    series: Mapping[str, CpiSeries]
    """Declared series by their own declared id, never by file name or load order (FR-002).

    Empty is a valid state and is reported by the figures that wanted one, not here.
    """

    series_files: Mapping[str, Path]
    """Which file declared each series. Not decoration: it is what lets a later failure -- a
    manifest entry, a duplicate discovered downstream -- still name the file after the TOML has
    been discarded."""

    assumption: InflationAssumption | None
    """The declared future-inflation belief, or ``None`` when this run was given none.

    ``None`` is a *reported reason* rather than an error: the assumed real figure comes back
    typed-unavailable naming the absence (FR-012), and there is no default rate anywhere for it
    to fall back on (FR-015).
    """

    assumption_file: Path | None
    """Which file declared the belief, so the run manifest can record it (FR-015)."""


def _resolved_cpi(files: Sequence[Path]) -> tuple[dict[str, CpiSeries], dict[str, Path]]:
    """Every declared series by id, refusing two files that claim one identity."""
    series: dict[str, CpiSeries] = {}
    declaring: dict[str, Path] = {}
    for path in files:
        declared = loader.cpi_from_file(path)
        if declared.id in series:
            raise DeclarationError(
                path,
                f"{loader.CPI_SERIES_TABLE}.id",
                f"declares the series id {declared.id!r}, which "
                f"{declaring[declared.id].name} already declares. Two series cannot share an "
                "identity: whichever loaded second would win by directory order, and every "
                "real figure would rest on the other one with nothing in the output to say "
                "which. A second economy's index is a second id.",
                f"give one of {declaring[declared.id].name} and {path.name} a distinct series id",
            )
        series[declared.id] = declared
        declaring[declared.id] = path
    return series, declaring


def _resolved_inflation_assumption(
    root: Path,
) -> tuple[InflationAssumption | None, Path | None]:
    """The one declared belief under a data root, or ``None`` when none is declared.

    Exactly one file, and a second is refused by name on feature 003's precedent for the
    spendable list: two beliefs cannot both be in force, and choosing between them -- by
    directory order, or by taking the higher rate -- would be stating the owner's belief for
    him. Running two assumptions is FR-015's *two runs*, each naming what it used, not one run
    holding both.
    """
    declared = sorted((root / INFLATION_ASSUMPTION_DIR).glob("*.toml"))
    if not declared:
        return None, None
    if len(declared) > 1:
        raise DeclarationError(
            root / INFLATION_ASSUMPTION_DIR,
            "",
            f"holds {len(declared)} inflation assumptions "
            f"({', '.join(path.name for path in declared)}), and one run rests on one belief. "
            "They are not merged and neither is preferred: FR-015 says two assumptions are two "
            "results, each naming the declaration it used, and picking one here would state "
            "the owner's belief for him.",
            "keep one file, and run the alternative belief as a separate run",
        )
    return loader.inflation_assumption_from_file(declared[0])[1], declared[0]


def inflation_from_data_root(root: Path) -> InflationDeclarations:
    """Every price series and the declared belief under one data root.

    ``cpi/*.toml`` and ``scenarios/inflation/*.toml``. Sorted, so a run does not depend on the
    order a filesystem happens to return, and neither directory is required to exist: an
    absent series and an absent assumption are reported by the figures that wanted them, in
    words, rather than as a load failure. See this section's banner for why that differs from
    `composition`.
    """
    series, declaring = _resolved_cpi(sorted((root / CPI_DIR).glob("*.toml")))
    assumption, assumption_file = _resolved_inflation_assumption(root)
    return InflationDeclarations(
        series=series,
        series_files=declaring,
        assumption=assumption,
        assumption_file=assumption_file,
    )


# ---------------------------------------------------------------------------
# 009-tax-depth: the assessment rules, and the owner's positions on them
# ---------------------------------------------------------------------------
#
# Two relations a per-file validator structurally cannot check:
#
# **A class mapped to a category that no rate pack declares.** Whether the class exists is a
# fact about another file, and reading the dangling reference as "no rules apply" would be the
# silent default this layer exists to prevent -- a class with rates and no category cannot be
# assessed at all.
#
# **Two files declaring one jurisdiction's rules.** Each is valid alone; together, whichever
# loaded second would win by directory order and every liability would rest on the other one.
#
# ⚙ **Absent rules are a load failure here, unlike an absent CPI series.** A tax year cannot be
# assessed at all without them -- there is no figure to come back typed-unavailable, because
# there is no figure. That is `composition`'s reading rather than `cpi`'s.

TAX_TIMING_DIR = "tax/timing"
"""Where the assessment rules live under a data root.

**A subdirectory of `tax/`, and the nesting is load-bearing.** `from_data_root` globs
`tax/*.toml` and validates every match as a rate pack, and `glob` does not recurse -- so these
files keep the directory's *citation requirement* (`scripts/check_provenance.py` uses `rglob`)
without being read as rate packs.
"""

TAX_POSITIONS_DIR = "scenarios/tax"
"""Where the owner's filing decisions and unsettled positions live.

A subdirectory of `scenarios/` for the reason `scenarios/inflation/` is one: it keeps the
citation exemption a belief needs without pretending to be a scenario document.
"""


def _timing_by_jurisdiction(root: Path) -> dict[str, tuple[loader.TimingDeclaration, Path]]:
    """Every ``data/tax/timing/<jurisdiction>.toml``, keyed by the jurisdiction it declares.

    Hoisted because two entry points need it -- the assessment rules a tax year is assembled
    from, and the official-rate series a taxation scheme's base is struck at -- and reading
    the directory twice would let the duplicate-jurisdiction refusal exist in one of them and
    not the other.

    An empty directory is **not** refused here: whether a run can proceed without assessment
    rules is the caller's question and they answer it differently.
    """
    declared: dict[str, tuple[loader.TimingDeclaration, Path]] = {}
    for path in sorted((root / TAX_TIMING_DIR).glob("*.toml")):
        timing = loader.timing_from_file(path)
        if timing.jurisdiction_id in declared:
            already = declared[timing.jurisdiction_id][1]
            raise DeclarationError(
                path,
                f"{loader.TIMING_TABLE}.jurisdiction",
                f"declares rules for {timing.jurisdiction_id!r}, which {already.name} already "
                "declares. Two rule sets cannot govern one jurisdiction: whichever loaded "
                "second would win by directory order, and every liability would rest on the "
                "other one.",
                f"merge {already.name} and {path.name}",
            )
        declared[timing.jurisdiction_id] = (timing, path)
    return declared


def tax_rules_from_data_root(
    root: Path, declarations: Declarations
) -> Mapping[str, AssessmentRules]:
    """Every jurisdiction's assessment rules, with their class references resolved.

    Keyed by jurisdiction id. ``declarations`` is passed in rather than re-read so that the
    class references resolve against **the same** rate packs the run will charge with: reading
    the files twice would let a reference resolve here and fail at the charge, or the reverse.
    """
    timing = _timing_by_jurisdiction(root)
    if not timing:
        raise DeclarationError(
            root / TAX_TIMING_DIR,
            "",
            "holds no assessment rules, so no tax year could be assembled: there would be no "
            "declared category, no declared deadline, and no declared finding about any basis "
            "method. Reported here rather than at the first assessment, which would blame "
            "whichever holding happened to be projected first.",
            "declare data/tax/timing/<jurisdiction>.toml",
        )
    rates = official_rates_from_data_root(root, _resolved_kinds(root / KINDS_FILE)[0])
    built: dict[str, AssessmentRules] = {}
    for jurisdiction, (declared, path) in timing.items():
        _check_timing_classes(path, declared, declarations)
        built[jurisdiction] = AssessmentRules(
            jurisdiction_id=declared.jurisdiction_id,
            tax_currency=declared.tax_currency,
            official_rate=_official_rate_for(path, declared, rates),
            categories={category.id: category for category in declared.categories},
            category_of_class=declared.category_of_class,
            timing={rule.category_id: rule for rule in declared.timing},
            methods={standing.method: standing for standing in declared.methods},
        )
    return built


def _check_timing_classes(
    path: Path, declared: loader.TimingDeclaration, declarations: Declarations
) -> None:
    """Every class the rules map to a category is a class some rate pack declares."""
    for class_id in sorted(declared.category_of_class):
        if class_id not in declarations.tax_classes:
            raise DeclarationError(
                path,
                f"{loader.TIMING_TABLE}.class",
                f"maps the tax class {class_id!r} to an income category, and no data/tax file "
                "declares that class. A category for a class that does not exist governs "
                "nothing, and the reference would look satisfied.",
                f"declare {class_id!r} in a data/tax file, or correct the reference",
            )


def tax_positions_from_data_root(
    root: Path,
) -> tuple[tax_year.FilingDecisions, tax_year.UnsettledPositions, Path] | None:
    """The owner's filing decisions and unsettled positions, or ``None`` if none are declared.

    ``None`` rather than a failure: a run that never reaches a taxable year needs none, and the
    refusals that *do* need them name the year or the question they were reached at, which is
    more useful than a load error naming a directory. A second file is refused by name, on
    003's precedent for the spendable list -- two sets of positions cannot both be in force,
    and choosing between them would state the owner's belief for him.
    """
    declared = sorted((root / TAX_POSITIONS_DIR).glob("*.toml"))
    if not declared:
        return None
    if len(declared) > 1:
        raise DeclarationError(
            root / TAX_POSITIONS_DIR,
            "",
            f"holds {len(declared)} sets of tax positions "
            f"({', '.join(path.name for path in declared)}), and one run rests on one set. "
            "They are not merged and neither is preferred: two positions on an unsettled "
            "question are two runs, each naming what it assumed.",
            "keep one file, and run the alternative position as a separate run",
        )
    filing, positions = loader.tax_positions_from_file(declared[0])
    return filing, positions, declared[0]


# ---------------------------------------------------------------------------
# 010-full-tuple: how an instrument is reached, and the whole set the join needs
# ---------------------------------------------------------------------------
#
# Four relations a per-file validator structurally cannot check, and they are the whole of
# this section:
#
# 1. **The instrument exists** -- of either declaration kind, because a fund and a bond share
#    one id space.
# 2. **The venues exist and can hold the instrument's currency**, which is `_check_venue`
#    unchanged. Money cannot sit where its currency cannot, and a purchase venue that cannot
#    hold what the instrument trades in is a seam nobody can cross.
# 3. **The quote's currency is the instrument's own.** The price states its currency so the
#    file reads on its own; the two are then checked against each other, on `_check_partner`'s
#    precedent, because a file that can state something wrong is a file whose disagreement can
#    be reported.
# 4. **A price is declared exactly where the instrument states none.** A fund prices from its
#    own declared NAV and entry markup; a bond declares a face value, which is what it repays,
#    and no purchase price at all. Both halves are refused: a missing bond price would leave a
#    purchase unsizable from an arriving amount, and a fund price here would be a second place
#    for one fact -- the two disagreeing the day one of them is updated, with nothing to say
#    which the figures used.
#
# ⚙ **This is also the first place the instrument side and the route side of the registry meet
# in one record.** `Declarations` (instruments, funds, tax) and `RampDeclarations` (venues,
# routes, channels, streams, kinds) have never known about each other, because until now
# nothing needed both: a projection had no route and a route bought nothing. The join needs
# every one of them at once, so `TupleDeclarations` composes rather than widens -- the same
# "a record beside X rather than more fields on X" the five records above already take.

ACCESS_DIR = "access"
"""Where access declarations live under a data root. Cited; in `SOURCED_DIRS`.

Its one observed value is a venue's unit quote, in `[access.price]`, which carries the four
citation keys every other sourced table does. The rest of an entry -- two venue ids, an
instrument id and a risk-class label -- is references and statements, and cites nothing, the
same reading `[instrument.tax_classes]` and `data/venues.toml` already carry.
"""


@dataclass(frozen=True, slots=True)
class TupleDeclarations:
    """Every declaration the join needs, in one place, resolved against each other.

    ⚙ **It composes the existing records rather than flattening them.** Reaching a route
    through `coverage.ramp.routes` is two attributes longer than a flat field would be, and it
    is what keeps one fact in one place: the venue set the access declarations were checked
    against is literally the venue set the routes were checked against, rather than a copy
    that can drift.
    """

    instruments: Declarations
    """The instrument, fund and tax-class declarations -- `from_data_root`'s output."""

    coverage: CoverageDeclarations
    """The routes, venues, channels, streams, kinds, regimes and spendable endpoints --
    `coverage_from_data_root`'s output, which already nests `RampDeclarations`."""

    access: Mapping[str, InstrumentAccess]
    """How each instrument is reached, keyed by instrument id."""

    access_files: Mapping[str, Path]
    """Which file declared each entry, so a later failure can still name it."""

    early_exit_file: Path
    """Which file declared the spread-holds belief every early-exit figure rests on."""

    registries: Registries
    """The same set again, flattened into the record the pure core takes.

    Built here rather than by every caller: assembling nine mappings by hand at each call site
    is nine chances to pass the wrong one, and the core must not learn how to read a data root
    to avoid that.
    """


def _access_instrument_currency(
    entry: InstrumentAccess,
    *,
    instruments: Mapping[str, InstrumentDeclaration],
    funds: Mapping[str, FundDeclaration],
    path: Path,
    field_prefix: str,
) -> tuple[Currency, bool]:
    """The declared currency of the instrument an entry names, and whether it self-prices.

    Both answers come from the same lookup, deliberately: they are two readings of *which
    declaration this is*, and computing them separately would let an entry be checked against
    one declaration's currency and another's pricing.
    """
    fund = funds.get(entry.instrument_id)
    if fund is not None:
        return fund.unit_currency, True
    declared = instruments.get(entry.instrument_id)
    if declared is not None:
        return declared.currency, False
    raise DeclarationError(
        path,
        f"{field_prefix}.instrument_id",
        f"says how {entry.instrument_id!r} is reached, and no declaration under "
        f"{INSTRUMENTS_DIR}/ declares it. An access entry for an instrument nobody declared "
        "describes a journey to nothing, and it is refused here rather than surfacing later "
        "as a tuple that refuses for a reason naming the wrong file. Declared instruments: "
        f"{sorted([*instruments, *funds])}.",
        "name a declared instrument, or add the instrument declaration",
    )


def _check_access(
    entry: InstrumentAccess,
    *,
    position: int,
    instruments: Mapping[str, InstrumentDeclaration],
    funds: Mapping[str, FundDeclaration],
    venues: Mapping[str, Venue],
    kinds: Mapping[str, ObservationKind],
    path: Path,
) -> None:
    """One access entry against the instruments, the venues, the kinds and its own pricing."""
    prefix = f"{loader.ACCESS_TABLE}[{position}]"
    currency, self_priced = _access_instrument_currency(
        entry, instruments=instruments, funds=funds, path=path, field_prefix=prefix
    )
    for field, venue_id in (("bought_at", entry.bought_at), ("proceeds_to", entry.proceeds_to)):
        _check_venue(venue_id, currency, venues, path=path, field_path=f"{prefix}.{field}")
    if entry.quote is not None:
        _check_kind(entry.quote.kind, kinds, path=path, field_path=f"{prefix}.price.kind")
    if entry.resale_price is not None:
        _check_kind(
            entry.resale_price.kind, kinds, path=path, field_path=f"{prefix}.resale_price.kind"
        )
    _check_access_price(
        entry, currency=currency, self_priced=self_priced, path=path, field_prefix=prefix
    )
    _check_resale_price(
        entry, currency=currency, self_priced=self_priced, path=path, field_prefix=prefix
    )


def _check_resale_price(
    entry: InstrumentAccess,
    *,
    currency: Currency,
    self_priced: bool,
    path: Path,
    field_prefix: str,
) -> None:
    """A resale price is optional, is in the instrument's currency, and is not a fund's.

    Optional because its absence is the shipped state and the thing 015 FR-031 refuses by name:
    an early exit that cannot be struck reports a missing declaration rather than a figure. A
    **fund** may not declare one, on the purchase quote's reasoning: it prices its own exit from
    its declared NAV and its declared exit discount, and a second price in a second file is one
    fact in two places.
    """
    quote = entry.resale_price
    if quote is None:
        return
    if self_priced:
        raise DeclarationError(
            path,
            f"{field_prefix}.resale_price",
            f"quotes a resale price for {entry.instrument_id!r}, which declares its own net "
            "asset value and its own exit discount. The quote is refused rather than preferred "
            "or ignored: an exit priced in two files is one fact in two places, and the day "
            "either moved the figure would rest on whichever the code happened to read.",
            "delete the [access.resale_price] table; the fund's own terms price its exit",
        )
    if quote.price.currency is not currency:
        raise DeclarationError(
            path,
            f"{field_prefix}.resale_price.currency",
            f"quotes a resale price for {entry.instrument_id!r} in {quote.price.currency.value}, "
            f"and that instrument is declared in {currency.value}. The two are refused rather "
            "than converted: there is no rate here, and inventing one would strike every early "
            "exit of this instrument at a sum nobody declared.",
            f"quote the resale price in {currency.value}, or correct the instrument's currency",
        )


def _check_access_price(
    entry: InstrumentAccess,
    *,
    currency: Currency,
    self_priced: bool,
    path: Path,
    field_prefix: str,
) -> None:
    """A price is declared exactly where the instrument states none, and in its currency."""
    quote = entry.quote
    price = None if quote is None else quote.price
    if self_priced and price is not None:
        raise DeclarationError(
            path,
            f"{field_prefix}.price",
            f"quotes a unit price for {entry.instrument_id!r}, which declares its own net "
            "asset value and its own entry markup. The quote is refused rather than preferred "
            "or ignored: one price in two files is one fact in two places, and the day either "
            "is updated the figures would rest on whichever the code happened to read, with "
            "nothing in the output to say which.",
            "delete the [access.price] table; the fund's own declaration prices it",
        )
    if not self_priced and price is None:
        raise DeclarationError(
            path,
            field_prefix,
            f"declares how {entry.instrument_id!r} is reached but quotes no unit price, and "
            "that instrument's own declaration states none either -- a face value is what a "
            "bond repays, not what it costs. Without a price an arriving amount cannot be "
            "turned into units at all, and assuming par would be putting a market fact into "
            "code where nobody declared it.",
            "add an [access.price] table quoting what one unit costs at that venue",
        )
    if price is not None and price.currency is not currency:
        raise DeclarationError(
            path,
            f"{field_prefix}.price.currency",
            f"quotes {entry.instrument_id!r} in {price.currency.value}, and that instrument "
            f"is declared in {currency.value}. The two are refused rather than converted: "
            "there is no rate here, and inventing one would size every purchase of this "
            "instrument at a number nobody declared.",
            f"quote the price in {currency.value}, or correct the instrument's currency",
        )


def _resolved_access(
    files: Sequence[Path],
    *,
    instruments: Mapping[str, InstrumentDeclaration],
    funds: Mapping[str, FundDeclaration],
    venues: Mapping[str, Venue],
    kinds: Mapping[str, ObservationKind],
) -> tuple[dict[str, InstrumentAccess], dict[str, Path]]:
    """Every access declaration by instrument id, checked, refusing two files that collide."""
    access: dict[str, InstrumentAccess] = {}
    declaring: dict[str, Path] = {}
    for path in files:
        for position, entry in enumerate(loader.access_from_file(path)):
            if entry.instrument_id in access:
                raise _refuse_duplicate(
                    "access declaration",
                    entry.instrument_id,
                    f"{loader.ACCESS_TABLE}[{position}].instrument_id",
                    declaring[entry.instrument_id],
                    path,
                )
            _check_access(
                entry,
                position=position,
                instruments=instruments,
                funds=funds,
                venues=venues,
                kinds=kinds,
                path=path,
            )
            access[entry.instrument_id] = entry
            declaring[entry.instrument_id] = path
    return access, declaring


EARLY_EXIT_DIR = "scenarios/early_exit"
"""Where the owner's early-exit belief lives, as a subdirectory of the scenarios directory.

Nested for ``INFLATION_ASSUMPTION_DIR``'s reason: ``scenarios/*.toml`` is globbed and validated
as scenario documents, and ``glob`` does not recurse.
"""


def _resolved_early_exit(
    root: Path, streams: Mapping[str, IncomeStream]
) -> tuple[SpreadHolds, Path]:
    """The one declared belief under a data root, checked against the streams' owner.

    An absent directory is an **error**, not an absent belief (015 FR-032): reading it as
    *the spread holds* would put a figure in the model that no file declares, which is the one
    thing the declaration exists to prevent.
    """
    declared = sorted((root / EARLY_EXIT_DIR).glob("*.toml"))
    if not declared:
        raise DeclarationError(
            root / EARLY_EXIT_DIR,
            "",
            f"contains no *.toml declarations. An empty {EARLY_EXIT_DIR} directory is reported "
            "rather than read as 'the observed spread holds': a horizon means the money comes "
            "out at its end, so every comparison can reach an early exit, and a run that "
            "assumed the belief would report a figure no file declares.",
            "check the data root, or declare what an early exit is struck under",
        )
    if len(declared) > 1:
        raise DeclarationError(
            root / EARLY_EXIT_DIR,
            "",
            f"holds {len(declared)} early-exit beliefs "
            f"({', '.join(path.name for path in declared)}), and this engine resolves one. Two "
            "beliefs cannot both be in force, and taking either would be choosing one by file "
            "order.",
            "keep one file per data root until multi-owner support lands",
        )
    owner_id, assumption = loader.early_exit_from_file(declared[0])
    owners = sorted({stream.owner_id for stream in streams.values()})
    if owner_id not in owners:
        raise DeclarationError(
            declared[0],
            f"{loader.EARLY_EXIT_TABLE}.owner_id",
            f"declares owner {owner_id!r}, but the income streams this belief is resolved with "
            f"belong to {owners}. What a person is willing to assume about a future price is "
            "his own statement, and one owner's belief marking another's figures would put two "
            "people's assumptions in one comparison.",
            f"name one of {owners}, or resolve this belief against that owner's streams",
        )
    return assumption, declared[0]


def tuple_from_data_root(
    root: Path, *, base_currency: Currency, scenario_id: str | None
) -> TupleDeclarations:
    """Every declaration a tuple evaluation needs, under one data root.

    The instrument side and the route side are resolved by the two entry points that already
    own them, and then the access declarations are checked against both. Nothing here
    re-parses a file either of them read.

    An empty ``access/`` directory is an **error**, on ``composition``'s precedent rather than
    ``cpi``'s: an absent CPI series makes every real figure say so in words, whereas an absent
    access set makes every tuple in the comparison refuse for a missing declaration -- and a
    comparison emptied by a forgotten directory looks exactly like one emptied by a genuine
    gap in the registry.
    """
    instruments = from_data_root(root)
    covered = coverage_from_data_root(root, base_currency=base_currency, scenario_id=scenario_id)
    files = sorted((root / ACCESS_DIR).glob("*.toml"))
    if not files:
        raise DeclarationError(
            root / ACCESS_DIR,
            "",
            "contains no *.toml declarations, so nothing says where any instrument is bought "
            "or where its proceeds land. It is reported rather than read as an empty world: "
            "every tuple would refuse for a missing declaration, and a comparison emptied by "
            "a mistyped path is indistinguishable from one emptied by a real gap.",
            "check the data root, or declare how each instrument is reached",
        )
    early_exit, early_exit_file = _resolved_early_exit(root, covered.ramp.streams)
    access, declaring = _resolved_access(
        files,
        instruments=instruments.instruments,
        funds=instruments.funds,
        venues=covered.ramp.venues,
        kinds=covered.ramp.kinds,
    )
    return TupleDeclarations(
        instruments=instruments,
        coverage=covered,
        access=access,
        access_files=declaring,
        early_exit_file=early_exit_file,
        registries=Registries(
            instruments=instruments.instruments,
            funds=instruments.funds,
            tax_classes=instruments.tax_classes,
            access=access,
            routes=covered.ramp.routes,
            channels=covered.ramp.channels,
            streams=covered.ramp.streams,
            kinds=covered.ramp.kinds,
            spendable=covered.spendable,
            spread_holds=early_exit,
            base_currency=covered.ramp.base_currency,
        ),
    )


# ---------------------------------------------------------------------------
# 011-official-rate: the declared official-rate series
# ---------------------------------------------------------------------------
#
# Two relations a per-file validator structurally cannot check:
#
# **Two files declaring one series identity.** Each is individually valid; together whichever
# loaded second would win by directory order and every tax base would rest on the other one.
#
# **The series a jurisdiction names for its tax currency.** Whether it exists is a fact about
# another file, and so is whether it quotes the currency the tax is assessed in — a series
# quoting dollars per hryvnia would strike every base at the reciprocal of the published rate
# and leave every figure plausible.
#
# ⚙ **An absent directory is an empty set, not a load failure**, on `cpi`'s reading rather
# than `composition`'s. A run that never strikes a foreign base needs no series, and the one
# that does comes back typed-unavailable, naming the pair it wanted and the event it failed on
# — which is more use to the owner than a load error naming a directory.

OFFICIAL_RATES_DIR = "official_rates"
"""Where declared official-rate series live under a data root. Cited; in `SOURCED_DIRS`."""


@dataclass(frozen=True, slots=True)
class OfficialRateDeclarations:
    """Every declared official-rate series under one data root, and which file declared it."""

    series: Mapping[str, OfficialRateSeries]
    """By their own declared id, never by file name or load order (FR-005).

    Empty is a valid state and is reported by the base that wanted one, not here.
    """

    files: Mapping[str, Path]
    """Which file declared each series, so a later failure can still name it after the TOML
    has been discarded."""


def official_rates_from_data_root(
    root: Path, kinds: Mapping[str, ObservationKind]
) -> OfficialRateDeclarations:
    """Every official-rate series under a data root, refusing two files claiming one identity.

    Sorted, so a run does not depend on the order a filesystem happens to return.

    ⚙ **``kinds`` is required, and this docstring is where that is explained.** A
    `[non_publication_rule]` table carries a citation and a list of dates and **no number**,
    so `scripts/check_provenance.py` -- which recognises a sourced table by its numeric
    leaves -- cannot see it, and its staleness kind would be checked nowhere. Left unchecked a
    misspelt kind loads clean and then raises from `staleness.kind_for` when a figure it
    marked is aged: a crash at report time for a file that could have been refused by name at
    load. Measured 2026-08-29.
    """
    series: dict[str, OfficialRateSeries] = {}
    declaring: dict[str, Path] = {}
    for path in sorted((root / OFFICIAL_RATES_DIR).glob("*.toml")):
        declared = loader.official_rate_from_file(path)
        if declared.rule is not None:
            # Sorted, for the reason the file list above is: a set has no order, and a
            # refusal that depends on one is a refusal that changes between runs. The field
            # path is the rule table's regardless of how many citations it grows, because
            # `loader._non_publication_rule` builds this provenance from that table alone.
            for source in sorted(declared.rule.provenance.sources, key=lambda ref: ref.id):
                _check_kind(
                    source.kind,
                    kinds,
                    path=path,
                    field_path=f"{loader.OFFICIAL_RATE_RULE_TABLE}.kind",
                )
        if declared.id in series:
            raise DeclarationError(
                path,
                f"{loader.OFFICIAL_RATE_SERIES_TABLE}.id",
                f"declares the series id {declared.id!r}, which "
                f"{declaring[declared.id].name} already declares. Two series cannot share an "
                "identity: whichever loaded second would win by directory order, and every "
                "tax base would rest on the other one with nothing in the output to say "
                "which. A second authority's series is a second id.",
                f"give one of {declaring[declared.id].name} and {path.name} a distinct id",
            )
        series[declared.id] = declared
        declaring[declared.id] = path
    return OfficialRateDeclarations(series=series, files=declaring)


def _official_rate_for(
    path: Path,
    declared: loader.TimingDeclaration,
    rates: OfficialRateDeclarations,
) -> OfficialRateSeries | None:
    """The series this jurisdiction declares for its tax currency, checked both ways.

    ``None`` when the file names none, which is a declared absence rather than an oversight:
    a foreign-currency taxable result then refuses saying this jurisdiction declared no series
    -- there is none to name -- and no other series is picked for it.
    """
    named = declared.official_rate_series
    if named is None:
        return None
    found = rates.series.get(named)
    if found is None:
        raise DeclarationError(
            path,
            f"{loader.TIMING_TABLE}.official_rate_series",
            f"names the official-rate series {named!r}, which no file in "
            f"data/{OFFICIAL_RATES_DIR} declares. There is no default series and no fallback "
            "to whichever one loaded first: a tax base struck from a series the jurisdiction "
            f"did not name is a legal figure nobody declared. Declared series: "
            f"{sorted(rates.series)}.",
            f"declare {named!r} in data/{OFFICIAL_RATES_DIR}, or name a series that exists",
        )
    if found.pair[0] is not declared.tax_currency:
        raise DeclarationError(
            path,
            f"{loader.TIMING_TABLE}.official_rate_series",
            f"assesses tax in {declared.tax_currency.value} and names the series {named!r}, "
            f"which quotes {found.pair[0].value} per {found.pair[1].value}. A series serves a "
            "tax currency only when that currency is the one it is quoted **in**; naming the "
            "series the other way round would strike every base at the reciprocal of the "
            "published rate and leave every figure plausible.",
            f"name a series quoting {declared.tax_currency.value} per another currency",
        )
    return found


# ---------------------------------------------------------------------------
# 012-fop-group-3: the taxation scheme, and where income is credited
# ---------------------------------------------------------------------------
#
# Three relations a per-file validator structurally cannot check:
#
# **Two files declaring one scheme identity.** Whichever loaded second would win by directory
# order, and every charge would rest on the other one.
#
# **A destination row's scheme and venue.** A row naming a scheme nobody declares computes
# nothing; a row naming a venue nobody declares records a judgement about a place this model
# cannot name.
#
# **A stream's declared treatment.** Whether it exists, and whether it is a scheme a stream is
# allowed to name — a `reading` scheme exists only inside a labelled what-if.

SCHEMES_DIR = "tax/schemes"
"""Where declared taxation schemes live. A subdirectory of `tax/`, which `check_provenance`
walks recursively and the rate-pack glob does not."""

DESTINATIONS_DIR = "tax/destinations"
"""Where the normative crediting-destination tables live."""


@dataclass(frozen=True, slots=True)
class SchemeDeclarations:
    """Every declared taxation scheme and crediting destination under one data root."""

    ramp: RampDeclarations
    """The venues and streams the rows above are checked against, resolved once."""

    schemes: Mapping[str, TaxationScheme]
    """By their own declared id, never by file name or load order."""

    official_rates: Mapping[str, OfficialRateSeries | None]
    """The series each scheme's jurisdiction declares for its tax currency, by jurisdiction id.

    Resolved here rather than left to the caller, because picking a series by hand is exactly
    how a base comes to be struck from one the jurisdiction did not name -- which is the
    refusal 011 already writes for the case, and which a caller cannot be relied on to avoid.
    ``None`` where the jurisdiction names no series, which is a declared absence: a
    foreign-currency charge under that scheme then refuses saying so.
    """

    destinations: Mapping[tuple[str, str], CreditingDestination]
    """Keyed ``(scheme id, venue id)``. A missing key is not an error here: it is what
    ``core.tax.scheme.apply`` refuses on, naming the destination and the scheme."""

    scheme_files: Mapping[str, Path]
    destination_files: Mapping[tuple[str, str], Path]


def schemes_from_data_root(root: Path, *, base_currency: Currency) -> SchemeDeclarations:
    """Every scheme and destination under a data root, with every reference checked.

    Composes ``ramp_from_data_root`` rather than taking venues and streams as arguments,
    because all three checks below need them and a caller assembling the pieces by hand is a
    caller who can assemble two-thirds of them.

    Sorted, so a run does not depend on the order a filesystem happens to return.
    """
    ramp = ramp_from_data_root(root, base_currency=base_currency)
    timing = _timing_by_jurisdiction(root)
    rates = official_rates_from_data_root(root, _resolved_kinds(root / KINDS_FILE)[0])
    schemes: dict[str, TaxationScheme] = {}
    scheme_files: dict[str, Path] = {}
    for path in sorted((root / SCHEMES_DIR).glob("*.toml")):
        declared = loader.scheme_from_file(path)
        if declared.id in schemes:
            raise DeclarationError(
                path,
                f"{loader.SCHEME_TABLE}.id",
                f"declares the scheme id {declared.id!r}, which "
                f"{scheme_files[declared.id].name} already declares. Two schemes cannot share "
                "an identity: whichever loaded second would win by directory order, and every "
                "charge under that name would rest on the other one's components with nothing "
                "in the output to say which.",
                f"give one of {scheme_files[declared.id].name} and {path.name} a distinct id",
            )
        _check_tax_currency(declared, timing, path=path)
        schemes[declared.id] = declared
        scheme_files[declared.id] = path

    official_rates: dict[str, OfficialRateSeries | None] = {}
    for scheme in schemes.values():
        found = timing.get(scheme.jurisdiction_id)
        official_rates[scheme.jurisdiction_id] = (
            None if found is None else _official_rate_for(found[1], found[0], rates)
        )

    destinations: dict[tuple[str, str], CreditingDestination] = {}
    destination_files: dict[tuple[str, str], Path] = {}
    for path in sorted((root / DESTINATIONS_DIR).glob("*.toml")):
        for position, row in enumerate(loader.destinations_from_file(path)):
            key = (row.scheme_id, row.venue_id)
            if key in destinations:
                already = destination_files[key]
                where = (
                    "this file already records it above"
                    if already == path
                    else f"{already.name} already records it"
                )
                raise DeclarationError(
                    path,
                    f"{loader.DESTINATION_TABLE}[{position}]",
                    f"records how {row.scheme_id!r} income credited at {row.venue_id!r} is "
                    f"treated, and {where}. One destination under one scheme has one verdict: "
                    "two rows for it are not merged and neither wins, because whichever the "
                    "lookup reached first would decide a legal position by file order.",
                    "delete one of the two rows",
                )
            _check_destination(row, schemes, ramp.venues, path=path, key=key)
            destinations[key] = row
            destination_files[key] = path

    for stream in ramp.streams.values():
        _check_treatment(stream, schemes, path=ramp.stream_files[stream.id])

    return SchemeDeclarations(
        ramp=ramp,
        schemes=schemes,
        official_rates=official_rates,
        destinations=destinations,
        scheme_files=scheme_files,
        destination_files=destination_files,
    )


def _check_tax_currency(
    scheme: TaxationScheme,
    timing: Mapping[str, tuple[loader.TimingDeclaration, Path]],
    *,
    path: Path,
) -> None:
    """A scheme assesses in the currency its jurisdiction assesses in, or it is refused.

    Checked only where the jurisdiction declares timing rules at all: a scheme in a
    jurisdiction with none has nothing to disagree with, and refusing it here would demand a
    tax year nobody is assembling.
    """
    declared = timing.get(scheme.jurisdiction_id)
    if declared is None or declared[0].tax_currency is scheme.tax_currency:
        return
    raise DeclarationError(
        path,
        f"{loader.SCHEME_TABLE}.tax_currency",
        f"is {scheme.tax_currency.value} and jurisdiction {scheme.jurisdiction_id!r} assesses "
        f"tax in {declared[0].tax_currency.value} ({declared[1].name}). The series that "
        "jurisdiction names quotes its own tax currency, so this scheme would refuse every "
        "foreign arrival for want of a pair -- and, worse, would charge an arrival already in "
        f"{scheme.tax_currency.value} with no rate consulted at all, producing a base in a "
        "currency the jurisdiction does not assess in and no sign that anything was wrong.",
        f'declare tax_currency = "{declared[0].tax_currency.value}", or move the scheme to a '
        "jurisdiction that assesses in the one it names",
    )


def _check_destination(
    row: CreditingDestination,
    schemes: Mapping[str, TaxationScheme],
    venues: Mapping[str, Venue],
    *,
    path: Path,
    key: tuple[str, str],
) -> None:
    """A row's scheme, its venue and every reading's scheme, checked against what exists."""
    field_prefix = f"{loader.DESTINATION_TABLE}[{key[0]}/{key[1]}]"
    # `is_reading` is carried rather than inferred from the field label. The comparison it
    # replaced -- `field != "scheme"` -- was in fact unreachable-safe, since a reading's label
    # always begins `reading[`; what is wrong with it is that its correctness depended on how
    # a message string happens to be spelled, and the next edit to that spelling would not
    # look like a behaviour change to anyone making it.
    for named, field, is_reading in (
        (row.scheme_id, "scheme", False),
        *((reading.scheme_id, f"reading[{reading.id}].scheme", True) for reading in row.readings),
    ):
        if named is None:
            continue
        if named in schemes:
            if is_reading and row.verdict is Verdict.INTERPRETED:
                _check_interpreted_reading(schemes[named], path=path, field_prefix=field_prefix)
            continue
        raise DeclarationError(
            path,
            f"{field_prefix}.{field}",
            f"names the taxation scheme {named!r}, which no file in data/{SCHEMES_DIR} "
            "declares. A reading that cannot resolve its scheme computes nothing, and "
            "there is no default scheme to fall back to: a charge under a scheme nobody "
            f"declared is a legal figure nobody wrote down. Declared schemes: "
            f"{sorted(schemes)}.",
            f"declare {named!r} in data/{SCHEMES_DIR}, or name a scheme that exists",
        )
    if row.venue_id not in venues:
        raise DeclarationError(
            path,
            f"{field_prefix}.venue",
            f"records a judgement about income credited at {row.venue_id!r}, which "
            "data/venues.toml does not declare. A row about a place this model cannot name "
            "is a row nothing can ever reach.",
            f"declare the venue, or name one of: {sorted(venues)}",
        )


def _check_interpreted_reading(named: TaxationScheme, *, path: Path, field_prefix: str) -> None:
    """An interpreted row may not charge under a scheme declared only for a reading.

    An interpreted destination produces **the tax owed**, and a ``declared_for = "reading"``
    scheme exists only inside a labelled what-if that says on its face it is not. Refusing an
    income stream from naming such a scheme and then letting one reach the same figure through
    a verdict would be the prohibition enforced at one door and open at the other -- and
    moving a verdict is one word in one file, which is exactly how it would happen.
    """
    if named.declared_for == "stream":
        return
    raise DeclarationError(
        path,
        f"{field_prefix}.verdict",
        f"is interpreted and its reading charges under {named.id!r}, which is declared for a "
        "reading rather than for a stream. An interpreted row produces the tax owed, and "
        "those rates exist only inside a labelled what-if that says on its face they are not "
        "it -- which is why an income stream may not name that scheme either.",
        "declare the verdict unsettled, or point the reading at a scheme declared for a stream",
    )


def _check_treatment(
    stream: IncomeStream, schemes: Mapping[str, TaxationScheme], *, path: Path
) -> None:
    """A stream's declared treatment: it must exist, and it must be one a stream may name."""
    named = stream.tax_scheme
    if named is None:
        return
    found = schemes.get(named)
    if found is None:
        raise DeclarationError(
            path,
            f"stream[{stream.id}].tax_scheme",
            f"names the tax treatment {named!r}, which no file in data/{SCHEMES_DIR} "
            "declares. There is no default treatment and none is substituted: a stream "
            "charged under a scheme nobody declared would be charged at rates nobody wrote "
            f"down. Declared schemes: {sorted(schemes)}.",
            f"declare {named!r} in data/{SCHEMES_DIR}, or name a scheme that exists",
        )
    if found.declared_for != "stream":
        raise DeclarationError(
            path,
            f"stream[{stream.id}].tax_scheme",
            f"names {named!r}, which is declared for a reading rather than for a stream. "
            "Such a scheme exists only inside a labelled what-if that says on its face it is "
            "not the tax owed; naming it here would make its rates somebody's actual "
            "treatment, which no source in this repository supports.",
            'name a scheme whose declared_for is "stream"',
        )


# ---------------------------------------------------------------------------
# 015-the-question: the questions, and the bundle one verb takes
# ---------------------------------------------------------------------------
#
# Three relations a per-file validator structurally cannot check, and every one of them is a
# **typo in an artefact under review** rather than a fact about the money (015 FR-004):
#
# 1. an amount for a stream the registry does not declare;
# 2. a declared stream the question states no amount for -- the case that fails *silently*
#    today, because such a stream's pairs yield no candidate and never reach `survey`;
# 3. an amount whose currency the named stream does not deliver.
#
# What is deliberately NOT checked here: whether a subject word names anything. A question is
# the owner's own vocabulary and its gaps are the answer's content (FR-009), which is the
# asymmetry with an instrument naming an undeclared group.

QUESTIONS_DIR = "questions"
"""Where the owner's questions live under a data root. Per-owner, beside `candidates/`."""


@dataclass(frozen=True, slots=True)
class AnswerDeclarations:
    """Everything the answer verb reads: the registries, the two policies, and the questions.

    ``Registries`` alone cannot carry it. The **candidate ceiling** comes from `data/candidates/`
    and the **segment bound** from `data/composition/`, and 014's `survey` takes both as its own
    arguments -- so a verb that could not receive them could not call it.
    """

    tuples: TupleDeclarations
    """The registries every candidate is evaluated against, and which file declared each."""

    candidates: CandidateDeclarations
    """The segment bound and the candidate ceiling, with the coverage set behind them."""

    questions: Mapping[str, Question]
    """Every declared question by its own id."""

    question_files: Mapping[str, Path]
    """Which file declared each question, so the manifest can name it after the TOML is gone."""


def _check_question(
    question: Question,
    streams: Mapping[str, IncomeStream],
    *,
    path: Path,
) -> None:
    """One question against the streams it names and the streams it does not."""
    owners = sorted({stream.owner_id for stream in streams.values()})
    if question.owner_id not in owners:
        raise DeclarationError(
            path,
            f"{loader.OWNER_TABLE}.id",
            f"declares owner {question.owner_id!r}, but the income streams this question is "
            f"resolved with belong to {owners}. A question is one person's, and answering it "
            "from another person's money would put two people's facts in one comparison.",
            f"name one of {owners}, or resolve this question against that owner's streams",
        )
    for stream_id, amount in question.amounts.items():
        field = f"{loader.QUESTION_TABLE}.amount"
        if stream_id not in streams:
            raise DeclarationError(
                path,
                f"{field}.stream",
                f"states an amount for {stream_id!r}, which no declaration under "
                f"{STREAMS_DIR}/ declares. The money has to leave somewhere: an amount for a "
                "stream nobody declared would be deployed by nothing and would silently "
                "disappear from the comparison.",
                f"name one of {sorted(streams)}, or declare that stream",
            )
        declared = streams[stream_id].amount.currency
        if amount.currency is not declared:
            raise DeclarationError(
                path,
                f"{field}.currency",
                f"states {stream_id!r}'s amount in {amount.currency.value}, and that stream "
                f"delivers {declared.value}. The two are refused rather than converted: there "
                "is no rate here, and in an artefact under review a mismatched currency is a "
                "typo rather than a fact about the money.",
                f"write the amount in {declared.value}",
            )
    for stream_id in sorted(streams):
        if stream_id not in question.amounts:
            raise DeclarationError(
                path,
                f"{loader.QUESTION_TABLE}.amount",
                f"states no amount for the declared stream {stream_id!r}. This is the case that "
                "fails silently: a stream with no stated amount whose pairs yield no candidate "
                "never reaches the comparison, so nothing raises and the answer is simply "
                "missing a stream nobody mentioned. In a file under review an omitted amount is "
                "a typo, not a decision to leave that money out.",
                f"state an amount for {stream_id!r}",
            )


def answer_from_data_root(
    root: Path, *, base_currency: Currency, scenario_id: str | None
) -> AnswerDeclarations:
    """Every declaration the answer verb reads, under one data root.

    An empty ``questions/`` directory is an **error**, on ``composition``'s precedent: a run
    that answered nothing would be indistinguishable from a mistyped path.
    """
    files = sorted((root / QUESTIONS_DIR).glob("*.toml"))
    if not files:
        raise DeclarationError(
            root / QUESTIONS_DIR,
            "",
            f"contains no *.toml declarations. An empty {QUESTIONS_DIR} directory is reported "
            "rather than read as 'nothing was asked': the two are indistinguishable to "
            "everything downstream, and one of them is a mistyped path.",
            "check the data root, or declare a question",
        )
    tuples = tuple_from_data_root(root, base_currency=base_currency, scenario_id=scenario_id)
    candidates = candidates_from_data_root(
        root, base_currency=base_currency, scenario_id=scenario_id
    )
    questions: dict[str, Question] = {}
    declaring: dict[str, Path] = {}
    for path in files:
        declared = loader.question_from_file(path)
        if declared.id in questions:
            raise _refuse_duplicate(
                "question",
                declared.id,
                f"{loader.QUESTION_TABLE}.id",
                declaring[declared.id],
                path,
            )
        _check_question(declared, tuples.registries.streams, path=path)
        questions[declared.id] = declared
        declaring[declared.id] = path
    return AnswerDeclarations(
        tuples=tuples,
        candidates=candidates,
        questions=questions,
        question_files=declaring,
    )
