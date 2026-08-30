# Feature Specification: The question, and the answer that refuses in parts

**Feature Directory**: `specs/015-the-question`

**Feature Branch**: `spec/015-question`

**Created**: 2026-08-30

**Status**: Ready for planning — both clarifications are answered and encoded (*Clarifications*)

**Input**: The owner asked a question. Every feature so far costs a tuple or finds one; this one
answers a sentence a person said out loud, end to end, and is the first whose deliverable is
user-facing. A question is a **declaration** under `data/questions/`, the API is **one verb**,
and the answer **refuses in parts** — because over the registry that ships today, an answer that
returns a number for everything the owner named has lied.

---

## Why this feature exists

The owner's question, as he stated it on 2026-08-30:

> "I have 50,000 UAH. I may need 20,000 UAH within six months. Compare cash, OVDP, Inzhur and
> BTC over 1, 3 and 12 months, including access, exit, taxes, inflation, liquidity and adverse
> scenarios."

Nothing in the repository can be handed that sentence. Feature 014 enumerates a candidate set
and hands it to 010's `compare`, and both take their inputs as **arguments constructed in a test
module**. There is no artefact that *is* the question, no verb that takes one, and no record
that holds what came back. `src/terezy/api/__init__.py` and `src/terezy/cli/__init__.py` are
docstrings and no code.

This feature is the vertical slice: the question as a declaration, one verb over it, and a
result record shaped to be a UI's only contract. Owner decision **D-B** keeps the web framework
unchosen *until the result schema has stabilised against real output*, which makes the `Answer`
record the most consequential thing specified here.

### The thing that makes it worth building before the data is real

Measured on the shipped registry (below), the owner's question has **no ranking at any of his
three horizons**. Two of the four subjects he named are not declared at all. Every figure that
could be produced rests on fixtures.

An answer that reports a number for each of the four has lied about all of it. An answer that
returns nothing has thrown away three real findings. **The deliverable is the third thing**: what
it ranked, what it dropped and why, what was never a candidate, and what the question named that
the registry does not declare — each with a **name**, so that every absent declaration is visible
rather than a silent default. Get that right and the feature is worth having today. Get it wrong
and it is a demo.

## The decision already taken — a question is a declaration

**Owner decision, 2026-08-30**, taken explicitly against a *command-line-arguments-are-canonical*
alternative. A question lives in `data/questions/*.toml` beside instruments, routes and tax
rules. CLI flags remain as sugar that builds the same record in memory; **the file is
canonical**. The reasons:

- **It is diffable, citable and reproducible from an artefact.** "The answer I got last March"
  is a file and a commit, not a shell history line.
- **It drops into machinery that already exists.** `src/terezy/data/manifest.py` identifies a
  declaration by the SHA-256 of its bytes precisely because *"a hand-maintained version number
  is one a maintainer must remember to bump"*. A question file gets that for free; a command line
  gets it never.
- **A new kind of question becomes a schema field**, rather than a CLI option *plus* an API
  parameter *plus* a call site. That is Principle II — domain knowledge is data, not code —
  applied to the API surface rather than to the engine.
- **The question cannot be flags anyway.** 014 FR-003 forbids a default for a consumption
  method, a coupon policy, a liquidity mode, a buyback availability, an exit date and a chosen
  point inside a stated range — so a question that can be *asked at all* carries a run plan per
  subject, each with six or more stated fields. Expressed as flags that is a configuration file
  with worse ergonomics and no digest.

## The API is one verb

```
answer(question, declarations, as_of) -> Answer | Refused
```

**What the second parameter must carry, because `Registries` alone cannot.** The owner's sketch
named it `registries`; the value has to be the whole loaded declaration bundle. `Registries`
carries neither the **candidate ceiling** — `resolver.CandidateDeclarations.ceiling`, from
`data/candidates/`, which FR-014a applies per section and which 014's `survey` takes as its own
argument — nor the **segment bound**, which comes from `data/composition/` and is a *required*
field of 014's `Question`. A verb that cannot receive them cannot call `survey`, and this repo
has produced that trap before: a requirement naming a function whose signature cannot take the
value it mandates.

**Resist a second.** The two that will be proposed, and why neither is one:

- *A verb for the cross-horizon reading* ("which candidate ranks where at 1, 3 and 12 months").
  It is a **derived function over the `Answer`**, on 014 FR-011's precedent — a tally is derived
  by one named function from the retained records and never stored as a second field beside them
  — and 014 FR-023's key rule is what makes the alignment exact: the candidate key is the five
  declared terms and nothing else, so sections align by key equality.
- *A verb for "just rank it"*. That is `answer` with a question that declares one horizon. A
  second entry point would be a second place the question's shape is decided, and the shape is
  the thing this feature exists to stabilise.

The verb appears **once per layer the constitution mandates** and no layer adds a second: the
pure function in the core, and the orchestration entry point in `api/` that loads the
declarations, calls it once, and attaches the run manifest. `cli/` is a client over `api/` with
one subcommand.

## Clarifications

### Session 2026-08-30

- Q: Does "over 1, 3 and 12 months" mean the money comes out at the end of that window, or is the
  window one through which each instrument runs its own declared plan? → A: **The money comes out
  at the end of the window, and selling early is normal.** Most platforms let an OVDP be sold,
  with a delay of hours to a day or two, at a spread — so the likely outcome of an early exit is
  a loss or a lower return, not an impossibility. A bond compared over one month is sold after
  one month.

- Q: When the owner names "cash, OVDP, Inzhur and BTC", is a subject an instrument id, a declared
  group of instruments, or something the answer never counts? → A: **An id or a declared group.**
  None of his four words is an instrument id, and feature 016 settles it: it declares 24 real OVDP
  issues, so an ids-only question file would grow to 33 entries and need a hand edit per issue
  thereafter. `ovdp` and `inzhur` resolve to id sets; `cash` and `btc` resolve to nothing and land
  in the undeclared population. FR-007 to FR-011 carry it.

**A claim in the first draft of this specification was wrong and is corrected here rather than
quietly edited.** It said the mid-life disposal price was missing. It is not.
`data/observations/inzhur.toml` publishes **`buy` and `sell` for every one of the 24 active
issues** (retrieved 2026-08-24), and the gap between them is the loss the owner describes:
**0.000% to 0.637% of the buy price, median 0.237%**, with **5** issues quoting buy equal to
sell. The delay is modelled too — an exit route carries a declared latency in days, and the
shipped `inzhur_to_monobank` costs three. What is genuinely missing is smaller and different, and
FR-029 to FR-033 are what it costs.

## The measurement

Every count below was read from `data/` on **2026-08-30** by loading the shipped registry and
running feature 014's `enumerate_candidates` and `survey` over it. It is reproducible from the
repository and from nothing else. The registry's *own* counts — 9 instruments, 2 streams, 10
routes, 1 spendable endpoint, 9 candidates from 18 pairs — are 014's measurement and are cited
rather than copied.

**1. The four subjects the owner named.**

