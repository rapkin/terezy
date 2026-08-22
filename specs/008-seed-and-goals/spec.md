# Feature Specification: Seeds and goals

**Feature Directory**: `specs/008-seed-and-goals`

**Feature Branch**: `spec/008-seed-and-goals`

**Created**: 2026-08-22

**Status**: Ready for planning — all clarifications resolved 2026-08-22

**Input**: Seeds and goals — what the owner already holds, and what the money is for.
Existing holdings enter as declared opening lots with a known or estimated cost basis
(SIMULATOR_SPEC §4.8, required test J2); a target is a sum, a date and a contribution,
of which the owner fixes any two and the tool solves the third (SIMULATOR_SPEC §4.7,
required test J1).

---

## Why this feature exists

Every projection the tool can run so far starts from zero and runs until asked to stop.
Reality does neither: the owner already holds positions acquired on real dates at real
costs, and the money has a job — a sum, by a date. This feature adds both ends.

Both are **per-owner declared data**, not curated market facts. Principle VII draws
that boundary on purpose: instruments, routes and tax packs are shared and
version-controlled; the owner's holdings and goals are the owner's life, kept separate
from them from the first commit. This feature is the first thing that actually lives on
the private side of that boundary.

Two sharp rules give the feature its shape:

- **A guessed cost is a guessed tax.** A seed is not a current value — the tax engine
  needs lots (§4.8). Where the owner genuinely does not know a lot's cost, the estimate
  is accepted but marked, and the mark propagates: a disposal's gain computed from a
  guessed basis is a guessed gain, and the tax on it is a guessed tax. This is
  Principle I applied to the owner's own declarations, not just to market observations.
- **The solver never quietly answers a different question.** Fix any two of
  (contribution, sum, date) and the third is solved; the three modes must agree with
  each other within the single project tolerance. A goal that cannot be met reports the
  binding shortfall — how much is missing, or how late — never a silent nearest answer.

The owner's actual figures — monthly amounts per stream, the real seed holdings with
their dates and costs — are still unstated (§11 item 3). Nothing here invents them:
fixtures are labelled synthetic, and the real files carry the owner's declarations when
they arrive.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start from what is actually held (Priority: P1)

The owner declares existing holdings as lots — which instrument, how many, acquired
when, at what cost — and every projection from then on starts from those positions
instead of from zero. The seeded lots are real ledger citizens: they open the ledger as
opening lots, they are counted by every conservation check from day one, and when one
is later disposed of, its realised gain is computed from its declared acquisition cost
exactly as if the engine had witnessed the purchase itself.

**Why this priority**: Without seeds every result the tool produces describes a
hypothetical person with no assets. The owner's actual decision — what to do next with
what is already held — is unanswerable until existing positions are in the ledger.

**Independent Test**: Declare a synthetic seed lot with a stated cost, project a
disposal, and check the realised gain against arithmetic worked out by hand. Confirm
that position quantity and cost basis equal the sums over the declared lots at every
point.

**Acceptance Scenarios**:

1. **Given** a declared seed lot of a known instrument with quantity, acquisition date
   and known cost, **When** a projection starts, **Then** the ledger opens holding that
   lot, the position quantity equals the declared quantity, and the position cost basis
   equals the declared cost.
2. **Given** a seeded lot with a known basis, **When** the lot is disposed of at a
   stated price, **Then** the realised gain equals proceeds minus the declared basis
   consumed minus fees allocated to the disposal, and matches the hand-computed figure
   within the single project tolerance.
3. **Given** several seed lots of the same instrument acquired on different dates at
   different costs, **When** the projection runs, **Then** each lot retains its own
   acquisition date and cost, and the position-level quantity and basis equal the sums
   over the lots at every point in the projection.
4. **Given** a seeded ledger, **When** the conservation invariants are checked from the
   opening date onward, **Then** cash conservation, lot conservation and basis
   conservation all hold — the opening lots are inside the invariants, not exempt from
   them.
5. **Given** a seed declaring an instrument that no curated declaration defines,
   **When** the seed file is loaded, **Then** loading fails naming the file and the
   unknown instrument, and no placeholder instrument is invented.

