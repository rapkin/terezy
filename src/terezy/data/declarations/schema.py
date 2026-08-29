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

    kind: str
    """An ``ObservationKind`` id -- which staleness threshold these values age under.

    ⚙ **Added by feature 002 as a migration**, and required rather than optional: FR-028
    says the threshold is per kind of value with no permissive default, so a sourced table
    that names no kind is a table whose values could never be reported stale. Every
    declaration in the project gained the field in one change, because a half-applied
    requirement makes ``scripts/check_provenance.py`` red for every file that has not caught
    up yet.

    Resolved against ``data/observation_kinds.toml`` by ``check_provenance.py`` rather than
    by the loader: the feature-001 core records this table becomes -- ``BondTerms``,
    ``InstrumentConstraints``, ``TaxClass`` -- have no field to carry a kind, because their
    staleness verdict is a later feature's, so a kind resolved here would be a value the
    engine reads nowhere. The gate is blocking, so the check is enforced either way.
    """

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

    kind: str
    """An ``ObservationKind`` id -- which staleness threshold these values age under.

    ⚙ **Added by feature 002 as a migration**, and required rather than optional: FR-028
    says the threshold is per kind of value with no permissive default, so a sourced table
    that names no kind is a table whose values could never be reported stale. Every
    declaration in the project gained the field in one change, because a half-applied
    requirement makes ``scripts/check_provenance.py`` red for every file that has not caught
    up yet.

    Resolved against ``data/observation_kinds.toml`` by ``check_provenance.py`` rather than
    by the loader: the feature-001 core records this table becomes -- ``BondTerms``,
    ``InstrumentConstraints``, ``TaxClass`` -- have no field to carry a kind, because their
    staleness verdict is a later feature's, so a kind resolved here would be a value the
    engine reads nowhere. The gate is blocking, so the check is enforced either way.
    """

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


# ---------------------------------------------------------------------------
# 013-enumerated-schedule: a bond declared as the payments it will make
# ---------------------------------------------------------------------------
#
# The same root table and the same ``[instrument] class`` key, on the precedent a fund set:
# one directory, several kinds of declaration, told apart by the one key they all carry.
#
# ⚙ **A payment's label is spelled ``pays``, not ``kind``.** ``kind`` is already the key
# every sourced table uses for the *observation* kind it ages under, and
# `scripts/check_provenance.py` reads it that way. A payment declaring ``kind = "coupon"``
# would be reported as naming an undeclared observation kind -- a true statement about the
# wrong field, sending the reader to fix a line that is correct. The same trap
# ``kind_of_observation`` exists for on a route leg, and the same fix: name the field for
# what it is.


class ScheduledPaymentTable(BaseModel):
    """One ``[[instrument.schedule.payment]]`` -- a dated per-unit amount and its label."""

    model_config = STRICT

    on: str
    """ISO date the payment is made. Not adjusted by anything: no business-day rule is
    declared, because none was applied to a payment somebody has already published."""

    amount: float
    """The payment **per unit**, in the instrument's currency, in its major units.

    A figure published in minor units is converted when it is **transcribed**, and the
    conversion is recorded here as an inference. The engine performs no unit scaling of a
    declared amount (FR-004): a division by 100 in a loader looks like plumbing.
    """

    pays: str
    """``coupon`` or ``principal_repayment`` -- a member of ``core.instruments.interface``'s
    ``PaymentKind``. Declared, never read off the amount, the date or the position."""

    kind: str
    """An ``ObservationKind`` id -- which staleness threshold this payment ages under."""

    source: str
    """This payment's own citation. For a transcribed schedule it is an **inference**: the
    published list carries no labels, and `scripts/check_provenance.py` requires the
    statement to say so."""

    retrieved_on: str

    verified_on: str


class EnumeratedScheduleTable(BaseModel):
    """``[instrument.schedule]`` -- the coverage claim, the face value, and the payments.

    **What is absent is absent by construction.** There is no ``issue_date``, no
    ``coupon_rate_pct``, no ``periodicity``, no ``business_day_rule`` and no
    ``maturity_date``, so a file supplying one gets the unrecognised-field error rather
    than being quietly accepted and ignored (FR-003). There is likewise no second coverage
    bound, which is what makes a two-ended window unrepresentable rather than checked for
    (FR-005).
    """

    model_config = STRICT

    face_value: float
    """Redemption amount per unit, in the instrument's currency. Positive."""

    covers_from: str
    """ISO date from which this list is complete, to the end of the instrument's life."""

    day_count: str
    """A declared key of ``core.primitives.conventions.DAY_COUNT_FNS``.

    Required, and not an exception to the absences above: it is a convention of
    **computation** rather than a term of the issue, and the contractual yield cannot be
    annualised without one (FR-003a).
    """

    published_in_order: list[str] | None = None
    """The payment dates in the order the **source** gave them, where that was not
    ascending. Omitted in the ordinary case; see ``loader`` for why declaring the
    ascending order is refused rather than accepted as a no-op."""

    payment: list[ScheduledPaymentTable]
    """The payments, in ascending date order. The loader neither sorts them nor accepts an
    unordered list."""

    kind: str
    """An ``ObservationKind`` id -- which staleness threshold these values age under."""

    source: str
    """The schedule's own citation, separate from each payment's."""

    retrieved_on: str

    verified_on: str


class EnumeratedVerificationTaskTable(BaseModel):
    """One ``[[instrument.verification_task]]`` on a declared schedule.

    The fund's shape plus one field: ``settles`` names **which inference** the task would
    settle, which is what lets `scripts/check_provenance.py` check the relation FR-022 asks
    for rather than merely counting tasks.
    """

    model_config = STRICT

    settles: str
    """Which inference this would settle: one of the four in ``loader.INFERENCES``."""

    question: str
    """What the documents did not answer, in the words a reader would ask it in."""

    searched: str
    """What was looked at before recording the question."""

    searched_on: str


class EnumeratedInstrumentTable(BaseModel):
    """``[instrument]`` for a bond declared as the payments it will make."""

    model_config = STRICT

    id: str

    name: str

    instrument_class: str = Field(alias="class")
    """``enumerated_schedule``. Aliased for the same reason a bond's is."""

    currency: str

    is_synthetic: bool

    schedule: EnumeratedScheduleTable
    """The one field that decides the form (FR-002). A file carrying this **and**
    ``[instrument.terms]``, or neither, fails on the unrecognised or missing field."""

    constraints: ConstraintsTable
    """Unchanged: what the instrument requires of a purchase is not a term of the paper."""

    tax_classes: dict[str, str]
    """Unchanged, and it must cover every income kind the schedule produces (FR-009)."""

    verification_task: list[EnumeratedVerificationTaskTable]
    """What is inferred, and what would settle it. Required and non-empty: every declared
    schedule rests on inferences, and a file claiming none has not looked."""


class EnumeratedInstrumentFile(BaseModel):
    """A whole ``data/instruments/<id>.toml`` declaring one bond by its payments."""

    model_config = STRICT

    instrument: EnumeratedInstrumentTable


