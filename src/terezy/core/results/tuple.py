"""The tuple and its outcome: what reaches a spendable endpoint, and what it cost to get there.

Constitution Principle VI names the product's unit of analysis::

    (instrument) x (funding route in) x (tax treatment) x (exit route out) x (risk class)

These records are the join, and `SIMULATOR_SPEC.md` §8 question 1 -- *does anything beat
15.5% tax-free OVDP after every other option's fees, taxes and access costs?* -- is the
question they exist to make computable. What feature 001's hurdle rate excluded, a tuple
outcome accounts for, and that is asserted rather than described:
``tests/contract/test_every_figure_states_its_scope.py``.

**The rule that governs this module: nothing here holds a figure the join computed itself.**
Every amount below came from the call that owns it -- 002's costing, 001's or 006's
projection, the declared tax rules -- and the join's own content is the chaining and the
refusals (research.md D1). A figure the join invented would have no owner and no test would
know where to check it.

**Both figures, always** (research.md D8). :attr:`TupleOutcome.reaches` is what can be spent;
:attr:`TupleOutcome.implied_rate` is what compares across horizons. Reporting one invites a
reader to derive the other under an assumption the tool never made -- and the assumption
available here is reinvestment, which is exactly the number FR-025 forbids inventing.

**Two exit-unknown cases, and they are different types.** :class:`NoExitRouteDeclared` is
002's FR-030 inherited whole: nobody has costed the way out of the *venue*.
:class:`NoExitTermsDeclared` is the instrument's own way out being unavailable. They call for
different actions -- declare a route, versus wait for termination or accept the discount --
so a reader must be able to tell them apart without reading prose (FR-008).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final, Literal

from terezy.core.instruments.interface import Assumptions, DateRange
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.ramp import ExitCostUnknown, RouteUnusable
from terezy.core.routes.legs import RouteStatus
from terezy.core.routes.path import Candidate, ExitChoice

InstrumentPlan = Assumptions | FundAssumptions
"""How the holding is run, and therefore **which declared way out this tuple takes**.

Matched with ``match``, never distinguished by a flag, and deliberately not a new record
wrapping the two: they are already the two per-kind assumption records, each required in full
with no default anywhere in the stack, and a wrapper would be a third place for a run's
choices to live.

The fund half carries the term that makes this the tuple's *exit terms* and not merely its
run settings: ``FundAssumptions.exit_on`` and ``liquidity_mode`` choose between the fund's
declared ways out -- a requested buyback at a discount settled in so many business days, or
the termination payout -- each with its own terms (spec.md, Key Entities). A bond has one
declared way out, redemption at maturity, so ``Assumptions`` names none.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Tuple:
    """The unit of analysis: an instrument, funded from a stream, reached and left by routes.

    **Identity is all five terms** (FR-010, research.md D5). The same instrument funded from
    the hryvnia salary and from the dollar contract income is two tuples with two outcomes,
    and that is the product's whole thesis -- it is only true if the key says so. A cost or an
    outcome attributed to an instrument alone stays unrepresentable, as 002's FR-008 and 004's
    FR-011 already require, because there is no type here with a shape to hold one.

    Keyword-only: ``instrument_id`` and ``stream_id`` are adjacent strings, and a positional
    constructor would let them be transposed with no type error anywhere.
    """

    instrument_id: str
    """The declared instrument bought -- of either declaration kind."""

    stream_id: str
    """Which declared income stream funds it. The term that carries §4.3.1's finding."""

    route_in: Candidate
    """The way in: one declared route, or a chain of them composed at query time."""

    exit_terms: InstrumentPlan
    """Which declared way out of the *instrument* this tuple takes, and how the holding is
    run. See :data:`InstrumentPlan`."""

    route_out: ExitChoice
    """The way out of the *venue*: a named chain, or
    :data:`~terezy.core.routes.path.FROM_THE_DECLARATION` to use the one the declarations name.

    Two different gaps hide behind one word, which is why this and :attr:`exit_terms` are
    separate fields rather than one "exit" (FR-008).
    """


