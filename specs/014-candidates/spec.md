# Feature Specification: The candidate set, and what the loop discarded

**Feature Directory**: `specs/014-candidates`

**Feature Branch**: `spec/014-candidates`

**Created**: 2026-08-29

**Status**: Ready for planning — no clarifications open (see *Questions that were drafted and closed*)

**Input**: The engine can cost a tuple you hand it; it cannot find one. Enumerate the
candidate tuples a registry declares, evaluate every one of them through feature 010's
`evaluate`, and account honestly for the three places a candidate can land: evaluated,
dropped with a typed reason, or never a candidate at all. Required test **I1**.

---

## Why this feature exists

Feature 010 built `evaluate(tuple, …)` and `compare(tuples, …)`. **The caller supplies the
tuples.** Section I of `docs/REQUIRED_TESTS.md` — the decision layer, the half of the product
the owner actually asked for — is 0 of 7, and its first row is the foundation the other six
stand on:

> **I1** — Feasibility pruning drops infeasible candidates with a recorded reason, and the
> count of dropped candidates is reported.

`SIMULATOR_SPEC.md` §4.10.2 says the same thing in the product's own words: *"Infeasible
candidates are dropped with the reason recorded, because 'your preferred plan is impossible
in March' is itself an output."*

### The idea that makes this cheap

**Feature 010 already built the pruning rules.** They are its seventeen typed refusals —
`DeclarationMissing`, `SeamDoesNotChain`, `FundedFromAnotherStream`, `RouteInUnusable`,
`RouteInCapExceeded`, `WayOutCapExceeded`, `WayOutUnusable`, `NoExitRouteDeclared`,
`NoExitTermsDeclared`, `BelowMinimumTicket`, `BuysNoWholeUnit`, `InstrumentRefused`,
`CannotSpanHorizon`, `TwoFiguresNotOne`, `PlanDoesNotFitInstrument`,
`TaxCurrencyConversionUnavailable`, `InstrumentDemandsCash` — the union
`core/results/tuple.py::TupleRefused`, whose count is asserted rather than described in
`tests/unit/test_tuple_refusals.py`.

Enumeration plus those refusals **is** feasibility pruning. This feature adds no new
judgement about what is infeasible. It adds the loop, and the accounting.

That framing is what keeps a second opinion about feasibility from growing up beside the
first — two rules for one fact, and in this repository the duplicate is where the drift
happened every time. FR-006 makes it a requirement rather than an intention.

### Where the framing does not hold, stated before it is relied on

Three places, each measured rather than supposed. None of them is a reason to abandon the
framing; each is a reason the accounting has more than one column.

**1. A pair that yields no candidate is not a dropped candidate, and 010 has no refusal for
it.** A `Tuple` cannot be constructed without a `route_in`, so 010 was never asked whether a
way in exists — it was handed one. `NoExitRouteDeclared` covers the way *out*; there is no
`NoRouteInDeclared` and there should not be, because the fact is about an
`(instrument, stream)` pair rather than about a candidate. This is the largest population in
today's registry (the measurement below), and it belongs in its own column.

**2. `compose` refuses three questions that are not about a candidate either.** Feature
004's `CompositionRefused` fires for a segment bound below one, an exit enumeration with no
declared spendable endpoint, and a stream that already arrives where the purchase happens.
The third is the opposite of a gap — compose's own words: *"money that is already where it was
wanted"* — and collapsing it into *nothing connects* would report a registry gap that does not
exist. FR-014 keeps the two apart and FR-014a says where the discrimination has to come from,
because `CompositionRefused` does not carry it today.

**3. The drop count is not a property of the registry.** Refusals across the union turn on the
**amount** (a leg minimum or a monthly ceiling, in **both** directions — `WayOutUnusable`
carries the same `RouteUnusable` record as `RouteInUnusable`, whose docstring is *"a route that
cannot carry this amount on this date"*), on the **horizon** (which sets the projection window,
so a date-carrying refusal moves with it), and on **as_of** (every staleness verdict). Two runs
over one registry drop different candidates. **How many of the seventeen is deliberately not
stated here**: a census in prose beside a union the code owns is the shape that goes stale, and
SC-016 asserts the dependency directly instead — which is what the requirement actually needs.
A drop count reported without the inputs that produced it is a number more confident than its
inputs (FR-012).

There is a fourth limit, and it is the sharpest, but it does not bite at this feature's
level — see *The one place the framing genuinely breaks* below.

### The measurement

Every count below was read from `data/` on 2026-08-30 by loading the shipped registry through
`terezy.data.declarations.resolver.tuple_from_data_root` and running feature 004's `compose`
over it. It is reproducible from the repository and from nothing else.

> **Superseded 2026-08-31 by feature 016, which declared 24 real ОВДП issues.** The registry is
> now **33** instruments and **33** access declarations, so the cross product is **66** pairs,
> **33** candidates and **33** pairs yielding no candidate — and at the module's own question
> **27** evaluated against **6** dropped, four of the six being issues placed after that
> question's outlay date. Every count in this section is left as it was measured, because it is
> the record of what this feature was designed against; the live figures are derived rather
> than written, in `tests/worked_examples/test_candidate_accounting.py` and
> `tests/worked_examples/test_candidate_enumeration.py`. **What did not change is the finding**:
> the dollar stream still contributes nothing, for the same reason, and the ratio is now one
> half of a much larger set.

| Declared | Count | Which |
|---|---|---|
| instruments | **9** | `enumerated_out_of_order`, `enumerated_taxable_x`, `ovdp_enumerated_a`, `ovdp_enumerated_mirror`, `ovdp_synthetic_a`, `ovdp_synthetic_b` (fixed income); `inzhur_miltech`, `inzhur_reit`, `synthetic_fund_c` (funds) |
| access declarations | **9** | one per instrument; **every one** `bought_at = "inzhur"`, `proceeds_to = "inzhur"` |
| income streams | **2** | `salary_uah` (UAH, arrives at `monobank_uah`), `contract_usd` (USD, arrives at `deel`) |
| routes | **10** | 7 `inbound`, 3 `exit` |
| venues | **7** | `binance`, `coinbase`, `deel`, `fop`, `ibkr_usd`, `inzhur`, `monobank_uah` |
| spendable endpoints | **1** | `monobank_uah` in UAH |
| tax classes | **7** | three real, four synthetic fixtures |
| segment bound | **3** | `data/composition/owner-001.toml` |

The naive cross product of instrument and stream is **18** pairs. What the routes actually
connect, at the declared bound of 3, is not 18:

| Pair | inbound chains | exit chains | candidates |
|---|---|---|---|
| each of 9 instruments × `salary_uah` | **1** (`inzhur_direct`) | **1** (`inzhur_to_monobank`) | 1 each |
| each of 9 instruments × `contract_usd` | **0** | 1 | **0** |