class RateEntryTable(BaseModel):
    """One ``[[jurisdiction.tax_class.rate]]`` entry: the rates in force from a date.

    ⚙ **Feature 006 moved the rates out of the class table and into these entries**, so a
    legislated change is one entry added to a file rather than a rebuild (`data/README.md`
    rule 3, ``SIMULATOR_SPEC.md`` §4.5.1, required test E10). The scalar pair the class
    used to carry is gone rather than deprecated (research.md D1).

    Every numeric field here is an observed legal value, so the citation keys are not
    optional -- **including for a rate of zero**. The exemption is the single most
    decision-relevant number in the model, and an uncited zero is exactly the figure that
    gets believed without checking (Principle I).
    """

    model_config = STRICT

    effective_from: str
    """ISO date this entry comes into force, inclusive.

    **A cited legal fact, and the sharpest trap in the tax data.** It must be exactly the
    date this entry's citation attests. Where a source establishes the current rate but
    not the date the previous one began, no earlier entry is invented: the schedule starts
    at the attested date, and an event before it is a typed refusal rather than a
    defaulted rate (research.md D2, FR-012). Back-dating an entry so that "everything just
    works" would put an invented legal fact in this file while every gate stayed green.
    """

    pit_rate_pct: float
    """Personal income tax as a **percentage** of the taxable base. ``0.0`` for an
    exemption, and the zero carries the citation like any other value."""

    levy_rate_pct: float
    """Military levy as a percentage of **its own** base. Separate from PIT because it is
    a separate charge, and blending the two at source makes cases like a foreign
    withholding creditable against one and not the other unrepresentable."""

    note: str
    """What this entry claims, and **what its citation says about the date**.

    Required per entry rather than only per class, because the effective date is the field
    a reviewer most needs prose for: the rate can be checked against the source in a
    glance, and the date it came into force usually cannot.
    """

    kind: str
    """An ``ObservationKind`` id -- which staleness threshold these values age under.

    Per entry, like the citation: the entry in force before a legislated change and the
    one after it are two observations, and they may age differently.
    """

    source: str

    retrieved_on: str

    verified_on: str


class TaxClassTable(BaseModel):
    """One ``[[jurisdiction.tax_class]]`` entry: a declared tax treatment.

    Carries no rate and no citation of its own. Both live on the dated entries below,
    because two rates cited by two sources are two observations with two verification
    dates, and one mark for both would let a checked figure vouch for an unchecked one
    (research.md D1).
    """

    model_config = STRICT

    id: str
    """Unique across every tax file."""

    applies_to: list[str]
    """Which income kinds this class governs. Non-empty; resolved against the core's
    closed ``TaxableEventKind`` by the loader."""

    note: str
    """Plain-language statement of what this class claims and what it does not.

    Required, not optional. Every tax figure links to its rule, its source and its
    verification date (constitution, *Documentation is part of the feature*), and the
    note is where the rule is stated in words a reader can check the citation against.
    """

    rate: list[RateEntryTable]
    """``[[jurisdiction.tax_class.rate]]`` -- the dated schedule, in effective-date order.

    Non-empty, strictly increasing and non-duplicated: all three are checked by the
    loader, where the file and the field can be named. A class with no entry cannot charge
    anything, and a silent zero is the worst available reading of that.
    """


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


# ---------------------------------------------------------------------------
# 002-ramp-cost: observation kinds, venues, channels, routes, streams, scenarios
# ---------------------------------------------------------------------------
#
# ⚙ **One qualification to "zero field defaults", and it is the only one.** Several fields
# below are declared ``X | None = None``. That is *not* a substituted value: **TOML has no
# null**, so an omitted key is the only way a file can say "nothing is declared here", and
# a pydantic field with no default cannot be omitted at all. The rule is therefore stated
# rather than bent -- a ``= None`` default is permitted **only** where the core field it
# feeds is itself ``X | None`` and ``None`` means *the owner declared nothing*, never
# where it would stand in for a number, a date or a policy. So ``minimum``,
# ``monthly_cap``, ``income_tax_rate_pct`` and ``partner_route`` may be omitted, because
# ``Leg.minimum``, ``Leg.monthly_cap``, ``IncomeStream.income_tax_rate`` and
# ``Route.partner_route`` are all "``None`` means none was declared" in the core; while
# ``fee_pct``, ``verified_on``, ``staleness_days`` and ``policy`` have no default and a
# file that omits one fails.
#
# ``contracts/declaration-schema.md`` writes ``partner_route = null`` and
# ``capacity_pool = null`` in its examples, which no TOML parser accepts. Omission is the
# expressible form of the same declaration, and ``verified_on = ""`` stays the exception it
# already was: present-and-empty, because for a citation a forgotten key and a deliberate
# "not yet" must not look alike.


class ObservationKindTable(BaseModel):
    """One ``[[kind]]`` entry of ``data/observation_kinds.toml``: how fast a value ages."""

    model_config = STRICT

    id: str
    """``p2p_premium``, ``bank_fee_schedule``, ``regulatory_limit``, ``bond_terms``,
    ``tax_rule``, ``venue_terms``. Every sourced table in the project names one of these."""

    staleness_days: int
    """Days after which a value of this kind is reported stale. **No default** (FR-028): a
    kind without one fails at load, because a permissive default is exactly the silently
    stale value the requirement exists to forbid."""

    note: str
    """Why this kind ages at this rate. Required -- a threshold nobody explained is a
    number nobody can argue with."""


class ObservationKindsFile(BaseModel):
    """The whole of ``data/observation_kinds.toml``.

    No provenance keys anywhere in it, deliberately: a staleness threshold is the owner's
    *policy* about how long he will trust a number, not an observation of the world, so
    there is nothing for a citation to vouch for.
    """

    model_config = STRICT

    kind: list[ObservationKindTable]


class VenueTable(BaseModel):
    """One ``[[venue]]`` entry: a place money can sit, and what it can hold."""

    model_config = STRICT

    id: str
    """``monobank_uah``, ``binance``, ``coinbase``, ``ibkr_usd``, ``inzhur``."""

    name: str
    """Human-readable and non-empty. For a fixture it says so in words."""

    currencies: list[str]
    """The currency codes this venue can hold. Non-empty, resolved against the core's
    closed ``Currency`` enum by the loader.

    Declared rather than inferred from the legs that touch the venue: inference would make
    a leg moving dollars into a hryvnia-only account *self-justifying*, since the leg
    declaring the impossible movement would be the evidence that it was possible.
    """


class VenuesFile(BaseModel):
    """The whole of ``data/venues.toml``.

    No citation keys: a venue table carries no observed numeric value, and
    ``core.routes.venues.Venue`` has no provenance field to carry one. Every number
    attached to a venue lives on a leg, in ``data/routes/``, with its own source.
    """

    model_config = STRICT

    venue: list[VenueTable]


class ChannelSideTable(BaseModel):
    """``[channel.buy_side]`` / ``[channel.sell_side]`` -- one side of a two-sided quote.

    **Exactly one of the two numeric forms.** Both set, or neither, is a load-time failure
    (FR-010). There is deliberately no precedence rule: "the markup wins if both are set"
    would silently ignore one of the two numbers the owner wrote, and an empty side is not
    a zero -- zero is declarable, so an absence can only mean an unfinished declaration.

    The side carries its **own** citation because it is its own observation: a P2P screen's
    buy price and its sell price are two numbers, and the loader unions both sides' sources
    with the reference rate's into the channel's provenance so no mark is lost.
    """

    model_config = STRICT

    markup_bps: float | None = None
    """A cost in basis points -- ``150.0`` is 1.5% -- always positive as a cost. Omitted
    when the premium form is used.

    Basis points reach the core **as basis points**: ``ChannelSide.markup_bps`` divides by
    10 000 itself, in one place, beside the channel that uses it. This is not a ``_pct``
    field and must not pass through the loader's percent conversion.
    """

    premium_per_unit: float | None = None
    """A signed offset from the reference, in price currency per unit of foreign currency.

    ``+3.0`` UAH per USD is what the owner reads off a P2P screen. **Zero is legal** (the
    channel is at the reference) and **negative is legal** (it trades below the reference).
    A *missing* premium is refused.
    """

    kind: str
    """An ``ObservationKind`` id: how fast this side's number ages."""

    source: str

    retrieved_on: str

    verified_on: str