---

### User Story 2 - A guessed cost is a guessed tax (Priority: P1)

Every seed lot states whether its cost basis is **known** or **estimated** — declared
explicitly, never inferred. An estimated basis is accepted, but from that moment every
figure that depends on it is visibly marked: the disposal's gain, the tax charged on
it, the after-tax return, and any aggregate they feed. A seed that declares neither a
known nor an estimated basis is refused outright — no default, no zero, no current
value standing in for a cost.

**Why this priority**: Equal-highest with Story 1 because it is the honesty half of the
same mechanism. Seeding with value but no basis means every later disposal computes the
wrong gain (§4.8), and a wrong tax figure presented confidently is precisely the defect
class this project exists to eliminate. The marking cannot be deferred: the owner's
real seed declarations, when they arrive, will almost certainly contain lots with
forgotten costs.

**Independent Test**: Declare two synthetic seed lots identical except that one basis
is known and the other estimated; dispose of both. Confirm the known-basis figures
carry no basis mark and the estimated-basis figures — gain, tax, after-tax result — all
do.

**Acceptance Scenarios**:

1. **Given** a seed lot whose basis is declared estimated, **When** the lot is disposed
   of, **Then** the realised gain, the tax computed on it, and every figure derived
   from either are all marked as resting on an estimated basis, and no derived figure
   appears unmarked.
2. **Given** a seed lot whose basis is declared known, **When** the lot is disposed of,
   **Then** the resulting figures carry no basis-estimated mark, and any provenance
   marks they do carry come from other inputs.
3. **Given** a seed lot declaring a basis value but no statement of whether it is known
   or estimated, **When** the seed file is loaded, **Then** loading fails naming the
   file and the missing declaration, and no default is substituted.
4. **Given** a seed lot declaring no basis value at all, **When** the seed file is
   loaded, **Then** loading fails naming the file and the field — the lot is never
   admitted with a zero, defaulted or back-filled cost.
5. **Given** a figure marked basis-estimated, **When** it is inspected, **Then** the
   mark states its reason — an estimated acquisition cost — distinguishably from a mark
   caused by an unverified market observation, and both kinds propagate to every
   derived figure.

---

### User Story 3 - Fix two, solve the third (Priority: P1)

The owner states a goal as any two of three variables — monthly contribution, target
sum, target date — and the tool solves the remaining one against a stated growth
assumption and a stated starting amount: what will I have by then, when do I get there,
or what must I put in monthly. The three modes are one model seen from three sides, and
they must agree: solving for the date from (contribution, sum) and then for the sum
from (contribution, that date) returns the original sum, within the single project
tolerance.

**Why this priority**: This is the other half of the feature's value. "What is this
money for" is the question every later recommendation is measured against; a goal that
exists only in the owner's head cannot bind anything.

**Independent Test**: State a synthetic (contribution, sum) pair, solve the date, then
solve the sum from (contribution, that date) and confirm the round trip returns the
original sum within the single project tolerance; check one solved value of each mode
against hand-computed arithmetic.

**Acceptance Scenarios**:

1. **Given** a stated contribution and target date, **When** the goal is evaluated,
   **Then** the tool reports the sum reached by that date, matching the hand-computed
   figure within the single project tolerance.
2. **Given** a stated contribution and target sum, **When** the goal is evaluated,
   **Then** the tool reports when the target is reached, and solving the sum back from
   that answer returns the original target within the single project tolerance.
3. **Given** a stated target sum and target date, **When** the goal is evaluated,
   **Then** the tool reports the required monthly contribution, and evaluating that
   contribution forward reproduces the target within the single project tolerance.
4. **Given** a goal declaring fewer than two of the three variables, **When** it is
   loaded, **Then** it is refused naming what is missing — the tool never fills in a
   variable to make the goal solvable.
5. **Given** a goal with no stated growth assumption or no stated starting amount,
   **When** it is evaluated, **Then** it is refused naming the missing input — no
   default rate and no assumed opening balance is ever substituted.
6. **Given** a growth assumption that is itself unverified or estimated, **When** a
   goal is solved against it, **Then** the solved figure carries the assumption's mark.

