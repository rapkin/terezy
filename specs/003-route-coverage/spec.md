# Feature Specification: The coverage report

**Feature Directory**: `specs/003-route-coverage`

**Feature Branch**: none — this repo works on `main` by design

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: The coverage report — which comparisons the declared route graph can and
cannot support, and which single missing declaration would unlock the most.

---

## Why this feature exists

Feature 002 made ramp cost computable per `(destination × stream × route)`, and its
FR-030 made a destination without a declared exit route honestly incomparable: it is
reported as *exit cost unknown*, naming the missing declaration, and kept out of every
round-trip ranking. That refusal is correct — and, one destination at a time, it is
also invisible as a whole. Nothing today answers: *of everything I have declared, what
can actually be compared, what cannot, and which single observation would change that
the most?*

This feature turns those per-route refusals into a first-class audit of the whole
registry. The owner's rule it enforces:

> Everything money can be moved into must have a declared way in AND a declared way
> out — at least through one other venue — before it may appear in any comparison.

A hole in the route graph is a **fact the owner acts on** ("go observe that
corridor"), never a silent absence. `SIMULATOR_SPEC.md` §11 opens its list of open
questions with the observed numbers still missing from the route registry and says
plainly: *"Your observations beat any published schedule."* This feature turns that
sentence into a to-do list ordered by value — for each missing declaration, how many
`(destination × stream)` comparisons it blocks, so the owner knows which observation
to make next.

The report is deliberately **not** a comparison. It is computed from declarations
alone — costing is not needed to establish absence — and its output carries no cost
figures at all, so it cannot be mistaken for one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit the whole registry at once (Priority: P1)

The owner asks what the declared route graph can support. For every declared
destination and every declared income stream, the report states a verdict: this pair
is comparison-ready, or it is not — and when it is not, exactly why, in one of three
distinguished deficits: no inbound route from this stream, inbound exists but no exit
partner, or an exit exists but ends somewhere the money cannot be spent.

**Why this priority**: this is the audit the feature exists to produce. Without it,
FR-030's refusals stay scattered across individual costing calls and the registry's
overall health is unknowable except by trying every comparison one at a time.

**Independent Test**: declare a small registry by hand — two streams, three
destinations, a deliberate mix of complete pairs and each kind of hole — and check
every verdict against a hand-enumerated coverage table checked in beside the
assertion.

**Acceptance Scenarios**:

1. **Given** a destination with a declared inbound route from a stream's arrival venue
   and a declared exit route ending in spendable base currency, **When** the report is
   produced, **Then** the pair is marked comparison-ready and names the route
   declarations it relied on.
2. **Given** a destination with no declared route from a stream's arrival venue,
   **When** the report is produced, **Then** the pair is marked not ready with the
   deficit *no inbound route from this stream* — never a bare "missing route".
3. **Given** a destination with an inbound route but no declared exit route, **When**
   the report is produced, **Then** the deficit is *inbound exists but no exit
   partner*, distinct from the no-inbound case, because it calls for a different
   observation.
4. **Given** a destination whose only exit route ends in a currency or at a venue the
   owner cannot spend from, **When** the report is produced, **Then** the deficit is
   *exit exists but does not reach a spendable endpoint*, distinct from both other
   cases.
5. **Given** any verdict in the report, **When** it is read, **Then** no cost figure —
   no percentage, no amount — appears anywhere in it.

---

### User Story 2 - Know which observation to make next (Priority: P1)

Where coverage is missing, the report names the exact missing declaration — origin
venue, destination venue, direction, currency endpoints — precisely enough that the
owner could write the declaration file from the report alone, once the corridor has
been observed. And it counts how many `(destination × stream)` pairs each single
missing declaration blocks, so the missing declarations form a to-do list ordered by
how much each one unlocks.

**Why this priority**: equal-highest with Story 1, because an audit that says "7 of 12
pairs are not comparable" without saying what to do about it is a complaint, not a
tool. The count is the feature's answer to §11: the owner's next observation should be
the one that unblocks the most comparisons.

**Independent Test**: declare a registry where one missing exit declaration blocks
several pairs (one destination reachable from both streams) and one missing inbound
blocks a single pair; confirm the to-do list orders them by blocked-pair count and
that writing precisely the declaration the report names — and nothing else — flips the
blocked pairs to comparison-ready.

**Acceptance Scenarios**:

1. **Given** a not-ready pair, **When** its deficit is reported, **Then** the missing
   declaration is stated with origin venue, direction, currency endpoints and its
   target — the destination for a missing inbound; any declared spendable endpoint,
   candidates listed, for a missing exit — and a declaration written from exactly that
   statement, with observed values filled in by the owner, makes the pair
   comparison-ready with no other change.
2. **Given** one destination with inbound routes from both streams and no exit,
   **When** blocked pairs are counted, **Then** the single missing exit declaration is
   credited with blocking both pairs, and ranks above a missing inbound that blocks
   one.
3. **Given** two missing declarations blocking the same number of pairs, **When** the
   to-do list is ordered, **Then** they are reported as a tie, not broken arbitrarily.
4. **Given** a pair missing both its inbound and its exit, **When** each missing
   declaration is listed, **Then** each counts the pair among those it blocks and each
   is marked as **not alone sufficient** — adding one still leaves the other missing,
   and the report never implies otherwise.
5. **Given** a destination with an inbound route and no exit, **When** the missing
   exit is described, **Then** the description is an exit from the destination toward
   a spendable endpoint — never the inbound route reversed, and never a suggested
   provider, fee, premium or cap. The report names **what to observe**, not what the
   numbers will be.

---

### User Story 3 - See coverage per regime (Priority: P2)

A link may exist in wartime and be missing in the normalized regime, or vice versa.
The report states every verdict per regime, so the owner sees not only what is
comparable today but what stops or starts being comparable when the regime changes.

**Why this priority**: feature 002 already made regimes first-class for costing; an
audit that blended regimes would report a corridor as covered because it exists in one
regime while a scenario running in the other silently loses it — exactly the class of
confident-but-wrong summary this project refuses.

**Independent Test**: declare a route present in the wartime regime's route set and
absent from the normalized one; confirm the same pair is ready in the first regime and
not ready in the second, with the deficit named, and that no blended cross-regime
verdict appears anywhere.

**Acceptance Scenarios**:

1. **Given** a route named by one regime's route set and not the other's, **When** the
   report is produced, **Then** the affected pair is ready in the first regime and not
   ready in the second, each stated under its regime.
2. **Given** verdicts that differ across regimes, **When** the report is read, **Then**
   there is no single blended verdict for the pair — coverage is stated per regime,
   and blocked-pair counts are counted per regime.
3. **Given** the same missing declaration blocking pairs in more than one regime,
   **When** the to-do list is produced, **Then** it is recognizably one declaration,
   with its blocked count stated per regime rather than summed into one number.

---

### User Story 4 - Grow the registry without touching the engine (Priority: P3)

A new venue, stream or corridor declared purely as data appears in the next report —
as new coverage, or as a new, precisely named hole.

**Why this priority**: Principle II applied to the audit itself. The report's whole
purpose is to direct registry growth; if growing the registry required a code change,
the report would be directing work on itself. P3 because it is verified rather than
built — feature 002's loader already owns declaration validation.

**Independent Test**: add a venue and a route declaration as data only; confirm the
report gains the corresponding verdicts and to-do items with zero source changes.

**Acceptance Scenarios**:

1. **Given** a new venue declared as data with no routes touching it, **When** the
   report is produced, **Then** its holdable currency balances appear as destinations
   with *no inbound route* deficits per stream — the hole is visible the moment the
   venue exists.
2. **Given** a new route declaration completing a previously blocked pair, **When**
   the report is produced, **Then** the pair is comparison-ready and its to-do items
   are gone, with no source-code change.

---

### Edge Cases

- **A destination that is a stream's own arrival point** — money is born there; no
  inbound route exists or is needed. The report marks inbound as *satisfied by
  arrival*, distinct from satisfied-by-route, and still requires the exit.
- **An empty registry dimension** — no streams, no venues, or no routes declared. The
  report states which dimension is empty as a typed outcome; it is never an empty
  result the caller could mistake for "all covered" (predecessor defect B10).
- **Two inbound routes to one destination, only one with an exit partner** — the pair
  is comparison-ready (one complete way in and out suffices), and the partner-less
  inbound is still visible per FR-030's per-route honesty, not hidden by the ready
  verdict.
- **An orphan exit** — an exit declared from a destination no stream can reach in that
  regime. Not a hole under the owner's rule, but not hidden either: the report lists
  it as an observation already made that nothing yet uses.
- **A two-hop way out** — the destination's exit ends at another venue, which itself
  has an exit to spendable currency. A human sees a path; this feature MUST NOT
  compose it. The pair is not ready, the deficit says the exit does not reach a
  spendable endpoint, and the report states that composing multi-route paths is
  deliberately not done here — it is the next feature, which will surface such pairs
  under a distinct "reachable by composition only" annotation (FR-018's forward note)
  rather than by changing this verdict's meaning.
- **A route declared but closed, or outside its availability window, in a regime that
  names it** — the declaration exists, so it counts for coverage; the verdict carries
  the status visibly. Coverage is a claim about *declarations*, not about today's
  availability — but a ready verdict resting on a closed route must never look
  identical to one resting on an open one.
- **A destination and stream in the same currency at different venues** — no
  conversion needed does not mean no route needed; a transfer is still a declared
  leg. Absence is still a deficit.
- **Every pair ready** — the honest happy path: the to-do list is explicitly empty,
  stating there is nothing to observe, rather than absent.
- **Two regimes naming identical route sets** — the per-regime verdicts agree; the
  report still states them per regime rather than deduplicating into one, because
  agreement today is a fact, not an identity.

## Requirements *(mandatory)*

### Functional Requirements

**Verdicts**

- **FR-001**: The system MUST produce, for every declared destination × every declared
  income stream × every declared regime, a verdict: **comparison-ready** or **not
  comparison-ready**. No pair in the declared universe may be silently absent from the
  report.

  ⚙ **The destination universe is derived, not separately declared.** A destination is
  a currency balance at a venue (feature 002's shape), so the universe is every
  declared venue × every currency it declares it can hold. This is what makes a venue
  with zero routes visible as a hole the moment it is declared, instead of invisible
  until someone tries to cost it.
- **FR-002**: A comparison-ready verdict MUST require, within the regime, that **both halves
  of the owner's rule hold** — a way in and a way out. Each half is satisfied either by a
  declaration or by the destination's own position, and the two forms MUST be reported
  distinctly:
  1. **the way in** — at least one declared inbound route from the stream's arrival venue and
     arrival currency to the destination, **or** the destination being that stream's own
     arrival venue and currency (*satisfied by arrival*, FR-005);
  2. **the way out** — at least one declared exit route from the destination that ends at a
     spendable endpoint, **or** the destination itself being a declared spendable endpoint
     (*satisfied by identity*).

  ⚙ **The second form of the second half is an owner decision, 2026-08-23, and it replaces a
  stricter reading.** This requirement originally admitted only a declared exit route, with no
  exception. Implemented literally, that made the hryvnia balance on the owner's own salary
  rail a hole: no route out of it is declared, so the report demanded an observation of how to
  get money out of the account the money is spent from. The owner's answer is that the money is
  **already where it needed to come back out to** — requiring a corridor out of a spendable
  endpoint would have made the salary rail the first finding in the first real report, and it
  would have been wrong.

  So a destination in FR-004's declared spendable set has its exit half satisfied by identity,
  produces no deficit 2 and no deficit 3, and contributes no missing-exit item to the to-do
  list. The replaced reading is recorded here rather than deleted: it was the correct reading
  of the original sentence, and the sentence was amended rather than the code bent around it.
- **FR-003**: The system MUST distinguish three deficits, because they call for
  different observations, and MUST NOT collapse them into one "missing route":
  1. **no inbound route from this stream** — nothing declared carries money from the
     stream's arrival venue to the destination;
  2. **inbound exists but no exit partner** — the destination is reachable but has no
     declared way out at all;
  3. **exit exists but does not reach a spendable endpoint** — a way out is declared
     but it ends in a non-spendable currency or at a non-spendable venue.
- **FR-004**: What counts as a **spendable endpoint** MUST be a declared fact, not a
  built-in constant: a data-file list of `(venue × currency)` pairs — **base currency
  (UAH) only, at the specific venues the owner actually spends from** (owner decision,
  2026-08-22). Not "UAH anywhere", and not foreign cash in hand. It is a fact about
  the owner's life, entered as data; changing it MUST change category-3 verdicts with
  no source-code change, and an exit ending in UAH at a venue the list does not name
  is deficit 3, exactly as one ending in a foreign currency is.
- **FR-005**: A destination identical to a stream's arrival venue and currency MUST
  report inbound as **satisfied by arrival**, explicitly distinct from satisfied by a
  route, and MUST still require the exit half of FR-002 to be satisfied before the pair is
  comparison-ready — by a declared route, or by identity where the destination is itself a
  declared spendable endpoint. Arrival answers one half of the owner's rule and says nothing
  whatever about the other.
- **FR-006**: The report MUST NOT invent, infer or compose a link: no reversing an
  inbound route as an exit (feature 002 FR-027), no chaining two declared routes into
  a way out, no assuming a same-currency transfer is free of declaration. Composition
  of multi-route paths is explicitly the next feature, and a verdict that would change
  under composition MUST say only what the declarations support today.

**Missing declarations**

- **FR-007**: Every deficit MUST name the exact missing declaration — origin venue,
  destination venue, direction (inbound or exit), currency endpoints, and the regime
  it is missing in — precisely enough that the owner could write the declaration file
  from the report alone once the corridor is observed.

  ⚙ **"Currency path" here means the endpoints, deliberately.** The description asked
  for the currency path; the interior hops of an unobserved corridor (UAH → USDT →
  USD, or UAH → USD directly) are exactly the thing only an observation can supply.
  Naming interior hops would be inventing the very link the report exists to refuse to
  invent, so the missing declaration states start currency at origin venue and end
  currency at destination venue, and leaves the interior to the owner.

  ⚙ **A missing exit's target is a set, not a point** (review finding, 2026-08-22).
  For a missing **inbound**, both endpoints are determined — the stream fixes one, the
  destination the other. For a missing **exit**, only the origin is determined: any
  declared spendable endpoint would satisfy the rule, and picking one would be the
  report inventing a preference. So a missing-exit declaration names its origin (the
  destination venue and currency) and its target as **any declared spendable
  endpoint**, listing the declared candidates from FR-004's list. Its identity is
  **origin + direction (+ regime)** — it is ONE to-do item, not one per candidate
  endpoint, so blocked-pair counts never multiply by the length of the spendable
  list.
- **FR-008**: The report MUST NOT suggest observed values — no provider, fee, premium,
  cap, latency or rate appears in a missing-declaration description. It names what to
  observe, never what the numbers will be; the numbers come from the owner's
  observation with its own provenance, per §11.
- **FR-009**: For each missing declaration, the system MUST count how many
  `(destination × stream)` pairs it blocks, per regime. A declaration *blocks* a pair
  when the pair is not comparison-ready and that declaration is among those required
  to make it so.
- **FR-010**: The to-do list MUST be ordered by blocked-pair count, descending, within
  each regime. The count is a plain count of pairs — never a weighted or composite
  score (required test B12 forbids a non-standard composite driving a user-visible
  ordering). Equal counts MUST be reported as a tie, not broken arbitrarily.
- **FR-011**: Where a blocked pair requires more than one missing declaration, each
  MUST count it among the pairs it blocks AND be marked **not alone sufficient** for
  that pair. The report MUST never present a necessary-but-not-sufficient declaration
  as if adding it alone would unlock the pair.
- **FR-012**: An exit declared from a destination that no stream can reach in a regime
  (an orphan exit) MUST be listed as such — an observation already made that nothing
  yet uses. It is not a deficit, and hiding it would misstate the registry.

**Regimes**

- **FR-013**: Every verdict, deficit and blocked-pair count MUST be stated per regime.
  A link present in one regime and absent in another MUST be reported as exactly that,
  and no blended cross-regime verdict or count may exist anywhere in the output.
- **FR-014**: The same missing declaration blocking pairs in more than one regime MUST
  be recognizable as one declaration, with its blocked count stated per regime rather
  than summed — which observation to make is one decision; what it unlocks differs by
  regime, and the owner weighs regimes, not the tool.
- **FR-015**: When no regime is declared, the report MUST cover a single implicit
  regime containing every declared route, and MUST say that this is what it did.

**Honesty of the report itself**

- **FR-016**: The report MUST be computed from declarations alone — venues, streams,
  routes, regimes. It MUST NOT invoke costing, and it MUST be deterministic: same
  declarations, same report.
- **FR-017**: The output MUST carry no cost figures whatsoever — no percentages, no
  monetary amounts, one-way or round-trip — so it cannot be mistaken for a comparison.
  Counts of pairs and identities of declarations are the only quantities in it.
- **FR-018**: The report MUST agree with what costing actually does, **scoped to
  costing over single declared routes, as of this feature**: a pair marked
  comparison-ready MUST be one for which feature 002's costing can produce a
  round-trip figure, and a pair whose costing over single declared routes is refused
  (no route, or *exit cost unknown* per FR-030) MUST NOT be marked ready. Two views of
  one registry MUST NOT disagree about what is comparable.

  ⚙ **A pair that names no route is outside this agreement's domain, not in disagreement
  with it** (added 2026-08-23). Costing is keyed by a `(destination × stream × route)` triple,
  so a pair whose way in is satisfied by arrival and/or whose way out is satisfied by identity
  has no route for costing to be asked about: it produces neither a figure nor a refusal. The
  hole already existed for arrival under FR-005; the FR-002 decision above widened it to the
  exit side. Such pairs MUST be partitioned out of the consistency claim **explicitly and
  asserted to be outside it**, never skipped silently, so the exclusion cannot swallow a real
  disagreement.

  ⚙ **Forward note for composed paths (feature 004).** The owner has decided, in
  004's clarification, that a chain of separately declared exit segments DOES satisfy
  feature 002's FR-027 — so once composition lands, costing will produce round-trip
  figures for some pairs this report marks not-ready, and an unscoped consistency
  claim would break. When composition lands, coverage gains a **distinct annotation:
  "reachable by composition only"** — computable from declarations alone by chaining,
  so the report stays pure and needs no costing — and the two views stay reconciled
  through that annotation, never by blending it into the single-route verdict.
- **FR-019**: The coverage verdict is **advisory in this feature** (owner decision,
  2026-08-22): it informs the owner, and feature 002's ranking behaviour does not
  change here. Producing the report MUST have no effect on any costing or ranking
  output — and the report itself MUST state that its verdicts are advisory and that
  enforcement is deferred, so a reader of the output, not only of this spec, sees the
  gap.

  ⚙ **A recorded incompleteness, not a final reading.** The owner's rule — "before it
  may appear in any comparison" — **remains the destination**, and the owner
  explicitly said this decision may later move to binding: a later feature may make
  ranking exclude a destination whose only exit is non-spendable, extending FR-030's
  refusal. Until then there is a stated gap between the rule and its enforcement: a
  deficit-3 destination stays in feature 002's round-trip ranking while this report
  says it should not be compared. That gap is deliberate, dated and on the spec's
  face — in the style of feature 001's nominal-only decision — so the softer reading
  is never mistaken for the rule itself.
- **FR-020**: An empty registry dimension — no streams, no venues, no routes — MUST
  produce a typed outcome naming which dimension is empty. The report MUST never be an
  empty result a caller could mistake for full coverage (predecessor defect B10).
- **FR-021**: Every verdict MUST be traceable: a ready verdict names the route
  declarations it relied on; a not-ready verdict names the missing declaration. The
  report as a whole MUST identify the exact declaration set it audited, so a verdict
  traces to the declarations that produced it.
- **FR-022**: A route that is declared but closed, or outside its availability window,
  in a regime that names it MUST count as declared for coverage, and the verdict MUST
  carry that status visibly.

  ⚙ **Declaration, not availability, is what coverage measures — by design.** The
  owner's rule is about *declared* ways in and out: the hole this report exists to
  surface is a corridor nobody has observed, and the fix is an observation. A closed
  route is a different fact — observed, declared, currently unusable — and feature
  002's feasibility reporting already owns it at costing time. Counting closed routes
  as holes would tell the owner to go observe a corridor that is already observed.
  The obligation this leaves: a ready verdict resting only on closed routes must be
  visibly different from one resting on open ones, or the report would be quietly
  overstating what can be compared today.
- **FR-023**: The report carries no verified/unverified marks of its own, because it
  contains no observed values — the existence of a declaration is a fact of the
  registry, not an observation of the world. It MUST NOT restate or aggregate the
  provenance or staleness of declared values; those belong to costing figures, and a
  second, summarized copy here would drift from the authoritative one.

**Extensibility**

- **FR-024**: A new venue, stream, route or regime declared purely as data MUST appear
  in the next report — as coverage or as a named hole — with no source-code change
  (Principle II). Malformed declarations remain the loader's concern and fail at load
  naming file and field, exactly as feature 002 established; this feature adds no
  second validation path.

### Key Entities

- **Coverage report** — the audit: every `(destination × stream × regime)` verdict,
  the to-do list of missing declarations, the orphan exits, and the identity of the
  declaration set audited. Contains no cost figures.
- **Pair verdict** — comparison-ready or not, for one destination × one stream in one
  regime; carries the routes relied on (with their status) or the deficit.
- **Deficit** — one of three distinguished kinds: no inbound from this stream; inbound
  but no exit partner; exit not reaching a spendable endpoint. Carries the missing
  declaration.
- **Missing declaration** — origin venue and currency, direction, regime, and the
  target: for an inbound, the destination venue and currency; for an exit, *any
  declared spendable endpoint*, with the candidates listed. Identity is origin +
  direction (+ regime) — one item, never one per candidate endpoint. Precise enough to
  write the declaration file from, silent on every value only an observation can
  supply.
- **To-do item** — a missing declaration with its blocked-pair count per regime and,
  per blocked pair, whether it is alone sufficient.
- **Spendable endpoint** — a declared `(venue × currency)` where money counts as
  having come back out: UAH at the specific venues the owner actually spends from,
  entered as a data-file list (FR-004, owner decision 2026-08-22).
- **Orphan exit** — a declared exit from a destination no stream can reach in a
  regime; listed, not counted as a deficit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a hand-declared registry of two streams, three destinations and a
  deliberate mix of holes, every `(destination × stream × regime)` verdict matches a
  hand-enumerated coverage table checked in beside the assertion, and no pair in the
  declared universe is absent from the report. (FR-001, FR-002)
- **SC-002**: Three crafted registries — one per deficit kind — each produce their own
  distinguished deficit, and no registry produces a bare undifferentiated "missing
  route". (FR-003)
- **SC-003**: For a not-ready pair, writing precisely the declaration the report names
  — and nothing else — flips that pair to comparison-ready in the next report; for a
  missing exit, writing an exit to **any one** of the listed spendable endpoints
  suffices. The report-to-declaration loop closes, measured by doing it. (FR-007)
- **SC-004**: No missing-declaration description anywhere in the output contains a
  provider, fee, premium, cap, latency or rate — verified across every to-do item, not
  sampled. (FR-008)
- **SC-005**: In a registry where one missing exit blocks two pairs and one missing
  inbound blocks one, the to-do list orders the exit first with a count of 2; in a
  registry where two missing declarations block equal counts, they are reported as a
  tie. (FR-009, FR-010)
- **SC-006**: A pair missing both inbound and exit appears in the blocked count of
  both to-do items, and both are marked not alone sufficient for it. (FR-011)
- **SC-007**: A route named by one regime and not another yields a pair that is ready
  in the first and not ready in the second; no blended verdict or summed cross-regime
  count exists anywhere in the output, and the shared missing declaration is
  recognizably one item with per-regime counts. (FR-013, FR-014)
- **SC-008**: No cost figure — no percentage, no monetary amount — and no restated
  provenance or staleness mark appears anywhere in the report, verified across the
  whole output, not sampled. (FR-017, FR-023)
- **SC-009**: For a generated battery of registries, every pair the report marks ready
  is one costing over single declared routes produces a round-trip figure for, and
  every pair such costing refuses is marked not ready — the two views never disagree,
  within this feature's single-route scope. (FR-018)
- **SC-010**: A registry with an inbound route and no exit yields a missing
  declaration whose direction is exit and whose origin is the destination venue — and
  nothing in the report reproduces the inbound route's shape as a suggestion. (FR-006)
- **SC-011**: A destination whose exit ends at a venue that itself has an exit to
  spendable currency is reported not ready with deficit 3 — the two-hop path is never
  composed. (FR-006)
- **SC-012**: A destination equal to a stream's arrival venue and currency reports
  inbound satisfied by arrival, and is comparison-ready if and only if its exit half is
  satisfied — by a declared exit route, or by the destination itself being a declared
  spendable endpoint, each reported as its own distinct sentinel. (FR-002, FR-005)
- **SC-013**: Each empty registry dimension produces a typed outcome naming that
  dimension; none produces an empty report. (FR-020)
- **SC-014**: A new venue declared as data, with no routes, appears in the next report
  as destinations with named no-inbound deficits — with zero lines of source changed.
  (FR-001 ⚙, FR-024)
- **SC-015**: A ready verdict resting only on a closed route is visibly distinct from
  one resting on an open route, and both are distinct from a hole. (FR-022)
- **SC-016**: The same declarations produce the identical report on every run, and the
  report identifies the declaration set it audited. (FR-016, FR-021)
- **SC-017**: An orphan exit is listed as unused, appears in no deficit, and blocks no
  count. (FR-012)
- **SC-018**: With no regime declared, the report covers one implicit regime
  containing every route and says so. (FR-015)
- **SC-019**: An exit ending in UAH at a venue absent from the declared spendable list
  is deficit 3; adding that venue to the list — a data change, zero lines of source —
  flips the pair to comparison-ready in the next report. (FR-004)
- **SC-020**: Feature 002's ranking output over one registry is identical with and
  without this feature's report produced — the verdict is advisory, and the deferral
  of enforcement is stated in the report's output, not merely in this spec. (FR-019)

## Assumptions

- **The declaration set is feature 002's, plus exactly one new file.** Venues with
  their holdable currencies, streams with arrival venue and currency, routes with
  direction and legs, regimes with their route sets. This feature reads them and adds
  exactly one declaration: the spendable-endpoint list of `(venue × currency)` pairs
  (FR-004) — and no other format.
- **The destination universe is venue × holdable currency** (FR-001 ⚙). This makes the
  report's size the size of the declared world, which is the point: a venue declared
  but unreachable is a finding, not noise.
- **An inbound route "from this stream" means from its arrival venue in its arrival
  currency.** A route from the right venue in a currency the stream does not arrive in
  does not carry that stream's money and does not count. This is the same chaining
  discipline feature 002 enforces at load, applied at the audit level.
- **"At least through one other venue"** in the owner's rule is read as: the exit
  leaves the destination venue — a way out exists to somewhere else that is spendable
  — not as a requirement that the exit differ from the inbound's venues. Where it must
  land is FR-004's declared list: UAH at the venues the owner spends from. **Amended
  2026-08-23**: this reading governs a destination that is *not* itself on that list. Where
  the destination **is** on it, no corridor is needed at all and the exit half is satisfied
  by identity (FR-002 ⚙) — money already at a spendable endpoint has nowhere left to go.
- **Coverage is about declarations, not availability** (FR-022 ⚙). Closed and
  out-of-window routes count as declared, visibly annotated. The alternative reading —
  coverage as "usable today" — is feature 002's feasibility reporting, which already
  exists at costing time.
- **No cross-regime aggregation anywhere.** Which regime matters more is the owner's
  judgement; the report supplies per-regime facts and refuses to weigh them.
- **The report carries no provenance marks of its own** (FR-023): it contains no
  observed values, only facts about the registry. Staleness and verification stay
  with the values they describe, surfaced by costing as feature 002 requires.
- **One owner, no authentication.** Records carry an owner identifier as before.
- **No delivery surface.** No web interface, no command-line interface. The report is
  produced and asserted by the test suite, like feature 002's results.

## Clarifications resolved

Both answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | What counts as a **spendable endpoint** — UAH at any venue, UAH at named venues only, or also foreign cash in hand? | **UAH only, at the specific venues the owner actually spends from**, declared as a data-file list of `(venue × currency)` pairs. A fact about the owner's life, entered as data. | FR-004, SC-019 |
| 2 | Does the coverage verdict **bind comparisons**, or is it advisory? | **Advisory for now** — feature 002's ranking does not change in this feature. The owner explicitly kept binding on the table: the rule "before it may appear in any comparison" remains the destination, and enforcement is a **recorded deferral** to a later feature, stated on the spec's face and in the report's own output. | FR-019, SC-020 |
| 3 | Does a destination that **is** a declared spendable endpoint still need a declared exit route? Answered **2026-08-23**, after implementation surfaced it. | **No — the exit half is satisfied by identity.** The money is already where it needed to come back out to. The reading this replaces (an exit route required without exception) made the owner's own salary rail a hole demanding an observation of how to get money out of his bank account. Reported as a distinct sentinel, mirroring *satisfied by arrival*, so it is never confused with a declared way out. | FR-002, FR-005, FR-018 ⚙, SC-012 |

**The second decision leaves a deliberate gap worth stating plainly.** Until
enforcement lands, a destination whose only exit is non-spendable still appears in
feature 002's round-trip ranking while this report says it should not be compared.
That is a stated, dated incompleteness — in the style of feature 001's nominal-only
decision — not a softer reading of the owner's rule.

### Corrections from external review (2026-08-22)

Two findings, both fixed in this spec rather than left for planning to trip over:

- **A missing exit's target was underdetermined.** FR-007 promised a declaration
  precise enough to write the file, but for a missing exit any declared spendable
  endpoint satisfies the rule — the target is a set, not a point. Fixed in FR-007's
  second ⚙: the missing-exit item names its origin and "any declared spendable
  endpoint" with the candidates listed; identity is origin + direction (+ regime), so
  it is one to-do item and blocked-pair counts never multiply by the length of the
  spendable list. SC-003 now closes the loop with an exit to any one listed endpoint.
- **FR-018 would have collided with composed paths.** Feature 004's clarification has
  the owner deciding that a chain of separately declared exit segments satisfies
  002's FR-027, so composition will let costing produce round-trip figures for pairs
  this report marks not-ready. FR-018 and SC-009 are now scoped to costing over single
  declared routes as of this feature, and FR-018's forward note commits the
  reconciliation path: a distinct "reachable by composition only" annotation, computed
  by chaining declarations — pure, no costing — never a blended verdict.

## Required tests this feature closes

**No lettered row in `docs/REQUIRED_TESTS.md` names a registry coverage audit**, so
this feature closes none of the existing rows — stated plainly rather than stretched.
The rows its tests reinforce, and the groundwork it lays:

| Row | Relation |
|---|---|
| **B10** | Exercised anew: empty registry dimensions and every not-ready verdict are typed outcomes carrying their reason, never empty results. |
| **B12** | Honoured by construction: the to-do ordering is a plain blocked-pair count, ties reported as ties; no composite score drives a user-visible ordering. |
| **H2** | Unchanged and relied on: declaration validation stays in the loader; this feature adds no second validation path. |
| **G6 / FR-030 (002)** | Extended in visibility: the per-route "exit cost unknown" refusal becomes auditable across the whole registry, and SC-009 pins the two views together. |
| **I1 (future)** | Groundwork: the decision layer's feasibility pruning will consume comparison-readiness; this feature defines what "comparable at all" means before anything is pruned. |

The feature's own behaviours land under Principle V regardless: SC-001's
hand-enumerated coverage table is a worked example with its enumeration checked in,
and SC-009 is a property over generated registries.

## Out of scope

Named explicitly so the plan does not drift: **composing or inferring multi-route
paths** (a two-hop way out is reported as a hole, never assembled — that is the next
feature); any new instrument; market prices, return models and live data; the decision
layer and candidate generation; any change to how costing computes numbers (FR-018 is
a consistency check against costing's existing single-route refusals, and FR-019's
enforcement is an owner-recorded deferral to a later feature — the verdict is advisory
here); staleness and provenance presentation, which stay
with the values they describe under feature 002's FR-022/FR-025/FR-028; the display
surface.

One boundary worth stating on its own, because the report will make it tempting: the
to-do list orders observations by how many pairs they unblock, **not by how much money
they are worth**. Valuing a corridor needs costing and a scenario; counting what it
unblocks needs only declarations. The moment someone wants "which observation is worth
the most hryvnia", that is a costing question over a registry that does not yet
contain the observation — an invented number by construction — and this report must
never grow one.
