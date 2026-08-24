# Phase 1 data model: the full tuple

**Feature**: `010-full-tuple` | **Date**: 2026-08-23 | **Reconciled with the code**: 2026-08-24

Frozen records, free functions, tagged unions matched with `match`. One imported tolerance.

**The rule that governs this file: the join holds no figure it computed itself.** Every
amount below came from a call that owns it, and the join's own content is the chaining and
the refusals (research.md D1).

⚙ **This file was written before the code and has been corrected against it once**, on
2026-08-24, after a review found six records here that no longer described anything shipped —
a `benchmark: TupleOutcome` where the code holds an index, a `float` rate where the code holds
a union, a refusal that was never built, and eight that were. A design document that has
drifted is worse than none: it is read as a specification of what exists. Where it and the
code now disagree, the code is right and this file is the defect.

---

### `Tuple` — the unit of analysis, `core/results/tuple.py`

| Field | Type | Meaning |
|---|---|---|
| `instrument_id` | `str` | Of either declaration kind |
| `stream_id` | `str` | Which income funds it |
| `route_in` | `Candidate` | 002/004's declared or composed path |
| `exit_terms` | `Assumptions \| FundAssumptions` | Which declared way out of the *instrument*, and how the holding is run |
| `route_out` | `ExitChoice` | A named chain, or `FROM_THE_DECLARATION` |

Identity is all five (FR-010). A cost or outcome attributed to an instrument alone stays
unrepresentable, as 002 FR-008 and 004 FR-011 already require.

**The risk class is not a field here.** It is declared per option in `data/access/`, carried
onto the outcome and scored nowhere (research.md D9) — a property of *this instrument reached
this way* rather than of the security, which is why it belongs with the other three terms the
access declaration holds. What that shape *admits* later, and does not express today, is set
out under `InstrumentAccess` below.

`Tuple.stream_id` and `route_in.stream_id` are two spellings of one fact and are **checked
against each other** before anything is costed; see `FundedFromAnotherStream`.

### `InstrumentAccess`, `core/instruments/access.py`

The declaration kind this feature had to add: nothing else in `data/` says *where* an
instrument is bought (FR-023, `docs/METHODOLOGY.md` §28.6). Keyed by instrument id, one row
each — a second row for one instrument is refused at load, so *one instrument at two venues*
is a shape the seam **admits later** rather than one it expresses today; expressing it would
also need a venue term on `Tuple`.

| Field | Type | Meaning |
|---|---|---|
| `instrument_id` | `str` | The key. Resolved against both instrument registries |
| `bought_at` | `str` | The venue the purchase happens at — the way in's far end |
| `proceeds_to` | `str` | The venue the proceeds land at — the way out's near end |
| `quote` | `VenueQuote \| None` | `None` where the instrument prices itself |
| `risk_class` | `str` | Principle VI's fifth term. Carried, never scored |

`VenueQuote` is `price: Money` and `kind: str` together, because a price with no staleness
kind can never be reported stale and a kind with no price is nothing at all.

### `TupleOutcome`

| Field | Type | Meaning |
|---|---|---|
| `key` | `Tuple` | All five terms; an outcome cannot exist without one |
| `outlay` | `Money` | What left the stream, whole, on `span.start` |
| `parts` | `tuple[PartContribution, ...]` | The six terms, separately (FR-005) |
| `arrivals` | `tuple[Arrival, ...]` | Every dated amount that reached a spendable endpoint |
| `reaches` | `Money` | The sum of `arrivals` |
| `implied_rate` | `NominalRate \| RateNotComparable` | Present and typed either way, never absent |
| `span` | `DateRange` | First outlay to last arrival — what the rate is a rate over |
| `horizon` | `DateRange` | The **one** horizon of the comparison (FR-025) |
| `undeployed` | `UndeployedCash \| None` | Money that made the trip and bought nothing |
| `routes` | `RouteStanding` | The declared status and disruption probability of **both** ways — the two `RampCost` fields that used to be dropped in silence |
| `risk_class` | `str` | Carried from the access declaration |
| `rests_on` | `tuple[str, ...]` | The stated assumptions, in words, sorted |
| `accounts_for` | `frozenset[str]` | Stated on every figure |
| `excludes` | `frozenset[str]` | Stated on every figure (FR-014) |
| `provenance` | `Provenance` | The union of every declared value behind every part |
| `staleness` | `StalenessVerdict` | Merged across the way in, the way out and the venue quote |

