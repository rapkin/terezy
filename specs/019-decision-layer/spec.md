# Feature Specification: Dominance, and the set that has no winner

**Feature Directory**: `specs/019-decision-layer`

**Feature Branch**: `spec/019-decision-layer`

**Created**: 2026-09-02

**Status**: Drafted — four clarifications open (*Clarifications*). Planning may not start.

**Input**: The owner's question is about to produce a ranked list of 24 real ОВДП issues at
each of three horizons, ordered by one rate. A ranked list is not the honest output. This is
the first step of the constitution's order — **dominance** → distribution → break-even → point
estimate — and it produces the **non-dominated set**, with the stated assumptions its members
do not share named beside it.

---

## Why this feature exists

Section I of `docs/REQUIRED_TESTS.md` — the decision layer, the half of the product the owner
asked for — stands at 1 of 7, and the one that is closed is feasibility pruning. Everything
built so far finds options and costs them honestly. Nothing yet **decides**, and the moment
the benchmark stops refusing, the tool will start presenting an ordered list whose head reads
as a winner.

The constitution's first principle states the order of preference for any answer: *dominance →
range/distribution → break-even framing → point estimate*. `docs/DIRECTION.md` states the same
thing as a fact about the problem's shape rather than as a rule: the honest output of a
constrained multi-objective path problem is the non-dominated set with the assumption that
separates its members named, and Pareto pruning is the algorithmic form of a rule that was
written down before anyone thought about algorithms.

014 recorded the same conclusion from below, under *What this makes reachable*: the
non-dominated set rests on its FR-020 (every candidate carries its dimensions) and FR-021 (the
set is complete or refused), and **the only reason it was not built there was the measured size
of the set**. That reason has expired. 016 declared 24 real issues; the set is no longer nine
fixtures.

## The decision already taken

**Owner decision, 2026-09-02**: the synthetic ОВДП declarations leave the shipped registry, and
a **real issue becomes the benchmark** of `data/questions/fifty-thousand.toml`. That answers the
`the-benchmark-is-a-fixture` future entry, whose whole content was that the last thing between
the owner and a ranked answer is one word in his own question file; the entry closes when the
data change lands, which is not this specification.

**Throughout this document, *the shipped registry* means the registry after that change** — the
four fixtures gone and a declared issue as the benchmark. It is said once here because it is the
difference between a section that produces a comparison and a section that refuses one, and every
requirement and criterion below turns on which of those it is. What the change costs is measured
below and is almost nothing: which instrument the benchmark names decides whether a comparison
exists at all, and decides nothing about any figure in it.

## The measurement

Every count and figure below was read on **2026-09-02** by loading `data/` and answering the
declared question `fifty-thousand-hryvnia` at `as_of` 2026-09-02, through
`terezy.api.answer.answer_question` and `terezy.core.decision.answer.section_evaluated`. It is
reproducible from the repository and from nothing else. Each item was read in **both** states —
the tree as it stands today, and the tree after the owner's decision, reproduced by deleting the
four fixture declarations with their access entries and naming a declared issue as the benchmark
— and where the two differ the item says so. The registry's own counts — instruments,
streams, routes, pairs, candidates — are 014's and 015's measurements and are **cited rather
than copied**.

**1. What the fixtures' departure costs.** Of the four ОВДП fixtures carrying the `ovdp` label,
exactly **one** — `ovdp_enumerated_a` — ever produces an evaluated outcome for this question,
and only at the twelve-month horizon. So the evaluated population goes from **24, 24, 25** to
**24, 24, 24** across the three horizons, and at one and three months it does not move at all.

**2. What the benchmark's departure costs: nothing, and that is the point.** Answering the same
question with a declared issue named as the benchmark turns each section's `BenchmarkUnavailable`
into a `Comparison` over **the same outcomes**: every candidate's amount and rate is unchanged,
and the order by rate is unchanged at all three horizons. Which issue is named decides
`beats_benchmark` and nothing else — with `UA4000238281` named, **7, 15 and 9** entries of
`Comparison.ranked` beat the hurdle at one, three and twelve months.

**2a. And one of those entries is a candidate the section refuses to report.** `beats_benchmark`
and `ties` are **indices into `Comparison.ranked`**, and `ranked` is the population 014 handed to
`compare` — which 015 FR-030 then narrows, withholding a candidate whose money arrives after the
window. Measured: `inzhur_miltech` is inside `beats_benchmark` at **all three** horizons, so of
the candidates the section actually reports only **6, 14 and 8** beat the hurdle. An index into a
sequence somebody else narrowed is the defect FR-029a exists to stop reaching a reader.

**3. Ordering by the rate is not ordering by the money, at any of the three horizons.** The
sharpest case is twelve months, and it is the whole argument of this feature in one row:

| At 2026-09-01 → 2027-09-01 | reaches the endpoint | rate | money all back on |
|---|---|---|---|
| the rate's **first** place, `UA4000235865` | **49 760.50 UAH** — the least of them all | +19.79% | 2026-09-19 |
| the money's first place, `UA4000237556` | 57 846.38 UAH | +17.30% | 2027-09-04 |

Every other evaluated candidate in that section reaches at least **50 842.25 UAH**, so the
candidate the rate ranks first is last by the money that comes back. The rate is not wrong: it is
a money-weighted return over the days the money was actually invested (010 FR-015), and
`UA4000235865` matures **fifteen** days after the window opens — its final coupon and principal
both fall on 2026-09-16 — with the proceeds reaching a spendable endpoint three days later, so
the rate is measured over an eighteen-day span and a small gain over eighteen days annualises
high. What it is not is an answer to *which of these leaves
me best off in a year*: the proceeds then sit as cash to 2027-09-01 under the question's own
declared continuation assumption, earning nothing, and a further **680.64 UAH** never left the
buying venue as undeployed cash. **A ranking by that one figure puts the option that comes back
with the least money at the head of the list.**

**4. Ties are computed and never reach a reader.** At one month exactly two candidates —
`UA4000238281` and `UA4000239016` — carry rates equal within the project tolerance, and
`Comparison.ties` reports them as one tied group; the same two tie at three months, and no two
tie at twelve. **On the tree as it stands today not even that is computed**, because a section
with no benchmark produces a `BenchmarkUnavailable`, which has no tie field at all — so the tie
rule arrives with the owner's decision. And it arrives invisible: `Comparison.ties` and
`Comparison.beats_benchmark` appear **nowhere** in `src/terezy/cli/`, so the machinery that keeps
the head of a tied group from reading as a winner is computed by the core and never rendered at
the only surface a person reads.

**4a. And the only notion of closeness in the engine is the width of float rounding.** The
project tolerance is `1e-9`, defined once, and it exists so a hand-computed schedule and a
machine-computed one can agree (Principle IV). **Nothing anywhere says two figures are too close
to distinguish**, so any real difference separates two candidates: the closest pair by what
reaches the endpoint is **6.39 UAH** apart at one month on an outlay of 50 000, and the closest
non-tied pair by rate is **0.003 percentage points** apart at twelve months. Both differences are
smaller than anything these inputs support, and both would decide a dominance verdict. In the
other direction, at three and twelve months `UA4000236624` and `UA4000237416` reach **exactly**
the same amount and are separated only by the date the money is back — 2026-10-17 against
2026-11-21.

**5. The candidates in one section do not all account for the same things.** At one month,
**23** of the 24 evaluated candidates are sold at the window's end and **one** — `UA4000235865` —
matures inside it. The section carries **69** stated exclusions, three per early-exit candidate
(015 FR-033), and **none** for that one. `TupleOutcome.accounts_for` and `TupleOutcome.excludes`
are identical across all 24, so the asymmetry is visible only in the section's exclusion
records — and the one candidate carrying no early-exit exclusion is a member of every
illustrative non-dominated set computed below.

**6. What a Pareto pass over the record would produce today**, computed from
`section_evaluated` over the shipped registry as an illustration rather than as a shipped
behaviour, on the two pairs a reader is most likely to propose:

| Objectives | 1 month | 3 months | 12 months |
|---|---|---|---|
| money at the endpoint (max), money all back (min) | 2 | 3 | 10 |
| the rate (max), money all back (min) | 2 | 2 | **1** |

Every one of those six counts is the same in both states: the fixtures' departure removes
`ovdp_enumerated_a` from the twelve-month population and it was in neither front. The second pair
produces, at twelve months, a **single dominating candidate** — and it is `UA4000235865`, the one
from item 3 that comes back with the least money. A one-member
non-dominated set is a winner by another name, arrived at without a weight and without anyone
choosing one. **Which objectives the pass runs over is therefore not a detail of the
implementation; it is the decision.** CL-1.