---

### User Story 4 - Told the truth when the goal cannot be met (Priority: P2)

When the goal's constraints cannot all hold, the tool says so and says by how much. All
three variables fixed is a feasibility question: met or missed, and when missed, the
binding shortfall — how much is missing at the date, and how late the target would
actually arrive. A target that can never be reached under the stated assumption is
reported as unreachable with its reason, never as an absurdly distant date or a
silently capped answer.

**Why this priority**: P2 because Stories 1–3 are useful without it, but it is the
difference between a solver and an honest solver. A tool that quietly answers a nearby
question instead of the asked one is the predecessor's defect wearing a new face.

**Independent Test**: State a synthetic goal that misses its target by a hand-computed
margin and confirm the reported shortfall matches; state one that can never be reached
and confirm the typed refusal names why.

**Acceptance Scenarios**:

1. **Given** all three variables fixed and consistent, **When** the goal is evaluated,
   **Then** the tool reports the goal as met, with the margin by which it is met.
2. **Given** all three variables fixed and inconsistent, **When** the goal is
   evaluated, **Then** the tool reports the goal as missed, the amount missing at the
   target date, and the earliest date the target would actually be reached — both
   faces of the binding shortfall — and never adjusts any variable to make the goal
   pass.
3. **Given** a target that can never be reached under the stated assumption — for
   example, zero contribution and no growth against a target above the starting amount,
   **When** the date is solved, **Then** the tool reports the goal as unreachable with
   the reason, rather than any finite date, any capped horizon, or any silent nearest
   answer.
4. **Given** a target already met by the starting amount alone, **When** the required
   contribution is solved, **Then** the tool reports that no contribution is needed,
   rather than a negative contribution presented as an instruction.
5. **Given** a solved date that falls between two contribution dates, **When** it is
   reported, **Then** the tool reports both the exact solution — the one the
   consistency property holds for — and the first calendar date on which the target is
   actually reached, each labelled as what it is, and never silently rounds one into
   the other.

---

### User Story 5 - The owner's life stays the owner's file (Priority: P3)

Seeds and goals are declared in per-owner data, separate from the curated market data,
and every row carries the owner identifier. A malformed declaration fails loudly naming
the file and the field. Until the owner's real figures arrive, every seed and goal in
the repository is a labelled synthetic fixture — and the tool runs correctly with no
seeds and no goals at all, inventing nothing in their absence.

**Why this priority**: P3 because it is largely verified rather than built: if Stories
1–4 respect the Principle VII boundary, this story's job is to prove it. It is what
makes multi-user cheap later and what keeps the owner's finances out of the shared
data.

**Independent Test**: Load seeds and goals from a per-owner declaration file, confirm
every resulting record carries the owner identifier, delete the file and confirm the
tool still runs producing no seeded positions and no goal results — with no curated
file touched either way.

**Acceptance Scenarios**:

1. **Given** a per-owner declaration of seeds and goals, **When** it is loaded,
   **Then** every seed lot and every goal carries the owner identifier, and no curated
   data file is modified by declaring them.
2. **Given** a declaration file with a misspelled or unrecognised field, **When** it is
   loaded, **Then** loading fails naming the file and the field, and no default is
   substituted.
3. **Given** no per-owner declaration at all, **When** a projection runs, **Then** it
   runs from empty positions with no goal, and no placeholder seed or goal is invented
   to fill the gap.
4. **Given** the synthetic fixtures used for testing, **When** any of them is
   inspected, **Then** it is plainly labelled synthetic and cannot be mistaken for the
   owner's actual declaration.

---

### Edge Cases

- **A seed lot with zero or negative quantity** — rejected as invalid input at load
  time, naming the file and the field.
- **A seed lot with a negative declared cost** — rejected as invalid input; a rebate is
  not a basis.
- **An acquisition date in the future** relative to the projection start — an
  inconsistency, reported; the lot is not admitted and not silently re-dated.
- **An acquisition date before the instrument existed** (where the curated declaration
  states an issue date) — an inconsistency, reported rather than accepted.
