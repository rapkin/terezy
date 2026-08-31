# Feature Specification: The declared working-day and public-holiday calendar

**Feature Directory**: `specs/017-working-day-calendar`

**Feature Branch**: `spec/017-calendar` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-30

**Status**: Specified and **unscheduled — this feature blocks nothing.** Both owner decisions
of 2026-08-30 are folded in (see "Clarifications"): CL-1 resolved to *record and defer*, and
018 was released from needing this feature at all, because the National Bank turns out to
publish an official rate for **every calendar day**. What remains is real but not urgent, and
"Why this feature exists" states the honest reason. Two owner verification tasks stay open;
neither changes the design, and the shipped state under both is the refusal that already
stands.

**Input**: The missing declaration kind. `core/tax/official_rate.py:31` says the module
"contains no notion of a weekend, a public holiday or a banking calendar", and 011 FR-018
records the consequence: the Ukrainian non-publication-day rule is written in working days,
pre-holiday days, weekends and post-holiday working days, so it **cannot be declared against
011's records at all**. That gap is real and this feature is what fills it; what changed on
2026-08-30 is that nothing needs it filled yet. This feature is that declaration — which dates a jurisdiction's law
calls working, which it calls holidays, and which it calls pre-holiday days — declared, cited,
bounded by an explicit coverage window, and refusing by name outside it.

---

## Why this feature exists

011 hit a wall and named it instead of working around it. Its module docstring is the
charter, and the sentence that defines this feature's job is
`src/terezy/core/tax/official_rate.py:31`:

> The one sanctioned escape is a **declared** non-publication-day rule … and this module
> contains no notion of a weekend, a public holiday or a banking calendar (FR-011).
>
> **A rule written in working days or public holidays cannot be declared against these
> records at all**, because evaluating one needs a working-day and holiday calendar and
> nothing declares one.

Nothing in the repository supplies one. `data/official_rates/ua_nbu_usd.toml:65` therefore
ships `observation = []` with no rule, and every date the National Bank did not publish for
refuses by name — naming the series, the pair and the date. That is correct behaviour, and it
sets this feature's bar: whatever lands here must not make anything *less* explicit than the
refusal it replaces. A calendar that guessed at a date outside its own coverage would be
strictly worse than no calendar, because the refusal it displaced was honest.

### Why it is nevertheless not blocking, established 2026-08-30

The premise that made this feature urgent was that a rate series has gaps a calendar is needed
to reason about. **It does not.** 018's specification established, and the owner verified
independently the same day, that the National Bank publishes an official rate for **every
calendar day**: Saturday 2026-08-29 and Sunday 2026-08-30 both return 44.5445, Monday
2026-08-31 returns 44.5505, and 1 January 2026 — a public holiday — returns 42.3532, each row
dated the day asked for.

Two things follow, and the second is the one that matters here:

1. **018 no longer needs this feature.** A series that covers every calendar day needs no rule
   to select an observation for a date, so 018's dependency on a calendar is gone.
2. **The residual case has a declared answer that needs no calendar.** The owner settled it in
   one sentence — *«є курс на неділю — супер, а як нема то бери останній робочий курс»* — and
   that is a **declared carry-forward rule**, precisely the sanctioned escape
   `core/tax/official_rate.py` describes: cited data stating which observation governs a date
   the publisher did not publish for, not a derivation in code. **Evaluating it needs no
   calendar while the series covers every day.** A calendar becomes necessary only if a series
   ever has gaps — and then only to decide *which* earlier observation is the last working
   one, rather than merely the last one.

**So what is this feature still worth?** Three consumers, and they are not alike — which is
the correction that matters, because the first draft of this section counted two and drew a
conclusion the third does not support.

- **Bond coupon and maturity dates** — `core/instruments/fixed_income.py:138`, `:521`, `:794`.
  **Reached today, and blocked on nothing but the calendar.** The only two declarations that
  name a business-day rule are `is_synthetic = true` fixtures the engine already marks in
  output, and every other bond in the tree is 013's enumerated form, which declares its dates
  and needs no calendar. So no figure anyone reads as correct moves through this path. The
  exposure is the **first real bond declared in the generative form**: no missing legal reading
  stands in its way and no missing declaration does, only that nobody has declared a calendar.
- **Fund settlement dates** — `core/instruments/fund.py:438`. Blocked on a **different
  calendar**: a fund's dealing days are Inzhur's, not Ukraine's, and nobody has retrieved
  them. A `civil` calendar is the wrong input here, which is CL-1's whole argument.
- **Tax due dates** — `core/tax/year.py:1821`. Blocked on a **legal reading**:
  `data/tax/timing/ua.toml` declares `non_business_day_rule = "none"` on all three categories
  (lines 57, 73, 89) precisely because the rule was never researched, so a calendar moves no
  due date until somebody answers that question.

**So the honest conclusion is narrower than "nothing needs this".** Two of the three are
blocked on something other than the calendar; the third is not blocked at all. What makes it
*unscheduled rather than urgent* is that placing a coupon on a public holiday is a **stated,
visible** wrongness — `_is_weekend` says so in its own docstring and `fixed_income.py` reports
the rule it applied — rather than a silent one, and no shipped instrument's figures are read as
correct while that sentence stands.

What the live consumer actually raises is **a scope question this specification is uniquely
equipped to ask, and deliberately does not answer**: is a coupon date moved by a
**jurisdiction's civil** calendar, or by the **settlement** calendar of the venue that pays it?
An issuer's terms may say either, and the two differ. FR-003's scope field is what makes the
question askable at all; answering it needs an issue's own terms read from a primary source,
which is nobody's task yet. Until it is answered, wiring `fixed_income.py` to whichever
calendar exists would be picking one by availability — the failure this whole feature is
written against.

### The engine already knows what a weekend is, and three modules consume it

This is the fact that changes the shape of the feature, and it is not in 011. Measured on the
merged tree at `021a587`.

The notion itself is one function and one constant:

- `src/terezy/core/primitives/conventions.py:196` — `_is_weekend` is `day.weekday() >= 5`,
  with `_SATURDAY: Final = 5` at line 51. Its docstring is honest about the *holiday* half of
  the gap — "Public holidays are declared domain knowledge with a citation and a verification
  date, and belong in `data/` … Until that data exists **a coupon** falling on a public
  holiday is placed on the holiday" — and silent about the weekend half, which carries no
  citation either.
- `src/terezy/core/primitives/conventions.py:208` — `is_business_day`, whose docstring makes a
  **promise this feature is the redemption of**: "the day public holidays arrive as declared
  data, one function changes and every settlement date changes with it."

**Three modules consume it**, two of them through the declared-convention registry
`conventions.business_day_rule` (`conventions.py:292`) over `BUSINESS_DAY_FNS`
(`conventions.py:256`), whose `following` and `modified_following` both loop on `_is_weekend`:

| Site | What it moves | Reached how |
|---|---|---|
| `src/terezy/core/instruments/fixed_income.py:138`, `:521`, `:794` | **Coupon dates and the maturity date** of a bond | `business_day_rule(terms.business_day_rule)` |
| `src/terezy/core/instruments/fund.py:438` | A fund redemption's **settlement date** | `is_business_day`, counting forward |
| `src/terezy/core/tax/year.py:1821` | A tax **payment deadline** | `business_day_rule(rule.non_business_day_rule)` |

**The first is the one the first draft of this specification missed.**
`data/instruments/ovdp_synthetic_a.toml:26` declares `business_day_rule = "following"` and
`ovdp_synthetic_b.toml:43` declares `"modified_following"`, so both shift dates off weekends
and place a coupon landing on a public holiday **on the holiday**, exactly as `_is_weekend`'s
own docstring says will happen until this data exists. **Both carry `is_synthetic = true`**,
which the loader and the diagram layer carry into output, so the wrongness is marked wherever
it surfaces — and the applied rule travels with it, in the emitted event's causation detail.
What is unguarded is the next declaration: nothing refuses a real bond in the generative form,
and the scope question below is unanswered when one arrives.

Reaching the notion **through the registry is not a narrower kind of consumption**: `_due_on`
reaches it the same way and is counted, so counting only direct callers of `is_business_day`
would be a distinction with nothing behind it — and it is precisely the narrowing that would
let FR-018's scan pass while asserting something false about the tree.