| He named | The registry declares |
|---|---|
| cash | **nothing**. No instrument declaration represents a hryvnia balance held at a venue |
| OVDP | six fixed-income declarations, **every one a fixture** (014's *Assumptions*), of which **five** carry the `ovdp` label — item 4 |
| Inzhur | `inzhur_reit` and `inzhur_miltech` — the only two real declarations in the registry |
| BTC | **nothing**. No instrument, and `binance` and `coinbase` are venues on the route graph only |

**2. The gaps that make a tax figure refuse.**

| Declared | Measured | Consequence |
|---|---|---|
| `data/official_rates/ua_nbu_usd.toml` | the series is declared and holds **0** observations | any tax figure struck from a foreign amount refuses by name (`TaxCurrencyConversionUnavailable`). **Unreachable from the shipped registry today**: every candidate is funded from `salary_uah` in hryvnia, so no foreign amount is struck. It becomes live the day an inbound USD corridor is declared |
| `data/tax/destinations/ua.toml` | **5** `(scheme × venue)` rows: **1** `interpreted`, **4** `unsettled` | income credited to an `unsettled` destination yields labelled what-if figures and no tax owed. **The row the owner's own `contract_usd` reaches is the `interpreted` one** (`fop`), and the four unsettled rows carry 3, 1, 1 and 2 readings respectively — so "two what-ifs" is true of one of them and not a general fact |

**3. The candidate set does not depend on the horizon.** Enumerating the shipped registry at
1, 3 and 12 months from 2026-09-01 produces the **same 9 candidate keys in the same order**;
exactly one candidate per instrument, so a benchmark named by instrument id resolves
unambiguously today. Only the *outcomes* move. This is an observed property of the code and not
a contract, which is why FR-013 asserts it per run rather than assuming it.

**4. What the four words resolve to, and why it is seven rather than nine.** Under FR-007 a
subject is an id or a group, so his question enumerates the union of `ovdp` and `inzhur` — not the
registry. The labels, each read from the fixture's **own header** rather than from its class:

| Group | Members | Read from |
|---|---|---|
| `ovdp` | `ovdp_synthetic_a`, `ovdp_synthetic_b`, `ovdp_enumerated_a`, `ovdp_enumerated_mirror`, `enumerated_out_of_order` — **5** | the last is *"modelled on a real issue and deliberately not it"*, naming `UA4000235865`, a real government issue |
| `inzhur` | `inzhur_reit`, `inzhur_miltech` — **2** | the two real declarations in the registry |
| in neither | `enumerated_taxable_x`, `synthetic_fund_c` | the first exists *because* ОВДП exempt both income kinds and it declares two taxable ones instead; the second's *"whole purpose is that it is different"* from the Inzhur funds |

**Seven, and seven is the honest figure.** Nine was *every instrument in the registry*, which is
not what he asked. The cheapest route back to nine is to put `ovdp` on `enumerated_taxable_x` and
`inzhur` on `synthetic_fund_c` — which is precisely the class-stands-in-for-the-group inference
FR-007a forbids, performed by hand on day one and then frozen into SC-018's golden. The two
instruments are out because their own files say what they are for.

**5. The owner's question, run today — the pre-feature baseline.** 50 000 UAH from `salary_uah`,
`as_of` 2026-08-30, horizons starting 2026-09-01, benchmark `ovdp_synthetic_a`, one
hold-to-maturity or low-end-of-range plan per subject, re-measured under group resolution.
**This is what the engine does before FR-029 and FR-030, and both of them move it** — which is why
SC-001 pins the shape of this table while SC-023 and SC-027 pin the changes, rather than one
criterion pinning both and contradicting itself:

| Horizon | pairs | enumerated | evaluated | dropped | why they dropped | the comparison |
|---|---|---|---|---|---|---|
| 1 month | 14 | 7 | **1** | 6 | `CannotSpanHorizon` ×5, `InstrumentRefused` ×1 | `BenchmarkUnavailable` — the hurdle itself was dropped |
| 3 months | 14 | 7 | **1** | 6 | `CannotSpanHorizon` ×5, `InstrumentRefused` ×1 | `BenchmarkUnavailable` |
| 12 months | 14 | 7 | **3** | 4 | `CannotSpanHorizon` ×3, `InstrumentRefused` ×1 | `BenchmarkUnavailable` |

Seven `(instrument, stream)` pairs yield no candidate in every section — the `contract_usd` half
of fourteen, unchanged in kind by the narrowing. **Nothing is ranked at any horizon the owner
asked about.** Every reason has a name.

**All thirteen `CannotSpanHorizon` drops — five distinct instruments across the three sections —
carry `binding_term = "instrument.maturity_date"`**, and every `InstrumentRefused` drop is
`inzhur_reit`. Over the whole registry the second one is `synthetic_fund_c`, which the group
narrowing removes; both are worth naming because the first draft called them *the two Inzhur
funds*, and one of them never was. Neither is the empty `ua_nbu_usd` series.
Read at source rather than inferred from the message: the refusal is `PegUnsizable`, raised in
`core/results/fund.py::_refuse_the_peg` with `missing_input = "FundAssumptions.exchange_rate"`,
and surfacing as `InstrumentRefused` through `_fund_outcome`'s catch-all arm. **No rate series is
consulted**, so filling `ua_nbu_usd` changes nothing here; the refusal says so in its own words —
*"No rate is assumed and none is read from anywhere: state one as the owner's assumption."* The
remedy is an owner-stated rate on the run plan, which FR-021a is what makes reachable. The first
draft of this specification attributed it to item 2's empty series, which would have sent a plan
to the wrong file.

**6. And the one candidate that survives at 1 and 3 months is not a one-month result.**
`inzhur_miltech` reports the **same** amount and the **same** rate at all three horizons, because
its plan requests an exit on 2028-01-17: at a one-month horizon its span runs **2026-09-01 to
2028-01-20**, sixteen months past the horizon's end, and nothing refuses it. That is 014's
recorded `horizon-as-a-latency-budget` gap — its second half, the one 014 called *unrefused
rather than mis-measured* — reached live by the owner's own question. Under the semantics the
clarification settles it stops being a curiosity: if a horizon means the money comes out at its
end, a figure whose money comes out sixteen months later is answering a different question while
looking like an answer to this one (FR-030).

**7. The whole set is already marked.** The enumerated set's merged provenance over the shipped
registry is both **unverified** and **synthetic** (`api.diagrams.marks.is_synthetic`), over 8
sources, with 8 staleness assessments and none stale at `as_of` 2026-08-23. So the marks the
answer must carry exist; what this feature must not do is lose them (FR-024).

**8. Two of the six things he asked to be included have no figure to report.** `TupleOutcome`
carries the outlay, the part contributions, the arrivals, what reaches a spendable endpoint, the
span, the routes, the risk class and the provenance — access, exit, instrument tax and liquidity
are all in there. **A real-terms rate is not**: `implied_rate` is
`NominalRate | RateNotComparable`, and the `RealRate | RealTermsUnavailable` slot exists on
feature 001's hurdle record and on nothing a tuple produces. And **income tax on the stated
amount** is feature 012's deployable capacity, which answers a question about a *stream* rather
than about money already held. Both are stated exclusions (FR-023a), not silently absent — the
`accounts_for` / `excludes` discipline `TupleOutcome` already carries, applied one layer up.

## What the shipped registry says about "cash", and why it is not a clarification

A declared cash instrument would be bought at the venue the money already sits at
(`monobank_uah`), and `compose` refuses that pairing in its own words — *money that is already
where it was wanted*. 014 FR-014 puts such a pair in the **no-candidate** column carrying
`NothingNeedsToConnect`, because nothing is missing and the two remedies are opposite.

So **the naive baseline the owner named first is the one candidate the engine cannot represent**,
and the gap is already recorded: `[[future]] zero-hop-way-in` — `Tuple.route_in` is required,
there is no `ENTRY_BY_IDENTITY`, and the mirror on the way out is solved and this one is not.
This feature makes that visible under FR-011 and does not close it.

## Early exit, and the one thing that is genuinely missing

The clarification settles the semantics: **a horizon window means the money comes out at the end
of it**, and an instrument that outlives the window is sold rather than refused. Three
consequences, each measured or read in the code rather than supposed.

**1. The price exists; the price *at a future date* does not.** Every active issue publishes a
`buy` and a `sell`, so the cost of selling today is observed rather than modelled. A sale one
month from now happens at *that day's* spread, which nobody knows. So what the engine needs is
not a price but a **declared assumption** — *the observed spread is taken to hold* — carried as
data, visible, changeable, and **marked**, so that every figure computed through it inherits the
mark and no early-exit number can be read as an observation (FR-031, FR-032). It must not
default silently and must not be invented per run: an assumption nobody declared is exactly the
invented number Principle I exists to prevent.

**2. No shipped declaration carries a resale price at all.** The observations are not
declarations — the file says so in its own header — and a declared `InstrumentAccess` carries
one `price.per_unit`, which is what a unit costs to *buy*. So on the shipped registry an early
exit refuses for a missing declaration rather than producing a figure, which is the correct
behaviour and is why this feature is still worth building before 016 lands. Derived from the
measurement rather than run: all thirteen `CannotSpanHorizon` drops bind on
`instrument.maturity_date` — five of them inside the seven his question resolves to — so under
the new semantics those instruments stop being *out of horizon* and become *no resale price
declared*. **The count does not change and the remedy does**
— from *shorten nothing, it is impossible* to *declare what this sells for*, which is feature
016's job.

**3. The figure carries the platform's spread and not rate risk, and that is an approximation in
a stated direction.** A bond's resale price also moves with market rates: a long bond sold after
rates rise fetches less than its spread implies. Modelling that is a secondary-market model and
is **out of scope**, recorded as `[[future]] secondary-market-rate-risk`. The direction must be
stated with it (FR-033), because an unsigned approximation is worse than none:

- it replaces a **distribution with a point**, and it does so for the one option chosen precisely
  for its optionality — so the early exit is reported as more certain than it is;
- the quoted spread is a **seller's quote under today's conditions**, and a seller's quote widens
  exactly when a forced sale is most likely;
- five of the twenty-four active issues quote **buy equal to sell**, so for those the assumption
  says an early exit is free — which is where it is least credible and where the mark matters
  most.

So the early-exit figure errs toward the early exit looking **better** than it is. That is the
form this project requires of an approximation: named, signed, and marked.

*A fourth fact, read in the source and stated because it bears on the assumption's credibility
rather than on any figure: 11 of the 24 active issues publish `available_quantity = 0`. What that
field constrains is not stated by the source — plausibly the platform's inventory for a buyer
rather than its willingness to buy back — and the unknown is part of why the spread holding is an
assumption and not an observation. Settling it is feature 016's, which is where a seller's
quotation becomes a declaration.*

## Three things this feature must not become

- **It does not optimise.** No objective function, no scoring weight, no shortlist. The
  constitution's order is dominance → distribution → break-even → point estimate, and this
  feature adds no ranking rule at all: ranking is 010's `compare` and the tie rule is 010's.
  I2–I7 are later features.
- **It converts no currency.** Feature 011's official rate is a legal reference for what an
  income was worth on a date; a channel rate is a transaction price. Reusing either to score a
  return is the role conflation Principle VI names, and `core/results/tuple.py::RateNotComparable`
  says so at length. FR-021.
- **It writes no sentence to be read aloud.** The `Answer` is the API's contract with a UI that
  does not exist yet. It returns what it computed and what it refused. FR-020.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner's question, asked as an artefact (Priority: P1)

The owner writes his question into a file — an amount per stream, the subjects he wants
compared, the horizons, the benchmark, a run plan per subject, and what he may need back and
when. He runs one verb over it. The answer names, per horizon, what was ranked, what was dropped
with its typed reason, what was never a candidate, and what he named that the registry does not
declare.

**Why this priority**: this is the sentence the product exists to be able to answer, and it is
the first output a person rather than a test module reads.

**Independent Test**: check in the owner's question as a declaration, answer it over the shipped
registry, and assert three sections, **seven** candidates enumerated in each, **no ranking in
any**, and `cash` and `btc` reported by name as undeclared. Stated over the shape rather than over
*The measurement* item 5's refusal names, which are the pre-feature baseline that FR-029 and
FR-030 move; the seven are the ids his four subjects resolve to (FR-007), derived from the
declared labels rather than written out.

**Acceptance Scenarios**:

1. **Given** a declared question and the shipped registry, **When** it is answered, **Then** the
   result holds one section per declared horizon, in the order the question declares them.
2. **Given** the same question and registry answered twice, **When** the two answers are
   compared, **Then** they are equal field for field, and their canonical digests are equal.
3. **Given** a question file edited in any load-bearing field, **When** it is answered, **Then**
   the run manifest's recorded digest for that file differs from the previous run's.
4. **Given** the question declares its horizons in a different order, **When** it is answered,
   **Then** the sections permute and nothing else changes.

---

### User Story 2 - The answer refuses in parts (Priority: P1)

Where the answer cannot produce a figure, it says which figure, for which candidate, at which
horizon, and **what is missing by name** — and everything it *can* say still stands beside it.

**Why this priority**: equal-highest with Story 1, and it is the whole reason this feature is
worth building against fixtures. Principle I: a refusal with a reason beats a plausible number.

**Independent Test**: over the shipped registry, assert that the 1-month section carries
`BenchmarkUnavailable` naming `CannotSpanHorizon` on the hurdle while the 12-month section is
computed independently of it; and that a question naming an undeclared subject produces an answer
rather than a whole-answer refusal.

**Acceptance Scenarios**:

1. **Given** a horizon in which the benchmark itself is dropped, **When** the answer is read,
   **Then** that section carries 010's `BenchmarkUnavailable` whole, the other sections are
   unaffected, and no section is silently omitted.
2. **Given** a question naming a subject the registry does not declare, **When** the answer is
   read, **Then** that subject appears by name in its own population, and every horizon section
   states how many of the question's named subjects it could not reach.
3. **Given** a candidate whose tax figure needs an official rate the series does not hold,
   **When** the answer is read, **Then** it is a dropped candidate carrying
   `TaxCurrencyConversionUnavailable`, and the answer names the empty series rather than
   producing a figure.
4. **Given** an answer in which no horizon produced a ranking, **When** it is read, **Then** it
   is an `Answer` and not a `Refused`: *nothing could be ranked, and here is why for each* is a
   result.
5. **Given** any part-refusal, **When** the answer is read, **Then** the refusal record is the
   one the core produced, carried whole — never summarised, sampled, truncated or rewritten.

---

### User Story 3 - What the question named, and what the answer covered (Priority: P1)

A ranking of two options never reads as a ranking of the four the owner asked about.

**Why this priority**: this is the failure mode that survives every other guard. Two ranked
figures, both correct, presented under a question that named four subjects, is a false optimum
with an impeccable audit trail — and it is what today's registry would produce for this exact
question.

**Independent Test**: answer a question some of whose named subjects the registry does not
declare, and assert every ranked section carries the count of named subjects it did not reach,
derived from the question and the section rather than stored twice, and asserted for all three
of FR-010's states rather than only for the reached one.

**Acceptance Scenarios**:

1. **Given** a question naming subjects the registry only partly declares, **When** any section
   is read, **Then** it states how many of the named subjects were reachable and how many were
   not, and the ranking cannot be read as covering the ones it did not reach.
2. **Given** a subject that is declared but yielded no candidate for every stream, **When** the
   answer is read, **Then** it is distinguishable from a subject that was never declared: the
   remedies are a corridor and an instrument, and they are not the same job.
3. **Given** a section whose ranking is empty, **When** it is read, **Then** the reason is on the
   section and the count of named-but-unreached subjects is on it too.

---

### User Story 4 - What he may need back, and when (Priority: P2)

The owner states that he may need 20 000 UAH within six months. The answer says, per candidate
per horizon, whether that candidate's own money is back at a place he can spend it by that date —
and where it is not, it says that raising part of the position early is not something this system
projects, rather than guessing at what a part-sold holding would then pay.

**Why this priority**: P2 because Stories 1–3 must exist first, but it is half of the question he
asked and dropping it would answer a different one.

**Independent Test**: declare a reserve dated before and after a candidate's last arrival and
assert the verdict flips between *covered by the plan* and *needs a partial exit, which is not
modelled*; and assert the candidate is present and evaluated in both cases.

**Acceptance Scenarios**:

1. **Given** a candidate whose arrivals put the whole amount at a spendable endpoint on or before
   the reserve date, **When** the verdict is read, **Then** it is *covered by the plan*, carrying
   the date and the amount that arrives.
2. **Given** a candidate whose money is not all back by then, **When** the verdict is read,
   **Then** it says a partial exit would be needed and that a partly-liquidated holding is not
   projected — and it is **not** phrased as *the reserve is not met*, which is a claim this
   system cannot make, nor as a missing price, which after FR-031 it is not.
3. **Given** any reserve verdict, **When** the candidate set is read, **Then** the candidate is
   still there, still evaluated, still ranked. A stated need never removes an option.

---

### User Story 5 - The answer traces to exactly what produced it (Priority: P2)

Every answer carries its manifest: the question file's digest, every declaration file the run
read with its digest, the as-of date, the regime, and the provenance and staleness of everything
behind every figure.

**Why this priority**: Principle III — *a result without a manifest is not a result* — and it is
the row (**H3**) this feature closes.

**Independent Test**: a scan asserting that every file under `data/` the run actually read
appears in the manifest with its SHA-256, that the question file is among them, and that editing
any one of them moves exactly that one digest.

**Acceptance Scenarios**:

1. **Given** an answer, **When** its manifest is read, **Then** the question's own file is an
   input reference like any other declaration.
2. **Given** two answers to two different questions over one registry, **When** their manifests
   are compared, **Then** only the question's digest and the question-derived fields differ.
3. **Given** an answer resting on an unverified or synthetic declaration, **When** it is read,
   **Then** the mark is on the answer and on every figure derived from that declaration.

---

### Edge Cases

- **Nothing is ranked at any horizon** — an `Answer`, never a `Refused`. Measured as today's
  behaviour for the owner's own question.
- **The question names no subject the registry declares** — an `Answer` with every named subject
  in the undeclared population and every section empty with its reason. Distinct from a registry
  that declares nothing.
- **The question names a subject twice** — refused at load, naming the file and the field. A
  duplicated subject would double-count a candidate in the accounting identity.
- **Two horizons with the same start and end** — refused at load. Two identical sections are not
  two answers, and the derived cross-horizon reading would key two rows the same.
- **A horizon that starts before `as_of`** — permitted and unremarkable: `as_of` decides
  staleness and nothing else (014's `Question.as_of`), and asking what a position begun in April
  looks like is a legitimate question.
- **A reserve dated after every horizon's end** — permitted; the verdict is computed against each
  candidate's own arrivals, which may run past a horizon (014's recorded
  `horizon-as-a-latency-budget` gap), and the verdict says which arrivals it used.
- **The enumerated set spans two streams** — 014's `MoreThanOneStreamInTheSet` is carried as the
  section's outcome, verbatim. This feature does not resolve the recorded
  `one-amount-per-stream-in-compare` gap and does not hide it (FR-022).
- **A question naming a benchmark that is not among its subjects** — the whole answer refuses:
  the benchmark must be one of the set's members exactly once (014 FR-022), and a benchmark
  outside the question's subjects can never be.
- **A question naming a benchmark instrument that yields more than one candidate** — refused,
  naming the instrument and the count. Picking the first would settle by declaration file order
  which figure everything else is ranked against.
- **A subject that is declared, is reachable, and has no run plan** — 014 FR-018 refuses the
  whole enumeration for that horizon's section. Not defaulted, not skipped.
- **A horizon shorter than the way in's declared latency** — the money has not arrived when the
  window ends. Under FR-029 it is a sale of something never bought, which is not a figure; 014's
  recorded `horizon-as-a-latency-budget` gap names the same corridor from the other side, and it
  is 010's to refuse rather than this feature's to invent.
- **An instrument that matures *inside* the window** — no sale, no spread, no assumption, and
  therefore no mark from FR-032. The early-exit machinery must be reachable only where an early
  exit actually happens, or every hold-to-maturity figure would inherit a mark it did not earn.

## Requirements *(mandatory)*

### The question is a declaration

- **FR-001**: A question MUST be a declaration under `data/questions/`, owner-scoped like
  `data/composition/` and `data/candidates/`, loaded by the same discipline: **fail loudly at
  load** on a malformed or unknown field, naming the file and the field, with **no default for
  any field** (Principle II; 002 FR-028 and 004 FR-006's precedent for a forgotten line never
  reading as a chosen policy).
- **FR-002**: A question MUST declare: an **id**; the **date it was asked**; **one regime**; the
  **continuation assumption**; an **amount per income stream** in that stream's own currency; its
  **subjects**; its **horizons**; its **benchmark**; a **sequence of run plans per subject**; and
  optionally one or more **stated reserves**. Nothing here adds a term to 010's `Tuple`.
  **The question file's fields and 014's `Question` fields are not the same set**, and the claim
  that they were was wrong. Two of 014's required fields are *not* declared in a question and are
  composed in by the verb: the **segment bound**, which is the owner's composition policy declared
  once in `data/composition/` and shared by every question he asks, and **`as_of`** (FR-006). The
  verb builds one 014 `Question` per horizon from the file, the declared bound and `as_of`.
- **FR-003**: `data/questions/` MUST be named in `scripts/check_provenance.py`'s `EXEMPT_DIRS`
  **with its reason recorded beside it** — a question is one person's stated preference, not an
  observation about the world, the same exemption `objectives`, `strategies`, `composition` and
  `candidates` carry. The gate is fail-closed over the whole data tree, so an unlisted directory
  is an error rather than a blind spot. If a number describing the world ever has to live in a
  question, it moves to a sourced directory rather than the exemption widening.
- **FR-004**: A question's declared amount MUST be in the currency its named stream declares. A
  mismatch MUST be a **load-time refusal naming the file and the field**, not the caller's
  construction error that 014 SC-020 leaves as a raise: the two are different mistakes, and one
  of them is a typo in an artefact under review.
- **FR-005**: The CLI MUST build the **same record in memory** from flags, and MUST NOT own a
  field the file cannot express or a default the file cannot state. A scan MUST assert that every
  field of the question record is reachable from a declared file.
- **FR-006**: `as_of` MUST be a parameter of the verb and MUST NOT be a field of the question
  file. 014's `Question.as_of` *decides staleness and nothing else*, so a question whose horizons
  or amounts moved with the calendar would be a different question each day while its digest
  stayed the same. Reproducibility is preserved by the manifest recording both the file's digest
  and the as-of date, not by putting a clock in an artefact.

### Subjects: what the question asked about

- **FR-007**: A question MUST state its **subjects** explicitly. A subject is a declared
  **instrument id** or a declared **group id**; a question may also state an explicit token
  meaning *every instrument the registry declares*. Neither stated, or both, MUST refuse at load.
  Omission MUST NOT mean *everything*, because "compare cash, OVDP, Inzhur and BTC" is not
  expressible over a registry-wide default and the absence of two of those four is the most
  useful thing the answer says today.
  **Groups exist because the owner asks in groups** (owner decision, 2026-08-30, taken against a
  subject-is-an-id-only alternative). None of his four words is an instrument id. What settles it
  beyond taste is feature 016: it declares 24 real OVDP issues, so under ids-only his question
  file grows to 33 entries and every future issue is a hand edit that is **silently wrong until
  somebody makes it**. Under a group, a new issue joins by carrying the label and his question
  file does not change at all. A question shape that rots as the registry grows is not a shape.
- **FR-007a**: A group MUST be a **declared label**, never a rule. An instrument declares which
  groups it is in; nothing computes membership from an instrument's class, its id, a name prefix,
  its issuer or where it is bought. Group ids MUST themselves be declared, and an **instrument**
  naming an undeclared group MUST fail at load naming the file and the field.
  Two inference traps are named because both are live in the shipped registry rather than
  hypothetical. **Class cannot stand in**: `enumerated_taxable_x` is fixed income and is not an
  OVDP. **Nor can the venue**: `inzhur` is already a venue id and *every one* of the nine access
  declarations reads `bought_at = "inzhur"`, so inferring the group from where an instrument is
  bought would put all nine in the `inzhur` group — including six bonds nobody would call an
  Inzhur fund. A third near-miss is worth stating because it looks like it works: five of the six
  fixed-income fixtures carry the `ua_government_bond` coupon class and `enumerated_taxable_x`
  does not, so the tax class happens to separate them today. It is still not the rule. A tax class
  is a legal fact about an instrument and a group is what the owner calls it; the two agreeing here
  is luck, and 016 may yet declare a government bond whose coupon is taxed another way. **Nor the
  id**: four of the six fixed-income fixtures are named `ovdp_*`, so a prefix rule would look
  right on two thirds of the registry and would then silently exclude `enumerated_out_of_order`,
  which is modelled on a real government issue and belongs in the group. An id is a dispatch key,
  never a fact about the paper.
- **FR-007b**: An instrument MAY be in **more than one group**, and a question MAY name both a
  group and one of its members, or two groups that overlap. Neither is an error.
  Forbidding multiple membership would force a false choice on the very data that motivates
  groups: 016 declares OVDP issues **sold through Inzhur**, so `ovdp` and `inzhur` are not
  disjoint, and the owner's own question names both.
  **Enumeration MUST therefore consider the union of the resolved ids, deduplicated**: an id
  named twice — by a group and by itself, or by two overlapping groups — yields **one** candidate
  and is counted **once**. This is stated as a requirement rather than left to the loader because
  an id counted twice is a wrong count in exactly the line FR-010 exists to produce.
- **FR-008**: Enumeration MUST consider **only** the ids the question's subjects resolve to. This
  is required work in feature 014 — its `Question` gains a declared subject set and its
  `_considered` narrows to it — made and reviewed there, on the same rule 014 applied to 004's
  `CompositionRefused`. The set MUST NOT be inferred from the supplied run plans: 014 FR-003
  refuses an instrument with no plan precisely so that *not asked about* and *forgotten* stay
  distinguishable.
- **FR-008a**: The answer MUST carry each named group's **resolution** — the ids it resolved to,
  and how many. This is the guard that keeps a group from reintroducing the failure it was chosen
  to avoid: a new issue declared in 016 **without** its label would silently shrink `ovdp`, and an
  answer that prints the membership makes the shrink visible on its face. A count on the answer is
  a check; a group that resolves quietly is a sentence nobody reads.
  **What this guard can and cannot do, stated so SC-033 does not overclaim.** The 016 regression —
  an issue declared without its label — does not *move* the count; it leaves it **lower than the
  owner expects**, and no test can know he expected 24. So the resolution is printed for a
  **human reader**, and what is mechanically checkable is the narrower property SC-033 pins: that
  the count is read from the labels instruments carry, and moves when they do.
- **FR-009**: A subject the question names that resolves to **no id at all** MUST be reported in
  its **own population**, by the word the owner wrote, and MUST NOT refuse the whole answer.
  `cash` and `btc` are exactly this today, and *you named this and nothing declares it* is the
  sentence worth having. The remedy is a **declaration**, which is a different job from a corridor
  and from a different amount.
  **A question naming an unresolvable word is a part-refusal; an instrument naming an undeclared
  group is a load failure (FR-007a). The asymmetry is deliberate**: a question is the owner's own
  vocabulary and its gaps are the answer's content, while an instrument is curated data and its
  typos are defects.
- **FR-010**: Every horizon section MUST state, per named subject, which of **three** states it is
  in, and MUST count them: **undeclared** (FR-009 — resolves to nothing), **declared but
  unreached** (resolves to ids, none of which yielded a candidate in this section), and
  **reached** (at least one candidate). The three MUST be distinguishable without reading prose,
  because their remedies differ — a declaration, a corridor, and nothing.
  The count MUST be over **named subjects**, and the deduplicated id count of FR-007b MUST be
  carried beside it rather than confused with it: *he named four things and two can be answered*
  and *seven instruments were enumerated* are both true and are different sentences. A ranking that
  reached two of four named subjects MUST NOT be readable as a ranking of the four (Principle I).
- **FR-011**: A subject that resolves to ids which yield no candidate MUST be reported through
  014's existing no-candidate column with its typed reason, and MUST be **distinguishable from
  FR-009's population without reading prose**. Where the reason is *nothing needs to connect*, the
  answer MUST carry compose's own words verbatim (014 FR-014) — that is the `zero-hop-way-in` gap
  made visible, and this feature does not close it.

### Horizons: several per question, one comparison each

- **FR-012**: A question MUST be able to declare **more than one horizon**, and the answer MUST
  hold **one section per declared horizon**, in the question's declared order, each section being
  exactly one candidate set and one comparison. *One horizon, stated once* stays 010's rule and
  is untouched: the horizon remains the unit of **computation**, and the question becomes the
  unit of **declaration**. Three separate runs would produce three artefacts with nothing tying
  them and no way to align them but by hand, and the cross-horizon reading — the ranking at one
  month is not the ranking at twelve — is the answer to the question the owner actually asked.
- **FR-013**: The candidate sets of two sections of one answer MUST be **asserted equal by key**,
  and an inequality MUST be reported as a finding rather than smoothed over. Measured on
  2026-08-30 the shipped registry produces identical keys across 1, 3 and 12 months, but that is
  an observed property of today's enumeration and not a contract — so it is checked per run, on
  014 FR-009's rule that a check cannot go stale silently and a sentence can.
- **FR-014**: A **section-level** failure MUST NOT refuse the answer. Any of 014's
  `EnumerationRefused` or `SurveyRefused` members, and 010's `BenchmarkUnavailable`, MUST be
  carried as that section's outcome, whole, with every other section computed independently. This
  is the central requirement of the feature: measured today, the 1-month and 3-month sections
  fail and the 12-month section fails differently, and all three facts are the answer.
- **FR-014a**: The declared candidate ceiling (014 FR-019) applies **per section**, unchanged, and
  this feature MUST NOT declare a second ceiling over the number of horizons. The enumeration
  ceiling exists because a *registry* can grow without anyone noticing; a horizon list is typed
  out by a person, one line each, in a file under review. A bound with no failure mode is a
  declaration nobody can answer.
- **FR-015**: The cross-horizon reading — which candidate placed where in each section — MUST be
  **derived by one named function** over the answer and MUST NOT be a stored second copy, on 014
  FR-011's rule. It is keyed by the candidate key, which 014 FR-023 fixes as the five declared
  terms and nothing else.

### Early exit: the money comes out at the end of the window

- **FR-029**: A horizon MUST mean that the position is **liquidated at its end**. An instrument
  whose own terms run past `horizon.end` MUST be sold at `horizon.end`, not refused for
  outliving the window. **This is a required change in feature 010**, made and reviewed there,
  and it is named rather than re-decided here: `CannotSpanHorizon`'s bond arm constructs
  `binding_term = "instrument.maturity_date"` and justifies itself with *"a return measured over
  a period the money could not have been withdrawn in is a rate for a holding nobody could have
  had"* — and the clarification falsifies that sentence, because the money can be withdrawn, at a
  spread. The refusal itself is **not** deleted, and the reason it survives is
  **narrower than the first draft of this specification claimed.** Its fund arm fires on a
  `FundProjection` whose `exit_line is None` — *"no exit was requested"* — which is a fact about
  the **plan**, not about what the fund owes. Under `liquidity_mode = "legal"` the distinction
  holds and the arm is right: neither Inzhur fund owes a buyback before termination (006 FR-015),
  so there is nothing to sell into. Under `liquidity_mode = "practice"` it does **not**:
  `core/results/fund.py` states that practice mode *is* the assumption that the buyback happens,
  `data/instruments/inzhur_miltech.toml` declares a same-day revocable buyback, and Inzhur
  publishes a MilTech sell price. So a practice-mode fund held with `exit_on = None` refuses today
  as `CannotSpanHorizon` where FR-029's reading says it should be sold. Whether the fund arm
  narrows to legal mode is **feature 010's to decide** under 014 FR-006; this specification
  records the case and does not re-decide it.
- **FR-030**: A section MUST report **no evaluated candidate** rather than a candidate whose
  money arrives after its `horizon.end`. Not a labelled figure, not a caveated one: the candidate
  does not appear among that section's evaluated population, and the section carries a typed
  part-refusal naming the candidate and the date its money actually arrives.
  **This is this feature's own rule, and it deliberately needs no change to 010's union** — FR-014
  already makes a section-level part-refusal cheap, so the prohibition costs nothing that is not
  already built.
  A label was the obvious alternative and it is refused, because measured on 2026-08-30 it
  produces exactly the failure this specification exists to prevent: at a one-month horizon
  `inzhur_miltech` is the **only** evaluated candidate, so under a label rule the section *is*
  one number — 18.11%, measured over a span running to 2028-01-20, wearing a caveat. A reader
  takes the number. *"Nothing could be ranked at one month, and here is why for each"* is the
  result User Story 2 argues for, and it is only available if the figure is withheld rather than
  annotated.
  **FR-029 does not reach this case**, which is why it is a separate requirement: MilTech's span
  runs long because the **plan requested an exit in 2028**, not because the instrument's terms
  outlive the window, so no rule about selling at `horizon.end` touches it.
- **FR-031**: The resale price an early exit is struck at MUST come from a **declaration**, and
  its absence MUST refuse **by name**, naming the instrument and the missing term. No shipped
  declaration carries one today, so this refusal is the shipped behaviour rather than a guard that
  reads as protection.
  **Where that refusal lives is 010's and 016's to settle, and this feature MUST NOT assume it.**
  `DeclarationMissing.part` is a closed five-member literal over the tuple's *parts* —
  `instrument`, `access`, `route_in`, `route_out`, `tax_class` — and a resale price is a **term**
  within one of them. If 016 declares the resale price on the access record beside `price.per_unit`
  then `part = "access"` with the term named in `what` is the existing home and nothing widens; if
  it is declared on the instrument, or as its own kind, then the union moves. The requirement here
  is that the refusal names the instrument and the term; the requirement it is **not** making is
  that a new union member exists. **This waits on 016**, and a planner must not settle it early:
  deciding it before the resale price has a declared home is how an eighteenth refusal gets added
  that a landed test then counts.
- **FR-032**: The assumption that **the observed spread holds at the exit date** MUST be
  **declared data with no default**, on 004 FR-006 and 002 FR-028's precedent, and MUST be
  marked. Every figure computed through it MUST inherit the mark and MUST reach the reader
  carrying it (Principle I: a derived figure that loses its parent's mark is a defect). It MUST
  NOT be inventable per run and MUST NOT be a constant in the engine: it is a belief about the
  future, which is `data/scenarios/`' kind of fact, not the engine's.
- **FR-033**: An early-exit figure MUST state, as a typed exclusion under FR-023a, that it
  carries the platform's spread and **not** rate risk. It MUST state **two claims separately**,
  because they have different warrants and only one of them has a sign:
  - **Certainty, and it is signed.** The figure replaces a distribution with a point, for the one
    option chosen precisely for its optionality. The early exit is therefore reported as **more
    certain** than it is, unconditionally.
  - **Level, and it is *not* signed.** Rate risk is **symmetric**: a bond sold after rates rise
    fetches less than its spread implies, and one sold after rates fall fetches more. The record
    MUST NOT claim a direction here. A separate and genuinely signed omission sits beside it —
    the *spread itself* is a seller's quote under today's conditions and widens exactly when a
    forced sale is most likely, so the **spread** is understated — and it MUST be carried as its
    own claim rather than folded into the rate-risk one, which it does not support.

  An approximation whose sign is unstated is incomplete; one whose sign is **asserted without a
  warrant** is a number more confident than its inputs, which is worse.

### The reserve: what he may need back

- **FR-016**: A question MAY declare one or more **reserves**: an amount, its currency and a
  date. Each reserve MUST produce a verdict per `(candidate × horizon)`.
- **FR-017**: The verdict MUST have exactly two values, and the second is a refusal:
  **covered by the plan** — the candidate's own arrivals put an amount at a declared spendable
  endpoint, in the reserve's currency, at least equal to the reserve, on or before its date — or
  **a partial exit would be needed, and a partly-liquidated holding is not projected**, naming
  what is missing. There MUST be no third value asserting that the reserve *cannot* be met.
  **The refusal names the projection and not the price, and the distinction is the correction the
  owner made on 2026-08-30**: after FR-031 a resale price is a declaration like any other and
  selling 20 000 of a 50 000 position is priced by the same term. What does not exist is the
  *projection* — a holding partly sold on a date carries different remaining cash flows and
  consumes basis under 009's declared consumption method, which is a modelling change and not a
  lookup. Refusing for a missing price where a missing projection is the truth would send the
  owner to declare a number that would not help.
- **FR-018**: A reserve verdict MUST NOT drop a candidate, remove it from a ranking, or change
  its order. A liquidity floor is a **constraint** (`SIMULATOR_SPEC.md` §4.10.4, required test
  **I3**) and constraints are a later feature; 014 FR-006 forbids a feasibility rule outside
  010's `TupleRefused` union, and a verdict that silently removed an option the owner might
  accept would be exactly that rule smuggled in one layer up.
- **FR-019**: A reserve verdict MUST name **which arrivals it read**, so that a verdict computed
  over arrivals falling past the horizon's end is visible as such (014's recorded
  `horizon-as-a-latency-budget` gap, whose second half is unrefused rather than mis-measured).

### The answer

- **FR-020**: The `Answer` MUST carry only typed values and the reason strings the core records
  already carry, **verbatim**. It MUST NOT carry a headline, a verdict sentence, a summary, a
  rendered table, a formatted number or any prose composed by this feature. The core formats
  nothing (Principle III), and the `Answer` is the contract with an interface that does not exist
  yet — a sentence baked into it is a decision taken on behalf of a UI nobody has chosen.
  **This forbids the shape `TupleOutcome.excludes` uses**, and the collision is resolved in the
  strict direction rather than by weakening the scan. `EXCLUDES` is a `frozenset[str]` of composed
  sentences — `'inflation (every figure here is nominal)'` is a live value — which is right for a
  record whose exclusions are a fixed, hand-written set, and wrong for an answer's, which are
  *computed per run* and must name an instrument, a term and a remedy. Every exclusion this
  feature produces is therefore a **typed record with named fields** (FR-023a). A tuple's own
  `excludes` is carried through **verbatim** as a core record's own words, which is what FR-020's
  first sentence already permits.
- **FR-020a**: The CLI MUST render the record and MUST NOT add a fact to it — no figure it
  computed, no verdict it inferred, no field the record does not carry. A refusal MUST reach the
  reader as a refusal with its reason, never as a blank, a dash, a zero or an omitted row: *a
  chart that cannot express "this figure refuses to exist, and here is why" is worse than a table
  that can* (`docs/DIRECTION.md`).
- **FR-020b**: The answer MUST NOT be presented as advice and MUST produce no filing (Principle
  I). This is the first deliverable a person reads rather than a test module, so the rule stops
  being structural and starts being a property of the output.
- **FR-021**: This feature MUST **derive** no exchange rate and MUST read none from a series. It
  MUST NOT convert one stream's amount into another's, MUST NOT value an outlay in a second
  currency to produce a rate, and MUST NOT consult a channel rate or feature 011's official rate
  for either purpose. Amounts are per stream in each stream's own currency (014 FR-005), a
  cross-currency candidate is evaluated and reported and **not ranked** (010's
  `RateNotComparable`), and a reserve in a currency a candidate's arrivals do not deliver is *not
  covered by the plan* rather than converted.
- **FR-021a**: A question MUST be able to carry an **owner-stated exchange-rate assumption on a
  run plan**, and this does not weaken FR-021. The two are different acts: FR-021 forbids the
  engine from *finding* a rate, and this requires the owner to be able to *state* one, which 014
  FR-003 already lists among the plan fields that have no default anywhere in the stack.
  Without it a declared fund whose payouts are sized in one currency and paid in another refuses
  permanently — measured, that is `inzhur_reit`, one of the **two real declarations in the whole
  registry** — for a reason this feature would otherwise have forbidden itself from supplying.
  The assumption MUST be marked and MUST propagate exactly as FR-032's spread assumption does: it
  is a belief about the future, and every figure computed through it inherits the mark.
- **FR-022**: Where a section's set spans more than one stream, the answer MUST carry 014's
  `MoreThanOneStreamInTheSet` as that section's outcome. The question shape does **not** avoid
  the recorded `one-amount-per-stream-in-compare` gap — it makes it easier to reach, because a
  person naturally states an amount for each of his streams — and this feature surfaces it rather
  than resolving it. It is unreachable from the shipped registry, where the dollar stream
  connects to nothing inbound.
- **FR-023**: The answer MUST carry **the whole question** and the `as_of` it was answered under,
  beside every count it reports (014 FR-012, one layer up).
- **FR-023a**: The answer MUST state what it excludes as a set of **typed records**, never as
  composed sentences (FR-020). Each record MUST carry: which exclusion it is, drawn from a closed
  set; what it applies to, where it is specific to one candidate; and **what would supply it**,
  named as a feature or a declaration rather than as a search. The closed set MUST include at
  least the three the measurement found: **no real-terms figure** (the rate reported is nominal;
  the real slot exists on 001's hurdle and on nothing a tuple produces), **no income tax on the
  stated amount** (a question about a stream, and charging it here would charge the owner twice
  for money he already holds), and FR-033's rate-risk exclusion. An exclusion that is not stated
  is a silent default, which is the top severity class regardless of how small the omission
  looks — and one stated as a sentence is a headline in the UI's contract.
- **FR-024**: The answer MUST carry the union of provenance marks and the merged staleness
  verdict of every declaration read, and every figure derived from an unverified, stale or
  synthetic input MUST carry the mark at the point the figure is reported — not only on the
  answer as a whole. **The `Answer` carries `Provenance` and `StalenessVerdict` — core records —
  and never a `Mark`**: `Mark` is an `api.diagrams` enum, and a core record importing it fails
  `lint-imports`. Rendering those two into marks is the api layer's, through the function that
  already does it (`marks.epistemic`, which takes provenance and a staleness verdict precisely so
  the core need not know what a mark is); no fourth mark is introduced here. Measured 2026-08-30: the shipped set is both unverified and synthetic, so an
  answer that presented a clean figure would be presenting a fixture as an observation.
- **FR-025**: Every answer MUST carry a **run manifest** naming every declaration file the run
  read with its SHA-256, the question file among them, the as-of date, the regime, the code
  version, and the unverified sources behind the figures. *A result without a manifest is not a
  result* (Principle III).
- **FR-026**: `Refused` MUST be returned **instead of** an `Answer`, never beside one, and MUST
  be reserved for what is wrong with the **question**: no horizon declared, no subject declared,
  an amount for a stream the registry does not declare, **a declared stream for which the
  question states no amount**, a benchmark outside the subjects, a benchmark instrument yielding
  more than one candidate, two identical horizons. The missing-amount case is named explicitly
  because it is the one that fails *silently* today: a stream with no stated amount whose pairs
  yield no candidates never reaches 014's `survey`, so nothing raises and nothing refuses, and
  the answer is simply missing a stream nobody mentioned. In a file under review an omitted
  amount is a typo, not a fact about the money (FR-004's rule). Anything about
  one horizon, one pair or one candidate is a part-refusal inside an `Answer` (FR-014).

### Determinism and order

- **FR-027**: The same question, registry and `as_of` MUST produce an equal answer, field for
  field, and an equal canonical digest. Loading the declarations in a different file order MUST
  change nothing (014 FR-016 and SC-003, one layer up).
- **FR-028**: The answer MUST be computable with no clock, no I/O, no logging and no
  randomness; `as_of`, the horizons and the regime are the caller's and the question's
  (Principle III).

## Key Entities

- **Question** — a declared, owner-scoped artefact: subjects, horizons, amounts per stream, run
  plans per subject, a benchmark, a regime, a continuation assumption and any reserves. Canonical;
  the CLI builds the same record from flags.
- **Answer** — one question, one `as_of`, one section per declared horizon, plus the populations
  that do not depend on a horizon: the subjects the registry does not declare, the pairs that
  yielded no candidate, and the merged provenance and staleness. Plus its manifest.
- **Horizon section** — one horizon and one outcome, where the outcome is 014's `CandidateSurvey`
  or any of its typed refusals, carried whole. A failed section is a section, never a missing one.
- **Group** — a declared label an instrument declares itself to be in, and the vocabulary a
  question is written in. Not a rule, not a plugin interface, and never inferred (FR-007a). An
  instrument may be in several.
- **Named subject** — one entry in the question's subject list: an instrument id, a group id, or a
  word that resolves to neither. Resolves to a **set** of ids; the sets may overlap and the union
  is what is enumerated (FR-007b). Carries one of three states per section — undeclared, declared
  but unreached, reached — whose remedies differ.
- **Undeclared subject** — a named subject resolving to no id at all: `cash` and `btc` today. Its
  own population, reported by the word the owner wrote; its remedy is a declaration.
- **Reserve verdict** — per `(candidate × horizon × reserve)`: covered by the plan, or a partial
  exit would be needed and none is modelled. Never a claim that the reserve cannot be met.
- **Refused** — the question itself did not stand up. A different type rather than a weaker
  answer, on `CompositionRefused` and `BenchmarkUnavailable`'s precedent.

## Success Criteria *(mandatory)*

- **SC-001**: The owner's question, checked in as a declaration and answered over the shipped
  registry at `as_of` 2026-08-30, produces **three sections, 7 candidates enumerated in each, and
  no ranking in any of them** — every count derived from the labels and declarations the test
  loads, never hard-coded. **Seven and not nine**: his four words resolve to five `ovdp` ids and
  two `inzhur` ids, and the registry's other two instruments are in neither group (*The
  measurement* item 4). A criterion pinning nine would be pinning *the whole registry*, which is
  not the question he asked — and the cheapest way to satisfy it would be the inference FR-007a
  forbids. It deliberately does **not** pin which refusal each dropped candidate carries: item 5
  records those as the **pre-feature baseline**, and FR-029 and FR-030 are changes that move
  them. SC-023 and SC-027 own the post-change claims, and a criterion
  pinning both would be two criteria that cannot pass together.
- **SC-002**: The owner's question names **four** subjects. `cash` and `btc` resolve to no id and
  are reported by the word he wrote (FR-009); `ovdp` and `inzhur` resolve to id sets, and every
  section reports each named subject's state among the three of FR-010 with the counts beside it.
  The membership is derived from the labels the registry declares, never hard-coded — which is
  what makes the criterion still true after 016 adds 24 issues to one of the groups.
- **SC-003**: A scan asserts the `Answer` record carries no string field that this feature
  composed: every string in it is an id, or a reason produced by a core record, compared
  byte-for-byte against the record it came from (FR-020).
- **SC-004**: A scan asserts **no rate is derived and none is read from a series** anywhere in
  this feature's modules, and that none imports `core.tax.official_rate` (FR-021). Deliberately
  **not** "no exchange rate anywhere in this feature's modules", which is what an earlier draft
  said: FR-021a requires a question to carry an owner-stated rate, and the question loader is one
  of this feature's modules, so the blanket form would forbid the record the owner states. SC-028
  scans for the same property from the other side and the two use one wording.
- **SC-005**: A question file with an unknown field, a missing field, a duplicated subject, two
  identical horizons, or an amount whose currency its stream does not declare fails at load,
  naming the file and the field, in every case — one assertion per case.
- **SC-006**: Answering twice produces equal answers and equal canonical digests. Answering over
  declaration files **renamed so they sort differently** produces an equal **computed result** and
  an equal canonical digest — stated over the result rather than over the whole answer, because
  FR-025 puts a manifest inside every answer and a manifest names its inputs by `directory/name`.
  Those names *must* differ after a rename: that is the manifest doing its job, not a
  nondeterminism. The canonical form already excludes provenance for the same class of reason
  (`tests/golden/test_candidate_set.py`), and this is that rule applied to file identity.
- **SC-007**: Editing any single declaration file the run read moves exactly one digest in the
  manifest and no other, including the question's own file (FR-025, H3).
- **SC-008**: A scan asserts that every file under `data/` the run read appears in the manifest,
  by walking the loader's inputs rather than by sampling — which is what makes H3 claimable.
- **SC-009**: A question declaring three horizons of which the first refuses as a whole (a
  missing run plan for a reachable subject) still returns an `Answer` whose other two sections are
  computed and complete (FR-014).
- **SC-010**: Across a battery covering every member of 014's `EnumerationRefused` and
  `SurveyRefused` and 010's `BenchmarkUnavailable`, each planted in one section, the answer
  stands and exactly one section carries the planted refusal, unmodified.
- **SC-011**: A question naming a benchmark outside its subjects, and one naming a benchmark
  instrument that yields two candidates, each produce a `Refused` naming the cause and **no**
  answer (FR-026).
- **SC-012**: The candidate sets of the three sections are asserted equal by key on the shipped
  registry, and a fixture in which they differ produces a reported finding rather than a silently
  chosen set (FR-013).
- **SC-013**: The cross-horizon reading recomputed from the answer equals the reading reported, in
  every generated case, and a scan finds no stored field holding it (FR-015).
- **SC-014**: A reserve dated one day before and one day after a candidate's qualifying arrival
  flips the verdict between its two values, and the candidate is present, evaluated and ranked
  identically in both runs (FR-017, FR-018).
- **SC-015**: A reserve in a currency the candidate's arrivals do not deliver produces *a partial
  exit would be needed*, and no rate is consulted (FR-021).
- **SC-016**: A fixture registry declaring the inbound USD corridor the shipped one lacks produces
  a candidate funded from `contract_usd`, whose tax figure drops as
  `TaxCurrencyConversionUnavailable` naming the empty `ua_nbu_usd` series — the gap made
  reachable, on 014's own technique for the same purpose.
- **SC-017**: Every figure in an answer derived from a declaration marked unverified or synthetic
  carries the mark at the point it is reported, verified by a walk over the whole result rather
  than by sampling (FR-024, 010 SC-007's rule).
- **SC-018**: A golden artefact records the owner's question and its whole answer over the shipped
  registry, regenerated deliberately, with provenance excluded from the digest so that filling in
  a `verified_on` cannot move it (`tests/golden/test_candidate_set.py`'s established discipline).
- **SC-019**: The CLI produces, from flags, a question record equal field for field to one loaded
  from the equivalent file. The scan asserts the CLI declares no option expressing a **question
  field** the file cannot express — and exempts, by name, the values that are deliberately not
  question fields: `--as-of` (FR-006 puts it on the verb), and the segment bound and candidate
  ceiling, which are declared in `data/composition/` and `data/candidates/` and reach the verb
  through its second parameter. An unscoped scan fails on all three and would push them into the
  question file, which is the opposite of what FR-006 decided.
- **SC-020**: A question whose subjects the registry declares none of returns an `Answer` with
  every named subject in the undeclared population and every section empty with its reason —
  distinct from an answer over a registry that declares nothing at all.
- **SC-021**: Every answer states its exclusions, and a walk over the result asserts that no
  real-terms figure and no stream income-tax figure appears anywhere in it — the exclusion and
  the absence checked against each other, so neither can drift from the other (FR-023a).
- **SC-022**: Rendering the owner's answer through the CLI produces output in which every one of
  the three sections' refusals appears with its reason text, asserted by finding each reason
  string in the output — no blank, no dash, no zero and no omitted row (FR-020a).
- **SC-023**: Every candidate that drops as `CannotSpanHorizon` with `binding_term =
  "instrument.maturity_date"` under the pre-feature baseline instead refuses for a **missing
  declared resale price**, naming the instrument and the term (FR-029, FR-031) — the count
  unchanged and the remedy changed. Asserted **per section**, because the population differs by
  horizon: measured 2026-08-30 under group resolution, **five** at one and three months and
  **only three at twelve**, the other two evaluating on their own terms. Derived from the registry the test
  loads, never hard-coded.
- **SC-024**: A fixture instrument declaring a resale price and a declared spread-holds
  assumption produces an early-exit figure at `horizon.end`; removing the assumption's
  declaration refuses at load naming the file and the field, and never falls back to a constant
  (FR-032).
- **SC-025**: Every figure computed through the spread-holds assumption carries its mark, verified
  by a **walk over the whole result** rather than by sampling (FR-032, Principle I). The first
  draft's second half — *a scan asserting no path from a marked assumption to an unmarked figure*
  — is deleted: it is a static dataflow claim over the whole engine, which no scan in this
  repository implements and which would have passed by asserting nothing. The walk is the
  implementable half and it is the one that catches the defect.
- **SC-026**: Every early-exit figure states FR-033's three claims with the sign on exactly two
  of them: a scan asserts a direction **is** present on the certainty claim and on the
  spread-is-understated claim, and **is absent** on the rate-risk one. The absence is asserted,
  not tolerated — an implementation that signs rate risk fails, which is the whole content of
  this criterion after FR-033 split. Written the other way round in an earlier draft, where it
  required a sign everywhere and so failed compliant output; the two cheap repairs available then
  were to write the unwarranted direction back, or to let the scan find a sign nearby and pass
  vacuously, and both are worse than the defect.
- **SC-027**: A candidate whose arrivals fall after `horizon.end` appears in **no** section's
  evaluated population, and the section carries a typed part-refusal naming it and the date its
  money arrives. Asserted on `inzhur_miltech` at a one-month horizon — which under the baseline
  is that section's **only** evaluated candidate, reporting 18.11% over a span to 2028-01-20 — so
  the criterion is exactly that the one-month section ranks **nothing** and says why, rather than
  returning one caveated number (FR-030).
- **SC-028**: A question carrying an owner-stated exchange-rate assumption on `inzhur_reit`'s run
  plan produces an evaluated candidate where the baseline produces `PegUnsizable`, and every
  figure computed through that assumption carries its mark; removing the assumption returns the
  refusal naming `FundAssumptions.exchange_rate`. A scan asserts no rate is derived and none is
  read from a series in either case (FR-021, FR-021a).
- **SC-029**: A question that states no amount for a declared stream refuses at load naming the
  stream — asserted for a stream that yields candidates **and** for one that yields none, since
  the second is the case that passes silently today (FR-026).
- **SC-030**: An instrument in **two** named groups, and a question naming both a group and one
  of its members, each yield **one** candidate for that instrument and count it **once** in the
  enumerated total — while the named-subject count still reports both subjects (FR-007b, FR-010).
  The two counts are asserted together, because the defect is them being conflated. **The
  fixture's group size MUST differ from the number of named subjects**: a group of exactly two
  named by two subjects makes both counts 2, and a conflated implementation passes. Set sizes
  that happen to coincide are the standing way a discrimination test asserts nothing.
- **SC-031**: An instrument declaration naming an undeclared group fails at load naming the file
  and the field; a **question** naming an undeclared word does not fail and appears in FR-009's
  population. Both asserted, because the asymmetry is the requirement.
- **SC-032**: A scan asserts group membership is read from the declared label alone: adding an
  instrument whose class, id prefix, tax class and `bought_at` all suggest a group it does not
  declare puts it in **no** group. The fixture is built from the **four** live near-misses
  FR-007a names, one per attribute, so the test fails if any of them is ever consulted.
- **SC-033**: The answer reports each named group's resolved ids and their count (FR-008a), pinned
  by a **pair** of fixtures over the same added instrument: added **without** the label the count
  is unchanged, and added **with** it the count rises by **exactly one**, with the new id in the
  reported membership. The pair is the criterion — the unchanged half alone passes for at least
  three broken implementations: a resolution field that is always empty, one computed once and
  cached, and one read from the group declaration file rather than from the labels the instruments
  carry, which is a live design fork rather than a hypothetical. Only the second half
  distinguishes *the label is read* from *nothing is read*.

## Assumptions

- **The amount is money already at the routing origin, deployed once.** 010's `evaluate` takes one
  amount at `horizon.start`, and a dated series of ramp-and-purchase events is 010's FR-018
  deferral. "I have 50,000 UAH" is exactly a lump, so the owner's question fits what is built;
  a question meaning *my monthly salary* does not, and this feature does not pretend otherwise.
- **Two of the owner's six "including" terms are excluded rather than computed**, under FR-023a
  and for the reasons the measurement records. Neither is a gap this feature opens.
- **Feature 014's `survey` and 010's `compare` are called, not forked.** This feature adds a
  caller and a declaration kind, not a variant. It does **not** follow that nothing outside its
  own module changes, and the first draft's *"and nothing else"* was false — it counted to two,
  named one, and denied three. The complete list, each made and reviewed where it lives:
  - **feature 014** — a declared subject set on its `Question`, and `_considered` narrowed to it
    (FR-008);
  - **a group declaration, and labels on the shipped instruments** — group ids declared, each
    instrument declaring which groups it is in (FR-007a). Data rather than code, and no plugin
    interface, but not free: **without labels the owner's question resolves `ovdp` and `inzhur` to
    nothing**, every section reports four undeclared subjects, and the feature cannot demonstrate
    itself. Which fixture belongs in which group is a labelling judgement about the owner's own
    vocabulary, not a legal or market value;
  - **feature 010** — FR-029's bond arm, and the home for FR-031's missing-resale-price refusal.
    FR-030 was moved out of this list deliberately: it is now this feature's own section-level
    rule and needs no change to 010's union;
  - **`scripts/check_provenance.py`** — `data/questions/` named in `EXEMPT_DIRS` with its reason
    (FR-003). The gate is fail-closed, so the directory cannot simply appear;
  - **`terezy.data.manifest`** — the largest of the four and the easiest to miss. `RunManifest` is
    **single-projection shaped**: it carries a `projected_instrument_id`, one `holding`, one
    `Assumptions` and one `horizon`, and it has **no `as_of` and no `regime`** — both of which
    FR-023 and FR-025 require an answer's manifest to record. `InputKind` is a **closed
    five-member `Literal`** (`cpi_series`, `fund`, `inflation_assumption`, `instrument`,
    `tax_class`) with no member for a `question`, a `route`, an `access` declaration, a `stream`,
    a `spendable` endpoint, a `composition` set or a `tax_destination` — and SC-008 requires the
    manifest to name **every** file the run read. Widening a closed set is a code change reviewed
    against the claim the set exists to support, which is that set's own rule.
- **The benchmark is named by instrument id.** Measured 2026-08-30, the shipped registry yields
  exactly one candidate per instrument, so it resolves; more than one refuses (FR-026) rather than
  settling by file order which figure everything is ranked against.
- **No legal, tax or fee value is introduced.** Nothing in answering a question needs one. Where a
  value would be needed — a cash instrument's terms, a BTC instrument's terms and tax class — it
  is an owner verification task below, not a guess.
- **One owner, one regime per question, loopback only.** The authentication gate (Principle VII)
  is not reached: this feature ships a file, a verb and a CLI, and listens on nothing.

## Subjects are ids or groups, because the owner asks in groups

**Owner decision, 2026-08-30**, taken after a review found that no subject list could satisfy two
of this specification's own criteria. The alternatives were: a subject is an **id only**, and his
question names all nine registry ids plus `cash` and `btc`; or a subject is an id **or a declared
group**; or ids only and the answer **never counts** named subjects. The second was taken, and
FR-007 carries the reason and its 016 argument. The other two are recorded here because each is
the shape of a proposal someone will make again:

- **Ids only** puts nine fixture ids in a question a person writes, and after 016 thirty-three.
  Every new issue is a hand edit that is silently wrong until somebody makes it — which is the
  failure mode the group exists to remove, so the option defeats its own purpose at exactly the
  moment the registry becomes real.
- **Never counting named subjects** is the cheapest of the three and drops FR-010 and half of
  SC-002 with it. It loses the one line in the answer that speaks to what he actually asked:
  *you named four things and two of them can be answered*. That line is the reason this feature
  is worth running against a registry that can answer almost nothing.

What the decision costs is a new declaration — group ids, and a label on each instrument — and
that cost is named under *Assumptions* as work this feature must do rather than left to be
discovered. **Labelling the shipped instruments is part of it**: without labels the owner's
question resolves `ovdp` and `inzhur` to nothing and the feature cannot demonstrate itself.

## Owner verification tasks

1. **A cash declaration.** The naive baseline he named first does not exist as an instrument. Its
   terms — what a hryvnia balance held at `monobank_uah` earns, if anything — are a market fact
   needing a citation and a `verified_on`, and are not mine to invent. Note that declaring it is
   **necessary and not sufficient**: bought at the venue the money already sits at, it reaches
   `compose`'s *money that is already where it was wanted* and stands in the no-candidate column
   until the recorded `zero-hop-way-in` gap is closed. The constitution requires naive baselines
   always scored and always shown, so this row staying open is a stated deficit rather than an
   oversight.
2. **A BTC declaration.** No instrument, no access declaration, and no settled tax class. The
   crypto material already in the repository is about *ФОП income credited to an exchange*
   (`data/tax/destinations/ua.toml`, the `coinbase` row), which is a different proposition from
   the disposal of a held position. Every part of it is a legal or market value that must come
   from a cited source entered as data.
3. **Confirm the question's own facts**: that the 50 000 UAH is at `monobank_uah` and therefore
   funded through the `salary_uah` stream's routing origin; the exact reserve date meant by
   "within six months"; and the start date the three horizons run from — which the question
   declares explicitly, because `as_of` decides staleness and nothing else.
4. **"Adverse scenarios" and "inflation" as asked for.** He named both and neither is answered
   here. *Adverse scenarios*: regimes exist under `data/scenarios/` and one question declares one
   regime (014 FR-023), so comparing under two regimes is two questions and a reading across them
   — confirm whether that is what he wants, or whether a scenario sweep is the feature he is
   actually asking for, in which case it is I7 and later. *Inflation*: measured 2026-08-30, a
   tuple has no real-terms rate at all — the slot exists on feature 001's hurdle and nowhere in
   `TupleOutcome`. Deflating a tuple's nominal rate is a new figure with a formula, a
   `docs/METHODOLOGY.md` entry and a worked example, and it is a change to 010 rather than a
   presentation choice here. Confirm whether that is the next feature he wants, ahead of 016.

## Questions that were drafted and closed

Recorded rather than deleted: each looked open, and the reasoning that made it look open is the
reasoning someone will repeat.

**Should a question naming an undeclared subject refuse as a whole?** It looked open because 014
FR-018 refuses the whole enumeration for a reachable instrument with no plan, and by analogy an
answer to "compare these four" that covers two is an answer to a different question — which
Principle I calls a false optimum. Closed by splitting the two facts apart: the *answer* stands
(FR-009), because refusing it discards three real findings and hides the one line that matters
most, while the *ranking* is fenced (FR-010), because a ranking of two read as a ranking of four
is exactly the failure the analogy is about. Refusing the whole answer would have made the tool
useless on the day it was built, for a reason that only ever bites a ranking.

**Should the horizons be three questions rather than one?** Closed on a measurement and a rule.
The measurement: the candidate set does not depend on the horizon, so sections align by key with
nothing to reconcile. The rule: 010's *one horizon, stated once* is about the unit of
computation, which FR-012 leaves untouched. Three files would produce three artefacts, three
manifests and no way to read the cross-horizon fact — that the ranking at one month is not the
ranking at twelve — which is the answer to what he asked. What decided it against the alternative
is that this is one decision by one person on one day, and the artefact should be the decision.

**Should the reserve exclude candidates that cannot meet it?** Closed against 014 FR-006 and
`SIMULATOR_SPEC.md` §4.10.4: a liquidity floor is a constraint, constraints are I3, and a new
reason to consider a candidate infeasible is a change to 010's union made and reviewed there.
Reporting rather than dropping survived the clarification: an early exit at the window's end is
now the semantics, and the reserve is still a *partial* exit at a date of the owner's choosing,
which is a different and unbuilt thing.

**Should `as_of` live in the question file, so the artefact is wholly self-contained?** Closed on
014's own words — `as_of` *decides staleness and nothing else* — and on the consequence: a file
whose horizons moved with the calendar would be a different question every day under one digest,
which is worse than a digest that does not cover the clock. The manifest records both.

**Should the answer carry a rendered summary for the CLI to print?** Closed on Principle III and
D-B. The core formats nothing, and a sentence in the `Answer` is a decision taken on behalf of a
UI framework the owner has deliberately not chosen. Rendering is `cli/`'s, over the same record a
UI would read, and FR-020a is what stops the rendering becoming a second place facts are decided.

**Should a question be able to declare a bound on its own horizons?** Drafted while asking what
stops a question costing an hour, closed by FR-014a: the candidate ceiling already bounds each
section, and the thing it guards against — a registry that grew past what enumeration suits — has
no analogue in a hand-written list of dates. A second declaration with no failure mode is a line
the owner would be asked to choose a number for and never hear about again.

*The `/speckit-clarify` pass on 2026-08-30 raised these three and no more. The taxonomy items it
found Partial were data volume, the CLI's surface, and the not-advice rule, and all three closed
against precedent in this repository rather than against the owner's judgement. The one question
that did not close went to the owner and is answered under* Clarifications *above.*

## Required tests this feature closes

| Row | What it asserts |
|---|---|
| **H3** | Every data file's values round-trip through the run manifest, so a result traces to the exact configuration that produced it |

H3 is claimed on **SC-007 and SC-008 together**: one digest moves per edited file, and a walk over
the loader's inputs proves the manifest names every file the run read rather than a sample of
them. The question's own file is an input reference like any other, which is what makes an answer
traceable to the sentence that asked for it.

**No row in Section I is closed.** I1 is 014's and is closed at the tuple level. I2–I7 are
objectives, constraints, the naive-baseline allocation, stability, indifference bands and
*sometimes best* versus *never bad* — every one of them a thing this feature is forbidden to
invent. **J4 is touched and not claimed**, on 014's terms unchanged.

## Out of scope

Named explicitly so the plan does not drift: **objectives and constraints** (I2, I3) and any
ranking rule other than 010's existing rate; **shadow costs**; **the naive baseline's allocation
half** (I4); **stability** (I5); **indifference bands** (I6); **sometimes-best versus never-bad**
(I7); **the non-dominated set**; **allocations and portfolios of any kind**; **scenario sweeps and
Monte Carlo** — one regime per question; **every change to 010's `TupleRefused` union except the
two FR-029 and FR-031 name**, which are required work listed under *Assumptions* — in particular
the second `horizon-as-a-latency-budget` gap stays 014's recorded gap rather than becoming work
here, because FR-030 answers it at the section level instead; **the `one-amount-per-stream-in-compare`
gap**, surfaced and not resolved (FR-022); **the `zero-hop-way-in` gap**, made visible and not
closed (FR-011); **the display-currency switch**; **partial disposal of a position**, which is
what FR-017's second verdict refuses by name; **a secondary-market model** — a bond's resale
price moving with market rates, recorded as `[[future]] secondary-market-rate-risk` and stated
with its direction rather than silently omitted (FR-033); **a real-terms rate for a tuple**, which does not
exist and whose absence is stated rather than filled (FR-023a); **authentication and any network
listener**; and
**the web UI**, whose framework stays unchosen until this feature's `Answer` has been read against
real output.

**Not out of scope, though a reader expects it to be**: the declared subject set in feature 014
(FR-008). It is a change to another feature's type, made and reviewed there, and without it a
question naming a subset of the registry refuses for every instrument it did not name.

## What this makes reachable, and deliberately does not build

- **The interface.** D-B's deferral ends when the `Answer` has been read against real output.
  This feature produces the first output a person reads, which is the input to that decision.
  `docs/DIRECTION.md` names the catch to carry into it: *a tracker's interface has no place to
  put a typed refusal, and flattening one into a blank cell is precisely the failure this project
  exists to prevent* — and every section of an answer over today's registry is a typed refusal.
- **The shortlist** (I2–I7) reads an `Answer`. Because a section carries 014's whole survey and
  014 FR-020 carries every dimension out of `evaluate`, an objective, a dominance pass or a
  stability check begins from this record rather than by enumerating and costing everything again.
- **A question set.** Two questions differing in one field — a regime, an amount, a horizon — are
  two files and two answers, and the deciding belief is read off the difference. That is I7's
  shape, and it needs no new machinery beyond a reading across answers, which is why one regime
  per question (014 FR-023) is not a limitation to be lifted.
- **Feature 016's payoff becomes measurable.** Today every OVDP figure in an answer is a fixture
  and is marked as one. The day real issues are declared, the same question over the same file
  produces marks that are no longer synthetic, and the golden artefact's diff is the evidence.
