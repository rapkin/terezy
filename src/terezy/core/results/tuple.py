"""The tuple and its outcome: what reaches a spendable endpoint, and what it cost to get there.

These records are the join over Principle VI's unit of analysis, and `SIMULATOR_SPEC.md` §8
question 1 -- *does anything beat 15.5% tax-free OVDP after every other option's fees, taxes
and access costs?* -- is the question they exist to make computable.

**Nothing here holds a figure the join computed itself.** Every amount below came from the
call that owns it -- 002's costing, 001's or 006's projection, the declared tax rules -- and
the join's own content is the chaining and the refusals (research.md D1). A figure the join
invented would have no owner and no test would know where to check it.

**Both figures, always** (research.md D8). :attr:`TupleOutcome.reaches` is what can be spent;
:attr:`TupleOutcome.implied_rate` is what compares across horizons. Reporting one invites a
reader to derive the other under an assumption the tool never made.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final, Literal

from terezy.core.instruments.cash import CashAssumptions
from terezy.core.instruments.interface import Assumptions, DateRange
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import NominalRate
from terezy.core.primitives.staleness import StalenessVerdict
from terezy.core.results.fund import FundAssumptions
from terezy.core.results.hurdle import RealTerms
from terezy.core.results.ramp import ExitCostUnknown, RouteUnusable
from terezy.core.routes.legs import RouteStatus
from terezy.core.routes.path import Candidate, EntryPath, ExitChoice
from terezy.core.scenarios.early_exit import SoldEarly
from terezy.core.scenarios.quotation import QuotationHolds

InstrumentPlan = Assumptions | FundAssumptions | CashAssumptions
"""How the holding is run, and therefore **which declared way out this tuple takes**.

Matched with ``match``, never distinguished by a flag, and deliberately not a new record
wrapping them: they are already the per-kind assumption records, each required in full with no
default anywhere in the stack, and a wrapper would be a further place for a run's choices to
live.

``FundAssumptions.exit_on`` and ``liquidity_mode`` choose between a fund's declared ways out
-- a requested buyback at a discount, or the termination payout. A bond has one way out,
redemption at maturity, so ``Assumptions`` names none; a balance has one with nothing to
choose about it, so ``CashAssumptions`` carries no field at all.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Tuple:
    """The unit of analysis: an instrument, funded from a stream, reached and left by routes.

    **Identity is all five terms** (FR-010, research.md D5). The same instrument funded from
    the hryvnia salary and from the dollar contract income is two tuples with two outcomes, so
    a cost or an outcome attributed to an instrument alone stays unrepresentable.

    Keyword-only: ``instrument_id`` and ``stream_id`` are adjacent strings, and a positional
    constructor would let them be transposed with no type error anywhere.
    """

    instrument_id: str
    """The declared instrument bought -- of either declaration kind."""

    stream_id: str
    """Which declared income stream funds it. The term that carries §4.3.1's finding."""

    route_in: EntryPath
    """The way in: one declared route, a chain of them composed at query time, or
    :data:`~terezy.core.routes.path.ENTRY_BY_IDENTITY` where there is nothing to do."""

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
dominates" would be satisfiable by a figure hiding under a key nobody reads. That every member
is actually reported is asserted in ``tests/contract/test_every_figure_states_its_scope.py``.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class PartContribution:
    """What one part of the round trip contributed, and which call produced it.

    **Never summed across parts.** They are in three different currencies in the general case
    -- the way in charges in the stream's, the instrument lives in its own, the way out
    delivers in the endpoint's -- and adding them would be the currency conflation Principle VI
    puts at top severity. They are reported side by side so a reader can see which term
    dominates.
    """

    part: Part
    """Which part charged."""

    amount: Money
    """Signed as the ledger signs things: negative for money leaving, positive for money
    arriving. A **declared zero is a value** and appears as a recorded zero line (FR-009);
    only an absent declaration is a refusal."""

    source: str
    """Which call produced this figure, in words, so a reader can go and check it.

    Required, and it is the mechanical half of "the join invents nothing": a part with no named
    producer is a figure the join computed, and there is nowhere to write one.
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
    """What the instrument released on this date **net of the tax charged on it**, at the venue
    it released it at.

    Net rather than gross: read as gross it would look like the ``lifecycle`` part line, and
    the two differ by exactly the charge on every taxed holding. The gross figure is that part
    line; this is what actually travelled the way out, and what the way out's fee was charged
    on.
    """

    amount: Money
    """What arrived, in the endpoint's currency, net of the way out's charge."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RemainderCameHome:
    """The remainder's own journey out along the tuple's declared way out."""

    left_on: date
    """The purchase date: it became no position, so it waits for nothing before leaving."""

    arrived_on: date
    """:attr:`left_on` plus the way out's declared latency."""

    reached: Money
    """What reached the spendable endpoint, in the endpoint's currency, net of the way out's
    charge and of no tax."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RemainderStayed:
    """The tuple's declared way out will not carry the remainder, so it is where it was left.

    Reported rather than refusing the tuple: the position itself came home perfectly well, and
    what is stranded is the change from the purchase. It is out of
    :attr:`TupleOutcome.reaches`, and :attr:`TupleOutcome.implied_rate` is a typed refusal --
    part of the outlay never came home, and nothing declares whether stranded cash is worth
    par or nothing.
    """

    reason: str
    """Why the declared way out will not carry it, in the output's own words."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UndeployedCash:
    """Money that made the trip in, bought nothing, and came home along the declared way out.

    FR-003 under the owner's decision of 2026-09-06
    (``specs/decisions/2026-09-06-undeployed-remainder-returns.toml``): the remainder is
    withdrawable from the purchase venue, so it rides the tuple's own declared way out rather
    than sitting there. It **never became a position**, which fixes every term of that journey:
    it leaves on the purchase date, it is charged whatever the way out charges, and it bears
    **no tax** -- nothing was disposed of and there is no gain.

    Reported as its own record either way: money the purchase could not deploy and money a
    holding paid out are different facts, and rounding the remainder into the purchase would
    spend money the owner did not agree to spend.
    """

    amount: Money
    """What was left over, in the instrument's currency, at :attr:`venue_id`."""

    venue_id: str
    """Where the purchase was made, and where this money left from."""

    journey: RemainderCameHome | RemainderStayed
    """Whether it got home, and on what terms."""

    reason: str
    """Why it could not be deployed, naming the constraint -- the minimum buyable increment
    and the unit price -- in the output's own words."""


