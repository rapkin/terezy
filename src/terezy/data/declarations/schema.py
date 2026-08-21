"""The TOML shapes, as pydantic models configured against pydantic's own defaults.

This module is the **only** place in the project where a validation-library type appears
(research.md D6, and the layer contract in ``.importlinter`` that keeps ``pydantic`` out
of ``core``). It is also the one permitted exception to the functional style: every model
here is a class with a base class, which is what pydantic is, and nothing it produces
escapes this package -- :mod:`terezy.data.declarations.loader` turns each one into a plain
frozen core record and the models stop existing.

**The configuration is the design.** Three settings, each closing a specific way a data
file can lie about itself:

``extra="forbid"``
    *Is* FR-016's unrecognised-field rule. A misspelled ``min_tickett`` sitting unread
    beside the real field would be a declared constraint that does nothing, and the
    engine would run happily with a limit nobody enforced.

``strict=True``
    Turns off coercion. ``coupon_rate_pct = "15.5"`` is a quoted string, and quietly
    reading it as a number would mean the file's type and the engine's type disagree
    while the answer still looks right. Note what strict mode still permits: an ``int``
    where a ``float`` is declared, because that widening is lossless -- ``face_value =
    1000`` is accepted and is the same value as ``1000.0``. It does *not* permit ``bool``
    for a number, or a number for a string.

``frozen=True``
    A validated document is a fact about a file on disk. Nothing may edit it afterwards
    and hand on a value that no file contains.

**Zero field defaults, anywhere.** Not one model below has a default, and that is a
standing rule rather than a coincidence: FR-016 says *"a default value MUST NOT be
substituted for anything absent"*, and in pydantic a default is the only mechanism by
which that substitution can happen. So the absence of defaults is the enforcement. Two
consequences a reader should expect and not try to fix:

* ``verified_on`` must be **present** in every sourced table, and empty (``""``) is how
  a value says it is unverified (FR-014). The key being absent is an error; a default of
  ``""`` would make "nobody filled this in" indistinguishable from "checked, and
  unverified" -- and would silently mark verified data unverified the day the key was
  forgotten.
* ``is_synthetic`` must be **stated**. Defaulting it to ``false`` would let a fixture be
  mistaken for a real issue through omission, and the omission runs the wrong way round.

**What these models deliberately do *not* validate.** Dates are typed ``str`` and parsed
by the loader; convention names, currencies, instrument classes and taxable event kinds
are typed ``str`` and resolved by the loader against the core's registries. That is not
laziness, it is where the error message can be good: the loader knows the file path and
the field path and can say *"``act/360`` is not a day count; known: act/365, act/act,
30/360"*, which is what FR-021 asks for. A pydantic validator would know the value and
not the file. This module owns **shape**; the loader owns **meaning**.

Dates are strings in these files rather than TOML's native date type, following the
contract's own examples (``retrieved_on = "2026-08-21"``). Under ``strict=True`` a
``date``-typed field would then reject every one of them, so the choice is between
changing the file format and parsing at the loader. Parsing at the loader is what gives
``instrument.terms.issue_date`` a message naming the file.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

STRICT: Final = ConfigDict(extra="forbid", strict=True, frozen=True)
"""The one configuration every model here uses.

Assigned rather than inherited from a shared base model on purpose: a base class would
be a second inheritance layer in the one module allowed any, and the point of naming the
config is that a reader can see all three settings at each model without following a
hierarchy. Sharing the object also means a model cannot drift to a laxer setting by
copying a neighbour and editing one word.
"""


class BondTermsTable(BaseModel):
    """``[instrument.terms]`` -- the contractual terms, and where they were read from."""

    model_config = STRICT

    face_value: float
    """Redemption amount per unit, in the instrument's currency. Positive."""

    coupon_rate_pct: float
    """Annual coupon as a **percentage** of face: ``15.5`` means 15.5%.

    The ``_pct`` suffix is part of the field name so the unit is unmissable at the point
    of editing, which is the failure this naming prevents: a file saying ``0.155`` and
    meaning 15.5% is indistinguishable from one meaning 0.155%. The loader divides by 100
    exactly once.
    """

    issue_date: str
    """ISO date the instrument started accruing."""

    maturity_date: str
    """ISO date the principal is repaid. Strictly after ``issue_date``, and it is the
    *engine* that says so: an impossible instrument is a well-formed declaration."""

    periodicity: str
    """A declared key of ``core.primitives.conventions.PERIODICITY_FNS``."""

    day_count: str
    """A declared key of ``core.primitives.conventions.DAY_COUNT_FNS``."""

    business_day_rule: str
    """A declared key of ``core.primitives.conventions.BUSINESS_DAY_FNS``."""

    source: str
    """A URL or document reference. These three keys are the terms' own citation.

    Provenance sits **per table, not per scalar** (the declaration-schema contract):
    values sharing a source are declared together and cite it once, and facts from
    different sources go in different tables. That is why ``[instrument.constraints]``
    repeats these keys instead of borrowing the terms' -- a minimum ticket and a coupon
    rate are two observations, and one citation covering both would be a claim about the
    source that is not true.
    """

    retrieved_on: str

    verified_on: str


