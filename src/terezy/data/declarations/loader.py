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

**Percent becomes a fraction exactly once in this module**: every ``_pct`` field passes
through :func:`_as_fraction`, which is the only division by 100 here. Doing it twice and
not doing it at all are the two likeliest bugs in this layer, and both are invisible in
the output -- a 15.5% coupon reading as 0.155% still produces a plausible schedule -- so
the conversion is one named function with one caller per field and a worked assertion in
the contract tests.

⚙ The sentence used to claim that nothing else divided by 100 **anywhere in the project**,
and feature 007 made it false: `core.inflation.series` turns a CPI observation published
against the previous month = 100 into a growth factor. Corrected in 013 rather than
restated, because a claim about another module is a test or it is not written --
``tests/contract/test_nothing_is_inferred.py`` now holds the project-wide version, with
each permitted site named beside its reason.

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

import itertools
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, assert_never, cast, get_args

from pydantic import BaseModel, ValidationError

from terezy.core.inflation.series import (
    CpiObservation,
    CpiSeries,
    InflationAssumption,
    Periodicity,
)
from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments.access import InstrumentAccess, VenueQuote
from terezy.core.instruments.fund import (
    BuybackAvailability,
    CapEntry,
    ChosenPoint,
    DeclaredYield,
    DistributionTerms,
    ExchangeRateAssumption,
    FeeFact,
    FundDeclaration,
    LegalTerms,
    LiquidityMode,
    LiquidityTerms,
    ObservedPractice,
    Peg,
    SpreadTerms,
    VerificationTask,
)
from terezy.core.instruments.groups import InstrumentGroup
from terezy.core.instruments.interface import (
    PAYMENT_KINDS,
    Assumptions,
    BondTerms,
    DateRange,
    EnumeratedTerms,
    InstrumentConstraints,
    InstrumentDeclaration,
    PaymentKind,
    ScheduledPayment,
)
from terezy.core.ledger import lots, seeds
from terezy.core.ledger.seeds import SeedLot
from terezy.core.primitives import conventions, periods
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.results.candidates import CandidateCeiling
from terezy.core.results.composed import SegmentBound
from terezy.core.results.coverage import SpendableEndpoint
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.goal import Goal
from terezy.core.results.question import Question, Reserve
from terezy.core.results.tuple import ContinuationAssumption, InstrumentPlan
from terezy.core.routes import capacity, legs
from terezy.core.routes.channels import ChannelSide, FxChannel, Side, effective_rate
from terezy.core.routes.legs import Leg, Route
from terezy.core.routes.venues import Venue
from terezy.core.scenarios.early_exit import SpreadHolds
from terezy.core.scenarios.regimes import Regime, RegimeTransition
from terezy.core.streams import streams
from terezy.core.streams.streams import IncomeStream, Indexation
from terezy.core.tax import scheme as scheme_module
from terezy.core.tax import year as tax_year
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.core.tax.official_rate import (
    NonPublicationDay,
    NonPublicationRule,
    OfficialRateObservation,
    OfficialRateSeries,
)
from terezy.core.tax.schedule import RateEntry
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

    The only place a declared **percentage** becomes a fraction, and the only division by
    100 in this module: every ``_pct`` field goes through here, which is what makes "exactly
    once, at the boundary" a checkable claim rather than a convention.

    ⚙ It is **not** the only division by 100 in the project -- `core.inflation.series` turns
    a CPI observation published against the previous month = 100 into a growth factor -- and
    this docstring said it was, twice, after feature 007 landed that one.
    ``tests/contract/test_nothing_is_inferred.py`` holds the project-wide version, with each
    permitted site named beside its reason and pinned to exactly one division each.
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
    kind: str,
    check_kind: bool = True,
) -> SourceRef:
    """One table's citation, as the core's ``SourceRef``.

    The id names the file and the table (see :func:`source_id`), the citation is required
    non-empty, and an empty ``verified_on`` becomes ``None`` -- the unverified mark that
    FR-015 propagates through every figure derived from this table.

    ⚙ **``kind`` is now carried as well as checked, and that reversed a decision.** It used to
    be validated here and dropped, on the reading that a kind resolved into feature 001's
    ``BondTerms``, ``InstrumentConstraints`` and ``TaxClass`` would be "a value nothing
    reads". Feature 010 made it a value something reads: a tuple's outcome is derived from
    those tables, FR-019 requires staleness to propagate from **every** declared value in
    every part, and by the time a provenance has been merged across five tables the record
    that knew each kind is gone. Carrying it on the citation is what lets a merged provenance
    be aged at all -- see :attr:`terezy.core.primitives.provenance.SourceRef.kind`.

    ``check_kind=False`` says the non-empty check happens at the record field this kind
    becomes -- a leg's ``kind_of_observation``, a channel's ``kind``, an access price's -- so
    that the error names the field the file actually uses. It suppresses the *check* and never
    the carrying: a kind checked elsewhere is still stamped here, because a source that
    reached the core without one could never be aged.
    """
    if check_kind:
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
        kind=kind,
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
        groups=_group_labels(path, f"{INSTRUMENT_TABLE}.groups", table.groups),
    )


# ---------------------------------------------------------------------------
# 013-enumerated-schedule: a bond declared as the payments it will make
# ---------------------------------------------------------------------------

SCHEDULE_TABLE: Final = f"{INSTRUMENT_TABLE}.schedule"

INFERENCES: Final[Mapping[str, str]] = {
    "face_value": "what face value this issue actually has",
    "payment_kind": "which payments are coupons and which repay principal",
    "minor_unit_conversion": "whether the published figures denote major or minor units",
    "coverage": "whether this list is complete from the coverage date onwards",
}
"""The four things a transcribed schedule infers, and what each would have to settle.

Read here to validate a ``settles`` key. ``scripts/check_provenance.py`` checks the relation
FR-022 asks for -- that each inferred value's source says it is an inference and that a task
exists for it -- and holds its own copy of these ids, because a script that imported the
engine would stop being runnable by someone who has not installed it. The two are held equal
by ``tests/contract/test_provenance_gate.py``, which is what makes the copy safe.
"""

INFERENCE_MARKER: Final = "INFERENCE:"
"""How a citation says it is an inference rather than a reading of a source.

A prefix, because a sentence in prose cannot be checked and a check cannot go stale
silently. It marks a value nobody stated: what it rests on follows in the citation's own
words, and its ``verified_on`` is empty by construction (FR-020).
"""


def _payment_kind(path: Path, field_path: str, value: str) -> PaymentKind:
    """A declared payment label as the core's closed enum member (FR-007, FR-008).

    Never inferred from the amount, the date or the position in the list: ``8305, 8305,
    8305, 100000`` is obviously three coupons and a repayment of principal to a human and
    obviously nothing at all to a machine, and the published data carries no labels.
    """
    for kind in PaymentKind:
        if kind.value == value:
            return kind
    raise DeclarationError(
        path,
        field_path,
        f"declares the payment kind {value!r}, which this engine does not model. What a "
        "payment is decides both what the ledger records and which income kind the tax "
        "layer assesses, so it is never guessed from the amount or the position.",
        f"one of: {', '.join(sorted(kind.value for kind in PaymentKind))}",
    )


def _scheduled_payment(
    path: Path,
    table: schema.ScheduledPaymentTable,
    currency: Currency,
    *,
    field_prefix: str,
) -> ScheduledPayment:
    """One ``[[instrument.schedule.payment]]``, carrying its own citation."""
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
    return ScheduledPayment(
        on=_parse_date(path, f"{field_prefix}.on", table.on),
        amount=Money(
            _positive(
                path,
                f"{field_prefix}.amount",
                table.amount,
                "a payment of nothing is not a payment, and a negative one would have the "
                "holder paying the issuer, which this engine does not model",
            ),
            currency,
            sources,
        ),
        pays=_payment_kind(path, f"{field_prefix}.pays", table.pays),
    )


def _enumerated_schedule(
    path: Path,
    table: schema.EnumeratedScheduleTable,
    currency: Currency,
    *,
    field_prefix: str,
) -> EnumeratedTerms:
    """``[instrument.schedule]`` as ``EnumeratedTerms``, with nothing repaired on the way in.

    **The loader neither sorts nor merges.** An unordered list is refused rather than put in
    order, because ordering is settled at transcription -- the same declared human step that
    turns minor units into major ones -- and sorting here would delete the fact FR-020a
    exists to keep: that the source published it differently.
    """
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
    if not table.payment:
        raise DeclarationError(
            path,
            f"{field_prefix}.payment",
            "declares no payments. A schedule that lists nothing is not a schedule that "
            "pays nothing -- it is a declaration whose one content is missing, and every "
            "figure derived from it would describe a holding that was never modelled.",
            "declare one [[instrument.schedule.payment]] per dated amount",
        )
    covers_from = _parse_date(path, f"{field_prefix}.covers_from", table.covers_from)
    payments = tuple(
        _scheduled_payment(path, entry, currency, field_prefix=f"{field_prefix}.payment[{index}]")
        for index, entry in enumerate(table.payment)
    )
    _check_ordered(path, payments, field_prefix=field_prefix)
    _check_covered(path, payments, covers_from, field_prefix=field_prefix)
    _check_repays_principal(path, payments, field_prefix=field_prefix)
    return EnumeratedTerms(
        face_value=Money(
            _positive(
                path,
                f"{field_prefix}.face_value",
                table.face_value,
                "a redemption amount of nothing redeems nothing, and every unit fraction a "
                "principal repayment retires would be computed against it",
            ),
            currency,
            sources,
        ),
        covers_from=covers_from,
        payments=payments,
        day_count=_known(
            path,
            f"{field_prefix}.day_count",
            table.day_count,
            conventions.DAY_COUNT_FNS,
            "day-count convention",
        ),
        published_in_order=_published_in_order(
            path, table.published_in_order, payments, field_prefix=field_prefix
        ),
        provenance=sources,
    )


def _check_ordered(
    path: Path, payments: tuple[ScheduledPayment, ...], *, field_prefix: str
) -> None:
    """Every payment on or after the one before it."""
    for index, (earlier, later) in enumerate(itertools.pairwise(payments)):
        if later.on < earlier.on:
            raise DeclarationError(
                path,
                f"{field_prefix}.payment[{index + 1}].on",
                f"is {later.on.isoformat()}, before the payment above it on "
                f"{earlier.on.isoformat()}, so the list is not in ascending date order. It "
                "is refused rather than sorted: that the source published its payments in "
                "another order is a fact about the source, and sorting here would delete it.",
                "put the payments in date order when transcribing them, and record the "
                "order the source gave in 'published_in_order'",
            )


def _check_covered(
    path: Path,
    payments: tuple[ScheduledPayment, ...],
    covers_from: date,
    *,
    field_prefix: str,
) -> None:
    """No payment before the date the schedule claims to be complete from."""
    for index, payment in enumerate(payments):
        if payment.on < covers_from:
            raise DeclarationError(
                path,
                f"{field_prefix}.payment[{index}].on",
                f"is {payment.on.isoformat()}, before this schedule claims to be complete "
                f"from {covers_from.isoformat()}. Two declared facts that cannot both hold: "
                "either the coverage claim starts earlier than it says, or this payment "
                "belongs to a holder the claim does not describe.",
                "correct 'covers_from', or remove the payment that precedes it",
            )


def _check_repays_principal(
    path: Path, payments: tuple[ScheduledPayment, ...], *, field_prefix: str
) -> None:
    """At least one payment that returns principal."""
    if any(payment.pays is PaymentKind.PRINCIPAL_REPAYMENT for payment in payments):
        return
    raise DeclarationError(
        path,
        f"{field_prefix}.payment",
        "declares no payment repaying principal. A stream of coupons that never returns "
        "anything is not something the observed data contains and not something a reader "
        "would mean; read as declared it would report a holding whose basis is never "
        "recovered.",
        'label the payment that returns principal pays = "principal_repayment"',
    )


def _published_in_order(
    path: Path,
    declared: list[str] | None,
    payments: tuple[ScheduledPayment, ...],
    *,
    field_prefix: str,
) -> tuple[date, ...] | None:
    """The order the source published, checked to be a real difference (FR-020a, SC-018).

    Two refusals, and both are about the field staying **evidence**. An order that is not a
    rearrangement of these very payments describes some other list; an order identical to
    the ascending one records no difference at all, and a field that can be filled in
    without saying anything is a field that stops tracking the source.

    ⚙ The second refusal is also the field's stated limit: two payments of different kinds
    on one date are one date here, so a source that published *that pair* the other way
    round has nothing to record and is told so. See ``EnumeratedTerms.published_in_order``.
    """
    if declared is None:
        return None
    field_path = f"{field_prefix}.published_in_order"
    order = tuple(
        _parse_date(path, f"{field_path}[{index}]", text) for index, text in enumerate(declared)
    )
    dates = tuple(payment.on for payment in payments)
    if sorted(order) != sorted(dates):
        raise DeclarationError(
            path,
            field_path,
            "is not a rearrangement of this schedule's own payment dates, so it describes "
            "some other list. It records what the source published; a list that does not "
            "match the payments cannot be that.",
            "write every declared payment date exactly once, in the order the source gave",
        )
    if order == dates:
        raise DeclarationError(
            path,
            field_path,
            "repeats the order the payments are already in, so it records no difference. "
            "The field exists to keep a fact that sorting would delete -- that the source "
            "published these payments in another order -- and stating the ascending order "
            "makes it boilerplate rather than evidence.",
            "omit the field where the source published in date order",
        )
    return order


def _check_kinds_are_taxed(
    path: Path,
    payments: tuple[ScheduledPayment, ...],
    declared: Mapping[TaxableEventKind, str],
    *,
    field_prefix: str,
) -> None:
    """Every income kind this schedule produces has a declared tax class (FR-009).

    Checked here rather than at the first charge, because the schedule is on the page: a
    declaration that lists a repayment of principal and declares no treatment for a disposal
    is incomplete as written. Reported rather than treated as untaxed -- an exemption is a
    cited claim and a missing rule is not.
    """
    for index, payment in enumerate(payments):
        _, assessed = PAYMENT_KINDS[payment.pays]
        if assessed in declared:
            continue
        raise DeclarationError(
            path,
            f"{field_prefix}.tax_classes",
            f"declares no tax class for {assessed.value!r} income, which this schedule "
            f"produces: the payment at {field_prefix}.schedule.payment[{index}] on "
            f"{payment.on.isoformat()} is a {payment.pays.value!r}. A missing rule and a "
            "cited exemption are opposite claims, and only one of them has a source.",
            f'declare {assessed.value} = "<tax class id>"',
        )


def _check_verification_tasks(
    path: Path,
    tasks: list[schema.EnumeratedVerificationTaskTable],
    *,
    field_prefix: str,
) -> None:
    """Each task names an inference this engine knows about, and asks something.

    Whether every inference **has** a task is `scripts/check_provenance.py`'s question
    (FR-022), because it is a relation over the whole file and the gate is what a person
    maintaining a declaration by hand runs. What is checked here is that a task is
    well-formed, so a typo in ``settles`` fails naming the file rather than silently
    satisfying nothing.
    """
    for index, task in enumerate(tasks):
        entry = f"{field_prefix}.verification_task[{index}]"
        if task.settles not in INFERENCES:
            raise DeclarationError(
                path,
                f"{entry}.settles",
                f"names {task.settles!r}, which is not one of the things a declared "
                "schedule infers. A task settling nothing this engine tracks would leave "
                "the inference it was written for uncovered.",
                f"one of: {', '.join(sorted(INFERENCES))}",
            )
        _require_text(
            path,
            f"{entry}.question",
            task.question,
            "a task with no question records that somebody looked, and not what for",
        )
        _require_text(
            path,
            f"{entry}.searched",
            task.searched,
            "a question with no record of what was searched invites the same search again",
        )
        _parse_date(path, f"{entry}.searched_on", task.searched_on)


