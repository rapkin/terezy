"""Read one declaration file, validate it, and build the core records it declares.

The boundary. On one side, TOML text a person maintains by hand; on the other, frozen
core records that know nothing about files. Everything that can go wrong with a file goes
wrong **here**, as a :class:`~terezy.data.declarations.errors.DeclarationError` naming the
file and the field (FR-016), and nothing downstream has to defend itself against a
half-loaded declaration.

Four things this module is responsible for, in the order they happen:

1. **Read.** ``tomllib``, and a missing or unparseable file is an error naming it -- not
   an empty document. ``tomllib`` lives in ``data``; ``.importlinter`` forbids it in
   ``core``, which is the mechanical statement of research.md D1.
2. **Shape.** ``schema.py``'s pydantic models, with ``extra="forbid"``, ``strict=True``
   and no defaults. A ``ValidationError`` never escapes: :func:`_validate` adapts it,
   because pydantic's own rendering does not name the file at all, and the file is half of
   what FR-016 asks for.
3. **Meaning.** Convention names, currencies, instrument classes and taxable event kinds
   are resolved against the core's registries; dates are parsed; amounts are checked
   positive; citations are checked non-empty. Every failure names the file, the field, the
   offending value, and -- for a closed set -- the values that would have worked.
4. **Construct.** Core records, with provenance attached. This package is one of the two
   places entitled to construct ``Money`` directly (the other is ``money.py`` itself),
   because it is where declared values *enter* the system and where their citation is
   attached; see ``tests/contract/test_money_construction_guard.py``.

**Percent becomes a fraction exactly once, here.** Every ``_pct`` field passes through
:func:`_as_fraction` and nothing else divides by 100 anywhere in the project. Doing it
twice and not doing it at all are the two likeliest bugs in this layer, and both are
invisible in the output -- a 15.5% coupon reading as 0.155% still produces a plausible
schedule -- so the conversion is one named function with one caller per field and a
worked assertion in the contract tests.

**Provenance is per table.** Each sourced table becomes one ``SourceRef`` whose id names
the file and the table, so a figure traces back to *where it was declared* rather than
only to a citation string. Two tables in a file are two observations and get two refs:
merging them would let a verified minimum ticket vouch for an unverified yield.

**What this module deliberately does not check.** Anything requiring a second file, and
anything requiring instrument mathematics. Duplicate ids and tax-class references need
every file parsed first and live in :mod:`terezy.data.declarations.resolver`; a maturity
on or before its issue date is a well-formed declaration of an impossible instrument and
is the engine's typed ``InconsistentTerms``, not a load error.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ValidationError

from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments.interface import (
    BondTerms,
    InstrumentConstraints,
    InstrumentDeclaration,
)
from terezy.core.ledger import seeds
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import conventions
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.composed import SegmentBound
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.goal import Goal
from terezy.core.routes import capacity, legs
from terezy.core.routes.channels import ChannelSide, FxChannel, Side, effective_rate
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.regimes import Regime, RegimeTransition
from terezy.core.streams import streams
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.data.declarations import schema
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

_CURRENCY_PAIR_LENGTH: Final = 2
"""A quote is between exactly two currencies. Named so the check reads as the rule it is
rather than as a magic number."""

_PERCENT: Final = 100.0
"""The divisor. Named so the one place it is used is greppable and cannot be mistaken for
an unrelated hundred."""

INSTRUMENT_TABLE: Final = "instrument"
"""Root table of an instrument file, and the prefix of every field path in one."""

JURISDICTION_TABLE: Final = "jurisdiction"
"""Root table of a tax file."""


def _as_fraction(percent: float) -> float:
    """A declared percentage as the fraction the core works in: ``15.5`` -> ``0.155``.

    The **only** division by 100 in the project. Every ``_pct`` field goes through here
    and no other code performs the conversion, which is what makes "exactly once, at the
    boundary" a checkable claim rather than a convention.
    """
    return percent / _PERCENT


def source_id(path: Path, table: str) -> str:
    """The identity of one declared observation: which file, and which table in it.

    ``instruments/ovdp_synthetic_a.toml#instrument.terms``. The parent directory is
    included because ``instruments/ua.toml`` and ``tax/ua.toml`` are different facts, and
    the bare file name would collide. The *absolute* path is deliberately not used: it
    would embed a machine's directory layout in a source id, and two checkouts of the
    same commit would describe the same declaration differently.

    ``SourceRef`` equality is by value, so this id is also what makes two refs to the
    same table merge into one rather than accumulating duplicates in a provenance set.
    """
    return f"{path.parent.name}/{path.name}#{table}"


def read_document(path: Path) -> Mapping[str, Any]:
    """The parsed TOML of one file, or an error naming the file.

    A missing file is an error, not an empty document. Treating absence as emptiness is
    the silent default the constitution puts in its top severity class: a tax pack that
    failed to load would look exactly like a jurisdiction that charges nothing.
    """
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise DeclarationError(
            path,
            "",
            "there is no such file, so nothing was declared. An absent declaration file "
            "is reported rather than read as an empty one: an empty tax pack looks "
            "exactly like a jurisdiction that charges nothing.",
            "check the path, or add the file",
        ) from exc
    except OSError as exc:
        raise DeclarationError(
            path, "", f"could not be read: {exc}", "check the file's permissions"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise DeclarationError(
            path,
            "",
            f"is not valid TOML: {exc}",
            "a TOML syntax error; the message above gives the line",
        ) from exc


def _field_path(location: tuple[int | str, ...]) -> str:
    """A pydantic error location as the dotted path the file itself uses.

    List indices render as ``[0]`` so an array of tables reads the way
    ``scripts/check_provenance.py`` prints it -- ``jurisdiction.tax_class[0].pit_rate_pct``
    -- and a reader looking for the offending entry counts entries rather than guessing.
    """
    rendered = ""
    for part in location:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}" if rendered else part
    return rendered


_REMEDIES: Final[Mapping[str, str]] = {
    "missing": (
        "add the field. Nothing is substituted for it: a default would turn a forgotten "
        "line into a value the file does not contain"
    ),
    "extra_forbidden": (
        "remove the field, or correct its spelling. An unrecognised field is refused "
        "rather than ignored, because a field that is silently ignored is a declared "
        "constraint that does nothing"
    ),
}
"""Remedies for the two pydantic error kinds where the fix is knowable in general.

Everything else -- a wrong type, a malformed nested table -- gets ``None`` rather than a
guess, because the loader knows what was rejected and not what the author meant.
"""


def _problem(error: Mapping[str, Any]) -> str:
    """One pydantic error as a sentence naming the value it rejected."""
    if error["type"] == "missing":
        return (
            "is required and is absent. No default value is substituted for a missing "
            "field (FR-016)."
        )
    if error["type"] == "extra_forbidden":
        return f"is not a field this loader recognises (found {error.get('input')!r})."
    return (
        f"{error['msg']}; got {error.get('input')!r}. Values are read strictly: a quoted "
        "number is a string, and is not silently converted."
    )


def _validate[M: BaseModel](model: type[M], document: Mapping[str, Any], path: Path) -> M:
    """Validate a document against a model, adapting any failure into the project's error.

    **No ``pydantic.ValidationError`` crosses this line** (research.md D6). Two things are
    lost if one does: the file path, which pydantic never had, and the caller's ability to
    handle a declaration problem without importing pydantic.

    When a document has several problems the **first** becomes the error's ``field_path``,
    in the order pydantic reports them, which is field-definition order and therefore
    stable. The rest are listed in ``problem``: a reader fixing a file wants to see every
    line that needs editing, and a loader that reported one problem per run would make a
    file with five faults take five runs to fix. The single ``field_path`` is honest about
    only being able to point at one place.
    """
    try:
        return model.model_validate(document, strict=True)
    except ValidationError as exc:
        errors = exc.errors()
        first = errors[0]
        problem = f"{_field_path(tuple(first['loc']))} {_problem(first)}"
        if len(errors) > 1:
            problem += " Also in this file: " + "; ".join(
                f"{_field_path(tuple(other['loc']))} {_problem(other)}" for other in errors[1:]
            )
        raise DeclarationError(
            path,
            _field_path(tuple(first["loc"])),
            problem,
            _REMEDIES.get(str(first["type"])),
        ) from exc


def _require_text(path: Path, field_path: str, value: str, what: str) -> str:
    """A string field that may not be blank -- an id, a name, a citation."""
    if not value.strip():
        raise DeclarationError(
            path,
            field_path,
            f"is empty, and {what}. An empty string is not a missing key, which is why "
            "it is checked here rather than left to the shape validation.",
            f"write the {field_path.rsplit('.', maxsplit=1)[-1]}",
        )
    return value


def _parse_date(path: Path, field_path: str, text: str) -> date:
    """An ISO date, or an error quoting what was written instead."""
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise DeclarationError(
            path,
            field_path,
            f"is not an ISO date: {text!r} ({exc}).",
            "write it as YYYY-MM-DD, in quotes",
        ) from exc


def _parse_verification_date(path: Path, field_path: str, text: str) -> date | None:
    """``""`` means unverified; anything else must be an ISO date (FR-014).

    The empty string is the *declared* statement that this value has not been checked
    against a primary source. It is permitted and expected, and it is not the same as the
    key being absent -- which the shape validation refuses, because a forgotten key and a
    deliberate "not yet" must not look alike.
    """
    if text == "":
        return None
    return _parse_date(path, field_path, text)


def _positive(path: Path, field_path: str, value: float, why: str) -> float:
    """An amount that must be strictly positive. Never clamped, never defaulted."""
    if value <= 0.0:
        raise DeclarationError(
            path,
            field_path,
            f"is {value!r}, and {why}. The value is refused rather than corrected: "
            "clamping it would put a number in the model that no file declares.",
            "write a value greater than zero",
        )
    return value


def _non_negative(path: Path, field_path: str, value: float, why: str) -> float:
    """A rate that may be zero but not negative.

    Zero is a real declaration -- a zero-coupon bond, an exempt tax class -- and it is
    exactly why this is a separate check from :func:`_positive` rather than a looser
    version of it.
    """
    if value < 0.0:
        raise DeclarationError(
            path,
            field_path,
            f"is {value!r}, and {why}. Zero is a valid declaration here; a negative "
            "value is not, and it is refused rather than taken as zero.",
            "write zero or a positive value",
        )
    return value


def _known(path: Path, field_path: str, value: str, known: Mapping[str, Any], what: str) -> str:
    """A name that must be a key of one of the core's registries (FR-021).

    The two halves of FR-021 meet here: the core refuses to invent a convention (asserted
    by ``tests/contract/test_unknown_convention.py``) and this names the file it was
    declared in, which the core structurally cannot do. The remedy lists every name that
    would have worked, because an unrecognised convention is almost always a typo.
    """
    if value not in known:
        raise DeclarationError(
            path,
            field_path,
            f"declares {value!r}, which is not a {what} this engine implements. There is "
            "no fallback: applying a different convention than the one declared would "
            "produce a schedule that is wrong by a fraction of a percent -- large enough "
            "to change a decision, small enough to look plausible.",
            f"one of: {', '.join(sorted(known))}",
        )
    return value


def _currency(path: Path, field_path: str, value: str) -> Currency:
    """A declared currency code as the core's closed enum member."""
    for currency in Currency:
        if currency.value == value:
            return currency
    raise DeclarationError(
        path,
        field_path,
        f"declares {value!r}, which is not a currency this engine models. A currency is "
        "an enumeration rather than a free string, so that a typo is a load-time failure "
        "instead of a silently distinct currency that never matches anything.",
        f"one of: {', '.join(sorted(member.value for member in Currency))}",
    )


