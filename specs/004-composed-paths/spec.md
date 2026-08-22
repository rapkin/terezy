# Feature Specification: Composed paths

**Feature Directory**: `specs/004-composed-paths`

**Feature Branch**: none — this repo works on `main` by design

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: Composed paths — reaching a destination through intermediate venues when no
single declared route goes end to end, by chaining declared routes.

---

## Why this feature exists

Feature 002 made a route a hand-declared end-to-end chain, and that was the right first
shape: every leg is an observation, every cost is traceable to a declaration. But it
leaves a gap that grows with the registry. `SIMULATOR_SPEC.md` §4.3.2 says corridors get
added and dropped constantly — and today a corridor nobody declared **end to end** is
unreachable even when the registry already contains **every segment of it**. The owner's
own venue list makes the case concrete: UAH salary → Binance is declared, Binance → IBKR
is declared, and UAH salary → IBKR **via** Binance does not exist unless someone sits down
and hand-writes the concatenation. Every new venue multiplies the concatenations nobody
will write.

This feature lets the engine compose candidate paths from declared routes: venues are
nodes, declared routes are edges, and a candidate is a chain whose venues, currencies,
directions and regimes connect. It widens the answer to `SIMULATOR_SPEC.md` §8 question 2
— *fund IBKR now, or wait?* — to every way of funding IBKR the registry can already
express, not only the ways someone remembered to declare in full.

**The reason to specify it carefully is the temptation it brings.** Composition is a
routing problem, and routing problems attract shortest-path heuristics, approximate
costing, pruning by estimate, and tie-breaks by whatever order the search visited things.
Every one of those is a number more confident than its inputs — the defect class this
project exists to refuse. Left unspecified, composition would grow inside the ranking
code and acquire those habits invisibly. So the spine of this specification is a set of
reconciliations with decisions already made once: composition **invents no numbers**;
composed candidates are **costed in full through the single costing function** (002
FR-029); they enter the **same lexicographic ranking and tie rules** (002 FR-016/FR-018);
cycles are refused; the search bound is **data, not code**; and within-noise results are
**ties**, never resolved by enumeration order (Principle I).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reach a destination nobody declared end to end (Priority: P1)

The owner names an amount, a stream and a destination for which no single declared route
exists — but the registry holds routes that chain from the stream's arrival venue,
through intermediate venues, to the destination. The tool composes those chains, costs
each one exactly as it would cost a declared route, and ranks them alongside any declared
routes to the same destination.

**Why this priority**: this is the capability the feature exists to add. Without it, the
comparison the owner most needs — the domestic hurdle against a foreign destination
reachable only through an intermediate venue — silently omits candidates the registry
already knows how to price.

**Independent Test**: declare two routes that chain (salary venue → exchange, exchange →
broker) and no end-to-end route; ask for the broker destination; check the composed
candidate's arriving amount and cost percentages against leg-by-leg arithmetic worked out
by hand.

**Acceptance Scenarios**:

1. **Given** a registry with a declared route A→B and a declared route B→C whose venues,
   currencies, directions and regimes connect, and no declared route A→C, **When** the
   owner asks to move an amount from A's stream to C, **Then** a composed candidate A→B→C
   is produced, and its arriving amount and cost match the hand-computed result of
   applying every leg of both segments in order.
2. **Given** a composed candidate and a declared route to the same destination, **When**
   they are compared, **Then** both are costed through the same costing path and ranked
   by the same lexicographic keys, and the comparison names which is cheaper round trip.
3. **Given** two declared routes whose meeting venue matches but whose currencies at the
   junction do not (one arrives in USDT, the next departs in USD), **When** candidates
   are enumerated, **Then** no candidate joins them — the chain does not connect, and the
   corridor's absence is a fact for the coverage report, not something to bridge.
4. **Given** any composed candidate, **When** its cost is presented, **Then** every
   figure is labelled one-way or round-trip exactly as 002 FR-002 requires, and cost is
   attributed both to its components and to its segments, so a reader can see which
   segment and which term dominates.

---

### User Story 2 - Trust that composition invented nothing (Priority: P1)