class ChannelTable(BaseModel):
    """One ``[[channel]]`` entry: a named, dated, two-sided rate source for one pair."""

    model_config = STRICT

    id: str
    """``nbu_official``, ``interbank``, ``bank_non_cash``, ``cash_desk``, ``card``,
    ``p2p``. Reaches the result's ``channels_applied``, because the choice changes the
    number (FR-011)."""

    pair: list[str]
    """Exactly two currency codes, ordered ``[price currency, unit currency]``.

    ``["UAH", "USD"]`` with a reference of 42 means *42 UAH per USD*. The order is
    load-bearing: it decides whether a leg is buying or selling, and reversing it would
    invert every spread in the system while leaving every number plausible.
    """

    reference_rate: float
    """Price-currency units per one unit of the unit currency, at the reference. Strictly
    positive, and **never transacted at on its own** (FR-010)."""

    buy_side: ChannelSideTable
    """Required. Applied when the unit currency is acquired."""

    sell_side: ChannelSideTable
    """Required, and **not** derived from :attr:`buy_side`. A system computing one from the
    other would be using a mid-rate with extra steps, and would force a symmetric spread on
    a market that is routinely asymmetric."""

    observed_on: str
    """ISO date this quote was seen. Data, never a clock."""

    kind: str
    """An ``ObservationKind`` id for the reference rate's own ageing."""

    source: str

    retrieved_on: str

    verified_on: str


class ChannelFile(BaseModel):
    """A whole ``data/channels/<pair>.toml``: one or more channels for one pair."""

    model_config = STRICT

    channel: list[ChannelTable]


class LegTable(BaseModel):
    """One ``[[route.leg]]`` entry: a single movement of money, as declared."""

    model_config = STRICT

    index: int
    """Position in the chain, from zero. Declared rather than taken from list order so a
    load-time error can name the leg the file itself names -- and checked against the
    position, because an index that disagrees with its own position makes every message
    about that leg point at the wrong lines."""

    kind: str
    """A key of ``core.routes.legs.LEG_COST_FNS``: ``transfer``, ``fx``, ``trade``,
    ``withdrawal``. An unknown kind fails at load naming the value and the known ones."""

    from_venue: str

    to_venue: str

    from_ccy: str
    """Currency in. Equal to :attr:`to_ccy` for every kind except ``fx``."""

    to_ccy: str

    channel: str | None = None
    """The ``FxChannel`` id applied. **Required when ``kind == "fx"`` and forbidden
    otherwise** (FR-011): a transfer with a channel is a declaration that means nothing,
    and accepting it would let a reader believe a conversion happened."""

    capacity_pool: str | None = None
    """The shared rail whose monthly limit this leg consumes, or omitted for none.

    Two legs on two different routes that both run over the owner's Monobank card name the
    **same** pool, and the accumulator keys on the pool rather than the route -- otherwise
    each route would receive its own full limit (research.md D10). A ``monthly_cap`` with no
    pool is refused: there would be no key to accumulate it under, so capacity consumed
    earlier in the month could never reduce it.
    """

    fee_pct: float
    """A percentage of the amount entering this leg: ``0.5`` means 0.5%. Non-negative.
    Divided by 100 exactly once, at the loader."""

    fee_fixed: float
    """A flat fee in the leg's ``from_ccy``. Non-negative."""

    minimum: float | None = None
    """The smallest amount this leg will carry, in ``from_ccy``, or omitted for none. An
    amount below it makes the route unusable, reported with the shortfall (FR-014) -- never
    rounded up."""

    maximum: float | None = None
    """The largest amount this leg will carry per movement, or omitted for none."""

    monthly_cap: float | None = None
    """The most the leg's rail carries in a calendar month, or omitted for none. Requires
    :attr:`capacity_pool`."""

    latency_days: int
    """How long this leg takes. Non-negative. Reported beside the cost, never inside it --
    a slow route is not an expensive one."""

    available_from: str | None = None
    """First ISO date this leg works, or omitted for "always".

    **A fact about the leg, with a source** -- "this corridor closed in March 2025". Never
    an assumption: a regime transition is scenario data with an explicit assumption marker,
    because burying a guess in a field whose every other value is an observation would make
    the two indistinguishable in every output (research.md D8).
    """

    available_until: str | None = None
    """Last ISO date this leg works, or omitted. Same epistemic status as
    :attr:`available_from`."""

    disruption_probability: float
    """The chance this leg stops working, in ``[0, 1]``. Reported, and **never folded into
    a cost** (FR-026): the chance a route stops working is a different claim from what it
    charges."""

    kind_of_observation: str
    """An ``ObservationKind`` id -- which staleness threshold this leg's numbers age under.

    Named ``kind_of_observation`` rather than ``kind`` because ``kind`` on a leg is already
    the *leg* kind. Where a leg's table carries values of two kinds, it names the
    fastest-ageing one: a table is verified as a whole, and the shorter threshold is the
    honest one.
    """

    source: str

    retrieved_on: str

    verified_on: str


class RouteTable(BaseModel):
    """``[route]`` -- one route and its ordered chain of legs."""

    model_config = STRICT

    id: str
    """Unique across every route file. The resolver enforces that across files."""

    provider: str
    """The named provider -- ``Monobank``, ``Binance P2P``, ``Interactive Brokers``.

    Registry identity is ``(provider x currency path x venue)`` and **not** provider alone
    (FR-023), because the number of conversions is usually the largest difference between
    two ways of doing the same thing.
    """

    origin: str
    """Venue id the first leg starts at."""

    destination: str
    """Venue id the last leg ends at."""

    direction: str
    """``inbound`` or ``exit``, declared rather than inferred (FR-027). An exit route is a
    separate declaration, never a reversal of the way in."""

    partner_route: str | None = None
    """The exit route paired with this inbound one. Omitted means **no round-trip figure
    exists** for this route (FR-030) -- it yields ``ExitCostUnknown``, never a reversal and
    never the one-way figure promoted into the gap. Forbidden on an ``exit`` route: a
    pairing is declared once, by the inbound side, so the two halves cannot disagree."""

    status: str
    """``open``, ``constrained`` or ``closed``. ``constrained`` is ranked and flagged;
    ``closed`` is excluded on the date **with its status recorded** (FR-014)."""

    leg: list[LegTable]
    """Non-empty. A route with no legs is refused at load rather than costed as free --
    free is the answer a reader would least question and the one most likely to be wrong."""


class RouteFile(BaseModel):
    """A whole ``data/routes/<id>.toml``: exactly one route.

    One route per file, named after the file, on the instrument precedent: a file declaring
    several would make a duplicate id harder to see and would put two unrelated review
    histories in one place. Inbound and exit are therefore two files, which is also what
    FR-027 wants a reader to see.
    """

    model_config = STRICT

    route: RouteTable


class IndexationTable(BaseModel):
    """``[stream.indexation]`` -- how the amount is expected to grow, as declared."""

    model_config = STRICT

    policy: str
    """``none``, ``cpi`` or ``fixed_rate``. Required: a stream that does not index needs a
    way to say so, and leaving the field out would make "not indexed" and "nobody said"
    indistinguishable."""

    rate_pct: float | None = None
    """The annual rate as a **percentage**, or omitted.

    Omission is legitimate for ``cpi`` (the rate comes from an inflation series nobody has
    declared yet) and for ``none`` (there is no rate). For ``fixed_rate`` it is a
    declaration that means nothing, and the loader refuses it.
    """


class StreamTable(BaseModel):
    """One ``[[stream]]`` entry: an income stream the owner declares about himself.

    No ``source`` and no ``verified_on``. An owner's own salary is not an observation
    needing a citation; it is a statement of fact by the only person who can make it -- the
    same exemption ``data/scenarios/`` has, and the reason ``check_provenance.py`` gains
    ``channels`` and not ``streams``.
    """

    model_config = STRICT

    id: str

    owner_id: str
    """Present from day one, while there is exactly one owner (Principle VII). Retrofitting
    tenancy is the expensive mistake; an unused column is free."""

    currency: str
    """The denomination of :attr:`amount`.

    Declared here and nowhere else in the record the core sees: ``IncomeStream`` has **no**
    currency field, because two fields stating one fact can disagree, and the loader builds
    one ``Money`` from this pair so ``amount.currency`` is the single place.
    """

    amount: float
    """What arrives per :attr:`cadence`, in :attr:`currency`. Non-negative -- ``0.0`` is the
    honest placeholder for a figure the owner has not stated (§11 item 3), and it produces a
    zero result rather than a made-up one."""

    cadence: str
    """``monthly``, ``biweekly`` or ``semimonthly``."""

    arrives_at: str
    """Venue id where the money lands. A route whose ``origin`` differs from this is a
    mismatch, reported rather than assumed away."""

    income_tax_rate_pct: float | None = None
    """Income tax withheld at source, as a **percentage**, or omitted.

    Omitting it means **the owner has not stated one**, which is a different claim from
    stating zero: ``streams.deployable`` then returns ``IncomeTaxRateUndeclared``, which has
    no net field at all, rather than a net figure that quietly equals the gross (FR-007).
    """

    indexation: IndexationTable