- **Two seed lots of the same instrument on the same date** — legitimate (two separate
  purchases), both admitted as distinct lots.
- **A duplicate goal identifier** — a collision, reported at load time.
- **A goal denominated in a currency other than the base** — refused at load with a
  reason naming the missing FX modelling, never treated as an invalid currency
  (FR-016).
- **A goal whose target date is in the past** — invalid input, reported; never solved
  "backwards".
- **A zero contribution with positive growth** — a valid goal; the sum grows from the
  starting amount alone.
- **A goal declaring all three variables where the target is met exactly** — reported
  as met with zero margin, not as missed by a rounding hair; the single project
  tolerance governs the boundary.
- **A goal evaluated against a growth assumption of exactly zero** — valid; the
  arithmetic degenerates to saving without growth and must still hand-compute.
- **A disposal larger than the seeded position** — refused as infeasible naming the
  available quantity; never silently clipped.
- **A seed file that is not valid syntax** — fails naming the file.

## Requirements *(mandatory)*

### Functional Requirements

**Seeds — opening the ledger from declared lots**

- **FR-001**: The system MUST accept per-owner declared seed lots, each stating the
  instrument, the quantity, the acquisition date, and the acquisition cost, and MUST
  open the projection ledger holding those lots as opening lots.
- **FR-002**: Every conservation invariant — cash conservation, lot conservation, basis
  conservation — MUST hold over a seeded ledger from the opening date onward. Opening
  lots are ordinary lots to every invariant; there is no seeded-lot exemption.
- **FR-003**: Position quantity MUST equal the sum of the declared lot quantities and
  position cost basis MUST equal the sum of the declared lot costs, at the opening and
  at every later point, with each lot retaining its own acquisition date and cost.
- **FR-004**: When a seeded lot is disposed of, the realised gain MUST equal proceeds
  minus the declared basis consumed minus fees allocated to the disposal, and MUST
  reproduce a hand-computed example within the single project tolerance.
- **FR-005**: A seed lot naming an instrument that no curated declaration defines MUST
  fail at load time naming the file and the instrument. No placeholder instrument is
  ever created.

**Basis honesty — known and estimated**

- **FR-006**: Every seed lot MUST explicitly declare its basis as **known** or
  **estimated**. A lot with a basis value but no such declaration, or a lot with no
  basis value at all, MUST be refused at load time naming the file and the field —
  never defaulted, never zero-filled, never back-filled from a current value.
- **FR-007**: An estimated basis MUST mark every downstream figure exactly as an
  unverified observation does: the disposal's realised gain, the tax computed on it,
  the after-tax result, and every aggregate containing any of them MUST carry the mark.
  A transform that drops the mark is a defect of the highest severity.
- **FR-008**: The basis-estimated mark MUST state its reason and MUST be
  distinguishable on inspection from a mark caused by an unverified market observation,
  while propagating by the same rule. A figure resting on both MUST show both.
- **FR-009**: An estimated basis is stated as **a single point value the owner
  asserts** (owner decision, 2026-08-22). A range form (low–high, whose width would
  propagate into the gain and the tax as a range per Principle I) was offered and
  **not taken** — recorded here explicitly so a later reader knows a range is a
  possible future widening, not an oversight. The point form changes only how the
  estimate is stated: the basis-estimated mark of FR-007 and FR-008 propagates exactly
  as specified, so the figure is honestly labelled even though it is a single number.
- **FR-010**: The declared acquisition cost of a seed lot is stated in the base
  currency (hryvnia), per the reference declaration shape (§4.8). A basis stated in any
  other currency MUST be refused in this feature rather than converted by an assumed
  rate; converting a foreign-currency basis at the dated official rate arrives with the
  FX features and is out of scope here.

**Goals — fix two, solve the third**

- **FR-011**: The system MUST accept a per-owner goal declaring any two of: monthly
  contribution, target sum, target date — and MUST solve the third. A goal declaring
  fewer than two MUST be refused naming what is missing.
- **FR-012**: Every goal evaluation MUST run against an explicitly stated starting
  amount and an explicitly stated growth assumption, each carrying provenance. A goal
  with either input missing MUST be refused naming the missing input; no default rate
  and no assumed opening balance may ever be substituted. Marks on the growth
  assumption — unverified, estimated — MUST propagate to every solved figure.