def _taxable_kind(path: Path, field_path: str, value: str) -> TaxableEventKind:
    """A declared income kind as the core's closed enum member."""
    for kind in TaxableEventKind:
        if kind.value == value:
            return kind
    raise DeclarationError(
        path,
        field_path,
        f"declares the income kind {value!r}, which this engine does not model. Tax "
        "treatment is declared per kind of income, so an unrecognised kind would leave "
        "some income with no declared treatment at all.",
        f"one of: {', '.join(sorted(kind.value for kind in TaxableEventKind))}",
    )


def _source_ref(
    path: Path,
    table: str,
    *,
    source: str,
    retrieved_on: str,
    verified_on: str,
    kind: str | None,
) -> SourceRef:
    """One table's citation, as the core's ``SourceRef``.

    The id names the file and the table (see :func:`source_id`), the citation is required
    non-empty, and an empty ``verified_on`` becomes ``None`` -- the unverified mark that
    FR-015 propagates through every figure derived from this table.

    ⚙ **``kind`` is checked here and carried nowhere**, for the tables whose core record has
    no field for it -- feature 001's ``BondTerms``, ``InstrumentConstraints`` and
    ``TaxClass``. The field is required in the file (FR-028: no sourced table ages under a
    threshold nobody named), and it is checked non-empty at the one place every citation
    passes through, so the check cannot be forgotten at a new call site. Resolution against
    ``data/observation_kinds.toml`` is ``scripts/check_provenance.py``'s, which reads the
    files rather than the records; see :class:`terezy.data.declarations.schema.BondTermsTable`
    for why a kind resolved into these records would be a value nothing reads.

    The parameter is **required and may be ``None``**, with no default, on the precedent
    ``DeclarationError.remedy`` sets: a default would make "no kind check" the thing that
    happens when nobody thought about it, which is the shape of mistake this project keeps
    finding. ``None`` is passed only where the table's kind is checked at the record field it
    becomes -- a leg's ``kind_of_observation``, a channel's ``kind`` -- because the error
    there can name the field the file actually uses.
    """
    if kind is not None:
        _require_text(
            path,
            f"{table}.kind",
            kind,
            "every table of observed values names the kind it ages under, and there is no "
            "default staleness threshold (FR-028): a value whose threshold nobody declared "
            "could never be reported stale",
        )
    return SourceRef(
        id=source_id(path, table),
        citation=_require_text(
            path,
            f"{table}.source",
            source,
            "a table carrying observed values must cite where they came from "
            "(constitution, Principle I). This holds for a rate of zero exactly as it "
            "does for a non-zero one",
        ),
        retrieved_on=_parse_date(path, f"{table}.retrieved_on", retrieved_on),
        verified_on=_parse_verification_date(path, f"{table}.verified_on", verified_on),
    )


def _bond_terms(
    path: Path,
    table: schema.BondTermsTable,
    currency: Currency,
    *,
    field_prefix: str,
) -> BondTerms:
    """``[instrument.terms]`` as ``BondTerms``: the one place percent becomes a fraction."""
    sources: Provenance = prov.of(
        [
            _source_ref(
                path,
                field_prefix,
                source=table.source,
                retrieved_on=table.retrieved_on,
                verified_on=table.verified_on,
                kind=table.kind,
            )
        ]
    )
    return BondTerms(
        face_value=Money(
            _positive(
                path,
                f"{field_prefix}.face_value",
                table.face_value,
                "a bond with no face value redeems nothing, and every coupon computed "
                "from it would be zero while the schedule still looked complete",
            ),
            currency,
            sources,
        ),
        coupon_rate=_as_fraction(
            _non_negative(
                path,
                f"{field_prefix}.coupon_rate_pct",
                table.coupon_rate_pct,
                "a negative coupon would have the holder paying the issuer, which this "
                "engine does not model",
            )
        ),
        issue_date=_parse_date(path, f"{field_prefix}.issue_date", table.issue_date),
        maturity_date=_parse_date(path, f"{field_prefix}.maturity_date", table.maturity_date),
        periodicity=_known(
            path,
            f"{field_prefix}.periodicity",
            table.periodicity,
            conventions.PERIODICITY_FNS,
            "coupon periodicity",
        ),
        day_count=_known(
            path,
            f"{field_prefix}.day_count",
            table.day_count,
            conventions.DAY_COUNT_FNS,
            "day-count convention",
        ),
        business_day_rule=_known(
            path,
            f"{field_prefix}.business_day_rule",
            table.business_day_rule,
            conventions.BUSINESS_DAY_FNS,
            "business-day rule",
        ),
        provenance=sources,
    )


def _constraints(
    path: Path,
    table: schema.ConstraintsTable,
    currency: Currency,
    *,
    field_prefix: str,
) -> InstrumentConstraints:
    """``[instrument.constraints]`` as ``InstrumentConstraints``, with its own citation."""
    sources: Provenance = prov.of(
        [
            _source_ref(
                path,
                field_prefix,
                source=table.source,
                retrieved_on=table.retrieved_on,
                verified_on=table.verified_on,
                kind=table.kind,
            )
        ]
    )
    return InstrumentConstraints(
        min_ticket=Money(
            _positive(
                path,
                f"{field_prefix}.min_ticket",
                table.min_ticket,
                "a minimum ticket of zero or less is not a constraint, and declaring one "
                "would make every purchase feasible by definition",
            ),
            currency,
            sources,
        ),
        min_unit=_positive(
            path,
            f"{field_prefix}.min_unit",
            table.min_unit,
            "the minimum unit is the divisor of the reinvestment remainder (FR-020), so "
            "zero or less is not a smaller increment but an arithmetic impossibility",
        ),
        provenance=sources,
    )


def _tax_class_references(
    path: Path,
    table: Mapping[str, str],
    *,
    field_prefix: str,
) -> Mapping[TaxableEventKind, str]:
    """``[instrument.tax_classes]`` as an enum-keyed mapping of class ids.

    References, not observations, so no citation -- the rates are cited where they are
    declared. Whether each id **resolves** is the resolver's job: it needs every tax file
    parsed first, and a reference that cannot be resolved is never read as an exemption.
    """
    if not table:
        raise DeclarationError(
            path,
            field_prefix,
            "declares no tax treatment for any kind of income. An instrument with no "
            "declared class is reported rather than projected untaxed: a missing rule "
            "and a cited exemption are opposite claims, and only one of them has a "
            "source.",
            'declare a class per income kind, for example coupon = "ua_government_bond"',
        )
    return {
        _taxable_kind(path, f"{field_prefix}.{kind}", kind): _require_text(
            path,
            f"{field_prefix}.{kind}",
            class_id,
            "an income kind must name the tax class that governs it",
        )
        for kind, class_id in table.items()
    }


def instrument_from_file(path: Path) -> InstrumentDeclaration:
    """One ``data/instruments/<id>.toml`` as an ``InstrumentDeclaration``.

    Everything the record needs comes from the file; nothing is inferred from the file
    *name*, so a renamed file is still the same declaration and a file whose name
    disagrees with its ``id`` is not silently reinterpreted.
    """
    document = read_document(path)
    table = _validate(schema.InstrumentFile, document, path).instrument
    currency = _currency(path, f"{INSTRUMENT_TABLE}.currency", table.currency)
    return InstrumentDeclaration(
        id=_require_text(
            path,
            f"{INSTRUMENT_TABLE}.id",
            table.id,
            "every declaration needs an identifier, because that is what a holding and a "
            "result refer to it by",
        ),
        name=_require_text(
            path,
            f"{INSTRUMENT_TABLE}.name",
            table.name,
            "a declaration a reader cannot recognise by name is one they cannot check",
        ),
        instrument_class=_known(
            path,
            f"{INSTRUMENT_TABLE}.class",
            table.instrument_class,
            instrument_registry.REGISTRY,
            "instrument class",
        ),
        currency=currency,
        is_synthetic=table.is_synthetic,
        terms=_bond_terms(path, table.terms, currency, field_prefix=f"{INSTRUMENT_TABLE}.terms"),
        constraints=_constraints(
            path, table.constraints, currency, field_prefix=f"{INSTRUMENT_TABLE}.constraints"
        ),
        tax_classes=_tax_class_references(
            path, table.tax_classes, field_prefix=f"{INSTRUMENT_TABLE}.tax_classes"
        ),
    )


def _tax_class(path: Path, entry: schema.TaxClassTable) -> TaxClass:
    """One ``[[jurisdiction.tax_class]]`` entry as a core ``TaxClass``.

    The field path names the entry by its **id** rather than its index --
    ``jurisdiction.tax_class[ua_government_bond].pit_rate_pct`` -- because the id is what
    a reader searches for and it does not change when the entries are reordered. The
    shape-validation errors from pydantic use the index, since a malformed entry may not
    have a usable id to name it by.
    """
    field_prefix = f"{JURISDICTION_TABLE}.tax_class[{entry.id}]"
    class_id = _require_text(
        path,
        f"{field_prefix}.id",
        entry.id,
        "a tax class is referred to by id from every instrument it governs",
    )
    _require_text(
        path,
        f"{field_prefix}.note",
        entry.note,
        "a tax class states in words what it claims, so a reader can check the citation "
        "against the claim (constitution, Documentation is part of the feature)",
    )
    if not entry.applies_to:
        raise DeclarationError(
            path,
            f"{field_prefix}.applies_to",
            "lists no income kinds, so the class governs nothing. A class that applies to "
            "nothing cannot be the reason any income is untaxed, and an empty list would "
            "make it look as though it were.",
            "list the income kinds this class governs",
        )
    sources = prov.of(
        [
            _source_ref(
                path,
                field_prefix,
                source=entry.source,
                retrieved_on=entry.retrieved_on,
                verified_on=entry.verified_on,
                kind=entry.kind,
            )
        ]
    )
    return TaxClass(
        id=class_id,
        applies_to=frozenset(
            _taxable_kind(path, f"{field_prefix}.applies_to", kind) for kind in entry.applies_to
        ),
        pit_rate=_as_fraction(
            _non_negative(
                path,
                f"{field_prefix}.pit_rate_pct",
                entry.pit_rate_pct,
                "a negative rate would be a refund rather than a charge, which is not "
                "what this rule models",
            )
        ),
        levy_rate=_as_fraction(
            _non_negative(
                path,
                f"{field_prefix}.levy_rate_pct",
                entry.levy_rate_pct,
                "a negative rate would be a refund rather than a charge, which is not "
                "what this rule models",
            )
        ),
        provenance=sources,
    )


def tax_classes_from_file(path: Path) -> tuple[TaxClass, ...]:
    """Every class declared in one ``data/tax/<jurisdiction>.toml``, in file order.

    File order is preserved rather than sorted: it is the order a reviewer reads the file
    in, and the resolver keys everything by id anyway, so nothing downstream depends on
    the sequence. What *would* be wrong is silently de-duplicating -- two entries with one
    id are reported, not collapsed.
    """
    document = read_document(path)
    jurisdiction = _validate(schema.TaxFile, document, path).jurisdiction
    _require_text(
        path,
        f"{JURISDICTION_TABLE}.id",
        jurisdiction.id,
        "a jurisdiction is referred to by id",
    )
    _require_text(
        path,
        f"{JURISDICTION_TABLE}.name",
        jurisdiction.name,
        "the name states which jurisdiction and which residence status the pack assumes",
    )
    _currency(path, f"{JURISDICTION_TABLE}.base_currency", jurisdiction.base_currency)
    if not jurisdiction.tax_class:
        raise DeclarationError(
            path,
            f"{JURISDICTION_TABLE}.tax_class",
            "declares no tax class. A jurisdiction file with no classes leaves every "
            "reference to it unresolved, and loading it quietly would defer that failure "
            "to whichever instrument happened to be projected first.",
            "declare at least one [[jurisdiction.tax_class]]",
        )
    return tuple(_tax_class(path, entry) for entry in jurisdiction.tax_class)