**Nine candidates in total, all funded from the hryvnia salary.** The dollar stream — the term
that carries `SIMULATOR_SPEC.md` §4.2's whole finding, and the reason access cost is keyed by
`(destination × stream × route)` at all — contributes **nothing**, because the only declared
corridors that turn dollars into hryvnia (`fop_usd_to_monobank_uah`,
`binance_p2p_to_monobank`) are declared in the `exit` direction, and an inbound enumeration
cannot see them (004 research.md D10: the direction filter is in the index, so a walk cannot
emit a mixed chain).

**That is a finding about the registry, not about this feature, and it is exactly the finding
this feature exists to make visible.** Whether the remedy is a declared inbound corridor or a
different reading of direction is feature 003's coverage audit to say and the owner's to
decide; what must not happen is that the comparison quietly contains nine options and nothing
anywhere says the other nine were never asked.

### Does it explode?

Today the space is not large; it is nearly empty. But the growth is real and it is worth
stating as arithmetic a reader can check rather than as an adjective.

The candidate count is

```
Σ over (instrument, stream) of  |inbound chains| × |exit chains| × |plans supplied for that instrument|
```

and the route terms are **paths in a graph**, not entries in a list, because feature 004
composes them. In a graph of `V` venues where every ordered pair is joined by one route in one
currency, the number of simple chains of at most `B` segments between two venues is
`Σ(k=1..B) (V−2)!/(V−1−k)!`. With today's **7** venues:

| bound | chains per (start, target) | candidates at 9 instruments × 2 streams |
|---|---|---|
| 1 | 1 | 18 |
| 2 | 6 | 648 |
| **3** (declared) | **26** | **12 168** |
| 4 | 86 | 133 128 |

Today's registry yields 1 rather than 26 at the same bound because the graph is sparse and
three of ten routes point the other way. **A denser registry at the same declared bound is
four orders of magnitude larger, and it is quadratic in the chain count because both ways
count.** The bound is already declared data with no default (004 FR-006) and already travels
with every answer it shaped, so a corridor missed because of it is distinguishable from one
nobody declared. That is the existing control, and this feature does not weaken it.

**The honest name for this problem is a resource-constrained shortest-path problem** — edges
carry cost, latency, a monthly ceiling, a disruption probability and a counterparty — and in
general it is exponential in the number of paths. **The cure is not to enumerate them.** The
cure is label-correcting search that keeps only non-dominated labels at each node, which is
Pareto pruning, which is the algorithmic form of a rule the constitution already states:
*dominance → distribution → break-even → point estimate, in that order* (Principle I), as
`docs/DIRECTION.md` records.

**This feature builds enumeration, not search**, and says plainly what makes that honest:

- At the measured registry size the whole space is nine candidates. A search that prunes nine
  candidates is a search with more machinery than subject, and every pruning heuristic is a
  place a number more confident than its inputs gets in (004's module docstring makes the same
  argument, at length, about composition).
- Enumeration evaluates **every** candidate through one function, so nothing is ever excluded
  by an estimate. That property is what makes the later search checkable: a label-correcting
  implementation must produce the same non-dominated set this one produces by brute force, on
  a registry small enough to run both.
- **A reader's instinct at this point is "so cap it", and it is exactly backwards.** FR-019's
  ceiling is the one design point that turns on that inversion, and the argument for it lives
  in the requirement.

## The one place the framing genuinely breaks

**Monthly capacity is a shared rail resource, and a per-candidate refusal cannot express it.**
`core/routes/capacity.py` keys on `(capacity_pool, year, month)` and deliberately **not** on
the route: *"Two different routes both moving money through the owner's Monobank card consume
one limit."* Feature 010's `evaluate` checks one candidate's cap against `RampCost.ceiling` in
isolation. So two candidates that are each feasible alone can be jointly infeasible.

At this feature's level that does not bite, and the reason is worth stating rather than
assuming: **a candidate set is a set of alternatives, not a plan.** Exactly one of them is
executed, so no two of them consume the same pool. The moment a *strategy* holds several
tuples at once — `SIMULATOR_SPEC.md` §4.10.2's allocation simplex, which is I2 and I4 — joint
feasibility becomes a real constraint, and it is a constraint **between** candidates that no
member of 010's seventeen can carry.

So: at the tuple level, enumeration plus 010's refusals is the whole of feasibility. At the
allocation level it is not, and pruning has to run a second time under a rule this feature
does not build. FR-021 exists so that second pass does not have to redo the first.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the registry what the options are (Priority: P1)

The owner names an amount per stream, a horizon, an as-of date, a continuation assumption and
how each instrument is to be run. The tool answers with every option the declarations actually
offer — instrument, stream, way in, way out — each one evaluated end to end by the same
pipeline feature 010 built, ranked against the hurdle.

**Why this priority**: this is the sentence the product has never been able to say. Every
comparison so far was a comparison of tuples somebody typed out by hand.

**Independent Test**: run enumeration over the shipped registry and assert the candidate set
is exactly the nine measured above, in the specified order, with the same figures each would
have produced had it been handed to `compare` individually.

**Acceptance Scenarios**:

1. **Given** the shipped registry, **When** the candidate set is enumerated, **Then** it
   contains exactly the candidates the declarations connect — nine today — and each one's
   five terms name declared things.
2. **Given** the same registry and the same question asked twice, **When** the two sets are
   compared, **Then** they are equal element for element and in the same order.
3. **Given** the registry's declaration files loaded in a different order, **When** the set is
   enumerated, **Then** nothing about it changes — neither membership nor sequence.
4. **Given** an enumerated candidate, **When** it is evaluated, **Then** the outcome is
   identical to the outcome the same key produces when handed to `evaluate` directly. The loop
   is a loop, not a second pipeline.

---

### User Story 2 - Every discard is accounted for, in the right column (Priority: P1)

Nothing leaves the process silently, and the reader can tell the three exits apart: a
candidate that was evaluated, a candidate that was dropped by one of 010's seventeen, and a
pair that was never a candidate at all.

**Why this priority**: equal-highest with Story 1, and it is I1's actual content. A count of
dropped candidates that silently folds in combinations that were never real is a figure a
reader divides by and gets a meaningless answer.

**Independent Test**: over the shipped registry, assert the three populations by name and by
count — 9 candidates enumerated from 18 pairs, and 9 pairs yielding no candidate — and assert
the identity holds. Then plant one infeasibility of each kind and assert each moves exactly one
candidate from the first column to the second and none to the third.

**Acceptance Scenarios**:

1. **Given** an enumeration, **When** its report is read, **Then** the three populations are
   separately counted, and the identity *pairs considered = pairs enumerated + pairs
   yielding no candidate* and *candidates enumerated = evaluated + dropped* both hold.