- **FR-013**: The three modes MUST be mutually consistent: solving for the date from
  (contribution, sum) and then for the sum from (contribution, that date) MUST return
  the original sum within the single project tolerance, and the corresponding round
  trips through the contribution mode MUST close the same way. No mode may define its
  own tolerance.
- **FR-014**: Each solved figure MUST reproduce hand-computed arithmetic within the
  single project tolerance, and the evaluation conventions the arithmetic depends on —
  when in the period a contribution lands, how growth compounds between contributions —
  MUST be stated in the result rather than left implicit, so the hand computation and
  the engine are checking the same model.
- **FR-015**: When the exact solved date falls between contribution dates, the system
  MUST report both the exact solution (the value for which the consistency property of
  FR-013 holds) and the first calendar date on which the target is actually reached,
  each labelled as what it is. Silently rounding one into the other is a silent nearest
  answer and is forbidden.
- **FR-016**: A goal's target sum carries a currency, and in this feature that
  currency MUST be the base currency (hryvnia) — owner decision, 2026-08-22. A goal
  denominated in any other currency MUST be refused at load time, as a typed result
  whose reason names the missing FX modelling — not the currency as invalid. **Stated
  deferral (a named seam, not a closed door)**: multi-jurisdiction support is planned,
  and with it goals denominated in several currencies; §4.7's point stands that a USD
  target and a UAH target are different goals under devaluation. The refusal message
  and the declaration shape MUST NOT paint a non-base goal as impossible — merely as
  not yet modelled — and the goal record therefore keeps its currency field rather
  than assuming hryvnia implicitly.
- **FR-017**: The target sum is reported and interpreted in **nominal** terms — owner
  decision, 2026-08-22, answering §11 item 5 — stated as such on its face, with a
  defined, currently-unpopulated place for the real-terms interpretation, following
  the pattern 001 set (its FR-022) so the CPI feature can fill the slot without
  changing the result's shape. The owner did **not** opt into real terms becoming the
  default once inflation modelling exists: if that changes, it will be a new explicit
  decision, not an implication of this one.

**Shortfall honesty**

- **FR-018**: With all three variables fixed, the system MUST report feasibility: met,
  with the margin — or missed, with the binding shortfall stated as both the amount
  missing at the target date and the earliest date the target would actually be
  reached. It MUST NOT adjust any declared variable to make the goal pass.
- **FR-019**: A target that cannot be reached under the stated assumption MUST be
  reported as unreachable, as a typed result carrying the reason. The system MUST NOT
  return a capped horizon, an arbitrarily distant date, or any other nearest answer in
  its place.
- **FR-020**: A solved contribution that comes out at or below zero MUST be reported as
  "no contribution needed", with the margin, rather than as a negative contribution
  presented as an instruction.