def money_home(
    arrivals: tuple[Arrival, ...], undeployed: UndeployedCash | None
) -> tuple[tuple[date, Money, Arrival | RemainderCameHome], ...]:
    """Every dated amount that reached a spendable endpoint, in date order, with its record.

    The releases and the remainder that came home, in **one** series, because
    :attr:`TupleOutcome.reaches`, the span's end, :attr:`TupleOutcome.implied_rate` and 019's
    reserve verdicts are four readings of one fact -- and building each from its own addition
    is how two of them came to leave the remainder out.
    """
    coming: list[tuple[date, Money, Arrival | RemainderCameHome]] = [
        (arrival.arrived_on, arrival.amount, arrival) for arrival in arrivals
    ]
    match undeployed:
        case UndeployedCash(journey=RemainderCameHome() as came):
            coming.append((came.arrived_on, came.reached, came))
    return tuple(sorted(coming, key=lambda item: item[0]))


ACCOUNTS_FOR: Final[frozenset[str]] = frozenset(
    {
        "funding route costs (in), for this stream and this route",
        "the instrument's entry terms, including any declared markup",
        "tax on every taxable event over the holding's life",
        "the instrument's own exit terms, as explicit lines",
        "exit route costs (out), charged on each amount that travelled it",
        "ramp and settlement latency, inside the span the rate is measured over",
    }
)
"""What a tuple outcome *is* net of, in the output's own words (FR-014).

The sibling of :data:`EXCLUDES`: a later feature moving a term the other way has to delete a
line here and add one there, in one change, where a reviewer sees both.
"""

EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "inflation on the amounts: the outlay and what reaches a spendable endpoint are "
        "nominal, and only the rate has a real counterpart beside it",
        "the risk class, which is declared and carried but never scored",
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

    Both directions, because a status describing the way in only would put a half-truth on a
    record whose headline number is a round trip.
    """

    status: RouteStatus
    """The most constrained status either way declares. ``closed`` never appears: such a route
    is refused before anything is costed."""

    disruption_probability: float
    """The largest single leg's declared probability, never compounded across legs.

    **A lower bound, and it has to be read as one**: the honest reading of 5% is *at least 5%*.
    Multiplying independent-looking per-leg probabilities would invent a joint distribution
    nobody declared, and the largest is the weakest claim the declarations support.

    Across **both** ways where the holding released something, and the way in's alone where it
    released nothing: there is then no way-out cost to read a figure off, and such a tuple has
    no rate either, so no ranked figure rests on the narrower reading.
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

    projection_key: str
    """Where this candidate's projection is served from (027 FR-006).

    The horizon and the five terms, rendered by
    :func:`terezy.core.results.canonical.candidate_key`. A **string** rather than the pair,
    because it is an address a client echoes back and never composes -- the five terms alone
    name the same candidate in all three sections, whose projections differ.

    The projection itself is not here: a field on this record is on the wire in every response
    that carries one, and a reader who opens one card should pay for one.
    """

    outlay: Money
    """What left the income stream, in the stream's currency, on :attr:`span`'s first day.

    The whole amount, and the whole amount is what :attr:`implied_rate` is measured against:
    the part of it :attr:`undeployed` says bought nothing comes home along the declared way
    out, so it is a receipt in the series rather than a deduction from the denominator.
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
    """The sum of :attr:`arrivals` and of the remainder's own arrival where it had one, in the
    spendable endpoint's currency.

    What the owner can actually spend. Deliberately **not** annualised, discounted or netted
    against the outlay: it is an amount, and the rate beside it is the other question.
    """

    implied_rate: NominalRate | RateNotComparable
    """The money-weighted return over :attr:`span` (FR-015), or a typed statement of why none.

    The internal rate of return, on their own dates, of the arrivals and of the remainder's own
    arrival against the whole :attr:`outlay`, measured with the instrument's declared day-count
    convention. Computed by
    :func:`terezy.core.results.hurdle.internal_rate_of_return`, which is also what produces
    feature 001's benchmark, so hurdle-versus-tuple is one kind of number against the same kind.

    Ramp latency and settlement latency sit **inside** the span, because waiting is a cost
    (owner decision, 2026-08-22).

    **Present and typed either way, never absent and never a substitute figure.** A tuple
    funded in one currency and spent in another has an amount and no rate -- see
    :class:`RateNotComparable` -- and :attr:`reaches` is unaffected, because what arrives is a
    fact about money rather than a ratio between two currencies.
    """

    real: RealTerms
    """What :attr:`implied_rate` returns in purchasing power: two figures, or two reasons.

    The same record the hurdle carries and filled by the same function, so a candidate's real
    figure is comparable with the benchmark's field for field. One half deflated by declared
    CPI observations covering the whole window, the other by the declared future-inflation
    belief, and where either input is missing that half alone is typed-unavailable naming what
    is missing (024 FR-001, FR-003).

    **Never ranked on, compared on, or used to choose a benchmark** (024 FR-017): a figure
    added for the reader must not reorder the answer.
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
    """Money that arrived and bought nothing, with what became of it, or ``None`` where the
    purchase deployed it all.

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

    sold_early: SoldEarly | None
    """The sale that closed the position at the horizon's end, or ``None`` where its own terms
    did (015 FR-029).

    Typed rather than left to be read out of :attr:`rests_on`: an early-exit figure carries
    stated exclusions of its own (FR-033), and deciding whether to attach them by searching a
    sentence is the string-matching 014 FR-014a already refuses for a refusal's case.
    """

    carried_quotation: QuotationHolds | None
    """The belief a price this outcome rests on leaned on, or ``None`` where none did.

    A quotation is a dated observation, so a price struck on any other day rests on it holding
    (022 FR-018) -- **either leg**, which is why this is not a field of :attr:`sold_early`: a
    holding bought from a quotation and held to its own maturity leans on the belief with no
    early exit anywhere in it. Typed rather than read out of :attr:`rests_on` for the reason
    that field gives: deciding whether to attach a stated exclusion by searching a sentence is
    the string matching 014 FR-014a refuses.
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

    An enumeration with one member rather than a bare string: a closed set makes a typo a type
    error, and it makes the *second* member -- reinvestment, when something declares its terms
    -- an addition a reviewer sees rather than a new string appearing at a call site.
    """

    HOLD_AS_CASH = "hold_as_cash"


HOLD_AS_CASH: Final = ContinuationAssumption.HOLD_AS_CASH
"""The one declared continuation assumption: proceeds arriving before the horizon sit as cash.