def enumerated_instrument_from_file(path: Path) -> InstrumentDeclaration:
    """One ``data/instruments/<id>.toml`` declaring a bond by its payments.

    The same record :func:`instrument_from_file` returns, differing in one field: its terms
    are the schedule rather than the closed form. Everything else about a declaration --
    what a purchase must satisfy, which class taxes which income -- is the same fact in
    both forms and is read by the same code.
    """
    document = read_document(path)
    table = _validate(schema.EnumeratedInstrumentFile, document, path).instrument
    currency = _currency(path, f"{INSTRUMENT_TABLE}.currency", table.currency)
    terms = _enumerated_schedule(path, table.schedule, currency, field_prefix=SCHEDULE_TABLE)
    tax_classes = _tax_class_references(
        path, table.tax_classes, field_prefix=f"{INSTRUMENT_TABLE}.tax_classes"
    )
    _check_kinds_are_taxed(path, terms.payments, tax_classes, field_prefix=INSTRUMENT_TABLE)
    _check_verification_tasks(path, table.verification_task, field_prefix=INSTRUMENT_TABLE)
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
        terms=terms,
        constraints=_constraints(
            path, table.constraints, currency, field_prefix=f"{INSTRUMENT_TABLE}.constraints"
        ),
        tax_classes=tax_classes,
        groups=_group_labels(path, f"{INSTRUMENT_TABLE}.groups", table.groups),
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
    return TaxClass(
        id=class_id,
        applies_to=frozenset(
            _taxable_kind(path, f"{field_prefix}.applies_to", kind) for kind in entry.applies_to
        ),
        rates=_rate_schedule(path, entry.rate, field_prefix=field_prefix),
    )


def _rate_schedule(
    path: Path,
    declared: list[schema.RateEntryTable],
    *,
    field_prefix: str,
) -> tuple[RateEntry, ...]:
    """``[[jurisdiction.tax_class.rate]]`` as the core's dated schedule, validated here.

    Four checks, all at load because all four need the file's name to be actionable
    (contracts/tax-schedule.md, loader validation table):

    * **empty** -- a class with no rate cannot charge anything, and a silent zero is the
      worst possible reading of that;
    * **duplicate effective date** -- two rates in force at once has no meaning, so one of
      them is a typo;
    * **out of order** -- the schedule is left in file order rather than sorted, so that
      the file reads as what it means and the fold is a plain scan. Sorting silently would
      make the file's order a thing nobody has to get right, and a reviewer scanning a
      misordered schedule would read the wrong rate as current;
    * **negative rate** -- a refund, which this rule does not model.

    The order check is the one worth being deliberate about. Sorting here was the obvious
    alternative and it is refused: a schedule whose written order disagrees with its
    effective order is a file a human misreads, and the load-time error is what stops that
    file existing at all.
    """
    if not declared:
        raise DeclarationError(
            path,
            f"{field_prefix}.rate",
            "declares no dated rate entry, so the class can charge nothing at all. An "
            "empty schedule is reported rather than read as an exemption: 'no rate is "
            "declared' and 'the declared rate is zero' are opposite claims, and only the "
            "second one has a citation behind it.",
            "declare at least one [[jurisdiction.tax_class.rate]] with its effective_from",
        )
    entries: list[RateEntry] = []
    for index, table in enumerate(declared):
        entry_prefix = f"{field_prefix}.rate[{index}]"
        effective_from = _parse_date(path, f"{entry_prefix}.effective_from", table.effective_from)
        _require_text(
            path,
            f"{entry_prefix}.note",
            table.note,
            "a dated entry states in words what its citation attests about the rate and "
            "about the date it came into force -- the date is the field a reviewer most "
            "needs prose for, because the rate can be checked at a glance and the date "
            "usually cannot",
        )
        if entries and effective_from == entries[-1].effective_from:
            raise DeclarationError(
                path,
                f"{entry_prefix}.effective_from",
                f"repeats {effective_from.isoformat()}, which the previous entry already "
                "declares. Two rates in force on one date has no meaning, and neither "
                "entry is preferred: whichever the lookup reached first would win by "
                "accident of file order.",
                "correct one of the two dates, or delete the entry that is a duplicate",
            )
        if entries and effective_from < entries[-1].effective_from:
            raise DeclarationError(
                path,
                f"{entry_prefix}.effective_from",
                f"is {effective_from.isoformat()}, before the previous entry's "
                f"{entries[-1].effective_from.isoformat()}. The schedule is read in the "
                "order it is written and is not silently sorted: a file whose order "
                "disagrees with its dates is one a human misreads, and reordering it here "
                "would make that file loadable.",
                "write the entries oldest first",
            )
        entries.append(
            RateEntry(
                effective_from=effective_from,
                pit_rate=_as_fraction(
                    _non_negative(
                        path,
                        f"{entry_prefix}.pit_rate_pct",
                        table.pit_rate_pct,
                        "a negative rate would be a refund rather than a charge, which is "
                        "not what this rule models",
                    )
                ),
                levy_rate=_as_fraction(
                    _non_negative(
                        path,
                        f"{entry_prefix}.levy_rate_pct",
                        table.levy_rate_pct,
                        "a negative rate would be a refund rather than a charge, which is "
                        "not what this rule models",
                    )
                ),
                provenance=prov.of(
                    [
                        _source_ref(
                            path,
                            entry_prefix,
                            source=table.source,
                            retrieved_on=table.retrieved_on,
                            verified_on=table.verified_on,
                            kind=table.kind,
                        )
                    ]
                ),
            )
        )
    return tuple(entries)


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

    A venue table carries no observed value -- an id, a name and a set of currency codes,
    no number and no date -- so no citation is read, and
    :class:`~terezy.core.routes.venues.Venue` has no provenance field to carry one. Every
    *number* attached to a venue lives on a leg, in ``data/routes/``, with its own source.

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


GROUP_TABLE: Final = "group"
"""Root array of ``data/groups.toml``."""


def groups_from_file(path: Path) -> tuple[InstrumentGroup, ...]:
    """Every declared group, in file order (015 FR-007a).

    A group table carries no observed value -- an id and a name -- so no citation is read and
    :class:`~terezy.core.instruments.groups.InstrumentGroup` has no field to carry one. This is
    ``venues_from_file``'s shape, for that function's reason.

    A duplicate id is refused here rather than by the resolver, because both entries are in one
    file and naming the other one needs nothing the caller has to supply.
    """
    document = read_document(path)
    declared = _validate(schema.GroupsFile, document, path).group
    if not declared:
        raise DeclarationError(
            path,
            GROUP_TABLE,
            "declares no groups. An empty vocabulary is reported rather than read as 'a "
            "question may name no group': every label an instrument carries would then be "
            "unresolvable, each refusal naming an instrument file instead of this one.",
            "declare at least one [[group]]",
        )
    seen: dict[str, int] = {}
    for position, entry in enumerate(declared):
        field = f"{GROUP_TABLE}[{position}].id"
        identifier = _require_text(
            path,
            field,
            entry.id,
            "a group is what a question names, and an unnamed one can be named by nothing",
        )
        if identifier in seen:
            raise DeclarationError(
                path,
                field,
                f"declares the group id {identifier!r}, which entry {seen[identifier]} already "
                "declares. Two entries with one id are not merged and neither is preferred: "
                "which name a reader sees would depend on file order.",
                "rename one of the two groups, or delete the duplicate entry",
            )
        seen[identifier] = position
        _require_text(
            path,
            f"{GROUP_TABLE}[{position}].name",
            entry.name,
            "a group a reader cannot recognise by name is one they cannot check",
        )
    return tuple(InstrumentGroup(id=entry.id, name=entry.name) for entry in declared)


def _group_labels(path: Path, field_path: str, declared: list[str]) -> tuple[str, ...]:
    """The groups one instrument declares itself into, refusing a blank or a repeat.

    Whether each id **exists** is a relation across files and is the resolver's; what can be
    seen from one file is that a label is a label and that it is claimed once.
    """
    labels: list[str] = []
    for position, label in enumerate(declared):
        identifier = _require_text(
            path,
            f"{field_path}[{position}]",
            label,
            "a group label is the id of a declared group, and an empty one names nothing",
        )
        if identifier in labels:
            raise DeclarationError(
                path,
                f"{field_path}[{position}]",
                f"declares the group {identifier!r} twice. Membership is a fact rather than a "
                "quantity, so a repeated label is a typo and not a stronger claim -- and it "
                "would be counted twice by anything that counts a group's members.",
                f"name {identifier!r} once",
            )
        labels.append(identifier)
    return tuple(labels)


def _non_empty_list[T](path: Path, field_path: str, values: list[T], why: str) -> list[T]:
    """A declared list that may not be empty, checked where the field can be named.

    Generic because its callers fail for the same reason in different files -- an empty list
    of a venue's currencies, of a regime's routes, of the two currencies a quote is between --
    and one message shape keeps them saying it the same way.

    ⚙ **The callers are deliberately not counted.** They were, and the count was already wrong
    when somebody re-read it -- then the sentence written to replace it got its own count
    wrong, and review caught that too. A number in prose beside a function that counts nothing
    is a claim with no way to fail except by being read.
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
        kind=table.kind,
        check_kind=False,
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
        kind=entry.kind,
        check_kind=False,
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
        kind=table.kind_of_observation,
        check_kind=False,
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

    An omitted ``tax_scheme`` becomes ``None``, which means *the owner has not named a
    treatment* -- a different claim from a scheme that charges nothing, and the reason
    ``capacity.deployable`` returns a record with no net field at all rather than a net
    figure that quietly equals the gross (012 FR-016).

    ``arrives_at`` and ``credited_to`` are both required and neither is derived from the
    other. Whether each names a declared venue, and whether ``tax_scheme`` names a declared
    scheme a stream is allowed to name, are relations and belong to the resolver.
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
        credited_to=_require_text(
            path,
            f"{field_prefix}.credited_to",
            entry.credited_to,
            "the venue income is credited at decides which reading of the law applies to it, "
            "and it is a different fact from where a funding route starts (012 FR-024a)",
        ),
        indexation=_indexation(path, entry.indexation, field_prefix=f"{field_prefix}.indexation"),
        tax_scheme=entry.tax_scheme,
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
# 006-inzhur-instruments: collective-investment funds
# ---------------------------------------------------------------------------
#
# Same four responsibilities in the same order -- read, shape, meaning, construct -- and the
# same two rules: **percent becomes a fraction exactly once**, in :func:`_as_fraction`, and
# **no pydantic type crosses this line**.
#
# ⚙ What is different here, and it is the whole point of the feature: a fund's numbers come
# from what the fund says about *itself*. Every table below therefore carries its own
# citation and is expected to carry an **empty** ``verified_on`` -- researched is not
# verified, and the mark propagates to every figure derived from it (FR-002). The provenance
# gate reports these as unverified rather than failing, which is the correct outcome and not
# something to work around.
#
# Two refusals here have no analogue in the bond loader and are worth naming. A
# ``verification_task`` that carries a **value** is refused, because the entire purpose of
# that record is that it holds none (research.md D8) -- ``extra="forbid"`` does the work, and
# the contract test asserts it. And ``is_assumption_driven = false`` is refused, because the
# core field is ``Literal[True]``: a fund whose terms are observed rather than stated is a
# different declaration, and silently accepting ``false`` would produce a record whose type
# says one thing and whose file says another.


FUND_BASIS: Final[Mapping[str, str]] = {
    "simple_annual": "a simple annual rate in the fund's own currency",
    "usd_equivalent_annual": "an annual rate on the unit's value in the pegged currency",
}
"""The declared-yield bases this engine models, with what each one means.

A mapping rather than a set so :func:`_known` can list them, and so the meaning of each is
written down next to the name a file has to spell correctly.
"""

FUND_FREQUENCIES: Final[Mapping[str, str]] = {"monthly": "one payout a month"}
"""The distribution frequencies implemented. Monthly is what both Inzhur products declare;
a quarterly fund arrives as another entry here plus the date arithmetic, not as a branch."""

FUND_RECORD_DAYS: Final[Mapping[str, str]] = {
    "last_day_of_month": "entitlement is fixed on the last calendar day of the month"
}
"""The record-day rules implemented."""

FUND_BUYBACK_TERMS: Final[Mapping[str, str]] = {
    "discretionary": "the manager may buy back before termination, and is not obliged to"
}
"""What a регламент can say about an early exit. There is deliberately no ``guaranteed``
member: none of the declared funds owes one, and adding the word before a fund that owes it
exists would invite a file to claim it."""

_MAX_PAYMENT_DAY: Final = 28
"""The last day of the shortest month, so a declared payment day exists in every month."""


def _fund_source(path: Path, table: str, entry: Any) -> Provenance:
    """One fund table's citation. Every sourced table in a fund file goes through here."""
    return prov.of(
        [
            _source_ref(
                path,
                table,
                source=entry.source,
                retrieved_on=entry.retrieved_on,
                verified_on=entry.verified_on,
                kind=entry.kind,
            )
        ]
    )


def _fraction_in_range(path: Path, field_path: str, percent: float, what: str) -> float:
    """A declared percentage that must land in ``[0, 1]`` as a fraction.

    The markup and the discount are both shares of NAV, so a declared 150% is not an
    aggressive spread -- it is a number that cannot be a share of anything. Refused rather
    than clamped, as everywhere else at this boundary.
    """
    return _bounded(
        path,
        field_path,
        _as_fraction(_non_negative(path, field_path, percent, f"{what} cannot be negative")),
        f"{what} is a share of net asset value, so above 100% it is not a share at all",
    )


def _declared_yield(path: Path, table: schema.DeclaredYieldTable, *, prefix: str) -> DeclaredYield:
    """``[instrument.declared_yield]`` as the core record, range preserved as a range."""
    low = _as_fraction(
        _non_negative(
            path,
            f"{prefix}.low_pct",
            table.low_pct,
            "a fund stating a negative return is stating a loss, which this engine does "
            "not model as a yield",
        )
    )
    high = _as_fraction(
        _non_negative(path, f"{prefix}.high_pct", table.high_pct, "the same holds here")
    )
    if high < low:
        raise DeclarationError(
            path,
            f"{prefix}.high_pct",
            f"is {table.high_pct!r}, below the declared low of {table.low_pct!r}. A range "
            "whose ends are the wrong way round is a typo, and swapping them here would "
            "make the file's own statement unreadable.",
            "write the low end first",
        )
    basis = _known(path, f"{prefix}.basis", table.basis, FUND_BASIS, "declared-yield basis")
    return DeclaredYield(
        low=low,
        high=high,
        basis=cast('Literal["simple_annual", "usd_equivalent_annual"]', basis),
        provenance=_fund_source(path, prefix, table),
    )


def _peg(path: Path, table: schema.PegTable, *, prefix: str) -> Peg:
    """``[instrument.distribution.peg]`` as the core record, cap ladder oldest first."""
    entries: list[CapEntry] = []
    for index, entry in enumerate(table.cap):
        entry_prefix = f"{prefix}.cap[{index}]"
        effective_from = _parse_date(path, f"{entry_prefix}.effective_from", entry.effective_from)
        if entries and effective_from <= entries[-1].effective_from:
            raise DeclarationError(
                path,
                f"{entry_prefix}.effective_from",
                f"is {effective_from.isoformat()}, on or before the previous entry's "
                f"{entries[-1].effective_from.isoformat()}. The ladder is read in the "
                "order it is written and is not sorted here, for the same reason a tax "
                "schedule is not: a file whose order disagrees with its dates is one a "
                "human misreads.",
                "write the cap entries oldest first, with no repeated date",
            )
        entries.append(
            CapEntry(
                effective_from=effective_from,
                uah_per_unit=_positive(
                    path,
                    f"{entry_prefix}.uah_per_unit",
                    entry.uah_per_unit,
                    "a ceiling of zero or less would size every pegged payment at nothing, "
                    "which is not what an undeclared ceiling means",
                ),
                provenance=_fund_source(path, entry_prefix, entry),
            )
        )
    return Peg(
        sized_in=_currency(path, f"{prefix}.sized_in", table.sized_in),
        cap=tuple(entries),
    )


