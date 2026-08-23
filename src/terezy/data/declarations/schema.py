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