class ConstraintsTable(BaseModel):
    """``[instrument.constraints]`` -- what the instrument requires of a purchase."""

    model_config = STRICT

    min_ticket: float
    """Smallest amount that may be invested, in the instrument's currency. Positive."""

    min_unit: float
    """Smallest buyable increment, in units. Positive."""

    source: str
    """Separate from the terms' citation, because a minimum ticket is a venue's fact and
    a coupon rate is an issuer's."""

    retrieved_on: str

    verified_on: str


class InstrumentTable(BaseModel):
    """``[instrument]`` -- the declaration itself, with its two sourced sub-tables."""

    model_config = STRICT

    id: str
    """Unique across every instrument file. The resolver enforces that across files."""

    name: str
    """Human-readable and non-empty. For a fixture it says so in words."""

    instrument_class: str = Field(alias="class")
    """Which ``InstrumentOps`` computes this thing's events.

    Declared as ``class`` in the file, because that is what it is called in the domain,
    and ``class`` is a Python keyword -- hence the alias. Only the alias is accepted:
    ``populate_by_name`` is left off, so a file writing ``instrument_class`` gets the
    unrecognised-field error rather than working by accident and diverging from every
    other file.
    """

    currency: str
    """The denomination, resolved against the core's closed ``Currency`` enum."""

    is_synthetic: bool
    """``true`` for a fixture whose terms are invented. Required; see the module
    docstring for why a default of ``false`` would be the wrong way round."""

    terms: BondTermsTable

    constraints: ConstraintsTable

    tax_classes: dict[str, str]
    """``[instrument.tax_classes]`` -- income kind to tax-class id.

    A table, not a scalar: the same instrument is taxed differently on distribution and
    on disposal. It carries no provenance because it holds *references*, not
    observations -- the citation lives with the rates, in the tax file.

    Typed ``dict[str, str]`` rather than an enum-keyed mapping so that an unrecognised
    income kind is reported by the loader naming the file, the key and the kinds that
    exist, instead of by pydantic naming a key it cannot place in a file.
    """


class InstrumentFile(BaseModel):
    """A whole ``data/instruments/<id>.toml`` document: exactly one instrument."""

    model_config = STRICT

    instrument: InstrumentTable
    """One instrument per file, named after the file. A file declaring several would make
    a duplicate id harder to see and would put two unrelated review histories in one
    place."""


class TaxClassTable(BaseModel):
    """One ``[[jurisdiction.tax_class]]`` entry: a declared tax treatment.

    Every numeric field here is an observed legal value, so the citation keys are not
    optional -- **including for a rate of zero**. The exemption is the single most
    decision-relevant number in the model, and an uncited zero is exactly the figure that
    gets believed without checking (Principle I).
    """

    model_config = STRICT

    id: str
    """Unique across every tax file."""

    applies_to: list[str]
    """Which income kinds this class governs. Non-empty; resolved against the core's
    closed ``TaxableEventKind`` by the loader."""

    pit_rate_pct: float
    """Personal income tax as a **percentage** of the taxable base. ``0.0`` for an
    exemption, and the zero carries the citation like any other value."""

    levy_rate_pct: float
    """Military levy as a percentage of **its own** base. Separate from PIT because it is
    a separate charge, and blending the two at source makes cases like a foreign
    withholding creditable against one and not the other unrepresentable."""

    note: str
    """Plain-language statement of what this class claims and what it does not.

    Required, not optional. Every tax figure links to its rule, its source and its
    verification date (constitution, *Documentation is part of the feature*), and the
    note is where the rule is stated in words a reader can check the citation against.
    """

    source: str

    retrieved_on: str

    verified_on: str


class JurisdictionTable(BaseModel):
    """``[jurisdiction]`` -- one jurisdiction's rule pack."""

    model_config = STRICT

    id: str
    """Short jurisdiction identifier, ``"ua"``."""

    name: str
    """Human-readable, including the residence status the pack assumes."""

    base_currency: str
    """The currency this jurisdiction assesses tax in, resolved against ``Currency``.

    Declared rather than assumed: the tax role of currency is distinct from the base and
    display roles (Principle VI), and the day a second jurisdiction arrives this field is
    the thing that stops UAH being hard-wired as the tax currency of the world.
    """

    tax_class: list[TaxClassTable]
    """The declared classes, as an array of tables. Non-empty: a jurisdiction file that
    declares no class is a file with no content, and loading it would leave every
    reference to it unresolved for a reason nobody reported."""


class TaxFile(BaseModel):
    """A whole ``data/tax/<jurisdiction>.toml`` document: one jurisdiction's pack."""

    model_config = STRICT

    jurisdiction: JurisdictionTable