# ---------------------------------------------------------------------------
# 002-ramp-cost: observation kinds, venues, channels, routes, streams, scenarios
# ---------------------------------------------------------------------------
#
# Same four responsibilities as above, in the same order -- read, shape, meaning, construct
# -- and the same two rules that make this boundary worth having: **percent becomes a
# fraction exactly once, in** :func:`_as_fraction`, and **no pydantic type crosses this
# line**.
#
# What is *not* here, and could not be: everything needing a second file. A leg naming a
# venue, a channel or an observation kind is a reference, and whether it resolves depends on
# files this function has never opened; leg-to-leg continuity is checkable here but is
# checked beside the reference resolution so that one pass reports the whole shape of a
# broken declaration (research.md D6). Those live in
# :mod:`terezy.data.declarations.resolver`.
#
# ⚙ **Basis points are not percent.** ``markup_bps`` reaches the core *as basis points* and
# ``ChannelSide`` divides by 10 000 itself, in one place beside the channel that uses it.
# Passing a bps field through :func:`_as_fraction` would be the "twice" half of the
# divided-once bug, and it would look plausible: a 150 bps markup would read as 1.5 bps.

OBSERVATION_KIND_TABLE: Final = "kind"
"""Root array of ``data/observation_kinds.toml``, and the prefix of every field path in
one."""

VENUE_TABLE: Final = "venue"
"""Root array of ``data/venues.toml``."""

CHANNEL_TABLE: Final = "channel"
"""Root array of a channel file."""

ROUTE_TABLE: Final = "route"
"""Root table of a route file."""

STREAM_TABLE: Final = "stream"
"""Root array of a stream file."""

SCENARIO_TABLE: Final = "scenario"
"""Root table of a scenario file."""

_CADENCES: Final[Mapping[str, streams.Cadence]] = {
    "monthly": "monthly",
    "biweekly": "biweekly",
    "semimonthly": "semimonthly",
}
"""Declared cadence to the core's closed ``Cadence``.

A mapping from a name to *itself* rather than an ``if`` chain: the keys are what an error
message lists, and the values are what makes the result a ``Literal`` rather than a ``str``
-- so a cadence this engine does not model is a load-time failure naming the file, and a
misspelt one can never reach a record. Same shape as :data:`_INDEXATION_POLICIES`,
:data:`_DIRECTIONS` and :data:`_STATUSES` below, and the same reason.
"""

_INDEXATION_POLICIES: Final[Mapping[str, streams.IndexationPolicy]] = {
    "none": "none",
    "cpi": "cpi",
    "fixed_rate": "fixed_rate",
}
"""Declared indexation policy to the core's closed set."""

_DIRECTIONS: Final[Mapping[str, legs.RouteDirection]] = {
    "inbound": "inbound",
    "exit": "exit",
}
"""Declared route direction to the core's closed set. Declared, never inferred (FR-027)."""

_STATUSES: Final[Mapping[str, legs.RouteStatus]] = {
    "open": "open",
    "constrained": "constrained",
    "closed": "closed",
}
"""Declared route status to the core's closed set."""

_FALLBACK_POLICIES: Final[Mapping[str, capacity.FallbackPolicy]] = {
    policy: policy for policy in capacity.POLICIES
}
"""Declared fallback policy to the core's closed set, built from the core's own tuple.

Built from :data:`terezy.core.routes.capacity.POLICIES` rather than restated, so the data
layer cannot come to accept a policy the engine does not implement, or refuse one it does.
"""


@dataclass(frozen=True, slots=True)
class ScenarioDeclaration:
    """One ``data/scenarios/<id>.toml``: the owner's regimes, transitions and fallback.

    A data-layer aggregate rather than a core record, because the core takes the pieces
    separately: ``regimes.routes_in_force`` wants a mapping of regimes and a sequence of
    transitions, and ``capacity.deploy`` wants a policy. Nothing in the core needs the three
    of them in one object, and inventing a core type to hold them would be adding a record
    for the loader's convenience.

    It carries **no provenance**, and the absence is the design. A regime is a belief and a
    transition is a guess; ``is_assumption`` is what they carry where an observation carries
    a source and a verification date. Giving them a provenance field would invite a citation
    for a guess, which is the one thing Principle I forbids most firmly (research.md D8).
    """

    id: str
    """Unique across every scenario file."""

    owner_id: str
    """Whose beliefs these are. Principle VII, from the first commit."""

    regimes: tuple[Regime, ...]
    """The declared regimes, in file order. Keyed by id by the resolver, which is also
    where a duplicate across files is caught."""

    transitions: tuple[RegimeTransition, ...]
    """The declared transitions, in file order -- which the loader has already checked is
    strictly ascending and joined end to end."""

    fallback_policy: capacity.FallbackPolicy
    """What happens to a contribution the route will not carry (FR-013)."""

    redirect_to: str | None
    """Where the excess goes under ``redirect``, and ``None`` for every other policy. A
    ``redirect`` with no named destination is refused: FR-013 requires the target be
    named."""


def _bounded(path: Path, field_path: str, value: float, why: str) -> float:
    """A fraction that must lie in ``[0, 1]`` -- a probability, not a rate.

    Separate from :func:`_non_negative` because the upper bound is real: a disruption
    probability above one is not a very likely disruption, it is a number that is not a
    probability, and reporting it beside a cost would put a meaningless figure in front of
    the owner. Refused rather than clamped, on the same reasoning as everywhere else here.
    """
    if not 0.0 <= value <= 1.0:
        raise DeclarationError(
            path,
            field_path,
            f"is {value!r}, and {why}. It is refused rather than clamped into range: a "
            "clamped probability is a number no file declares.",
            "write a value between 0 and 1 inclusive",
        )
    return value


def _non_negative_days(path: Path, field_path: str, value: int, why: str) -> int:
    """A whole number of days that may be zero but not negative.

    Zero is a real declaration -- an instant transfer, a same-day threshold -- which is why
    this is the day-count sibling of :func:`_non_negative` rather than a use of
    :func:`_positive`.
    """
    if value < 0:
        raise DeclarationError(
            path,
            field_path,
            f"is {value!r}, and {why}. Zero is a valid declaration here; a negative number "
            "of days is not, and it is refused rather than read as zero.",
            "write zero or a positive whole number of days",
        )
    return value


def _optional_money(
    path: Path,
    field_path: str,
    value: float | None,
    *,
    currency: Currency,
    sources: Provenance,
    why: str,
) -> Money | None:
    """A limit that may be absent, as ``Money`` or ``None``.

    ``None`` here means **the file declares no such limit**, which is why the field is
    allowed to be absent at all -- the core's ``Leg.minimum`` and ``Leg.monthly_cap`` are
    ``Money | None`` for exactly that reason. It is not a default standing in for a number:
    there is no number, and every consumer of these fields branches on the absence rather
    than treating it as zero (which would make every amount below a minimum, and every cap
    binding at nothing).
    """
    if value is None:
        return None
    return Money(_positive(path, field_path, value, why), currency, sources)


def _optional_date(path: Path, field_path: str, text: str | None) -> date | None:
    """An availability window bound, or ``None`` for "always".

    Distinct from :func:`_parse_verification_date`: there the empty *string* is the declared
    statement "not verified", because the key must be present. Here the key may be absent,
    and its absence is the declaration -- a leg with no window works on every date, which is
    a claim a reader can check against the source beside it.
    """
    if text is None:
        return None
    return _parse_date(path, field_path, text)


def observation_kinds_from_file(path: Path) -> tuple[ObservationKind, ...]:
    """Every kind declared in ``data/observation_kinds.toml``, in file order.

    No citation is read, and none is expected: a staleness threshold is the owner's policy
    about how long he will trust a number of this kind, not an observation of the world.
    What *is* enforced is that the threshold exists and is positive, because FR-028's whole
    content is that there is no permissive default -- a kind with no threshold, or one of
    zero days, would make every value of that kind either permanently fresh or permanently
    stale, and both are warnings that get ignored.
    """
    document = read_document(path)
    declared = _validate(schema.ObservationKindsFile, document, path).kind
    if not declared:
        raise DeclarationError(
            path,
            OBSERVATION_KIND_TABLE,
            "declares no observation kinds. An empty kinds file is reported rather than "
            "read as 'nothing ages': every sourced table in the project names a kind, so "
            "every one of them would fail to resolve for a reason naming the wrong file.",
            "declare at least one [[kind]]",
        )
    return tuple(
        ObservationKind(
            id=_require_text(
                path,
                f"{OBSERVATION_KIND_TABLE}[{entry.id}].id",
                entry.id,
                "a kind is referred to by id from every sourced table that ages under it",
            ),
            staleness_days=int(
                _positive(
                    path,
                    f"{OBSERVATION_KIND_TABLE}[{entry.id}].staleness_days",
                    float(entry.staleness_days),
                    "a threshold of zero days or fewer makes every value of this kind stale "
                    "the moment it is read, which is a warning that gets ignored rather than "
                    "a policy",
                )
            ),
            note=_require_text(
                path,
                f"{OBSERVATION_KIND_TABLE}[{entry.id}].note",
                entry.note,
                "a threshold nobody explained is a number nobody can argue with; the note is "
                "where the reason is stated in words",
            ),
        )
        for entry in declared
    )


def venues_from_file(path: Path) -> tuple[Venue, ...]:
    """Every venue declared in ``data/venues.toml``, in file order.

    A venue table carries no observed numeric value -- an id, a name and a set of currency
    codes -- so no citation is read, and :class:`~terezy.core.routes.venues.Venue` has no
    provenance field to carry one. Every *number* attached to a venue lives on a leg, in
    ``data/routes/``, with its own source.

    The currency set is required non-empty. A venue that can hold nothing is a place money
    cannot sit, and every leg touching it would fail the can-hold check for a reason that
    names the leg rather than the venue that is actually wrong.
    """
    document = read_document(path)
    declared = _validate(schema.VenuesFile, document, path).venue
    if not declared:
        raise DeclarationError(
            path,
            VENUE_TABLE,
            "declares no venues. An empty venue file is reported rather than read as "
            "'money cannot sit anywhere': every route endpoint and every stream arrival "
            "would fail to resolve, each naming its own file instead of this one.",
            "declare at least one [[venue]]",
        )
    return tuple(
        Venue(
            id=_require_text(
                path,
                f"{VENUE_TABLE}[{entry.id}].id",
                entry.id,
                "a venue is referred to by id from every leg and every stream that touches it",
            ),
            name=_require_text(
                path,
                f"{VENUE_TABLE}[{entry.id}].name",
                entry.name,
                "a venue a reader cannot recognise by name is one they cannot check",
            ),
            currencies=frozenset(
                _currency(path, f"{VENUE_TABLE}[{entry.id}].currencies", code)
                for code in _non_empty_list(
                    path,
                    f"{VENUE_TABLE}[{entry.id}].currencies",
                    entry.currencies,
                    "a venue that can hold no currency is a place money cannot sit, and "
                    "every leg touching it would be refused for a reason naming the leg "
                    "rather than the venue",
                )
            ),
        )
        for entry in declared
    )