Part = Literal["ramp_in", "entry", "lifecycle", "tax", "exit_terms", "ramp_out"]
"""What charged, as a **closed** set (FR-005).

Closed rather than a free-form string for :class:`~terezy.core.results.ramp.CostComponent`'s
reason: a free mapping would let a term invent a name, and then "a reader can see which part
dominates" would be satisfiable by a figure hiding under a key nobody reads. That every
member is actually reported is asserted in
``tests/contract/test_every_figure_states_its_scope.py``, because a closed set the builder
does not fill is a gap nothing else catches.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class PartContribution:
    """What one part of the round trip contributed, and which call produced it.

    **Never summed across parts.** They are in three different currencies in the general
    case -- the way in charges in the stream's, the instrument lives in its own, the way out
    delivers in the endpoint's -- and adding them would be the currency conflation Principle
    VI puts at top severity. They are reported side by side so a reader can see which term
    dominates, which is the sentence this feature exists to let the tool write about a
    *holding* rather than about a currency balance.
    """

    part: Part
    """Which part charged."""

    amount: Money
    """Signed as the ledger signs things: negative for money leaving, positive for money
    arriving. A **declared zero is a value** and appears as a recorded zero line (FR-009);
    only an absent declaration is a refusal."""

    source: str
    """Which call produced this figure, in words, so a reader can go and check it.

    Required, and it is the mechanical half of "the join invents nothing": a part with no
    named producer is a figure the join computed, and there is nowhere to write one.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Arrival:
    """One dated amount reaching a spendable endpoint, and the release that produced it."""

    released_on: date
    """When the instrument released the money -- the coupon, distribution or redemption date."""

    arrived_on: date
    """When it reached the endpoint: :attr:`released_on` plus the way out's declared latency.

    **Inside the span the rate is measured over** (FR-015, owner decision 2026-08-22): waiting
    is a cost, so it moves the date rather than sitting in a footnote beside the figure.
    """

    released: Money
    """What the instrument released on this date **net of the tax charged on it**, at the
    venue it released it at.

    Net rather than gross, and the field says so because two contract tests now assert
    ``released == lifecycle + tax`` against it. Read as gross it would look like the
    ``lifecycle`` part line, and the two differ by exactly the charge on every taxed holding.
    The gross figure is that part line; this is what actually travelled the way out, which is
    what the way out's fee was charged on.
    """

    amount: Money
    """What arrived, in the endpoint's currency, net of the way out's charge."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UndeployedCash:
    """Money that made the trip in and bought nothing, reported with its amount and location.

    FR-003. It is neither vanished nor swept into the rate as though it were invested: the
    minimum buyable increment left it over, it is sitting at the purchase venue, and both
    facts are on the record. Rounding it into the purchase would spend money the owner did not
    agree to spend; rounding it out of the report would make the money disappear.

    It is deliberately **not** part of :attr:`TupleOutcome.reaches`, and it is netted off the
    outlay the rate is measured against rather than left in the series. Bringing it home would
    mean deciding *when* the owner sweeps it -- an assumption nobody declared -- and pricing a
    second journey nobody asked for; leaving it in the outlay would price it as a **total
    loss**, which it is not. So the rate is measured on the money that was actually invested,
    and what was not invested is stated beside it.

    Both halves of that are on the outcome's face rather than only here: see the undeployed
    clause of :data:`EXCLUDES`, which says the recovery is not costed.
    """

    amount: Money
    """What was left over, in the instrument's currency."""

    venue_id: str
    """Where it is sitting: the venue the purchase was made at."""

    reason: str
    """Why it could not be deployed, naming the constraint -- the minimum buyable increment
    and the unit price -- in the output's own words."""


ACCOUNTS_FOR: Final[frozenset[str]] = frozenset(
    {
        "funding route costs (in), for this stream and this route",
        "the instrument's entry terms, including any declared markup",
        "tax on every taxable event over the holding's life",
        "the instrument's own exit terms, as explicit lines",
        "exit route costs (out), charged on each amount the instrument released",
        "ramp and settlement latency, inside the span the rate is measured over",
    }
)
"""What a tuple outcome *is* net of, in the output's own words (FR-014).

The sibling of :data:`EXCLUDES`, and it is the sentence feature 001's hurdle rate could not
say: 001's ``EXCLUDES`` names *funding route costs (in)* and *exit route costs (out)*, and
here both have moved to this set. A later feature moving a term the other way has to delete a
line here and add one there, in one change, where a reviewer sees both.
"""

EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "inflation (every figure here is nominal)",
        "the risk class, which is declared and carried but never scored",
        "the cost of recovering undeployed cash: the rate is measured on the money actually "
        "invested, and the remainder is reported at the venue it is sitting at, with no "
        "figure for what getting it back would cost",
        "public holidays (weekends are observed; no holiday calendar is modelled)",
        "when the tax is paid: the charge is netted on the date the income accrued, not on "
        "the declared deadline in a later year, so the money leaves sooner here than it does "
        "in life and the rate is understated rather than flattered",
    }
)
"""What a tuple outcome still does not account for, in the output's own words (FR-014).

Each is a whole later feature or a stated deferral. They are phrased for a reader rather than
as identifiers, because they are meant to be shown.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteStanding:
    """How usable the two declared routes are, on the outcome's own face.

    ``RampCost`` reports eight things about a way in and a tuple's outcome uses four of them:
    the key, the one-way cost, the latency and the ceiling. Two more are dropped with a reason
    -- the round-trip figure is about a different journey, and the inbound record's exit path
    is not this tuple's. **These two were dropped with no reason recorded anywhere**, which is
    how a `constrained` way in came to produce an outcome with nothing on its face saying so
    -- and ``RampCost.status``'s own docstring calls that "the field a reader scans to decide
    whether to trust the figure beside it".

    Both directions, because a status that described the way in only would put a half-truth on
    a record whose headline number is a round trip -- the gap ``RampCost.status`` records
    about itself, repeated one layer up rather than closed.
    """

    status: RouteStatus
    """The most constrained status either way declares. ``closed`` never appears: such a route
    is refused before anything is costed."""

    disruption_probability: float
    """The largest single leg's declared probability, never compounded across legs.

    **A lower bound, and it has to be read as one.** ``RampCost``'s own field says so in as
    many words -- the honest reading of 5% is *at least 5%* -- and this is the field a reader
    actually meets, on the outcome's face, so the reading belongs here rather than two records
    away. Multiplying independent-looking per-leg probabilities would invent a joint
    distribution nobody declared, and the largest is the weakest claim the declarations
    support.

    Across **both** ways where the holding released something, and the way in's alone where it
    released nothing: there is then no way-out cost to read a figure off. Such a tuple has no
    rate either, so no ranked figure rests on the narrower reading.
    """

    constrained: tuple[Literal["route_in", "route_out"], ...]
    """Which ways are constrained, in journey order, or empty.

    The remedies differ and the figure does not say which applies: a constrained way in is
    answered by funding the purchase differently, a constrained way out by declaring another
    exit. Naming the side is what turns a warning into an action.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class TupleOutcome:
    """One tuple's whole round trip: what reaches the endpoint, and what every term took."""

    key: Tuple
    """All five terms. An outcome cannot exist without one, which is how FR-010's
    "unrepresentable" is a property of the type rather than a rule to remember."""

    outlay: Money
    """What left the income stream, in the stream's currency, on :attr:`span`'s first day.

    The whole amount, including any part of it :attr:`undeployed` says bought nothing --
    :attr:`implied_rate` is the figure measured net of that, and reporting the netted number
    here as well would leave the money that made the trip unaccounted for anywhere.
    """

    parts: tuple[PartContribution, ...]
    """Each term's contribution, separately (FR-005). One entry per :data:`Part`, in journey
    order."""

    arrivals: tuple[Arrival, ...]
    """Every dated amount that reached a spendable endpoint, in date order.

    A series rather than one figure, and that is the model rather than an implementation
    detail: a coupon paid in 2027 is money at the endpoint in 2027, and holding it at the
    instrument until the redemption would be a decision nobody declared. Each release travels
    the declared way out on its own date and is charged what that chain charges -- which is
    why a fixed fee makes a small distribution expensive, honestly and visibly.
    """

    reaches: Money
    """The sum of :attr:`arrivals`, in the spendable endpoint's currency.

    What the owner can actually spend. Deliberately **not** annualised, discounted or netted
    against the outlay: it is an amount, and the rate beside it is the other question.
    """

    implied_rate: NominalRate | RateNotComparable
    """The money-weighted return over :attr:`span` (FR-015), or a typed statement of why none.

    The internal rate of return of the arrivals on their own dates against the money actually
    invested -- :attr:`outlay` less whatever :attr:`undeployed` says bought nothing -- measured
    with the instrument's declared day-count convention, the same convention that sized the
    instrument's flows. Computed by
    :func:`terezy.core.results.hurdle.internal_rate_of_return`, which is also what produces
    feature 001's benchmark, so hurdle-versus-tuple is one kind of number against the same
    kind.

    **A remainder therefore moves this figure by nothing at all**, which is the honest answer:
    the same holding was bought either way, and a whole outlay against a part-sized holding
    would price the stranded cash as a total loss.

    Ramp latency and settlement latency sit **inside** the span, because waiting is a cost
    (owner decision, 2026-08-22).

    **Present and typed either way, never absent and never a substitute figure.** A tuple
    funded in one currency and spent in another has an amount and no rate -- see
    :class:`RateNotComparable` -- and :attr:`reaches` is unaffected, because what arrives is a
    fact about money rather than a ratio between two currencies.
    """

    span: DateRange
    """First outlay to last arrival. The period :attr:`implied_rate` is a rate over."""

    horizon: DateRange
    """The comparison's **one** horizon, stated once and applied to every tuple in it (FR-025).

    Distinct from :attr:`span`, and the difference is the point: an instrument that terminates
    early has a span shorter than the horizon, and what it does in between is a declared
    continuation assumption rather than a silent extension of its return.
    """

    undeployed: UndeployedCash | None
    """Money that arrived and bought nothing, or ``None`` where the purchase deployed it all.

    ``None`` means there was no remainder, which is a different claim from a remainder of
    zero being unreported -- and it is exactly what a whole-unit purchase of an exact multiple
    produces.
    """

    routes: RouteStanding
    """How usable the declared ways in and out are. See :class:`RouteStanding`."""

    risk_class: str
    """The declared risk class of this option, carried from the access declaration.

    **Never scored** (research.md D9). It is here so the fifth term of Principle VI's tuple is
    visible in every output rather than silently dropped, and scoring it would need a model
    nobody has declared.
    """

    rests_on: tuple[str, ...]
    """The stated assumptions this outcome depends on, in words, sorted.

    The continuation assumption where the instrument terminates before the horizon, the
    liquidity mode and buyback availability where the instrument is a fund, and anything else
    the owner stated rather than declared. Figures resting on an assumption are marked
    assumption-driven, exactly as FR-025 requires.
    """

    accounts_for: frozenset[str]
    """See :data:`ACCOUNTS_FOR`. On the record's face, never in a footnote."""

    excludes: frozenset[str]
    """See :data:`EXCLUDES`."""

    provenance: Provenance
    """The union of every declared value behind every part: the route legs' fee schedules and
    premiums, the instrument's terms, the venue's quote, the tax entries that charged.

    A join step that dropped one of these would be a top-severity defect (FR-019), which is
    why the union is taken once, here, over the parts' own provenances rather than rebuilt.
    """

    staleness: StalenessVerdict
    """The merged verdict over every observation any part aged, at the run's as-of date."""