So the repository already contains a working-day notion; it is weekends-only, uncited, and
lives in code. A feature that declares a cited calendar and leaves that notion untouched
creates **two notions of a working day** — the exact drift shape this project keeps finding.
A feature that rewires it moves figures pinned by three other features' goldens, and for the
fund would point a *civil* calendar at a *settlement* question. That tension went to the owner
as CL-1 and came back *record and defer* on 2026-08-30; everything else here is settled by
argument below.

### Which of these three things a calendar asserts

Three different facts sit behind the phrase "the calendar", and conflating any two is the
shape of bug this project keeps finding — the same shape Principle VI names for currency:

| | What it is | Who says so | What it would decide |
|---|---|---|---|
| **civil** | Which dates a jurisdiction's law calls working, rest, holiday and pre-holiday | A statute, and an annual executive act moving working days | Whether a legal rule written in working days applies |
| **settlement** | Which dates a named operator actually deals or settles on | The operator's own published terms | When proceeds arrive (`fund.py:438`) |
| **observed publication** | Which dates a publisher in fact published a rate for | Nobody — it is an observation | Nothing; it is already declared |

**A calendar declaration in this feature asserts a `civil` calendar, and carries a declared
scope so it cannot be mistaken for either of the others.**

- **The observed-publication kind is refused outright and gets no scope.** It is already
  representable — it is the set of dates `OfficialRateSeries.observations` declares — and
  admitting it as a calendar would let a consumer ask "was this a working day?" and be
  answered from what a publisher happened to do. 011's edge cases say the engine "cannot tell
  the two apart and must not try" about a weekend versus a gap in the series; a calendar built
  from publication days would answer that question by construction, and answer it wrong.
- **The settlement kind gets a scope value and no declaration in this feature.** A fund's
  settlement calendar is a property of Inzhur, not of Ukraine, and the two genuinely differ.
  Reserving the scope now costs one closed-set member and makes the eventual venue calendar a
  data-only addition (Principle II); refusing to name it now would mean the first settlement
  calendar either gets declared as a civil one — the conflation — or forces a schema change.
- **Scope is a precondition, never a branch.** A consumer states the scope its question needs
  and a mismatch refuses, exactly as `strike_base` refuses a series that quotes another pair
  (`official_rate.py`, `OfficialRateSeriesUnavailable`). Nothing computes differently by
  scope. This matters because Principle II forbids branching on domain knowledge, and a scope
  that selected an algorithm would be exactly that.

### Enumerated, not generative — and the argument that decides it

013 faced the enumerated-versus-generative choice for bond schedules and settled it by
supporting **both** forms with no layer branching on which was used, enforced by a scan
(013 FR-011, FR-012; `tests/contract/test_no_layer_knows_the_form.py`). **That precedent does
not carry here, and the reason is a difference in kind rather than in degree.**

013's generative form is arithmetic over *declared* terms — a coupon rate, a periodicity, a
day count, a business-day rule — each of which the owner declares by **name**, selecting from a
registry the engine implements. That is not the same as a legal fact reaching the engine
through a declaration, and the distinction has to be drawn carefully, because **one of those
four already leaks**: `business_day_rule` is declared by name and resolves to a function
hard-coding Saturday and Sunday (`conventions.py:196`), so 013's generative form does today
rest on an uncited calendar fact in code. The right line is therefore not *no legal fact* but
**bounded**: what leaks through 013's registry is one weekday convention, closed, small, and
already named as a defect here (FR-017). A generative *calendar* form is a different order:

1. **It would put a legal fact in the engine.** "Easter Sunday is computed thus, and Trinity
   is fifty days after it" is not a convention somebody declares; it is a rule the engine
   would have to contain. Principle I forbids a legal value originating from an implementer's
   or an agent's memory, and a Paschalion in `core/` is precisely that, wearing an algorithm's
   clothes. `data/README.md` rule 4 says the same thing in one line.
2. **It would still be incomplete.** 011 FR-018 records that пункт 11 of the same розділ adds
   the Cabinet's power to **move working days**, which is exercised by an individual act each
   year and is arbitrary by construction. No rule generates it. A generative form would
   therefore need an enumerated override layer beside it — two forms *plus* a precedence rule,
   which is 013's cost without 013's benefit.
3. **And it is the form that would deepen the martial-law trap.** A generative form would
   express the suspension of the holiday regime as a rule conditioned on martial law being in
   force — one more mechanism keyed to the end of martial law, hanging off the same unstated
   belief as the military levy's sunset and the route-regime switch
   (`specs/features.toml`, `martial-law-ends-one-belief-two-places`). An enumerated calendar
   conditions on nothing: it declares what each year's law was, stops at its last declared
   year, and refuses past it. **A refusal is not a belief.** That is the argument that decides
   this, because it is the only one that makes the enumerated form *safer* rather than merely
   simpler.

The standing objection to an enumerated form is that it goes stale silently at its last
declared year. **That objection is answered rather than accepted**: the calendar declares an
explicit two-ended coverage window, and a date past either end refuses by name (FR-010). 011
FR-010 already ships that shape for a rate outside its window, and 013 FR-005 already
established a declared coverage claim as a declaration primitive — one-ended there because a
bond's schedule runs to the end of its life, two-ended here because a calendar knows both a
first and a last year. The staleness is therefore loud, not silent, which is the whole of what
the generative form was being considered for.

### What this feature deliberately does not finish

It declares a calendar and answers questions about dates. **It computes no money, changes no
figure, and moves no golden.** It has **no consumer in the tree**, by the decision above, and
FR-012 to FR-014 specify the queries a rule written in working days would ask — the shape
пункт 10 needs — without wiring any of them to a coupon, a rate, a settlement or a deadline.
Building a consumer here would put a rule and the calendar it is evaluated against in one
change and leave neither reviewable against its own tests; and while the only candidate
consumers are each blocked on something else, it would also be building against a need nobody
has.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A jurisdiction's working days are declared, cited and dated (Priority: P1)

The owner declares a calendar for a jurisdiction: its coverage window, the weekly rest pattern
its law sets, and every date inside that window whose classification departs from that pattern
— each public holiday, each pre-holiday day, each working day an executive act moved. Every one
carries its own source, retrieval date and verification date. Nothing is computed from a rule
the engine holds.

**Why this priority**: This is the feature. Without it the missing declaration kind stays
missing and 011 FR-018's gap stays open — unfilled rather than blocking, per the Status.

**Independent Test**: Declare a small, clearly-labelled synthetic calendar — a fortnight, two
declared holidays, one moved working day — and classify every date in it against a
hand-written table checked into the test.

**Acceptance Scenarios**:

1. **Given** a declared calendar and a date inside its coverage window, **When** the date is
   classified, **Then** the answer states whether it is a working day and which declared fact
   made it one — the rest pattern, an enumerated holiday, or a declared move — and no answer is
   produced from anything the engine knows on its own.
2. **Given** a date the calendar's declaration does not mention, inside the window, **When** it
   is classified, **Then** the declared weekly rest pattern decides it, and the answer says the
   pattern is what decided it.
3. **Given** a calendar whose declaration carries no weekly rest pattern, **When** it is
   loaded, **Then** loading fails naming the file and the field, rather than defaulting to
   Saturday and Sunday.
4. **Given** any declared holiday, pre-holiday day or moved working day, **When** it is
   inspected, **Then** it carries its own citation, its own retrieval date and its own
   verification date, and an empty verification date renders visibly marked.

---

### User Story 2 — A date the calendar does not reach refuses by name (Priority: P1)

A calendar covers the years somebody actually read the law for. Asked about a date outside
that, it says so — naming the calendar, the date and the window it does cover — rather than
extending its last year's pattern forward.

**Why this priority**: Equal-highest with Story 1, and for the reason 011 gives its own
refusal story P1: the wrong behaviour is silent and plausible. Extending the rest pattern past
the window produces a classification indistinguishable from a correct one, and any rule
evaluated against it would select a legal fact — an official rate, a settlement date, a payment
deadline — with no mark on it. The feature's bar is
that it must not be less explicit than the refusal it replaces, and this is the requirement
that meets it.

**Independent Test**: Ask a declared calendar about a date before its window, a date after it,
and a date whose classification would require walking past either end, and confirm all four
produce typed refusals naming the calendar and the date, and that no option makes any of them
answer.