**7. Every figure in every one of these sections is marked.** The answer reports the count of
unverified sources behind its figures — **137** on the tree as it stands, **129** once the four
fixtures leave — and 016 settled why the mark itself cannot be cleared: the price is a seller's
quotation and nobody can verify it. A dominance verdict computed over marked figures is a marked
verdict.

## What dominance is here, and the trap inside it

Candidate **A dominates** candidate **B** when A is at least as good as B on every declared
objective and strictly better on at least one. The non-dominated set is what no candidate
dominates. No weight is chosen, no criterion is traded against another, and nothing is
calibrated — which is exactly why the constitution puts it first.

Three traps, each measured above rather than supposed:

- **A rate over each candidate's own span is not a comparison over one window.** Item 3. Two
  candidates measured over spans of eighteen days and twelve months carry rates that are both
  correct and not comparable as *outcomes at the horizon*, because what happens in the gap is
  the declared continuation assumption — hold as cash, earning nothing — and the rate does not
  see it.
- **Earliness is not a return; it is liquidity.** At a fixed horizon under hold-as-cash, money
  back sooner buys nothing inside the window. It is worth something to this owner for a
  different reason he stated himself — he may need 20 000 UAH within six months — which is
  015's reserve, and a reserve verdict is a fact about *availability*, never about return.
  Treating earliness as a return term is how the twelve-month front reaches ten members.
- **Two figures that exclude different things are not comparable without saying so.** Item 5.
  Nothing in a Pareto pass notices that one member's figure carries three stated exclusions and
  another's carries none.

## Clarifications

Four questions only the owner can settle. Each is stated with its options and the consequence
of each, and with a recommendation. **Planning may not start until they are answered** — that is
what the `drafted` status means.

### CL-1 — Which objectives is the non-dominated set taken over?

[NEEDS CLARIFICATION: which criteria the dominance pass compares on, and in which direction]

The measurement's item 6 shows the answer changes the output completely, and item 3 shows why
the obvious choice is the wrong one.

| Option | What the owner gets | What it costs |
|---|---|---|
| **A. Two: the money that reaches a spendable endpoint (more is better), and the date all of it is back there (sooner is better).** | A set of 2, 3 and 10 members at his three horizons. The money figure is comparable across every candidate in a section because they share the window; the date is liquidity, which he asked about. | The rate stops being a criterion of the set. It is still reported per candidate and still ranks the list. |
| **B. Three: A plus the rate.** | The set always contains the rate's leader as well. | At twelve months that leader is the candidate returning the least money (item 3), so the set will always contain an option nobody would take. |
| **C. One: the money alone.** | A single answer per horizon: dominance degenerates to a total order and there is no set. | Throws away the liquidity dimension he stated himself, and produces exactly the winner this feature exists not to produce. |
| **D. A plus a confidence dimension** — how much of a candidate's figure rests on unverified or stale declarations. | Model risk enters the partial order rather than a footnote, which is 014's own argument about step count. | Needs an ordering over marks nobody has declared: is one unverified input worse than two stale ones? That is a new declaration and a new judgement. |

**Recommendation: A.** It is the only option in which every criterion is comparable across the
candidates being compared and answers something the owner actually said. D is the right *next*
move and should be a separate decision once there is an ordering over marks to declare.

### CL-2 — How close is "too close to call"?

[NEEDS CLARIFICATION: how wide the indifference band is, per objective, or whether there is one at all]

Principle I requires that where a range of answers scores within noise, the output is the range.
The engine has exactly one notion of closeness and it is not this one: the project tolerance is
the width of float64 rounding, not a statement about how much precision the inputs support. So
nothing says a 6.39 UAH difference on an outlay of 50 000 is too small to matter (item 4a) — on
figures that rest on a seller's quotation nobody can verify.

| Option | What the owner gets | What it costs |
|---|---|---|
| **A. A declared indifference band, one per objective, no default** — e.g. so many hryvnia on the money and so many days on the date. | Two candidates inside the band on every objective are reported as indistinguishable and neither is put ahead of the other. He decides how much precision he believes his own inputs carry. | He has to name two numbers, and a forgotten line refuses at load rather than reading as a chosen policy. |
| **B. Nothing beyond the float tolerance.** | Today's behaviour kept: candidates 6.39 UAH apart on 50 000 stay strictly ordered. | The tool asserts a difference its inputs cannot support, which is Principle I's named defect. |
| **C. Derive the band from the provenance of the inputs.** | Nobody names a number; the band follows the data's own uncertainty. | Needs an error model for every declared value — the spreads, the quotations, the schedules — and nothing in the repository has one. It would be an invented number wearing a derivation. |

**Recommendation: A**, declared per objective with no default, on the precedent of the segment
bound (004 FR-006), the staleness threshold (002 FR-028) and the candidate ceiling (014 FR-019).
C is the honest ideal and is unbuildable today; B is what happens if this question is not
answered.

### CL-3 — Borrow a portfolio-optimisation library, or not?

[NEEDS CLARIFICATION: whether a portfolio-optimisation library is adopted, given that adopting one turns determinism from a structural guarantee into a seeding discipline]

`docs/DIRECTION.md` names one as a thing to borrow rather than build, and names the catch in the
same breath: the core forbids nondeterminism and stochastic solvers bring it, so adopting one
turns determinism from a structural guarantee into a seeding discipline — *the owner's decision,
not an implementation detail*.

| Option | What the owner gets | What it costs |
|---|---|---|
| **A. No library in this feature.** | A Pareto pass is a comparison of records: no solver, no seed, no floating-point search, no new dependency in the pure core. Determinism stays structural. | Nothing yet. The question returns unchanged the day an optimiser is genuinely needed. |
| **B. Adopt one now.** | Risk metrics and optimisation routines written by people who got them right, which is worth something: the predecessor's list of hand-written metric mistakes is checked into this repository. | The catch above, plus a mismatch of subject — DIRECTION's own words are that the hard part here is the **constraint set**, not the objective, and a mean-variance optimiser solves the easy half. It also wants a return series, which no instrument in this registry has. |
| **C. Adopt one later, behind the same seam this feature establishes.** | The decision stays cheap: an objective is declared data, and what reads it is a function. | A note, and the discipline not to let the partial order acquire a weight in the meantime. |

**Recommendation: A now, C as the standing position.** State it once so the question is not
reopened by every later feature. Note what makes B genuinely tempting and where it becomes
right: the day an *allocation* over candidates is scored (I4), the search space stops being 24
records and the library's subject arrives.

### CL-4 — Which real issue is the benchmark?