2. **Given** a candidate dropped by `evaluate`, **When** the report is read, **Then** its key
   and its typed reason are both present — the whole record, not a summary of it.
3. **Given** an `(instrument, stream)` pair the routes do not connect, **When** the report is
   read, **Then** it appears in the no-candidate column with the typed reason *nothing
   connects*, and it is **not** in the dropped count.
4. **Given** a stream that already arrives where the instrument is bought, **When** the pair
   is reported, **Then** it carries compose's own reason verbatim — the money is already
   there — and is not reported as a corridor nobody declared.
5. **Given** any reported count, **When** it is read, **Then** the inputs that determine it
   are on the same record: the amounts, the horizon, the as-of date, the continuation
   assumption, the run plans, the segment bound and the regime.

---

### User Story 3 - The loop invents nothing the caller did not state (Priority: P1)

An instrument's run settings — which lots a disposal consumes, what a coupon does when it is
paid, when a fund is asked to exit, which point inside a stated range — change the answer and
have no default anywhere in the stack. Enumeration does not acquire the power to default them
by virtue of running in a loop.

**Why this priority**: this is where a candidate generator quietly becomes an opinion. A
default `exit_on` would silently pick one of a fund's declared ways out and drop the other
from the comparison, and both figures would look entirely reasonable.

**Independent Test**: enumerate with a plan missing for one reachable instrument and confirm
the **whole enumeration** refuses naming the instrument, rather than skipping it, defaulting
it, or reporting it as yielding no candidate.

**Acceptance Scenarios**:

1. **Given** a reachable instrument with no supplied run plan, **When** enumeration runs,
   **Then** it refuses as a whole, naming the instrument and the missing plan.
2. **Given** two run plans supplied for one fund — a requested buyback and a hold to
   termination — **When** enumeration runs, **Then** both appear as separate candidates with
   separate outcomes, keyed apart, never blended into one figure per fund.
3. **Given** one plan supplied for an instrument that declares more than one way out, **When**
   the set is reported, **Then** the report states how many plans were supplied per
   instrument, so a way out no plan reaches is visibly absent rather than silently so.
4. **Given** two streams in two currencies, **When** enumeration runs, **Then** each stream's
   amount is the one the caller supplied for that stream, and no exchange rate is applied
   anywhere.

---

### User Story 4 - A partial answer is refused, never returned (Priority: P1)

Where enumeration cannot produce the complete set for the question it was asked, it says so
and returns nothing rather than returning most of it.

**Why this priority**: Principle I. A shortlist computed over a silently partial candidate set
is a false optimum with an audit trail that looks impeccable, and every one of I2–I7 is built
on top of this set.

**Independent Test**: a battery — a candidate count above the declared ceiling, an undeclared
route id inside a supplied chain, a benchmark tuple absent from the set, a missing plan — and
assert each produces a typed whole-enumeration refusal naming the cause, with no candidate
list attached.

**Acceptance Scenarios**:

1. **Given** a registry whose candidate count exceeds the declared ceiling, **When**
   enumeration runs, **Then** it refuses naming the ceiling and the count reached, and returns
   **no** candidates. A truncated list is never produced.
2. **Given** a `CompositionRefused` for a reason that is about the question rather than about
   one pair — a segment bound below one, no declared spendable endpoint — **When**
   enumeration runs, **Then** the whole enumeration refuses, carrying compose's reason.
3. **Given** a benchmark that is not among the enumerated candidates, **When** the set is
   handed to `compare`, **Then** the benchmark is never appended beside the set to make it fit.

---

### User Story 5 - What comes out is enough to reason over later (Priority: P2)

Every evaluated candidate leaves this feature carrying what a later objective, a dominance
pass or a stability check needs, so none of them begins by enumerating and costing everything
again.

**Why this priority**: P2 because Stories 1–4 must exist first, but it is the requirement that
decides whether I2–I7 are cheap or are five re-implementations of this one.

**Independent Test**: a scan asserting that every field FR-020 names is reachable from the
candidate set without calling `evaluate` again, and that the candidate key is byte-identical
across two enumerations run under two different regimes.

**Acceptance Scenarios**:

1. **Given** the candidate set, **When** a later pass needs an amount, a rate, a span, a
   part-by-part breakdown, a segment count, a route status, a disruption probability, a
   provenance mark, a staleness verdict or a stated assumption, **Then** every one of them is
   already on the record.
2. **Given** two enumerations under two different declared regimes, **When** their candidates
   are compared, **Then** candidates present in both are equal by key, and a candidate present
   in only one is a **finding** about that regime rather than a missing row.

---

### Edge Cases

- **The registry connects nothing at all** — an empty candidate set is a legitimate answer and
  a real finding, distinct from a refusal. 004's `Enumeration`-versus-`CompositionRefused`
  distinction is inherited whole.
- **Every candidate is dropped** — the set is empty *after* evaluation, the drop tally
  accounts for all of it, and `compare` returns `BenchmarkUnavailable` if the benchmark was
  among them. Nothing anywhere reports "no options" without saying which of the two happened.
- **The benchmark itself is dropped** — 010's `BenchmarkUnavailable` handles it and this
  feature adds nothing: the other candidates' figures are carried unranked, which is the
  behaviour FR-011 of 010 already argues for.
- **One instrument, two supplied plans, one of which refuses** — one candidate evaluated and
  one dropped, both keyed to the same instrument. The instrument is not thereby "infeasible".
- **A pair that yields a candidate in one regime and none in another** — two enumerations, two sets,
  and the difference is the deciding belief the shortlist will eventually have to name.
- **An instrument whose proceeds land somewhere the owner already spends** — the way out is the
  identity exit, it costs a recorded zero, and the candidate is evaluated like any other
  (FR-004a). Unreachable in the shipped registry and live the day an instrument's `proceeds_to`
  is `monobank_uah`; stated because the obvious reading — *no exit chain, therefore no
  candidate* — is the false verdict.
- **An instrument declared with no access entry** — the loader already refuses at load
  (`tuple_from_data_root`), so this never reaches enumeration. Stated because a reader expects
  it to be a candidate-level refusal and it is not.
- **A tuple naming an instrument nobody declared** — never constructed, never counted, in no
  column. It was not a candidate; it was a typo.
- **A candidate whose way out carries money past the horizon** — evaluated, not refused: 010's
  `span` runs to the last arrival and may exceed `horizon.end`. See *what this makes reachable*
  for why that is recorded rather than changed here.

## Requirements *(mandatory)*

### Functional Requirements

**Enumeration**