Every number on a composed candidate is traceable to a declaration. Provenance,
staleness, capacity pools, latency, status and disruption compose by the rules feature
002 already fixed — a composed path behaves exactly as a declared route with the same
concatenated legs would.

**Why this priority**: equal-highest with Story 1, because a composed candidate that
*looks* like a costed route but rests on an interpolated rate, a defaulted cap or a
dropped provenance mark is worse than no candidate. Principle I outranks the convenience
of reachability.

**Independent Test**: compose a path where one segment carries an unverified value and a
short-threshold stale value; confirm every figure derived on the composed candidate
carries the unverified mark and the staleness report.

**Acceptance Scenarios**:

1. **Given** a composed candidate one of whose segments carries an unverified value,
   **When** it is costed, **Then** every figure derived from that value on the composed
   candidate carries the unverified mark (002 FR-022), with no laundering at the join.
2. **Given** a segment value aged past its declared per-kind staleness threshold,
   **When** the composed candidate is reported, **Then** every derived figure is reported
   stale by the rules of 002 FR-025/FR-028.
3. **Given** two segments of one composed path whose legs name the same capacity pool,
   **When** feasibility is computed, **Then** both legs consume the one shared monthly
   headroom (002's pool accounting), and the deployable amount matches the hand-computed
   joint consumption — never each leg getting the full limit.
4. **Given** any composed candidate, **When** disruption is reported, **Then** every
   leg's declared disruption probability appears per leg (002 FR-026), and no combined
   path-level probability is synthesized — combining them would require an independence
   assumption nobody declared.
5. **Given** a composed candidate, **When** its latency and ceiling are reported,
   **Then** they are exactly what a declared route with the same concatenated legs would
   report — latency accumulating across legs, the ceiling set by the binding constraint,
   with the binding segment named.

---

### User Story 3 - Keep the search honest and bounded (Priority: P2)

Enumeration is exhaustive within a declared bound, cycles are refused, and no candidate
is dropped, truncated or approximated without a recorded reason.

**Why this priority**: the bound and the cycle rule are what keep enumerate-and-rank
finite without smuggling in a heuristic. They follow Stories 1 and 2 because a small
registry needs neither to be useful, but the spec must fix them before the registry
grows.

**Independent Test**: declare a registry whose route graph contains a loop and a corridor
requiring more segments than the declared bound; confirm no candidate visits a venue
twice, no candidate exceeds the bound, and the bound in force is visible in the results.

**Acceptance Scenarios**:

1. **Given** a registry whose routes form a cycle among venues, **When** candidates are
   enumerated, **Then** no candidate visits any venue more than once, verified over the
   full candidate set rather than sampled.
2. **Given** a maximum segment count declared as data, **When** candidates are
   enumerated, **Then** every chain of connectable declared routes up to that length
   appears as a candidate, none longer does, and the bound in force is recorded with the
   results — so a missing corridor is attributable to the bound rather than mistaken for
   a gap in the registry.
3. **Given** no declared maximum segment count, **When** declarations are loaded,
   **Then** loading fails naming the file and the missing field — no permissive default,
   exactly as 002 FR-028 refuses a default staleness threshold.
4. **Given** the same registry, bound and as-of date, **When** enumeration runs twice,
   **Then** the candidate sets are identical and identically ordered — enumeration order
   never influences any reported result.
5. **Given** two candidates whose round-trip costs are equal within the project
   tolerance, one composed and one declared, **When** they are ranked, **Then** they are
   reported as a tie under 002 FR-018 — never resolved in favour of whichever the search
   found first.

---

### User Story 4 - Respect feasibility, regimes and the join (Priority: P2)

A composed candidate is subject to every constraint its segments declare, on the date in
question, within one regime.

**Why this priority**: an unexecutable composed plan reported as executable is the top
severity defect class, same as it was in 002. It follows Story 1 because composition is
useful before regime handling, but not before feasibility.

**Independent Test**: compose a path with one segment declared closed on the date; confirm
the candidate is excluded with the binding constraint named and its absence visible.

**Acceptance Scenarios**:

1. **Given** a composed candidate one of whose segments is closed or outside its
   availability window on the date, **When** candidates are ranked, **Then** it is
   excluded with the binding segment and status recorded, and its absence is visible
   rather than silent (002 FR-014).
2. **Given** a scenario with a regime transition, **When** candidates are enumerated for
   a date, **Then** every segment of every candidate belongs to the route set of the
   regime in force on that date — no candidate connects by mixing route sets across the
   transition.
3. **Given** an amount below a minimum declared anywhere along the chain, **When** the
   candidate is costed, **Then** it is reported unusable for that amount naming the
   minimum, the shortfall and the segment, and is never silently rounded up.
4. **Given** a composed candidate and a monthly cap partly consumed earlier in the month
   — by any route or candidate touching the same capacity pool — **When** feasibility is
   computed, **Then** the remaining headroom applies, not the full cap (002 FR-015 across
   composition).

---

### User Story 5 - Extend reach with a declaration, never with an engine edit (Priority: P3)

Adding one declared route extends the reachable graph. Nothing else is needed, and
nothing else is allowed: composition uses what is declared, and what is not declared is
the coverage report's news to deliver (feature 003), not composition's gap to fill.

**Why this priority**: the framework claim of Principle II, applied to composition. P3
because it is verified rather than built — the property falls out of composition reading
the same registry the coverage report reads.

**Independent Test**: add one route declaration connecting a previously terminal venue
onward; confirm new composed candidates appear, fully costed and ranked, with zero source
changes.

**Acceptance Scenarios**:

1. **Given** a registry where venue B is reachable but terminal, **When** a route B→C is
   added purely as data, **Then** composed candidates ending at C appear in the next run,
   fully costed and ranked, with no source-code change.
2. **Given** a corridor whose chain is broken by one missing segment, **When** candidates
   are enumerated, **Then** no candidate is fabricated to span the gap — the corridor is
   simply absent, and saying so is the coverage report's job (feature 003), not this
   feature's.
3. **Given** a malformed declaration of the segment bound, **When** it is loaded,
   **Then** loading fails naming file and field with no default substituted (002 FR-024's
   rule, applied to this feature's one new declaration).

---

### Edge Cases

- **A composed chain whose leg sequence is identical to a declared route's** — the same
  thing counted twice. It appears **once**, as the declared route; a ranking never holds
  two candidates with identical leg chains. A chain over the same *venues* with different
  legs or terms is a genuinely different candidate and both stand.
- **A junction where venue matches but currency does not** (segment arrives in USDT, next
  departs in USD) — not connected. Never bridged by an implicit conversion; an implicit
  conversion is an invented leg with an invented rate.
- **A segment bound declared as 1** — composition is effectively off: only declared
  routes are candidates. Legal, and the explicit way to disable composition; distinct
  from a *missing* bound, which is refused at load.
- **Revisiting a venue in a different currency** (A/UAH → B → A/USD → C) — refused. A
  cycle is a repeated venue, because venues are the nodes; a genuinely useful
  out-and-back corridor can still be hand-declared as a single route, where its terms are
  observations rather than a search artifact.
- **Two segments each individually within their caps whose shared pool binds jointly** —
  the pool binds once across both; deployable amount reflects joint consumption, never
  double-counted headroom.
- **A composed candidate every segment of which is verified except one** — the whole
  candidate's derived figures carry the mark. One unverified segment is enough; the mark
  does not average away across segments.
- **Fees along a long chain exceeding the amount moved** — reported as such, never
  clamped (002 FR-005). Chains make this case more likely, not more acceptable.
- **A destination reachable only by composition whose exit is also only composable** —
  it has a round-trip figure: a chain of declared exit routes satisfies 002 FR-027 by
  owner decision (FR-012). Where no declared exit segments chain to a spendable
  endpoint, 002 FR-030's *exit cost unknown* stands and no one-way figure is promoted.
- **Several composed exit chains from one destination** — one round-trip figure per exit
  chain, each keyed and reported separately (FR-012); chains within tolerance of each
  other tie under the same rule as everything else, and are never averaged into a
  blended exit cost.
- **An exit route that would complete an inbound chain** (or the reverse) — not a
  connection (FR-022). The corridor may exist in the world; what was *observed* is one
  direction, and composition uses observations, not symmetry.
- **An enormous candidate set within the bound** — costed in full anyway (002 FR-029).
  Slow and honest beats fast and approximate; if the owner wants fewer candidates, the
  bound is the declared knob.
- **The same corridor reachable both as a declared end-to-end route and by composition,
  costing within tolerance of each other** — a tie, reported as a tie, and the useful
  fact that the hand-declared route buys nothing over its segments is visible rather
  than suppressed.

## Requirements *(mandatory)*

### Functional Requirements

**Composition**

- **FR-001**: The system MUST enumerate composed candidates for a stated
  `(stream, amount, destination)`: ordered chains of declared routes in which each
  segment's destination venue and arriving currency match the next segment's origin venue
  and departing currency, the first segment starts at the stream's arrival venue, and the
  last segment ends at the destination.
- **FR-002**: Composition MUST invent no numbers. Every segment of a composed candidate
  is a declared route used exactly as declared; no rate, fee, cap, minimum, latency,
  status, window or probability may exist on a composed candidate that does not exist on
  one of its segments. In particular, no implicit conversion, bridging leg or
  interpolated value may be created at a junction.
- **FR-022**: Directions connect only with themselves. A route's direction — inbound or
  exit — is part of what was declared and observed, and composition MUST NOT mix
  directions: an inbound composed candidate chains only routes declared inbound, and a
  composed exit chain (FR-012) chains only routes declared exit. Using an exit route as
  a segment of an inbound journey, or an inbound route as a segment of an exit chain, is
  **not a connection** — an observation of a corridor in one direction says nothing
  about its terms, limits, or existence in the other, and treating it as if it did would
  invent a corridor nobody observed. A composed exit chain starts at the destination and
  ends at a **declared spendable endpoint** — the owner-declared spendable list this
  project already recognises — and obeys every other composition rule (cycles, bound,
  exhaustiveness, determinism) unchanged.

  ⚙ **Added on review.** "Directions connect" appeared in User Story 1 and the composed
  candidate's definition without any requirement saying what connecting meant. Once the
  owner's first decision made composed exit chains real, leaving it undefined would have
  left the inbound/exit boundary to the implementer.
- **FR-003**: A composed candidate MUST be costed **in full, through the same single
  costing function as a declared route** (002 FR-029), by applying every leg of every
  segment in order (002 FR-001). No shortest-path or best-first heuristic may skip,
  summarise, or approximate the costing of any candidate, and no candidate's cost may be
  produced by a different path than any other's.
- **FR-004**: A composed candidate MUST behave, for every rule feature 002 states over a
  route's legs — cost attribution, channel attribution, caps, minimums, monthly
  headroom, latency, availability, disruption reporting, provenance and staleness —
  exactly as a declared route with the same concatenated legs would. Composition adds
  reach, never new arithmetic.

**Search discipline**

- **FR-005**: A composed candidate MUST NOT visit any venue more than once. Venues are
  the nodes of the search; a chain that would revisit one is never emitted as a
  candidate.
- **FR-006**: The maximum number of segments in a composed candidate MUST be declared as
  data, never hardcoded. A registry with no declared bound MUST fail at load naming file
  and field — no permissive default, by the same rule that refuses a default staleness
  threshold (002 FR-028). A malformed bound fails at load the same way (002 FR-024).
- **FR-007**: Within the declared bound, enumeration MUST be exhaustive: every chain of
  connectable declared routes up to the bound is a candidate, and no candidate is
  dropped, truncated or deferred without a recorded reason. The bound in force MUST be
  recorded alongside the results, so a corridor's absence is attributable to the bound
  rather than mistaken for a registry gap.
- **FR-008**: Enumeration MUST be deterministic — the same registry, bound, regime and
  as-of date produce the same candidate set — and enumeration order MUST NOT influence
  any reported figure, ranking position, recommendation or tie. Within-tolerance results
  are ties per 002 FR-018 and Principle I, never resolved by the order the search found
  them.
- **FR-009**: A ranking MUST NOT contain two candidates with identical leg chains. Where
  a composed concatenation reproduces a declared route leg for leg, the declared route
  stands and the duplicate is not emitted. Candidates over the same venues with
  differing legs or terms are distinct and all stand.

**Ranking and comparison**

- **FR-010**: Composed candidates MUST enter the same lexicographic ranking as declared
  routes — `(round-trip cost, ceiling descending, latency)` per 002 FR-016 — in one
  candidate set, under the same tie rules (002 FR-018). There is no separate league for
  composed paths and no bonus or penalty for being composed.
- **FR-011**: Access cost for a composed candidate MUST be keyed per
  `(destination × stream × path)`, and a cost attributed to a destination alone MUST
  remain unrepresentable, extending 002 FR-008 to composed candidates without exception.
- **FR-012**: A chain of separately declared exit routes **satisfies** 002 FR-027's
  "separately declared exit route" (owner decision, 2026-08-22). A composed round trip
  exists whenever declared exit segments chain from the destination back to a declared
  spendable endpoint, under exactly the composition rules of this spec — same
  connectivity, same direction discipline (FR-022), same cycle refusal, same declared
  segment bound, same exhaustive and deterministic enumeration. The owner's reasoning is
  recorded: this reinforces the rule that *everything must have at least one way out* —
  every link is a declared observation, and composing declared exit segments is exactly
  the mechanism that makes "a way out, at least through one other venue" real. Three
  consequences bind:
  - The composed exit chain is **part of the candidate's identity**. A round-trip figure
    is keyed per `(destination × stream × inbound path × exit chain)`; two different
    exit chains from one destination are **two different round-trip figures**, each
    reported, never blended into one.
  - Ties among exit chains follow the same tie rules as everything else: round-trip
    figures equal within the project tolerance are reported as a tie (002 FR-018),
    never resolved by enumeration order.
  - **002 FR-030 stands where no chain exists.** A destination from which no declared
    exit segments chain to a spendable endpoint has no round-trip figure, reports *exit
    cost unknown* naming the missing declaration, and is not comparison-ready. A
    one-way figure is never promoted to stand in for it.
- **FR-013**: A composed path MUST be presented as **its own kind of candidate, visibly
  distinct from a hand-declared route in every ranking, report and recommendation**
  (owner decision, 2026-08-22). The distinction is structural, not decorative: a
  composed candidate is always shown segment by segment, each segment naming the
  declared route it is — so which comparisons rest on composition, and on which
  declarations, is visible everywhere composed candidates appear.
- **FR-014**: Destinations remain **currency balances at venues**, exactly as feature
  002 scoped them (owner decision, 2026-08-22) — composition does not extend to
  instrument access in this feature. **Instrument access is a known future need,
  recorded as a stated deferral rather than a rejection**: the owner expects an
  instrument's declared venue to serve as a terminal node in a later feature. The seam
  is the destination, not the search — the later feature widens what counts as a
  destination (the instrument's declared venue and trading currency become a terminal
  node) while every composition rule in this spec applies unchanged. Nothing here may be
  shaped in a way that makes that widening an engine rewrite.

**Feasibility, state and regimes**

- **FR-015**: A composed candidate containing any segment closed, disrupted by status, or
  outside its availability window on the date MUST be excluded with the binding segment
  and constraint recorded, never silently omitted (002 FR-014).
- **FR-016**: Capacity pools MUST bind across a composed candidate exactly as they bind
  across routes: every leg naming a pool consumes the one shared monthly headroom,
  including two legs in different segments of the same candidate, and headroom already
  consumed this month by anything else applies (002 FR-015).
- **FR-017**: Every segment of a composed candidate MUST belong to the route set of the
  single regime in force on the contribution date. No candidate may connect by mixing
  route sets across a regime transition, and the transition date remains a stated
  assumption (002 FR-019/FR-020).

**Honesty and provenance**

- **FR-018**: Provenance MUST propagate across the whole composed candidate: an
  unverified value on any segment marks every figure derived from it on the candidate
  (002 FR-022), and staleness is evaluated per value by its declared kind threshold
  across all segments (002 FR-025/FR-028). A join between segments MUST NOT launder a
  mark.
- **FR-019**: Disruption probabilities MUST be reported per leg for every leg of every
  segment (002 FR-026), and the system MUST NOT synthesize a combined path-level
  disruption probability — combining per-leg probabilities requires an independence
  assumption nobody declared, which would be an invented number.
- **FR-020**: Cost attribution on a composed candidate MUST name both the component
  (conversion spread, percentage fee, fixed fee) and the **segment** it arose on, so a
  reader can see which segment dominates and trace it to its declaration.
- **FR-021**: Composition MUST NOT declare, fabricate or persist anything: no missing
  link is auto-declared, no composed candidate is written back to the registry, and an
  unreachable corridor is reported as unreachable by the coverage report (feature 003),
  not patched by this feature.

### Key Entities

- **Composed candidate** — an ordered chain of declared routes whose venues, currencies,
  directions and regime membership connect end to end, from a stream's arrival venue to a
  destination. Exists only at query time; never stored, never declared.
- **Segment** — one declared route playing a position in a composed candidate. Carries
  nothing of its own: every term is the declared route's, used verbatim.
- **Junction** — the meeting point of two adjacent segments: a venue plus the currency in
  which value arrives and departs. Either it matches exactly or the chain does not exist;
  a junction never converts, charges or waits on its own.
- **Direction** — inbound or exit, part of a route's declaration. Composition never
  mixes directions: what was observed one way says nothing about the other way.
- **Composed exit chain** — an ordered chain of declared exit routes from a destination
  back to a declared spendable endpoint, satisfying 002 FR-027 by owner decision. Part
  of the identity of the round trip it completes: one inbound path paired with two exit
  chains is two round-trip candidates.
- **Spendable endpoint** — where an exit chain may end: a venue-and-currency the owner
  has declared spendable. Owner data this spec references but does not define; the same
  declared list the coverage report (feature 003) reads.
- **Segment bound** — the declared maximum number of segments in a candidate. Data, owner-
  set, recorded with results; its absence is a load failure.
- **Candidate set** — every declared route and every composed candidate for a
  `(destination × stream)` on a date, all costed by the one costing function, all ranked
  by the one lexicographic rule. The set the recommendation is an index into.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a registry with declared segments and no end-to-end declaration, the
  composed candidate's arriving amount and cost percentages match independently
  hand-computed leg-by-leg arithmetic within the single project tolerance, with the
  arithmetic recorded beside the check.
- **SC-002**: The cost of every composed candidate and every declared route in a
  comparison is produced by the same costing function — asserted by construction, as 002
  SC-016 asserts it, not by comparing numbers that happen to agree.
- **SC-003**: A composed candidate and a declared route costing the same within the
  project tolerance are reported as a tie, and reversing the enumeration order of the
  registry changes nothing in any reported figure, ranking or tie — verified by running
  both orders.
- **SC-004**: In a registry whose route graph contains a cycle, zero candidates visit any
  venue twice — verified over the entire enumerated set, not sampled.
- **SC-005**: With a declared bound of `n`, no candidate has more than `n` segments,
  every connectable chain of at most `n` segments appears, and the bound is visible in
  the results. A registry with no declared bound fails at load naming file and field.
- **SC-006**: With one segment value left unverified, 100% of figures derived from it on
  every composed candidate carry the unverified mark; a value aged past its kind's
  threshold is reported stale on every derived figure.
- **SC-007**: Two legs in different segments of one composed candidate naming the same
  capacity pool consume shared headroom: the deployable amount equals the hand-computed
  joint figure, never the sum of two full limits.
- **SC-008**: A composed candidate with a closed segment is excluded with the binding
  segment and status recorded; its absence appears in the output rather than leaving
  silence.
- **SC-009**: No cost figure on any composed candidate is attributable to a destination
  alone; every one names its stream and its full path.
- **SC-010**: Adding one route declaration that connects a terminal venue onward makes
  new composed candidates appear, fully costed and ranked, with **zero** lines of source
  code changed.
- **SC-011**: Every leg of every segment reports its declared disruption probability, and
  no combined path-level disruption figure appears anywhere in the output.
- **SC-012**: Across a regime transition, candidates dated before it use only the first
  regime's route set and candidates after use only the second's; no candidate mixes the
  two — verified with a registry where only a mixed chain would connect.
- **SC-013**: No ranking contains two candidates with identical leg chains, verified with
  a registry that declares a route and its exact segment-wise equivalent.
- **SC-014**: Attribution on a composed candidate names the dominating segment and
  component, and every attributed figure traces to a specific declaration.
- **SC-015**: A destination whose exit is reachable only by chaining declared exit
  routes yields a round-trip figure matching hand-computed leg-by-leg arithmetic within
  the project tolerance; a destination from which no declared exit segments chain still
  reports *exit cost unknown* and is excluded from round-trip ranking — verified both
  ways.
- **SC-016**: No candidate mixes directions: in a registry where the only way to
  complete an inbound chain runs through a route declared exit (and the reverse), zero
  such candidates appear — verified over the entire enumerated set, not sampled.
- **SC-017**: Every composed candidate in every ranking, report and recommendation is
  visibly distinct from a hand-declared route and shown segment by segment, each segment
  naming its declared route — verified across every reported candidate, not sampled.
- **SC-018**: Two distinct composed exit chains from one destination produce two
  distinct round-trip figures, each keyed per its exit chain; when equal within the
  project tolerance they are reported as a tie under the same rule as everything else.

## Assumptions

- **A composed candidate is a query-time construction, not a declaration.** Nothing is
  written back to the registry, nothing persists between runs, and the registry remains
  the sole record of what is observed. What the registry cannot reach is the coverage
  report's finding (feature 003), which this feature reads conceptually but does not
  produce.
- **A cycle is a repeated venue.** The feature description fixes venues as the nodes, so
  the cycle rule follows: no candidate visits a venue twice, even in a different
  currency. An out-and-back corridor that is genuinely worth modelling can still be
  hand-declared as one route, where its terms are observations rather than search
  artifacts.
- **Duplicate suppression is by leg-chain identity.** A composed concatenation identical
  leg for leg to a declared route is the same real-world sequence of movements; it
  appears once, as the declared route. Anything differing in any leg or term is a
  distinct candidate.
- **The segment bound is owner policy, like a staleness threshold.** It is declared once
  as data, has no default, and is recorded with results so its effect on coverage is
  visible. This spec does not choose its value.
- **Feature 002's decisions are inherited wholesale, not reargued.** One costing
  function (FR-029), separately declared exit routes (FR-027) with *exit cost unknown*
  as the honest gap (FR-030), lexicographic ranking (FR-016) with cost-only ties
  (FR-018), per-kind staleness (FR-025/FR-028), capacity pools, per-leg disruption
  (FR-026), and per `(destination × stream × route)` keying (FR-008). Where composition
  put pressure on one of them — FR-027 above all — the question went to the owner, and
  the answers are recorded in **Clarifications resolved** below.
- **The segment bound applies to each chain separately.** An inbound candidate and a
  composed exit chain each obey the declared bound on their own; the bound is not a
  shared budget across the pair. A shared budget would make an inbound path's
  reachability depend on which exit chain it happens to be paired with — entangling two
  independently declared facts. If the owner wants a different discipline, that is a
  change to this assumption, not a quiet reinterpretation of it.
- **The declared spendable endpoints are owner data this spec references but does not
  define.** They are the same owner-declared list the coverage report (feature 003)
  reads. This feature depends on the concept — an exit chain must end somewhere the
  owner calls spendable — not on feature 003's artifacts.
- **Rates and premiums remain declared observations, not a live feed**, and everything
  002 assumed about them still holds: no provider, no network, no cache.
- **One owner, no authentication; no delivery surface.** Results are produced and
  asserted by the test suite, as in features 001 and 002.

## Clarifications resolved

All three answered by the owner on 2026-08-22; a fourth item is an underspecification
found by external review and fixed in the same pass.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Does a chain of declared exit segments satisfy 002 FR-027's "separately declared exit route", or must an end-to-end exit still be declared explicitly? | **Yes, it satisfies FR-027** — a composed round trip exists whenever declared exit segments chain to a spendable endpoint; FR-030 stands where none chains | FR-012, FR-022, SC-015, SC-018 |
| 2 | Is a composed path visibly distinct from a hand-declared route? | **Yes** — its own kind of candidate, shown segment by segment in every ranking, report and recommendation | FR-013, SC-017 |
| 3 | Does composition extend to instrument access, or do destinations remain currency balances at venues? | **Currency balances at venues, as in 002** — instrument access recorded as a stated deferral, not a rejection | FR-014, Out of scope |
| 4 | *(review finding)* "Directions connect" was used but never defined | Directions never mix: inbound chains inbound, exit chains exit; an exit chain runs destination → declared spendable endpoint | FR-022, SC-016 |

**The first decision has consequences worth stating on their own.** The owner's reasoning
— *everything must have at least one way out*, and composing declared exit segments is
exactly the mechanism that makes "a way out, at least through one other venue" real —
cuts the other way from 002's caution, and deliberately so: in 002 the danger was a
round-trip figure resting on an exit **nobody had observed** (reversing the inbound
route); here every link of the exit chain **is** an observation, so composing them
invents nothing. Two things follow and are now requirements: the composed exit chain is
part of the round trip's identity, so a round-trip figure is keyed per
`(destination × stream × inbound path × exit chain)` and two exit chains from one
destination are two figures, never a blend; and ties among exit chains obey the same
tolerance-tie rule as everything else (002 FR-018). FR-030 is unchanged — a destination
from which no declared exit segments chain still has no round-trip figure and says so.

**The third decision is a deferral, not a rejection, and the seam is named** — in the
style of 002's decision to leave `Provider` unbuilt while designing the signature it
will slot into. Instrument access is a known future need: a later feature makes an
instrument's declared venue (with its trading currency) a terminal node. The seam is
**what counts as a destination**, nothing else — every composition rule in this spec is
written over venues, currencies, directions and regimes, and applies unchanged when the
destination type widens. A design that would need composition itself rewritten to admit
instrument terminal nodes fails FR-014 as written.

**The review finding earned a requirement rather than a footnote.** "Directions connect"
did real work in User Story 1 while no FR defined it, and the resolved first decision
made the gap load-bearing: with composed exit chains real, an undefined boundary between
inbound and exit would have been the implementer's to draw. FR-022 draws it: a route's
direction is part of what was declared and observed, an observation of one direction
says nothing about the other, and mixing them would invent a corridor nobody observed.

## Standing required tests this feature must keep true

This feature closes no new row of `docs/REQUIRED_TESTS.md` by itself, but it presses
directly on rows that are already commitments:

| Row | Pressure composition puts on it |
|---|---|
| **B12** | No non-standard composite score drives the primary ordering — a routing search is exactly where a "path score" would sneak in. Composed candidates rank lexicographically or not at all. |
| **G6** | No comparison reports a one-way cost as round-trip — a composed round trip exists only through a chain of declared exit routes (FR-012); where none chains, *exit cost unknown* stands and no composed one-way figure is promoted. |
| **H1** | Data-only extensibility — SC-010 is this row's claim applied to composition: one declaration, new reach, zero engine edits. |

## Out of scope

Named explicitly so the plan does not drift: **any optimisation beyond
enumerate-and-rank** — no shortest-path algorithms, no admissible-heuristic pruning, no
cost estimation, no caching of partial costs across differing amounts; **new instruments**
of any kind; **live data** — no providers, no network, no cache; **the decision layer** —
composition produces candidates for the existing ranking, it does not choose strategies;
and **automatic declaration of missing links** — composition uses what is declared, and
the coverage report (feature 003) says what is not. **Instrument terminal nodes** are out
of scope in full by owner decision 3 — recorded as a stated deferral with its seam named
in FR-014 and in *Clarifications resolved*, not as a rejection: the composition rules are
written to survive that widening unchanged.

One boundary worth stating on its own, because routing invites it: **performance work is
not a licence to approximate.** If enumeration within the declared bound is slow, the
honest levers are the bound and the registry — both data, both owner-visible. A faster
answer produced by costing less than every candidate in full is not this feature done
efficiently; it is 002 FR-029 undone.