[NEEDS CLARIFICATION: which declared ОВДП issue replaces `ovdp_synthetic_a` as the question's benchmark]

The owner has decided that a real issue replaces `ovdp_synthetic_a` in his question file. Which
one is his judgement and not an implementer's: the benchmark is what everything else is measured
against.

Measured (item 2), the choice is cheap and reversible: it changes **no figure and no order**,
only which candidates are reported as beating the hurdle. Options are any of the 24 declared
issues. Two rules of thumb, either of which he may reject:

- **The one he would actually buy if he did nothing clever** — that is what a naive baseline
  means, and Principle I requires naive baselines to be always scored and always shown.
- **The one whose own maturity is nearest the horizon he cares most about**, so the hurdle is a
  hold-to-maturity figure rather than an early-exit figure resting on the spread assumption.

**Recommendation: the second rule**, because a benchmark that itself rests on the observed-spread
assumption makes every *comparison against it* rest on that assumption too — and the point of a
hurdle is to be the thing you can trust while you doubt the rest.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The answer stops having a head (Priority: P1)

The owner asks the same question he already asks. For each horizon, instead of a list whose top
row reads as the recommendation, he gets the **set of candidates nothing dominates** on his
declared objectives, and every other evaluated candidate is reported as dominated, naming a candidate
that dominates it.

**Why this priority**: it is the feature. The constitution puts dominance before every other
form of answer, and the shipped output is one place away from presenting a point estimate as a
verdict.

**Independent Test**: answer the owner's question over the shipped registry with the declared
objective set and assert that each section reports a non-dominated set, that every evaluated
candidate lands in exactly one of FR-008's three populations — in the set, dominated by a named
member, or not placed — and that no candidate lands in two.

**Acceptance Scenarios**:

1. **Given** a section with evaluated candidates and a declared objective set, **When** the
   dominance pass runs, **Then** every evaluated candidate is in exactly one of FR-008's three
   populations — non-dominated, dominated with at least one dominating candidate named, or not
   placed with the objective it could not be read on.
2. **Given** the non-dominated set, **When** it is read, **Then** it is in the same total order
   014 FR-016 fixes for the candidate set, and no member is presented ahead of another as better.
3. **Given** a candidate that dominates another, **When** the record is read, **Then** it names
   which objectives it was at least as good on and which one it was strictly better on.
4. **Given** the same question and registry answered twice, **When** the two sets are compared,
   **Then** they are equal member for member and in the same order.

---

### User Story 2 — Too close to call is reported as too close to call (Priority: P1)

Where two candidates differ by less than the owner's declared indifference band on every
objective, neither is reported ahead of the other: each is shown with the candidates it cannot be
told apart from.

**Why this priority**: equal-highest, and it is Principle I's own sentence — *reporting 51.3%
when anything in 40–60% is indistinguishable is a defect, not a rounding choice*. Measured, the
engine today has the machinery to say two things are tied and no surface that says it.

**Independent Test**: two candidates inside the declared band on every objective are reported as
indistinguishable from each other; widening the gap past the band on exactly one objective turns
that into a dominance verdict; and the CLI output shows the relation.

**Acceptance Scenarios**:

1. **Given** two candidates within the declared band on every objective, **When** the set is
   read, **Then** each names the other as indistinguishable, neither is ahead of the other, and
   the bands that produced the verdict travel with it.
2. **Given** a candidate with indistinguishable neighbours, **When** the CLI renders the answer,
   **Then** the relation is visible — not left to be inferred from adjacent rows in a list a
   reader will read as ordered.
3. **Given** three candidates in which the first and second, and the second and third, are within
   the band while the first and third are not, **When** the result is read, **Then** it reports
   exactly those two facts and **no** partition into groups (FR-011a).
4. **Given** an existing tied group from 010's tie rule, **When** it is read beside this
   feature's relation, **Then** the two are distinguishable and neither is presented as the other:
   one says two rates agree to the last bits, the other says a difference on every declared
   objective is smaller than the owner believes his inputs can support.

---

### User Story 3 — The set is reported against the hurdle, whether or not it holds up (Priority: P1)

The benchmark is one of the candidates. The answer says whether it is itself non-dominated, which
members dominate it, and — when none does — says plainly that nothing dominates the hurdle.

**Why this priority**: Principle I requires naive baselines always scored and always shown, and
010 FR-011 and FR-012 already put the hurdle inside the ranking rather than beside it. A
dominance pass that reported a set without saying where the hurdle sits in it would reintroduce
the privileged side channel one layer up.

**Independent Test**: over the shipped registry, assert that the benchmark appears exactly once
among the evaluated candidates and that its dominance standing is reported; then, on a fixture in
which nothing dominates the benchmark while other members stand beside it in the set, assert the
*nothing dominates the hurdle* statement is produced — and that it is **not** produced on a
fixture where something does.

**Acceptance Scenarios**:

1. **Given** a section whose benchmark is dominated, **When** the answer is read, **Then** the
   members that dominate it are named.
2. **Given** a section in which nothing dominates the benchmark, **When** the answer is read,
   **Then** it says so plainly and the benchmark is in the reported set.
3. **Given** a section carrying `BenchmarkUnavailable`, **When** the dominance pass runs,
   **Then** it produces a typed refusal rather than a set: without the hurdle among them, a set
   of survivors is a shortlist nobody can measure.
4. **Given** the one-dimensional *beats the benchmark* verdict 010 already computes, **When** it
   is reported beside the dominance standing, **Then** the two are separate fields, each labelled
   with the figure and the closeness rule behind it, and where they disagree the disagreement is
   on the record rather than resolved (FR-013).

---

### User Story 4 — What separates the members is named (Priority: P2)

Where the set has more than one member, the answer names the **stated assumptions the members do
not share** — so a reader can see that the choice between two options is a choice between two
beliefs rather than between two numbers.

**Why this priority**: P2 because Stories 1–3 must exist first, and it is `DIRECTION.md`'s own
formulation of what an honest output is. Measured under **both** illustrative objective pairs of
the measurement's item 6, the one-month set contains a candidate that rests on the observed-spread
assumption and one that does not; whether the owner's own set does is CL-1's to settle.

**Independent Test**: a set whose two members rest on different stated assumptions reports the
difference; a set whose members rest on identical assumptions says that plainly rather than
reporting an empty list a reader would read as *nothing separates them*.

**Acceptance Scenarios**:

1. **Given** a set of two members resting on different stated assumptions, **When** it is read,
   **Then** the assumptions each rests on and the other does not are named, by the id and words
   the core record already carries.
2. **Given** a set whose members rest on exactly the same assumptions, **When** it is read,
   **Then** it says the members are separated by no stated assumption — which is a finding, not
   an absence.
3. **Given** two members whose section-level exclusions differ, **When** the set is read,
   **Then** the difference is named, because two figures accounting for different things are
   being placed side by side.
4. **Given** any such report, **When** it is read, **Then** it does **not** claim which
   assumption decides between the members: that needs re-evaluation under a changed assumption,
   which is required test I5's feature and is deliberately not built here.

---

### User Story 5 — The objective set is declared, and the answer records which one it used
(Priority: P2)

The objectives are the owner's, in a file, with no default, and the question names which set it
is answered under. Two questions alike but for that name produce two different answers over one
candidate set, and each answer's manifest records which set produced it.

**Why this priority**: P2 in order, but it is the row this feature closes (**I2**) and the thing
that keeps a criterion from being a constant in the engine. *The owner picks, the tool never
assumes* is `SIMULATOR_SPEC.md` §4.10.3's own heading.

**Independent Test**: two questions differing only in the objective set they name, over one
registry, produce two different non-dominated sets, and the manifest of each names the objective
file it read with its digest.

**Acceptance Scenarios**:

1. **Given** a registry with no declared objective set, **When** a question is answered,
   **Then** it fails at load naming the file and what is missing. A forgotten line never reads
   as a chosen policy.
2. **Given** two questions alike in everything but the objective set they name, **When** each is
   answered, **Then** the two non-dominated sets differ and each answer's manifest names its own
   objective file.
3. **Given** an objective naming a criterion the closed set does not contain, **When** it is
   loaded, **Then** it fails naming the file, the field and the criteria that exist.
4. **Given** an objective set, **When** the answer is read, **Then** the objectives are on the
   answer beside every dominance verdict they produced, as 014 FR-012 puts the question beside
   every count.

---

### Edge Cases

- **One evaluated candidate** — a non-dominated set of one, and it is *not* a winner: the record
  says the set has one member because one candidate was evaluated, which is a different fact
  from one candidate dominating others. The two must not render the same.
- **No evaluated candidates** — an empty set is a legitimate value meaning the section evaluated
  nothing, and it is distinct from a refusal, on the `Enumeration`-versus-`CompositionRefused`
  precedent 014 inherited from 004.
- **Every candidate non-dominated** — a set the size of the population. Honest and useless, and
  it is the signal that the declared objectives are not discriminating; the count is reported so
  the owner can see it rather than being protected from it.
- **A candidate with no comparable rate** — where an objective reads a figure a candidate does
  not carry (010's `RateNotComparable`), the candidate is reported as *not placed*, with the
  objective and the missing figure named. It is neither dominated nor non-dominated, and it is
  never dropped.
- **Amounts in two currencies in one section** — the **pair** is incomparable, not the section:
  the two candidates yield no verdict between them, recorded with the objective and both
  currencies named, while every same-currency pair around them is decided normally (FR-008a).
  Principle VI: values in different currencies are never silently combined, and *more money* is
  not a question across a rate nobody declared — but that is a fact about two candidates, and
  refusing the whole section for it would drop 23 verdicts to report one absence, against FR-009.
- **The section withheld a candidate** — 015 FR-030's `arrives_after_horizon` population is not
  in the dominance pass, because its figure was withheld from the reader. Measured,
  `inzhur_miltech` is withheld from every section of the owner's question.
- **A tie under 010's rule and indistinguishability under the declared bands** — two different
  relations over two different figures, and neither contains the other: 010's is the rate agreeing
  to the last bits, and this one is closeness on **every** declared objective, which need not
  include the rate at all. Both are reported, and a reader who sees only one cannot tell whether
  two figures agree or merely fail to differ enough to matter.
- **An indifference band wider than the whole spread of a section's figures** — every candidate
  indistinguishable from every other, so nothing dominates anything and the set is the whole
  population. Legitimate and worth seeing: it says the question cannot be answered at that
  precision from these inputs.
- **A dominated candidate that dominates nothing and is dominated by exactly one** — reported
  with that one named. The relation is not a ranking and a candidate may be dominated by several.

## Requirements *(mandatory)*

### The objectives are declared

- **FR-001**: The objectives a dominance pass runs over MUST be **declared data** under
  `data/objectives/`, owner-scoped, with **no default**: a run with no declared objective set
  MUST fail at load naming the file and the field, on the precedent of the segment bound (004
  FR-006), the staleness threshold (002 FR-028) and the candidate ceiling (014 FR-019).
- **FR-001a**: The **question** MUST name which declared objective set it is answered under, as
  a field with no default, refusing at load when it names none or names one the registry does not
  declare. That is a change to 015's question schema, and it is where the choice belongs: a
  question is a declaration (015's owner decision), so the objective set is covered by the
  question file's own digest and *the answer I got last March* stays reproducible from an
  artefact. It is deliberately **not** a parameter of the verb like `as_of`, which is excluded
  only because it is a clock.
- **FR-002**: An objective MUST name a **criterion** drawn from a closed declared set, and a
  **direction** — more is better, or less is better. A criterion naming a figure the outcome
  record does not carry MUST fail at load naming the criterion and the figure.
- **FR-003**: The criterion set MUST be closed, and widening it MUST be a reviewed source change
  rather than a data change — stated plainly rather than left to be discovered, because it is the
  one place this feature is **not** data-only. A criterion is a *reader over a computed figure*,
  so a new criterion is a new figure or a new way of reading one, and both are code. What is
  data is **which** criteria the owner compares on and in which direction, which is the whole of
  the choice CL-1 puts to him.
- **FR-004**: `data/objectives/` MUST NOT acquire a citation requirement: it is already named in
  `scripts/check_provenance.py`'s `EXEMPT_DIRS` with the reason that an objective set is a stated
  preference and not an observation. If a number describing the world is ever needed here, it
  moves to a sourced directory rather than the exemption widening.
- **FR-005**: An objective set MUST NOT carry a **weight**, a **score**, a coefficient, a
  priority order or any means of trading one criterion against another. Required test **B12**
  forbids a non-standard composite driving the primary user-visible ordering, and a weighted sum
  of two objectives is exactly that. A partial order is what makes this step need no calibration.

### The dominance pass

- **FR-006**: The system MUST compute, for one horizon section, the **non-dominated set** over
  the candidates that section **evaluated** — the population `section_evaluated` defines, which
  is 014's evaluated set less the candidates 015 FR-030 withheld. A candidate whose figure was
  withheld from the reader MUST NOT decide another candidate's standing.
- **FR-007**: A candidate **dominates** another when it is **at least as good on every declared
  objective** — not worse by more than **the project's own closeness comparison allows**, which is
  the one tolerance policy Principle IV puts in a single place — **and better on at least one by
  more than that objective's declared indifference band** (FR-011). The weak half goes through the
  project comparison rather than a bare one because a last-bit difference on one objective would
  otherwise withdraw a dominance verdict a five-thousand-hryvnia gap on another had earned,
  leaving a dominated candidate standing in the set; and it goes through *that* comparison rather
  than a fresh absolute one because a second rule for when two amounts are the same money is a
  second tolerance policy, which Principle IV forbids.
  **The slack it allows is therefore not a constant.** `TOLERANCE` is applied as a relative *and*
  an absolute bound, so on figures of the size this question deals in the slack is orders of
  magnitude wider than the constant — the tolerance module says so in its own words. Everything
  FR-011c states about the band is stated against **that slack**, never against the constant, and
  writing the floor in units of `1e-9` would be a guarantee that guarantees nothing.
  **What the split buys is the width of the window in which a cycle is possible, not its
  absence.** With the band in both halves the window is *(p − 1)* **bands** wide — it scales with
  the band, so no floor on the band ever closes it once *p ≥ 3*. With the slack in the weak half
  the window is *(p − 1)* **slacks** wide, which a floor on the band can close, and FR-011c is
  that floor. Measured 2026-09-03, over 400 000 draws per objective count of three to five
  candidates whose every figure is uniform on `[−6, 6]` with the slack taken as 1 and the band at
  the floor: the rejected definition leaves an empty set over a non-empty placed population **13**
  times at *p* = 3 and **49** at *p* = 4, and **never** at *p* = 2. The accepted definition: never,
  at any of the three. *Never at two objectives* is a theorem rather than a sample — with the band
  in both halves a cycle needs `2k_j < L` on every objective, and summing gives `K < L` against
  `K ≥ L` — and it is why FR-011c's ***(p − 1)* factor** is vacuous at *p* = 1 and 2 and load-bearing above.
  Its **first** clause — the band strictly exceeds the slack — is load-bearing at every *p*,
  including two: at a slack of 1 and a band of 0.5, two candidates differing by `(0.8, −0.8)`
  dominate **each other**, and the set is empty over a population both of whose members are
  placed.
  So the relation is **irreflexive** while FR-011b holds, and **asymmetric and acyclic** while
  FR-011c's floor does — the second pair rests on the floor and not on positivity, which is worth
  keeping straight because only the first is checkable at load. Together they are what makes the
  set never empty while the **placed** population is not (SC-004).
  **Transitive it is not**, for any band, and the claim is not made: slack does not compose, so
  *A ≻ B* and *B ≻ C* leave *A ≻ C* free to fail. Acyclicity is what the emptiness guarantee
  needs and transitivity is not, which is why only one of them is asserted. The definition MUST
  live in exactly one place.
- **FR-008**: Every evaluated candidate MUST land in exactly one of three populations, and the
  three MUST be **separately counted** and disjoint: **non-dominated**, **dominated** — carrying
  at least one dominating candidate's key and the objectives that decided it — and **not
  placed**, a candidate no pair involving it could be decided on. The identity *evaluated =
  non-dominated + dominated + not placed* MUST be an asserted check rather than a claim in prose
  (014 FR-009's rule).
- **FR-008a**: Where a **pair** cannot be compared on an objective — one candidate carries no
  such figure (010's `RateNotComparable`), or the two deliver different currencies — that **pair**
  MUST yield no verdict and MUST be recorded as **incomparable**, naming the objective and what
  made it so. It MUST NOT refuse the section, and it MUST NOT remove either candidate from any
  other pair's verdict: incomparability is a property of two candidates, and a candidate is *not
  placed* only when **every** pair involving it is incomparable.
- **FR-009**: The pass MUST **prune nothing and drop nothing**. Every evaluated candidate's
  outcome remains reported with its figures; dominance is a reported relation over the set, never
  a filter applied to it. A dominated candidate is one the owner may still choose, for a reason
  no declared objective carries.
- **FR-010**: The pass MUST add **no feasibility rule**. A candidate is infeasible only for a
  member of 010's `TupleRefused` union (014 FR-006), and this feature MUST NOT contain a
  pre-screen, a cheap filter, an early exit, or a reason of its own to consider a candidate
  unavailable.

### Never a number more confident than its inputs

- **FR-011**: An **indifference band** MUST be declared per objective, as data, with **no
  default**, and MUST be what FR-007's strictness is measured against. Two candidates within the
  band on **every** objective are **indistinguishable**, and the result MUST report that as a
  **symmetric relation over pairs** — per candidate, the candidates it is indistinguishable from.
- **FR-011a**: The result MUST NOT present a **partition into groups**. Closeness within a band is
  not transitive, so no partition exists, and any procedure that produces one depends on an order
  the objectives do not fix: with declared bands of 6 on money, candidates at 100, 105 and 110
  fall into `{100, 105}` or `{105, 110}` according to which one an implementation anchors on —
  and FR-025 orders by 014 FR-016's candidate key, so the anchor would be an instrument id.
  `core/primitives/tolerance.py::tied_groups` may anchor precisely because it runs over a sequence
  sorted by the **one** figure it groups; a pass over several objectives has no such sequence,
  which is why the relation is reported and the partition is refused.
- **FR-011b**: A declared band MUST be **finite and strictly positive**, refused at load naming
  the file and the field. A **negative** band makes FR-007's relation reflexive, and a candidate
  that dominates itself empties the set SC-004 requires to be non-empty. A band of **zero** does
  not do that — it can simply never exceed the slack, so it can never clear FR-011c's floor, and
  refusing it at load says so at the file rather than at the run.
- **FR-011c**: A band MUST additionally clear an **acyclicity floor**: it MUST be strictly greater
  than the slack FR-007's weak half allows on that objective's figures, and at least *(p − 1)*
  times that slack, where *p* is the number of declared objectives. Below the floor a cycle is
  possible — the slack does not compose, so around a cycle it accumulates once per objective —
  and a cycle empties the set over a population every member of which is placed. **A floor of one
  slack is not enough**: at three objectives and a band of one and a half slacks, `(0, 0, 0)`,
  `(−1.6, 0.8, 0.8)` and `(−0.8, −0.8, 1.6)` form a three-cycle with every candidate placed and
  the set **empty**, verified 2026-09-03. It is stated in the objectives' own count because a
  cycle's length runs to the size of the population and bounds nothing.
  **This check cannot live at load, and that is the requirement rather than an inconvenience.**
  The slack is not a constant (FR-007): it depends on the magnitudes of the figures being
  compared, which a declaration file does not know. So the floor MUST be checked where those
  figures are — in the pass — and a band that fails it MUST produce a typed **refusal** naming the
  objective, the declared band and the slack it did not clear (FR-026), never a set computed under
  a relation whose acyclicity nobody established. A load-time check written against the bare
  constant would pass a band five orders of magnitude too small and guarantee nothing.
- **FR-012**: The declared band MUST be **distinguishable from the project tolerance** wherever
  either is reported, and MUST NOT be implemented by loosening it. The project tolerance is the
  width of float64 rounding and is defined in exactly one place (Principle IV); an indifference
  band is a statement about what the *inputs* support. Conflating them would put a modelling
  judgement inside the constant that exists so hand arithmetic and machine arithmetic can agree.
- **FR-013**: **Two verdicts about the hurdle exist and they answer different questions**, and
  the answer MUST carry both, each labelled with the figure and the closeness rule that produced
  it: 010's `beats_benchmark` — strict, one-dimensional, on the **rate**, at the **project
  tolerance** — and this feature's standing, a partial order over the **declared objectives** at
  the **declared bands**. Neither MUST be derived from, restated as, or rendered as the other.
  Where the two **disagree** — a candidate beats the hurdle on the rate and is indistinguishable
  from it on every declared objective — the disagreement MUST be reported as such and MUST NOT be
  resolved, because resolving it needs a weight (FR-005). Under CL-1's recommended objectives the
  rate is not among them, so the disagreement is not an edge case but the ordinary state.
- **FR-014**: Where the reported set has one member, the record MUST say **why**, against
  FR-008's populations rather than in prose: the section evaluated one candidate; or every other
  evaluated candidate is dominated; or every other is *not placed*; or some mixture, in which case
  the counts say which. Only *every other is dominated* is a finding, and the cases MUST be
  distinguishable without reading prose. *Dominates every other* is deliberately not the wording: dominance is
  reported per pair, and a member can be the only survivor without being the dominator named on
  every other candidate's record.
- **FR-015**: Two candidates whose figures **exclude different things** MUST have that difference
  reported wherever they appear in one set. Measured, a section's stated exclusions differ per
  candidate while `TupleOutcome.excludes` does not, so the comparison MUST read the section's
  exclusion records and not the outcome's fixed set.

### The benchmark

- **FR-016**: The benchmark MUST be a **member** of the population the pass runs over, exactly
  once, and MUST be scored by the same comparison as every other member (010 FR-012, 014 FR-022).
  It MUST NOT be evaluated separately, held aside, or appended.
- **FR-017**: The result MUST state the benchmark's own standing: non-dominated, or dominated
  with the members that dominate it named. Where **nothing dominates the benchmark**, the result
  MUST say so as its own typed statement — this is Principle I's *when nothing beats them the tool
  says so plainly*, in the only terms a partial order can carry it. The statement MUST be
  worded as *nothing dominates the hurdle* and MUST NOT be worded as *the hurdle is best*: other
  members may sit beside it in the set, better on one objective and worse on another, and a
  hurdle that dominates everything is a different and stronger fact.
- **FR-018**: A section carrying `BenchmarkUnavailable` MUST produce a typed **refusal** from
  this pass rather than a set. Without the hurdle among them, a set of survivors is a shortlist
  with nothing to measure it against, and its head reads as a winner — which is the argument 010
  FR-011 already made one layer down and this feature MUST NOT undo one layer up.
- **FR-018a**: A section whose **benchmark was withheld** under 015 FR-030 MUST produce a refusal
  too, naming the benchmark and the date its money arrives, and it MUST be a **different reason**
  from FR-018's. This is the case a reader misses and the one FR-016 cannot otherwise satisfy: the
  comparison is a `Comparison` rather than a `BenchmarkUnavailable`, so every figure is there, the
  benchmark is not in the population this pass runs over, and nothing refuses. It is not a new
  judgement — `core/decision/answer.py::section_ranking` already withholds the *ranking* in
  exactly this case, in its own words, and this is that rule applied to the set.

### What separates the members

- **FR-019**: Where the set has more than one member, the result MUST name the **stated
  assumptions the members do not share**, by the ids and the words the core records already carry
  (010's `rests_on`, 015's stated exclusions), **verbatim**. It MUST NOT compose a sentence of
  its own.
- **FR-020**: Where the members rest on exactly the same stated assumptions, the result MUST say
  so as a typed statement rather than reporting an empty list, which a reader takes as *nothing
  separates them* when the truth is *the same beliefs are behind all of them*.
- **FR-021**: The result MUST NOT claim which assumption **decides** between two members. Naming
  the deciding assumption requires re-evaluating the set under a changed assumption, which is
  required test **I5**'s feature; this feature reports the assumptions that differ and states
  that it has not tested which of them would flip the order. An unwarranted claim about a
  deciding belief is a number more confident than its inputs wearing a sentence.

### Provenance, purity, determinism

- **FR-022**: A dominance verdict MUST carry the union of the provenance marks and the merged
  staleness verdict of **both** candidates it relates, so a verdict never looks cleaner than the
  figures behind it. Principle I's propagation rule applies to a comparison exactly as it applies
  to a figure: *A dominates B* computed from two unverified figures is an unverified claim.
- **FR-023**: The result MUST carry the whole declared objective set and the declared bands
  beside every population it counts (014 FR-012's rule, one layer up). A dominance count read
  without the objectives that produced it is meaningless, and the objectives are the one input a
  reader is most likely to assume.
- **FR-024**: The pass MUST be pure and deterministic: no clock, no I/O, no randomness, no
  solver, no seed. The same section and the same objective set MUST produce an equal result,
  field for field, and loading the declarations in a different file order MUST change nothing
  (014 FR-016, 015 FR-027).
- **FR-025**: The non-dominated set and every reported population MUST be **totally ordered** by
  the order 014 FR-016 already fixes over candidates, and MUST NOT be ordered by any objective —
  because an order by an objective is the ranking this feature exists to refuse to present.
- **FR-026**: Every refusal MUST be a **typed record carrying its reason**, returned instead of a
  set: no empty set standing for a failure, no partial set, no `None`. The refusals this feature
  needs are a section with no benchmark (FR-018), a section whose benchmark was withheld
  (FR-018a), and a declared band that does not clear its acyclicity floor against the figures
  actually compared (FR-011c). **Two things a reader expects here are deliberately not refusals.** A missing or
  undeclared objective set is a **load failure** (FR-001, FR-001a), and a runtime refusal for it
  would be a second answer to a question the loader has already refused. A figure that cannot be
  compared is a property of a **pair** (FR-008a), and refusing the section for it would drop every
  verdict around it, against FR-009.

### The answer, and the surface a person reads

- **FR-027**: The dominance result MUST be carried on the **horizon section**, beside the survey
  015 FR-014 carries whole, and MUST NOT replace, reorder or summarise it. Every figure the
  section already reports stays reported.
- **FR-028**: The `Answer` MUST NOT acquire a composed sentence, a headline or a verdict phrase
  (015 FR-020). Every string this feature adds is an id, a criterion name, or a reason a core
  record already carries.
- **FR-029**: The command-line surface MUST render **all three** of FR-008's populations — the
  non-dominated set, the dominated population with what dominates each member, and the *not
  placed* population with what could not be read — plus the incomparable pairs, each candidate's
  indistinguishable neighbours, the benchmark's standing, and 010's existing tie groups and
  beats-the-benchmark verdict, none of which reach a reader today. All three populations, because
  FR-014 requires *every other candidate is dominated* and *every other is not placed* to be
  distinguishable **on the record**, and a surface that renders two of three makes them
  indistinguishable to the one person who reads it — which is this feature's own defect one level
  down. The requirement is this one's; FR-014 says nothing about a surface. A ranking rendered without
  its tie groups is the same defect, printed.
- **FR-029a**: What is rendered from 010's `ties` and `beats_benchmark` MUST be **resolved to
  candidates and restricted to the population the section reports**. Both are indices into
  `Comparison.ranked`, which 015 FR-030 narrows afterwards, so rendering them as they stand puts a
  withheld figure in front of a reader, against 015 FR-030 and the rendering half of SC-016 —
  measured, `inzhur_miltech` is
  inside `beats_benchmark` at all three of the owner's horizons (measurement item 2a). Every count
  derived from either MUST be over the reported population, and where the two differ the
  difference MUST be visible rather than silently taken.
- **FR-030**: The run manifest MUST record the declared objective set as an input reference with
  its digest, so that two answers differing only in their objectives are distinguishable from
  their manifests (required test **I2**, and Principle III's *a result without a manifest is not a
  result*). `terezy.data.manifest`'s `InputKind` is a closed set with no member for an objective
  set, so **widening it is required work in the data layer**, made and reviewed there.

## Key Entities

- **Objective** — a declared criterion and a direction, plus its indifference band. The owner's
  preference, not an observation. Carries no weight (FR-005).
- **Objective set** — the declared collection of objectives one dominance pass runs over,
  identified and digested like any other declaration.
- **Dominance verdict** — one ordered pair: which candidate dominates which, on which objectives
  it was at least as good, on which it was strictly better, and the merged provenance **and
  staleness verdict** of both (FR-022).
- **Non-dominated set** — the members no evaluated candidate dominates, in the candidate set's
  own total order, with the benchmark's standing among them. Single-member is a legitimate value
  whose meaning FR-014 requires be stated; empty is legitimate only where the placed population is
  empty too (FR-008, SC-004), and anywhere else it is the cycle FR-011c's floor exists to prevent.
- **Indistinguishability** — a symmetric relation over pairs: two candidates within the declared
  band on every objective. Reported per candidate as the neighbours it cannot be told apart from,
  never as a partition, because the relation is not transitive (FR-011a). Distinct from 010's
  tolerance tie, which is about float arithmetic (FR-012).
- **Incomparable pair** — two candidates **some** objective could not decide between: a missing
  figure, or two currencies. One objective suffices, because FR-007's weak half has to hold on
  every objective. A property of the pair, recorded with its reason (FR-008a) — and distinct from
  *not placed*, which is the *every*-pair condition below.
- **Not placed** — an evaluated candidate every pair involving which is incomparable. Neither
  dominated nor non-dominated, never dropped.
- **Separating assumptions** — the stated assumptions the set's members do not share, carried
  verbatim. Explicitly not a claim about which one decides (FR-021).
- **Dominance refusal** — the pass did not stand up, and there are three ways: the section has no
  benchmark (FR-018), its benchmark was withheld (FR-018a), or a declared band does not clear its
  acyclicity floor against the figures compared (FR-011c). A different type rather than a weaker
  set, on `CompositionRefused` and `BenchmarkUnavailable`'s precedent. **A missing
  objective set is not one of them** — that is a load failure (FR-001, FR-001a) — and neither is a
  figure that cannot be compared, which belongs to a pair (FR-008a).

## Success Criteria *(mandatory)*

- **SC-001**: Answering the owner's declared question over the shipped registry with a declared
  objective set produces, in every section, a reported non-dominated set and the accounting
  identity of FR-008 holding — every count derived from the registry and the objectives the test
  loads, never hard-coded.
- **SC-002**: **A** pair of questions differing only in the objective set they name (FR-001a),
  over one registry, produces **different** non-dominated sets, and each answer's manifest names
  its own objective file with its own digest. A chosen pair rather than any pair: two objective
  sets may honestly agree, and the criterion is that a disagreeing pair exists and is pinned. Both halves are one criterion because I2 is one row: an objective that changes the
  answer without being recorded is a run nobody can reproduce.
- **SC-003**: A registry with no declared objective set fails at load naming the file and the
  field; an objective naming a criterion outside the closed set fails naming the field and the
  criteria that exist; an objective with no direction fails; a question naming no objective set,
  or one the registry does not declare, fails (FR-001a); and a band that is negative, zero or
  infinite fails at load (FR-011b). One assertion per case. **The acyclicity floor is not among
  them** and its criterion is SC-004's: FR-011c states why it cannot be checked at load, and a
  case here would be a check written against a constant that decides nothing.
- **SC-004**: Over generated candidate sets and bands drawn at or above FR-011c's floor, the
  dominance relation is **irreflexive, asymmetric and acyclic**, the non-dominated set is **never
  empty while the placed population is not**, and no candidate appears in two of FR-008's three
  populations. The emptiness half is scoped to *placed* deliberately: a *not placed* candidate is
  in the population and in neither of the other two, so a section all of whose candidates are not
  placed has an empty set honestly (FR-008).
  **The generator MUST produce at least three objectives**, and the reason is FR-007's
  measurement, which is stated there and not restated here: the definition FR-007 rejects cannot
  empty the set at two objectives **at all**, so a two-objective battery passes under both
  definitions and proves nothing, while a three-objective one separates them by random draw rather
  than by construction.
- **SC-004a**: Non-transitivity is pinned by a **planted witness**, not asserted over generated
  inputs: a triple for which *A ≻ B* and *B ≻ C* hold and *A ≻ C* does not. It is existential
  where SC-004's properties are universal, and asserting it the same way would fail on correct
  code, which is transitive on most triples. It earns its place because an implementation that
  quietly strengthened FR-007's weak half into a bare comparison would become transitive and pass
  every criterion above.
- **SC-005**: A scan asserts that no module in this feature constructs, matches on or raises a
  feasibility verdict, and that no declared objective carries a weight, a coefficient or a
  priority — FR-005 and FR-010 stated as checks rather than as rules to remember (014 SC-006's
  technique).
- **SC-006**: Two candidates placed inside the declared band on every objective are reported as
  indistinguishable from each other; moving one of them past the band on exactly one objective
  replaces that with a dominance verdict. The pair is the criterion: the first half alone passes
  for an implementation that calls everything indistinguishable. A third case pins FR-011a — three
  candidates whose closeness does not chain produce two pairs and **no** partition, asserted in
  both candidate-key orders so a partition built by anchoring fails.
- **SC-007**: A scan asserts the two closeness rules are used only where they belong: the
  project's comparison in FR-007's weak half and in FR-011c's floor check — those two sites and no
  other — and the declared bands in FR-007's strict half and in the indifference relation, neither
  read where the other belongs (FR-012). And a band that clears FR-011b's load-time check but not
  FR-011c's floor produces the typed refusal rather than a set, which is the criterion that would
  otherwise have nothing asserting it. 010's
  tie groups are read off the comparison record this feature carries through, never recomputed
  here (FR-013). Stated this way rather than as a blanket ban on importing the tolerance, which
  an earlier draft said and which FR-007 makes impossible to satisfy.
- **SC-008**: The benchmark appears exactly once in the population the pass runs over, its
  standing is reported in every section, and a registry in which nothing dominates it produces
  the *nothing dominates the hurdle* statement rather than a set with no comment on the hurdle.
  The wording is part of the criterion: *beats* is 010's one-dimensional verdict on the rate, and
  FR-013 forbids restating it as the dominance standing.
- **SC-009**: A section carrying `BenchmarkUnavailable` produces a typed dominance refusal
  carrying that record's own reason verbatim, and **no** set — asserted by a string comparison so
  the reason cannot be rewritten (014 SC-008's technique).
- **SC-009a**: A section whose benchmark is withheld under 015 FR-030 — its comparison a
  `Comparison`, every figure present, the benchmark absent from the population — produces a
  dominance refusal naming the benchmark and the date its money arrives, and **its reason differs
  from** the one SC-009's section produces, asserted by comparing the two records rather than by
  reading them. The pair is the criterion: the case has no natural test and is the one FR-018a
  calls the case a reader misses.
- **SC-010**: A set of two members resting on different stated assumptions names the difference,
  by ids and words compared byte-for-byte against the records they came from; a set whose members
  rest on identical assumptions produces the typed *no stated assumption separates them*
  statement; and a set whose members carry **different section-level exclusions** names that
  difference too (FR-015, FR-019) — asserted on a fixture whose set has two such members, because
  whether the owner's own one-month set has two depends on CL-1's answer and a criterion may not
  rest on an open clarification. All three, because each is a different way for the same
  requirement to be quietly unimplemented.
- **SC-011**: A scan asserts this feature makes no claim about which assumption decides between
  two members: no record carries a deciding-assumption field, and no string it produces asserts
  one (FR-021).
- **SC-012**: Every dominance verdict computed from a marked figure carries the mark, verified by
  a **walk over the whole result** rather than by sampling — the propagation half is 010 SC-007's
  rule and the walk-rather-than-sample half is 010 **SC-009**'s, which 015 SC-017 cites as SC-007's
  and this corrects rather than copies. On the
  shipped registry every verdict is marked, because every figure is.
- **SC-013**: A candidate for which an objective can read no figure produces an incomparable pair
  against every other candidate, naming the objective and the figure; where that is true of every
  pair it is reported *not placed*, in neither of the other two populations; and in both cases it
  appears in the section's reported figures unchanged (FR-008a, FR-009).
- **SC-014**: In a fixture section whose candidates deliver two currencies, every cross-currency
  **pair** is recorded incomparable naming the objective and both currencies; every same-currency
  pair is still decided; a candidate with both kinds of pair is **not** in the *not placed*
  population, which is the only case that exercises FR-008a's *only when every pair*; and no
  exchange rate is consulted anywhere (015 FR-021's rule). All four together: an implementation
  that marks every pair incomparable passes the first, and one that marks a candidate *not placed*
  on any incomparable pair passes the first two. Asserted on a fixture, because the shipped
  registry has one spendable endpoint.
- **SC-015**: A candidate the section withheld under 015 FR-030 is in **no** dominance population
  and decides no other candidate's standing — asserted on `inzhur_miltech`, which the owner's own
  question withholds from every section.
- **SC-016**: Rendering the answer produces output in which all three of FR-008's populations,
  the incomparable pairs, each dominated candidate's dominator, each candidate's indistinguishable
  neighbours, the benchmark's standing, 010's tie groups and 010's beats-the-benchmark verdict all
  appear — asserted by finding each in the output, and asserted to name **candidates rather than
  positions** and to mention no candidate the section withheld (FR-029a). Two sections differing
  only in whether the rest of the population is dominated or *not placed* render differently,
  which is FR-029's own requirement rather than FR-014's. The last two items are the regression: the core computes them and no reader has
  ever seen them.
- **SC-016a**: The section carries the dominance result **beside** the survey and changes nothing
  in it: the survey a section reports equals, field for field, the one 014's `survey` returned for
  that section — every figure, every refusal, every order (FR-027). Stated against the survey the
  pass was **handed** rather than against a run with no objectives declared, which FR-001 makes
  unproducible: a registry without an objective set fails at load, so there is no second answer to
  compare with. And a scan asserts the `Answer` carries no string this feature composed: every string
  it adds is an id, a criterion name, or a reason compared byte-for-byte against the core record it
  came from (FR-028, on 015 SC-003's technique). Both halves are *do not break what exists*
  requirements, which is the kind an implementation passes silently unless something asserts them.
- **SC-017**: Answering twice produces equal results and equal canonical digests, and answering
  over declaration files renamed so they sort differently produces an equal computed result (015
  SC-006's rule for why the manifest is excluded).
- **SC-018**: A golden artefact records the owner's question, its answer and its dominance
  populations over the shipped registry, regenerated deliberately, with provenance excluded from
  the digest so that filling in a `verified_on` cannot move it.

## Assumptions

- **The registry this is specified against is the one the owner decided on 2026-09-02**: the ОВДП
  fixtures out, a real issue as the benchmark. The measurement records what that costs and it is
  one candidate at one horizon; every other figure is unchanged.
- **014's `survey` and 015's `answer` are called, not forked.** This feature adds a pass over what
  a section already computed and a declaration kind. It does not re-enumerate, does not re-evaluate
  and does not build a second pipeline.
- **Work outside this feature's own module, named rather than left to be discovered**: the
  question schema's objective-set field (FR-001a), which is a change to 015 made and reviewed
  there and one added line in the owner's own question file; **the width of the slack, as a value
  rather than a verdict** — FR-011c has to name it in a refusal and FR-007 has to compare against
  it, and `core/primitives/tolerance.py` exports nothing that says *how wide* the comparison was,
  so it gains one function, in that module, because computing it in
  `core/decision/` would be the second copy of the closeness rule FR-012 forbids; a member for the
  objective set in `terezy.data.manifest`'s closed `InputKind` (FR-030); and the command-line
  rendering of FR-029,
  which is a change to `cli/` including two fields that exist today and reach no reader.
- **No legal, tax or fee value is introduced.** Nothing in comparing two computed figures needs
  one. If a requirement here ever seems to want one, the scope has slipped.
- **A dominance pass is a comparison of records, not a search.** At 24 candidates a pairwise pass
  is 276 comparisons per section. Nothing here needs a solver, an approximation or a bound, which
  is why CL-3's recommendation costs nothing today.
- **One owner, one regime per question, loopback only.** The authentication gate (Principle VII)
  is not reached.

## What the break-even step needs, and does not have

The constitution's order is dominance → distribution → break-even → point estimate. This feature
builds the first. Recorded here so the next feature does not begin by discovering it, and because
naming what is missing is cheaper now than after a plan assumes otherwise:

- **An assumption that carries a number.** A break-even sentence is *B beats A only if X is worse
  than Y*, and Y is a value. Of the beliefs the owner's question rests on, the yield point and
  the stated exchange rate carry numbers; the observed-spread assumption does not — it says the
  observed spread holds, which is a claim with no dial on it. Solving for a break-even in it means
  first declaring a **parametrised** spread, which is a change to what an assumption is.
- **A declared admissible range per assumption.** A break-even value outside what the owner would
  entertain is arithmetic, not a finding. Nothing declares a range for any belief today; the one
  precedent is a fund's own stated yield range, which is the instrument's statement rather than
  the owner's.
- **An answer to what happens when the function has no root.** Purchases are in whole units, so an
  outcome is a **step function** of any assumption that moves the price — a break-even is
  therefore an *interval*, not a point, and reporting a point would be exactly the false precision
  Principle I forbids. That is the same rule as this feature's indifference band and it should
  reuse it rather than grow a second notion.
- **One belief, one place.** A break-even on the war ending is unsound while the same event is
  declared in several places with nothing tying them together — the recorded
  `martial-law-ends-one-belief-two-places` entry, which its own note records as **three** places
  as of 2026-08-30 and keeps the old count in its id deliberately. A break-even computed by moving
  one of them reports a threshold for a world that cannot happen.
- **A pair, not a set.** Break-even is pairwise between two candidates; over a non-dominated set
  of ten that is 45 pairs, and which pairs are worth solving is a presentation decision this
  feature deliberately does not take.

## Questions that were drafted and closed

Recorded rather than deleted: each looked open, and the reasoning that made it look open is the
reasoning someone will repeat.

**Should dominance prune?** It is the whole point of Pareto pruning inside a *search*, and it is
the wrong move inside an *answer*. A dominated candidate is dominated on the **declared**
objectives, and the owner may take it for a reason none of them carries — a maturity he likes, an
issuer he trusts, a paper he already holds. Closed against 014 FR-006 and required test **B12**:
removing an option from a comparison is a feasibility judgement, and this feature is forbidden
one. FR-009 reports the relation and filters nothing. Pruning becomes correct the day the same
relation is used inside a label-correcting search, where what is discarded is a partial path
rather than an option.

**Should the objective set live on the question rather than in `data/objectives/`?** Closed by
doing both, which is not a compromise: the *sets* are declarations (SIMULATOR_SPEC §4.10.1 puts
them in the framework surface, and I2 needs two of them to exist at once), and *which set this
question is answered under* is a field of the question (FR-001a), so the choice is inside the
digest that already makes an answer reproducible.

**Should this feature name the assumption that decides between two members?** It is
`docs/DIRECTION.md`'s own phrase and the temptation is strong. Closed by splitting the claim:
naming the assumptions the members **do not share** is a read over records that already exist
(FR-019), and naming the one that **decides** requires re-evaluating under a changed assumption,
which is required test **I5** and needs a per-assumption perturbation policy nobody has declared.
Writing the second sentence while computing only the first is the shape of defect this repository
keeps finding — a claim whose warrant is somewhere else.

**Should the indifference band be one number rather than one per objective?** Drafted as the
simpler declaration and closed on units: the objectives are in hryvnia and in days, and one number
cannot be both. A single relative band was the near miss — a percentage applies to money and is
meaningless on a date.

## Required tests this feature closes

| Row | What it asserts |
|---|---|
| **I2** | Two objectives over the same candidate set produce different rankings, and each run's manifest records which objective was used |

I2 is claimed on **SC-002**, which asserts both halves together: the objective set changes the
answer, and the manifest names which set was used. The row's word *rankings* is read as *the
answers the objectives produce* — this feature's answer is a partial order rather than a list, and
the measurement records the fact the row is about, that ordering by one figure and ordering by
another over the same 24 candidates disagree at all three horizons.

**The dominance step itself closes no row**, and no row is invented for it. No lettered behaviour
in `docs/REQUIRED_TESTS.md` names a non-dominated set — the sources it is derived from predate the
framing — and a row written by the feature that flips it is a row that proves nothing (013's
precedent). What the landing change should record instead is that Section I's remaining rows are
now blocked on named things rather than on the decision layer not existing.

**No other row in Section I moves, and each one's reason is different:**

- **I3** — a binding constraint's shadow cost. There are **no constraints**: 015 FR-018 states in
  as many words that a liquidity floor is a constraint, that constraints are I3, and that a
  verdict which removed an option would be a feasibility rule smuggled in. A shadow cost is *what
  the best feasible strategy gave up*, which needs an optimum and a feasible region, and this
  feature computes neither.
- **I4** — the naive baselines. Half is structural already (010 holds the hurdle as an index into
  the ranking), and this feature adds the *nothing dominates the hurdle* statement (FR-017). The row stays open for the two reasons 015 recorded and neither is closed here:
  the cash instrument does not exist and is an owner verification task, and `50/50 OVDP + VWCE` is
  an **allocation** over candidates, which nothing in this repository can represent.
- **I5** — stability under a 1% perturbation. Deliberately not attempted, and FR-021 is where the
  boundary bites: naming the assumption that *decides* between two members is the same computation
  as re-ranking under a perturbed input. It needs a per-assumption perturbation policy nobody has
  declared — what a 1% change to *the observed spread holds* even means is undefined.
- **I6** — the indifference band. **The nearest miss, and the box does not move**, which is worth
  saying because a reader will expect FR-011 to close it. I6's own words are *a range of
  allocations scores within noise* and *no allocation is ever reported to sub-percent precision*:
  it is written over **allocations**, and there are none. What this feature builds is the same
  rule one level down, over candidates, and the landing change should record it as reinforcement
  so the row is not later read as covered.
- **I7** — *sometimes best* versus *never bad*. Needs a candidate scored under **several
  scenarios**, and a question declares **one** regime (014 FR-023). Two regimes are two answers
  and a reading across them, which is a feature and not a pass. What this feature contributes is
  the shape: dominance inside a scenario is what *sometimes best* and *never bad* are computed
  over.

**Section A moves by nothing, and the twelve rows are blocked by five things rather than by
twelve.** The largest group — **A1, A3, A4, A5, A8, A10 and A11** — are behaviours of statistics
computed from a **series of observed returns**, and this repository has none at all: every
instrument is contractual, and the only market observation behind any figure is a single dated
quotation carrying a buy and a sell price. There is nothing for those rows to be true or false
about, and a test written against a synthesised series would assert that the synthesiser works.
Of the remaining five: **A2** is a money-weighted rate, which 010 **does** compute, and is the
near miss below rather than a member of that group; **A6** needs paydays mapped onto trading days,
colliding paydays summed, and one schedule shared by every compared strategy — and **no such
schedule is declared**, which is a narrower claim than it looks, because 008 *does* declare a
monthly contribution and solve closed forms over it (`core/goals/solve.py`, `data/goals/`), and
that is a monthly annuity rather than a payday calendar and is shared by no comparison; **A7** is
a day-count behaviour belonging to the instrument layer, where declared conventions already live;
**A9** is constraints, which is I3; and **A12** is the caching layer behind the reserved
`Provider` interface, recorded as the `provider-automation` future.

Two are near misses and are named so nobody flips them by analogy:

- **A2** — *XIRR reported separately as the money-weighted outcome*. 010's `implied_rate` **is** a
  money-weighted internal rate of return over dated flows, and 001's contractual yield is a
  different figure kept separate, so half the row is arguably already satisfied. What is missing is
  the other half — the `(final/invested)^(1/y)` pseudo-CAGR the row says must not reappear needs a
  dollar-cost-averaged position for the prohibition to bite on, and there is none. If the row is
  ever claimed it is 010's to claim, not this feature's.
- **A9** — *infeasible constraints raise instead of silently returning an invalid portfolio*.
  Nearest in spirit and wrong in every particular: there are no constraints (I3), no portfolio,
  and in this repository a degraded outcome is a **typed result**, never a raise (Principle IV) —
  so closing A9 as written would require doing the thing the constitution forbids.

## Out of scope

Named explicitly so the plan does not drift: **constraints and shadow costs** (I3); **allocations
and portfolios of any kind**, including I4's second naive baseline; **the stability check and any
perturbation of an input** (I5); **the break-even step**, whose prerequisites are recorded above
and not built; **scenario sweeps, Monte Carlo and any reading across regimes** (I7) — one regime
per question stands; **any optimiser, solver or search**, and any dependency for one (CL-3);
**any change to 010's `TupleRefused` union**; **any change to 010's ranking, tie or benchmark
rule**, all three of which are carried unchanged; **the recorded `horizon-as-a-latency-budget`,
`one-amount-per-stream-in-compare`, `zero-hop-way-in`, `provenance-on-a-refusal`,
`real-terms-for-a-tuple` and `secondary-market-rate-risk` gaps**, none of which this feature
closes and several of which it makes more visible; **the display-currency switch**; and **the web
UI**, whose framework stays unchosen.

**Not out of scope, though a reader expects it to be**: the question schema's objective-set field
(FR-001a), the slack-width function in the tolerance module (FR-011c), the `InputKind` member for
the objective set (FR-030), and the command-line rendering (FR-029) — including two fields,
`Comparison.ties` and `Comparison.beats_benchmark`, that the core computes today and no reader has
ever seen.

## What this makes reachable, and deliberately does not build

Each is reachable **because of** a requirement above and is named so the next feature does not
re-derive the argument.

- **Label-correcting search with Pareto pruning.** 014 recorded that the cure for an exploding
  candidate space is not enumeration but keeping only non-dominated labels at each node — and
  that a search implementation must produce the same non-dominated set brute force produces, on a
  registry small enough to run both. FR-006 is that reference implementation. It is not built
  because 014's ceiling is the declared signal that enumeration has stopped being the right
  primitive, and it has not fired.
- **A bound from the benchmark.** FR-016 keeps the hurdle inside the population, so any partial
  path whose best completion cannot beat it can be cut without being completed — branch and bound
  with a bound the system already computes. Same reason for not building it.
- **Dominance across scenarios (I7).** FR-024's determinism and 014 FR-023's regime-independent
  key mean two per-regime results align by key equality with nothing to reconcile, which is what
  *sometimes best* and *never bad* are computed over.
- **The deciding assumption (I5).** FR-019 names the assumptions the members do not share, which
  is the input to the question *which of them flips the order* — one re-evaluation per assumption
  over an already-computed set.
- **A confidence dimension (CL-1 option D).** FR-022 puts the merged marks on every verdict, so
  the day an ordering over marks is declared, the partial order gains a dimension without the
  verdict record changing shape.

## Owner verification tasks

1. **Answer CL-1 to CL-4.** Nothing here can be planned until CL-1 and CL-2 are settled: they
   decide what the output *is*. CL-3 is a standing position rather than a blocker. CL-4 is one
   word in `data/questions/fifty-thousand.toml` and the feature cannot demonstrate itself without
   it.
2. **Name the indifference bands** once CL-2 is settled — one number per objective, in the
   objective's own units. There is no citation and no source: how much precision he believes his
   inputs support is a statement about him, which is why `data/objectives/` is exempt.
3. **Confirm that a dominated candidate stays visible.** FR-009 reports every candidate and prunes
   none, on the reading that he may take a dominated option for a reason no objective carries. If
   he would rather the dominated population were withheld, that is his call and it changes what
   the answer shows — but it does not change what is computed.