def _non_empty_list[T](path: Path, field_path: str, values: list[T], why: str) -> list[T]:
    """A declared list that may not be empty, checked where the field can be named.

    Generic because the three callers -- a venue's currencies, a regime's routes, a
    scenario's transitions -- fail for the same reason in three different files, and one
    message shape keeps them saying it the same way.
    """
    if not values:
        raise DeclarationError(
            path,
            field_path,
            f"is an empty list, and {why}.",
            "list at least one entry",
        )
    return values


def _channel_side(
    path: Path,
    table: schema.ChannelSideTable,
    *,
    field_prefix: str,
    price_currency: Currency,
) -> tuple[ChannelSide, SourceRef]:
    """One side of a channel quote, and the citation it rests on.

    **Exactly one of the two forms**, checked here where the file and the field can be
    named (FR-010). Both set is refused because there is no precedence rule that does not
    silently ignore one of the two numbers the owner wrote; neither set is refused because
    an empty side is not a zero -- "at the reference" is declarable as ``0.0``, so an
    absence can only mean an unfinished declaration, and reading an unfinished declaration
    as free would make the cheapest route the one nobody described.

    The premium is built as ``Money`` in the **price** currency, which is what a premium per
    unit is denominated in: ``+3`` on a ``["UAH", "USD"]`` channel is three hryvnia per
    dollar. It is deliberately **not** put through :func:`_positive` or
    :func:`_non_negative` -- zero means at the reference and negative means below it, and
    both are real declarations.

    Basis points pass through untouched: ``ChannelSide`` divides by 10 000 itself, so
    sending this field through :func:`_as_fraction` would be the "divided twice" bug in its
    most plausible disguise.
    """
    ref = _source_ref(
        path,
        field_prefix,
        source=table.source,
        retrieved_on=table.retrieved_on,
        verified_on=table.verified_on,
        # Checked below, at ``ChannelSide.kind``, where the message names the field the
        # file actually uses. A side is its own observation, and its kind is carried into
        # the record so the staleness verdict ages the side under it (FR-028) -- not
        # validated here and dropped, which would leave the side ageing under the
        # channel's kind.
        kind=None,
    )
    sources = prov.of([ref])
    kind = _require_text(
        path,
        f"{field_prefix}.kind",
        table.kind,
        "every table of observed values names the kind it ages under, and there is no "
        "default staleness threshold (FR-028): a side aged under the channel's kind would "
        "be reported fresh long after its own threshold had passed",
    )
    if table.markup_bps is not None and table.premium_per_unit is not None:
        raise DeclarationError(
            path,
            f"{field_prefix}.markup_bps",
            f"declares both markup_bps={table.markup_bps!r} and "
            f"premium_per_unit={table.premium_per_unit!r}. A side is declared in exactly "
            "one of the two forms; there is no precedence rule, because 'the markup wins' "
            "would silently ignore one of the two numbers written in this file (FR-010).",
            "delete whichever of the two lines does not describe this side",
        )
    if table.markup_bps is not None:
        return (
            ChannelSide(
                markup_bps=_non_negative(
                    path,
                    f"{field_prefix}.markup_bps",
                    table.markup_bps,
                    "a markup is a cost magnitude and a negative one would be a rebate this "
                    "engine does not model; a channel that trades below the reference is "
                    "declared as a negative premium_per_unit instead, where the sign has a "
                    "meaning",
                ),
                premium_per_unit=None,
                kind=kind,
                provenance=sources,
            ),
            ref,
        )
    if table.premium_per_unit is not None:
        return (
            ChannelSide(
                markup_bps=None,
                premium_per_unit=Money(table.premium_per_unit, price_currency, sources),
                kind=kind,
                provenance=sources,
            ),
            ref,
        )
    raise DeclarationError(
        path,
        field_prefix,
        "declares neither markup_bps nor premium_per_unit. An empty side is not a zero: "
        "'at the reference' is declared as premium_per_unit = 0.0, so an absence can only "
        "mean an unfinished declaration -- and reading an unfinished declaration as free "
        "would make the cheapest route the one nobody described (FR-010).",
        "declare exactly one of markup_bps or premium_per_unit",
    )


def _check_effective(
    path: Path,
    side_prefix: str,
    side: ChannelSide,
    reference: float,
    *,
    role: Side,
) -> None:
    """A declared side must still be a rate on its own declared reference (FR-010).

    The effective rate is what a conversion transacts at, and the costing arithmetic
    divides by it on the buy side and converts through it on both. A side whose offset
    gives away the whole reference -- ``premium_per_unit = -42`` against a reference of
    42, or ``markup_bps >= 10000`` on the sell side -- makes it zero or negative, and
    without this check the file loads and the first costing dies mid-walk in arithmetic
    that can name neither the file nor the field.

    The bound is on the **effective rate per role**, not on the declared number: a
    negative premium is legal while the effective rate stays positive (a discount is a
    real market fact), and a buy-side markup of any size is expensive rather than
    impossible. Checked here rather than in ``core``, because the reference and the side
    are declared in one table and the refusal can name both values.
    """
    effective = effective_rate(side, reference, role=role)
    if effective <= 0.0:
        field, declared = (
            ("premium_per_unit", side.premium_per_unit.amount)
            if side.premium_per_unit is not None
            else ("markup_bps", side.markup_bps)
        )
        raise DeclarationError(
            path,
            f"{side_prefix}.{field}",
            f"declares {field} = {declared!r} against reference_rate = {reference!r}, "
            f"which makes this side's effective rate {effective!r}. A side that pays away "
            "the whole reference or more is not a rate: a conversion divides by this "
            "number, so the declaration would load and then fail mid-costing in "
            "arithmetic that names neither the file nor the field. A discount is legal "
            "only while the effective rate stays positive (FR-010).",
            "declare an offset that leaves the effective rate above zero",
        )


def channels_from_file(path: Path) -> tuple[FxChannel, ...]:
    """Every channel declared in one ``data/channels/<pair>.toml``, in file order.

    **Both sides required, neither derived from the other** (FR-010). A single mid-rate is
    never used for a transaction, and a system computing the sell side from the buy side
    would be using a mid-rate with extra steps -- so the shape validation requires both
    sub-tables and this function reads each independently.

    **The channel's provenance is the union of three citations**: the reference rate's and
    both sides'. Each is its own observation, read off its own line, so each carries its own
    ``SourceRef``; unioning them is what makes ``core.routes.legs`` able to attach the whole
    mark to a converted figure through ``money.scale_sourced``, since it applies a spread
    through ``channel.provenance``. Attaching only the reference rate's ref would silently
    drop the mark on the number that actually costs the money, which is the top-severity
    defect class.
    """
    document = read_document(path)
    declared = _validate(schema.ChannelFile, document, path).channel
    if not declared:
        raise DeclarationError(
            path,
            CHANNEL_TABLE,
            "declares no channels. An empty channel file is reported rather than read as "
            "'this pair cannot be converted': every fx leg naming a channel would fail to "
            "resolve, each naming its own route file instead of this one.",
            "declare at least one [[channel]]",
        )
    return tuple(_channel(path, entry) for entry in declared)


def _channel(path: Path, entry: schema.ChannelTable) -> FxChannel:
    """One ``[[channel]]`` entry as an :class:`~terezy.core.routes.channels.FxChannel`.

    The field path names the entry by its **id** rather than its index, on the tax-class
    precedent: the id is what a reader searches for, and it does not change when entries are
    reordered.
    """
    field_prefix = f"{CHANNEL_TABLE}[{entry.id}]"
    channel_id = _require_text(
        path,
        f"{field_prefix}.id",
        entry.id,
        "a channel is referred to by id from every fx leg that converts through it, and the "
        "id is what appears in a cost's channels_applied (FR-011)",
    )
    pair = _non_empty_list(
        path,
        f"{field_prefix}.pair",
        entry.pair,
        "a channel quotes one ordered currency pair and cannot quote none",
    )
    if len(pair) != _CURRENCY_PAIR_LENGTH:
        raise DeclarationError(
            path,
            f"{field_prefix}.pair",
            f"declares {len(pair)} currencies {pair!r}. A quote is between exactly two: the "
            "price currency and the unit currency, in that order, because the order is what "
            "decides whether a leg is buying or selling -- and reversing it would invert "
            "every spread in the system while leaving every number plausible.",
            'write it as ["UAH", "USD"], meaning UAH per USD',
        )
    price_currency = _currency(path, f"{field_prefix}.pair", pair[0])
    unit_currency = _currency(path, f"{field_prefix}.pair", pair[1])
    if price_currency is unit_currency:
        raise DeclarationError(
            path,
            f"{field_prefix}.pair",
            f"quotes {price_currency.value} against itself. A channel converts between two "
            "different currencies; a self-quote has no side to take and no spread to cost.",
            "name two different currencies",
        )
    reference = _positive(
        path,
        f"{field_prefix}.reference_rate",
        entry.reference_rate,
        "a reference of zero or less is not a rate: a cost fraction divides by it and "
        "an attribution translates through it, so either would produce a figure that "
        "merely looks like a number",
    )
    buy_side, buy_ref = _channel_side(
        path,
        entry.buy_side,
        field_prefix=f"{field_prefix}.buy_side",
        price_currency=price_currency,
    )
    sell_side, sell_ref = _channel_side(
        path,
        entry.sell_side,
        field_prefix=f"{field_prefix}.sell_side",
        price_currency=price_currency,
    )
    _check_effective(path, f"{field_prefix}.buy_side", buy_side, reference, role=Side.BUY)
    _check_effective(path, f"{field_prefix}.sell_side", sell_side, reference, role=Side.SELL)
    reference_ref = _source_ref(
        path,
        field_prefix,
        source=entry.source,
        retrieved_on=entry.retrieved_on,
        verified_on=entry.verified_on,
        # Checked below, at ``FxChannel.kind``, where the message names ``channel[id].kind``.
        kind=None,
    )
    return FxChannel(
        id=channel_id,
        pair=(price_currency, unit_currency),
        reference_rate=reference,
        buy_side=buy_side,
        sell_side=sell_side,
        observed_on=_parse_date(path, f"{field_prefix}.observed_on", entry.observed_on),
        kind=_require_text(
            path,
            f"{field_prefix}.kind",
            entry.kind,
            "every observed value names the kind it ages under, and there is no default "
            "threshold (FR-028)",
        ),
        provenance=prov.of([reference_ref, buy_ref, sell_ref]),
    )