**Both figures, always** (research.md D8): the amount is what can be spent, the rate is what
compares across horizons, and reporting one invites deriving the other under an assumption
the tool did not make.

**Every field of `RampCost` either reaches the outcome or has a recorded reason.**
`round_trip` is about a different journey — this tuple's way out starts where the *instrument*
releases its proceeds, not where the inbound chain ended — and `exit_path` is the inbound
record's, not this tuple's. Those two are dropped and say so.

**Five fields of a `WayOutCost` reach nowhere, symmetrically with a `OneWayCost`'s**, and this
is the reason rather than an omission: `path`, `fraction`, `spreads_over_reference`,
`channels_applied` and `by_segment` are the *cost record's* attribution of one movement, and a
tuple's outcome reports its own attribution — six parts, in journey order, each naming the
call that produced it. A round trip's way-out charges arrive there summed into `ramp_out`,
with the same five facts available on the `WayOutCost` a reader can go and re-cost. Carrying
them per release would put a second, finer attribution on the outcome that nothing reads and
that would disagree with the first the moment either changed. What is *not* symmetrical is
`status`, `disruption_probability` and `ceiling`: those say whether the figure can be trusted
or produced at all, and all three are carried.

**The rate's denominator is `outlay` less `undeployed`** — the money actually invested. The
remainder is cash at the purchase venue, not money lost, and leaving it in the series prices
it as a total loss. What that netting assumes — recovery at par, which is not free — is one of
the `excludes` clauses rather than a footnote.

### `PartContribution`

| Field | Type | Meaning |
|---|---|---|
| `part` | `Literal["ramp_in","entry","lifecycle","tax","exit_terms","ramp_out"]` | Closed |
| `amount` | `Money` | Signed as the ledger signs things |
| `source` | `str` | Which call produced it — so a reader can go check it |

Never summed across parts: the six are in up to three currencies, and two of them describe
the same money from two sides.

### `Arrival` and `UndeployedCash`

| `Arrival` | Type | | `UndeployedCash` | Type |
|---|---|---|---|---|
| `released_on` | `date` | | `amount` | `Money` |
| `arrived_on` | `date` | | `venue_id` | `str` |
| `released` | `Money` | | `reason` | `str` |
| `amount` | `Money` | | | |

`arrived_on` is `released_on` plus the way out's declared latency, and it is **inside** the
span the rate is measured over (FR-015).

### `WayOutCost`, `core/results/ramp.py`

One dated release, costed from where it was released to a spendable endpoint. Unrelated to
`OneWayCost` and `RoundTripCost` by type, so neither can stand in for it.

| Field | Type | Meaning |
|---|---|---|
| `path` | `Candidate` | Keyed by the whole triple, from the other end (FR-008) |
| `sent` | `Money` | What left the venue the instrument released it at |
| `arrived` | `Money` | What reached the endpoint. May be zero or negative |
| `components` | `Mapping[CostComponent, Money]` | Every member present, zero where it does not apply |
| `fraction` | `float` | Not capped, in either direction |
| `spreads_over_reference` | `tuple[float, ...]` | One rate-space spread per converting leg — §4.3.1's own figure, not the cost |
| `channels_applied` | `tuple[str, ...]` | Which channel each `fx` leg used, in leg order |
| `by_segment` | `tuple[SegmentAttribution, ...]` | The same charge split by segment, numbered from zero within this way out |
| `latency_days` | `int` | On the figure, because it moves the arrival date |
| `status` | `RouteStatus` | The most constrained segment's — `RampCost.status`'s counterpart, whose absence that field's own docstring recorded as a gap |
| `disruption_probability` | `float` | The largest single leg's, never compounded |
| `ceiling` | `Money \| None` | `RampCost.ceiling`'s twin. FR-016 applies on the way out too, and a caller that reads it nowhere repatriates past it in silence |
| `provenance`, `staleness` | | Carried like every other cost |