def _distribution(
    path: Path,
    table: schema.DistributionTable,
    *,
    prefix: str,
) -> DistributionTerms:
    """``[instrument.distribution]`` as the core record."""
    if not 1 <= table.payment_day <= _MAX_PAYMENT_DAY:
        raise DeclarationError(
            path,
            f"{prefix}.payment_day",
            f"is {table.payment_day!r}. A payment day must exist in every month, so it is "
            f"bounded at {_MAX_PAYMENT_DAY}: a fund declaring the 31st would pay in seven "
            "months of the year and silently skip the rest.",
            f"write a day between 1 and {_MAX_PAYMENT_DAY}",
        )
    frequency = _known(
        path, f"{prefix}.frequency", table.frequency, FUND_FREQUENCIES, "distribution frequency"
    )
    record_day = _known(
        path, f"{prefix}.record_day", table.record_day, FUND_RECORD_DAYS, "record-day rule"
    )
    return DistributionTerms(
        frequency=cast('Literal["monthly"]', frequency),
        basis_note=_require_text(
            path,
            f"{prefix}.basis_note",
            table.basis_note,
            "a payout whose declared basis nobody wrote down is one a reader cannot check "
            "against the fund's own documents",
        ),
        record_day=cast('Literal["last_day_of_month"]', record_day),
        payment_day=table.payment_day,
        paid_in=_currency(path, f"{prefix}.paid_in", table.paid_in),
        peg=None if table.peg is None else _peg(path, table.peg, prefix=f"{prefix}.peg"),
        payout_share=_fraction_in_range(
            path, f"{prefix}.payout_share_pct", table.payout_share_pct, "the payout share"
        ),
        provenance=_fund_source(path, prefix, table),
    )


def _spread(path: Path, table: schema.SpreadTable, *, prefix: str) -> SpreadTerms:
    """``[instrument.spread]`` as the core record, with the live settings kept separate."""
    maxima = {
        "entry_markup": _fraction_in_range(
            path, f"{prefix}.entry_markup_max_pct", table.entry_markup_max_pct, "an entry markup"
        ),
        "exit_discount": _fraction_in_range(
            path, f"{prefix}.exit_discount_max_pct", table.exit_discount_max_pct, "an exit discount"
        ),
    }
    live = {
        "entry_markup": _fraction_in_range(
            path, f"{prefix}.live_entry_markup_pct", table.live_entry_markup_pct, "an entry markup"
        ),
        "exit_discount": _fraction_in_range(
            path,
            f"{prefix}.live_exit_discount_pct",
            table.live_exit_discount_pct,
            "an exit discount",
        ),
    }
    for what, field in (
        ("entry_markup", "live_entry_markup_pct"),
        ("exit_discount", "live_exit_discount_pct"),
    ):
        if live[what] > maxima[what]:
            raise DeclarationError(
                path,
                f"{prefix}.{field}",
                f"declares a live {what.replace('_', ' ')} above the maximum the terms "
                f"allow ({live[what]!r} against {maxima[what]!r}). One of the two is "
                "wrong, and the engine cannot say which: charging the live figure would "
                "exceed the declared ceiling, and capping it would hide the disagreement.",
                "correct the live setting, or the maximum the terms declare",
            )
    return SpreadTerms(
        entry_markup_max=maxima["entry_markup"],
        exit_discount_max=maxima["exit_discount"],
        live_entry_markup=live["entry_markup"],
        live_exit_discount=live["exit_discount"],
        provenance=_fund_source(path, prefix, table),
    )


def _liquidity(path: Path, table: schema.LiquidityTable, *, prefix: str) -> LiquidityTerms:
    """``[instrument.liquidity]`` as two records, kept distinguishable."""
    legal_prefix = f"{prefix}.legal"
    practice_prefix = f"{prefix}.practice"
    buyback = _known(
        path,
        f"{legal_prefix}.buyback_before_termination",
        table.legal.buyback_before_termination,
        FUND_BUYBACK_TERMS,
        "pre-termination buyback term",
    )
    if not table.practice.is_revocable:
        raise DeclarationError(
            path,
            f"{practice_prefix}.is_revocable",
            "declares an observed practice that cannot be revoked, which is an obligation "
            "rather than a practice. The distinction is the whole reason the two are "
            "separate records: what the регламент owes and what the company currently "
            "does are different kinds of claim.",
            "declare it in [instrument.liquidity.legal] if the fund is actually obliged",
        )
    return LiquidityTerms(
        legal=LegalTerms(
            buyback_before_termination=cast('Literal["discretionary"]', buyback),
            settlement_business_days=_non_negative_days(
                path,
                f"{legal_prefix}.settlement_business_days",
                table.legal.settlement_business_days,
                "a settlement delay may be zero but not negative",
            ),
            note=_require_text(
                path,
                f"{legal_prefix}.note",
                table.legal.note,
                "the legal terms state in words what the fund owes, so a reader can check "
                "the citation against the claim",
            ),
            provenance=_fund_source(path, legal_prefix, table.legal),
        ),
        practice=ObservedPractice(
            settlement_business_days=_non_negative_days(
                path,
                f"{practice_prefix}.settlement_business_days",
                table.practice.settlement_business_days,
                "a settlement delay may be zero but not negative",
            ),
            is_revocable=True,
            note=_require_text(
                path,
                f"{practice_prefix}.note",
                table.practice.note,
                "an observed practice states in words what the company currently does, and "
                "that it may stop",
            ),
            provenance=_fund_source(path, practice_prefix, table.practice),
        ),
    )


def fund_from_file(path: Path) -> FundDeclaration:
    """One ``data/instruments/<id>.toml`` declaring a fund, as a ``FundDeclaration``.

    Nothing is inferred from the file *name*, as with a bond: a renamed file is the same
    declaration, and a file whose name disagrees with its ``id`` is not reinterpreted.
    """
    document = read_document(path)
    table = _validate(schema.FundFile, document, path).instrument
    prefix = INSTRUMENT_TABLE
    _known(
        path,
        f"{prefix}.class",
        table.instrument_class,
        {instrument_registry.COLLECTIVE_INVESTMENT_FUND: "a collective-investment fund"},
        "fund instrument class",
    )
    if not table.is_assumption_driven:
        raise DeclarationError(
            path,
            f"{prefix}.is_assumption_driven",
            "declares a fund whose figures are not assumption-driven. This engine has no "
            "such case: a fund's projections are contractual arithmetic over terms the "
            "fund states about itself, and the core field is Literal[True] so there is "
            "nothing for false to become. A fund with an observed price history is a "
            "different declaration and a different feature.",
            "declare is_assumption_driven = true, or declare a different instrument class",
        )
    currency = _currency(path, f"{prefix}.unit_currency", table.unit_currency)
    terminates_on = _parse_date(path, f"{prefix}.terminates_on", table.terminates_on)
    cutoff = _optional_date(path, f"{prefix}.subscription_cutoff", table.subscription_cutoff)
    if cutoff is not None and terminates_on < cutoff:
        raise DeclarationError(
            path,
            f"{prefix}.terminates_on",
            f"is {terminates_on.isoformat()}, before the subscription cutoff "
            f"{cutoff.isoformat()}. A fund that ends before it stops accepting money "
            "cannot be bought at all, and projecting it would report a holding nobody "
            "could have opened.",
            "correct whichever of the two dates is wrong",
        )
    nav_prefix = f"{prefix}.nav"
    return FundDeclaration(
        id=_require_text(
            path,
            f"{prefix}.id",
            table.id,
            "every declaration needs an identifier, because that is what a holding and a "
            "result refer to it by",
        ),
        name=_require_text(
            path,
            f"{prefix}.name",
            table.name,
            "a declaration a reader cannot recognise by name is one they cannot check",
        ),
        unit_currency=currency,
        is_assumption_driven=True,
        nav_per_unit=Money(
            _positive(
                path,
                f"{nav_prefix}.per_unit",
                table.nav.per_unit,
                "a unit worth nothing has no price for a markup to be a share of, and "
                "every figure computed from it would be zero while the projection still "
                "looked complete",
            ),
            currency,
            _fund_source(path, nav_prefix, table.nav),
        ),
        day_count=_known(
            path, f"{prefix}.day_count", table.day_count, conventions.DAY_COUNT_FNS, "day-count"
        ),
        declared_yield=_declared_yield(
            path, table.declared_yield, prefix=f"{prefix}.declared_yield"
        ),
        distribution=(
            None
            if table.distribution is None
            else _distribution(path, table.distribution, prefix=f"{prefix}.distribution")
        ),
        spread=_spread(path, table.spread, prefix=f"{prefix}.spread"),
        liquidity=_liquidity(path, table.liquidity, prefix=f"{prefix}.liquidity"),
        minimum_units=_positive(
            path,
            f"{prefix}.constraints.minimum_units",
            table.constraints.minimum_units,
            "a minimum of zero units is not a constraint, and declaring one would make "
            "every purchase feasible by definition",
        ),
        subscription_cutoff=cutoff,
        terminates_on=terminates_on,
        tax_classes=_tax_class_references(
            path, table.tax_classes, field_prefix=f"{prefix}.tax_classes"
        ),
        fee_context=tuple(
            FeeFact(
                what=_require_text(
                    path,
                    f"{prefix}.fee_fact[{index}].what",
                    entry.what,
                    "a fee fact recorded as context for the declared yield has to say what "
                    "it is, because nothing computes from it and the words are all there is",
                ),
                provenance=_fund_source(path, f"{prefix}.fee_fact[{index}]", entry),
            )
            for index, entry in enumerate(table.fee_fact)
        ),
        verification_tasks=tuple(
            VerificationTask(
                question=_require_text(
                    path,
                    f"{prefix}.verification_task[{index}].question",
                    entry.question,
                    "an open question with no question is not a task",
                ),
                searched=_require_text(
                    path,
                    f"{prefix}.verification_task[{index}].searched",
                    entry.searched,
                    "a task says which document was read, so the next reader does not read "
                    "it again",
                ),
                searched_on=_parse_date(
                    path,
                    f"{prefix}.verification_task[{index}].searched_on",
                    entry.searched_on,
                ),
            )
            for index, entry in enumerate(table.verification_task)
        ),
        groups=_group_labels(path, f"{prefix}.groups", table.groups),
    )


def declared_class_of(path: Path) -> str:
    """The ``[instrument] class`` of a declaration file, read without validating the rest.

    The resolver's dispatch key, and the only thing read before a loader is chosen. A bond
    file and a fund file share a directory and a root table and have almost nothing else in
    common, so *something* has to look first; reading one key is the smallest thing that
    can, and it fails naming the file when the key is missing rather than guessing.
    """
    document = read_document(path)
    table = document.get(INSTRUMENT_TABLE)
    if not isinstance(table, dict):
        raise DeclarationError(
            path,
            INSTRUMENT_TABLE,
            "is missing, so the file declares no instrument at all. Every declaration file "
            "under data/instruments/ has an [instrument] table naming what it declares.",
            "add an [instrument] table",
        )
    declared = table.get("class")
    if not isinstance(declared, str) or not declared.strip():
        raise DeclarationError(
            path,
            f"{INSTRUMENT_TABLE}.class",
            "is missing or empty, so nothing can say which kind of declaration this is. "
            "There is no default: reading an unlabelled file as a bond would fail later, "
            "against a field the reader never wrote.",
            'declare class = "fixed_income" or class = "collective_investment_fund"',
        )
    return declared


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
# 014-candidates: how many candidates one enumeration may produce
# ---------------------------------------------------------------------------
#
# `composition`'s reading, unchanged: an owner's own policy, no citation read and none
# expected, and **no default** -- a forgotten line must never read as a chosen one.
#
# The one refusal this loader owns is `max_candidates < 1`. A ceiling of zero admits nothing
# at all, so every run would refuse with the registry blameless; unlike the segment bound,
# there is no reading of a small number here that turns the feature off, because refusing is
# what exceeding the ceiling already does.

CANDIDATES_TABLE: Final = "candidates"
"""Root table of a candidate-ceiling file, and the prefix of every field path in one."""


def candidates_from_file(path: Path) -> tuple[str, CandidateCeiling]:
    """One ``data/candidates/<owner>.toml`` as its owner id and the declared ceiling.

    Returns the owner id beside the ceiling rather than folding it into the record, on
    :func:`composition_from_file`'s reasoning: the ceiling is a number and the owner is a
    property of the *file*.
    """
    document = read_document(path)
    file = _validate(schema.CandidatesFile, document, path)
    owner_id = _require_text(
        path,
        f"{OWNER_TABLE}.id",
        file.owner.id,
        "the candidate ceiling is one person's policy about his own registry, and it is "
        "resolved against that person's income streams (Principle VII)",
    )
    if file.candidates.max_candidates < 1:
        raise DeclarationError(
            path,
            f"{CANDIDATES_TABLE}.max_candidates",
            f"declares {file.candidates.max_candidates}, and an enumeration that may hold no "
            "candidate at all refuses every question -- including the ones the registry answers "
            "perfectly well. A ceiling is a statement about when enumeration has stopped being "
            "the right primitive, not a way to switch it off.",
            "write the largest number of candidates you are willing to have enumerated",
        )
    return owner_id, CandidateCeiling(max_candidates=file.candidates.max_candidates)


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
# **The mark on an estimated basis is built here and joined to the cost in the core.** This is
# where the owner's reason enters the system, so `core.ledger.seeds.basis_estimated` is called
# here to turn it into a `SourceRef` -- but the *join* between that mark and the amount happens
# in `seeds.seed_cost`, not in this function. The declared cost therefore rests on no cited
# source of its own (`prov.EMPTY`, the reading `data/streams/` already has for a salary), and a
# seed assembled without a file still reaches the ledger marked (008 FR-007).
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


def _basis(
    path: Path, entry: schema.SeedTable, *, field_prefix: str, declared_at: str
) -> seeds.Basis:
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
        declared_at=declared_at,
        reason=_require_text(
            path,
            f"{field_prefix}.reason",
            entry.reason,
            "an empty reason is not a reason: a mark that cannot say what it rests on is a "
            "taint flag rather than provenance",
        ),
        estimated_for=_parse_date(path, f"{field_prefix}.acquired_on", entry.acquired_on),
    )


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
        declared_at = source_id(path, field_prefix)
        basis = _basis(path, entry, field_prefix=field_prefix, declared_at=declared_at)
        declared.append(
            SeedLot(
                owner_id=owner_id,
                lot_id=f"{SEED_TABLE}-{position}",
                declared_at=declared_at,
                is_synthetic=entry.is_synthetic,
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
                    # The declared amount rests on no cited source: an owner's own record is
                    # not an observation, the reading `data/streams/` already takes for a
                    # salary. Where the cost is a *guess*, the mark that says so travels on
                    # `basis` and `core.ledger.seeds.seed_cost` joins the two -- so a lot the
                    # loader never saw carries it too, and this boundary is not the only thing
                    # standing between a guessed cost and an unmarked tax (008 FR-007).
                    prov.EMPTY,
                ),
                basis=basis,
            )
        )
    return owner_id, tuple(declared)


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
                is_synthetic=entry.is_synthetic,
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


# ---------------------------------------------------------------------------
# 007-cpi-real-terms: the CPI series and the inflation assumption
# ---------------------------------------------------------------------------
#
# Same four responsibilities -- read, shape, meaning, construct -- over two declarations of
# opposite epistemic kinds, and the difference is the whole point of loading them separately.
#
# A CPI file is the most heavily cited declaration in the project: **one `SourceRef` per
# observation**, 411 of them in the shipped Ukrainian series. Not one per file, which would
# collapse into a single ref in a frozenset and make a real figure over a long window look as
# though it rested on one thing. It rests on every month it chained, and research.md D6 says
# to report that honestly rather than summarise it.
#
# An inflation assumption is a *belief*, and carries `is_assumption` where an observation
# carries a source. An external forecast may carry a citation as well -- and is still an
# assumption (FR-010).
#
# **No network, no cache, and no knowledge that a fetcher exists.** `scripts/fetch_cpi.py`
# wrote `data/cpi/ua.toml` and is tooling outside the package; this module reads a committed
# file (research.md D10, Principle III).
#
# What is *not* here, because it needs a second file: whether two series declare one identity.
# That is a relation and lives in the resolver, where the whole set is in hand.

