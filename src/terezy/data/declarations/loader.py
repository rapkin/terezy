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
from terezy.core.primitives import conventions
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.tax.interface import TaxableEventKind, TaxClass
from terezy.data.declarations import schema
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping

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
) -> SourceRef:
    """One table's citation, as the core's ``SourceRef``.

    The id names the file and the table (see :func:`source_id`), the citation is required
    non-empty, and an empty ``verified_on`` becomes ``None`` -- the unverified mark that
    FR-015 propagates through every figure derived from this table.
    """
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