def _leg(path: Path, table: schema.LegTable, *, position: int) -> Leg:
    """One ``[[route.leg]]`` entry as a :class:`~terezy.core.routes.legs.Leg`.

    Three checks live here rather than in the resolver, because all three are properties of
    one leg read in isolation:

    * **The declared index matches the position.** A leg declaring index 3 in position 0
      would make every message about it point at the wrong lines, including the chaining
      errors the resolver raises by index.
    * **A channel exactly when the kind converts** (FR-011). A ``transfer`` naming a channel
      is a declaration that means nothing, and accepting it would let a reader believe a
      conversion happened; an ``fx`` leg with no channel is a mid-rate transaction, which
      FR-010 forbids outright.
    * **A cap needs a rail.** A ``monthly_cap`` with no ``capacity_pool`` has no key to
      accumulate under, so capacity consumed earlier in the month could never reduce it --
      and a limit that is never consumed is not a limit (research.md D10).

    Whether the *named* channel, venues and kind exist is the resolver's, and so is
    continuity with the neighbouring legs.
    """
    field_prefix = f"{ROUTE_TABLE}.leg[{position}]"
    if table.index != position:
        raise DeclarationError(
            path,
            f"{field_prefix}.index",
            f"declares index {table.index!r} but is the leg in position {position}. The "
            "index is not renumbered to match: every load-time and run-time message about "
            "this leg names it by the declared index, so a disagreement would point a "
            "reader at the wrong lines.",
            f"write index = {position}, or move the leg to position {table.index}",
        )
    kind = _known(path, f"{field_prefix}.kind", table.kind, legs.LEG_COST_FNS, "leg kind")
    from_ccy = _currency(path, f"{field_prefix}.from_ccy", table.from_ccy)
    to_ccy = _currency(path, f"{field_prefix}.to_ccy", table.to_ccy)
    converts = kind == legs.FX
    if converts and table.channel is None:
        raise DeclarationError(
            path,
            f"{field_prefix}.channel",
            f"is absent on a leg of kind {legs.FX!r}. A conversion with no declared "
            "two-sided quote is a mid-rate transaction, which FR-010 forbids outright -- "
            "and there is no default channel, because substituting one would reprice the "
            "leg at a rate nobody declared.",
            "name the channel this conversion goes through",
        )
    if not converts and table.channel is not None:
        raise DeclarationError(
            path,
            f"{field_prefix}.channel",
            f"names channel {table.channel!r} on a leg of kind {kind!r}, which converts "
            f"nothing. Only an {legs.FX!r} leg converts, so the channel is refused rather "
            "than ignored: an ignored channel is a declaration that lets a reader believe a "
            "conversion happened (FR-011).",
            f"delete the channel, or declare the leg as kind = {legs.FX!r}",
        )
    if not converts and from_ccy is not to_ccy:
        raise DeclarationError(
            path,
            f"{field_prefix}.to_ccy",
            f"moves {from_ccy.value} to {to_ccy.value} on a leg of kind {kind!r}, which "
            f"converts nothing. Only an {legs.FX!r} leg changes currency; the only way to "
            "satisfy this declaration would be to invent a rate.",
            f"declare the leg as kind = {legs.FX!r} with a channel, or make the currencies match",
        )
    if converts and from_ccy is to_ccy:
        raise DeclarationError(
            path,
            f"{field_prefix}.to_ccy",
            f"declares a conversion from {from_ccy.value} to itself. A channel quotes an "
            "ordered pair of two different currencies, so there is no side of it to take "
            "here, and the leg would charge a spread for a conversion that did not happen.",
            "make the currencies differ, or declare the leg as a transfer",
        )
    if table.monthly_cap is not None and table.capacity_pool is None:
        raise DeclarationError(
            path,
            f"{field_prefix}.capacity_pool",
            f"is absent on a leg declaring monthly_cap = {table.monthly_cap!r}. A monthly "
            "limit belongs to a rail -- a card, an account, a corridor under a regulatory "
            "ceiling -- and without a rail there is no key to accumulate consumption "
            "under, so capacity already used in the same month could never reduce it "
            "(FR-015). A limit that is never consumed is not a limit.",
            "name the pool, even where only this leg uses it: a pool is a fact about the "
            "world and is declared rather than inferred (research.md D10)",
        )
    if table.capacity_pool is not None and table.monthly_cap is None:
        raise DeclarationError(
            path,
            f"{field_prefix}.monthly_cap",
            f"is absent on a leg naming capacity_pool {table.capacity_pool!r}. A rail with "
            "no declared limit consumes nothing and constrains nothing, so the pool would "
            "be a name in a file that no figure ever reads.",
            "declare the rail's monthly cap, or delete the capacity_pool",
        )
    ref = _source_ref(
        path,
        field_prefix,
        source=table.source,
        retrieved_on=table.retrieved_on,
        verified_on=table.verified_on,
        # Checked below, at ``Leg.kind_of_observation``: a leg's ``kind`` is the *leg* kind,
        # so the message has to name the field the file actually uses.
        kind=None,
    )
    sources = prov.of([ref])
    return Leg(
        index=position,
        kind=kind,
        from_venue=_require_text(
            path,
            f"{field_prefix}.from_venue",
            table.from_venue,
            "a leg starts at a named venue, so that 'this leg moves dollars into a "
            "hryvnia-only account' is a question something can answer",
        ),
        to_venue=_require_text(
            path,
            f"{field_prefix}.to_venue",
            table.to_venue,
            "a leg ends at a named venue",
        ),
        from_ccy=from_ccy,
        to_ccy=to_ccy,
        channel=table.channel,
        fee_pct=_as_fraction(
            _non_negative(
                path,
                f"{field_prefix}.fee_pct",
                table.fee_pct,
                "a negative percentage fee would have the venue paying the owner to move "
                "money, which this engine does not model",
            )
        ),
        fee_fixed=Money(
            _non_negative(
                path,
                f"{field_prefix}.fee_fixed",
                table.fee_fixed,
                "a negative flat fee would be a rebate this engine does not model; zero is "
                "a real declaration and is what a free leg says",
            ),
            from_ccy,
            sources,
        ),
        minimum=_optional_money(
            path,
            f"{field_prefix}.minimum",
            table.minimum,
            currency=from_ccy,
            sources=sources,
            why="a minimum of zero or less is not a constraint, and declaring one would make "
            "every amount feasible by definition",
        ),
        maximum=_optional_money(
            path,
            f"{field_prefix}.maximum",
            table.maximum,
            currency=from_ccy,
            sources=sources,
            why="a maximum of zero or less would make every amount refused, which is a closed "
            "leg rather than a limit -- a leg that does not work is declared with a status "
            "or a window",
        ),
        monthly_cap=_optional_money(
            path,
            f"{field_prefix}.monthly_cap",
            table.monthly_cap,
            currency=from_ccy,
            sources=sources,
            why="a cap of zero or less carries nothing in a month, which is a closed rail "
            "rather than a limited one",
        ),
        capacity_pool=table.capacity_pool,
        latency_days=_non_negative_days(
            path,
            f"{field_prefix}.latency_days",
            table.latency_days,
            "a leg cannot take a negative number of days; a same-day leg declares zero",
        ),
        available_from=_optional_date(path, f"{field_prefix}.available_from", table.available_from),
        available_until=_optional_date(
            path, f"{field_prefix}.available_until", table.available_until
        ),
        disruption_probability=_bounded(
            path,
            f"{field_prefix}.disruption_probability",
            table.disruption_probability,
            "a disruption probability outside [0, 1] is not a probability (FR-026), and it "
            "is reported beside the cost where the owner would read it as one",
        ),
        kind_of_observation=_require_text(
            path,
            f"{field_prefix}.kind_of_observation",
            table.kind_of_observation,
            "every table of observed values names the kind it ages under, and there is no "
            "default threshold (FR-028)",
        ),
        provenance=sources,
    )


def route_from_file(path: Path) -> Route:
    """One ``data/routes/<id>.toml`` as a :class:`~terezy.core.routes.legs.Route`.

    Nothing is inferred from the file *name*, on the instrument precedent: a renamed file is
    still the same declaration, and a file whose name disagrees with its ``id`` is not
    silently reinterpreted.

    **A route with no legs is refused, never costed as free.** Free is the answer a reader
    would least question and the one most likely to be wrong.

    **``partner_route`` is refused on an ``exit`` route.** A pairing is declared once, by
    the inbound side (FR-027); allowing both halves to name each other would let the two
    declarations disagree, and nothing in the model says which of them wins. Whether the
    named partner *exists*, is an exit, starts where this route ends and finishes in the
    base currency are cross-file questions and belong to the resolver.
    """
    document = read_document(path)
    table = _validate(schema.RouteFile, document, path).route
    if not table.leg:
        raise DeclarationError(
            path,
            f"{ROUTE_TABLE}.leg",
            "declares no legs. A route with no movements is refused rather than costed as "
            "free: zero is the figure a reader would question least and the one most likely "
            "to be wrong, and a route that moves nothing cannot deliver an amount either.",
            "declare at least one [[route.leg]]",
        )
    direction = _DIRECTIONS[
        _known(path, f"{ROUTE_TABLE}.direction", table.direction, _DIRECTIONS, "route direction")
    ]
    if direction == "exit" and table.partner_route is not None:
        raise DeclarationError(
            path,
            f"{ROUTE_TABLE}.partner_route",
            f"names {table.partner_route!r} on a route whose direction is {direction!r}. A "
            "pairing is declared once, by the inbound route (FR-027): if both halves named "
            "each other the two declarations could disagree, and nothing in the model says "
            "which one wins.",
            "delete the partner_route here, and declare it on the inbound route instead",
        )
    return Route(
        id=_require_text(
            path,
            f"{ROUTE_TABLE}.id",
            table.id,
            "a route is referred to by id from every funding path and every regime that "
            "includes it",
        ),
        provider=_require_text(
            path,
            f"{ROUTE_TABLE}.provider",
            table.provider,
            "registry identity is (provider x currency path x venue), so a route with no "
            "named provider cannot be distinguished from another way of doing the same "
            "thing (FR-023)",
        ),
        origin=_require_text(
            path,
            f"{ROUTE_TABLE}.origin",
            table.origin,
            "a route starts at a named venue, which is what a stream's arrival venue is "
            "checked against",
        ),
        destination=_require_text(
            path,
            f"{ROUTE_TABLE}.destination",
            table.destination,
            "a route ends at a named venue, which is what a funding path's destination is",
        ),
        direction=direction,
        partner_route=table.partner_route,
        status=_STATUSES[
            _known(path, f"{ROUTE_TABLE}.status", table.status, _STATUSES, "route status")
        ],
        legs=tuple(
            _leg(path, entry, position=position) for position, entry in enumerate(table.leg)
        ),
    )


def _indexation(path: Path, table: schema.IndexationTable, *, field_prefix: str) -> Indexation:
    """``[stream.indexation]`` as :class:`~terezy.core.streams.streams.Indexation`.

    A ``fixed_rate`` policy with no rate is refused: it is a declaration that means nothing,
    and the two readings available to an engine -- treat it as zero, or treat it as ``cpi``
    -- are both substituted defaults for a growth assumption the owner stated only half of.
    A rate declared *with* ``none`` is refused for the mirror-image reason: a number nothing
    will ever apply is a line a reader would expect to see in a figure.
    """
    policy = _INDEXATION_POLICIES[
        _known(
            path, f"{field_prefix}.policy", table.policy, _INDEXATION_POLICIES, "indexation policy"
        )
    ]
    if policy == "fixed_rate" and table.rate_pct is None:
        raise DeclarationError(
            path,
            f"{field_prefix}.rate_pct",
            "is absent on an indexation policy of 'fixed_rate', which is a declaration "
            "that means nothing. Reading it as zero would state that the amount never "
            "grows, and falling back to 'cpi' would substitute a different policy: both "
            "are the owner's assumption invented for him.",
            "declare the annual rate as a percentage, or change the policy to 'none' or 'cpi'",
        )
    if policy != "fixed_rate" and table.rate_pct is not None:
        raise DeclarationError(
            path,
            f"{field_prefix}.rate_pct",
            f"declares {table.rate_pct!r} under an indexation policy of {policy!r}, which "
            "takes no rate. It is refused rather than ignored: a rate nothing will ever "
            "apply is a line a reader would reasonably expect to see in a figure.",
            "delete the rate, or declare policy = 'fixed_rate'",
        )
    return Indexation(
        policy=policy,
        rate=(
            None
            if table.rate_pct is None
            else _as_fraction(
                _non_negative(
                    path,
                    f"{field_prefix}.rate_pct",
                    table.rate_pct,
                    "a negative indexation rate is a decline rather than an indexation, and "
                    "this feature applies neither",
                )
            )
        ),
    )