class StreamFile(BaseModel):
    """A whole ``data/streams/<owner>.toml``: one owner's income streams."""

    model_config = STRICT

    stream: list[StreamTable]


class FallbackTable(BaseModel):
    """``[scenario.fallback]`` -- what happens to a contribution the route will not carry.

    §4.3.4 calls this the *scenario's* fallback policy, which is why it is declared here
    rather than on a route or a stream: it is a decision about the owner's money, not a
    property of a corridor.
    """

    model_config = STRICT

    policy: str
    """``hold_as_cash``, ``redirect`` or ``skip`` -- three of §4.3.4's four. ``deposit``
    needs a deposit instrument and fails at load naming the feature that will bring it,
    because treating it as "hold as cash" would substitute a default for a policy the owner
    explicitly chose (FR-013)."""

    redirect_to: str
    """Where the excess goes under ``redirect``, and ``""`` for every other policy.

    Present-and-empty rather than omitted, on the ``verified_on`` precedent: a ``redirect``
    whose destination line was forgotten must not read as a deliberate blank. FR-013
    requires the redirect target be *named*.
    """


class RegimeTable(BaseModel):
    """One ``[[scenario.regime]]`` entry: which routes a regime believes in.

    No provenance, and the absence is load-bearing. A belief has nothing to cite; giving a
    regime a source field would invite a citation for a guess.
    """

    model_config = STRICT

    id: str
    """``wartime``, ``normalized``."""

    route_ids: list[str]
    """Ids of the declared routes this regime includes. Non-empty, every one resolved
    against ``data/routes/``, and **partner-closed**: including an inbound route while
    excluding the exit route it names would make money one-way."""


class TransitionTable(BaseModel):
    """One ``[[scenario.transition]]`` entry: an assumed change of regime on a date."""

    model_config = STRICT

    on_date: str
    """ISO date the regime is assumed to change. The date belongs to the regime *after*
    it."""

    before: str
    """Regime id in force up to :attr:`on_date`."""

    after: str
    """Regime id in force from :attr:`on_date` onward."""

    is_assumption: bool
    """Must be declared, and must be ``true``.

    Typed ``bool`` here and ``Literal[True]`` in the core: the loader refuses ``false`` with
    a message that can say *why*, which pydantic could not. FR-020 requires a transition
    date be presented as a stated assumption, and a marker that can be switched off is not
    a marker.
    """

    rationale: str
    """The owner's stated belief, in words. Required: it is what this record carries where
    an observation carries a source."""


class ScenarioTable(BaseModel):
    """``[scenario]`` -- one scenario: its regimes, its transitions, its fallback."""

    model_config = STRICT

    id: str

    owner_id: str
    """Principle VII: every scenario carries an owner from the first commit."""

    fallback: FallbackTable

    regime: list[RegimeTable]
    """At least two: a transition between one regime and itself is not a transition."""

    transition: list[TransitionTable]
    """Non-empty, strictly ascending by date, and joined end to end -- otherwise some date
    falls in a regime nobody declared, and picking one would be inventing the owner's
    belief."""


class ScenarioFile(BaseModel):
    """A whole ``data/scenarios/<id>.toml``: exactly one scenario."""

    model_config = STRICT

    scenario: ScenarioTable


# ---------------------------------------------------------------------------
# 003-route-coverage: the spendable-endpoint list
# ---------------------------------------------------------------------------
#
# One new declaration, and no other format (spec Assumptions). Same three settings as every
# model above, and the same standing rule: **zero field defaults**. There is nothing here that
# could legitimately be omitted -- a venue with no currency and a currency at no venue are both
# half a statement -- so no field below is `X | None`.
#
# ⚙ **No citation keys, and their absence is the design.** `contracts/spendable-schema.md` and
# research.md D4 both argue it: there is no observed value in this file for a source to vouch
# for -- an id, a currency code, and the owner's statement about where he spends. Adding
# `source` / `retrieved_on` / `verified_on` here would invite a citation for a fact about a
# person's life, which is the same category error as citing a regime. The same reading
# `data/venues.toml` already carries in its own header. Every *number* attached to a venue
# lives on a leg, in `data/routes/`, cited.


class OwnerTable(BaseModel):
    """``[owner]`` -- whose list this is.

    A table rather than a bare `owner_id` key beside the array, on the `[jurisdiction]` and
    `[scenario]` precedent: the file declares one owner's facts, so the owner is the document's
    subject rather than a column of it.
    """

    model_config = STRICT

    id: str
    """Non-empty, and checked by the resolver against the owner of the streams it is resolved
    with. Where the owner spends is a fact about *this* person's life (Principle VII)."""


class SpendableTable(BaseModel):
    """One ``[[spendable]]`` entry: a ``(venue x currency)`` where money counts as spent."""

    model_config = STRICT

    venue: str
    """Must name a declared venue that can hold :attr:`currency`. Typed ``str`` and resolved by
    the loader and resolver, which know the file and the field; pydantic would know neither."""

    currency: str
    """Must be the base currency the set was resolved against (FR-004).

    Base currency only, at the specific venues the owner actually spends from -- not "UAH
    anywhere", and not foreign cash in hand. An exit ending in hryvnia at a venue this list does
    not name is deficit 3, exactly as one ending in dollars is.
    """


class SpendableFile(BaseModel):
    """A whole ``data/spendable/<owner_id>.toml``: one owner's spendable endpoints.

    Per-owner, beside ``data/streams/`` and **not** at the root beside curated ``venues.toml``
    (research.md D3). A curated declaration is a public fact about the world; a per-owner one is
    a fact about this person, and putting both at one filesystem level would make the boundary a
    matter of reading field names.
    """

    model_config = STRICT

    owner: OwnerTable

    spendable: list[SpendableTable]
    """Non-empty, checked by the loader. A file with no entries would make every exit deficit 3
    -- a confident wrong answer built out of a forgotten line (research.md D13)."""


# ---------------------------------------------------------------------------
# 006-inzhur-instruments: collective-investment funds
# ---------------------------------------------------------------------------
#
# Same three settings and the same standing rule: ``STRICT`` everywhere, and **zero field
# defaults** except where TOML's lack of a null leaves an omitted key as the only way to
# say "nothing is declared here" -- which here is exactly three fields, each feeding a core
# field that is itself ``X | None``: ``subscription_cutoff`` (a fund that never stops
# accepting money), ``peg`` (a payout that is not pegged to another currency) and
# ``distribution`` (an accumulation fund, which owes no dividend at all).
#
# ⚙ **A fund file and a bond file share a directory and a root table**, and are told apart
# by ``[instrument] class``. The resolver reads that one key and picks a loader, because
# the two declarations have almost nothing in common beyond an id: a fund has no coupon, no
# maturity and no face value, and forcing them into one model would mean a table of
# optional fields where every combination is loadable and only two are meaningful.
#
# ⚙ **``[[instrument.verification_task]]`` carries no numeric leaf and therefore no
# citation**, deliberately. It is the record of a question nobody has answered; a source
# would be a source for *what*?