**Acceptance Scenarios**:

1. **Given** a date before the calendar's first covered date or after its last, **When** it is
   classified, **Then** the outcome is a typed refusal naming the calendar, the date and the
   covered window, and no classification is produced.
2. **Given** a request for the next working day on or after a date, **When** the search would
   have to leave the covered window to find one, **Then** it refuses naming the calendar, the
   starting date and the window — rather than returning the window's edge or looping.
3. **Given** the same refusal, **When** it is inspected, **Then** it distinguishes *before the
   window*, *after the window* and *the search ran off the window* without a reader opening a
   data file.
4. **Given** any refusal in this story, **When** the whole engine is searched, **Then** no
   configuration, flag or declared option turns it into an answer.

---

### User Story 3 — A rule written in working days becomes declarable (Priority: P3)

A legal rule written the way пункт 10 is written names four things, and this feature answers
each without supplying anything about rates. The mapping is stated once here, because "four"
otherwise names two different sets:

| The law's word | Answered by |
|---|---|
| *«робочий день»* — a working day | FR-012 |
| *«передсвятковий день»* — a pre-holiday day | FR-012, on the same answer |
| *«перший післясвятковий робочий день»* — the first working day after | FR-013 |
| *«останній робочий день тижня»* — the last working day of the week | FR-014 |

FR-013 also answers the last working day **on or before** a date, which пункт 10 does not name
but a carry-forward rule does.

**Why this priority**: demoted from P1 to P3 on 2026-08-30, when the National Bank turned out
to publish for every calendar day and 018 was released from needing a calendar. The four
questions are still the right interface — they are what the law's own vocabulary asks — but
**no declared rule in the tree asks them today**, and the honest statement of that is a low
priority rather than a deleted story. Deleting it would lose the shape a future gapped series,
or a researched `non_business_day_rule`, would need.

**Independent Test**: Against a synthetic calendar, evaluate every query of FR-012 to FR-014
across a week containing a holiday, a pre-holiday day and a moved working day, and check every answer
against a hand-written table — with no rate series, no series identity and no money anywhere in
the test.

**Acceptance Scenarios**:

1. **Given** a declared calendar and a date, **When** the last working day of that date's week
   is requested, **Then** the answer is computed from the calendar's own declared week start
   and its declared classifications, and the week start is data rather than an assumption.
2. **Given** a date classified as a holiday, **When** the first working day after it is
   requested, **Then** the answer skips every consecutive rest day and holiday and stops at the
   first working day, whether or not that day is also a pre-holiday day.
3. **Given** a working day the calendar declares pre-holiday, **When** it is classified,
   **Then** it is reported as a working day *and* as a pre-holiday day, and the two facts are
   not collapsed into one.
4. **Given** a declaration that attaches the pre-holiday fact to a date it also declares
   non-working, **When** it is loaded, **Then** loading fails naming the file and the date.

---

### User Story 4 — A second jurisdiction's calendar is a data-only addition (Priority: P2)

A calendar for another country — another rest pattern, another week start, another holiday
list, another authority — loads and is addressable with no source change, even though nothing
consumes a second one yet.

**Why this priority**: P2 because Stories 1–3 must exist before there is anything to add a
second of. The requirement is Principle II applied to the input most likely to be hard-coded
as a singleton, and it is the story that catches a Ukrainian assumption baked into the shape —
a five-day week, a Monday week start, a Saturday–Sunday weekend.

**Independent Test**: Declare a second calendar with a different rest pattern and a different
week start, purely as data, and confirm it loads, is addressable, classifies dates by *its*
pattern, and that the first is unaffected — with zero source lines changed.

**Acceptance Scenarios**:

1. **Given** a second calendar with a distinct identity declared purely as data, **When** it is
   loaded, **Then** loading succeeds and it is addressable, with zero source lines changed.
2. **Given** two calendars with different rest patterns, **When** the same date is classified
   against each, **Then** the answers may differ and each names the calendar that produced it.
3. **Given** two calendars declared with the same identity, **When** they are loaded, **Then**
   loading fails naming both files.
4. **Given** a consumer that needs a `civil` calendar and a calendar declared with a
   `settlement` scope, **When** the consumer asks, **Then** it refuses naming the scope wanted
   and the scope found, rather than answering from the wrong kind of calendar.

---

### User Story 5 — Nothing in the engine holds a date the law set (Priority: P2)

No holiday, no weekend and no moved working day is written in source. The two places that
decide a working day without a declared calendar today are known, counted, and named in a
recorded deferral rather than left to be discovered.

**Why this priority**: P2 because it constrains the implementation rather than delivering a
capability, and non-negotiable in substance: it is Principle I's "no legal value from memory"
applied to the one input this feature could most easily smuggle into code.

**Independent Test**: Scan the source tree for calendar-date literals and for weekday
literals, and assert the count and the identity of the sites that still decide a working day
without a calendar.

**Acceptance Scenarios**:

1. **Given** the source tree, **When** it is scanned, **Then** no module outside test fixtures
   contains a month-and-day literal that is a public holiday, and no new site decides whether a
   day is a working day from a weekday number.
2. **Given** the source tree, **When** the pre-existing weekend sites are enumerated, **Then**
   exactly the known sites appear, and a new one fails the scan rather than being reviewed for.
3. **Given** `conventions.is_business_day`'s docstring, **When** this feature lands, **Then**
   its promise that "one function changes and every settlement date changes with it" no longer
   stands unqualified, because a declared calendar now exists and that function did not change.

---

### Edge Cases

- **A date past the calendar's last covered date** — a refusal naming the calendar, the date
  and the window. Never the last year's pattern extended forward. This is the one that matters
  most, because it is the one that arrives by simply waiting.
- **A search for the next working day that runs off the window** — FR-011's *out of coverage*
  reason carrying the *ran off an end* discriminator, not a fourth reason: the *asked-about*
  date was inside the window and the *answer* is not, and telling the reader to extend the
  calendar is a different sentence from telling them the date was never covered.
- **A holiday that falls on a weekly rest day** — declared, not derived. Whether the law moves
  the following working day is a legal reading nobody in this repository has, and deriving it
  would be inventing one. The declaration says what the law said; if a day was moved, the move
  is its own declared row with its own citation.
- **A pre-holiday day attached to a non-working date** — a load failure naming the file and the
  date. A shortened working day that is not a working day is two declared facts that cannot
  both hold, which is what every other declaration in this repository calls an inconsistency.
- **A calendar whose holiday enumeration for a year is empty** — loads, and means it. A year in
  which a jurisdiction's holiday regime was suspended is expressible as an empty enumeration
  with the suspending act as its citation, and it must not look like a year somebody forgot to
  transcribe: the year is inside the declared window either way, so the distinction is carried
  by the window rather than by the absence.
- **A calendar with no coverage window** — a load failure. An unbounded calendar is one that
  never refuses, and a calendar that never refuses is a calendar somebody will read past the
  end of.
- **Two rows classifying the same date** — a load-time collision naming the file and the date.
  One date, one classification; whichever the lookup reached first would otherwise decide a
  legal question by file order, which is the reasoning `loader._non_publication_rule` already
  applies to a duplicated `applies_to`.
- **A declared rest pattern naming every day of the week** — a load failure. A calendar with no
  working days answers every working-day question with a refusal that names the date rather
  than the declaration, sending the reader to fix the wrong thing.
- **A date inside the window that no row mentions** — classified by the declared rest pattern,
  and the answer says so. This is the ordinary case and it is listed because it is where an
  enumerated form could otherwise be read as requiring a row per day.
- **An observed publication day used as a calendar** — not representable. There is no scope for
  it, which is the point.
- **A consumer holding no calendar at all** — refuses naming what it wanted. The absence of a
  calendar is not permission to assume a weekend, exactly as 011 FR-011 holds that the absence
  of a rule is not permission to choose one.

## Requirements *(mandatory)*

### The calendar as declared data

- **FR-001**: A working-day calendar MUST enter the system as a declared data file. It MUST
  declare its own identity, the jurisdiction it speaks for, the authority whose acts it
  transcribes, its **scope**, its **coverage window** as an explicit first and last date, its
  **weekly rest pattern**, and its **week start**. Adding a calendar MUST require no
  source-code change.
