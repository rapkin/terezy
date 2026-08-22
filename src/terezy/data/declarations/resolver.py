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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.core.primitives import money
from terezy.core.routes.venues import can_hold
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from terezy.core.instruments.interface import InstrumentDeclaration
    from terezy.core.primitives.currency import Currency
    from terezy.core.primitives.money import Money
    from terezy.core.primitives.staleness import ObservationKind
    from terezy.core.results.coverage import SpendableEndpoint
    from terezy.core.routes.channels import FxChannel
    from terezy.core.routes.legs import Leg, Route
    from terezy.core.routes.venues import Venue
    from terezy.core.streams.streams import IncomeStream
    from terezy.core.tax.interface import TaxClass
    from terezy.data.declarations.loader import ScenarioDeclaration

INSTRUMENTS_DIR = "instruments"
"""Where instrument declarations live under a data root."""

TAX_DIR = "tax"
"""Where jurisdiction rule packs live under a data root."""


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
    for path in instrument_files:
        declaration = loader.instrument_from_file(path)
        if declaration.id in instruments:
            raise _refuse_duplicate(
                "instrument",
                declaration.id,
                "instrument.id",
                instrument_files_by_id[declaration.id],
                path,
            )
        instruments[declaration.id] = declaration
        instrument_files_by_id[declaration.id] = path

    for identifier, declaration in instruments.items():
        _check_references(
            declaration,
            tax_classes,
            path=instrument_files_by_id[identifier],
        )

    return Declarations(
        instruments=instruments,
        tax_classes=tax_classes,
        instrument_files=instrument_files_by_id,
        tax_class_files=tax_class_files,
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
    return resolve(instrument_files=instruments, tax_files=tax)


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
#    starts where the inbound route ends, and finishes holding the base currency.
# 7. **``capacity_pool`` cap agreement** across *files* (research.md D10). Two legs naming
#    one rail must declare one cap.
# 8. **A regime's ``route_ids``** resolve, and a regime is **partner-closed**.
# 9. **A stream's ``arrives_at``** names a declared venue.
#
# ⚙ **One seam this pass cannot cover, stated rather than left to be discovered.** A
# channel *side* declares its own ``kind``, and ``ChannelSide`` has no field to carry it --
# the core's staleness verdict for a channel is taken from ``FxChannel.kind``. So a side
# naming an undeclared kind is caught by ``scripts/check_provenance.py``, which reads the
# files rather than the records and is a blocking gate, and not here. Adding a field to the
# core record for the sake of this check would put a value in the engine that no figure
# reads.

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
    *,
    path: Path,
    base_currency: Currency,
) -> None:
    """The four things a declared exit route must be (FR-027), each refused by name.

    ``partner_route`` absent is **legal and expected**: it means nobody has costed the way
    out, and it produces ``ExitCostUnknown`` rather than a reversal or a promoted one-way
    figure (FR-030). What is refused is a partner that *looks* declared and is not usable:

    * **A dangling id.** ``cost._round_trip`` raises on it, blaming the loader -- correctly,
      since the whole reason the absence is expressible is that a typo must not become it.
    * **A partner whose direction is not ``exit``.** An inbound route is not an exit; pairing
      two ways *in* would produce a round trip that never comes back.
    * **A partner that does not start where this route ends.** This is the sharpest of the
      four: a pair that does not meet would load and produce a *confident round-trip figure
      for two unrelated journeys*, which is the exact class of number FR-030 exists to
      refuse.
    * **A partner that does not end holding the base currency.** §4.3.3 asks for money back
      in **spendable** base currency; an exit that stops in dollars at an exchange has not
      got the money out, and an asset that cannot be liquidated into spendable base currency
      is not worth its stated value (Principle VI).
    """
    if route.partner_route is None:
        return
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

    for route_id, route in routes.items():
        _check_partner(route, routes, path=files[route_id], base_currency=base_currency)
    _check_pools(routes, files)
    return routes, files


def _resolved_streams(
    paths: Sequence[Path], venues: Mapping[str, Venue]
) -> tuple[dict[str, IncomeStream], dict[str, Path]]:
    """Declared income streams by id, each landing at a venue that can hold its currency."""
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
) -> None:
    """The list must belong to the owner whose streams it is resolved with (Principle VII).

    Checked against the *streams* rather than against a configured owner id, because the streams
    are the other per-owner declaration in the run and the report pairs the two on every line:
    every verdict is a `(destination x stream)`, and the spendable list is what decides half of
    it. A list belonging to somebody else would answer this owner's question with that owner's
    life.
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


def resolve_coverage(
    *,
    ramp: RampDeclarations,
    spendable_file: Path,
) -> CoverageDeclarations:
    """The ramp declarations plus a resolved spendable list, checked against them.

    Takes the resolved :class:`RampDeclarations` rather than the paths that produced them: the
    spendable list is checked against the *venues*, the *base currency* and the *streams*, all
    three of which are already resolved by then, and re-resolving them here would give a data
    root two chances to disagree with itself.
    """
    owner_id, endpoints = loader.spendable_from_file(spendable_file)
    _check_spendable_owner(owner_id, ramp.streams, path=spendable_file)
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
    )


def coverage_from_data_root(root: Path, *, base_currency: Currency) -> CoverageDeclarations:
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
    )