def streams_from_file(path: Path) -> tuple[IncomeStream, ...]:
    """Every stream declared in one ``data/streams/<owner>.toml``, in file order.

    **No citation is read, and that is the exemption argued in the contract**: an owner's
    own salary is not an observation needing a source, it is a statement of fact by the only
    person who can make it. The same exemption ``data/scenarios/`` has, and the reason
    ``check_provenance.py`` gains ``channels`` and not ``streams``.

    The declared ``currency`` and ``amount`` become **one** ``Money``: ``IncomeStream`` has
    no currency field, because two fields stating one fact can disagree and a record with
    ``currency = UAH`` and an amount in dollars would typecheck while being nonsense.

    An omitted ``income_tax_rate_pct`` becomes ``None``, which means *the owner has not
    stated a rate* -- a different claim from stating zero, and the reason ``deployable``
    returns a record with no net field at all rather than a net figure that quietly equals
    the gross (FR-007).
    """
    document = read_document(path)
    declared = _validate(schema.StreamFile, document, path).stream
    if not declared:
        raise DeclarationError(
            path,
            STREAM_TABLE,
            "declares no income streams. An empty stream file is reported rather than read "
            "as 'no money arrives': access cost is keyed per (destination x stream x "
            "route), so every funding path would fail to resolve its stream.",
            "declare at least one [[stream]]",
        )
    return tuple(_stream(path, entry) for entry in declared)


def _stream(path: Path, entry: schema.StreamTable) -> IncomeStream:
    """One ``[[stream]]`` entry as an :class:`~terezy.core.streams.streams.IncomeStream`."""
    field_prefix = f"{STREAM_TABLE}[{entry.id}]"
    currency = _currency(path, f"{field_prefix}.currency", entry.currency)
    return IncomeStream(
        id=_require_text(
            path,
            f"{field_prefix}.id",
            entry.id,
            "a stream is referred to by id from every funding path funded out of it, and "
            "the stream is the term that carries the whole per-stream finding (FR-008)",
        ),
        owner_id=_require_text(
            path,
            f"{field_prefix}.owner_id",
            entry.owner_id,
            "every per-owner row carries its owner from the first commit (Principle VII); "
            "retrofitting tenancy is the expensive mistake",
        ),
        amount=Money(
            _non_negative(
                path,
                f"{field_prefix}.amount",
                entry.amount,
                "a negative arrival is not income. Zero is a real declaration and is the "
                "honest placeholder for a figure the owner has not stated (§11 item 3): it "
                "produces a zero result rather than a made-up one",
            ),
            currency,
            prov.EMPTY,
        ),
        cadence=_CADENCES[
            _known(path, f"{field_prefix}.cadence", entry.cadence, _CADENCES, "income cadence")
        ],
        arrives_at=_require_text(
            path,
            f"{field_prefix}.arrives_at",
            entry.arrives_at,
            "a stream lands at a named venue, and a route whose origin differs from it is a "
            "mismatch that is reported rather than assumed away",
        ),
        indexation=_indexation(path, entry.indexation, field_prefix=f"{field_prefix}.indexation"),
        income_tax_rate=(
            None
            if entry.income_tax_rate_pct is None
            else _as_fraction(
                _non_negative(
                    path,
                    f"{field_prefix}.income_tax_rate_pct",
                    entry.income_tax_rate_pct,
                    "a negative income-tax rate would be a payment to the owner rather than "
                    "a withholding. Zero is a real declaration -- it says nothing is "
                    "withheld -- and is why omitting the field means something different",
                )
            )
        ),
    )


def scenario_from_file(path: Path) -> ScenarioDeclaration:
    """One ``data/scenarios/<id>.toml`` as a :class:`ScenarioDeclaration`.

    **Exempt from the citation requirement, and it carries something else instead.** A
    regime is a belief about which corridors exist and a transition is a guess about a date;
    ``is_assumption`` is what they carry where an observation carries a source and a
    verification date (research.md D8). Never present anything from here as though it were
    observed.

    Four properties are checked here because they are properties of this one file:
    duplicate regime ids, an ``is_assumption`` that is not ``true``, transitions that are
    not strictly ascending, and a chain that does not join up. The core refuses the last two
    as well -- and *raises* when it sees them, because by then the caller bypassed this
    check -- so checking here is what turns a raise mid-comparison into a message naming
    this file and this row.

    Whether a regime's ``route_ids`` resolve, and whether a regime is partner-closed, need
    ``data/routes/`` and belong to the resolver.
    """
    document = read_document(path)
    table = _validate(schema.ScenarioFile, document, path).scenario
    scenario_id = _require_text(
        path,
        f"{SCENARIO_TABLE}.id",
        table.id,
        "a scenario is referred to by id from every run that uses its regimes",
    )
    _require_text(
        path,
        f"{SCENARIO_TABLE}.owner_id",
        table.owner_id,
        "every scenario carries its owner from the first commit (Principle VII)",
    )
    regimes = _regimes(path, table.regime)
    transitions = _transitions(path, table.transition, regimes)
    policy, redirect_to = _fallback(path, table.fallback)
    return ScenarioDeclaration(
        id=scenario_id,
        owner_id=table.owner_id,
        regimes=regimes,
        transitions=transitions,
        fallback_policy=policy,
        redirect_to=redirect_to,
    )


def _regimes(path: Path, declared: list[schema.RegimeTable]) -> tuple[Regime, ...]:
    """The declared regimes, refusing an empty set and a duplicate id within one file.

    Two regimes with one id in one file is not a merge and not a preference: whichever was
    read second would win by position, and every figure conditional on the regime would
    silently describe the other one.
    """
    _non_empty_list(
        path,
        f"{SCENARIO_TABLE}.regime",
        declared,
        "a scenario with no regime states no belief about which corridors exist, and every "
        "transition in it would name a regime that does not exist",
    )
    seen: dict[str, int] = {}
    regimes: list[Regime] = []
    for position, entry in enumerate(declared):
        field_prefix = f"{SCENARIO_TABLE}.regime[{entry.id}]"
        identifier = _require_text(
            path,
            f"{field_prefix}.id",
            entry.id,
            "a regime is referred to by id from the transitions that move between regimes",
        )
        if identifier in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.id",
                f"declares the regime id {identifier!r}, which entry {seen[identifier]} of "
                "this file already declares. Two regimes with one id are not merged and "
                "neither is preferred: the one read second would win by position, and every "
                "figure conditional on the regime would describe the other one.",
                "rename one of the two regimes",
            )
        seen[identifier] = position
        regimes.append(
            Regime(
                id=identifier,
                route_ids=frozenset(
                    _non_empty_list(
                        path,
                        f"{field_prefix}.route_ids",
                        entry.route_ids,
                        "a regime that includes no route says money cannot move at all, "
                        "which is a claim about the world rather than an empty list; if that "
                        "is the belief, it is stated by a regime naming the routes that do "
                        "work and leaving the rest out",
                    )
                ),
            )
        )
    return tuple(regimes)


def _transitions(
    path: Path,
    declared: list[schema.TransitionTable],
    regimes: tuple[Regime, ...],
) -> tuple[RegimeTransition, ...]:
    """The declared transitions, checked for the four things that make a chain a chain.

    Ascending, joined, naming declared regimes, and marked as assumptions. Every one of them
    is refused rather than repaired: reordering, deduplicating or bridging a gap would be
    choosing the owner's belief for him, and the whole point of the record is that the belief
    is his and is visible.
    """
    _non_empty_list(
        path,
        f"{SCENARIO_TABLE}.transition",
        declared,
        "a scenario with no transition has no regime for any date, and there is no default "
        "regime to fall back on: substituting one would state a belief about which "
        "corridors exist that the owner never expressed (FR-019)",
    )
    known = {regime.id for regime in regimes}
    transitions: list[RegimeTransition] = []
    for position, entry in enumerate(declared):
        field_prefix = f"{SCENARIO_TABLE}.transition[{position}]"
        for field, named in (("before", entry.before), ("after", entry.after)):
            if named not in known:
                raise DeclarationError(
                    path,
                    f"{field_prefix}.{field}",
                    f"names the regime {named!r}, which this scenario does not declare. A "
                    "transition moves between two regimes stated in the same file; a name "
                    f"that resolves to nothing would leave the dates on that side of "
                    f"{entry.on_date!r} in no regime at all. Declared here: "
                    f"{sorted(known)}.",
                    "declare that regime, or correct the name",
                )
        if entry.before == entry.after:
            raise DeclarationError(
                path,
                f"{field_prefix}.after",
                f"names the same regime as 'before' ({entry.before!r}), so nothing changes "
                f"on {entry.on_date!r}. A transition that transitions nothing would put an "
                "assumption in the output with no consequence attached to it.",
                "name the regime in force after the date, or delete the transition",
            )
        if not entry.is_assumption:
            raise DeclarationError(
                path,
                f"{field_prefix}.is_assumption",
                "is declared false. A regime transition is always an assumption: nobody "
                "knows when a war ends, and FR-020 requires the date be presented as a "
                "stated assumption rather than a known fact. The field exists to make that "
                "claim unmissable in the output, not to be switched off -- which is why the "
                "core types it as a Literal admitting one value.",
                "write is_assumption = true, or move the fact into a leg's "
                "available_from/available_until where an observation belongs",
            )
        transitions.append(
            RegimeTransition(
                on_date=_parse_date(path, f"{field_prefix}.on_date", entry.on_date),
                before=entry.before,
                after=entry.after,
                is_assumption=True,
                rationale=_require_text(
                    path,
                    f"{field_prefix}.rationale",
                    entry.rationale,
                    "the rationale is what a transition carries where an observation "
                    "carries a source: it is the owner's stated belief in words, and a "
                    "figure conditional on an unexplained guess cannot be argued with",
                ),
            )
        )
    _chained(path, transitions)
    return tuple(transitions)


def _chained(path: Path, transitions: list[RegimeTransition]) -> None:
    """Refuse a sequence of transitions that does not describe one chain of regimes.

    The same two properties ``core.scenarios.regimes`` refuses, checked where the file and
    the row can be named. The core raises on them because reaching it with a broken chain
    means this check was bypassed; here they are data errors with a location.
    """
    for position in range(1, len(transitions)):
        earlier = transitions[position - 1]
        later = transitions[position]
        field_prefix = f"{SCENARIO_TABLE}.transition[{position}]"
        if later.on_date <= earlier.on_date:
            raise DeclarationError(
                path,
                f"{field_prefix}.on_date",
                f"is dated {later.on_date.isoformat()}, which is not after transition "
                f"{position - 1}'s {earlier.on_date.isoformat()}. Transitions are neither "
                "reordered nor deduplicated: two regimes claiming one date is a "
                "contradiction in the scenario, and choosing between them would be choosing "
                "the owner's belief for him.",
                "declare the transitions in strictly ascending date order",
            )
        if earlier.after != later.before:
            raise DeclarationError(
                path,
                f"{field_prefix}.before",
                f"begins in regime {later.before!r} while transition {position - 1} ends in "
                f"{earlier.after!r}, so every date between "
                f"{earlier.on_date.isoformat()} and {later.on_date.isoformat()} falls in a "
                "regime nobody declared. A chain of regimes has to join up; a gap cannot be "
                "bridged by picking one of the two.",
                f"write before = {earlier.after!r}, or add the transition that is missing",
            )