- **FR-002**: The weekly rest pattern and the week start MUST be declared explicitly and MUST
  NOT default. A Saturday-and-Sunday weekend and a Monday week start are the two facts this
  feature is most likely to inherit from the implementer rather than from a source, and the
  engine already asserts the first uncited at `core/primitives/conventions.py:51`. A default
  here would make a second jurisdiction's calendar silently Ukrainian.
- **FR-003**: Scope MUST be a declared closed set with exactly two members — a jurisdiction's
  **civil** calendar and a named operator's **settlement** calendar — and it MUST be a
  precondition rather than a branch: a consumer names the scope its question requires, a
  mismatch refuses (FR-011), and **no computation MUST differ by scope**. Exactly one calendar
  MUST be **shipped in `data/`**, and its scope MUST be `civil`; test fixtures declaring further
  calendars — a second jurisdiction (SC-006), a `settlement`-scoped one (SC-007) — are required
  by those criteria and are not shipped data.
- **FR-003a**: A consumer MUST reach a calendar by **naming its declared id**, and the engine
  MUST NOT select one from a jurisdiction, a scope, or load order. Two calendars declared for
  one jurisdiction MUST NOT be a load error. 011 settled the identical question for rate
  series and the precedent is exact: `data/tax/timing/ua.toml:35` declares
  `official_rate_series = "ua_nbu_usd"` by name, and 011 SC-011 requires that the series used
  be "named in its output rather than being whichever loaded first". A jurisdiction may
  legitimately have a civil calendar and, later, a settlement calendar for a venue inside it;
  picking between them by jurisdiction would decide a legal question by directory contents.
- **FR-003b**: The scope check MUST live **with the asking**, not with the calendar: the
  question a consumer asks MUST carry the scope it requires, and the refusal MUST be produced
  where the question is answered (FR-011, FR-012 to FR-014). A calendar MUST NOT be validated
  against a scope at load, because at load there is no question to check it against. This is
  what lets FR-015 hold — the feature ships no consumer, yet the check is reachable and
  asserted (SC-007) because a test asks the question a consumer would.
- **FR-004**: A calendar MUST NOT be declared from observed publication days. There MUST be no
  scope for it and no field that admits one. The dates a publisher published for are already
  declared, as `OfficialRateSeries.observations`; a calendar built from them would answer "was
  this a working day?" from what a publisher did, which is the one inference 011's edge cases
  say the engine cannot make and must not try.
- **FR-005**: Every declared classification row MUST carry its own source, retrieval date and
  verification date, and MUST name a declared observation kind. Provenance MUST be **per row**,
  never per calendar. The rows of one calendar do not share a provenance: a holiday list comes
  from a labour statute, a moved working day from an individual executive act of that year, and
  a suspension from a third law. A single citation on the file would attach one of those three
  to all of them, which is the mis-attribution `test_no_legal_value_from_memory.py` records as
  its own first uncovered hole.
- **FR-006**: The provenance gate MUST require **both a citation and a declared observation
  kind** on every classification row.
  **Neither followed from listing the directory in `SOURCED_DIRS`, and the gap was measured
  rather than supposed**: `_has_observed_value` decided that a table "carries observed values"
  by counting **numeric leaves** not in `STRUCTURAL_KEYS`, and `check_table` gated **both**
  `_check_kind_field` **and** the citation loop behind that one predicate. A classification row
  is a date and a label and holds no number at all, so a calendar directory would have been
  scanned and every row would have passed **uncited and with an unvalidated kind**. An uncited
  holiday is precisely the legal value from memory Principle I forbids, and this is the one gate
  that would otherwise be believed to catch it. **SATISFIED ON `main` BY `e6def2f`**: the
  predicate now counts dates in either TOML spelling, and a planted row of dates and labels
  fails the gate with its `source` removed and fails it again on an undeclared `kind`
  (`tests/contract/test_provenance_gate.py`). The same script still refuses an unlisted
  directory outright (`unknown_directories`), so the directory MUST be listed by name with its
  reason.
- **FR-006a**: Because the predicate FR-006 changes is shared by **every** entry in
  `SOURCED_DIRS`, the fix MUST be measured as a **delta over the gate's full finding set**: the
  complete set of findings is recorded before the change and after it, and the difference MUST
  be exactly the calendar rows. **A widening would be caught by CI and a narrowing would not** —
  and a narrowing in the gate whose job is preventing blind spots is the worst available
  outcome. Asserting only that deleting a calendar row's `source` now fails (SC-005) does not
  see a narrowing at all. This is the mechanical form the `quotation_unit` precedent used:
  that gap was established by deleting the exemption line and **counting** the four errors it
  produced, rather than by reasoning about what the gate ought to do.
  **SATISFIED ON `main` BY `e6def2f`, and the delta was empty.** No calendar directory existed
  yet, so the change is a guard rather than a repair. Measured 2026-08-30, the survey FR-006b asks
  for found the widened predicate reaching **29** tables the old one did not: every
  `[[verification_task]]`, whose `searched_on` dates a search rather than an observation, and
  three fund identity tables. All three key names are exempted with their reasons, leaving the
  finding set over the shipped tree byte-identical. The fund
  one is a **recorded hole rather than a judgement**: `terminates_on` and `subscription_cutoff`
  are `fund_terms` observations that `[instrument]` has nowhere to cite, since `FundTable` is
  `extra="forbid"`.
- **FR-006b**: FR-006 and FR-006a described a **live defect on `main` that had nothing to do
  with calendars**, and were fixed ahead of this feature rather than inside it — including a
  survey of what else under `data/` is numberless and therefore already exempt without saying
  so. This feature states them because they are its preconditions, and inherits the fix.
- **FR-007**: Loading a calendar MUST fail loudly — naming the file and the offending field or
  date — on a malformed value, an unrecognised field, a missing required field, a missing
  coverage window, a missing or empty rest pattern, a rest pattern naming every weekday, a
  missing week start, a duplicated calendar identity, two rows classifying the same date, a row
  dated outside the coverage window, a pre-holiday fact attached to a non-working date, or an
  undeclared observation kind. No default MUST be substituted for anything absent.

### The enumerated form, and the refusal that answers its one weakness

- **FR-008**: A calendar MUST be declared as an **enumerated set of exceptions over a declared
  recurring rest pattern**, within a declared window. It MUST NOT be declared as a generative
  rule, and the engine MUST NOT contain a rule that derives a holiday date from anything — not
  a fixed date, not an Easter computation, not an observance rule that moves a holiday off a
  rest day. Applying a *declared* rest pattern is not a derivation of a legal fact: the
  pattern is data with a citation and the engine applies it the way it applies a declared
  periodicity. Computing which Sunday Easter falls on is a legal-and-ecclesiastical fact
  rendered as code, which Principle I forbids and `data/README.md` rule 4 restates.
- **FR-009**: This feature MUST NOT introduce a second declaration form, and MUST NOT be
  planned as 013's two-form design. 013 supports both forms because both are arithmetic over
  declared terms and neither requires the engine to hold a legal fact; that is not true here
  (see "Enumerated, not generative"). A single form makes 013's no-branching scan vacuous, so
  the mechanical check this feature owes is a different one — FR-018's scan for legal dates in
  source — and stating that swap here is what stops a planner reaching for the wrong precedent.
- **FR-010**: A date outside the declared coverage window MUST produce a typed refusal naming
  the calendar, the date and the window. The system MUST NOT extend the rest pattern past
  either end, repeat the last declared year, or infer a classification from an adjacent year.
  This is the requirement that answers the enumerated form's only real weakness. An
  enumerated calendar goes stale at its last declared year; what this turns that from a silent
  staleness into a loud one is that the window is declared and the refusal names it. A
  calendar without this requirement would be worse than the refusal it replaces.
