# Phase 0 research: 002-ramp-cost

**Date**: 2026-08-22

Nine decisions. Each records what was chosen, why, and what was rejected. No
`NEEDS CLARIFICATION` remains — the spec's three were resolved by the owner before
planning; everything below is a design question.

---

## D1 — Where routes, legs, channels and streams live, without a fifth interface

**The constraint**: Principle II permits exactly four plugin interfaces — `Instrument`,
`Provider`, `TaxRule`, `ReturnModel`. Adding a fifth requires a constitution amendment.
This feature introduces four new kinds of thing, so it looks like it needs one.

**Decision**: it needs none. The four break down as:

| Thing | Where it lives | Why not an interface |
|---|---|---|
| **Route**, **leg**, **stream**, **venue** | Pure declared data | There is no pluggable *behaviour*. A leg's cost is arithmetic determined entirely by its declared fields. Nothing varies but the numbers. |
| **Leg kind** (`transfer`, `fx`, `trade`, `withdrawal`) | `Mapping[str, LegCostFn]` in core | An *algorithm registry*, exactly like `DAY_COUNT_FNS` and `COUPON_POLICY_FNS`. Adding a kind is code; adding a leg that *uses* one is data. |
| **FX channel** | Declared data now; `Provider` later | See below. |

**The leg-kind registry is the point worth defending**, because it is the thing that most
resembles a fifth interface. The precedent is already set and already argued: day-count
conventions are named in data and implemented in code, and research.md D7 of feature 001
records why that is not a Principle II violation. Principle II requires that adding an
**instrument, venue, tax regime or jurisdiction** be data-only. A leg *kind* is none of
those — it is an algorithm. A leg, a route and a venue are all data-only, which is what the
principle actually protects.