CPI_SERIES_TABLE: Final = "series"
"""The identity table of a CPI file, and the prefix of every field path in it."""

CPI_OBSERVATION_TABLE: Final = "observation"
"""The observation array of a CPI file."""

INFLATION_ASSUMPTION_TABLE: Final = "inflation_assumption"
"""Root table of an inflation-assumption file."""

_PERIODICITIES: Final[Mapping[str, Periodicity]] = {"monthly": "monthly"}
"""The publication cadences this engine can annualise, keyed by their declared name.

A registry with one entry rather than a bare string comparison, so an unknown cadence fails
naming what would have worked (FR-021's pattern) instead of silently annualising a quarterly
series by twelve -- which is wrong by a factor of three and produces a plausible number.
"""

_MINIMUM_ANNUAL_RATE: Final = -1.0
"""Prices cannot fall to nothing. The bound that keeps the Fisher denominator away from zero."""


def _cpi_period(path: Path, field_path: str, period: str, periodicity: Periodicity) -> str:
    """A declared period, checked against the series' declared periodicity.

    For a monthly series that means ``YYYY-MM`` and nothing else: ``2025-01-15`` is a day,
    ``2025-Q1`` is a quarter and ``2025`` is a year, and each of them would chain into a
    figure covering a span nobody declared. The message names both the value and the
    periodicity it failed, because the fix is one or the other.
    """
    match periodicity:
        case "monthly":
            if periods.is_period(period):
                return period
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(periodicity)
    raise DeclarationError(
        path,
        field_path,
        f"declares the period {period!r}, which is not a whole month and so does not conform "
        f"to this series' declared {periodicity!r} periodicity. Periods are not reinterpreted: "
        "reading a day or a quarter as a month would chain a value into a figure covering a "
        "span nobody declared.",
        "write the period as YYYY-MM, in quotes",
    )


def _elapsed_when_retrieved(path: Path, field_path: str, period: str, retrieved_on: date) -> None:
    """Refuse an observation whose period had not ended when the value was read.

    A published index for a month covers a month that has **finished**. A value for a month
    still running is a forecast wearing an observation's clothes, and it would chain into a
    real figure indistinguishable from a measured one -- the exact confusion FR-010 exists to
    prevent, arriving through the back door.

    Aged against the observation's **own** ``retrieved_on`` rather than a clock, so the same
    file loads the same way for ever. There is no wall clock in this project and there is not
    one here either: a run's ``as_of`` answers staleness, and this is not a staleness question.
    """
    retrieval_month = periods.month_of(retrieved_on)
    if period >= retrieval_month:
        raise DeclarationError(
            path,
            field_path,
            f"declares a value for {period!r} but was retrieved on "
            f"{retrieved_on.isoformat()}, in {retrieval_month}. A published price index covers "
            "a period that has ended, so a value read before its own period finished is a "
            "forecast rather than an observation -- and a forecast chained into a real figure "
            "would be indistinguishable from a measured one.",
            "remove the row, or re-fetch the series once the period has been published",
        )


def cpi_from_file(path: Path) -> CpiSeries:
    """One ``data/cpi/<economy>.toml`` as a :class:`~terezy.core.inflation.series.CpiSeries`.

    Every refusal below is a property of this one file read in isolation, and every one names
    the file and the offending field or period (FR-003):

    * **An empty series.** A file declaring no observations would make every window uncovered
      for a reason naming the *window*, sending the reader to the wrong place.
    * **A non-positive index value.** See :class:`schema.CpiObservationTable.value`.
    * **A period that does not conform to the declared periodicity**, and an unknown
      periodicity, both with the alternatives listed.
    * **A period that had not elapsed when the value was retrieved.**
    * **A duplicate period**, and **periods running backwards**. Strictly ascending is what
      "overlapping" means for a series of whole months, and a file that jumps backwards is one
      somebody edited twice.

    **Gaps between declared months are permitted** and load. A month the publisher did not
    publish is a fact about the world, and FR-004 forbids inventing one. The refusal for a gap
    belongs to ``core.inflation.series.coverage``, which knows the window being asked about
    and can name the missing month for *that* question.
    """
    document = read_document(path)
    file = _validate(schema.CpiFile, document, path)
    series_id = _require_text(
        path,
        f"{CPI_SERIES_TABLE}.id",
        file.series.id,
        "a series is referred to by id from every figure it deflates, and two series "
        "declaring one id are refused across the whole data root",
    )
    periodicity = _PERIODICITIES[
        _known(
            path,
            f"{CPI_SERIES_TABLE}.periodicity",
            file.series.periodicity,
            _PERIODICITIES,
            "publication periodicity this engine can annualise",
        )
    ]
    if not file.observation:
        raise DeclarationError(
            path,
            CPI_OBSERVATION_TABLE,
            "declares no observations. An empty series is reported rather than read as 'prices "
            "never moved': every deflation window would come back uncovered for a reason "
            "naming the window, which would send a reader to check the wrong thing.",
            "declare at least one [[observation]], or delete the file",
        )

    observations: list[CpiObservation] = []
    seen: dict[str, int] = {}
    for position, entry in enumerate(file.observation):
        field_prefix = f"{CPI_OBSERVATION_TABLE}[{position}]"
        period = _cpi_period(path, f"{field_prefix}.period", entry.period, periodicity)
        if period in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.period",
                f"declares {period!r} for the second time; entry {seen[period]} of this file "
                "already declares it. The two are not merged and neither wins: one value per "
                "period is what makes a chained product reproducible, and a repeated period is "
                "a file that was edited twice.",
                "delete the duplicate entry",
            )
        if observations and period <= observations[-1].period:
            raise DeclarationError(
                path,
                f"{field_prefix}.period",
                f"declares {period!r} after {observations[-1].period!r}, so the series runs "
                "backwards here. Observations are declared in strictly ascending order and are "
                "not reordered: a series that jumps backwards is one somebody edited twice, and "
                "sorting it silently would hide which edit was meant.",
                "put the observations in calendar order",
            )
        seen[period] = position
        retrieved_on = _parse_date(path, f"{field_prefix}.retrieved_on", entry.retrieved_on)
        _elapsed_when_retrieved(path, f"{field_prefix}.period", period, retrieved_on)
        observations.append(
            CpiObservation(
                period=period,
                value=_positive(
                    path,
                    f"{field_prefix}.value",
                    entry.value,
                    "a price index is a strictly positive factor: 100.9 means prices rose 0.9% "
                    "that month. Zero or below would make the chained product zero or negative "
                    "and leave the real rate undefined",
                ),
                kind=_require_text(
                    path,
                    f"{field_prefix}.kind",
                    entry.kind,
                    "every observation names the kind it ages under, and there is no default "
                    "staleness threshold (FR-028)",
                ),
                provenance=prov.of(
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
                ),
            )
        )
    return CpiSeries(
        id=series_id,
        country=_require_text(
            path,
            f"{CPI_SERIES_TABLE}.country",
            file.series.country,
            "a series states which economy it measures; that is half of what makes a second "
            "country's index a data-only addition (FR-002)",
        ),
        index=_require_text(
            path,
            f"{CPI_SERIES_TABLE}.index",
            file.series.index,
            "a series states which index it is; two indices for one country are two series",
        ),
        periodicity=periodicity,
        base=_require_text(
            path,
            f"{CPI_SERIES_TABLE}.base",
            file.series.base,
            "the form the values are in decides how they chain, and reading a month-on-month "
            "series as a level index gives a wrong answer that looks entirely plausible",
        ),
        observations=tuple(observations),
    )


def _forecast_citation(
    path: Path, table: schema.InflationAssumptionTable
) -> tuple[Provenance | None, str | None]:
    """An external forecast's citation and staleness kind, or ``(None, None)`` for a belief.

    Three keys decide it together -- ``source``, ``retrieved_on`` and ``kind`` -- and they are
    all empty or all filled. A **half-filled** citation is refused rather than half-read: a
    source with no retrieval date is a quotation nobody can date, and a retrieval date with no
    source is a date attached to nothing. Either one is an edit somebody abandoned, and
    guessing which half was meant would put an unfinished claim in the output.

    ``verified_on`` is not part of that group and may be empty either way, exactly as it is on
    an observation -- and verifying a forecast vouches for the *quotation*, never for the
    number.
    """
    declared = {
        "source": table.source.strip(),
        "retrieved_on": table.retrieved_on.strip(),
        "kind": table.kind.strip(),
    }
    filled = {name for name, value in declared.items() if value}
    if not filled:
        if table.verified_on.strip():
            raise DeclarationError(
                path,
                f"{INFLATION_ASSUMPTION_TABLE}.verified_on",
                "declares a verification date for an assumption that cites no source. There is "
                "nothing to have verified it against: the owner's own belief about future "
                "inflation has no publisher, and a date here would claim a check that cannot "
                "have happened.",
                "leave verified_on empty, or declare the forecast's source, retrieved_on and "
                "kind as well",
            )
        return None, None
    missing = sorted(set(declared) - filled)
    if missing:
        raise DeclarationError(
            path,
            f"{INFLATION_ASSUMPTION_TABLE}.{missing[0]}",
            f"is empty while {sorted(filled)} are declared, so this assumption cites a source "
            "only halfway. An external forecast carries its citation, its retrieval date and "
            "its staleness kind together; a partial one is an edit somebody abandoned, and "
            "there is no honest way to guess which half was meant.",
            f"declare {missing}, or clear source, retrieved_on and kind to declare the owner's "
            "own belief instead",
        )
    return (
        prov.of(
            [
                _source_ref(
                    path,
                    INFLATION_ASSUMPTION_TABLE,
                    source=table.source,
                    retrieved_on=table.retrieved_on,
                    verified_on=table.verified_on,
                    kind=table.kind,
                )
            ]
        ),
        declared["kind"],
    )


def inflation_assumption_from_file(path: Path) -> tuple[str, InflationAssumption]:
    """One ``data/scenarios/inflation/<owner>.toml`` as its owner id and the declared belief.

    Returns the owner id beside the record rather than folding it into it, on
    ``spendable_from_file``'s precedent: the belief is a rate and the owner is a property of
    the *file*.

    **Exempt from the citation requirement, and it carries something else instead.** A belief
    about next year's prices has no publisher; ``is_assumption`` is what it carries where an
    observation carries a source. An external published forecast *may* carry a citation as
    well and remains an assumption (FR-010) -- cited does not make it observed, because there
    is no primary source for a year that has not happened.

    Two refusals are this function's own. ``is_assumption = false`` is refused, because the
    field exists to make the claim unmissable in the output rather than to be switched off. A
    rate at or below -100% is refused, because prices cannot fall to nothing and every real
    rate against such a figure would be infinite.
    """
    document = read_document(path)
    table = _validate(schema.InflationAssumptionFile, document, path).inflation_assumption
    if not table.is_assumption:
        raise DeclarationError(
            path,
            f"{INFLATION_ASSUMPTION_TABLE}.is_assumption",
            "is declared false. A future-inflation rate is always an assumption: nobody knows "
            "next year's prices, and FR-010 requires the figure be presented as a stated "
            "belief rather than as a measurement. The field exists to make that unmissable in "
            "the output, not to be switched off -- which is why the core types it as a Literal "
            "admitting one value.",
            "write is_assumption = true, or declare the value in data/cpi/ where an observation "
            "belongs",
        )
    annual_rate = _as_fraction(table.annual_rate_pct)
    if annual_rate <= _MINIMUM_ANNUAL_RATE:
        raise DeclarationError(
            path,
            f"{INFLATION_ASSUMPTION_TABLE}.annual_rate_pct",
            f"declares {table.annual_rate_pct!r}%, which is prices falling to nothing or worse. "
            "Every real rate deflated by it would be infinite or undefined. The value is "
            "refused rather than corrected: clamping it would put a belief in the model that "
            "no file declares.",
            "write a percentage above -100",
        )
    provenance, kind = _forecast_citation(path, table)
    return (
        _require_text(
            path,
            f"{INFLATION_ASSUMPTION_TABLE}.owner_id",
            table.owner_id,
            "a belief about the future is one person's, and every declaration carries its "
            "owner from the first commit (Principle VII)",
        ),
        InflationAssumption(
            id=_require_text(
                path,
                f"{INFLATION_ASSUMPTION_TABLE}.id",
                table.id,
                "the run manifest records which assumption produced a result, so two runs with "
                "two different beliefs are two results rather than one (FR-015)",
            ),
            annual_rate=annual_rate,
            is_assumption=True,
            rationale=_require_text(
                path,
                f"{INFLATION_ASSUMPTION_TABLE}.rationale",
                table.rationale,
                "the rationale is what an assumption carries where an observation carries a "
                "source: it is the owner's stated belief in words, and a figure conditional on "
                "an unexplained guess cannot be argued with",
            ),
            provenance=provenance,
            kind=kind,
        ),
    )


# ---------------------------------------------------------------------------
# 015-the-question: the belief an early exit is struck under
# ---------------------------------------------------------------------------

EARLY_EXIT_TABLE: Final = "early_exit"
"""Root table of an early-exit belief file, and the prefix of every field path in one."""