class FundNavTable(BaseModel):
    """``[instrument.nav]`` -- the declared net asset value of one unit."""

    model_config = STRICT

    per_unit: float
    """In the instrument's unit currency. Strictly positive: a unit worth nothing has no
    price to charge a markup on, and every figure computed from it would be zero while the
    projection still looked complete."""

    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class DeclaredYieldTable(BaseModel):
    """``[instrument.declared_yield]`` -- the rate the fund states about itself.

    Two fields rather than one because a fund may state a range, and the range is the
    answer: MilTech's 25-29% is not a figure with error bars, it is two numbers the fund
    published. A fund stating one figure writes it twice, which reads oddly and is correct
    -- it says "the low end and the high end are the same", which is what a point rate is.
    """

    model_config = STRICT

    low_pct: float
    high_pct: float
    basis: str
    """``simple_annual`` or ``usd_equivalent_annual``, resolved by the loader."""

    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class PegCapTable(BaseModel):
    """One ``[[instrument.distribution.peg.cap]]`` entry -- a dated «граничний курс»."""

    model_config = STRICT

    effective_from: str
    uah_per_unit: float
    """Hryvnia per one unit of the pegged currency. Strictly positive: a ceiling of zero
    would size every payment at nothing, which is not what an undeclared ceiling means."""

    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class PegTable(BaseModel):
    """``[instrument.distribution.peg]`` -- what the payout is sized in, and its ceiling.

    Carries no numeric leaf of its own and therefore no citation: the currency is a
    reference to the core's enum, and every number lives on a dated cap entry that cites
    itself.
    """

    model_config = STRICT

    sized_in: str
    cap: list[PegCapTable]
    """Oldest first. May be **empty**, which declares that no ceiling is known -- and a
    payment dated where no ceiling is declared is refused rather than sized at the full
    assumed rate."""


class DistributionTable(BaseModel):
    """``[instrument.distribution]`` -- what the fund pays out, when, and sized in what."""

    model_config = STRICT

    frequency: str
    basis_note: str
    """The declared basis in words. Required and non-empty: a payout whose basis nobody
    wrote down is one a reader cannot check against the регламент."""

    record_day: str
    payment_day: int
    paid_in: str
    payout_share_pct: float
    """The declared share of the yield paid out; the rest accretes to NAV. ``100.0`` for a
    fund that distributes everything it earns."""

    peg: PegTable | None = None
    """Omitted where the payout is not pegged to another currency. One of the three
    permitted ``= None`` defaults; see the section comment above."""

    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class SpreadTable(BaseModel):
    """``[instrument.spread]`` -- the markup and discount around NAV.

    Four numbers, not two. "Up to 1%" is what the terms allow and "1% is what is charged
    today" is a different claim that nobody has verified; collapsing them would lose the
    distinction FR-024 exists to keep.
    """

    model_config = STRICT

    entry_markup_max_pct: float
    exit_discount_max_pct: float
    live_entry_markup_pct: float
    live_exit_discount_pct: float
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class LegalTermsTable(BaseModel):
    """``[instrument.liquidity.legal]`` -- what the регламент owes, and when it settles."""

    model_config = STRICT

    buyback_before_termination: str
    """``discretionary`` is the only value this engine models, and it is written out rather
    than assumed: the one word that matters about the exit is not a default."""

    settlement_business_days: int
    note: str
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class ObservedPracticeTable(BaseModel):
    """``[instrument.liquidity.practice]`` -- what the company currently does."""

    model_config = STRICT

    settlement_business_days: int
    is_revocable: bool
    """Must be ``true``; the loader refuses ``false``. A buyback that could not be withdrawn
    would be an obligation, and an obligation is declared in the legal terms."""

    note: str
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class LiquidityTable(BaseModel):
    """``[instrument.liquidity]`` -- both readings of the same exit, kept apart."""

    model_config = STRICT

    legal: LegalTermsTable
    practice: ObservedPracticeTable


class FundConstraintsTable(BaseModel):
    """``[instrument.constraints]`` -- the smallest purchase the fund accepts."""

    model_config = STRICT

    minimum_units: float
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class FeeFactTable(BaseModel):
    """One ``[[instrument.fee_fact]]`` -- a researched fee term, recorded as context.

    Nothing computes from these. They exist so a reader can see what the declared net yield
    is net *of*, and the core record they become has no numeric field at all -- which is
    the structural half of owner decision B.
    """

    model_config = STRICT

    what: str
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class VerificationTaskTable(BaseModel):
    """One ``[[instrument.verification_task]]`` -- a question the documents did not answer.

    **No value field, and no citation.** The record exists precisely because nothing is
    known, so there is nowhere for a later contributor in a hurry to put a plausible
    number, and nothing for a source to vouch for.
    """

    model_config = STRICT

    question: str
    searched: str
    searched_on: str


class FundTable(BaseModel):
    """``[instrument]`` for a collective-investment fund."""

    model_config = STRICT

    id: str
    name: str
    instrument_class: str = Field(alias="class")
    """``collective_investment_fund``. Aliased for the same reason a bond's is."""

    unit_currency: str
    is_assumption_driven: bool
    """Must be ``true``; the loader refuses ``false``. A fund whose terms are observed
    rather than stated is a different declaration and a different feature, and the core
    field is ``Literal[True]`` so there is nothing for ``false`` to become."""

    day_count: str
    terminates_on: str
    subscription_cutoff: str | None = None
    """Omitted by a fund that never stops accepting subscriptions. One of the three
    permitted ``= None`` defaults; see the section comment above."""

    nav: FundNavTable
    declared_yield: DeclaredYieldTable
    distribution: DistributionTable | None = None
    """Omitted by an accumulation fund, which owes no dividend at all. That is a declared
    fact rather than a missing field, and it is why nothing invents a payout for MilTech."""

    spread: SpreadTable
    liquidity: LiquidityTable
    constraints: FundConstraintsTable
    tax_classes: dict[str, str]
    fee_fact: list[FeeFactTable]
    verification_task: list[VerificationTaskTable]


class FundFile(BaseModel):
    """A whole fund declaration document: exactly one fund, as with an instrument."""

    model_config = STRICT

    instrument: FundTable


# ---------------------------------------------------------------------------
# 004-composed-paths: the segment bound
# ---------------------------------------------------------------------------
#
# One new declaration, and the smallest one in the project: an owner and an integer. Same three
# settings as every model above, and the same standing rule: **zero field defaults**. FR-006
# rests entirely on that rule -- a `max_segments` with a default would make a forgotten line
# read as a chosen policy, which is the substitution `extra="forbid"` and the absent defaults
# exist together to prevent.
#
# ⚙ **No citation keys, and their absence is the design.** How far the owner is willing to let
# a search run is a statement about him, not an observation of the world, so there is nothing
# for a source to vouch for. The same reading `data/objectives/`, `data/strategies/` and
# `data/spendable/` already carry. Every *number* that describes a corridor lives on a leg, in
# `data/routes/`, cited.
#
# `[owner]` is the shared `OwnerTable` above rather than a copy: it is the same claim -- whose
# file this is -- and two models for it would eventually disagree about whether the id may be
# blank.


class CompositionTable(BaseModel):
    """``[composition]`` -- the owner's policy on how far a chain may run."""

    model_config = STRICT

    max_segments: int
    """At least one, checked by the loader, which can name the file and the field.

    Typed ``int`` under ``strict=True``, so ``2.5`` and ``"3"`` are both refused at the shape
    stage: half a segment is not a chain, and a quoted number is a file whose type and the
    engine's type disagree while the answer still looks right.
    """


class CompositionFile(BaseModel):
    """A whole ``data/composition/<owner_id>.toml``: one owner's reach policy.

    Per-owner, beside ``data/streams/`` and ``data/spendable/`` and **not** at the root beside
    curated ``venues.toml`` (research.md D8, on feature 003's precedent). A corridor is a public
    fact about the world; how far this person will let a search run is a fact about him.
    """

    model_config = STRICT

    owner: OwnerTable

    composition: CompositionTable