- **FR-021**: Shortfall **probability** across scenarios (§4.7's fourth row) is
  explicitly deferred: it requires the stochastic machinery this feature does not have.
  The feasibility verdict of FR-018 is deterministic under the stated assumption, and
  the result MUST say so rather than imply a probability was assessed.

**The owner boundary and explicit failure**

- **FR-022**: Seeds and goals MUST be declared in per-owner data, separate from the
  curated market data, and every seed lot and goal MUST carry the owner identifier.
  Declaring, changing or deleting them MUST NOT touch any curated file.
- **FR-023**: Loading a seed or goal declaration MUST fail loudly on a malformed value,
  an unrecognised field, a missing required field, a duplicate identifier, or a
  reference to an undeclared instrument — naming both the file and the offending
  field. A default MUST NOT be substituted for anything absent.
- **FR-024**: The system MUST run correctly with no seeds and no goals declared,
  starting from empty positions and producing no goal results — and MUST NOT invent a
  placeholder seed, goal, contribution or starting amount in their absence. The owner's
  actual figures (§11 item 3) enter only when the owner declares them.
- **FR-025**: Every seed and goal fixture used in tests MUST be plainly labelled
  synthetic. No fixture value may be presented, stored or cached as if it were the
  owner's declaration.

### Key Entities

- **Seed declaration** — a per-owner data file listing opening lots and goals; the
  first inhabitant of the private side of the Principle VII boundary. Fails loudly on
  any malformed content.
- **Opening lot** — a declared holding lot: instrument, quantity, acquisition date,
  basis. Enters the ledger at projection start and is indistinguishable from an
  engine-witnessed lot to every invariant and every disposal thereafter.
- **Basis** — the acquisition cost of one lot, in base currency, declared explicitly as
  known or estimated. The estimated kind is the source of the basis-estimated mark.
- **Basis-estimated mark** — the propagating annotation on every figure downstream of
  an estimated basis; names its reason, is distinguishable from the unverified-source
  mark, and propagates by the same rule.
- **Goal declaration** — a per-owner statement of any two of (monthly contribution,
  target sum, target date), plus the target's currency and its nominal/real slot.
- **Growth assumption** — the explicitly stated rate a goal is evaluated against,
  carrying provenance; never defaulted. Which figure the owner points it at (for
  example the hurdle rate) is the owner's declaration, not the tool's guess.
- **Starting amount** — the explicitly stated opening balance a goal is evaluated
  from; may be declared zero, never assumed.
- **Goal solution** — the solved third variable, labelled with its mode, the
  conventions applied, its nominal framing, and every inherited mark; where the exact
  solution and the first achievable calendar date differ, both.
- **Feasibility report** — the all-three-fixed verdict: met with margin, or missed
  with the binding shortfall (amount missing, and how late), or unreachable with
  reason. A typed result, never a nearest answer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across a generated body of (contribution, sum) pairs — not a single
  example — solving the date and then solving the sum back returns the original sum
  within the single project tolerance, with zero exceptions (required test J1).
- **SC-002**: Disposal of a seeded known-basis lot reproduces a hand-computed realised
  gain within the single project tolerance, with the arithmetic checked in beside the
  assertion (required test J2, first half).
- **SC-003**: With one seed lot's basis declared estimated, 100% of the tax figures
  downstream of it carry the basis-estimated mark, and no derived figure appears
  unmarked (required test J2, second half).
- **SC-004**: Across a deliberate battery of broken declarations — missing basis,
  missing known/estimated declaration, unknown instrument, unrecognised field,
  duplicate identifier, invalid dates and quantities — every case fails naming the
  file and the field, and zero cases result in a substituted default.
- **SC-005**: Cash, lot and basis conservation hold across a large body of randomly
  generated ledgers that begin from seeded opening lots, not merely on the worked
  examples.
- **SC-006**: Every infeasible or unreachable synthetic goal in a test battery yields
  a typed report naming the binding shortfall or the reason — zero silent nearest
  answers, zero adjusted variables, zero capped horizons.
- **SC-007**: Every seed lot and goal record carries the owner identifier; deleting
  the per-owner declaration removes all of them and changes no curated file, verified
  by comparing the curated data before and after.
- **SC-008**: A run with no seeds and no goals completes with empty positions, no goal
  output, and no invented placeholder value anywhere in the result.
- **SC-009**: Every reported goal figure is labelled nominal, and the slot reserved
  for the real-terms interpretation is present and explicitly empty — never absent,
  never filled with a nominal value standing in for a real one.
- **SC-010**: A goal evaluated against a marked growth assumption produces solved
  figures that all carry the assumption's mark — 100% of them, with no unmarked
  figure downstream.

## Assumptions

- **The goal model is deterministic and explicit.** A goal is evaluated against one
  explicitly stated growth assumption and one explicitly stated starting amount, both
  with provenance. The tool does not choose the rate: pointing the assumption at the
  hurdle rate, or at anything else, is the owner's declaration. Distributional
  answers — shortfall probability across scenarios — wait for the stochastic
  machinery (FR-021).
- **Base currency only, per the resolved clarifications.** Seed bases are declared in
  hryvnia (FR-010, matching the reference shape's `cost_uah`) and goals are
  denominated in hryvnia (FR-016). Foreign-currency bases and the
  devaluation-sensitive currency of a goal are deliberately not modelled here; the
  declaration shapes must not preclude them, and the FR-016 refusal names the missing
  FX modelling rather than the currency.
- **Nominal, per the resolved clarification.** Per 001's FR-022 pattern, goal figures
  are nominal, say so, and carry a typed empty slot for the real-terms interpretation
  to be filled by the CPI feature (007) — FR-017.
- **Seeds cover instruments the engine already declares.** The worked examples seed
  the contractual fixed-income instruments that exist today. Market-priced
  instruments, venues and their valuation are later features; a venue noted on a lot
  (as in the reference's BTC example) is out of scope here, and the lot shape must not
  preclude carrying one later.
- **The owner's real figures are absent on purpose.** §11 item 3 is an open item.
  Every seed and goal in this feature is a labelled synthetic fixture; the real
  per-owner file is written by the owner when the figures exist, and nothing is
  invented meanwhile.
- **One owner.** Records carry the owner identifier per the constitution; there is no
  authentication, no second user, and no per-user storage machinery beyond the
  declared-data boundary in this feature.
- **No delivery surface.** No web interface and no command-line interface; results
  are produced and asserted by the test suite. The §4.8 note that "the UI must ask
  for an estimate" lands here as the declaration rule (FR-006): the data shape forces
  the known/estimated question that a future UI will ask.

## Clarifications resolved

All three answered by the owner on 2026-08-22.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | May an estimated basis be a point value, a range, or either? | **A single point value the owner asserts**; the range option was offered and not taken | FR-009 |
| 2 | Are non-base-currency goals accepted before FX modelling exists? | **Base currency (UAH) only**; any other currency refused at load, naming the missing FX modelling | FR-016 |
| 3 | Is the target nominal or real (§11 item 5)? | **Nominal**, per 001's pattern — labelled nominal on its face, typed empty slot for the real interpretation | FR-017 |

**The first decision records its rejected alternative on purpose.** A range-form
estimate would have let Principle I carry the owner's uncertainty all the way into the
gain and the tax as a range. The owner chose the simpler declaration instead, and the
honesty burden moves entirely onto the mark: a point-estimated basis produces
point-valued figures that are all visibly basis-estimated. If a range form is ever
wanted, it is a widening of FR-009, not a repair of it.

**The second decision is a stated deferral, not a boundary.** Multi-jurisdiction
support is planned, and with it goals denominated in several currencies — §4.7 is
explicit that a USD target and a UAH target are different goals under devaluation. The
refusal of a non-base goal therefore names what is missing (FX modelling), never what
is impossible, and the goal record keeps its currency field so the widening changes a
validation rule, not the data shape.

**The third decision does not pre-commit the future.** Nominal-with-a-typed-slot
follows 001 FR-022 so the CPI feature (007) can fill the slot without reshaping the
result. The owner did not opt into real terms becoming the default later; that would
be a new decision.

## Required tests this feature closes

Rows in `docs/REQUIRED_TESTS.md` that must be flipped, with their test paths recorded,
before this feature is done:

| Row | What it asserts |
|---|---|
| **J1** | The three goal modes are mutually consistent: date solved from (contribution, sum), then sum solved from (contribution, that date), returns the original sum |
| **J2** | A seed lot with a known basis produces the hand-computed gain on disposal; a basis-estimated seed marks every downstream tax figure |

The conservation invariants (C1–C3) are already flipped by 001; this feature extends
their generated inputs to ledgers that open from seeded lots (SC-005) rather than
adding new rows.

## Out of scope

Named explicitly so the plan does not drift into them: recommendations and the
decision layer; market-priced instruments, venues and their valuation; funding and
exit routes and income-stream integration (contributions here are stated amounts, not
routed flows); inflation and real terms (feature 007 fills the slot FR-017 reserves);
FX conversion of bases or targets and non-base-currency goals (a stated deferral —
refused naming the missing FX modelling, per the FR-016 decision, until
multi-jurisdiction support arrives); shortfall probability across scenarios and any
stochastic machinery (FR-021); the
owner's actual figures (§11 item 3); the web interface; and the command-line
interface.