- **FR-011**: The refusal MUST be **exactly three typed reasons**, because there are three
  different remedies and one reason would send a reader to the wrong one. Each MUST carry only
  what is knowable in its own case:
  1. **No calendar with this id** — the consumer named one that is not declared. Carries the id
     wanted. No window, because no calendar was found to have one.
  2. **Wrong scope** — the named calendar exists and asserts something else. Carries the id,
     the scope wanted and the scope found.
  3. **Out of coverage** — the named calendar exists, has the right scope, and does not reach
     the date. Carries the id, the date, the declared window, and **which way it missed**:
     before the window, after it, or *a working-day search that started inside the window ran
     off an end* (FR-013, FR-014).

  **Recorded and not built: the refusal does not carry which end to widen.** A consumer holding
  only a *ran off an end* refusal cannot render the remedy — the end follows from the question
  asked, and the record does not carry the question. Threading the crossed bound into the
  refusal's reason is the cheap honest form (`_search` knows which bound it fell off, and the
  week query knows which end its week crosses), and it is **not** a fourth reason: which end to
  widen is a detail of the third, not a fourth remedy. Deferred because nothing consumes a
  calendar (FR-015), so no output is degraded today and there is no consumer to design against.
  Recorded 2026-08-31 in review.

  **There is deliberately no "no calendar is declared for this jurisdiction" reason**, because
  FR-003a forbids the engine from asking that question: nothing looks a calendar up by
  jurisdiction, so nothing can discover that a jurisdiction has none. Shipping that reason
  would be a guard whose message is false. The three-way shape follows 011's split of
  `OfficialRateSeriesUnavailable` from `OfficialRateUndeclaredOnDate`, with its first member
  divided because *misspelt an id* and *asked the wrong kind of calendar* have different fixes.

### What a consumer may ask

- **FR-012**: Given a calendar and a date, the system MUST answer whether that date is a
  **working day**, and MUST state which declared fact decided it — the rest pattern, an
  enumerated non-working day, or a declared move. The answer MUST make a wrong state
  unrepresentable: the pre-holiday fact MUST be attachable only to a date the same answer
  reports as working.
- **FR-013**: Given a calendar and a date, the system MUST answer the **first working day on or
  after** it and the **last working day on or before** it, skipping every consecutive
  non-working day. A search that would leave the coverage window MUST refuse under FR-010 with
  the *ran off an end* discriminator of FR-011's third reason, rather than return the window's
  edge or loop. The discriminator is required rather than optional: *the date you asked about
  was never covered* and *the date you asked about was covered but the answer is not* have
  different remedies, and which **end** to extend follows from the question rather than from
  the reason alone — earlier for a date before the window and for a backwards search that ran
  off, later for a date after it and a forwards search, and for a week straddling the boundary
  whichever end the week crosses.
- **FR-014**: Given a calendar and a date, the system MUST answer the **last working day of the
  week containing that date**, computed from the calendar's own declared week start. Included
  because пункт 10 is written in it — *«останній робочий день тижня»* — and omitting it would
  force whichever rule needs it to define where a week begins, which is a convention nobody
  declared: the same failure this feature exists to fix, one level up.

  **A week that straddles the coverage boundary MUST refuse** under FR-011's *out of coverage*
  reason with the ran-off-an-end discriminator, even when a working day exists inside the
  window. Answering from the visible part would return "the last working day of the week" from
  a week the calendar cannot see the end of — a plausible date that is not the answer to the
  question asked, which is the whole class of failure FR-010 exists to refuse.
- **FR-015**: FR-012 to FR-014 MUST be everything this feature exposes, and it MUST ship with
  **no consumer**. It MUST NOT extend 011's `NonPublicationRule` to a calendar-evaluated form,
  MUST NOT declare an official-rate observation, MUST NOT change any tax base, and MUST NOT
  touch settlement or due-date arithmetic (FR-017). Owner decision 2026-08-30: 018 was released
  from needing a calendar, and the carry-forward rule the owner declared in its place needs
  none while the series covers every day. Wiring a consumer here would build against a need
  nobody has, and would put a rule and the calendar it is evaluated against in one diff where
  neither is reviewable against its own tests.

### Purity, and the notion of a working day that already exists

- **FR-016**: Every date MUST be an argument. The calendar MUST be an explicit argument to
  every question asked of it, and no module MUST hold one implicitly, read a clock, or consult
  a run's `as_of` to decide a classification. Principle III, and the concrete failure it
  prevents here: a calendar reached from module state would make "which calendar answered this"
  unrecoverable from the result, and every classification in this feature is an input to a
  legal figure downstream.
- **FR-017**: This feature MUST NOT silently leave two notions of a working day in the tree.
  The pre-existing uncited notion is `conventions._is_weekend` (`conventions.py:196`) reached
  through `conventions.is_business_day` (`:208`) and through the declared-convention registry
  `conventions.business_day_rule` (`:292`), and it has **three** consumers, listed here as the
  canonical set FR-018's scan pins:

  1. `core/instruments/fixed_income.py:138`, `:521`, `:794` — coupon dates and maturity date;
  2. `core/instruments/fund.py:438` — fund redemption settlement date;
  3. `core/tax/year.py:1821` — tax payment deadline.

  All three MUST either be rewired onto declared calendars or be recorded as a named deferral
  with its cost stated **and** have the prose that becomes false corrected in this change.

  **Decided by the owner on 2026-08-30: record and defer.** None of the three is rewired here.
  The argument is per consumer and is in "Why it is nevertheless not blocking": the fund needs a
  *settlement* calendar nobody has retrieved, the due date needs a legal reading nobody has
  done, and the bond needs an answer to *which kind of calendar moves a coupon date* that only
  an issue's own terms can give.

- **FR-017a**: **Three sentences go false when a declared calendar exists, and all three MUST be
  corrected in this change** — not the most quotable one. Each is a promise made in the present
  tense about a state of the world this feature changes:
  - `conventions.py:199-203` — "*Until that data exists* a coupon falling on a public holiday is
    placed on the holiday". The data now exists and the coupon is still placed on the holiday.
  - `fund.py:441-444` — "*until that data exists* a settlement landing on a holiday is placed on
    the holiday". Same shape, same falsity.
  - `conventions.py:211-214` — "the day public holidays arrive as declared data, one function
    changes and every settlement date changes with it". This feature is that day and that
    function did not change.

  The first two are the ones that actually become false, because each is conditioned on the
  absence of exactly the data this feature adds; the third is a prediction that did not come
  true. Correcting only the third — which an earlier draft of this requirement did — leaves the
  two load-bearing ones standing. Each correction MUST say what is true instead: a calendar is
  declarable and these sites do not consult one, by CL-1, with its date.
- **FR-018**: A **scan** MUST assert that no module in `src/` outside the calendar's own
  declaration surface contains a month-and-day literal standing for a public holiday, and that
  the set of sites deciding whether a day is a working day without a declared calendar is
  exactly the set FR-017 names. A new such site MUST fail the scan rather than be caught by
  review. Mechanical form over prose, per the constitution: the enumeration of those sites is
  a claim about elsewhere, so it is a check or it is not written. The precedent for pinning a
  count this way is `tests/contract/test_no_legal_value_from_memory.py`, and the precedent for
  recording what a scan does *not* catch is that file's own four measured holes — this scan's
  limits MUST be stated the same way, and a holiday spelled as a computed date will pass it.

  **The set is FR-017's three, and reaching `_is_weekend` through
  `conventions.business_day_rule` counts.** A scan scoped to direct callers of
  `is_business_day` would pass green while asserting something false about the tree, because
  `year.py::_due_on` is already counted and reaches it by that same indirect path. A scan that
  cannot see `fixed_income.py` is worse than no scan: it converts an unexamined site into a
  documented absence.
- **FR-018a**: FR-018's scan is landed **first within this feature** rather than ahead of it on
  `main`, because the feature was scheduled after all. Its entire value is that a fourth site
  cannot appear quietly, so it went in before the calendar existed —
  `tests/contract/test_no_calendar_free_working_day.py`, phase 0 — and the calendar's own
  declaration surface is excluded by path, exactly as this requirement's wording anticipates.

A second stale claim found in that same neighbourhood — `_due_on`'s docstring naming "the same
four names" where `conventions.BUSINESS_DAY_FNS` declares three — was confirmed and is **fixed
on `main` at `021a587`**, which this branch has merged. It carries no requirement here, and no
line reference either: the line it was on no longer says it.

### Martial law