# ---------------------------------------------------------------------------
# 008-seed-and-goals: the owner's opening lots, and what the money is for
# ---------------------------------------------------------------------------
#
# Two new declarations, and the first two that live *wholly* on the private side of Principle
# VII's boundary. Same three settings as every model above, and the same standing rule: **zero
# field defaults**, with the one qualification the 002 banner already states -- a `X | None =
# None` is permitted only where the core field it feeds is itself `X | None` and `None` means
# *the owner declared nothing*. That qualification does real work here: `Goal` declares any
# *two* of three variables and the third is the question, so all three are nullable in the
# core record and all three may be omitted in the file. `reason` on a seed is nullable for the
# same reason -- it is required for an estimated basis and forbidden for a known one, a pairing
# no pydantic field can express, so the loader owns it and can say which of the two lines is
# probably wrong.
#
# ⚙ **No citation keys, and their absence is the design.** What the owner paid for a lot, and
# what sum he is aiming at, are his own records rather than observations of the world -- there
# is nothing for a source to vouch for. It is the same exemption `objectives`, `strategies`,
# `streams`, `spendable` and `composition` already carry, and `scripts/check_provenance.py`
# names both directories in `EXEMPT_DIRS` with that reason written out. The gate is fail-closed
# over the data tree, so absence from `SOURCED_DIRS` is an error rather than an exemption. If a
# *market value* ever has to live in either file, it moves to a sourced directory instead of
# the exemption widening.
#
# ⚙ **There is deliberately no `currency` key on a seed** (008 FR-010). A cost is in the base
# currency, full stop: converting a foreign-currency basis needs a rate on the acquisition date
# and this feature has none, so rather than accept the field and refuse the value, the field
# does not exist. A file that states one gets the unrecognised-field error, which is a stronger
# guarantee than a validation rule -- no later change can quietly start converting it.
#
# `[owner]` is the shared `OwnerTable` above rather than a copy, as `composition` does: it is
# the same claim -- whose file this is -- and two models for it would eventually disagree about
# whether the id may be blank.


class SeedTable(BaseModel):
    """One ``[[seed]]`` entry: a holding the owner already has, as a lot rather than a value.

    §4.8: a seed is *units acquired on a date at a price*, because the tax engine needs lots.
    "I hold 100 units worth X today" cannot produce a disposal gain at all.
    """

    model_config = STRICT

    instrument_id: str
    """Must name a curated instrument declaration. The reference is resolved by the resolver,
    which holds the whole set; an unknown one fails at load naming the file and the instrument
    (FR-005), and no placeholder instrument is ever created."""

    quantity: float
    """Units held. Strictly positive, checked by the loader: a lot may not exist at zero."""

    acquired_on: str
    """ISO date the units were acquired. What a holding-period rule is measured from, and the
    date the opening event is recorded on."""

    cost: float
    """What was paid for these units, in the **base currency** (FR-010). Non-negative.

    Zero is a legitimate declaration -- a gift, a bonus allocation -- and is accepted. What is
    refused is the field being *absent*, because a zero substituted for a cost nobody stated
    would make every later disposal compute the wrong gain (FR-006).
    """

    is_synthetic: bool
    """``true`` for a fixture whose holding is invented. Required; there is no default.

    The same field and the same argument ``InstrumentTable`` carries, and here it is doing more
    work than a label. `data/README.md` rule 5 -- the owner's own rule -- permits this file in
    the repository *because* what ships in it is synthetic, so the claim has to be readable by
    something other than a human reading a comment. Defaulting it to ``false`` would let a
    fixture be mistaken for the owner's real position through omission, and the omission runs
    the wrong way round; defaulting it to ``true`` would let his real holdings be committed
    while claiming to be invented, which is worse.
    """

    basis: str
    """``known`` or ``estimated``, and there is no third value and no default (FR-006).

    Typed ``str`` and resolved by the loader rather than by an enum here, for the reason this
    module's docstring gives: the loader knows the file and can name the two words that would
    have worked. Defaulting it to ``known`` would make every forgotten declaration produce a
    confidently unmarked tax figure, which is the single most expensive omission available in
    this file.
    """

    reason: str | None = None
    """Why the owner does not know the cost. **Required when ``basis = "estimated"`` and
    forbidden otherwise** -- a pairing the loader checks, because a reason on a known basis
    means one of the two lines is wrong and guessing which would be inventing a declaration.

    It becomes the citation text of the ``SourceRef`` that marks every figure derived from
    this lot, including the tax on its disposal, which is why an empty one is refused: a mark
    that says nothing is a taint flag rather than provenance (FR-008).
    """


class SeedFile(BaseModel):
    """A whole ``data/seeds/<owner_id>.toml``: one owner's opening lots."""

    model_config = STRICT

    owner: OwnerTable

    seed: list[SeedTable]
    """May be **empty**, and this is the only declaration list in the project of which that is
    true (008 FR-024, research.md D9). An empty spendable list makes every exit fail a test it
    should pass; an empty seed list means the owner holds nothing, which is an ordinary state
    of affairs and not a mistyped path."""


class GoalTable(BaseModel):
    """One ``[[goal]]`` entry: a target the owner states as any two of three variables."""

    model_config = STRICT

    id: str
    """Unique within the file. A duplicate is refused at load."""

    is_synthetic: bool
    """``true`` for a fixture whose target is invented. Required; see :class:`SeedTable`."""

    currency: str
    """The target's denomination, resolved against the closed ``Currency`` enum. Must be the
    base currency in this feature; another is refused as *not yet modelled* by the resolver,
    which is where the run's base currency is known."""

    monthly_contribution: float | None = None
    """What goes in each month, or omitted when that is the variable to solve for.

    Non-negative: a withdrawal is not a contribution. **Zero is legal** -- a goal reached out
    of growth on the starting amount alone -- which is why omission and zero mean different
    things here and the field cannot be defaulted to either.
    """

    target_sum: float | None = None
    """How much is wanted, or omitted when that is the question. Strictly positive."""

    target_date: str | None = None
    """ISO date the target is wanted by, or omitted when that is the question."""


class GoalFile(BaseModel):
    """A whole ``data/goals/<owner_id>.toml``: one owner's targets.

    No growth assumption and no starting amount, deliberately (008 FR-012). Neither is a
    property of the goal: both are inputs to the evaluation, both carry their own provenance,
    and a rate written here would silently become "the rate" for every goal in the file.
    """

    model_config = STRICT

    owner: OwnerTable

    goal: list[GoalTable]
    """May be empty, for the reason :attr:`SeedFile.seed` may: a person with no stated target
    is an ordinary person."""


# ---------------------------------------------------------------------------
# 007-cpi-real-terms: the CPI series and the inflation assumption
# ---------------------------------------------------------------------------
#
# Two declarations of opposite epistemic kinds, which is why they are two files in two
# directories rather than two tables in one.
#
# `data/cpi/*.toml` is the most heavily *cited* declaration in the project: one source per
# observation, 411 of them in the shipped Ukrainian series, every `verified_on` empty because
# a number that was downloaded is not a number anyone has checked. It lives in `SOURCED_DIRS`
# and `scripts/check_provenance.py` reports every one of those empties as a warning, which is
# correct and expected.
#
# `data/scenarios/inflation/*.toml` is a *belief*. It carries `is_assumption = true` where an
# observation carries a source, on `TransitionTable`'s precedent, and `data/scenarios/` is
# exempt from the citation gate for that reason. An external published forecast may carry a
# citation too -- and is **still** an assumption (007 FR-010): a forecast is a statement about
# a year that has not happened, and no source makes it observed.
#
# Same three settings as every model above, and the same standing rule: **zero field
# defaults**. Nothing below may be omitted. The assumption's four citation keys follow
# `verified_on`'s own precedent -- present and empty for the owner's own belief, all filled in
# for an external forecast -- because a forgotten line must not read as a deliberate blank.
#
# ⚙ **The shipped `data/cpi/ua.toml` is generated by `scripts/fetch_cpi.py`.** Where that file
# and these models disagree, the models are right and the script is updated (007 research.md
# D10): the file can be regenerated, while a schema bent to match a generator's convenience is
# a schema that will accept the next convenience too.