def _fallback(
    path: Path, table: schema.FallbackTable
) -> tuple[capacity.FallbackPolicy, str | None]:
    """``[scenario.fallback]`` as a policy and, for ``redirect``, its named destination.

    **A policy this feature knows about but has not built fails by name.** ``deposit`` --
    §4.3.4's "place it on deposit" -- needs a deposit instrument, and this feature adds no
    instruments; treating it as *hold as cash* would substitute a default for a policy the
    owner explicitly chose (FR-013). The message says which feature will bring it, because
    an unrecognised policy and a real policy that is not built yet are different facts and
    the owner acts differently on each: one is a typo, the other is a wait.

    ``redirect_to`` is present-and-empty for every policy but ``redirect``, on the
    ``verified_on`` precedent: a ``redirect`` whose destination line was forgotten must not
    read as a deliberate blank, and FR-013 requires the target be *named*.
    """
    deferred = capacity.DEFERRED_POLICIES.get(table.policy)
    if deferred is not None:
        raise DeclarationError(
            path,
            f"{SCENARIO_TABLE}.fallback.policy",
            f"declares the fallback policy {table.policy!r}, which this engine does not "
            f"implement yet: {deferred}.",
            f"declare one of {sorted(_FALLBACK_POLICIES)} until then, chosen deliberately "
            "rather than as a stand-in for the one you wanted",
        )
    policy = _FALLBACK_POLICIES[
        _known(
            path,
            f"{SCENARIO_TABLE}.fallback.policy",
            table.policy,
            _FALLBACK_POLICIES,
            "fallback policy",
        )
    ]
    if policy == capacity.REDIRECT:
        return policy, _require_text(
            path,
            f"{SCENARIO_TABLE}.fallback.redirect_to",
            table.redirect_to,
            "a redirect sends the excess to a **named** destination (FR-013), and an empty "
            "name would send it nowhere while reporting that it was redirected",
        )
    if table.redirect_to != "":
        raise DeclarationError(
            path,
            f"{SCENARIO_TABLE}.fallback.redirect_to",
            f"names {table.redirect_to!r} under a fallback policy of {policy!r}, which "
            "redirects nothing. It is refused rather than ignored: a destination in the file "
            "that no excess is ever sent to is a line a reader would take for a plan.",
            f"leave it empty, or declare policy = {capacity.REDIRECT!r}",
        )
    return policy, None


# ---------------------------------------------------------------------------
# 003-route-coverage: the spendable-endpoint list
# ---------------------------------------------------------------------------
#
# Same four responsibilities -- read, shape, meaning, construct -- and the one difference worth
# stating: **no citation is read and none is expected.** An owner's statement about where he
# spends is not an observation of the world; it is a fact about his own life, the same exemption
# `data/streams/` and `data/scenarios/` already have.
#
# `scripts/check_provenance.py` therefore does not scan `data/spendable/` -- but **not** because
# the directory is absent from `SOURCED_DIRS` (research.md D4, amended 2026-08-23). That gate is
# fail-closed over the whole data tree: a directory in neither list is an *error*, never a blind
# spot. `spendable` goes unscanned only because it is named in `EXEMPT_DIRS` **with its reason
# recorded beside it**, which is the one way a directory is permitted to be out of scope. If a
# number ever has to live here it moves to a sourced directory, rather than the exemption
# widening to cover it. Contract tests assert both halves rather than assuming either.
#
# What is *not* here, because it needs a second file: whether the venue exists, whether it can
# hold the currency, whether the currency is the run's base currency, and whether the owner owns
# the streams. All four are relations, and they live in the resolver where the whole set is in
# hand.

SPENDABLE_TABLE: Final = "spendable"
"""Root array of a spendable file, and the prefix of every field path in one."""

OWNER_TABLE: Final = "owner"
"""The owner table of a spendable file."""


def spendable_from_file(path: Path) -> tuple[str, tuple[SpendableEndpoint, ...]]:
    """One ``data/spendable/<owner>.toml`` as its owner id and its declared endpoints.

    Returns the owner id beside the endpoints rather than folding it into each record: the
    endpoints are `(venue x currency)` pairs and the owner is a property of the *file*, so
    putting him on every row would be one fact in as many places as there are venues.

    Three refusals belong here because all three are properties of this one file read in
    isolation:

    * **An empty ``[[spendable]]`` list.** A file with no entries would make every exit deficit
      3 -- a report full of confident wrong verdicts built out of a forgotten line (research.md
      D13). Refused for the same reason an empty venue file is.
    * **A duplicate ``(venue, currency)`` pair.** The loader's existing duplicate-id precedent:
      the second entry says nothing the first does not, so a file that repeats itself is a file
      somebody edited twice, and merging the two silently would hide that.
    * **A currency this engine does not model.** A closed enum, so a typo is a load-time failure
      rather than a fourth currency that never matches anything.
    """
    document = read_document(path)
    file = _validate(schema.SpendableFile, document, path)
    owner_id = _require_text(
        path,
        f"{OWNER_TABLE}.id",
        file.owner.id,
        "the spendable list is one person's statement about his own life, and it is resolved "
        "against that person's income streams (Principle VII)",
    )
    if not file.spendable:
        raise DeclarationError(
            path,
            SPENDABLE_TABLE,
            "declares no spendable endpoints. An empty list is reported rather than read as "
            "'money can never come back out': it would make every declared exit fail the "
            "spendable test at once, and the coverage report would name a third deficit for "
            "every destination in the registry -- a confident wrong answer built out of a "
            "forgotten line.",
            "declare at least one [[spendable]] entry, naming a venue you actually spend from",
        )
    endpoints: list[SpendableEndpoint] = []
    seen: dict[tuple[str, Currency], int] = {}
    for position, entry in enumerate(file.spendable):
        field_prefix = f"{SPENDABLE_TABLE}[{position}]"
        venue_id = _require_text(
            path,
            f"{field_prefix}.venue",
            entry.venue,
            "a spendable endpoint is a named venue the owner spends from, and it is checked "
            "against the declared venues",
        )
        currency = _currency(path, f"{field_prefix}.currency", entry.currency)
        if (venue_id, currency) in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.venue",
                f"declares {venue_id!r} holding {currency.value} for the second time; entry "
                f"{seen[(venue_id, currency)]} of this file already declares it. The two are "
                "not merged: the second says nothing the first does not, so a repeated pair is "
                "a file that was edited twice and one of the edits is probably not the one that "
                "was meant.",
                "delete the duplicate entry",
            )
        seen[(venue_id, currency)] = position
        endpoints.append(SpendableEndpoint(venue_id=venue_id, currency=currency))
    return owner_id, tuple(endpoints)


# ---------------------------------------------------------------------------
# 004-composed-paths: the segment bound
# ---------------------------------------------------------------------------
#
# Same four responsibilities -- read, shape, meaning, construct -- over the smallest declaration
# in the project, and the same difference `spendable` already has: **no citation is read and
# none is expected.** How far the owner is willing to let a search run is a statement about his
# own preferences, not an observation of the world.
#
# `scripts/check_provenance.py` therefore does not scan `data/composition/` -- but **not**
# because the directory is absent from `SOURCED_DIRS`. That gate is fail-closed over the whole
# data tree: a directory in neither list is an *error*, never a blind spot. `composition` goes
# unscanned only because it is named in `EXEMPT_DIRS` **with its reason recorded beside it**,
# which is the one way a directory is permitted to be out of scope. If a number that describes
# the world ever has to live here it moves to a sourced directory, rather than the exemption
# widening to cover it.
#
# **The one refusal that is this feature's own**: `max_segments` below 1. It is checked here
# rather than in the schema because the message has to name the file and say what the number
# would mean -- a bound of 0 admits nothing at all, including declared routes, so it is a broken
# registry and not a way to turn composition off. A bound of 1 *is* that way, and it loads.
#
# What is *not* here, because it needs a second file: whether the owner owns the streams the
# bound is resolved with. That is a relation, and it lives in the resolver where both are in
# hand.

COMPOSITION_TABLE: Final = "composition"
"""Root table of a composition file, and the prefix of every field path in one."""


def composition_from_file(path: Path) -> tuple[str, SegmentBound]:
    """One ``data/composition/<owner>.toml`` as its owner id and the declared bound.

    Returns the owner id beside the bound rather than folding it into the record: the bound is
    a number and the owner is a property of the *file*, and a core record carrying him would be
    one fact in two places (the same shape as ``spendable_from_file``).
    """
    document = read_document(path)
    file = _validate(schema.CompositionFile, document, path)
    owner_id = _require_text(
        path,
        f"{OWNER_TABLE}.id",
        file.owner.id,
        "the segment bound is one person's policy about his own registry, and it is resolved "
        "against that person's income streams (Principle VII)",
    )
    if file.composition.max_segments < 1:
        raise DeclarationError(
            path,
            f"{COMPOSITION_TABLE}.max_segments",
            f"declares {file.composition.max_segments}, and a candidate has at least 1 segment. "
            "A bound below 1 admits nothing at all -- not even a declared route -- so it is a "
            "broken registry rather than a way to switch composition off. Enumerating nothing "
            "for it would report every corridor as unreachable while the fault was one digit.",
            "write max_segments = 1 to consider only declared routes, or a larger number to "
            "chain that many",
        )
    return owner_id, SegmentBound(max_segments=file.composition.max_segments)


# ---------------------------------------------------------------------------
# 008-seed-and-goals: the owner's opening lots, and what the money is for
# ---------------------------------------------------------------------------
#
# Same four responsibilities -- read, shape, meaning, construct -- and the same difference
# `spendable` and `composition` already have: **no citation is read and none is expected.**
# What the owner paid for a lot and what sum he is aiming at are his own records, not
# observations of the world, so there is nothing for a source to vouch for. Both directories
# are named in `EXEMPT_DIRS` of `scripts/check_provenance.py` **with their reason recorded**,
# which is the one way a directory is permitted to be out of scope under a fail-closed gate.
#
# **The refusals that are this feature's own** are the two the honesty mechanism rests on:
#
# * `basis` must be `known` or `estimated`, with no default. A cost whose reliability nobody
#   stated would produce a confidently unmarked tax figure, which is the defect class this
#   project exists to remove (FR-006).
# * `estimated` requires `reason` and `known` forbids it. The loader cannot know which of the
#   two lines is wrong, and either guess is a declaration it invented: ignoring the reason
#   drops something the owner wrote, and marking the figure contradicts what he said (FR-008).
#
# **Provenance is attached here, and it is the only place it could be.** A known basis rests
# on no cited source -- `prov.EMPTY`, the reading `data/streams/` already has for an owner's
# own salary -- while an estimated one carries the mark `core.ledger.seeds.basis_estimated`
# builds, so the guess follows the cost into the gain and the tax without anything downstream
# having to remember (FR-007).
#
# What is *not* here, because it needs a second file or a run: whether the instrument exists
# (the resolver holds every declaration), whether the goal's currency is the run's base
# currency (`spendable`'s precedent -- a base currency is a property of the run), and whether
# the acquisition date is consistent with the instrument's issue date. The last of those is
# deliberately **not** a load error at all: it is a well-formed declaration of an impossible
# history, and the engine reports it as a typed `InconsistentTerms` -- the same division this
# module already draws for a maturity on or before its issue date.