- **FR-019**: This feature MUST NOT add one more place the end of martial law lives, and MUST
  NOT resolve the three that exist. The calendar MUST express a suspended holiday regime by
  **enumeration within a declared window** — the years whose law somebody read, transcribed as
  they were — and MUST NOT carry a condition, a switch or an effective-until keyed to martial
  law ending. `specs/features.toml`'s `martial-law-ends-one-belief-two-places` was opened recording two
  levy facts hanging off one unstated belief: the ФОП group-3 levy's termination and the
  personal-income levy's reversion, with the same event already declared as a route-regime
  transition in `data/scenarios/war_end.toml`. A holiday regime altered by martial law is a
  third belief of the same shape, and this requirement is what keeps it from becoming one more
  *mechanism*: an enumerated calendar that stops and refuses conditions on nothing. The entry
  MUST be updated to say the calendar is a third instance and that this feature deliberately
  did not deepen it.
- **FR-020**: Whether the National Bank's вихідні, святкові and передсвяткові days track the
  Labour Code's holiday regime — including its martial-law suspension — MUST NOT be assumed in
  either direction. It is owner verification task 2. Until it closes, the shipped Ukrainian
  calendar's coverage window MUST cover only years the owner has verified, and any rule
  evaluated against it refuses outside that window under FR-010.

### Documentation

- **FR-021**: `docs/METHODOLOGY.md` MUST gain the classification rule — what a working day, a
  rest day, a public holiday and a pre-holiday day mean here, how the declared pattern and the
  enumerated exceptions combine, and what happens past the window — in the same change that
  implements it. `docs/REQUIRED_TESTS.md` MUST be updated for any row this feature's tests
  close.

### Key Entities

- **Working-day calendar** — a declared, identified, scoped statement about which dates a
  jurisdiction's law calls working: its identity, its jurisdiction, its authority, its scope,
  its coverage window, its weekly rest pattern, its week start, and its enumerated exceptions.
  Shaped so a second calendar is a data-only addition.
- **Calendar scope** — a closed set of two: a jurisdiction's `civil` calendar and a named
  operator's `settlement` calendar. A precondition on a question, never a branch in a
  computation. There is deliberately no third member for observed publication days (FR-004).
- **Coverage window** — the first and last date the calendar speaks for. Two-ended, unlike
  013's one-ended schedule coverage, because a calendar knows both ends and it is the end that
  arrives by waiting. Declared, never inferred from the rows.
- **Weekly rest pattern** — which weekdays the jurisdiction's law makes rest days, declared and
  cited. What `conventions._is_weekend` asserts today without a citation.
- **Classification row** — one date whose classification departs from the rest pattern: a
  public holiday, a pre-holiday day, or a working or rest day an executive act moved, with its
  own source, retrieval date, verification date and observation kind. One row per date.
- **Day classification** — the answer: whether the date is a working day, which declared fact
  decided it, and — only where it is a working day — whether it is a pre-holiday day. A
  pre-holiday non-working day is unrepresentable rather than refused at the query.
- **Calendar-unavailable reason** — the typed refusal, in **three** members because there are
  three remedies (FR-011): *no calendar with this id*, *wrong scope*, and *out of coverage* —
  the last carrying which way it missed. Not an error, not a default, and not a working day.
  There is deliberately no member for a jurisdiction having no calendar, because FR-003a means
  nothing can ask.
- Reused unchanged: the provenance record and its source references, the observation-kind
  staleness thresholds, and every record in `core/tax/official_rate.py`, which this feature
  does not touch.

## Success Criteria *(mandatory)*

- **SC-001**: A synthetic calendar with a hand-sized window classifies every date in that
  window in agreement with a hand-written table checked in beside the assertion, including at
  least one date decided by the rest pattern, one enumerated holiday, one pre-holiday working
  day and one moved working day. (FR-008, FR-012)
- **SC-002**: Across a deliberate battery of out-of-window questions — a date before the
  window, a date after it, a next-working-day search that runs off the end, and a
  last-working-day-of-week search whose week straddles the boundary — 100% produce typed
  refusals naming the calendar and the date, and zero produce a classification. No
  configuration, flag or declared option makes any of them answer. (FR-010, FR-013, FR-014)
- **SC-003**: All three refusal reasons of FR-011 are constructed and distinguished **per
  field**, asserted field-by-field rather than by matching a message: *no calendar with this id*
  carries an id and no window; *wrong scope* carries both scopes; *out of coverage* carries the
  window and a discriminator that separates before, after, and ran-off-an-end. A scan asserts
  that no reason exists for a jurisdiction having no calendar, since nothing can ask that
  (FR-003a, FR-011). (FR-011, FR-013)
- **SC-004**: Across a deliberate battery of broken calendar files — unknown field, missing
  field, missing window, missing rest pattern, a rest pattern naming every weekday, missing
  week start, duplicate identity, two rows for one date, a row outside the window, a
  pre-holiday day on a non-working date, an undeclared observation kind — every case fails
  naming the file and the offending field or date, and no case substitutes a default. (FR-007)
- **SC-005**: A classification row with an empty verification date marks every answer derived
  from it, and the mark survives into whatever a consumer builds on that answer. Removing a
  row's citation fails the provenance gate — **demonstrated by measurement, the way the
  `quotation_unit` gap was measured**: the gate is run against a calendar file with a row's
  `source` deleted and the failure count recorded, so FR-006's fix is shown to bite rather than
  assumed to. The predicate half of that fix already landed with its own planted-row tests
  (`e6def2f`); what SC-005 adds is the same demonstration on a real calendar file. (FR-005,
  FR-006)
- **SC-006**: A second calendar with a different rest pattern and a different week start,
  declared purely as data, loads and classifies dates by *its* pattern with zero source lines
  changed, and the first calendar's answers are unchanged. (FR-001, Story 4)
- **SC-007**: A consumer that requires a `civil` calendar, handed one declared `settlement`,
  refuses naming both scopes and produces no classification. (FR-003, FR-011)
- **SC-008**: Every query of FR-012 to FR-014, and each row of User Story 3's mapping table,
  answers a week containing a holiday, a
  pre-holiday day and a moved working day in agreement with a hand-written table — the
  evaluation a rule written in the law's own vocabulary would perform, exercised here with no
  rate series, no series identity and no money in the test. (FR-012, FR-013, FR-014)
- **SC-009**: A scan finds zero month-and-day literals standing for public holidays in `src/`,
  and reports the set of sites deciding a working day without a calendar as exactly the **three**
  FR-017 names — including the two reached through the declared-convention registry rather than
  by a direct call, so a scan narrowed to direct callers fails this criterion instead of passing
  it. A fourth site fails the scan rather than being caught by review. The scan's own limits are
  recorded in its docstring, measured rather than supposed. (FR-018)
- **SC-010**: No golden result file moves, and no tax base, charge, cost, route or ranking
  figure changes anywhere in the engine, as a consequence of this feature landing. Stated as
  a criterion rather than an assumption because it is the check that this feature stayed on its
  own side of the no-consumer line FR-015 draws: a moved golden would mean a rate, a settlement
  or a deadline started consulting the calendar here. (FR-015)
- **SC-011**: Whatever answers FR-012 to FR-014 imports nothing forbidden to the pure core,
  holds no clock, and takes every date and every calendar as an argument — asserted by the
  existing architecture contracts plus one assertion that no calendar is reachable except
  through an argument. (FR-016)
- **SC-012**: `docs/METHODOLOGY.md` gains the classification rule and the out-of-window
  behaviour in the same change that implements them, verified by that change's own diff rather
  than by a follow-up. (FR-021)
- **SC-013**: `specs/features.toml`'s `martial-law-ends-one-belief-two-places` entry names the
  calendar as a third instance of the same belief, and no calendar declaration, field or record
  introduced here is keyed to martial law ending. (FR-019)

## Assumptions

- **No real holiday dates enter with this spec.** Acceptance examples run against
  clearly-labelled synthetic calendars whose dates are stated in the test itself, exactly as
  011 did with its synthetic observations. The examples test the classification logic, not
  Ukrainian law. The real Ukrainian calendar arrives as a data file carrying its own provenance
  from the published texts, and nothing is invented to make an example work.
- **The shipped Ukrainian calendar's window is whatever the owner verifies.** Following 011
  FR-017's pattern of a declared absence with a visible consequence: a narrow window that
  refuses is honest, and a wide window transcribed from memory is the defect. A calendar with
  an empty window is a load failure, so the smallest honest shipped state is one verified year.
- **One consuming jurisdiction.** UA is the only jurisdiction whose calendar is declared here.
  The second calendar of Story 4 is declarable and addressable, not consumed.