- **FR-001**: The system MUST enumerate the **candidate set** for one stated question: a
  registry, an amount **per income stream**, one horizon, an as-of date, a continuation
  assumption, a sequence of run plans per instrument, the declared segment bound, and one
  named regime. It MUST return the complete set or a typed refusal, and nothing in between.
- **FR-001a**: Evaluating and comparing the set **is in scope**, and the boundary is worth
  stating because FR-022 and SC-015 depend on it: this feature enumerates the set and hands it
  to 010's `compare` with a caller-named benchmark. It adds no ranking rule, no tie rule and no
  benchmark rule — all three are 010's and stay there. What it adds around `compare` is the
  accounting of FR-008, which `compare` has no place to put: `Comparison` reports the tuples it
  was handed and knows nothing of the pairs that never became tuples.
  ⚙ **`compare`'s own loop is the only evaluation**, and that has to be said because the
  obvious reading is that this feature evaluates and then compares. `compare` calls `evaluate`
  itself over every member including the benchmark, so a second call here would produce two
  outcomes per candidate and two dropped sets, and FR-008's column could then disagree with
  `Comparison.refused` with nothing to say which is authoritative. FR-008's first two
  populations **are** the ones `compare` already returns — the outcomes it scored, and the
  `RefusedTuple` records it collected — read out and counted, in both the ranked case and
  `BenchmarkUnavailable`. FR-007 is satisfied by that loop, not beside it.
  ⚙ **A gap, recorded rather than worked around:** `compare` takes **one** `amount` for the
  whole set, while FR-001 and FR-005 take one **per stream**. Today's set is single-stream, so
  the two agree and SC-015 is constructible; a two-stream set cannot be handed to `compare` at
  all — and none can be built from the shipped registry, where `contract_usd` connects to
  nothing inbound, so no question reaches the disagreement. Widening the signature is a change
  to 010, made and reviewed there on the rule FR-014a states, and a `[[future]]` entry — not a
  per-stream loop here, which would produce one ranking per stream and none of the set.
- **FR-002**: Every candidate's five terms MUST name declared things, and the two route terms
  MUST be read off candidates feature 004's `compose` emitted. Enumeration MUST NOT construct
  a chain, extend one, or decide that two routes join. Every rule about what connects stays in
  004.
  **One carve-out, and it is about the absence of a chain rather than about what connects:** the
  identity exit of FR-004a is not something `compose` can emit — `exit_chain_of` states in as
  many words that it never returns `EXIT_BY_IDENTITY`, and `_chains` emits no zero-segment chain
  — so enumeration constructs it, from the owner's declared spendable list and nothing else. No
  route is joined to any other in doing so.
- **FR-003**: Enumeration MUST NOT invent a run assumption. Run plans arrive **keyed by
  instrument id**, and a reachable instrument with no supplied plan MUST refuse the whole
  enumeration (FR-018). There is no default anywhere in the stack for a consumption method, a
  coupon policy, a liquidity mode, a buyback availability, an exit date, a chosen point inside
  a stated range, or an exchange-rate assumption, and running in a loop does not create one.
- **FR-004**: The way-out term MUST be **named, never defaulted**. Enumeration MUST NOT emit
  `FROM_THE_DECLARATION`: that sentinel is an *instruction to go and read `partner_route`*, so
  a set containing it holds a journey whose identity is settled after the fact, and a reader
  cannot tell which chain was costed. The prohibition is on the **default**, not on a way out
  that happens to have no segments.
- **FR-004a**: Where an instrument's `proceeds_to` is itself a declared spendable endpoint, the
  way out MUST be the **identity exit** and the candidate MUST exist. That is 003's FR-002
  (owner decision, 2026-08-23) — a destination that is already spendable satisfies its own exit
  — and it is not this feature's to re-decide. Emitting nothing there would put the pair in
  FR-013's *no candidate* column and report a corridor nobody declared, which is the false
  verdict FR-014 exists to prevent.
  ⚙ **This needs no change to 010, and the check was made at source.** `EXIT_BY_IDENTITY` is
  already a member of `ExitChain` and therefore already a valid `ExitChoice`; `_chosen_way_out`
  returns a non-sentinel choice unexamined; and `_identity_way_out` exists precisely to verify a
  caller's assertion of it against the declared endpoints — its own docstring distinguishes the
  claim *"derived from the declarations"* from the claim *"asserted by a caller"*, and this
  feature is that caller. What has no route to it is **`compose`** — which is why FR-002 needs
  its carve-out, and why FR-004's prohibition had to be narrowed to the default: a rule reading
  *"the way out is always something `compose` emitted"* forbids the one way out `compose` cannot
  produce.
- **FR-005**: The amount MUST be supplied **per stream, in that stream's currency**, and
  enumeration MUST convert nothing. Converting one amount into the other would need a rate that
  values one currency in another **for a return**, and neither declared rate is one: a channel
  rate is a transaction price, and feature 011's official rate is a legal reference for what an
  income was worth on a date. Reusing either to score a return conflates a role rather than
  filling this one (Principle VI), which is what `RateNotComparable` says at length.
  ⚙ **The consequence is stated rather than smoothed over.** A cross-currency candidate — a
  dollar-funded purchase of a hryvnia instrument — is enumerated, evaluated and reported, and
  it is **not ranked**: `RateNotComparable` names exactly that case as the one reachable today,
  so the rate is absent and 010 places the outcome in `not_comparable`. So "compare by rate
  instead" is the answer for same-currency candidates and is **not** an answer for the
  cross-currency one, which is the case this requirement is most about. That is 010's existing
  honest behaviour rather than a gap this feature opens, and it is moot in the shipped
  registry, where `contract_usd` yields no candidates at all.

**Pruning is 010's, and nothing else**

- **FR-006**: A candidate MUST be dropped **only** for a member of feature 010's
  `TupleRefused` union. This feature MUST NOT contain a feasibility rule of its own, a
  pre-screen, a cheap filter, or an early exit that skips evaluation. A new reason to consider
  a candidate infeasible is a **change to 010's union**, made and reviewed there, with 010's
  exhaustiveness test and every match site moving with it.
- **FR-007**: Every enumerated candidate MUST be evaluated by the same call feature 010's
  FR-001 defines, with no candidate excluded by an estimate, a bound, a cost, or an ordering.
  Pruning by score is what turns a search into a composite ranking (required test **B12**),
  and 004's composition module refuses the same thing for the same reason.

**The accounting**

- **FR-008**: The result MUST separate and separately count **three** populations: candidates
  **evaluated** (feature 010 then places each as ranked or not-comparable), candidates
  **dropped** with a typed reason, and `(instrument, stream)` pairs that **yielded no
  candidate**. The third is a column of pairs each carrying a **typed reason**, not a bare
  list: its two members today are *nothing connects* and *nothing needs to connect*, and the
  owner's remedy for them is opposite (FR-013, FR-014).