class CpiSeriesTable(BaseModel):
    """``[series]`` -- what this price index measures, and in what form."""

    model_config = STRICT

    id: str
    """``ua_cpi_monthly``. Unique across every declared series; a collision is refused by the
    resolver naming both files, because whichever loaded second would win by directory order
    and every real figure would silently rest on the other one."""

    country: str
    """The economy measured. Half of the identity FR-002 requires, and the half that makes a
    second country's index a data-only addition rather than a rewrite."""

    index: str
    """Which index this is, in words. Two indices for one country are two series."""

    periodicity: str
    """``monthly``. Typed ``str`` and resolved by the loader against the core's closed set, so
    the error can name the file and list what would have worked.

    **Declared per series and never assumed** (FR-002): the annualisation divides by the
    number of periods in a year, so an engine that assumed twelve would be wrong by a factor
    of three on a quarterly series with nothing in the output to say so.
    """

    base: str
    """The form the values are in: ``"previous month = 100"``.

    Carried as stated text rather than inferred, because reading a month-on-month series as a
    level index gives a wrong answer that looks entirely plausible, and the file is the only
    thing that knows which it is.
    """


class CpiObservationTable(BaseModel):
    """One ``[[observation]]`` entry: a period, its published value, and where it came from."""

    model_config = STRICT

    period: str
    """The period covered, as ``YYYY-MM`` for a monthly series. Checked against the declared
    periodicity by the loader, which can name the file and the offending period."""

    value: float
    """The published index **against the previous month**: ``100.9`` is +0.9%.

    Strictly positive, checked by the loader. Not a formality: a factor of zero or below makes
    the chained product zero or negative and puts the Fisher denominator on or past zero, so
    the constraint on the declaration is what keeps the arithmetic total.
    """

    kind: str
    """The ``ObservationKind`` this value ages under -- ``cpi_index``, 45 days.

    Per observation rather than per series because ``check_provenance.py`` treats each
    ``[[observation]]`` as a sourced table and requires a kind on each, and because that is
    where the threshold is declared for every other sourced table in the project.
    """

    source: str
    """Non-empty. A published statistic with no citation is the thing Principle I forbids."""

    retrieved_on: str
    """ISO date the value was read from the publisher.

    Load-bearing beyond provenance: an observation's period must have **ended** before this
    date, or the value is a forecast wearing an observation's clothes. Checking against the
    file's own retrieval date rather than against a clock is what keeps the loader
    deterministic -- the same file loads the same way in 2026 and in 2030.
    """

    verified_on: str
    """Present, and empty for every shipped value. See the module docstring on why the key may
    not be omitted: a forgotten line and a deliberate "not yet" must not look alike."""


class CpiFile(BaseModel):
    """A whole ``data/cpi/<economy>.toml``: exactly one series and its observations."""

    model_config = STRICT

    series: CpiSeriesTable

    observation: list[CpiObservationTable]
    """Non-empty, strictly ascending by period, no duplicates -- all three checked by the
    loader, which can name the offending row.

    **Gaps are permitted**, and that is not an oversight: a month the publisher did not
    publish is a fact, and FR-004 forbids inventing one. The refusal for a gap belongs to the
    deflation, where the *window* is known and the missing month can be named for the question
    actually asked.
    """


class InflationAssumptionTable(BaseModel):
    """``[inflation_assumption]`` -- a declared belief about future inflation.

    ``RegimeTransition``'s shape, applied to a rate instead of a date. Everything here is a
    statement about a year that has not happened, and the fields exist to keep that unmissable
    rather than to be computed with.
    """

    model_config = STRICT

    id: str
    """Recorded in the run manifest, so a result can say which belief produced it (FR-015).
    Two runs with two different assumptions are two results, never one."""

    owner_id: str
    """Whose belief this is. Present from the first commit, per Principle VII."""

    annual_rate_pct: float
    """The assumed rate per annum as a **percentage**: ``10.0`` means 10%.

    The ``_pct`` suffix is part of the name so the unit is unmissable at the point of editing,
    and the loader divides by 100 exactly once. Strictly above ``-100``: prices cannot fall to
    nothing, and the bound is what keeps the Fisher denominator away from zero.
    """

    is_assumption: bool
    """Must be ``true``. Refused when false by the loader, and typed ``Literal[True]`` in the
    core, so the claim cannot be switched off and cannot be omitted."""

    rationale: str
    """The owner's stated belief in words. Required -- a rate with no reasoning behind it is
    indistinguishable from a typo, and a figure conditional on an unexplained guess cannot be
    argued with."""

    kind: str
    """The staleness kind an external forecast ages under, or ``""`` for the owner's own belief.

    A belief does not go stale; it is superseded when the owner changes his mind, which is a
    different event with no threshold. A *retrieved* forecast does, because the publisher
    issues a new one.
    """

    source: str
    """An external forecast's citation, or ``""`` for the owner's own figure.

    Empty is a *statement* here, not an omission: a belief has nothing to cite, and attaching a
    fabricated source to one would be the worst defect in Principle I's list. The loader
    refuses a half-filled citation -- all four keys empty, or ``source``, ``retrieved_on`` and
    ``kind`` all filled -- because a partial one is an edit somebody abandoned.
    """

    retrieved_on: str
    """When an external forecast was read, or ``""`` alongside a bare belief."""

    verified_on: str
    """When the quotation was checked against the publisher, or ``""``.

    Verifying a forecast vouches for the *quotation*, never for the number: there is no
    primary source for next year's prices, and a verified forecast is still an assumption.
    """


class InflationAssumptionFile(BaseModel):
    """A whole ``data/scenarios/inflation/<owner>.toml``: one declared belief.

    In a **subdirectory** of ``data/scenarios/`` rather than beside ``war_end.toml``, because
    the resolver globs ``scenarios/*.toml`` as scenario documents and does not recurse -- the
    same reading ``data/instruments/nav/`` already carries. It keeps the citation exemption
    ``data/scenarios/`` has, which is what a belief needs, without pretending to be a scenario.
    """

    model_config = STRICT

    inflation_assumption: InflationAssumptionTable


# ---------------------------------------------------------------------------
# 009-tax-depth: how a tax year is assembled, and the owner's positions on it
# ---------------------------------------------------------------------------
#
# Two declarations of opposite epistemic kinds again, and split the same way 007's were.
#
# `data/tax/timing/<jurisdiction>.toml` is **cited law**: which category a class belongs to,
# whether that category nets, what a loss in it does, when the money is due, and what each
# basis method stands on. It sits under `data/tax/`, so `scripts/check_provenance.py` requires
# a citation on every table carrying a number -- which is why the deadlines are declared as
# month and day integers rather than as an `"08-01"` string. The gate counts numeric leaves,
# and a legal value that reaches the engine as text would sit outside it.
#
# `data/scenarios/tax/<owner>.toml` is the **owner's own**: whether he filed, and which branch
# of an unanswered legal question this run takes. It carries `is_assumption = true` where an
# observation carries a source, on `TransitionTable`'s precedent.
#
# Same three settings as every model above, and the same standing rule: **zero field
# defaults**. A missing filing decision must fail rather than read as `false`.


