# Phase 0 research: 002-ramp-cost

**Date**: 2026-08-22

Thirteen decisions. D10–D12 were added after an external review of the artifacts; D13 during
implementation. Each records what was chosen, why, and what was rejected. No
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
cost_one(path, amount, ...)      -> RampCost        pure, no ledger, run for every candidate
execute(cost: RampCost, ...)     -> Sequence[Event] one fee event per fee-bearing component
```

⚙ **Corrected after review.** This decision originally wrote `execute(path, amount, as_of)`,
which contradicts its own conclusion: taking the path and the amount would mean `execute`
recomputes the arithmetic, which is exactly the second code path the paragraph below rejects.
It takes the **costed figure**. `contracts/route-costing.md` had it right; this decision did
not.

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

⚙ **Corrected after review.** `scripts/check_provenance.py` gains **`channels` only** —
not `streams`. A stream is the owner's own salary: a statement of fact by the only person who
can make it, not an observation needing a citation, and it carries the same exemption
`data/scenarios/` already has. `contracts/declaration-schema.md` had this right and this
decision did not. It also gains a check that every sourced table names a declared kind. It cannot check staleness itself — it has no
as-of date and should not invent one — so it verifies the *declaration* is complete and
leaves the verdict to the engine.

**Alternatives rejected**:

- *One project-wide threshold.* Rejected by the owner, and rightly: it would either warn
  constantly on fee schedules or stay silent on premiums, and a staleness warning that is
  usually wrong is one that gets ignored — worse than none.
- *Threshold per value, inline.* Drift, invisibly.
- *`datetime.now()` behind a "just for staleness" exemption.* It would make a run's output
  depend on the day it was run, breaking C4 determinism for a convenience.

## D10 — A monthly cap belongs to a shared rail, not to a route

**The defect this fixes**, found by review before `capacity.py` was written: caps were
declared per leg and accumulated by `(route_id, year, month)`. Two different routes both
using the owner's Monobank card would each get their **own full monthly limit**, when the
real limit belongs to the card and is consumed by whichever route touches it. Monobank's
monthly limit is one of the four numbers §11 item 1 names as the reason this feature exists,
so a model that cannot express it is not a modelling nicety — it is the feature failing at
its own purpose.

**Decision**: a leg declares `capacity_pool: str | None` — an identifier for the *shared
resource* whose limit it consumes. The accumulator keys on `(capacity_pool, year, month)`,
not on the route.

```toml
[[route.leg]]                                 # a different route, the same card
kind          = "fx"
capacity_pool = "monobank_card_uah_usd"       # <- both routes name this
monthly_cap   = 100000.0
```

`None` means the leg consumes no shared limit and its cap, if any, is its own. Two legs
naming the same pool **must declare the same cap** — a mismatch is a load-time failure,
because two different numbers for one real limit means at least one of them is wrong and
picking either silently would be a guess.

**Rationale**: a limit is a property of the *rail* — a card, an account, a corridor under a
regulatory ceiling — and a route is a path that uses rails. Keying on the route conflates a
path with a resource, which is the same category error as keying an access cost on an
instrument (FR-008, D2). FR-015's "capacity already consumed in the same month" then holds
*across* routes, which is the only reading under which it means anything.

**Alternatives rejected**:

- *Key on `(venue, year, month)`.* Closer, and still wrong: one venue can expose several
  rails with separate limits (a card and a bank transfer at the same bank), and one rail can
  span venues.
- *Derive the pool from the leg's `(from_venue, to_venue, from_ccy, to_ccy)` tuple.* Would
  work for the card case by accident and break the moment two products at one bank share a
  regulatory ceiling. The pool is a fact about the world; it should be declared, not inferred.
- *Leave it per route and document the limitation.* Rejected: the limitation is the feature's
  own headline number.

## D11 — Ranking is lexicographic, not scored

**The gap this fills**: FR-016 says "rank by round-trip cost, ceiling and latency" — three
keys and no aggregation rule. `Ranking.ties` implied a scalar score, and required-test row
**B12** forbids a non-standard composite score from driving the primary ordering.

**Decision**: **lexicographic** on `(round-trip cost, ceiling descending, latency)`, and a
**tie is a tie on the first key only** — two routes whose round-trip costs are equal within
the project tolerance are reported as tied even if their ceilings or latencies differ.

**Rationale**: B12 forecloses a weighted score, so the three keys have to be ordered rather
than combined, and FR-016 already states the order. Round-trip cost first is the whole point
of the feature. Reporting the tie on cost alone rather than on the full tuple is deliberate:
the owner asked "which is cheapest", and answering "these two cost the same, and here is how
they differ on ceiling and latency" is more useful than silently preferring one on a tiebreak
he did not ask for.

A weighted score would also have to weight hryvnia against days, which is a preference and
not a fact — precisely the kind of invented number Principle I refuses.

⚙ **Three things implementation had to settle that this decision did not**, recorded here
because they are now load-bearing:

- **A `None` ceiling sorts first.** `None` means no leg declares a cap — the *least*
  constrained a route can be — so it precedes every finite ceiling. Treating an absent cap as
  zero would rank the freest route last while looking like a sensible default.
- **Ties are anchored, not chained.** Tolerance equality is not transitive, so every member
  of a tie group is within one tolerance of the group's **first** member. Chaining
  neighbour-to-neighbour would let an arbitrarily wide band become one tie as candidates
  accumulate — the tolerance absorbing a real difference.
- **Ordering and tying are separate answers.** The sequence is ordered by all three keys, so
  it is deterministic; the tie is *reported* on the first key. The recommendation may sit
  inside a tie group, which is what stops the head of the sequence being read as a strict
  winner while still giving a defined order.

**Alternatives rejected**: a composite score (**B12** forbids it); cost-only with the other
two as decoration (throws away FR-016's other two keys); asking the owner for weights (a
decision-layer question, and this feature is not the decision layer).

## D12 — Staleness ages from the later of verification and retrieval

**The ambiguity this closes**: FR-025 says "verification **or** retrieval date has aged",
and the first implementation looked only at `retrieved_on`.

**Decision**: age from `verified_on` when it is set, otherwise from `retrieved_on` —
equivalently, from the later of the two, since a verification cannot precede the retrieval it
verifies.

**Rationale**: verifying a value against a primary source is the strongest possible refresh
of confidence in it, and stronger than re-fetching. A value retrieved two years ago and
verified last week is not stale; treating it as stale would tell the owner to re-check the
one thing he has actually checked, and a staleness warning that fires on verified values is
one that gets ignored.

The asymmetry is intentional and worth stating: an **unverified** value ages from retrieval,
which is the common case today and the stricter one.

## D13 — What `rank` returns when nothing is comparable

**The gap**, found during implementation of T019: `data-model.md` gives
`Ranking.recommended: int` and the contract gives `rank(...) -> Ranking`. Neither says what
either means when every candidate was refused or has no declared exit route. There is no
honest integer for "nothing".

**Decision**: `rank` returns `Ranking | NothingComparable`, where `NothingComparable` is an
unrelated frozen record carrying its reason plus the refused and exit-less candidates. Every
`Ranking` that exists therefore has a valid index, and `recommended_cost` is total with no
failure mode.

**Rationale**: a sentinel index would be **worse than the gap**. `-1` indexes the last
element of a tuple, so a ranking that had recommended nothing would silently recommend
something — a wrong number produced by a value chosen to mean "no number", which is the top
severity class. An `int | None` would work and forces narrowing at every call site including
each SC-016 assertion, which buys nothing over a distinct type and reads worse.

Same mechanism, same reason, as `RoundTripCost | ExitCostUnknown` (D4) and
`RealRate | RealTermsUnavailable` in feature 001: when there is no answer, the type says so
rather than a value standing in for it.

**`NothingComparable` distinguishes four cases** in its reason — nothing was offered, all
were refused, all lacked an exit route, or a mix — because the owner acts differently on
each, and "no comparison available" alone would tell him nothing about what to fix.