### `Comparison`

| Field | Type | Meaning |
|---|---|---|
| `horizon` | `DateRange` | Stated once, applied to all (FR-025) |
| `continuation` | `ContinuationAssumption` | Required, no default anywhere (FR-025) |
| `ranked` | `tuple[TupleOutcome, ...]` | Comparison-ready, best first |
| `benchmark` | `int` | An **index** into `ranked`, never a copy (FR-012) |
| `ties` | `tuple[tuple[int, ...], ...]` | 002's tie rules unchanged, hurdle included (FR-013) |
| `refused` | `tuple[RefusedTuple, ...]` | Visible, never silently absent |
| `not_comparable` | `tuple[TupleOutcome, ...]` | Computed in full, holding no rate |
| `beats_benchmark` | `tuple[int, ...]` | Strictly more than the tolerance. Empty is an answer |

The three lists **partition** the tuples offered: every one lands in exactly one, and that is
asserted as a partition rather than as a total that adds up.

### `BenchmarkUnavailable`

Returned *instead of* a `Comparison` where the benchmark itself refused or produced no rate.
Carries `refusal`, `scored` (the other outcomes, in **candidate order** — deliberately not
ranked), `refused`, `not_comparable` and `reason`.

## Refusals — seventeen, and the count is asserted

| Record | When |
|---|---|
| `DeclarationMissing` | Which part, and which declaration (FR-006) |
| `SeamDoesNotChain` | A venue/currency seam, naming **both sides** (FR-004) |
| `FundedFromAnotherStream` | The tuple's stream and its way in's stream disagree (FR-010) |
| `RouteInUnusable` | 002's feasibility on the way in, carried whole -- a per-transaction `leg.maximum`, a closed route (FR-016) |
| `RouteInCapExceeded` | The way in's declared monthly ceiling is below the amount. Distinct from the above: the rail carries this much *a month*, and the remedy is to wait rather than to split (FR-016, FR-018) |
| `WayOutCapExceeded` | The same on the way out, naming **which dated release** could not go home (FR-016, FR-018) |
| `WayOutUnusable` | The way out will not carry what was released, on the date it was |
| `NoExitRouteDeclared` | Inherits 002 FR-030's treatment (FR-007) |
| `NoExitTermsDeclared` | The instrument side of the same gap (FR-008) |
| `BelowMinimumTicket` | Names the minimum, what arrived and the shortfall (FR-017) |
| `BuysNoWholeUnit` | Clears the ticket, will not buy one increment |
| `InstrumentRefused` | The projection's own reason, carried verbatim |
| `CannotSpanHorizon` | FR-025's second consequence, with the binding term named |
| `TwoFiguresNotOne` | A declared range and no chosen point inside it |
| `PlanDoesNotFitInstrument` | Run settings for the other declaration kind |
| `TaxCurrencyConversionUnavailable` | A foreign-currency taxable event (research.md D10) |
| `InstrumentDemandsCash` | A date that nets negative, refused rather than netted forward |

## What is deliberately absent

- **No figure the join computed.** Only sums of what the owning calls returned.
- **No reinvestment assumption** for proceeds arriving before the horizon ends.
- **No risk score.** The class is declared and carried; scoring needs a model nobody declared.
- **No display currency** of any kind (FR-024).
- **No partial deployment.** FR-018 defers it (owner decision, 2026-08-22), so there is no
  record for a split acquisition and no `PartiallyDeployable`: an acquisition is **one dated
  purchase event**. An earlier draft of this file listed one; it was never built. An amount
  over a declared monthly ceiling therefore **refuses** — see `plan.md`'s departures list for
  why deploying up to the cap could not be done honestly here.
- **No special case that makes H1 pass.** A data-only addition needing an engine edit is a
  recorded defect in the abstraction, and fixing the abstraction is in scope (FR-023).