**FX channels sit exactly on the `Provider` seam, and this feature deliberately does not
build it.** A channel has two parts: a *reference rate on a date*, and a *markup or premium
off that reference*. The markup is declared data (the owner observes "+3 UAH per dollar on
Binance P2P"). The reference rate is what `Provider` exists to supply — §7 lists `fx` among
its responsibilities. But in this feature the reference is **also** a declared observation,
because there is no network, no cache and no snapshot of rates yet.

So the channel is declared data today, and the plan names precisely where `Provider` slots
in later: the function that resolves `(channel, date) -> two-sided rate` becomes a
`Provider` call instead of a lookup in a declared table. The signature is designed for that
substitution now so the seam is visible without being built. Implementing `Provider`
speculatively would mean inventing a rate source, which is the one thing Principle I
forbids most firmly.

**Alternatives rejected**:

- *A `Route` plugin interface.* Would let a route compute its own cost. But then two routes
  could cost the same amount differently, and FR-029's whole point is that they must not —
  see D3.
- *A `Channel` interface now.* It would have exactly one implementation, "read the declared
  table", and would exist only to be replaced. `Provider` already covers the eventual case.

## D2 — Making a per-destination cost unrepresentable (FR-008)

**Decision**: the cost is keyed by a frozen record that has no partial form.

```
FundingPath(destination_id, stream_id, route_id)     # all three required, no defaults
RampCost(path: FundingPath, ...)
```

Every function that produces or looks up a cost takes or returns a `FundingPath`. There is
no overload, no optional field, no `stream_id: str | None`. "The cost of reaching Binance"
has **no type to live in** — it is not a discouraged call, it is an expression that does not
typecheck.

**Rationale**: Principle VI's rule is the one most likely to be broken by accident rather
than by intent. A helper named `cost_of_reaching(venue)` reads perfectly reasonable, would
pass review from anyone not holding §4.3.1 in mind, and would silently hide the entire
finding — the same purchase is nearly free from the USD stream and 5–10% from the UAH one.
A convention cannot stop that; a missing type can.

A contract test additionally asserts that no public function in `core.routes` accepts a
destination without a stream and a route, so the property is checked rather than assumed
from the shape.

**Alternatives rejected**:

- *A required keyword argument.* Better than nothing, and still expressible: someone can
  pass a constant stream id to get past it, which is exactly what a hurried caller does.
- *A naming convention plus review.* This is the mechanism that already failed once in this
  project — the `nominal_ytm` mislabelling in feature 001 passed review and two agents.

## D3 — Proving the same code path costed the winner and the alternatives (FR-029, SC-016)

**Decision**: there is exactly **one** costing function, and the recommendation is an
*index into the costed set* rather than a separately computed field.

```
cost_one(path, amount, as_of) -> RampCost | RouteUnusable          # the only costing fn
Ranking(costed: tuple[RampCost, ...], recommended: int)            # an index, not a copy
```

`recommended_cost(ranking)` returns `ranking.costed[ranking.recommended]`. The winner is
not *compared against* the alternatives — it **is** one of them.

**SC-016 asks for proof by construction, and this is what makes that possible**: the test
asserts *identity*, `recommended_cost(r) is r.costed[r.recommended]`, not equality. Two
numbers that happen to agree today prove nothing about tomorrow; the same object cannot
disagree with itself. Nothing in the design has a second place for a cost to come from.

**Alternatives rejected**:

- *`Ranking(recommended: RampCost, alternatives: tuple[RampCost, ...])`.* The natural shape,
  and the wrong one: `recommended` is a separate value that could have been produced by a
  separate path, and a test comparing it to the alternatives compares two numbers rather
  than establishing they share an origin.
- *A fast pre-pass to discard obviously-bad routes, then full costing of the rest.* Rejected
  as a *costing* shortcut. A cheap **feasibility** filter is still permitted — a route
  declared closed on the date is excluded before costing, with its status recorded (FR-014)
  — because that is not an approximation of cost, it is an answer to a different question.

## D4 — A missing exit route must not be fillable with a one-way figure (FR-030)

**Decision**: distinct types, following the precedent `RealRate | RealTermsUnavailable` set
in feature 001's D4.

```
OneWayCost      # distinct type
RoundTripCost   # distinct type
round_trip: RoundTripCost | ExitCostUnknown       # ExitCostUnknown carries the missing id
```

`OneWayCost` and `RoundTripCost` are unrelated frozen records, so assigning a one-way figure
into the round-trip slot is a **mypy strict error**. `ExitCostUnknown` names the exit
declaration that does not exist, satisfying FR-017's rule that a degraded outcome carries
its reason.

Ranking accepts only costs whose round trip is a `RoundTripCost`; a destination with an
unknown exit is reported separately and is **not** comparison-ready.

**Rationale**: this is the same mechanism, for the same reason, as the nominal/real split —
and that one has already earned its keep. The tempting silent fix here (promote the one-way
figure, since it is "most of" the cost) would produce a confident round-trip number for an
exit path nobody has ever looked at. Principle VI: an asset that cannot be liquidated at a
reasonable cost is not worth its stated value, and "we never checked" is that case.

## D5 — Costing is a pure calculation; execution writes events

**The tension**, stated as the plan input put it: FR-005 says every fee is an explicit
recorded line and B13 forbids blending fees into an outcome, which argues for ledger
events. But a route comparison costs *many* routes and only *one* is executed. Writing
events for all of them would put fees in the ledger for money that never moved.

**Decision**: two functions, one arithmetic.

```
cost_one(path, amount, as_of)  -> RampCost        pure, no ledger, run for every candidate
execute(path, amount, as_of)   -> Sequence[Event] one fee event per fee-bearing leg
```

`execute` is defined in terms of `cost_one`'s per-leg attribution: it walks the same
`RampCost` and emits an event per component. So the ledger cannot disagree with the
comparison — the events are *derived from* the costed figure rather than recomputed
alongside it.

**The invariant that makes this safe** is a property test: for any route and amount,
the fee events `execute` produces sum to exactly the cost `cost_one` reported, and the
arriving amount in the ledger equals the arriving amount in the `RampCost`. Cost-then-execute
agreement is asserted, not assumed.

**Alternatives rejected**:

- *Events for every candidate, discarded for the losers.* Fees in the ledger for money that
  never moved; cash conservation (C1) would have to learn about hypothetical events.
- *Cost computed by folding events for each candidate.* Cleanest-sounding, and it makes the
  comparison as expensive as an execution while forcing the ledger to model counterfactuals.
- *Two independent implementations, cross-checked by a test.* This is the shape D3 exists to
  forbid, one layer down.

## D6 — Leg chaining is validated at load, not at cost time

**Decision**: currency and venue continuity — leg *n* ending where leg *n+1* begins, the
route's first leg starting at its declared origin, the last ending at its declared
destination — is checked in `data.declarations.resolver`, the same cross-file pass that
already catches duplicate ids and undeclared tax classes. Failure names the file and the
leg index.

Core may then assume a chained route. If it is handed a broken one anyway, it raises
`LedgerInvariantError` rather than returning a typed failure, because at that point the
caller is a programmer error and not a data error — the established split from feature 001.

**Rationale**: continuity is a structural property of the declaration, knowable with no
amount and no date, so it belongs where the file is read and where the error can name it.
Deferring it to cost time would mean the same broken route produced an error message per
call site rather than one message naming the file.

## D7 — A monthly cap is state in the fold, not a clock lookup

**Decision**: consumed capacity is accumulated in ledger state, keyed by
`(route_id, year, month)`, exactly the way per-currency cash balances already are. The month
comes from the event's `occurred_on`, which is data. Remaining headroom is
`cap − consumed`, and it is passed explicitly to the function that decides feasibility.

**Rationale**: the core has no clock and may not acquire one (`datetime.now` is blocked by
`.importlinter`). Every date in this system arrives as data — that is what makes the whole
engine reproducible. A cap is not an exception to that; it is one more accumulator in a
fold that already accumulates.

This also gets FR-015 for free: capacity consumed earlier in the same month is already in
the accumulator, so "the remaining headroom applies, not the full cap" is not a special
case.

## D8 — Regimes are scenario data; leg windows are facts

**The question**: legs already carry `available_from/until`, so a regime transition could be
expressed as a set of leg windows. Should it be?

**Decision**: no. Both exist, with a division that is about *epistemic status*, not
mechanics:

- **A leg's `available_from/until` is a fact.** "This corridor closed in March 2025." It
  happened; it is observed; it carries a source.
- **A regime transition is an assumption.** "The war ends mid-2027." Nobody knows. FR-020
  requires it be presented as a stated assumption rather than a known fact.

Collapsing regimes into leg windows would bury an assumption inside a field whose every
other value is an observation — and then no output could honestly distinguish "this route is
closed because it closed" from "this route is closed because I guessed a date". That
distinction is the entire content of `SIMULATOR_SPEC.md` §1.3 and of User Story 4.

So a regime is a named record in scenario data: a transition date marked as an assumption,
and the route set effective on each side. `data/scenarios/` already exists and is already
exempt from the citation requirement precisely because it holds the owner's own beliefs.

## D9 — Staleness is evaluated against an as-of date, and thresholds are per kind

**Decision**, two halves.

**Per kind, declared once.** A new `data/observation_kinds.toml` declares each kind of
observed value and its staleness threshold in days: a peer-to-peer premium ages in days, a
published fee schedule in years, a regulatory limit when the regulator says so. Every
sourced table names its kind. A kind with no declared threshold **fails at load** —
FR-028's "no permissive default" — and so does a table naming a kind that does not exist.

Declaring the threshold once per kind rather than per value means the owner sets the policy
in one place; repeating it per value would guarantee drift, and drift in a staleness
threshold is invisible.

**Evaluated against an explicit as-of date.** The core has no clock, so staleness is
`as_of − retrieved_on > threshold`, where `as_of` is an input to the run, recorded in the
manifest. This keeps the whole computation reproducible: the same inputs produce the same
staleness verdicts forever, which would be false if "now" were read from the machine.

`scripts/check_provenance.py` gains `streams` and `channels` to `SOURCED_DIRS`, and a check
that every sourced table names a declared kind. It cannot check staleness itself — it has no
as-of date and should not invent one — so it verifies the *declaration* is complete and
leaves the verdict to the engine.

**Alternatives rejected**:

- *One project-wide threshold.* Rejected by the owner, and rightly: it would either warn
  constantly on fee schedules or stay silent on premiums, and a staleness warning that is
  usually wrong is one that gets ignored — worse than none.
- *Threshold per value, inline.* Drift, invisibly.
- *`datetime.now()` behind a "just for staleness" exemption.* It would make a run's output
  depend on the day it was run, breaking C4 determinism for a convenience.