class ContinuationAssumption(Enum):
    """What proceeds arriving before the horizon do until it (FR-025).

    An enumeration with one member rather than a bare string, on
    :class:`~terezy.core.routes.path.ExitByIdentity`'s precedent: a closed set makes a typo a
    type error, and it makes the *second* member -- reinvestment, when something declares its
    terms -- an addition a reviewer sees rather than a new string appearing at a call site.
    """

    HOLD_AS_CASH = "hold_as_cash"


HOLD_AS_CASH: Final = ContinuationAssumption.HOLD_AS_CASH
"""The one declared continuation assumption: proceeds arriving before the horizon sit as cash.

FR-025 requires a comparison to *state* what an instrument maturing before the horizon does
with its proceeds -- reinvest on stated terms, or sit as cash -- and forbids defaulting it. It
is a required argument of :func:`terezy.core.decision.compare.compare` with no default
anywhere, so a caller has to say it.

**Reinvestment is deliberately not offered.** "Reinvest on stated terms" needs terms: a rate,
an instrument, an entry cost, a tax treatment. None of them is declared, and inventing any of
them is the number this feature is most likely to reach for (research.md D4). A second member
arrives with the declaration that gives it something to mean.

**It changes no figure, and that is worth stating rather than hiding.** The rate is an
internal rate of return over dated flows, and cash earns nothing, so holding proceeds from
termination to the horizon moves neither an arrival nor a date. The assumption is still
recorded on every outcome that rests on it, because *reinvest* would move both -- and a
reader comparing a two-year instrument against a twenty-year one over one horizon is entitled
to know which of the two answers he is being given.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RateNotComparable:
    """The rate slot, present and explicitly empty, naming what would be needed to fill it.

    Not an error and not a failure -- a valid, honest occupant of a slot whose value is
    genuinely unavailable, exactly as ``ExitCostUnknown`` occupies the round-trip slot and
    ``RealTermsUnavailable`` the real-terms one. The round trip happened, the amount that
    reached a spendable endpoint is real and is reported; what is missing is a *ratio*.

    **The case that is reachable today** is a tuple funded in one currency and spent in
    another: dollar contract income reaching a hryvnia fund produces a dollar outflow and
    hryvnia inflows, and an internal rate of return over the two is not a rate of anything.
    Valuing the outlay in hryvnia needs a rate that values one currency in another **for a
    return**, and nothing in this system declares one. Neither of the two rates that do exist
    is it. A channel rate is a transaction price, and using it to value an outlay against a
    return would put a price where a valuation belongs and quietly change every ranking it
    touched. The official rate feature 011 brought is a *legal* reference -- what the law says
    an income was worth on a date -- and reusing it to score a return is the role conflation
    Principle VI names, not a shortcut around it.

    A remainder the purchase could not deploy joins that first case when it is in a third
    currency, because it is netted off the outlay: three amounts, and a rate is a rate only
    over one currency. **That case turns on divisibility**, which is a fact about the data
    rather than an inconsistency: a hryvnia outlay buying a dollar instrument and coming home
    in hryvnia is one currency out and one back and has a perfectly good rate, and only a
    remainder the unit price left behind puts a third currency in the series. It is
    unreachable today for the reasons ``decision.tuple_outcome._rate`` records.

    The other case is a series with no rate to find: a round trip that returned nothing, or
    whose repatriation charges exceeded what was released. Reported rather than approximated,
    because a rate extrapolated past the bracket would be invented.

    A tuple holding one of these is **not comparison-ready** and is kept out of the ranking,
    reported separately -- 002's ``Ranking.not_comparable``, unchanged.
    """

    reason: str
    """Why there is no rate, in the output's own words."""

    missing: str
    """What would be needed to produce one, named so the remedy is a feature or a
    declaration rather than a search."""


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------
#
# Every one of them is a typed value naming what is missing and, where two things had to meet,
# **both sides**. None of them is an exception: a fact about the money is a result, and `raise`
# is for a caller that built something incoherent (Principle IV).