def early_exit_from_file(path: Path) -> tuple[str, SpreadHolds]:
    """One ``data/scenarios/early_exit/<owner>.toml`` as its owner id and the declared belief.

    ``inflation_assumption_from_file``'s shape, with **no citation read and none expected**: a
    platform that committed to its quoted buyback price would have declared a term on the
    access record, so a source here would replace the belief rather than vouch for it.
    """
    document = read_document(path)
    table = _validate(schema.EarlyExitFile, document, path).early_exit
    if not table.is_assumption:
        raise DeclarationError(
            path,
            f"{EARLY_EXIT_TABLE}.is_assumption",
            "is declared false. Whether a quoted spread still holds on a future date is nobody's "
            "observation: a platform that committed to its price would have declared a term, "
            "and the term would live on the access declaration beside the price. The field "
            "exists to make the belief unmissable on every figure it touches, not to be "
            "switched off -- which is why the core types it as a Literal admitting one value.",
            "write is_assumption = true, or declare the committed price as an access term",
        )
    return (
        _require_text(
            path,
            f"{EARLY_EXIT_TABLE}.owner_id",
            table.owner_id,
            "a belief about the future is one person's, and every declaration carries its "
            "owner from the first commit (Principle VII)",
        ),
        SpreadHolds(
            id=_require_text(
                path,
                f"{EARLY_EXIT_TABLE}.id",
                table.id,
                "every outcome computed through the belief names it, so a reader can find the "
                "file the assumption is stated in",
            ),
            is_assumption=True,
            rationale=_require_text(
                path,
                f"{EARLY_EXIT_TABLE}.rationale",
                table.rationale,
                "the rationale is what an assumption carries where an observation carries a "
                "source: a figure conditional on an unexplained guess cannot be argued with",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# 009-tax-depth: the assessment rules, and the owner's positions on them
# ---------------------------------------------------------------------------
#
# Two loaders, split by what the file *is*. `data/tax/timing/` is cited law and every table
# carrying an observed value needs a citation; `data/scenarios/tax/` is the owner's own
# statements and needs none, on the exemption `data/scenarios/` already carries.
#
# Every closed set below is resolved against the core's own enums rather than re-listed here,
# so a value the engine cannot act on fails at load naming the file, the field, and what would
# have worked.

TIMING_TABLE: Final = "timing"
"""Root table of an assessment-rules file, and the prefix of every field path in one."""

POSITIONS_TABLE: Final = "tax_positions"
"""Root table of an owner's tax-positions file."""

_MONTHS_IN_YEAR: Final = 12
_SHORTEST_MONTH: Final = 28
"""The day of a recurring deadline is capped at 28 so that no declared deadline can fail to
exist in some year. A 30 April deadline is fine and a 30 February one is not a deadline."""


def _closed_value[T](
    path: Path,
    field_path: str,
    value: str,
    members: Mapping[str, T],
    what: str,
) -> T:
    """One member of a closed set the core defines, or a failure listing the set.

    The mapping is built from the core's own enum at each call site, so this cannot drift from
    what the engine can act on: a member added to the enum is offered here without an edit.
    """
    if value not in members:
        raise DeclarationError(
            path,
            field_path,
            f"is {value!r}, which is not a {what} this engine implements.",
            f"use one of: {', '.join(sorted(members))}",
        )
    return members[value]


def _annual_date(path: Path, field_prefix: str, month: int, day: int) -> tax_year.AnnualDate:
    """A recurring deadline: a month and a day, checked so it exists in every year."""
    if not 1 <= month <= _MONTHS_IN_YEAR:
        raise DeclarationError(
            path,
            f"{field_prefix}_month",
            f"is {month!r}, which is not a month.",
            "declare a month from 1 to 12",
        )
    if not 1 <= day <= _SHORTEST_MONTH:
        raise DeclarationError(
            path,
            f"{field_prefix}_day",
            f"is {day!r}. A deadline is capped at the 28th so that it exists in every month "
            "of every year: a 30 February deadline is not a deadline, and a rule that "
            "silently moved it would be inventing one.",
            "declare a day from 1 to 28",
        )
    return tax_year.AnnualDate(month=month, day=day)


def _timing_category(
    path: Path, entry: schema.TimingCategoryTable
) -> tuple[tax_year.IncomeCategory, tax_year.TimingRule]:
    """One ``[[timing.category]]`` as the two records it declares: how it nets, and when."""
    field_prefix = f"{TIMING_TABLE}.category[{entry.id}]"
    identifier = _require_text(
        path,
        f"{field_prefix}.id",
        entry.id,
        "a category is referred to by id from every tax class that belongs to it",
    )
    _require_text(
        path,
        f"{field_prefix}.note",
        entry.note,
        "a category states in words what it claims, so a reader can check the citation "
        "against the claim",
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
    category = tax_year.IncomeCategory(
        id=identifier,
        treatment=_closed_value(
            path,
            f"{field_prefix}.treatment",
            entry.treatment,
            {member.value: member for member in tax_year.Treatment},
            "netting treatment",
        ),
        carryforward=_closed_value(
            path,
            f"{field_prefix}.carryforward",
            entry.carryforward,
            {member.value: member for member in tax_year.Carryforward},
            "carryforward rule",
        ),
        note=entry.note,
        provenance=sources,
    )
    rule = tax_year.TimingRule(
        category_id=identifier,
        settlement=_closed_value(
            path,
            f"{field_prefix}.settlement",
            entry.settlement,
            {member.value: member for member in tax_year.SettlementBehaviour},
            "settlement behaviour",
        ),
        declare_by=_annual_date(
            path, f"{field_prefix}.declare_by", entry.declare_by_month, entry.declare_by_day
        ),
        pay_by=_annual_date(path, f"{field_prefix}.pay_by", entry.pay_by_month, entry.pay_by_day),
        non_business_day_rule=_known(
            path,
            f"{field_prefix}.non_business_day_rule",
            entry.non_business_day_rule,
            conventions.BUSINESS_DAY_FNS,
            "business-day convention",
        ),
        note=entry.note,
        provenance=sources,
    )
    return category, rule


def _lot_method(path: Path, entry: schema.LotMethodTable) -> tax_year.MethodStanding:
    """One ``[[timing.lot_method]]`` as the finding it records about the law."""
    field_prefix = f"{TIMING_TABLE}.lot_method[{entry.method}]"
    return tax_year.MethodStanding(
        method=_closed_value(
            path,
            f"{field_prefix}.method",
            entry.method,
            {member.value: member for member in lots.LotMethod},
            "basis method",
        ),
        verdict=_closed_value(
            path,
            f"{field_prefix}.verdict",
            entry.verdict,
            {member.value: member for member in tax_year.MethodVerdict},
            "legal-standing verdict",
        ),
        what_the_law_says=_require_text(
            path,
            f"{field_prefix}.what_the_law_says",
            entry.what_the_law_says,
            "a verdict about the law is unreadable without the finding in words -- and a "
            "figure produced under this method carries it to the reader",
        ),
        provenance=prov.of(
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
        ),
    )


@dataclass(frozen=True, slots=True)
class TimingDeclaration:
    """One ``data/tax/timing/<jurisdiction>.toml``, before the class references are resolved.

    The class-to-category mapping is carried as declared text rather than resolved here,
    because resolving it needs every rate pack parsed first -- the same boundary an
    instrument's ``tax_classes`` sits on.
    """

    jurisdiction_id: str
    tax_currency: Currency
    official_rate_series: str | None
    """The id of the series this jurisdiction declares for its tax currency, or ``None``.

    Carried as declared text rather than resolved here, on ``category_of_class``'s precedent:
    resolving it needs every official-rate file parsed first, which is the resolver's boundary
    and the only place that can name both files.
    """

    categories: tuple[tax_year.IncomeCategory, ...]
    timing: tuple[tax_year.TimingRule, ...]
    methods: tuple[tax_year.MethodStanding, ...]
    category_of_class: Mapping[str, str]


def timing_from_file(path: Path) -> TimingDeclaration:
    """One assessment-rules file, validated as far as one file can be."""
    document = read_document(path)
    table = _validate(schema.TimingFile, document, path).timing
    jurisdiction = _require_text(
        path,
        f"{TIMING_TABLE}.jurisdiction",
        table.jurisdiction,
        "the rules belong to a jurisdiction, and the rate pack they govern names the same one",
    )
    currency = _currency(path, f"{TIMING_TABLE}.tax_currency", table.tax_currency)
    if not table.category:
        raise DeclarationError(
            path,
            f"{TIMING_TABLE}.category",
            "declares no income category, so no tax class in this jurisdiction could be "
            "assessed at all.",
            "declare at least one [[timing.category]]",
        )
    built = [_timing_category(path, entry) for entry in table.category]
    categories = tuple(category for category, _ in built)
    _no_duplicates(path, f"{TIMING_TABLE}.category", [category.id for category in categories])
    methods = tuple(_lot_method(path, entry) for entry in table.lot_method)
    _no_duplicates(
        path,
        f"{TIMING_TABLE}.lot_method",
        [standing.method.value for standing in methods],
    )
    declared = {category.id for category in categories}
    mapping: dict[str, str] = {}
    for index, entry in enumerate(table.class_):
        field_prefix = f"{TIMING_TABLE}.class[{index}]"
        if entry.category not in declared:
            raise DeclarationError(
                path,
                f"{field_prefix}.category",
                f"names the income category {entry.category!r}, which this file does not "
                "declare. A class mapped to a category nobody defined could not be netted, "
                "charged per event, or excluded -- three different answers.",
                "declare it as a [[timing.category]], or use one of: "
                f"{', '.join(sorted(declared))}",
            )
        if entry.tax_class in mapping:
            raise DeclarationError(
                path,
                f"{field_prefix}.tax_class",
                f"maps {entry.tax_class!r} to a second category. One class belongs to one "
                "category: whichever mapping the lookup reached first would win by accident "
                "of file order.",
                "delete one of the two entries",
            )
        mapping[entry.tax_class] = entry.category
    return TimingDeclaration(
        jurisdiction_id=jurisdiction,
        tax_currency=currency,
        official_rate_series=table.official_rate_series,
        categories=categories,
        timing=tuple(rule for _, rule in built),
        methods=methods,
        category_of_class=mapping,
    )


def _no_duplicates(path: Path, field_path: str, identifiers: list[str]) -> None:
    """Every id in one list appears once, or a failure naming the repeat.

    Collapsing a duplicate silently would leave whichever entry loaded second in force, and
    the file would read as though the first one were.
    """
    seen: set[str] = set()
    for identifier in identifiers:
        if identifier in seen:
            raise DeclarationError(
                path,
                field_path,
                f"declares {identifier!r} more than once.",
                "delete the duplicate entry",
            )
        seen.add(identifier)


def tax_positions_from_file(
    path: Path,
) -> tuple[tax_year.FilingDecisions, tax_year.UnsettledPositions]:
    """One ``data/scenarios/tax/<owner>.toml``: what was filed, and the two positions taken.

    No citation is required and none is accepted: whether a declaration was filed is a fact
    only the owner can state, and a position on an unsettled reading is a belief.
    ``is_assumption = true`` is what each carries where an observation carries a source.
    """
    document = read_document(path)
    table = _validate(schema.TaxPositionsFile, document, path).tax_positions
    owner = _require_text(
        path,
        f"{POSITIONS_TABLE}.owner_id",
        table.owner_id,
        "a tax position is one person's declaration about his own returns, and every figure "
        "built from it carries him (Principle VII)",
    )
    by_year: dict[int, bool] = {}
    for index, entry in enumerate(table.filing):
        field_prefix = f"{POSITIONS_TABLE}.filing[{index}]"
        if entry.year in by_year:
            raise DeclarationError(
                path,
                f"{field_prefix}.year",
                f"declares the {entry.year} filing decision twice.",
                "delete the duplicate entry",
            )
        _require_text(
            path,
            f"{field_prefix}.note",
            entry.note,
            "a filing decision states in words what it rests on -- a record, or a fixture",
        )
        by_year[entry.year] = entry.filed
    return (
        tax_year.FilingDecisions(
            owner_id=owner,
            declared_at=f"{path.parent.name}/{path.name}#{POSITIONS_TABLE}.filing",
            by_year=by_year,
        ),
        tax_year.UnsettledPositions(
            chain=tax_year.ChainContinuity(
                position=_closed_value(
                    path,
                    f"{POSITIONS_TABLE}.carryforward_chain.position",
                    table.carryforward_chain.position,
                    {member.value: member for member in tax_year.ChainPosition},
                    "carryforward-chain position",
                ),
                switch=_unsettled_switch(
                    path,
                    "carryforward_chain",
                    question=table.carryforward_chain.question,
                    position=table.carryforward_chain.position,
                    rationale=table.carryforward_chain.rationale,
                    resolution_path=table.carryforward_chain.resolution_path,
                    is_assumption=table.carryforward_chain.is_assumption,
                ),
            ),
            method=tax_year.SelfDeclarantMethod(
                method=_closed_value(
                    path,
                    f"{POSITIONS_TABLE}.self_declarant_method.method",
                    table.self_declarant_method.method,
                    {member.value: member for member in lots.LotMethod},
                    "basis method",
                ),
                switch=_unsettled_switch(
                    path,
                    "self_declarant_method",
                    question=table.self_declarant_method.question,
                    position=table.self_declarant_method.method,
                    rationale=table.self_declarant_method.rationale,
                    resolution_path=table.self_declarant_method.resolution_path,
                    is_assumption=table.self_declarant_method.is_assumption,
                ),
            ),
        ),
    )


def _unsettled_switch(
    path: Path,
    table_name: str,
    *,
    question: str,
    position: str,
    rationale: str,
    resolution_path: str,
    is_assumption: bool,
) -> tax_year.UnsettledSwitch:
    """One declared position on a question no source answers, with its label.

    ``is_assumption`` must be true. The field is not decoration: it is what this record
    carries where an observation carries a citation, and a position declared as anything else
    would be presented as a finding by every figure that rests on it.
    """
    field_prefix = f"{POSITIONS_TABLE}.{table_name}"
    if not is_assumption:
        raise DeclarationError(
            path,
            f"{field_prefix}.is_assumption",
            "is false. A position on a question no source answers is an assumption by "
            "definition: declaring it otherwise would let a belief render as a finding on "
            "every figure it touches.",
            "set is_assumption = true, or find a citation and declare the rule instead",
        )
    for name, value in (("question", question), ("rationale", rationale)):
        _require_text(
            path,
            f"{field_prefix}.{name}",
            value,
            "an unsettled position is only usable by a reader who can see what was open and "
            "why this branch was taken",
        )
    return tax_year.UnsettledSwitch(
        question=question,
        position=position,
        resolution_path=_require_text(
            path,
            f"{field_prefix}.resolution_path",
            resolution_path,
            "a label nobody can retire is a permanent one; the path is what would replace "
            "this belief with a citation",
        ),
        declared_at=f"{path.parent.name}/{path.name}#{field_prefix}",
    )


# ---------------------------------------------------------------------------
# 010-full-tuple: how an instrument is reached
# ---------------------------------------------------------------------------
#
# Same four responsibilities in the same order -- read, shape, meaning, construct -- and the
# same rule that no pydantic type crosses this line.
#
# What is checked here is everything true of one file read in isolation: the list is
# non-empty, ids and labels are not blank, a duplicate ``instrument_id`` within the file is
# refused, the price is positive and its currency is one this engine models, and the citation
# is complete.
#
# What is **not** here, because each needs a second file: whether the instrument exists,
# whether the venues exist and can hold its currency, whether the quote's currency is the
# instrument's own, and whether this kind of instrument is entitled to declare a price at all.
# Four relations, and all four live in the resolver where the whole set is in hand and both
# files can be named.

ACCESS_TABLE: Final = "access"
"""Root array of an access file, and the prefix of every field path in one."""


def access_from_file(path: Path) -> tuple[InstrumentAccess, ...]:
    """One ``data/access/<name>.toml`` as the access declarations it makes.

    A tuple rather than a mapping: the resolver keys them, because a duplicate *across* files
    is its question and reporting it needs both file names.
    """
    file = _validate(schema.AccessFile, read_document(path), path)
    if not file.access:
        raise DeclarationError(
            path,
            ACCESS_TABLE,
            "declares no access entries. An empty list is reported rather than read as 'no "
            "instrument can be reached': every tuple naming an instrument would refuse for a "
            "missing declaration, and a comparison emptied by a forgotten line looks exactly "
            "like one emptied by a genuine gap in the registry.",
            "declare at least one [[access]] entry, or delete the file",
        )
    declared: list[InstrumentAccess] = []
    seen: dict[str, int] = {}
    for position, entry in enumerate(file.access):
        prefix = f"{ACCESS_TABLE}[{position}]"
        instrument_id = _require_text(
            path,
            f"{prefix}.instrument_id",
            entry.instrument_id,
            "an access declaration says how one named instrument is reached, and it is "
            "resolved against the declared instruments",
        )
        if instrument_id in seen:
            raise DeclarationError(
                path,
                f"{prefix}.instrument_id",
                f"declares how {instrument_id!r} is reached for the second time; entry "
                f"{seen[instrument_id]} of this file already does. The two are not merged and "
                "neither wins: an instrument reached two ways is two declarations only once "
                "there is a term to tell them apart, and until then a repeated id is a file "
                "that was edited twice.",
                "delete the duplicate entry",
            )
        seen[instrument_id] = position
        declared.append(
            InstrumentAccess(
                instrument_id=instrument_id,
                bought_at=_require_text(
                    path,
                    f"{prefix}.bought_at",
                    entry.bought_at,
                    "the purchase happens at a named venue, and that venue is the far end the "
                    "funding route has to reach (FR-004)",
                ),
                proceeds_to=_require_text(
                    path,
                    f"{prefix}.proceeds_to",
                    entry.proceeds_to,
                    "the instrument's proceeds land at a named venue, and that venue is where "
                    "the exit route has to depart from (FR-004)",
                ),
                quote=_access_price(path, f"{prefix}.price", entry.price),
                resale_price=_access_price(path, f"{prefix}.resale_price", entry.resale_price),
                risk_class=_require_text(
                    path,
                    f"{prefix}.risk_class",
                    entry.risk_class,
                    "the risk class is the fifth term of the unit of analysis and is carried "
                    "into every outcome; it is declared and never scored",
                ),
            )
        )
    return tuple(declared)


def _access_price(
    path: Path, field: str, declared: schema.AccessPriceTable | None
) -> VenueQuote | None:
    """One declared quote and the kind it ages under, or ``None`` where the table is absent.

    ``field`` is the whole dotted path, because the same table shape is declared twice: what a
    unit costs, and what it sells for (015 FR-031). ``None`` is a *statement* either way and is
    returned without judgement -- whether this instrument is entitled to make it is a relation
    between two files and belongs to the resolver.

    ``check_kind=False`` is passed to :func:`_source_ref` because the kind is also carried into
    the record and checked at the field it becomes -- the same reading a leg's
    ``kind_of_observation`` gets. The citation is stamped with it either way, and *resolving*
    the name against the declared kinds is the resolver's, which reads a second file to do it.
    """
    if declared is None:
        return None
    return VenueQuote(
        price=Money(
            _positive(
                path,
                f"{field}.per_unit",
                declared.per_unit,
                "a unit costs something. A price of zero or below would make a purchase "
                "acquire unlimited units from any amount, and every figure downstream of it "
                "meaningless rather than merely large",
            ),
            _currency(path, f"{field}.currency", declared.currency),
            prov.of(
                [
                    _source_ref(
                        path,
                        field,
                        source=declared.source,
                        retrieved_on=declared.retrieved_on,
                        verified_on=declared.verified_on,
                        # Checked below, at ``VenueQuote.kind``, naming ``[access.price].kind``.
                        kind=declared.kind,
                        check_kind=False,
                    )
                ]
            ),
        ),
        kind=_require_text(
            path,
            f"{field}.kind",
            declared.kind,
            "a venue quote ages under a declared threshold, and there is no default one "
            "(FR-028): a price whose kind nobody named could never be reported stale",
        ),
    )


# ---------------------------------------------------------------------------
# 011-official-rate: the declared official-rate series
# ---------------------------------------------------------------------------
#
# The same four responsibilities -- read, shape, meaning, construct -- over the one
# declaration whose values decide what the *law* says an income was rather than what the
# owner received. Nothing here knows about a channel, and `.importlinter` keeps it that way
# in both directions: an official rate may never price a leg (FR-012) and a channel's
# reference rate may never strike a tax base (FR-013).
#
# **No network, no cache, and no knowledge that a fetcher exists.** The National Bank
# publishes through an open developer API and `scripts/fetch_cpi.py` established the pattern
# a script would follow -- retrieve, write an EMPTY `verified_on`, never verify. Building it
# is `provider-automation`'s, not this module's; what this module owes it is the shape it
# writes into.
#
# What is *not* here, because it needs a second file: whether two files declare one series
# identity, and whether the series a jurisdiction names exists and quotes its tax currency.
# Both are relations and live in the resolver, where the whole set is in hand.

OFFICIAL_RATE_SERIES_TABLE: Final = "series"
"""The identity table of an official-rate file, and the prefix of every field path in it."""

OFFICIAL_RATE_OBSERVATION_TABLE: Final = "observation"
"""The observation array of an official-rate file."""

OFFICIAL_RATE_RULE_TABLE: Final = "non_publication_rule"
"""The optional rule table of an official-rate file."""


def _non_publication_rule(
    path: Path,
    table: schema.NonPublicationRuleTable,
    declared: Mapping[date, OfficialRateObservation],
) -> NonPublicationRule:
    """A declared rule, checked against the observations it points at.

    Two checks make the runtime lookup total, so a broken rule can never masquerade as a
    missing date:

    * **``governed_by`` must be a declared observation.** A rule pointing at a date the series
      does not carry selects nothing, and the refusal a reader would then see would name the
      *event's* date and send them to declare the wrong observation.
    * **``applies_to`` must not be.** A rule speaks for dates the publisher does not publish
      for; one claiming a published date contradicts the publication, and which of the two
      won would depend on lookup order.
    """
    rule_id = _require_text(
        path,
        f"{OFFICIAL_RATE_RULE_TABLE}.id",
        table.id,
        "a rule is named so a base can say which rule chose the date its rate came from",
    )
    if not table.day:
        raise DeclarationError(
            path,
            f"{OFFICIAL_RATE_RULE_TABLE}.day",
            "declares a non-publication-day rule with no days. A rule that governs no date "
            "grants nothing and refuses nothing; it reads as though the dates it was written "
            "for were covered.",
            f"declare at least one [[{OFFICIAL_RATE_RULE_TABLE}.day]], or delete the table",
        )
    days: list[NonPublicationDay] = []
    seen: set[date] = set()
    for position, entry in enumerate(table.day):
        field_prefix = f"{OFFICIAL_RATE_RULE_TABLE}.day[{position}]"
        applies_to = _parse_date(path, f"{field_prefix}.applies_to", entry.applies_to)
        governed_by = _parse_date(path, f"{field_prefix}.governed_by", entry.governed_by)
        if applies_to in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.applies_to",
                f"declares {applies_to.isoformat()} for the second time. One date is governed "
                "by one observation: two rows for it are not merged and neither wins, because "
                "whichever the lookup reached first would decide a legal base by file order.",
                "delete the duplicate row",
            )
        if applies_to in declared:
            raise DeclarationError(
                path,
                f"{field_prefix}.applies_to",
                f"sends {applies_to.isoformat()} to another date's rate, and this series "
                "declares an observation for it. A non-publication-day rule speaks for dates "
                "the publisher does NOT publish for; one that redirects a published date "
                "contradicts the publication, and which answer won would depend on lookup "
                "order.",
                "remove the row, or remove the observation it contradicts",
            )
        if governed_by not in declared:
            raise DeclarationError(
                path,
                f"{field_prefix}.governed_by",
                f"sends {applies_to.isoformat()} to {governed_by.isoformat()}, which this "
                "series does not declare. A rule pointing at a date that carries no rate "
                "selects nothing, and the refusal a reader would then see would name the "
                "event's date and send them to declare the wrong observation.",
                f"declare an [[{OFFICIAL_RATE_OBSERVATION_TABLE}]] for "
                f"{governed_by.isoformat()}, or point the row at a date that has one",
            )
        seen.add(applies_to)
        days.append(NonPublicationDay(applies_to=applies_to, governed_by=governed_by))
    return NonPublicationRule(
        id=rule_id,
        days=tuple(days),
        provenance=prov.of(
            [
                _source_ref(
                    path,
                    OFFICIAL_RATE_RULE_TABLE,
                    source=table.source,
                    retrieved_on=table.retrieved_on,
                    verified_on=table.verified_on,
                    kind=table.kind,
                )
            ]
        ),
    )


def official_rate_from_file(path: Path) -> OfficialRateSeries:
    """One ``data/official_rates/<series>.toml`` as an :class:`OfficialRateSeries`.

    Every refusal below is a property of this one file read in isolation, and every one names
    the file and the offending field or date (FR-004):

    * **A non-positive rate**, and **a missing or non-positive quotation unit**. A rate quoted
      per 100 units and read as per 1 is wrong by two orders of magnitude while looking
      entirely reasonable, which is why the unit has no default.
    * **A duplicate date**, and **dates running backwards**. One date, one official rate:
      unlike a channel there is nothing here for a second value to legitimately be.
    * **A rate dated after its own retrieval.** A rate for a date that has not arrived is a
      forecast wearing an observation's clothes, and this one would silently set a legal base.
      Aged against the file's own ``retrieved_on`` rather than a clock, so the same file loads
      the same way for ever.
    * **A rule pointing at an undeclared date, or redirecting a published one.**

    **An observation carrying two sides is refused by the schema**, not here: there is no
    field for a second side, so ``extra="forbid"`` makes declaring one an unrecognised field.

    **Gaps between declared dates load, and so does a series declaring ``observation = []``.**
    A date the publisher did not publish for is a fact and FR-010 forbids inventing one; and
    an empty declaration is the shape a fetch script writes into. The refusal for both belongs
    to ``core.tax.official_rate.strike_base``, which knows the date being asked about.
    """
    document = read_document(path)
    file = _validate(schema.OfficialRateFile, document, path)
    series_id = _require_text(
        path,
        f"{OFFICIAL_RATE_SERIES_TABLE}.id",
        file.series.id,
        "a series is referred to by id from the jurisdiction whose tax currency it serves, "
        "and two series declaring one id are refused across the whole data root",
    )
    pair = _non_empty_list(
        path,
        f"{OFFICIAL_RATE_SERIES_TABLE}.pair",
        file.series.pair,
        "a series quotes one ordered currency pair and cannot quote none",
    )
    if len(pair) != _CURRENCY_PAIR_LENGTH:
        raise DeclarationError(
            path,
            f"{OFFICIAL_RATE_SERIES_TABLE}.pair",
            f"declares {len(pair)} currencies {pair!r}. A quote is between exactly two: the "
            "price currency and the unit currency, in that order. The order decides which "
            "direction the series converts, and reversing it would strike every tax base at "
            "the reciprocal of the published rate while leaving every figure plausible.",
            'write it as ["UAH", "USD"], meaning UAH per USD',
        )
    price_currency = _currency(path, f"{OFFICIAL_RATE_SERIES_TABLE}.pair", pair[0])
    unit_currency = _currency(path, f"{OFFICIAL_RATE_SERIES_TABLE}.pair", pair[1])
    if price_currency is unit_currency:
        raise DeclarationError(
            path,
            f"{OFFICIAL_RATE_SERIES_TABLE}.pair",
            f"quotes {price_currency.value} against itself. A series converts between two "
            "different currencies, and an amount already in the tax currency needs no "
            "official rate at all (FR-009).",
            "name two different currencies",
        )

    observations: list[OfficialRateObservation] = []
    seen: dict[date, int] = {}
    for position, entry in enumerate(file.observation):
        field_prefix = f"{OFFICIAL_RATE_OBSERVATION_TABLE}[{position}]"
        on_date = _parse_date(path, f"{field_prefix}.on_date", entry.on_date)
        retrieved_on = _parse_date(path, f"{field_prefix}.retrieved_on", entry.retrieved_on)
        if on_date in seen:
            raise DeclarationError(
                path,
                f"{field_prefix}.on_date",
                f"declares {on_date.isoformat()} for the second time; entry {seen[on_date]} of "
                "this file already declares it. The two are not merged and neither wins: one "
                "date has one official rate, and a repeated date is a file edited twice.",
                "delete the duplicate entry",
            )
        if observations and on_date <= observations[-1].on_date:
            raise DeclarationError(
                path,
                f"{field_prefix}.on_date",
                f"declares {on_date.isoformat()} after "
                f"{observations[-1].on_date.isoformat()}, so the series runs backwards here. "
                "Observations are declared in strictly ascending order and are not reordered: "
                "sorting silently would hide which edit was meant, and the covered window a "
                "refusal reports is read off the two ends.",
                "put the observations in date order",
            )
        if on_date > retrieved_on:
            raise DeclarationError(
                path,
                f"{field_prefix}.on_date",
                f"declares a rate for {on_date.isoformat()} but was retrieved on "
                f"{retrieved_on.isoformat()}. An authority sets an official rate for a date on "
                "or before that date, so a value read before the date it applies to is a "
                "forecast rather than an observation -- and this forecast would silently set a "
                "legal base.",
                "correct the date, or re-fetch the series once the rate has been published",
            )
        seen[on_date] = position
        observations.append(
            OfficialRateObservation(
                on_date=on_date,
                value=_positive(
                    path,
                    f"{field_prefix}.value",
                    entry.value,
                    "an official rate is a strictly positive number of the price currency per "
                    "quotation_unit units of the unit currency. Zero or below is not a rate "
                    "and would produce a base that merely looks like money",
                ),
                provenance=prov.of(
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
                ),
            )
        )
    declared = {observation.on_date: observation for observation in observations}
    return OfficialRateSeries(
        id=series_id,
        authority=_require_text(
            path,
            f"{OFFICIAL_RATE_SERIES_TABLE}.authority",
            file.series.authority,
            "a series states which authority publishes it; that is half of what makes a "
            "second jurisdiction's series a data-only addition (FR-005)",
        ),
        pair=(price_currency, unit_currency),
        quotation_unit=_positive(
            path,
            f"{OFFICIAL_RATE_SERIES_TABLE}.quotation_unit",
            file.series.quotation_unit,
            "the number of units a rate is quoted per is declared and never defaulted "
            "(FR-002): a rate quoted per 100 and read as per 1 is wrong by two orders of "
            "magnitude and looks entirely plausible",
        ),
        rule=(
            None
            if file.non_publication_rule is None
            else _non_publication_rule(path, file.non_publication_rule, declared)
        ),
        observations=tuple(observations),
    )


# ---------------------------------------------------------------------------
# 012-fop-group-3: the taxation scheme, and where income is credited
# ---------------------------------------------------------------------------
#
# The scheme an income stream is under, rather than the tax class an instrument's income
# falls in. Nothing here knows which components exist: a scheme charges exactly what it
# declares, and the two component kinds differ in what they are asked -- a date, or a period.
#
# What is *not* here, because it needs a second file: whether two files declare one scheme
# identity, whether a destination's scheme and venue exist, and whether a stream's declared
# treatment does. All three are relations and live in the resolver.

SCHEME_TABLE: Final = "scheme"
"""The identity table of a scheme file, and the prefix of every field path in it."""

DESTINATION_TABLE: Final = "destination"
"""The array of rows in a crediting-destination file."""

_PERIODS: Final[Mapping[str, scheme_module.Period]] = {"month": "month"}
"""The periods a periodic component can be owed per. One member; see ``scheme.Period``."""

_DECLARED_FOR: Final[Mapping[str, scheme_module.DeclaredFor]] = {
    "stream": "stream",
    "reading": "reading",
}

_VERDICTS: Final[Mapping[str, scheme_module.Verdict]] = {
    member.value: member for member in scheme_module.Verdict
}


def _recorded_context(
    path: Path, declared: list[schema.DeclaredContextTable], *, field_prefix: str
) -> tuple[scheme_module.DeclaredContext, ...]:
    """Cited facts recorded beside a schedule and deliberately not applied."""
    recorded: list[scheme_module.DeclaredContext] = []
    for position, entry in enumerate(declared):
        entry_prefix = f"{field_prefix}.context[{position}]"
        recorded.append(
            scheme_module.DeclaredContext(
                id=_require_text(
                    path,
                    f"{entry_prefix}.id",
                    entry.id,
                    "a recorded fact is named so a figure can point at it",
                ),
                statement=_require_text(
                    path,
                    f"{entry_prefix}.statement",
                    entry.statement,
                    "a recorded fact carries the provision in its own words, because a "
                    "declaration carrying half a provision is the same defect as a citation "
                    "to a proposition the source does not make",
                ),
                not_applied_because=_require_text(
                    path,
                    f"{entry_prefix}.not_applied_because",
                    entry.not_applied_because,
                    "a provision declared beside a schedule and silently not applied is "
                    "indistinguishable from an oversight",
                ),
                provenance=prov.of(
                    [
                        _source_ref(
                            path,
                            entry_prefix,
                            source=entry.source,
                            retrieved_on=entry.retrieved_on,
                            verified_on=entry.verified_on,
                            kind=entry.kind,
                        )
                    ]
                ),
            )
        )
    return tuple(recorded)


def _ascending(path: Path, field_path: str, effective_from: date, previous: date | None) -> None:
    """Refuse a duplicate or an out-of-order effective date, in the file's own order.

    The schedule is read in the order it is written and is never sorted: a file whose order
    disagrees with its dates is one a human misreads, and reordering it here would make that
    file loadable.
    """
    if previous is None:
        return
    if effective_from == previous:
        raise DeclarationError(
            path,
            field_path,
            f"declares {effective_from.isoformat()} for the second time. One date has one "
            "value: two entries for it are not merged and neither wins, because whichever "
            "the fold reached first would decide a legal figure by file order.",
            "delete the duplicate entry",
        )
    if effective_from < previous:
        raise DeclarationError(
            path,
            field_path,
            f"is {effective_from.isoformat()}, before the previous entry's "
            f"{previous.isoformat()}. The schedule is read in the order it is written and is "
            "not silently sorted.",
            "write the entries oldest first",
        )


def _rate_component(path: Path, entry: schema.RateComponentTable) -> scheme_module.RateComponent:
    """One rate component and its dated schedule, refusing an empty or disordered one."""
    field_prefix = f"{SCHEME_TABLE}.rate_component[{entry.id}]"
    identifier = _require_text(
        path, f"{field_prefix}.id", entry.id, "a component is referred to by id"
    )
    if not entry.rate:
        raise DeclarationError(
            path,
            f"{field_prefix}.rate",
            "declares no rate at all. A component with an empty schedule charges nothing on "
            "every date and says so nowhere, which is the silent zero this whole feature "
            "exists to refuse.",
            f"declare at least one [[{SCHEME_TABLE}.rate_component.rate]], or delete the component",
        )
    schedule: list[scheme_module.ComponentRate] = []
    for position, rate in enumerate(entry.rate):
        entry_prefix = f"{field_prefix}.rate[{position}]"
        effective_from = _parse_date(path, f"{entry_prefix}.effective_from", rate.effective_from)
        _ascending(
            path,
            f"{entry_prefix}.effective_from",
            effective_from,
            schedule[-1].effective_from if schedule else None,
        )
        schedule.append(
            scheme_module.ComponentRate(
                effective_from=effective_from,
                rate=_as_fraction(
                    _non_negative(
                        path,
                        f"{entry_prefix}.rate_pct",
                        rate.rate_pct,
                        "a component charges a share of the base, and a negative rate would "
                        "be a refund rather than a charge",
                    )
                ),
                provenance=prov.of(
                    [
                        _source_ref(
                            path,
                            entry_prefix,
                            source=rate.source,
                            retrieved_on=rate.retrieved_on,
                            verified_on=rate.verified_on,
                            kind=rate.kind,
                        )
                    ]
                ),
            )
        )
    return scheme_module.RateComponent(
        id=identifier,
        name=_require_text(
            path,
            f"{field_prefix}.name",
            entry.name,
            "a component is reported under the name the law uses for it",
        ),
        schedule=tuple(schedule),
        context=_recorded_context(path, entry.context or [], field_prefix=field_prefix),
    )


def _periodic_component(
    path: Path, entry: schema.PeriodicComponentTable
) -> scheme_module.PeriodicComponent:
    """One periodic component and its dated schedule of statutory sums."""
    field_prefix = f"{SCHEME_TABLE}.periodic_component[{entry.id}]"
    identifier = _require_text(
        path, f"{field_prefix}.id", entry.id, "a component is referred to by id"
    )
    if not entry.amount:
        raise DeclarationError(
            path,
            f"{field_prefix}.amount",
            "declares no amount at all. A periodic component with an empty schedule owes "
            "nothing for every period and says so nowhere.",
            f"declare at least one [[{SCHEME_TABLE}.periodic_component.amount]], or delete "
            "the component",
        )
    schedule: list[scheme_module.ComponentAmount] = []
    for position, amount in enumerate(entry.amount):
        entry_prefix = f"{field_prefix}.amount[{position}]"
        effective_from = _parse_date(path, f"{entry_prefix}.effective_from", amount.effective_from)
        _ascending(
            path,
            f"{entry_prefix}.effective_from",
            effective_from,
            schedule[-1].effective_from if schedule else None,
        )
        sources = prov.of(
            [
                _source_ref(
                    path,
                    entry_prefix,
                    source=amount.source,
                    retrieved_on=amount.retrieved_on,
                    verified_on=amount.verified_on,
                    kind=amount.kind,
                )
            ]
        )
        schedule.append(
            scheme_module.ComponentAmount(
                effective_from=effective_from,
                amount=Money(
                    _non_negative(
                        path,
                        f"{entry_prefix}.amount",
                        amount.amount,
                        "a periodic component owes a statutory sum, and a negative one would "
                        "be a payment to the taxpayer",
                    ),
                    _currency(path, f"{entry_prefix}.currency", amount.currency),
                    sources,
                ),
                provenance=sources,
            )
        )
    return scheme_module.PeriodicComponent(
        id=identifier,
        name=_require_text(
            path,
            f"{field_prefix}.name",
            entry.name,
            "a component is reported under the name the law uses for it",
        ),
        period=_closed_value(path, f"{field_prefix}.period", entry.period, _PERIODS, "period"),
        schedule=tuple(schedule),
        context=_recorded_context(path, entry.context or [], field_prefix=field_prefix),
    )


def _no_shared_component_id(
    path: Path,
    rates: tuple[scheme_module.RateComponent, ...],
    periodics: tuple[scheme_module.PeriodicComponent, ...],
) -> None:
    """No two components of a scheme share an id, **across both kinds**.

    Checked across the kinds because ``component_standing`` looks a component up by id alone:
    two sharing one would make which of them answered depend on scan order. And reported
    naming **the tables the duplicate is actually written in** -- the file has a
    ``rate_component`` and a ``periodic_component`` array and no ``component`` one, so a path
    naming a table nobody wrote sends the reader looking for it.
    """
    kinds: dict[str, list[str]] = {}
    for rate_component in rates:
        kinds.setdefault(rate_component.id, []).append("rate_component")
    for periodic_component in periodics:
        kinds.setdefault(periodic_component.id, []).append("periodic_component")
    for identifier, tables in kinds.items():
        if len(tables) == 1:
            continue
        # First-appearance order rather than sorted: it is the order the file declares them
        # in, which is the order a reader will scroll through looking for the second one.
        distinct = list(dict.fromkeys(tables))
        if len(distinct) == 1:
            # Repeats of ONE table are counted, not listed: naming `rate_component[levy]` twice
            # tells a reader nothing they did not already have, and joining a list of one
            # repeated string with "and" is how a message comes to say "A and A both declare".
            where = f"{len(tables)} times in {SCHEME_TABLE}.{distinct[0]}"
        else:
            where = "in " + " and ".join(f"{SCHEME_TABLE}.{table}" for table in distinct)
        raise DeclarationError(
            path,
            f"{SCHEME_TABLE}.{tables[0]}[{identifier}].id",
            f"declares the component id {identifier!r} {where}. A component is looked up by "
            "id alone, so two sharing one would make which of them answered depend on the "
            "order they were scanned in.",
            "give each of them a distinct id",
        )


def _amounts_in_the_tax_currency(
    path: Path, scheme: scheme_module.TaxationScheme
) -> scheme_module.TaxationScheme:
    """Every periodic amount is money in the currency this scheme assesses in.

    A statutory sum carries its own currency because money does, and inheriting one would let
    a scheme silently charge a sum stated in another. Checked after the components are built
    rather than inside them, because it is the only rule here that needs the scheme's own
    ``tax_currency`` -- which is read at the end.

    Without this, a periodic charge could leave in a currency nothing downstream can add to
    the rate lines, and the mismatch would surface as a ``CurrencyMismatchError`` from a
    caller's own arithmetic rather than as a file with a field named in it.
    """
    for component in scheme.periodic_components:
        for position, entry in enumerate(component.schedule):
            if entry.amount.currency is scheme.tax_currency:
                continue
            raise DeclarationError(
                path,
                f"{SCHEME_TABLE}.periodic_component[{component.id}].amount[{position}].currency",
                f"is {entry.amount.currency.value} and scheme {scheme.id!r} assesses in "
                f"{scheme.tax_currency.value}. A statutory sum owed in another currency "
                "cannot be added to what this scheme charges on income, and the mismatch "
                "would surface from a caller's arithmetic rather than from the file that "
                "declared it.",
                f'write currency = "{scheme.tax_currency.value}"',
            )
    return scheme


def scheme_from_file(path: Path) -> scheme_module.TaxationScheme:
    """One ``data/tax/schemes/<id>.toml`` as a :class:`TaxationScheme`.

    Every refusal below is a property of this one file read in isolation, and every one names
    the file and the offending component or field: a scheme charging no component at all, an
    empty schedule, two entries on one effective date, a schedule running backwards, a
    negative rate or amount, two components sharing an id, an unknown period, currency or
    ``declared_for``, and a recorded fact with no reason it is not applied.

    **A rate written on a periodic component, or an amount on a rate component, is refused by
    the schema** rather than here: neither field exists on the other table, so ``extra="forbid"``
    makes writing one an unrecognised field instead of a check somebody has to remember.
    """
    document = read_document(path)
    file = _validate(schema.SchemeFile, document, path)
    declared = file.scheme
    if not declared.rate_component and not declared.periodic_component:
        raise DeclarationError(
            path,
            SCHEME_TABLE,
            "declares no component at all. A scheme charges exactly the components it "
            "declares, so one that declares none charges nothing on every income and every "
            "period -- which is a file nobody meant to write rather than a tax-free regime.",
            f"declare a [[{SCHEME_TABLE}.rate_component]] or a "
            f"[[{SCHEME_TABLE}.periodic_component]]",
        )
    rate_components = tuple(_rate_component(path, entry) for entry in declared.rate_component or [])
    periodic_components = tuple(
        _periodic_component(path, entry) for entry in declared.periodic_component or []
    )
    _no_shared_component_id(path, rate_components, periodic_components)
    return _amounts_in_the_tax_currency(
        path,
        scheme_module.TaxationScheme(
            id=_require_text(
                path,
                f"{SCHEME_TABLE}.id",
                declared.id,
                "a scheme is named by an income stream and by every reading that consumes it, "
                "and two schemes declaring one id are refused across the whole data root",
            ),
            name=_require_text(path, f"{SCHEME_TABLE}.name", declared.name, "a scheme is named"),
            jurisdiction_id=_require_text(
                path,
                f"{SCHEME_TABLE}.jurisdiction",
                declared.jurisdiction,
                "a scheme belongs to the jurisdiction whose tax currency its base is struck in",
            ),
            tax_currency=_currency(path, f"{SCHEME_TABLE}.tax_currency", declared.tax_currency),
            variant=_require_text(
                path,
                f"{SCHEME_TABLE}.variant",
                declared.variant,
                "a scheme names which of the law's alternative rate sets it declares, so the "
                "second is a file rather than a schema change the day its rate is cited",
            ),
            reporting_cadence=_require_text(
                path,
                f"{SCHEME_TABLE}.reporting_cadence",
                declared.reporting_cadence,
                "a scheme declares the cadence it reports and pays on, so the feature that "
                "models payment inherits a declared fact rather than guessing one",
            ),
            declared_for=_closed_value(
                path,
                f"{SCHEME_TABLE}.declared_for",
                declared.declared_for,
                _DECLARED_FOR,
                "declaration audience",
            ),
            rate_components=rate_components,
            periodic_components=periodic_components,
        ),
    )


def _optional_text(path: Path, field_path: str, value: str | None, what: str) -> str | None:
    """A field that may be omitted, but that may not be written blank.

    ``None`` is *the key was not written*; ``""`` is a key that was written and says nothing.
    The two are different claims everywhere else in this schema, and they have to stay
    different here, because each of these fields is **read as a claim downstream**.
    """
    if value is None:
        return None
    return _require_text(path, field_path, value, what)


def _reading(path: Path, entry: schema.ReadingTable, *, field_prefix: str) -> scheme_module.Reading:
    """One candidate treatment, declared either as a scheme or as a reason it is not one."""
    entry_prefix = f"{field_prefix}.reading[{entry.id}]"
    names_a_scheme = entry.scheme is not None
    if names_a_scheme == (entry.uncomputable_because is not None):
        raise DeclarationError(
            path,
            entry_prefix,
            "declares both a scheme and a reason it cannot be computed, or neither. A "
            "candidate is one or the other: a declared scheme gets a computed, labelled "
            "figure, and everything else is named on the switch as uncomputed with the "
            "reason -- so that an omitted reading can never make a switch look complete.",
            "declare exactly one of scheme and uncomputable_because",
        )
    if names_a_scheme and entry.recognised_on is None:
        raise DeclarationError(
            path,
            f"{entry_prefix}.recognised_on",
            "names a scheme and no date name. A reading computes on a declared date, and "
            "two readings of one destination can disagree about which; borrowing another "
            "reading's date would compute the reading this one contests.",
            "declare recognised_on",
        )
    if not names_a_scheme and entry.recognised_on is not None:
        raise DeclarationError(
            path,
            f"{entry_prefix}.recognised_on",
            "names a date for a candidate that is declared uncomputable. Nothing reads it, "
            "and a field nothing reads is a field a reader believes is doing something.",
            "delete recognised_on, or declare the scheme this reading computes",
        )
    return scheme_module.Reading(
        id=_require_text(path, f"{entry_prefix}.id", entry.id, "a reading is named"),
        label=_require_text(
            path,
            f"{entry_prefix}.label",
            entry.label,
            "a figure states which reading produced it, in words a reader will see",
        ),
        scheme_id=_optional_text(
            path,
            f"{entry_prefix}.scheme",
            entry.scheme,
            "a reading computes under a declared scheme, and a key written blank is "
            "misdiagnosed downstream as a scheme nobody declared",
        ),
        # Each of the others is optional and each, once written, must say something. An empty
        # string is not the absence of a declaration -- the absent key is -- and every one of
        # these is read as a claim downstream: an uncomputable candidate is named on a switch
        # WITH ITS REASON, a reading computes on the date its name selects, and a declared
        # departure from a source is rendered on the figure. Blank, each would render as a
        # claim that was made and says nothing.
        uncomputable_because=_optional_text(
            path,
            f"{entry_prefix}.uncomputable_because",
            entry.uncomputable_because,
            "a candidate that cannot be computed is named on the switch with the reason it "
            "cannot be, so a switch is never read as complete when it is not",
        ),
        recognised_on=_optional_text(
            path,
            f"{entry_prefix}.recognised_on",
            entry.recognised_on,
            "a reading computes on the date its declared name selects, and the caller "
            "supplies dates by that name",
        ),
        departs_from_source=_optional_text(
            path,
            f"{entry_prefix}.departs_from_source",
            entry.departs_from_source,
            "a declared departure from a source is rendered on the figure, and a departure "
            "nothing reports is one that becomes a silent absorption",
        ),
        provenance=prov.of(
            [
                _source_ref(
                    path,
                    entry_prefix,
                    source=entry.source,
                    retrieved_on=entry.retrieved_on,
                    verified_on=entry.verified_on,
                    kind=entry.kind,
                )
            ]
        ),
    )


def destinations_from_file(path: Path) -> tuple[scheme_module.CreditingDestination, ...]:
    """One ``data/tax/destinations/<jurisdiction>.toml`` as the rows of a normative table.

    The table is normative rather than illustrative: a destination it does not name cannot be
    resolved by reasoning about it, and refuses instead. So every row carries the judgement
    that put it there, and a row with empty grounds is refused here.
    """
    document = read_document(path)
    file = _validate(schema.DestinationFile, document, path)
    rows: list[scheme_module.CreditingDestination] = []
    for position, entry in enumerate(file.destination):
        field_prefix = f"{DESTINATION_TABLE}[{position}]"
        verdict = _closed_value(
            path, f"{field_prefix}.verdict", entry.verdict, _VERDICTS, "verdict"
        )
        if not entry.reading:
            raise DeclarationError(
                path,
                f"{field_prefix}.reading",
                "declares no reading at all. A row with no candidate says nothing about the "
                "destination it names, which is what a missing row already says.",
                f"declare at least one [[{DESTINATION_TABLE}.reading]], or delete the row",
            )
        readings = tuple(
            _reading(path, reading, field_prefix=field_prefix) for reading in entry.reading
        )
        _no_duplicates(path, f"{field_prefix}.reading.id", [reading.id for reading in readings])
        if verdict is scheme_module.Verdict.INTERPRETED and (
            len(readings) != 1 or readings[0].scheme_id is None
        ):
            raise DeclarationError(
                path,
                f"{field_prefix}.verdict",
                "is interpreted and the row does not carry exactly one computable reading. "
                "An interpreted destination produces a charge, and a charge cannot be two "
                "figures or none; a row with competing candidates is unsettled, and a row "
                "whose only candidate is uncomputable has nothing to charge.",
                "declare one computable reading, or declare the verdict unsettled",
            )
        rows.append(
            scheme_module.CreditingDestination(
                scheme_id=_require_text(
                    path,
                    f"{field_prefix}.scheme",
                    entry.scheme,
                    "a row records how one scheme's income is treated at one destination",
                ),
                venue_id=_require_text(
                    path,
                    f"{field_prefix}.venue",
                    entry.venue,
                    "a row names the venue the income is credited at",
                ),
                verdict=verdict,
                grounds=_require_text(
                    path,
                    f"{field_prefix}.grounds",
                    entry.grounds,
                    "the table is normative, so every row records the judgement that put it "
                    "there rather than leaving it to be re-derived",
                ),
                resolution_path=_require_text(
                    path,
                    f"{field_prefix}.resolution_path",
                    entry.resolution_path,
                    "a row states what would close the question, because an unsettled "
                    "verdict with no way out is a gap rather than a finding",
                ),
                readings=readings,
                provenance=prov.of(
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
                ),
            )
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# 015-the-question: the question itself
# ---------------------------------------------------------------------------
#
# `composition`'s reading, unchanged: an owner's own statement, no citation read and none
# expected, and **no default** anywhere. What this loader owns is every refusal a *single*
# file can carry. Whether a subject word names anything, whether the benchmark is among the
# subjects and whether an amount's stream exists are relations across files and belong to the
# resolver and the verb -- and a word naming nothing is not a refusal at all, but the answer's
# own content (FR-009).

QUESTION_TABLE: Final = "question"
"""Root table of a question file, and the prefix of every field path in one."""

BOND_PLAN: Final = "bond"
FUND_PLAN: Final = "fund"
PLAN_KINDS: Final = (BOND_PLAN, FUND_PLAN)
"""What a run plan may be for. Closed: a typo selects nothing rather than the other kind."""

HOLD_TO_TERMINATION: Final = "termination"
"""What a fund plan writes where the holding runs to the fund's own end.

A stated value rather than an omitted key, because *hold to termination* is a **choice**: it
picks one of the fund's two declared ways out, and 014 FR-003 refuses a default for exactly
that. An absent key would make the choice the thing that happens when nobody thought about it.
"""


def question_from_file(path: Path) -> Question:
    """One ``data/questions/<id>.toml`` as the question it declares."""
    return question_from_document(read_document(path), path)


def question_from_document(document: Mapping[str, Any], path: Path) -> Question:
    """One question, from a document the caller has already read.

    Split from :func:`question_from_file` so the **CLI** builds its record through this exact
    function (015 FR-005). Flags are sugar over the file, and the guarantee that they own no
    field the file cannot express and no default it cannot state is then structural rather than
    a scan somebody has to keep honest: there is one validator and one set of refusals.
    """
    file = _validate(schema.QuestionFile, document, path)
    table = file.question
    prefix = QUESTION_TABLE
    owner_id = _require_text(
        path,
        f"{OWNER_TABLE}.id",
        file.owner.id,
        "a question is one person's, and every declaration carries its owner from the first "
        "commit (Principle VII)",
    )
    subjects = _question_subjects(path, table)
    return Question(
        id=_require_text(
            path,
            f"{prefix}.id",
            table.id,
            "the run manifest records which question produced an answer, so two questions are "
            "two results rather than one",
        ),
        owner_id=owner_id,
        asked_on=_parse_date(path, f"{prefix}.asked_on", table.asked_on),
        regime_id=_require_text(
            path,
            f"{prefix}.regime",
            table.regime,
            "every candidate's segments belong to one regime's route set, and which world was "
            "searched is half of what the answer means (014 FR-023)",
        ),
        continuation=_continuation(path, f"{prefix}.continuation", table.continuation),
        amounts=_question_amounts(path, table),
        subjects=subjects,
        every_declared_instrument=table.every_declared_instrument is True,
        horizons=_question_horizons(path, table),
        benchmark_instrument_id=_require_text(
            path,
            f"{prefix}.benchmark",
            table.benchmark,
            "a ranking with no benchmark invites its own head to be read as a winner (010 FR-011)",
        ),
        plans=_question_plans(path, table),
        reserves=_question_reserves(path, table),
    )


def _continuation(path: Path, field_path: str, value: str) -> ContinuationAssumption:
    """The declared continuation assumption as the core's closed enum member."""
    for member in ContinuationAssumption:
        if member.value == value:
            return member
    raise DeclarationError(
        path,
        field_path,
        f"declares {value!r}, which is not a continuation assumption this engine implements. "
        "What proceeds arriving before a horizon's end do until it has no default anywhere in "
        "the stack, so an unrecognised name is refused rather than read as the nearest one.",
        f"write one of {sorted(member.value for member in ContinuationAssumption)}",
    )


def _question_subjects(path: Path, table: schema.QuestionTable) -> tuple[str, ...]:
    """The words the owner wrote, refusing a blank, a repeat, and the two silent readings.

    Neither ``subjects`` nor ``every_declared_instrument`` is refused because omission must not
    mean *everything*; both are refused because a list beside the token would leave which one
    was in force to be settled by whichever the code read first.
    """
    prefix = QUESTION_TABLE
    stated = table.subjects is not None
    everything = table.every_declared_instrument is not None
    if stated == everything:
        raise DeclarationError(
            path,
            f"{prefix}.subjects",
            (
                "declares both a subject list and every_declared_instrument"
                if stated
                else "declares neither a subject list nor every_declared_instrument"
            )
            + ". Exactly one of the two says what the question is about (FR-007): omission must "
            "not read as *everything*, because the absence of a subject the owner named is the "
            "most useful thing an answer can say.",
            "write subjects = [...], or every_declared_instrument = true",
        )
    if table.subjects is None:
        if table.every_declared_instrument is False:
            raise DeclarationError(
                path,
                f"{prefix}.every_declared_instrument",
                "is declared false, which states nothing at all: it is neither a subject list "
                "nor the every-instrument token. A question that is about nothing has no "
                "answer to give.",
                "write subjects = [...], or every_declared_instrument = true",
            )
        return ()
    if not table.subjects:
        raise DeclarationError(
            path,
            f"{prefix}.subjects",
            "is empty. A question about nothing enumerates nothing, and an empty list is not "
            "the way to ask about everything the registry declares.",
            "name what the question is about, or write every_declared_instrument = true",
        )
    seen: list[str] = []
    for position, word in enumerate(table.subjects):
        field = f"{prefix}.subjects[{position}]"
        subject = _require_text(
            path, field, word, "a subject is what the question is about, and a blank names it"
        )
        if subject in seen:
            raise DeclarationError(
                path,
                field,
                f"names {subject!r} twice. A duplicated subject would be counted twice in the "
                "line that says how many of the named subjects an answer reached, which is the "
                "one line that speaks to what was actually asked (FR-010).",
                f"name {subject!r} once",
            )
        seen.append(subject)
    return tuple(seen)


def _question_amounts(path: Path, table: schema.QuestionTable) -> Mapping[str, Money]:
    """What leaves each stream, in that stream's own currency, refusing a repeat."""
    prefix = f"{QUESTION_TABLE}.amount"
    if not table.amount:
        raise DeclarationError(
            path,
            prefix,
            "states no amount. A question about no money has nothing to compare: enumeration "
            "sizes every purchase from the amount the stream releases, and defaulting it to "
            "zero would score every real option at nothing.",
            "state an amount for the stream the money leaves",
        )
    amounts: dict[str, Money] = {}
    for position, entry in enumerate(table.amount):
        field = f"{prefix}[{position}]"
        stream_id = _require_text(
            path, f"{field}.stream", entry.stream, "an amount belongs to a named income stream"
        )
        if stream_id in amounts:
            raise DeclarationError(
                path,
                f"{field}.stream",
                f"states a second amount for {stream_id!r}. Two amounts for one stream are two "
                "questions: whichever loaded last would size every purchase, and nothing in the "
                "answer would say which.",
                f"state one amount for {stream_id!r}",
            )
        amounts[stream_id] = Money(
            _positive(
                path,
                f"{field}.amount",
                entry.amount,
                "an amount of zero or below deploys nothing and scores every option at nothing",
            ),
            _currency(path, f"{field}.currency", entry.currency),
            prov.EMPTY,
        )
    return amounts


def _question_horizons(path: Path, table: schema.QuestionTable) -> tuple[DateRange, ...]:
    """The windows, in declared order, refusing an empty list and two identical horizons."""
    prefix = f"{QUESTION_TABLE}.horizon"
    if not table.horizon:
        raise DeclarationError(
            path,
            prefix,
            "declares no horizon. Every figure in an answer is measured over one, and a "
            "question with none has no section to put an answer in.",
            "declare at least one [[question.horizon]]",
        )
    horizons: list[DateRange] = []
    for position, entry in enumerate(table.horizon):
        field = f"{prefix}[{position}]"
        window = DateRange(
            start=_parse_date(path, f"{field}.start", entry.start),
            end=_parse_date(path, f"{field}.end", entry.end),
        )
        if window.end < window.start:
            raise DeclarationError(
                path,
                f"{field}.end",
                f"is {window.end.isoformat()}, before the start {window.start.isoformat()}. A "
                "window that runs backwards measures nothing.",
                "correct whichever of the two dates is wrong",
            )
        if window in horizons:
            raise DeclarationError(
                path,
                field,
                f"repeats the window {window.start.isoformat()} to {window.end.isoformat()}. "
                "Two identical sections are not two answers, and the cross-horizon reading "
                "would key two rows the same.",
                "delete the duplicate, or correct its dates",
            )
        horizons.append(window)
    return tuple(horizons)


def _question_reserves(path: Path, table: schema.QuestionTable) -> tuple[Reserve, ...]:
    """What the owner may need back, and when. An empty list is a stated absence."""
    prefix = f"{QUESTION_TABLE}.reserve"
    return tuple(
        Reserve(
            amount=Money(
                _positive(
                    path,
                    f"{prefix}[{position}].amount",
                    entry.amount,
                    "a reserve of zero or below is not a need and its verdict would be "
                    "covered by every candidate that arrives at all",
                ),
                _currency(path, f"{prefix}[{position}].currency", entry.currency),
                prov.EMPTY,
            ),
            by=_parse_date(path, f"{prefix}[{position}].by", entry.by),
        )
        for position, entry in enumerate(table.reserve)
    )


def _question_plans(
    path: Path, table: schema.QuestionTable
) -> Mapping[str, tuple[InstrumentPlan, ...]]:
    """One or more run plans per subject, in the order the owner wrote them."""
    prefix = f"{QUESTION_TABLE}.plan"
    if not table.plan:
        raise DeclarationError(
            path,
            prefix,
            "supplies no run plan. There is no default anywhere in the stack for a consumption "
            "method, a coupon policy, a liquidity mode, a buyback availability or an exit date "
            "(014 FR-003), so a question that supplies none can run nothing.",
            "declare a [[question.plan]] for each subject",
        )
    plans: dict[str, list[InstrumentPlan]] = {}
    for position, entry in enumerate(table.plan):
        field = f"{prefix}[{position}]"
        subject = _require_text(
            path, f"{field}.subject", entry.subject, "a run plan is a plan for a named subject"
        )
        plans.setdefault(subject, []).append(_question_plan(path, field, entry))
    return {subject: tuple(supplied) for subject, supplied in plans.items()}


def _question_plan(
    path: Path, field: str, entry: schema.QuestionPlanTable
) -> Assumptions | FundAssumptions:
    """One run plan, of the kind it declares itself to be."""
    kind = entry.kind
    if kind not in PLAN_KINDS:
        raise DeclarationError(
            path,
            f"{field}.kind",
            f"declares {kind!r}, and a run plan is for a {BOND_PLAN!r} or a {FUND_PLAN!r}. "
            "Which one is declared rather than inferred from the fields present, so a typo is "
            "refused instead of quietly selecting the other kind's plan.",
            f"write one of {sorted(PLAN_KINDS)}",
        )
    consumption = _require_text(
        path,
        f"{field}.consumption_method",
        entry.consumption_method,
        "which lots a disposal consumes changes the gain and the tax on it, and there is no "
        "default anywhere in the stack",
    )
    fund_only = {
        "liquidity_mode": entry.liquidity_mode,
        "buyback": entry.buyback,
        "exit_on": entry.exit_on,
    }
    if kind == BOND_PLAN:
        for name, value in (("yield_point", entry.yield_point), *fund_only.items()):
            _refuse_field_of_the_other_kind(path, field, name, value, kind=BOND_PLAN)
        if entry.exchange_rate is not None:
            _refuse_field_of_the_other_kind(
                path, field, "exchange_rate", entry.exchange_rate, kind=BOND_PLAN
            )
        return Assumptions(
            consumption_method=consumption,
            coupon_policy=_require_text(
                path,
                f"{field}.coupon_policy",
                entry.coupon_policy or "",
                "what a coupon does when it arrives changes the answer, and there is no "
                "default anywhere in the stack (014 FR-003)",
            ),
        )
    _refuse_field_of_the_other_kind(
        path, field, "coupon_policy", entry.coupon_policy, kind=FUND_PLAN
    )
    for name, value in fund_only.items():
        if value is None:
            raise DeclarationError(
                path,
                f"{field}.{name}",
                f"is absent from a {FUND_PLAN!r} plan. A liquidity mode, whether the "
                "discretionary buyback is on offer and when the owner asks to exit are three "
                "stated choices with no default anywhere in the stack (014 FR-003), and each "
                "of them changes the figure.",
                f"state {name} on this plan",
            )
    return FundAssumptions(
        liquidity_mode=_literal(
            path,
            f"{field}.liquidity_mode",
            fund_only["liquidity_mode"] or "",
            get_args(LiquidityMode),
        ),
        buyback=_literal(
            path, f"{field}.buyback", fund_only["buyback"] or "", get_args(BuybackAvailability)
        ),
        exit_on=(
            None
            if entry.exit_on == HOLD_TO_TERMINATION
            else _parse_date(path, f"{field}.exit_on", entry.exit_on or "")
        ),
        yield_point=(
            None
            if entry.yield_point is None
            else ChosenPoint(
                rate=_as_fraction(entry.yield_point.rate_pct),
                is_assumption=_is_assumption(
                    path, f"{field}.yield_point.is_assumption", entry.yield_point.is_assumption
                ),
                rationale=_require_text(
                    path,
                    f"{field}.yield_point.rationale",
                    entry.yield_point.rationale,
                    "a point chosen inside a stated range is the owner's assumption, and a "
                    "figure conditional on an unexplained guess cannot be argued with",
                ),
            )
        ),
        exchange_rate=(
            None
            if entry.exchange_rate is None
            else ExchangeRateAssumption(
                uah_per_unit=_positive(
                    path,
                    f"{field}.exchange_rate.uah_per_unit",
                    entry.exchange_rate.uah_per_unit,
                    "a rate of zero or below values the whole payout at nothing or less",
                ),
                is_assumption=_is_assumption(
                    path,
                    f"{field}.exchange_rate.is_assumption",
                    entry.exchange_rate.is_assumption,
                ),
                rationale=_require_text(
                    path,
                    f"{field}.exchange_rate.rationale",
                    entry.exchange_rate.rationale,
                    "an owner-stated rate is a belief about the future, and every figure "
                    "computed through it inherits the mark (015 FR-021a)",
                ),
            )
        ),
        consumption_method=consumption,
    )


def _refuse_field_of_the_other_kind(
    path: Path, field: str, name: str, value: object, *, kind: str
) -> None:
    """A plan carrying a field its declared kind has no use for is a plan of the wrong kind."""
    if value is None:
        return
    raise DeclarationError(
        path,
        f"{field}.{name}",
        f"is declared on a {kind!r} plan, which has no {name}. It is refused rather than "
        "ignored: a field that is silently dropped is a stated choice that does nothing, and "
        "the run would proceed under settings the owner believes are in force.",
        f"delete {name}, or correct this plan's kind",
    )


def _is_assumption(path: Path, field_path: str, value: bool) -> Literal[True]:
    """``is_assumption`` on a stated belief. There is no observed case."""
    if not value:
        raise DeclarationError(
            path,
            field_path,
            "is declared false. A point chosen inside a stated range and a rate for a date "
            "that has not happened are both assumptions: the field exists to make the claim "
            "unmissable on every figure it touches, not to be switched off -- which is why the "
            "core types it as a Literal admitting one value.",
            "write is_assumption = true",
        )
    return True


def _literal[T: str](path: Path, field_path: str, value: str, allowed: tuple[T, ...]) -> T:
    """A declared name that must be one of a closed set the core admits."""
    for member in allowed:
        if member == value:
            return member
    raise DeclarationError(
        path,
        field_path,
        f"declares {value!r}, which is not one of {sorted(allowed)}. There is no default and "
        "no nearest match: each of these changes the figure, and picking one would answer a "
        "question nobody asked.",
        f"write one of {sorted(allowed)}",
    )