- **The calendar answers questions; it does not schedule anything.** It says what a date *is*.
  It does not move a coupon (`fixed_income.py`), a settlement (`fund.py`) or a deadline
  (`year.py`) — those three are the consumers FR-017 names, and by CL-1 none of them comes to
  consult a calendar in this feature.
- **Calendar data is hand-transcribed, not fetched, and that is a difference from CPI and
  rates.** `scripts/fetch_cpi.py` and `scripts/fetch_inzhur.py` established the retrieve-and-
  write-an-empty-`verified_on` pattern for series a publisher exposes machine-readably. A
  holiday list is not that: it is a statute's text plus one executive act per year, read and
  transcribed by a person. So there is no fetch script to build and none is deferred — the
  provenance obligation falls entirely on FR-005's per-row citation and on the owner's reading.
  Stated because the absence of a `[[future]]` fetch entry here would otherwise read as an
  oversight beside 011's, which has one.
- **No delivery surface.** Results are produced and asserted by the test suite; there is no UI
  and no CLI in this feature.

## Terminology

Two words for one idea already exist across the boundary this feature sits on, and they are
kept apart deliberately rather than unified.

- **Working day** — this specification's term, and the calendar's. It means what a
  jurisdiction's law means: a day that is not a weekly rest day and not a public holiday,
  including a day an executive act moved into that status. It is the word пункт 10 is written
  in (*«робочий день»*), and every requirement here uses it.
- **Business day** — the existing code's term for the weekends-only notion in
  `core/primitives/conventions.py` (`is_business_day`, `business_day_rule`,
  `BUSINESS_DAY_FNS`) and its consumers' declared fields (`settlement_business_days` in
  `data/instruments/inzhur_reit.toml:102`). It means *not Saturday and not Sunday*, and it
  knows nothing about holidays.

**They are not synonyms here and MUST NOT be made to look like it.** The two notions coexist
by decision (FR-017, owner 2026-08-30), and one word covering both would hide exactly the thing
FR-018's scan exists to count. If a later change ever rewires the business-day sites onto
declared calendars, the words converge and one of them is retired in that change — not before.

## Clarifications

### Session 2026-08-30

Four questions were raised while writing this specification. Three were settled from the
repository's own precedents; the fourth went to the owner and came back on 2026-08-30, together
with a decision nobody had asked for that removed this feature from the critical path.

| # | Question | Resolution | Where it landed |
|---|---|---|---|
| 1 | Is a calendar enumerated, generative, or both — following 013's two-form precedent? | **Enumerated only.** A generative form would put a legal-and-ecclesiastical fact in the engine (Principle I), would still be incomplete against an annual executive act moving working days, and — the argument that decides it — would express the martial-law holiday suspension as a rule conditioned on the war ending, adding **another mechanism keyed to a belief the system already holds in more than one place and does not know it holds twice**. An enumerated calendar with a declared window conditions on nothing: it stops and refuses. | FR-008, FR-009, FR-010, FR-019; "Enumerated, not generative" |
| 2 | Whose calendar is it — a jurisdiction's law, a settlement system's, or a publisher's observed days? | **A jurisdiction's civil calendar**, with a declared scope reserving `settlement` for a named operator and **no member at all** for observed publication days. The third is already declared as `OfficialRateSeries.observations`, and admitting it would let a consumer answer "was this a working day?" from what a publisher happened to do — the one inference 011's edge cases forbid. | FR-003, FR-004; "Which of these three things a calendar asserts" |
| 3 | How does a consumer reach a calendar — by naming it, or by jurisdiction and scope? | **By naming its declared id.** Settled by 011's exact precedent: `data/tax/timing/ua.toml:35` names its rate series, and 011 SC-011 forbids "whichever loaded first". | FR-003a |
| 4 | Are the pre-existing uncited weekend sites rewired here, or recorded and deferred? | **Record and defer** — owner, 2026-08-30, taking this specification's own recommendation. `_is_weekend` and its **three** consumers stay. The question was answered while this spec counted two of them; review found the third and it does not change the answer, because that one needs a decision about *which kind* of calendar moves a coupon date before it needs a calendar. | FR-017, FR-017a, FR-018 |
| 5 | *(not asked — decided alongside)* Does 018 need this feature? | **No.** The National Bank publishes for every calendar day, so a rate series needs no working-day rule to be complete, and the owner's declared carry-forward rule for a hypothetical gap needs no calendar to evaluate. 018's dependency on 017 is removed; this feature blocks nothing. | Status; "Why it is nevertheless not blocking" |

## The decision that was the owner's

One question could not be settled from the repository, because the repository argued both
ways. It went up and came back on 2026-08-30.

### CL-1 — Are the pre-existing weekend sites rewired here, or recorded and deferred?

**Answer: recorded and deferred**, which was this specification's own recommendation.

**Context**: `conventions._is_weekend` (`core/primitives/conventions.py:196`) is an uncited
Saturday-and-Sunday rule with the **three** consumers FR-017 lists. The question was put to the
owner while this specification counted only two of them; the third — `fixed_income.py`, moving
coupon and maturity dates — was found in review afterwards. **It does not change the answer**,
and the reason it does not is worth stating: the third consumer is the one *least* served by
rewiring, because what it needs first is a decision about *which kind* of calendar moves a
coupon date, and that decision is not this feature's to take.

**What decided it**: not correctness — both answers are defensible — but that rewiring would
be premature at every one of the three sites, each for its own reason.

| Site | Why not rewired |
|---|---|
| `fixed_income.py:138`, `:521`, `:794` | Needs an answer to *civil or settlement?* for a coupon date, which only an issue's own terms give. Wiring it to whichever calendar exists would pick one by availability. |
| `fund.py:438` | Needs an **operator's** calendar — Inzhur's dealing days, unretrieved. Wiring it to a `civil` calendar is exactly what FR-003's scope field exists to prevent. |
| `year.py:1821` | Would move no figure: `data/tax/timing/ua.toml` declares `non_business_day_rule = "none"` on all three categories (lines 57, 73, 89) because the legal rule was never researched. |

**What the deferral costs, stated rather than glossed**: two notions of a working day coexist
in the tree, and one of them silently misplaces a coupon that falls on a public holiday. That
is made loud in three places rather than left to be discovered — the three sentences that go
false are corrected in this change (FR-017a), the divergence is recorded with its date, and
FR-018's scan pins the three-site set so a fourth cannot appear quietly.

## Owner verification tasks

No legal value has been filled in from memory, and none of the three tasks below is urgent:
nothing consumes the calendar (FR-015). Task 1's **retrieval** closed on 2026-08-31 and its
*verification* half stays open; task 2 stays open by design; task 3 is new and is the one place
this feature could have inherited a value from an implementer.

**On FR-020's window.** The shipped window covers what somebody read the law for rather than
what the owner has checked, because a calendar with an empty window is a load failure and no
`verified_on` under `data/` is filled anywhere in this repository. Every citation on the file
is empty-verified, so every classification it produces renders marked, and a date past
2026-10-30 refuses by name (FR-010).