@dataclass(frozen=True, slots=True, kw_only=True)
class DeclarationMissing:
    """One of the tuple's parts has no declaration, and the join will not assume one.

    FR-006. Never an outcome computed with the missing part at zero, free or instantaneous:
    those are the three flattering defaults, and a comparison built on any of them recommends
    whatever nobody has costed.
    """

    part: Literal["instrument", "access", "route_in", "route_out", "tax_class"]
    """Which part the declaration belongs to."""

    what: str
    """The declaration that is missing, named so the remedy is a file rather than a search."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SeamDoesNotChain:
    """Two declarations that had to meet do not, and the refusal names both sides.

    FR-004, and the one place this feature is most likely to be silently wrong. Feature 004
    shipped an exit chain anchored at neither end: money moved between venues for free, and
    the record still read as a coherent three-hop journey -- an arriving amount in one currency
    beside a cost fraction computed in another. Two more places where two declarations have to
    meet at a *venue* are available here, so both are anchored and each is tested with a
    deliberate mismatch. The third seam is not a place at all and has its own record:
    :class:`FundedFromAnotherStream`.

    Bridging the gap is what must never happen: a conversion or a transfer nobody declared,
    inserted to make two declarations meet, is an invented leg at an invented rate.
    """

    seam: Literal["route_in_to_purchase", "proceeds_to_route_out"]
    """Which seam failed."""

    left: str
    """Where the money is, as ``venue/currency`` -- the end of the way in, or where the
    instrument releases its proceeds."""

    right: str
    """Where it would have to be, as ``venue/currency`` -- where the purchase happens, or
    where the way out departs from."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FundedFromAnotherStream:
    """The tuple names one funding stream and its way in is costed from another (FR-010).

    The third seam, and the only one with no venue in it. A
    :class:`~terezy.core.routes.path.Candidate` carries its own ``stream_id`` and the way in
    is costed from *that* one -- the same acquisition is free from the hryvnia salary and
    crosses a P2P spread from the dollar contract income -- while :attr:`Tuple.stream_id` is
    what resolves the stream, keys the way out, and appears in every report. Two fields, one
    fact, and until this refusal existed nothing compared them: a tuple claiming to be funded
    from ``contract_usd`` over the free domestic hryvnia route produced complete, plausible
    figures for a journey nobody could make.

    Refused rather than resolved in either direction. Preferring the tuple's would re-cost a
    way in the caller did not name; preferring the candidate's would silently rewrite the key
    the whole comparison is built on, which is the term SC-004 exists to protect.
    """

    tuple_stream_id: str
    """The stream the tuple says funds the purchase."""

    route_stream_id: str
    """The stream the way in is costed from."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInUnusable:
    """The way in will not carry this amount on this date. 002's feasibility, unchanged.

    FR-016. The refusal 002 produced is carried whole rather than re-worded, so the binding
    constraint, the binding segment and the shortfall say exactly what they say in a ramp
    comparison -- one vocabulary for one fact.
    """

    refused: RouteUnusable
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInCapExceeded:
    """The way in declares a monthly ceiling below the amount, and the excess has nowhere to go.

    **Distinct from :class:`RouteInUnusable` because the two bind for different reasons and
    the reader has to know which.** A per-transaction ``leg.maximum`` says *this route cannot
    carry this movement at all*, and 002 refuses it inside ``cost_one``. A ``leg.monthly_cap``
    says *this rail carries this much a month*, which 002 deliberately does **not** treat as a
    refusal: ``routes.capacity`` reports the ceiling and decides what fits, because refusing
    would deploy nothing where the honest answer is to deploy the cap and report the rest.

    Deploying the cap is what this feature cannot honestly do. FR-018 defers partial
    deployment (owner decision, 2026-08-22), and the machinery that would report the excess
    needs two things a tuple does not carry: a declared fallback policy with its
    ``redirect_to``, and the month's consumed capacity. Choosing one -- holding the excess as
    cash, say -- is the substituted default ``routes.capacity`` refuses by name.

    So the tuple refuses, naming the ceiling and the excess. It is the one answer that invents
    nothing, and it is temporary by construction: when a planning feature brings staggered
    entry this becomes a split rather than something to unwind.

    Without it a monthly cap below the outlay is read nowhere at all, and the join returns a
    complete outcome buying more units than the rail will carry -- the silent execution of an
    infeasible plan that Principle VI puts at the highest severity.
    """

    path: Candidate
    """Which way in declares the ceiling, and from which stream (FR-008)."""

    ceiling: Money
    """The tightest monthly cap any leg of the way in declares, in the sending currency."""

    requested: Money
    """What the caller asked to send. ``ceiling``/``requested``/``excess`` rather than
    ``cap``/``amount``/``over``: it is the vocabulary ``capacity.Deployment`` and
    ``BelowMinimumTicket`` already use for the same shape of statement."""

    excess: Money
    """``requested - ceiling``: what the rail will not carry this month."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WayOutCapExceeded:
    """A monthly ceiling on the way out, below what the instrument released on one date.

    :class:`RouteInCapExceeded`'s twin, and a separate record for the reason
    :class:`WayOutUnusable` is one: the remedies differ, and a cap that carries every coupon
    while refusing the redemption is a real and non-obvious finding rather than a variant of
    the inbound case. Only this record can say **which release** could not go home, which is
    the first thing a reader needs and the thing the inbound record has no field for.

    **It checks one movement against the ceiling, not a month's worth against it.** Several
    releases can fall in one month and share one rail's allowance; adding them up is the
    capacity accumulator's job (FR-012, FR-015), and a tuple carries no accumulator. So this
    is the *loosest* honest check -- it fires only where a single release alone exceeds the
    cap -- and the gap is stated rather than left to be discovered: two coupons of 700.00 in
    one month against a 1 000.00 cap still pass here. Narrowing it needs the accumulator, and
    inventing a month's consumption would be worse than reporting less than everything.
    """

    path: Candidate
    """Which way out declares the ceiling, and from which stream (FR-008)."""

    released_on: date
    """The date of the release that could not be carried. :class:`WayOutUnusable` carries the
    same field for the same reason: "the way out will not carry it" is unactionable until a
    reader knows *which* movement, and the answer decides whether the remedy is a different
    exit or a different exit date."""

    ceiling: Money
    """The tightest monthly cap any leg of the way out declares, in the released currency."""

    requested: Money
    """What the instrument released on that date, net per date."""

    excess: Money
    """``requested - ceiling``: what the rail will not carry that month."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WayOutUnusable:
    """The way out will not carry what the instrument released, on the date it released it.

    FR-016 on the way back. Distinct from :class:`RouteInUnusable` because the remedies
    differ, and because a way out that cannot carry a *coupon* while carrying the redemption
    perfectly well is a real and non-obvious finding: a fixed minimum on an exit leg makes
    small, frequent distributions unrepatriable.
    """

    refused: RouteUnusable
    released_on: date
    """The date the amount that could not be carried was released."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NoExitRouteDeclared:
    """Nobody has costed the way out of the venue. 002's FR-030, inherited whole (FR-007).

    Not comparison-ready, and the one-way figure is **not** promoted into the gap: "most of
    the cost" is not the cost, and an asset that cannot be liquidated into spendable base
    currency at a reasonable cost is not worth its stated value (Principle VI).
    """

    unknown: ExitCostUnknown
    """002's own statement of what is missing, carried rather than re-worded."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class NoExitTermsDeclared:
    """The *instrument* has no way out available, which is the other exit-unknown (FR-008).

    Distinct from :class:`NoExitRouteDeclared` by type, because the two call for different
    actions: this one is answered by waiting for the instrument's own termination, by
    accepting a discretionary discount, or by declaring an exit the terms do not currently
    owe -- and never by declaring a route.

    The instrument's own refusal is carried in :attr:`reason` verbatim, because the call that
    owns the terms is the one entitled to say why they do not produce an exit.
    """

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BelowMinimumTicket:
    """What arrived is less than the instrument's declared minimum purchase (FR-017).

    The tuple is infeasible for this amount, and the refusal names the minimum, what arrived
    and the shortfall. Nothing is rounded: rounding up would spend money the owner did not
    agree to spend, and rounding down would report a return on a holding never bought.

    ``arrived`` may be zero or negative where the way in's fees exceeded the amount, and it is
    reported as it stands -- feature 002's B13 regression, extended through the join.
    """

    instrument_id: str
    path: Candidate
    """Which way in delivered :attr:`actual`, and from which stream (FR-008).

    Carried because the figure it refuses is a *post-ramp* amount: "1 000 short of the minimum"
    says nothing until a reader knows which stream and which route delivered what arrived, and
    the same purchase is feasible from one and infeasible from the other. That difference is
    the finding this project exists to surface.
    """

    required: Money
    actual: Money
    shortfall: Money
    reason: str

    # ``required``/``actual``/``shortfall`` rather than ``minimum``/``arrived``: it is the
    # vocabulary ``errors.InfeasiblePurchase`` and ``ramp.RouteUnusable`` already use for the
    # same shape of statement, and one word per concept across three records is worth more than
    # a locally prettier name.


@dataclass(frozen=True, slots=True, kw_only=True)
class BuysNoWholeUnit:
    """What arrived clears the minimum ticket but will not buy one buyable increment.

    A separate refusal from :class:`BelowMinimumTicket` because it names a different figure --
    the unit price and the minimum increment rather than the ticket -- and because the two can
    disagree: an instrument may declare a ticket smaller than one unit costs, in which case
    this is the binding constraint and saying "below the minimum ticket" would be false.
    """

    instrument_id: str
    path: Candidate
    """Which way in delivered :attr:`actual`, and from which stream. See
    :attr:`BelowMinimumTicket.path`."""

    price_per_unit: Money
    min_unit: float
    actual: Money
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentRefused:
    """The instrument's own projection refused, and its reason is carried verbatim.

    The call that owns the terms is the one entitled to say why it produced no figure -- a
    purchase after a subscription cutoff, a redemption the terms do not owe, a value the
    primary documents never gave. Re-wording any of them here would put the join's
    interpretation between the owner and the declaration.
    """

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CannotSpanHorizon:
    """The instrument cannot be held to the comparison's horizon, with the binding term named.

    FR-025's second consequence. Reported as infeasible **for this comparison** rather than
    silently truncated to whatever span the instrument can manage: a twenty-year lock-up
    evaluated over two years and reported as a two-year return is a rate measured over a
    period the money could not have been withdrawn in.
    """

    instrument_id: str
    binding_term: str
    """The declared term that binds -- ``instrument.maturity_date``,
    ``instrument.terminates_on``."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TwoFiguresNotOne:
    """The instrument states a range and the owner chose no point inside it.

    A range is the honest answer and a tuple has one outcome, so the two cannot be
    reconciled here: taking the midpoint, the low end or the high end would be the false
    point 006's FR-023 refuses by name. The remedy is a stated choice, which is an input the
    owner supplies rather than a figure this feature can derive.
    """

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanDoesNotFitInstrument:
    """The run settings are for a different kind of declaration than the instrument is.

    A bond has no liquidity mode and a fund has no coupon policy. Reported rather than
    coerced: silently ignoring the fields that do not apply would run the holding under
    settings the caller believes are in force.
    """

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaxCurrencyConversionUnavailable:
    """A taxable instrument in a currency the projection cannot hold its tax in.

    Principle VI's tax role -- base currency at the official rate on the transaction date --
    exists as of feature 011, and ``core.tax.year`` strikes a base with it at assessment. This
    refusal is upstream of that and is about a different gap: ``core.results.project`` folds a
    holding under **one** currency and sums every charge in it, so a hryvnia charge inside a
    dollar projection is a currency mismatch rather than a figure. A disposal adds a second
    gap, because a realised gain needs a per-lot basis carried in both currencies with each
    leg struck at its own date's rate.

    Both are ``fx-tax-asymmetry-f1`` in ``specs/features.toml``, whose remaining blocker this
    refusal names. 011 supplied the dated rates it needs and deliberately did not build it.

    **It must not be satisfied with a channel rate**, and neither must the base itself. A
    channel is a market you transact in; the official rate is a legal reference you never
    transact at, and substituting one for the other would strike a tax base at a price nobody
    was charged.

    Unreachable in the shipped registry, where every declared instrument is in hryvnia, and it
    exists because unreachable-today is not the same as never.
    """

    instrument_id: str
    instrument_currency: str
    tax_currency: str
    missing: str
    """The machinery that would be needed, named so the remedy is a feature rather than a
    workaround."""

    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentDemandsCash:
    """On some date the holding takes more out than it puts in, and nothing routes money back.

    A tax charge landing on a date with too little income to pay it from is the shape of this:
    the money would have to travel *in* along a route nobody costed for it, on a date nobody
    planned. It is refused rather than netted against a later receipt, because netting would
    move a real outflow to a date it did not happen on and quietly improve the rate.

    Unreachable while every declared class charges a **fraction** of the income it taxes: the
    charge is netted on that income's own date, so the date nets to zero at worst.

    **Strictly above 100%, and not at it.** At exactly 100% the date nets to zero,
    ``_released_by_date`` drops it, and the holding simply sends nothing home on it -- which
    ``tests/unit/test_rate_and_horizon_boundaries.py`` pins from both sides, at 50+50 for the
    dropped date and at 90+90 for this refusal. Which side of the boundary the declared rates
    fall on is a property of the rates rather than of the arithmetic, and is why this is a
    guard rather than an assertion that it cannot happen.
    """

    instrument_id: str
    on: date
    shortfall: Money
    reason: str