- **FR-009**: The accounting MUST be an asserted identity rather than a claim in prose: *pairs
  considered = pairs enumerated + pairs yielding no candidate*, and *candidates enumerated =
  evaluated + dropped*. Every pair in the second term carries one of FR-013's or FR-014's
  reasons, so the identity closes over a partition rather than over a residue. A check cannot
  go stale silently; a sentence can.
- **FR-010**: Every dropped candidate MUST keep its **key and its typed reason** — the record
  feature 010 already defines as `RefusedTuple`, not a new one and not a summary of one. The
  core MUST NOT summarise, elide, sample or truncate the dropped set: the core formats nothing
  (Principle III), and choosing what a reader sees is the presenting layer's job.
- **FR-011**: A **tally per reason** MUST be available, derived by one named function from the
  retained records and **never stored as a second field beside them**. Each group MUST name
  the distinct declarations its members implicate — the instrument, the route, the missing
  declaration — so that the remedy is readable from the tally alone without reading hundreds
  of individual records.
- **FR-012**: Every reported count MUST be carried together with **the whole question that
  produced it** — the amounts, the horizon, the as-of date, the continuation assumption, the
  supplied plans, the segment bound and the regime id — because the question is what determines
  it. Refusals in 010's union turn on the amount, on the horizon and on the as-of date, so a
  bare count is a figure more confident than its inputs. The requirement is stated over the
  *whole* question rather than over an enumerated subset of the seventeen: which members are
  amount-sensitive is a fact the union owns and may change, and a list here would be a second
  copy of it going quietly out of step. SC-016 asserts the dependency; SC-017 asserts the
  question travels whole.

**What is not a candidate at all**

- **FR-013**: An `(instrument, stream)` pair for which the inbound or the exit enumeration
  returns an `Enumeration` with **no candidates** MUST be reported in the no-candidate column
  with the reason **nothing connects**, and MUST NOT appear in the dropped count. It is the
  absence of an option, not the rejection of one, and the owner's remedy is a declaration
  rather than a different amount.
- **FR-014**: An `(instrument, stream)` pair for which `compose` **refuses** because the stream
  already arrives where the purchase happens MUST be reported in the same column with the
  reason **nothing needs to connect**, carrying compose's own words verbatim, and MUST be
  **distinguishable from FR-013's members without reading prose**. It MUST NOT be counted
  toward, or reported as, a gap in the registry: nothing is missing, the money is already
  there, and the two remedies are opposite. What is missing is the *candidate*, and that is the
  `zero-hop-way-in` gap recorded under *Questions that were drafted and closed* — a pair
  standing in this column with this reason is that gap made visible, which is the honest
  interim answer and not a permanent one.
- **FR-014a**: The discrimination FR-014 and FR-018 rest on MUST come from the refusal
  **record**, never from matching its `reason` text. ⚙ `CompositionRefused` carries one
  `reason: str` for all three of its cases today, so **widening it to say which of the three
  fired is required work in feature 004**, on the same rule this specification applies to 010:
  a distinction the caller must act on belongs in the type, in the module that owns it, not in
  a local re-check here. Re-checking `bound < 1` and `not spendable` before calling `compose`
  is explicitly refused — it duplicates two of compose's own guards, against FR-002.
- **FR-015**: A tuple naming an instrument, stream or route the registry does not declare MUST
  never be constructed and MUST NOT be counted in any of the three populations.

**Order and determinism**

- **FR-016**: The candidate set MUST be **totally ordered** by a function of the declarations
  and the caller's inputs alone: instrument id, then stream id, then the way in's
  `candidate_id`, then the way out's segment ids, then the run plan's position in the sequence
  the caller supplied for that instrument. Loading the same declarations in a different file
  order MUST change neither membership nor sequence (004 FR-008 and SC-003, applied one layer
  up).
- **FR-017**: A run plan's order MUST be **its position in the caller's sequence**, recorded on
  the candidate. A plan record holds a date, a chosen point inside a range and an exchange-rate
  assumption; there is no ordering over those a reader could reproduce, and inventing one
  would make the sequence depend on a comparison nobody asked for.

**Refusing the whole enumeration**

- **FR-018**: Enumeration MUST refuse **as a whole**, returning no candidates, when: a
  reachable instrument has no supplied run plan; the declared candidate ceiling is exceeded; a
  supplied way in or way out names a route the registry does not declare; or `compose` refuses
  for one of the two reasons that are about the **question** rather than about one pair — a
  segment bound admitting nothing, and an exit enumeration with no declared spendable endpoint.
  Which reason fired is read off the record per FR-014a. Each refusal MUST name what did not
  stand up, in the output's own words.
- **FR-019**: A **candidate ceiling** MUST be declared data with **no default**, on the
  precedent of 004's segment bound (FR-006) and 002's staleness threshold (FR-028): a
  forgotten line must never read as a chosen policy. Exceeding it MUST **refuse**, naming the
  ceiling and the count reached, and MUST NOT truncate. The ceiling exists to say *the
  enumeration primitive has stopped being the right one for this registry*, which is a finding
  the owner acts on; a silent cap would hide exactly that.

**What a candidate carries out**

- **FR-020**: Every evaluated candidate MUST leave this feature carrying, without any later
  recomputation: its key; the amount that reaches the spendable endpoint; the comparable rate
  or the typed statement of why there is none; the span, from which latency is read; the six
  part contributions; the segment count of both ways; the route status and the disruption
  probability; the union of provenance and the merged staleness verdict; the stated assumptions
  the outcome rests on; and the declared risk class. **Every one of these is already on 010's
  `TupleOutcome` or is derivable from the key it carries** — all but one are fields; the segment
  count of the way in is read off `key.route_in` through `segments_of` and of the way out off
  `key.route_out` through `exit_segments_of`, which is part of why the key must travel too. The
  requirement is that enumeration adds no lossy projection over the record and hands the whole
  of it forward. A candidate set reduced to *feasible / not feasible* makes every one of I2–I7
  begin by enumerating and costing everything again.
- **FR-021**: The candidate set MUST be the **complete** set for its question or a refusal
  (FR-018). Dominance, an objective, a stability check or an indifference band computed over a
  silently partial set is a false optimum, which Principle I names as the project's reason for
  existing.
- **FR-022**: Where the set is compared, the benchmark MUST be **one of its members** and MUST
  appear exactly once. It MUST NOT be appended beside a set that does not contain it: feature
  010's FR-012 forbids a benchmark from a privileged side channel, and appending one here would
  reintroduce it one layer up.