class TimingCategoryTable(BaseModel):
    """``[[timing.category]]`` -- how one income category's year is put together."""

    model_config = STRICT

    id: str
    treatment: str
    """``nets``, ``per_event`` or ``outside``. Resolved by the loader against the core's closed
    set, so an unrecognised value names the file and lists what would have worked."""

    carryforward: str
    """``unlimited`` or ``none``. What a negative annual result does."""

    settlement: str
    """``self_assessed`` or ``withheld_at_source``. FR-003 asks for the timing behaviour of a
    tax class as declared data, and this is it: a class names its category, the category names
    its settlement, so a withheld-at-source class is a data-only addition."""

    declare_by_month: int
    declare_by_day: int
    pay_by_month: int
    pay_by_day: int
    """The deadlines, in the year **after** the tax year. Four integers rather than one
    ``"05-01"`` string: a recurring deadline has no year of its own, and the provenance gate
    sees numbers rather than text."""

    non_business_day_rule: str
    """The declared convention when a deadline falls on a non-business day (FR-008). Resolved
    against ``core.primitives.conventions``, so an unrecognised name fails at load."""

    note: str
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class TimingClassTable(BaseModel):
    """``[[timing.class]]`` -- which category one declared tax class belongs to.

    A reference rather than an observation, so no citation: the rates are cited where they are
    declared. Whether the class **resolves** is the resolver's job, since it needs every rate
    pack parsed first.
    """

    model_config = STRICT

    tax_class: str
    category: str
    note: str


class LotMethodTable(BaseModel):
    """``[[timing.lot_method]]`` -- what the sources say about one basis method.

    Cited even where the finding is that nothing prescribes the method: "no source prescribes
    this" is a claim about the law, and an uncited one is indistinguishable from nobody having
    looked.
    """

    model_config = STRICT

    method: str
    verdict: str
    what_the_law_says: str
    kind: str
    source: str
    retrieved_on: str
    verified_on: str


class TimingTable(BaseModel):
    """``[timing]`` -- the root table of one jurisdiction's assessment rules."""

    model_config = STRICT

    jurisdiction: str
    tax_currency: str
    category: list[TimingCategoryTable]
    lot_method: list[LotMethodTable]
    class_: list[TimingClassTable] = Field(alias="class")
    """``class`` is a Python keyword, so the field is aliased. ``populate_by_name`` is off, so
    the file must spell it ``[[timing.class]]`` and nothing else."""


class TimingFile(BaseModel):
    """A whole ``data/tax/timing/<jurisdiction>.toml``."""

    model_config = STRICT

    timing: TimingTable


class FilingTable(BaseModel):
    """``[[tax_positions.filing]]`` -- was one year's declaration filed?

    No default anywhere, which is the whole content of FR-014: a year with investment
    operations and no entry stops the run naming the year.
    """

    model_config = STRICT

    year: int
    filed: bool
    note: str


class CarryforwardChainTable(BaseModel):
    """``[tax_positions.carryforward_chain]`` -- the position on an unanswered question."""

    model_config = STRICT

    position: str
    """``chain_broken_forfeits`` or ``chain_restorable``. Neither is a default."""

    question: str
    rationale: str
    resolution_path: str
    """What would retire the label. An individual tax consultation, and nothing less."""

    is_assumption: bool


class SelfDeclarantMethodTable(BaseModel):
    """``[tax_positions.self_declarant_method]`` -- which source-backed method this run reads
    as governing a self-declaring individual."""

    model_config = STRICT

    method: str
    question: str
    rationale: str
    resolution_path: str
    is_assumption: bool


class TaxPositionsTable(BaseModel):
    """``[tax_positions]`` -- the owner's own tax statements for one run."""

    model_config = STRICT

    owner_id: str
    is_synthetic: bool
    """Required, on ``seeds`` and ``goals``' precedent: a label only a human can read cannot be
    checked by anything (`data/README.md` rule 5)."""

    filing: list[FilingTable]
    carryforward_chain: CarryforwardChainTable
    self_declarant_method: SelfDeclarantMethodTable


class TaxPositionsFile(BaseModel):
    """A whole ``data/scenarios/tax/<owner>.toml``."""

    model_config = STRICT

    tax_positions: TaxPositionsTable


# ---------------------------------------------------------------------------
# 010-full-tuple: how an instrument is reached
# ---------------------------------------------------------------------------
#
# Same three settings and the same standing rule: ``STRICT`` everywhere, and **zero field
# defaults** except where TOML's lack of a null leaves an omitted key as the only way to say
# "nothing is declared here" -- which here is exactly one field, ``price``, feeding a core
# field that is itself ``Money | None``.
#
# ⚙ **A separate file rather than four keys on the instrument declaration.** Every field here
# is a property of the **option** -- this instrument, reached this way -- rather than of the
# security: where it is bought, where its proceeds land, what a unit costs *at that venue*,
# and how risky reaching it that way is. Today the resolver enforces **one row per
# instrument**, so one instrument at two venues is not yet declarable; what the separate file
# buys is that it becomes declarable here, in one file, without touching the terms the paper
# carries. Keying by (instrument, venue) now would also need a venue term on the tuple, and
# building it for a second venue nobody has declared would be speculation.
#
# ⚙ **``[[access]]`` itself carries no numeric leaf and therefore no citation**, deliberately.
# A venue id, an instrument id and a risk-class label are references and statements, not
# observations -- the same reading ``[instrument.tax_classes]`` and ``data/venues.toml``
# already carry. The one observed value, the unit price, is a *venue quote* and lives in its
# own ``[access.price]`` table with its own four citation keys, exactly as ``[instrument.nav]``
# does.


class AccessPriceTable(BaseModel):
    """``[access.price]`` -- what one unit costs at the venue the instrument is bought from."""

    model_config = STRICT

    per_unit: float
    """The price of one unit. Strictly positive.

    A **quote**, not a term of the paper: a bond's declaration states the face value it
    repays, which is a different number the moment it trades away from par, and sizing a
    purchase from the face value would be assuming par in code where nobody declared it.
    """

    currency: str
    """What the quote is in. Stated rather than inherited from the instrument, and then
    **checked against** the instrument's own declared currency by the resolver.

    Two declarations of one fact, on purpose and on ``_check_partner``'s precedent: a price
    that silently adopted whatever currency the instrument named would be unreadable on its
    own -- ``per_unit = 1000.0`` of what? -- and a file that can state something wrong is a
    file whose disagreement can be reported. One that cannot is a file whose author's
    intention is unrecoverable.
    """

    kind: str
    """The ``ObservationKind`` this quote ages under. A price goes out of date faster than a
    coupon rate does, which is the whole reason the threshold is declared per kind."""

    source: str
    """Non-empty. A price with no citation is the thing Principle I forbids."""

    retrieved_on: str
    """ISO date the quote was read."""

    verified_on: str
    """Present, empty where nobody has checked it. See the module docstring on why the key may
    not be omitted."""


class AccessTable(BaseModel):
    """One ``[[access]]`` entry: how one declared instrument is reached."""

    model_config = STRICT

    instrument_id: str
    """The declared instrument -- of either kind. Resolved by the resolver against both
    registries, because a fund and a bond share an id space and an entry naming neither is a
    typo the reader must be told about."""

    bought_at: str
    """The venue the purchase happens at. Resolved against ``data/venues.toml``, and required
    to be able to hold the instrument's currency."""

    proceeds_to: str
    """The venue the instrument's proceeds land at. Resolved the same way, and declared
    separately from :attr:`bought_at` rather than assumed equal to it."""

    risk_class: str
    """The declared risk class of this option. Non-empty, carried into every outcome, and
    scored nowhere."""

    price: AccessPriceTable | None = None
    """The unit quote, or omitted where the instrument declares its own price.

    **The one omittable field in this model**, and the one default in it: TOML has no null, so
    an omitted table is the only way to say *this instrument prices itself*. Which kinds may
    omit it is not a matter of taste and is not checked here -- it is a relation between this
    file and the instrument's own, so the resolver decides it and can name both files.
    """


class AccessFile(BaseModel):
    """A whole ``data/access/<name>.toml``: one or more access declarations."""

    model_config = STRICT

    access: list[AccessTable]
    """Non-empty, checked by the loader. A file declaring nothing is a file somebody started
    and did not finish, and reading it as "no instrument is reachable" would turn every tuple
    in the comparison into a refusal built out of a forgotten line."""