SEED_TABLE: Final = "seed"
"""Root array of a seed file, and the prefix of every field path in one."""

GOAL_TABLE: Final = "goal"
"""Root array of a goal file."""

BASIS_KNOWN: Final = "known"
"""The declared word for a cost the owner is sure of."""

BASIS_ESTIMATED: Final = "estimated"
"""The declared word for a cost he is not. Requires a reason; produces a propagating mark."""

_GOAL_VARIABLES: Final = ("monthly_contribution", "target_sum", "target_date")
"""The three, in declaration order. Any two fix the third (FR-011)."""

_VARIABLES_A_GOAL_NEEDS: Final = 2
"""Named so the check below reads as the rule it is rather than as a magic number."""


def _owner_of(path: Path, table: schema.OwnerTable, *, what: str) -> str:
    """The owner a per-owner file belongs to, non-empty.

    Shared by the two loaders below rather than written twice: it is one claim -- whose file
    this is -- and two copies would eventually disagree about whether the id may be blank.
    """
    return _require_text(
        path,
        f"{OWNER_TABLE}.id",
        table.id,
        f"{what} is one person's declaration about his own life, and every record built from "
        "it carries him from the first commit (Principle VII)",
    )


def _basis(path: Path, entry: schema.SeedTable, *, field_prefix: str) -> seeds.Basis:
    """``known`` or ``estimated``, with the reason rule the two words imply.

    The pairing is checked here rather than in the shape validation because pydantic can see
    one field at a time: "``reason`` is required for one value of ``basis`` and forbidden for
    the other" is a statement about two fields, and the message has to be able to say which
    of the two the author probably meant.
    """
    declared = entry.basis
    if declared not in (BASIS_KNOWN, BASIS_ESTIMATED):
        raise DeclarationError(
            path,
            f"{field_prefix}.basis",
            f"declares {declared!r}, which is neither {BASIS_KNOWN!r} nor {BASIS_ESTIMATED!r}. "
            "There is no third kind of basis and no default: a cost whose reliability nobody "
            "stated would produce a tax figure that looks as confident as a documented one.",
            f"write {BASIS_KNOWN!r} if you know what these units cost, or {BASIS_ESTIMATED!r} "
            "with a reason if you are stating it from memory",
        )
    if declared == BASIS_KNOWN:
        if entry.reason is not None:
            raise DeclarationError(
                path,
                f"{field_prefix}.reason",
                f"is declared beside a {BASIS_KNOWN!r} basis. A reason explains why a cost is "
                "a guess, so one of the two lines is wrong -- and the loader cannot tell "
                "which. Ignoring the reason would drop something you wrote; marking the "
                "figure would contradict what you said.",
                f"delete the reason, or change the basis to {BASIS_ESTIMATED!r}",
            )
        return seeds.KNOWN
    if entry.reason is None:
        raise DeclarationError(
            path,
            f"{field_prefix}.reason",
            f"is absent beside an {BASIS_ESTIMATED!r} basis. The mark this estimate puts on "
            "every figure derived from the lot -- the gain, the tax on it, everything "
            "containing either -- has to state why the cost is a guess (FR-008).",
            "write what makes the cost uncertain, in your own words",
        )
    return seeds.basis_estimated(
        declared_at=source_id(path, f"{SEED_TABLE}[{_position_of(field_prefix)}]"),
        reason=_require_text(
            path,
            f"{field_prefix}.reason",
            entry.reason,
            "an empty reason is not a reason: a mark that cannot say what it rests on is a "
            "taint flag rather than provenance",
        ),
        estimated_for=_parse_date(path, f"{field_prefix}.acquired_on", entry.acquired_on),
    )


def _position_of(field_prefix: str) -> str:
    """The entry index out of a field prefix like ``seed[1]``.

    The declaration reference and the field prefix must name the same entry, so the index is
    read back from the prefix rather than passed a second time: two parameters carrying one
    fact are two places for it to disagree.
    """
    return field_prefix.removeprefix(f"{SEED_TABLE}[").removesuffix("]")


def seeds_from_file(path: Path, *, base_currency: Currency) -> tuple[str, tuple[SeedLot, ...]]:
    """One ``data/seeds/<owner>.toml`` as its owner id and the lots it declares.

    Returns the owner beside the lots rather than folding him into the file record, on
    ``spendable_from_file``'s precedent -- though each lot *does* carry him, because a lot
    outlives the file it was read from and "whose holding is this" must still be answerable
    when it does.

    ``base_currency`` is required and keyword-only because the file states no currency and
    must not: a declared cost is in the base currency by FR-010, and the base currency is a
    property of the run rather than of the holding. Passing it in is what keeps this loader
    from hard-wiring hryvnia into the one place a second jurisdiction would have to change.

    Lot ids come from the entry's position -- ``seed-0``, ``seed-1`` -- rather than being
    declared. Two purchases of one instrument on one date are legitimate and must be two lots,
    so identity cannot be derived from ``(instrument, date)``; and asking the owner to invent
    an id would be a field with nothing to say.
    """
    document = read_document(path)
    file = _validate(schema.SeedFile, document, path)
    owner_id = _owner_of(path, file.owner, what="a declaration of what he already holds")
    declared: list[SeedLot] = []
    for position, entry in enumerate(file.seed):
        field_prefix = f"{SEED_TABLE}[{position}]"
        basis = _basis(path, entry, field_prefix=field_prefix)
        declared.append(
            SeedLot(
                owner_id=owner_id,
                lot_id=f"{SEED_TABLE}-{position}",
                declared_at=source_id(path, field_prefix),
                instrument_id=_require_text(
                    path,
                    f"{field_prefix}.instrument_id",
                    entry.instrument_id,
                    "a lot is a holding *of* something, and the something is checked against "
                    "the curated instrument declarations (FR-005)",
                ),
                quantity=_positive(
                    path,
                    f"{field_prefix}.quantity",
                    entry.quantity,
                    "a lot may not exist at zero or below: an empty lot would keep an "
                    "acquisition date alive that holds nothing and would take its turn in the "
                    "consumption order",
                ),
                acquired_on=_parse_date(path, f"{field_prefix}.acquired_on", entry.acquired_on),
                cost=Money(
                    _non_negative(
                        path,
                        f"{field_prefix}.cost",
                        entry.cost,
                        "a rebate is not a basis. Zero is a real declaration -- a holding that "
                        "genuinely cost nothing -- and is accepted; what is refused is the "
                        "field being absent, because a zero nobody wrote would make every "
                        "later disposal compute the wrong gain (FR-006)",
                    ),
                    base_currency,
                    _basis_provenance(basis),
                ),
                basis=basis,
            )
        )
    return owner_id, tuple(declared)


def _basis_provenance(basis: seeds.Basis) -> Provenance:
    """What the declared cost rests on: nothing, or the owner's own estimate.

    A known cost gets ``prov.EMPTY`` -- the reading ``data/streams/`` already has for a salary:
    an owner's own record is not an observation, so there is no source to cite and nothing to
    mark. An estimated one carries the mark, which is how the guess reaches the tax.

    This is one of the two places in the project entitled to hand ``Money`` its provenance, and
    it is the whole of FR-007's mechanism: attach it here and every transform downstream
    carries it, because none of them can drop it.
    """
    match basis:
        case seeds.BasisKnown():
            return prov.EMPTY
        case seeds.BasisEstimated():
            return prov.of([basis.mark])


def goals_from_file(path: Path) -> tuple[str, tuple[Goal, ...]]:
    """One ``data/goals/<owner>.toml`` as its owner id and the targets it declares.

    No ``base_currency`` argument, unlike :func:`seeds_from_file`, and the asymmetry is the
    declarations': a goal *states* its currency (FR-016 keeps the field so the multi-currency
    case stays open) while a seed's cost has no currency field at all. Whether the stated
    currency is the run's base currency is therefore a question for the resolver, exactly as
    it is for the spendable list.

    **Fewer than two of the three variables is refused here, naming what is missing** (FR-011).
    It is a property of one entry read in isolation, so it belongs to the loader; and the
    message lists the absent fields rather than saying "declare more", because the whole point
    is that the tool will not choose which one to invent.
    """
    document = read_document(path)
    file = _validate(schema.GoalFile, document, path)
    owner_id = _owner_of(path, file.owner, what="a declaration of what his money is for")
    declared: list[Goal] = []
    seen: dict[str, int] = {}
    for position, entry in enumerate(file.goal):
        field_prefix = f"{GOAL_TABLE}[{position}]"
        goal_id = _require_text(
            path,
            f"{field_prefix}.id",
            entry.id,
            "a goal is reported against by id, and an unnamed target cannot be reported "
            "against at all",
        )
        if goal_id in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.id",
                f"declares the goal id {goal_id!r} for the second time; entry {seen[goal_id]} "
                "of this file already declares it. The two are not merged and neither is "
                "preferred: two targets with one name cannot be told apart, so neither could "
                "be reported on.",
                "rename one of the two goals, or delete the one that is a duplicate",
            )
        seen[goal_id] = position
        currency = _currency(path, f"{field_prefix}.currency", entry.currency)
        _require_two_variables(path, entry, field_prefix=field_prefix)
        declared.append(
            Goal(
                owner_id=owner_id,
                id=goal_id,
                currency=currency,
                monthly_contribution=None
                if entry.monthly_contribution is None
                else Money(
                    _non_negative(
                        path,
                        f"{field_prefix}.monthly_contribution",
                        entry.monthly_contribution,
                        "a withdrawal is not a contribution. Zero is a real declaration -- a "
                        "goal reached out of growth on the starting amount alone -- and is "
                        "accepted",
                    ),
                    currency,
                    prov.EMPTY,
                ),
                target_sum=None
                if entry.target_sum is None
                else Money(
                    _positive(
                        path,
                        f"{field_prefix}.target_sum",
                        entry.target_sum,
                        "a target of zero is not something to aim at and a negative one is not "
                        "a target",
                    ),
                    currency,
                    prov.EMPTY,
                ),
                target_date=_optional_date(path, f"{field_prefix}.target_date", entry.target_date),
            )
        )
    return owner_id, tuple(declared)


def _require_two_variables(path: Path, entry: schema.GoalTable, *, field_prefix: str) -> None:
    """FR-011: any two of the three fix the third, and fewer than two fixes nothing.

    The absent ones are named in the message. A goal declaring only a target sum could be
    completed by inventing a contribution or by inventing a date, and either would be the tool
    answering a question the owner did not ask -- so it says which two fields it found nothing
    in and stops.
    """
    missing = [name for name in _GOAL_VARIABLES if getattr(entry, name) is None]
    if len(_GOAL_VARIABLES) - len(missing) >= _VARIABLES_A_GOAL_NEEDS:
        return
    raise DeclarationError(
        path,
        field_prefix,
        f"declares fewer than two of {list(_GOAL_VARIABLES)}: nothing is declared for "
        f"{missing}. Any two fix the third, and fewer than two fix nothing -- filling one in "
        "would be the tool inventing the plan rather than solving it.",
        "declare two of monthly_contribution, target_sum and target_date -- or all three, "
        "which asks whether they are consistent",
    )