TupleRefused = (
    DeclarationMissing
    | SeamDoesNotChain
    | FundedFromAnotherStream
    | RouteInUnusable
    | RouteInCapExceeded
    | WayOutCapExceeded
    | WayOutUnusable
    | NoExitRouteDeclared
    | NoExitTermsDeclared
    | BelowMinimumTicket
    | BuysNoWholeUnit
    | InstrumentRefused
    | CannotSpanHorizon
    | TwoFiguresNotOne
    | PlanDoesNotFitInstrument
    | TaxCurrencyConversionUnavailable
    | InstrumentDemandsCash
)
"""The seventeen ways a tuple honestly produces no outcome. Match exhaustively.

Never a partial outcome and never an empty one. A ``case _:`` arm the type checker proves
unreachable means a new member becomes an error at every site that must handle it.

The count is asserted rather than left to rot: ``tests/unit/test_tuple_refusals.py`` compares
it against ``get_args``, so an eighteenth member fails a test instead of quietly making
this sentence false.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RefusedTuple:
    """One tuple that produced no outcome, kept in the comparison with its reason.

    Present rather than dropped. A silent exclusion is how a comparison comes to recommend the
    only option left standing, with nothing in the output to say why the others are missing --
    and here the missing ones are precisely the options nobody has finished declaring, which
    is the most decision-relevant thing the report could say.
    """

    key: Tuple
    refusal: TupleRefused


@dataclass(frozen=True, slots=True, kw_only=True)
class Comparison:
    """Every tuple, scored over one horizon, with the hurdle among them as the benchmark."""

    horizon: DateRange
    """Stated once and applied to every tuple (FR-025). Evaluating a two-year instrument over
    two years and a twenty-year one over twenty compares two different questions."""

    continuation: ContinuationAssumption
    """The declared continuation assumption for this comparison. See :data:`HOLD_AS_CASH`."""

    ranked: tuple[TupleOutcome, ...]
    """Every comparison-ready tuple, ordered by :attr:`TupleOutcome.implied_rate`, best first.

    Ordered on the rate alone, and the ordering is a **sequence** rather than a verdict: where
    two outcomes are within the project tolerance :attr:`ties` says so, and the sequence order
    between them is arbitrary and must not be read as a preference.
    """

    benchmark: int
    """An **index** into :attr:`ranked`, never a copy of one of its entries.

    This is the whole of FR-012 and of research.md D3. Holding an index rather than a record
    means there is nowhere here for a separately computed benchmark to sit: whatever this
    points at came out of the same call, in the same loop, as everything it is ranked against.
    A separately computed benchmark drifts from what it benchmarks, and the drift is invisible
    because both numbers look reasonable.

    002's ``Ranking.recommended`` sets the precedent, and its argument applies unchanged.
    """

    ties: tuple[tuple[int, ...], ...]
    """Groups of indices into :attr:`ranked` whose rates agree within the project tolerance.

    FR-013, and 002's FR-018 rule unchanged, **including a tie between a tuple and the
    hurdle**: "nothing beats the hurdle" must be sayable when it is true by a whisker. Only
    groups of two or more appear; a tuple tied with nothing is not a tie.
    """

    refused: tuple[RefusedTuple, ...]
    """Every tuple that produced no outcome, with its typed reason. Visible, never absent."""

    not_comparable: tuple[TupleOutcome, ...]
    """Outcomes that were computed in full but hold no rate, kept out of :attr:`ranked`.

    002's ``Ranking.not_comparable``, unchanged in shape and in reasoning: the figures are
    real and are reported, and what is missing is the one thing a ranking orders by. Ranking
    them on the amount instead would compare a hryvnia total against a hryvnia total over two
    different spans, which is a comparison of two different questions.
    """

    beats_benchmark: tuple[int, ...]
    """Indices of the tuples that beat the benchmark by more than the project tolerance.

    Empty is the answer the product exists to be able to give plainly: **nothing beats the
    hurdle** (FR-011). It is a separate field rather than something a reader derives from the
    ordering, because deriving it means re-implementing the tie rule at every call site and
    the first implementation to get it wrong will report a winner by a hair.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkUnavailable:
    """The benchmark tuple itself refused, so there is no comparison -- only its parts.

    Returned *instead of* a :class:`Comparison`, on the precedent of
    ``Ranking | NothingComparable`` one layer down. FR-011 says the hurdle must **always** be
    scored and always shown, so a comparison without it is not a weaker comparison: it is a
    different thing, and ranking the rest against nothing would invite the head of the list to
    be read as a winner.

    Unrelated to :class:`Comparison`, so a caller that forgot this case is a mypy error rather
    than an ``IndexError`` in front of the owner.
    """

    refusal: TupleRefused | RateNotComparable
    """Why there is no benchmark figure.

    Two different facts share this slot on purpose, and the reason field says which: the
    benchmark tuple **refused** outright, or it produced a complete outcome carrying no rate.
    They are both "there is nothing to rank against", and separating them into two records
    would make every caller handle a distinction it does not act on.
    """

    scored: tuple[TupleOutcome, ...]
    """The other tuples' outcomes, unranked and carried rather than discarded: they were
    computed, they are real, and throwing them away would hide work the owner paid for."""

    refused: tuple[RefusedTuple, ...]
    """The other tuples that refused, in the shape a :class:`Comparison` would have carried."""

    not_comparable: tuple[TupleOutcome, ...]
    """The other outcomes that hold no rate, likewise."""

    reason: str