FR-025 requires a comparison to *state* what an instrument maturing before the horizon does
with its proceeds and forbids defaulting it, so it is a required argument of
:func:`terezy.core.decision.compare.compare` with no default anywhere.

**Reinvestment is deliberately not offered.** "Reinvest on stated terms" needs terms: a rate,
an instrument, an entry cost, a tax treatment. None of them is declared, and inventing any of
them is the number this feature is most likely to reach for (research.md D4).

**It changes no figure.** The rate is an internal rate of return over dated flows and cash
earns nothing, so holding proceeds from termination to the horizon moves neither an arrival
nor a date. It is still recorded on every outcome that rests on it, because *reinvest* would
move both.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RateNotComparable:
    """The rate slot, present and explicitly empty, naming what would be needed to fill it.

    Not an error -- a valid occupant of a slot whose value is genuinely unavailable, exactly
    as ``ExitCostUnknown`` occupies the round-trip slot. What is missing is a *ratio*.

    **The case that is reachable today** is a tuple funded in one currency and spent in
    another: a dollar outflow against hryvnia inflows, and an internal rate of return over the
    two is not a rate of anything. Valuing the outlay in hryvnia needs a rate that values one
    currency in another *for a return*, and neither rate this system declares is it -- a
    channel rate is a transaction price, and the official rate is a legal reference, so using
    either would be the role conflation Principle VI names.

    A remainder the purchase could not deploy joins that case when it is in a third currency,
    because it is netted off the outlay. That turns on divisibility and is unreachable today
    for the reasons ``decision.tuple_outcome._rate`` records.

    The other case is a series with no rate to find: a round trip that returned nothing, or
    whose repatriation charges exceeded what was released. Reported rather than approximated,
    because a rate extrapolated past the bracket would be invented.
    """

    reason: str
    """Why there is no rate, in the output's own words."""

    missing: str
    """What would be needed to produce one, named so the remedy is a feature or a
    declaration rather than a search."""


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


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

    FR-004, and the one place this feature is most likely to be silently wrong: feature 004
    shipped an exit chain anchored at neither end, so money moved between venues for free and
    the record still read as a coherent three-hop journey. The third seam is not a place at
    all and has its own record: :class:`FundedFromAnotherStream`.

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
    :class:`~terezy.core.routes.path.Candidate` carries its own ``stream_id`` and the way in is
    costed from *that* one, while :attr:`Tuple.stream_id` is what resolves the stream, keys the
    way out, and appears in every report. Until this refusal existed nothing compared them: a
    tuple claiming to be funded from ``contract_usd`` over the free domestic hryvnia route
    produced complete, plausible figures for a journey nobody could make.

    Refused rather than resolved in either direction. Preferring the tuple's would re-cost a
    way in the caller did not name; preferring the candidate's would silently rewrite the key
    the whole comparison is built on.
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

    **Distinct from :class:`RouteInUnusable` because the two bind for different reasons.** A
    per-transaction ``leg.maximum`` says *this route cannot carry this movement at all*; a
    ``leg.monthly_cap`` says *this rail carries this much a month*, which ``routes.capacity``
    deliberately treats as a ceiling to report rather than a refusal.

    Deploying the cap is what this feature cannot honestly do: FR-018 defers partial deployment
    (owner decision, 2026-08-22), and reporting the excess needs a declared fallback policy
    with its ``redirect_to`` and the month's consumed capacity, neither of which a tuple
    carries. So the tuple refuses, naming the ceiling and the excess.

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
    """A monthly ceiling on the way out, below an amount that was to travel it on one date.

    :class:`RouteInCapExceeded`'s twin, and a separate record because the remedies differ and
    only this one can say **which release** could not go home.

    **It checks one movement against the ceiling, not a month's worth against it.** Several
    movements can fall in one month and share one rail's allowance; adding them up is the
    capacity accumulator's job (FR-012, FR-015), and a tuple carries no accumulator. So this is
    the *loosest* honest check -- two coupons of 700.00 in one month against a 1 000.00 cap
    still pass here -- and inventing a month's consumption would be worse than reporting less
    than everything.
    """

    path: Candidate
    """Which way out declares the ceiling, and from which stream (FR-008)."""

    released_on: date
    """The date the amount that could not be carried was to set out -- a release date, or the
    purchase date for the remainder the purchase could not deploy. "The way out will not carry
    it" is unactionable until a reader knows *which* movement, and the answer decides whether
    the remedy is a different exit or a different exit date."""

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

    FR-016 on the way back. Separate from :class:`RouteInUnusable` because a way out that
    cannot carry a *coupon* while carrying the redemption perfectly well is a real and
    non-obvious finding: a fixed minimum on an exit leg makes small, frequent distributions
    unrepatriable.
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

    Nothing is rounded: rounding up would spend money the owner did not agree to spend, and
    rounding down would report a return on a holding never bought.

    ``arrived`` may be zero or negative where the way in's fees exceeded the amount, and it is
    reported as it stands -- feature 002's B13 regression, extended through the join.
    """

    instrument_id: str
    path: EntryPath
    """Which way in delivered :attr:`actual`, and from which stream (FR-008).

    Carried because the figure it refuses is a *post-ramp* amount: "1 000 short of the minimum"
    says nothing until a reader knows which stream and which route delivered what arrived, and
    the same purchase is feasible from one and infeasible from the other.
    """

    required: Money
    actual: Money
    shortfall: Money
    reason: str

    # ``required``/``actual``/``shortfall`` rather than ``minimum``/``arrived``: it is the
    # vocabulary ``errors.InfeasiblePurchase`` and ``ramp.RouteUnusable`` already use for the
    # same shape of statement.


@dataclass(frozen=True, slots=True, kw_only=True)
class BuysNoWholeUnit:
    """What arrived clears the minimum ticket but will not buy one buyable increment.

    A separate refusal from :class:`BelowMinimumTicket` because it names a different figure --
    the unit price and the minimum increment rather than the ticket -- and because the two can
    disagree: an instrument may declare a ticket smaller than one unit costs, in which case
    this is the binding constraint and saying "below the minimum ticket" would be false.
    """

    instrument_id: str
    path: EntryPath
    """Which way in delivered :attr:`actual`, and from which stream. See
    :attr:`BelowMinimumTicket.path`."""

    price_per_unit: Money
    min_unit: float
    actual: Money
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentRefused:
    """The instrument's own projection refused, and its reason is carried verbatim.

    The call that owns the terms is the one entitled to say why it produced no figure.
    Re-wording it here would put the join's interpretation between the owner and the
    declaration.
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
    """The declared term that binds.

    ``instrument.terminates_on`` today, and only that: 015 FR-029 sells a **bond** that
    outlives its window rather than refusing it, so what is left here is a fund still open at
    the horizon's end with no exit requested.
    """

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

    ``core.results.project`` folds a holding under **one** currency and sums every charge in
    it, so a hryvnia charge inside a dollar projection is a currency mismatch rather than a
    figure. A disposal adds a second gap, because a realised gain needs a per-lot basis carried
    in both currencies with each leg struck at its own date's rate. Both are
    ``fx-tax-asymmetry-f1`` in ``specs/features.toml``.

    **It must not be satisfied with a channel rate**, and neither must the base itself. A
    channel is a market you transact in; the official rate is a legal reference you never
    transact at, and substituting one for the other would strike a tax base at a price nobody
    was charged.

    Unreachable in the shipped registry, where every declared instrument is in hryvnia.
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

    Unreachable while every declared class charges a **fraction** of the income it taxes.

    **Strictly above 100%, and not at it.** At exactly 100% the date nets to zero,
    ``_released_by_date`` drops it, and the holding simply sends nothing home on it, which
    ``tests/unit/test_rate_and_horizon_boundaries.py`` pins from both sides. Which side of the
    boundary the declared rates fall on is a property of the rates rather than of the
    arithmetic, which is why this is a guard rather than an assertion that it cannot happen.
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
unreachable means a new member becomes an error at every site that must handle it. The count
is asserted against ``get_args`` in ``tests/unit/test_tuple_refusals.py``.
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

    Returned *instead of* a :class:`Comparison`. FR-011 says the hurdle must **always** be
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