1. **The holiday enumeration itself, and the acts that move working days.** The provision that
   sets Ukraine's святкові і неробочі дні is **стаття 73 Кодексу законів про працю України**
   (`https://zakon.rada.gov.ua/laws/show/322-08`), with **стаття 53** setting the shortened
   pre-holiday day and **стаття 67** the weekly rest days; пункт 11 розділу III of the НБУ
   Положення that 011 cites records the Cabinet's power to move working days, which is
   exercised by an individual act each year and must be cited per year, per row.

   **RETRIEVED 2026-08-31, and this half of the task is closed.** The 2026-08-30 failure had
   one cause and it was the request rather than the document: retrieval needs **both** a
   browser `User-Agent` **and** `/print`. With both, `curl --compressed` returns the whole
   consolidated Code — 141 KB, all three articles present. Without a `User-Agent` every path
   returns HTTP 403; with one, the bare URL and `/card` return **HTTP 200 on an incomplete
   document**, which is the more convincing false negative and is what the earlier attempt hit.
   The `WebFetch` tool still truncates the Code mid-стаття 40 and is not a route to it.

   **What the three articles say, and what the implementation therefore declares.** Стаття 73
   (святкові і неробочі дні) and стаття 53 (the shortened передсвятковий день) each carry the
   marker *«У період дії воєнного стану не застосовуються норми статті … згідно із Законом
   № 2136-IX від 15.03.2022 з урахуванням змін, внесених Законом № 2352-IX від 01.07.2022»*, as
   does частина третя статті 67. Частина друга статті 67 is **not** suspended and reads
   *«Загальним вихідним днем є неділя»*, leaving the second rest day of a five-day week to the
   enterprise's own schedule. So inside a martial-law window the Code enumerates **no** holidays
   and **no** pre-holiday days, and makes exactly one weekday a rest day — which is what
   `data/calendars/ua_civil.toml` declares, with the enumeration empty and the suspending act
   cited on the coverage window.

   **The Cabinet's power to move working days is not in статті 67 any more.** Частини п'ята і
   шоста статті 67 were **excluded** by Закон № 3494-IX від 22.11.2023, and what remains puts
   перенесення вихідних та робочих днів in a трудовий/колективний договір or an employer's
   order. Пункт 11 розділу III of the НБУ Положення that 011 cites is a different instrument and
   is unread here; the enumerated form is what makes either answer declarable without the engine
   holding a rule.

   **What is still open on this task**: the owner's own verification. Every citation in the
   shipped file carries an empty `verified_on`, so every classification it produces renders
   marked. Extending the window past 2026-10-30 is a retrieval of the next martial-law Указ
   rather than a judgement, and the window refuses until somebody performs it.

2. **Whether the National Bank's holiday vocabulary tracks the Labour Code's suspension.** This
   is the load-bearing one, and it is the martial-law trap in its concrete form.

   Retrieved 2026-08-30 from `https://zakon.rada.gov.ua/laws/show/2136-20/print` — Закон
   України «Про організацію трудових відносин в умовах воєнного стану» № 2136-IX, **частина
   шоста статті 6**:

   > У період дії воєнного стану не застосовуються норми статті 53, частини першої статті 65,
   > частин третьої - п'ятої статті 67, статей 71, 73, 78-1 Кодексу законів про працю України…

   marked *{Частина шоста статті 6 в редакції Закону № 2352-IX від 01.07.2022}*. Стаття 73 is
   the holiday list and стаття 53 the pre-holiday shortened day: **both are among the articles
   suspended**, which is precisely the vocabulary 011 FR-018 quotes пункт 10 as being written
   in — *«передсвятковий день»*, *«вихідні або святкові дні»*.

   **What this does not settle, and must not be assumed either way.** That the *Labour Code's*
   holiday regime is suspended does not establish that the *National Bank* stopped treating
   those dates as святкові for the purpose of пункт 10, and nothing retrieved here speaks to
   that. Both readings are live and they give opposite calendars for four years:
   - if пункт 10's terms follow КЗпП, the martial-law years enumerate **no** holidays and no
     pre-holiday days, and пункт 10's підпункти reduce to the weekend clause;
   - if the НБУ observes holidays as a matter of its own practice regardless, the enumeration is
     the ordinary one.

   **Part of it was answered on 2026-08-30, and by exactly the evidence this task predicted.**
   The National Bank published an official rate for **1 January 2026** — a public holiday —
   returning 42.3532 dated that day, and publishes for weekends too. That **falsifies** the
   reading that the NBU treats holidays as non-publication days: for publication purposes it
   does not. What it does **not** answer is what пункт 10's own «святкові дні» and
   «передсвятковий день» mean where the rule still speaks — and it may not be turned into the
   answer, because FR-004 forbids deriving a calendar from publication days. Publication data
   can falsify a reading of the law; it may never become one. The task stays open for the
   reading itself.

   **Read the consolidated text and the amendment markers under the provision you quote.** The
   lesson 011 records twice, and the reason the marker above is quoted with the provision.

3. **Is Saturday a rest day as a matter of Ukrainian law?** The one place the implementation
   could have inherited a value from an implementer rather than from a source, and it declined
   to.

   Стаття 67 ч. 2 КЗпП makes **Sunday** the general rest day and says the second rest day of a
   five-day week, *«якщо він не визначений законодавством, визначається графіком роботи
   підприємства»* — an enterprise's own schedule, which is not a fact about the jurisdiction.
   So `data/calendars/ua_civil.toml` declares `rest_days = ["sunday"]`, and
   `core/primitives/conventions.py::_is_weekend` asserts Saturday **and** Sunday with no
   citation at all. **The two disagree about every Saturday in the window.**

   **Nothing consumes the calendar (FR-015), so landing it moved no figure — but the question
   is not free of consequence, and the first draft of this task said it was.** `_is_weekend`'s
   uncited Saturday already travels into `fund.settlement_date` and into a bond's coupon dates
   through `conventions.business_day_rule`, so if the law does not rest Saturday those are
   already wrong today. They are wrong *visibly*, which is CL-1's stated cost: the bond path is
   reached only by `is_synthetic = true` fixtures the engine marks, and `year._due_on` moves
   nothing because `data/tax/timing/ua.toml` declares `non_business_day_rule = "none"` on all
   three categories. The fund path has no such cover, and it is the one that needs an
   operator's calendar rather than this one.

   What would settle the question is a provision naming Saturday, or a reading that the
   five-day week's second rest day is fixed by legislation somewhere else — neither of which is
   in the three articles retrieved. FR-002 predicted exactly this inheritance, which is why the
   transcription rather than the familiar answer is what shipped.

## Recorded, not resolved: martial law is now three places

`specs/features.toml`'s `martial-law-ends-one-belief-two-places` was opened recording two levy
facts hanging off one unstated belief — the ФОП group-3 levy's termination and the personal-income levy's
reversion — with that same event already declared as a route-regime transition in
`data/scenarios/war_end.toml`. A holiday regime altered by martial law is a **third**, and this
specification does not resolve it.

What it does instead is refuse to add one more *mechanism*. FR-019 forbids a calendar
declaration keyed to martial law ending; the calendar states what each declared year's law was
and refuses past its window. The consequence is worth stating plainly, because it is the
opposite of the usual trade: a run that assumes the war ends in 2027 for routing purposes, and
charges the levy for ever, is the defect that entry records — and a calendar declared to 2026
simply refuses to classify a date in 2028, which no belief can make wrong. The entry MUST be
updated to name the calendar as the third instance and to record that this feature declined to
deepen it.

## Required tests this feature relates to

- **H1** (data-only extensibility) is exercised by Story 4: a second calendar, declared purely
  as data, must load, be addressable and classify by its own pattern. It does not *close* H1,
  which is about an instrument, a route, a tax class and a jurisdiction reaching the comparison
  — a calendar reaches no comparison in this feature (SC-010).
- **H2** (loud failure at load) is exercised by SC-004's battery.
- **E8** (a second jurisdiction) is not closed and is not attempted, but Story 4 establishes the
  calendar's half of it before a second jurisdiction discovers otherwise — the same relationship
  011's Story 5 has to E8.
- Per the constitution, every behaviour above lands with a hand-computed worked example (the
  classification table, SC-001, SC-008), load-failure coverage (SC-004), refusal coverage
  (SC-002, SC-003) and propagation checks (SC-005). SC-009 and SC-011 are `contract` tests,
  because each is a compliance statement about a principle rather than an assertion about one
  call site.

## Out of scope

Named explicitly so the plan does not drift into them: **011's non-publication-day rule
itself**, in any form — the calendar-evaluated rule, the Ukrainian пункт 10 encoding, and any
change to `NonPublicationRule`, `OfficialRateSeries` or `strike_base`, all of which belong to
011 and 018; **any official-rate observation**, likewise; **any consumer at all** (FR-015); a settlement calendar for any venue, and
therefore any change to `instruments/fund.py::settlement_date`; the rewiring of
`conventions._is_weekend` and `tax/year.py::_due_on`, deferred by CL-1 and recorded as such; the legal reading of `non_business_day_rule` that
`data/tax/timing/ua.toml` records as unresearched; any generative or rule-based holiday form,
including Easter computation and holiday-observance shifting (FR-008); a calendar derived from
observed publication days (FR-004); a clock, an `as_of`-driven classification, or any notion of
"today" (FR-016); resolving where martial law ends, in any of its three places (FR-019); and
the web and command-line interfaces.