- **FR-023**: A candidate set MUST be enumerated for **one** named regime, and the regime id
  MUST travel with the set (004 FR-017). The candidate **key** MUST be regime-independent — the
  five declared terms and nothing else — so that two sets enumerated under two regimes are
  comparable by key equality. A candidate present in one set and absent from the other is a
  finding about that regime, and it is what a deciding belief will eventually be read off.

**Provenance and honesty**

- **FR-024**: The enumeration MUST carry the union of the provenance marks and the merged
  staleness verdict of every declaration it read to build the set, so a candidate set never
  looks cleaner than the registry behind it. ⚙ **A known gap, recorded rather than closed:**
  010's refusal records carry a `reason` string and no provenance, so *which* unverified value
  caused a particular drop is not traceable from the drop itself. Closing it is a change to
  010's union under FR-006 and is a `[[future]]` entry, not a local workaround here.
- **FR-025**: The result MUST state, per instrument, **how many run plans were supplied**, so
  that a declared way out no supplied plan reaches is visibly absent rather than silently so.
  Enumerating an instrument's declared ways out is not possible without dates and points nobody
  declared (FR-003), so this states the scope rather than filling it — feature 010's
  `accounts_for` / `excludes` discipline applied to the candidate set.

### Key Entities

- **Candidate** — one tuple key the registry declares: an instrument, a stream, a way in, a
  run plan choosing a way out of the instrument, and a way out of the venue. Feature 010's
  `Tuple`, unchanged; this feature adds no term and no field to it.
- **Candidate set** — the ordered, complete set of candidates for one question, with the
  regime, the bound, the amounts, the horizon, the as-of date and the continuation assumption
  that shaped it. Empty is a legitimate value meaning *the declarations connect nothing*.
- **Pair yielding no candidate** — an `(instrument, stream)` pair with no way in or no way
  out, carrying a **typed** reason: *nothing connects* (FR-013) or *nothing needs to connect*
  (FR-014). A separate population from a dropped candidate, never counted with one, and never
  reported as a single undifferentiated total — the two reasons call for opposite actions.
- **Dropped candidate** — 010's `RefusedTuple`: a key and one of the seventeen typed reasons.
- **Drop tally** — a derived per-reason grouping over the dropped candidates, naming the
  declarations implicated. Derived on demand, never a stored second copy.
- **Enumeration refusal** — the whole question did not stand up: a missing plan, an exceeded
  ceiling, an undeclared route, a `CompositionRefused` about the question. Returned *instead
  of* a set, on the precedent of `CompositionRefused` and `BenchmarkUnavailable`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Enumeration over the shipped registry produces exactly **9** candidates, all
  funded from `salary_uah`, and reports exactly **9** `(instrument, stream)` pairs yielding no
  candidate — all of them for FR-013's reason, *nothing connects* —
  all of them `contract_usd`. The numbers are asserted against the declarations, not
  hard-coded: the test derives them from the registry it loads.
- **SC-002**: Each of the 9 candidates, evaluated through the loop, produces an outcome
  identical field for field to the outcome the same key produces when passed to `evaluate`
  directly. The loop is proven to be a loop.
- **SC-003**: The same question asked twice returns an equal set in an equal order; and a
  registry loaded from files renamed so that they sort differently returns the same set in the
  same order. Two runs, one assertion each, and the second is the one that catches an ordering
  that depends on the filesystem.
- **SC-004**: The accounting identity holds across a generated battery of registries and
  questions (property-based), for every combination of populated and empty populations —
  including all-dropped, all-yielding-nothing, and nothing declared at all.
- **SC-005**: A deliberate battery plants **each** of feature 010's seventeen refusals in turn
  and asserts that each moves exactly one candidate from evaluated to dropped, changes the
  no-candidate count by zero, and appears in the tally under its own name. A refusal that cannot
  be reached from a declared registry is recorded as such with the reason, not skipped
  silently.
- **SC-006**: A scan asserts that no module in this feature constructs, matches on, or raises
  a feasibility verdict of its own: every drop in the output is a value produced by 010's
  `evaluate`. FR-006 stated as a check rather than a rule to remember.
- **SC-007**: The drop tally recomputed from the retained records equals the tally reported, in
  every generated case. There is one place the grouping lives and it is proven to be one.
- **SC-008**: An `(instrument, stream)` pair whose stream already arrives at the buying venue
  is reported with compose's own reason verbatim, and a string comparison asserts the text was
  not rewritten.
- **SC-009**: A candidate count one above the declared ceiling produces a typed refusal naming
  the ceiling and the count, carrying **zero** candidates; and a scan finds no code path that
  returns a candidate set shorter than the set the question implies.
- **SC-010**: With a run plan missing for one reachable instrument, enumeration refuses as a
  whole and names the instrument. Across a battery covering every plan field, no case produces
  a defaulted plan, a skipped instrument, or an instrument reported as yielding no candidate.
- **SC-011**: One fund with two supplied plans yields two candidates with two outcomes and two
  distinct keys, and no figure anywhere in the result is attributable to the fund alone —
  010's FR-010 keying, verified through the loop. Supplying the same two plans in the opposite
  order permutes those two candidates and nothing else, which is FR-017 asserted rather than
  implied by SC-003's stability.
- **SC-012**: Everything FR-020 names is reachable from an evaluated candidate without a second
  call to `evaluate` — the fields by a walk over the record rather than by sampling, and the
  segment counts through `segments_of` and `exit_segments_of` over the carried key.
- **SC-013**: Two enumerations under two declared regimes produce candidate keys that compare
  equal where the candidate exists in both, and the symmetric difference is reported as a
  per-regime finding rather than as an absence.
- **SC-014**: A candidate set carrying an unverified declared value reports the unverified mark
  on the set, and a value aged past its kind's threshold reports stale — verified across the
  whole result rather than sampled, per 010's SC-007.
- **SC-015**: Enumerating the shipped registry and handing the result to `compare` produces a
  `Comparison` whose benchmark index points at a member of the enumerated set, and a scan finds
  no path that appends a benchmark to a set not containing it.
- **SC-016**: The same registry enumerated at two different amounts produces two different drop
  tallies, and at two different horizons likewise — FR-012's dependency asserted directly
  rather than counted in prose. A registry and pair of amounts for which the tallies coincide
  is not a failure; the criterion is that a case exists and is pinned, because that is what
  makes the dependency a fact rather than a claim about the union's membership.
- **SC-017**: Every reported count is accompanied by the whole question — amounts, horizon,
  as-of, continuation, plans, bound, regime — verified by a walk over the result rather than
  sampled, so a count can never be read without what determines it.
- **SC-018**: An instrument whose `proceeds_to` is a declared spendable endpoint yields a
  candidate whose way out is the identity exit, it is **evaluated** rather than landing in the
  no-candidate column, and its way-out cost is a recorded zero rather than an absent term
  (FR-004a). Asserted on a fixture registry, because the shipped one reaches it nowhere: every
  `proceeds_to` is `inzhur` and the only spendable endpoint is `monobank_uah`.
- **SC-019**: A scan asserts that enumeration constructs no route chain: every `route_in` in a
  produced set is object-identical to something `compose` emitted, and every non-identity
  `route_out` equals `exit_chain_of(c)` for a candidate `c` that `compose` emitted — equality
  rather than identity because that function builds a fresh record, and `compose` emits no
  `ExitChain` for it to be identical to. The identity exit is the single permitted construction
  (FR-002's carve-out, FR-004a), and `FROM_THE_DECLARATION` appears in no produced set at all
  (FR-004).
- **SC-020**: A question naming two streams in two currencies carries an amount for each, in
  each stream's own currency, and a scan finds no exchange rate, channel rate or currency
  conversion anywhere in this feature (FR-005). An amount in a currency its stream does not
  deliver **raises**, which is 010's existing behaviour for a caller's construction error: this
  feature neither catches it nor turns it into a refusal, because it is a mistake in the
  question rather than a fact about the money.
- **SC-021**: The result states the number of run plans supplied per instrument (FR-025), and a
  tuple naming an instrument, stream or route the registry does not declare appears in none of
  the three populations and in no count (FR-015).
- **SC-022**: A scan asserts that no module in this feature branches on a refusal's `reason`
  text: which of `CompositionRefused`'s cases fired is read from the record, and the only use
  made of that string is carrying it through verbatim (SC-008). FR-014a stated as a check
  rather than a rule to remember.

## Assumptions

- **Feature 010's `evaluate` and `compare` are used as they are.** This feature adds a caller,
  not a variant. If a candidate cannot be evaluated by the existing call, that is a finding
  about 010 recorded under FR-006, not a reason for a second evaluation path here.
- **Run plans come from the caller.** Where they eventually come from — a declared objective
  set under `data/objectives/`, a sweep, the owner typing them — is a later question. Today
  they are an argument, as `continuation` and `horizon` already are.
- **The shipped registry is small and largely synthetic.** Only the two Inzhur funds are real:
  every fixed-income declaration carries `is_synthetic = true`, and `synthetic_fund_c` says so
  in its own name. Both stream amounts are `0.0` because the owner has not stated his figures
  (`data/streams/owner-001.toml`). The counts above are counts of *declarations*, which is what
  this feature enumerates; none of them is a claim about money.
- **No legal, tax or fee value is introduced.** Nothing in enumeration needs one. If a
  requirement here ever seems to want one, the scope has slipped.
- **One owner, no delivery surface.** Results are produced and asserted by the test suite, as
  in every feature so far.
- **The dollar stream's zero candidates are the registry's finding, not this feature's bug.**
  This feature reports it. Whether an inbound USD→UAH corridor should be declared is feature
  003's audit to surface and the owner's to answer.

## What this makes reachable, and deliberately does not build

Each item below is reachable **because of** a requirement above, and is named here so the next
feature does not re-derive the argument.

**The non-dominated set** rests on **FR-020** (every candidate carries its dimensions) and
**FR-021** (the set is complete or refused). Once every candidate is costed, the non-dominated
set is computable — and `docs/DIRECTION.md` records that Pareto pruning is the algorithmic
form of a rule already written down rather than a technique to bolt on. **The reason it is not
built here is the measured size of the set, and nothing else.** The dimensions are not the
blocker and it matters that this is said plainly — a fee, a latency, a disruption probability,
provenance and staleness are all already separate terms on the outcome, as the next three
paragraphs use, and FR-020 carries them out. A reader who takes "wait for the objectives" from
this section will defer work that is not blocked.

**Dominance versus weights, and the line between them.** A rule belongs in a *partial order*
when it needs no calibration, and in a *score* only when a weight can be justified. That line
decides three of the four things a reader will want to add. **The fourth — treating the horizon
as a budget — is not decided by this line at all**: it is a *feasibility* question rather than a
dominance-or-weight one, which is why it has a section of its own below.

- **"Fewer steps is better" does not go in the objective.** Each hop already carries a fee, a
  latency and a disruption probability, and all three are separately modelled dimensions on the
  outcome. Scoring step count as well **counts the same thing twice**, and it would penalise a
  three-hop route that is cheaper and faster than a two-hop one. What step count *does* capture
  that the three do not is **model risk**: a five-segment path rests on five sets of
  declarations, each of which may be unverified or stale. That is confidence, not cost,
  and this project's first principle is about confidence. So step count belongs in the
  provenance and staleness dimension, or as a tie-breaker — never as a weighted penalty. It is
  on the record under FR-020 for exactly that use.
- **"Sooner to the same result is better" is the strongest of the four, and it is a dominance
  rule rather than a weight.** Two candidates reaching the same endpoint with the same amount,
  one sooner: the sooner dominates, and no calibration is needed to say so. That is precisely
  why the constitution puts dominance before point estimates, and FR-020 carries `span` so the
  rule is computable without re-evaluating anything.
- **Irreversibility is not a new dimension.** A fund whose only guaranteed exit is its
  termination is not expensive and not slow — it is optionality lost — but the facts that say
  so are already three declared, carried values: whether a way out is owed or discretionary
  (010's `NoExitTermsDeclared` versus a declared exit, and 006's finding that the same-day
  buyback is revocable company practice), the settlement latency inside `span`, and
  `RouteStanding.disruption_probability`. Collapsing them into one optionality score would be
  the non-standard composite ordering required test **B12** exists to forbid. Where it earns a
  place is as a dominance rule on the same criterion as above: same endpoint, same amount, same
  date, one guaranteed and one discretionary — the guaranteed dominates.

**A bound from the benchmark, and it is free.** The hurdle is always scored and is a member of
the set (FR-022), so any partial path whose best possible completion cannot beat it can be cut
without being completed. That is branch-and-bound with a bound the system already computes,
and it is what makes the search version of this feature cheap when enumeration stops being the
right primitive (FR-019's ceiling is the signal). It is not built here for the same reason the
non-dominated set is not.

**The horizon as a hard budget, not a cost.** A path whose total latency exceeds the horizon is
infeasible rather than expensive, and that kills whole branches early. **010 does not already
have this**, and the check was made rather than assumed:

- `CannotSpanHorizon` names an **instrument** term at both of the two sites that construct it:
  `"instrument.maturity_date"` for a bond and `"instrument.terminates_on"` for a fund, each
  hard-coded. `binding_term` is a bare `str`, so nothing in the *type* forbids a route id; what
  is true and sufficient is that **neither construction site produces one, and the record
  carries no route id to name**. So a way in whose latency pushes the purchase past
  `horizon.end` reaches that refusal with the binding term pointing at the instrument rather
  than at the corridor that was actually slow.
- On the way out there is no check at all: `span.end` is the last arrival, and an exit chain's
  latency may carry arrivals past `horizon.end` with nothing refusing. **This one is unrefused,
  not mis-measured**: `implied_rate` is an internal rate of return over `span`, so a late
  arrival is *priced*, by the owner decision that put waiting inside the span. What breaks is
  comparability against candidates measured over the horizon, and **visibility** — the
  assumption list fires only on the *undershoot*, an instrument terminating before the horizon,
  so an outcome that ran past the horizon says nothing at all on its face. Whether the remedy is
  a refusal, a stated assumption, or neither is a modelling question, which is why the
  `[[future]]` entry hedges it and this section now does too.

The first is a change to 010's union under FR-006; the second may or may not be. Both are what
a latency-budget pruning rule
would rest on. Recorded as a `[[future]]` entry rather than fixed here, because fixing them
changes figures 010's goldens pin and belongs in a change reviewed against 010's own tests.

**Time-expanded nodes, named and not built.** Monthly caps reset and latencies are non-zero, so
the same edge costs differently in different months; the standard move is to expand a node into
`(venue, time bucket)`, which turns a time-dependent problem into a static one and stops the
monthly cap being a special case. What would force it is **010's FR-018 deferral** — the moment
an acquisition becomes a dated *series* of ramp-and-purchase events rather than one purchase,
the monthly cap stops being a per-candidate check and becomes a per-`(capacity_pool, month)`
resource, which is already the shape `core/routes/capacity.py` keys on. Not before.

**A candidate is a vector over scenarios, not one label.** The constitution requires scoring
under *every* scenario, and I7 requires *"sometimes best"* and *"never bad"* computed
separately — so dominance runs **inside** a scenario first and **across** scenarios second, and
a candidate that dominates in one and loses in another is a finding rather than a winner.
**FR-023** is what makes that buildable without redoing enumeration: the candidate key is the
five declared terms and carries no regime, so two per-regime sets align by key equality, and a
candidate that exists in only one regime is the deciding belief in its rawest form.

**I4's naive baseline** is half-built and the other half is named: 010's `Comparison.benchmark`
already scores the hurdle always and shows it always, and `BenchmarkUnavailable` carries the
others unranked when it cannot — what I4 still needs is the *other* baseline, `50/50 OVDP +
VWCE`, which is an **allocation over candidates** rather than a candidate, and 010 put
allocations explicitly out of scope. So I4 needs a scoreable allocation and a declared baseline
set; this feature gives it the candidate set the allocation is over.

**Joint feasibility across a strategy's members** — the shared capacity pool of *The one place
the framing genuinely breaks* — is I2/I4's, and FR-020 exists so that second pruning pass reads
this one's output rather than repeating it.

## Questions that were drafted and closed

Recorded rather than deleted: each looked open, and the reasoning that made it look open is the
reasoning someone will repeat.

**Should the candidate ceiling refuse, or should there be no ceiling at all?** Drafted as a
clarification for the owner, closed against precedent — FR-019 carries the shape and its
citations and they are not repeated here. What the owner was *not* being asked, and the reason
this closed without him: whether a partial candidate set may ever be returned. Principle I
answers that, so the only open question was the ceiling's *number*, which is a line in a data
file rather than a decision about the design.

**What is "the same amount" across two streams in two currencies?** Closed by refusing the
question rather than answering it. Converting one into the other needs a rate that values one
currency in another for a **return**, and no landed feature declares one: a channel rate never
strikes anything but a leg, and feature 011's official rate is a legal reference, so reaching
for it here would conflate a role rather than fill this one. FR-005 takes an amount per stream,
invents nothing, and leaves the
cross-stream comparison to the rate — which is what `implied_rate` is for and what 010's
`RateNotComparable` already says about the amount.

**Should enumeration produce a candidate with no way in, where the money already arrives at the
buying venue?** Closed as a recorded gap rather than a clarification. 010's `Tuple` requires a
`route_in`, so a zero-hop way in is not representable, and the shipped registry never reaches
the case: no instrument is bought at `monobank_uah` or `deel`. FR-014 carries compose's own
reason so the pair is never mistaken for an undeclared corridor, and making the zero-hop tuple
representable is a `[[future]]` entry. **The mirror of it on the way out is solved** — 003's
FR-002 and `EXIT_BY_IDENTITY` — and FR-004a is what makes this specification actually use that
solution rather than merely cite it; the first draft of FR-004 forbade the sentinel outright
and thereby made the solved case unreachable, which is the trap worth recording. What has no
mirror is the way **in**: there is no `ENTRY_BY_IDENTITY`, `Tuple.route_in` requires a
`Candidate`, and so the zero-hop way in is not representable at all.

## Required tests this feature closes

| Row | What it asserts |
|---|---|
| **I1** | Feasibility pruning drops infeasible candidates with a recorded reason, and the count of dropped candidates is reported |

I1 is closed **at the tuple level**, which is the level `SIMULATOR_SPEC.md` §4.3.4's
feasibility list is written at. The landing change should record beside the flipped box that
§4.10.2's *allocation* candidates are a second population, pruned again under a rule this
feature does not build, so the row is not read later as covering more than it does.

**J4 is touched and not claimed.** A lock-up longer than the horizon reaches
`CannotSpanHorizon`, and this feature makes every such candidate visible in one report rather
than one at a time — but a declared `lock_up_months` term still does not exist, which is the
half 006 deliberately did not claim.

## Out of scope

Named explicitly so the plan does not drift: **objectives and constraints** (I2, I3) and
anything that ranks by something other than 010's existing rate; **shadow costs**; **the naive
baseline's allocation half** (I4); **the stability check** (I5); **indifference bands** (I6);
**"sometimes best" versus "never bad"** (I7); **the non-dominated set**, reachable and
deliberately not built; **label-correcting search, branch-and-bound and time-expanded nodes**,
all named above with what would force each; **allocations and portfolios of any kind** — this
feature enumerates and evaluates single tuples, exactly as 010 compares them; **Monte Carlo and
scenario sweeps** — one regime per set (FR-023); **any change to 010's `TupleRefused` union**,
including the two horizon-budget gaps this specification records; **the display-currency
switch**; and the web and command-line interfaces.

⚙ **Not out of scope, though a reader expects it to be**, two pieces of work outside this
feature's own module that it cannot ship without:

- **The candidate ceiling's declaration file and its loader** — a new declaration kind with an
  owner, no default and a load-time refusal (FR-019).
- **Widening `CompositionRefused` in feature 004 to say which of its three cases fired**
  (FR-014a). It is a change to another feature's type, made and reviewed there, and it is the
  reason FR-014 and FR-018 are implementable at all without string-matching a reason field.
