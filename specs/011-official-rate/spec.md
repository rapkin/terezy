# Feature Specification: The official rate and the tax-currency role

**Feature Directory**: `specs/011-official-rate`

**Feature Branch**: `spec/011-012-rev` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-23

**Status**: Ready for planning — clarifications resolved 2026-08-23. One **owner
verification task** is open: the Ukrainian non-publication-day rule. The behaviour in its
absence is fully specified (FR-010, FR-011) and this feature ships it live (FR-017). The
rule's text was located on 2026-08-24 after the earlier attempts failed, and reading it on
2026-08-25 showed that **declaring it is not a data-only change**: пункт 10 is written in
working days and public holidays, which nothing in this system can declare. FR-018 records
that as what it is — a declared calendar, a feature-sized question — and the refusal stands
meanwhile.

**Input**: The official rate — the third currency role, which has been declared since the
first commit and has never had any machinery behind it. Official rates enter as declared,
dated, sourced observations in the same epistemic category as CPI; the tax base of a
foreign-currency event is that event's own amount at the official rate for that event's
own date; and the amount actually received is never computed from it.

---

## Why this feature exists

Constitution Principle VI names three currency roles — **base** (UAH), **tax** (UAH at the
official rate on the transaction date) and **display** (user-switchable) — and says that
conflating any two of them is a defect. Two of the three are built. The third is a
docstring.

`core/primitives/currency.py` states the rule and then says, correctly, that the enum is
"deliberately not a role". `core/tax/interface.py` says `TaxContext.taxable_base` is "the
amount the rates are applied to, **in the tax currency**", and adds the honest caveat that
"all three currency roles are UAH here, so the obligation is negative: do not collapse
them… because for a foreign security it will not" hold. Neither file is wrong. What is
missing is underneath both of them: **there is no dated official-rate series anywhere in
the repository, and no function that converts an amount at the official rate for a date.**
Every taxable amount the engine has ever computed has been hryvnia already, so the tax
role has never had to exist.

Two sites refuse to fill the gap by accident, and both are right to.
`core/routes/legs.py` (`channel_for`) says: *"There is deliberately no fallback channel.
Substituting 'the official rate' for a misspelt channel id would silently reprice a P2P leg
at the reference and delete the entire spread this feature exists to measure."*
`data/declarations/resolver.py` (`_check_channel`) repeats it at load time. Those refusals
are load-bearing and this feature does not touch them. Their consequence is simply that the
tax side has nothing at all to work with.

### The distinction this whole feature rests on

An **FX channel is a market you transact in**. It has two sides, a spread, a fee, a
counterparty, and it decides how much money you end up with. An **official rate is a legal
reference you never transact at**. It has one side, no spread and no counterparty, and it
decides nothing about how much money you end up with — it decides what number the law says
your income was.

Conflating them is the failure mode this feature exists to prevent, and it is a
*bidirectional* prohibition:

- the official rate determines a **tax base**, and never an amount received;
- a channel rate determines an amount **received**, and never a tax base.

`SIMULATOR_SPEC.md` §4.4 states the same thing as a headline finding: *"Tax on FX gains
never received: the trade uses a channel rate, the tax uses the NBU rate. This asymmetry is
a headline effect and belongs in the attribution."* Nothing in the repository can express
that sentence today, because half of it does not exist.

### What this feature does *not* claim to finish

`features.toml` records `fx-tax-asymmetry-f1`: *"flat-in-USD posts taxable UAH gain; needs
a taxable foreign instrument + dated official rates"*. That entry names two prerequisites.
This feature supplies exactly one of them. **011 makes required test F1 reachable; it does
not close it**, because F1 needs a taxable foreign-currency *position* — an instrument with
a cost basis struck at one date's official rate and proceeds struck at another's — and no
such instrument is declared here or by feature 012. The `[[future]]` entry stays open, with
one of its two blockers removed. See "Required tests this feature relates to".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A foreign-currency event has a hryvnia tax base (Priority: P1)

The owner declares official-rate observations — dated, sourced, one value per date. An
income or disposal event denominated in dollars is then taxed on a hryvnia base: the
event's own amount, converted at the official rate for the event's own date. The output
shows the rate that did the converting, the date that rate belongs to, and the series it
came from, so the base can be re-derived on paper.

**Why this priority**: This is the feature. Without it there is no tax currency, only a
docstring saying there should be one, and every future foreign-currency figure would have
to invent its own conversion at the point of use — which is how a project ends up with
three different answers to the same question.

**Independent Test**: Declare a small set of clearly-labelled synthetic official-rate
observations, tax a dollar-denominated event dated inside that window, and check the
hryvnia base against arithmetic worked out by hand on paper.

**Acceptance Scenarios**:

1. **Given** a declared official-rate series covering a date, and a taxable event on that
   date denominated in a currency other than the tax currency, **When** the charge is
   computed, **Then** the taxable base is the event's amount converted at that date's
   declared official rate, matching hand-computed arithmetic within the single project
   tolerance.
2. **Given** the same charge, **When** it is inspected, **Then** it names the series, the
   observation date whose rate was used, the rate value and the quotation unit — enough to
   re-derive the base without opening a data file.
3. **Given** a taxable event already denominated in the tax currency, **When** the charge
   is computed, **Then** no official rate is consulted, the base is the amount itself, and
   no rate-unavailable reason is attached to a figure that never needed a rate.
4. **Given** two events of the same dollar amount on two dates with different declared
   official rates, **When** both are charged, **Then** their hryvnia bases differ by
   exactly the declared rate difference times the amount — the date is load-bearing, not
   decorative.

---

### User Story 2 - The rate you are taxed at is not the rate you sold at (Priority: P1)

A dollar amount is credited on one date and converted to hryvnia on another, through a
declared channel, at a market price. Two different numbers come out of that: what the law
says the income was, and what the owner actually has. The tool reports both, labelled, and
never lets either stand in for the other.

**Why this priority**: Equal-highest with Story 1, because a tax base is only useful next
to the money it is a base *for*. This is the structural half of the asymmetry
`SIMULATOR_SPEC.md` §4.4 calls a headline effect, and it is the half that is cheap to get
wrong: one careless substitution of the official rate into a cost path, or of a channel's
reference rate into a tax path, and both numbers become the same number and the finding
disappears.

**Independent Test**: Run one dollar amount through a declared channel to hryvnia and
through the official rate to a tax base, on deliberately different dates and deliberately
different rates, and confirm the two figures are separately reported, separately labelled
and never equal by construction.

**Acceptance Scenarios**:

1. **Given** an amount credited in a foreign currency and later converted through a
   declared channel, **When** results are produced, **Then** the hryvnia **received** comes
   from the channel and the hryvnia **taxable base** comes from the official rate, both are
   reported, and neither is presented as the other.
2. **Given** a route leg whose channel is missing or misspelt, **When** costing runs,
   **Then** it refuses exactly as it does today; the official rate is never substituted,
   and this feature adds no path by which it could be.
3. **Given** a declared channel carrying a `reference_rate`, **When** a tax base is
   computed, **Then** the reference rate is not consulted: a mid-market reference used for
   costing is not a legal reference, and using one for the other would be inventing a legal
   value.
4. **Given** the display currency is switched, **When** every figure re-renders, **Then**
   no tax base, no charge and no ranking changes by a single digit.

---

### User Story 3 - A date with no declared rate refuses (Priority: P1)

The publisher does not publish a rate for every calendar day. Where no rate is declared for
an event's date, the tool says so — naming the series, the pair and the date — rather than
reaching for the nearest one.

**Why this priority**: P1 rather than P2 because the wrong behaviour here is silent and
plausible. Interpolating, carrying yesterday's rate forward, or snapping to the nearest
observation all produce a number that looks exactly like a correct number, and every tax
figure downstream inherits the invention without a mark. 007 settled the same question for
CPI (its FR-004) and this feature settles it identically for rates.

**Independent Test**: Ask for a tax base on a date inside a declared gap, before the
series' first observation, and after its last, and confirm all three produce typed
refusals naming the specific date — and that no configuration makes any of them return a
number.

**Acceptance Scenarios**:

1. **Given** a taxable event on a date the declared series does not cover, **When** the
   charge is attempted, **Then** the outcome is a typed refusal naming the series, the
   currency pair and the date, and no charge is produced.
2. **Given** the same case, **When** the refusal is inspected, **Then** no value has been
   interpolated between neighbouring observations, carried forward from an earlier date, or
   taken from the nearest observation in either direction.
3. **Given** a series that declares a non-publication-day rule with its own citation,
   **When** an event falls on a day the rule covers, **Then** the rule selects a declared
   observation from another date, the base is computed from that observation, and the
   output states which date's rate was applied to which date's event.
4. **Given** a series that declares no such rule, **When** an event falls on a
   non-publication day, **Then** scenario 1's refusal stands — the absence of a declared
   rule is not permission to pick one.

---

### User Story 4 - The mark reaches every tax figure (Priority: P2)

Every official-rate observation carries its source, its retrieval date and its verification
date. A rate that nobody has verified marks the tax base computed from it, and everything
computed from that. A rate that has aged past its declared threshold says so on every
figure it touched.

**Why this priority**: P2 only because Stories 1–3 must exist before there is anything to
mark. The requirement itself is Principle I and is not negotiable: an official rate is the
single input that turns a foreign amount into a legal one, and an unmarked tax figure
resting on an unverified rate is precisely the confidently-wrong number this project exists
to refuse.

**Independent Test**: Leave one observation unverified and confirm every derived tax figure
carries the mark; age one past its declared threshold and confirm every derived tax figure
reports the staleness; declare the rate kind with no threshold and confirm loading fails.

**Acceptance Scenarios**:

1. **Given** an official-rate observation with an empty verification date, **When** a tax
   base is computed from it, **Then** that base, the charge derived from it and every
   figure downstream carry the unverified mark.
2. **Given** an observation whose age — from the later of its verification and retrieval
   dates — exceeds the declared threshold for its kind, **When** a tax figure is derived,
   **Then** the figure reports the staleness, naming the observation and its threshold.
3. **Given** an official-rate value kind declared with no staleness threshold, **When** the
   data is loaded, **Then** loading fails naming the kind, rather than defaulting to a
   permissive threshold.
4. **Given** a taxable event whose own inputs are marked and a fully verified rate, **When**
   the base is converted, **Then** the event's mark survives the conversion: converting a
   marked amount never launders the mark.

---

### User Story 5 - Nothing treats one country's rate as the rate (Priority: P3)

Official rates are declared per publishing authority and per ordered currency pair. A
second series — another central bank, another pair, another jurisdiction's tax currency —
is a data-only addition that loads and is addressable, even though nothing consumes a
second one yet.

**Why this priority**: Principle II applied to the input most likely to be hard-coded as a
singleton, and P3 for the same reason 007's equivalent story was: if Stories 1–4 are built
correctly this already works, and this story's job is to prove it before a second
jurisdiction (required test E8) discovers otherwise.

**Independent Test**: Declare a second, differently identified series purely as data and
confirm it loads and is addressable, with the first still driving results and no source
file edited.

**Acceptance Scenarios**:

1. **Given** a second official-rate series with a distinct identity declared purely as
   data, **When** it is loaded, **Then** loading succeeds and the series is addressable,
   with zero source lines changed.
2. **Given** two series that both quote the same pair, **When** a tax base is computed,
   **Then** the series used is the one the jurisdiction declares for its tax currency —
   named in the output — and never picked by whichever loaded first.
3. **Given** an official rate quoted per a number of units other than one, **When** a base
   is computed, **Then** the declared quotation unit is applied and appears in the output;
   a series with no declared quotation unit fails at load rather than defaulting to one.

---

### Edge Cases

- **An event on a weekend or a public holiday** — the publisher does not publish that day.
  Either the series declares a cited non-publication-day rule and the output states which
  date's rate was applied, or the request refuses naming the date. There is no third
  behaviour, and the engine never decides for itself what a weekend is (FR-011). For the
  Ukrainian series this is the refusal, and stays the refusal: its rule is written in
  working days and cannot be declared until a calendar can be (FR-018).
- **A date inside a gap in an otherwise continuous series** — a refusal naming the date,
  identical in shape to the weekend case; the engine cannot tell the two apart and must not
  try.
- **A date before the series' earliest observation, or after its latest** — a refusal
  naming the date and the covered window. No extrapolation in either direction; "the last
  known rate" is an invention with a plausible face.
- **Two observations for the same series, pair and date** — a load-time collision naming
  the file. One date, one official rate: unlike a channel, there is nothing here for a
  second value to legitimately be.
- **An observation dated in the future** — rejected at load. A rate for a date that has not
  arrived is a forecast wearing an observation's clothes (007's own edge case, restated
  where it bites harder: a forecast rate would silently set a legal base).
- **An observation declared with two sides (a buy and a sell)** — a load failure. Two sides
  is what a channel has. An official rate that acquired a spread would be a channel with a
  government's name on it, and the whole distinction would be gone.
- **A rate of zero, a negative rate, or a missing quotation unit** — load failure naming
  the file and the field. No default unit, because a rate quoted per 100 units read as per
  1 is wrong by two orders of magnitude and looks entirely reasonable.
- **A route leg naming no channel, or an unknown one** — costing refuses exactly as it does
  today. This feature adds no fallback and removes none of the existing refusals.
- **A tax base requested for an event already in the tax currency** — no rate is consulted
  and no rate-unavailable reason is produced. A refusal for a rate nobody needed is a false
  refusal, and a false refusal trains a reader to ignore true ones.
- **A tax base requested against a series that does not quote the event's currency pair** —
  refused naming both. No pair is inferred from another, exactly as 002's `_check_channel`
  refuses to infer one.
- **The display currency switched to the currency an event was denominated in** — the tax
  base does not move. It is fixed by law at the official rate on the event's date and has
  nothing to do with what the reader is looking at (Principle VI).
- **An official-rate observation with an empty verification date** — proceeds under the
  unverified mark, exactly like every other observed value; distinct from a missing
  observation, which does not proceed at all.

## Requirements *(mandatory)*

### Functional Requirements

**The official rate as declared data**

- **FR-001**: Official rates MUST enter the system as declared, dated observations in data
  files. Each observation states the date it applies to, the value, its source, its
  retrieval date and its verification date — which MAY be empty but MUST NOT be absent. No
  official-rate value may originate from an implementer's or an agent's memory. This is the
  same epistemic category, and deliberately the same shape of obligation, as 007's CPI
  observations (its FR-001).
- **FR-002**: A series MUST declare its own identity: the authority that publishes it, the
  ordered currency pair it quotes, and the **quotation unit** — the number of units of the
  quoted currency the value is stated per. The quotation unit MUST be declared explicitly
  and MUST NOT default. ⚙ A published table that quotes some currencies per 1 unit and
  others per 100 is normal, and a value read at the wrong unit is wrong by two orders of
  magnitude while looking entirely plausible. A default here would make that failure silent.
- **FR-003**: Exactly one observation MUST exist per (series, date). A second is a
  load-time collision naming the file, and no observation may carry two sides. ⚙ An
  official rate is one number. Two sides is the defining property of an `FxChannel`, and a
  rate that acquired a spread would be a channel with a government's name on it.
- **FR-004**: Loading official-rate data MUST fail loudly — naming the file and the
  offending field or date — on a malformed value, an unrecognised field, a missing required
  field, a duplicate date, a non-positive rate, a missing or non-positive quotation unit, a
  date that has not yet arrived, an observation carrying two sides, or a duplicated series
  identity. No default MUST be substituted for anything absent.
- **FR-005**: Nothing in the system may treat one country's official rate as a singleton. A
  second series with a different identity MUST be a data-only addition that loads and is
  addressable, even though no second series is consumed in this feature — exactly what 007
  FR-002 requires of CPI, for the same reason (required test E8, a second jurisdiction).
- **FR-006**: Official rates MUST be a staleness kind of their own, with a threshold
  declared alongside the kind, following 002's FR-028 pattern: per kind of value, no
  permissive default, and a kind with no declared threshold fails at load. Staleness is
  measured from the later of an observation's verification and retrieval dates (002's
  FR-025 rule). ⚙ The kind is its own and not `tax_rule`: a legal *rate* changes by
  legislation and a six-month re-read is the right prompt, while an official *rate series*
  ages the way `cpi_index` does — what decays is the retrieval, because the publisher adds
  a day roughly every day and a series fetched long ago is a series missing its recent end.

**The tax base**

- **FR-007**: The taxable base of an event denominated in a currency other than the tax
  currency MUST be that event's own amount converted at the official rate declared **for
  that event's own date**, taken from the series the jurisdiction declares for its tax
  currency. Never an average, never a period rate, never the rate on a neighbouring date,
  and never a rate from a series the jurisdiction did not name.
- **FR-008**: This feature MUST NOT introduce a second notion of "the event's date". It
  consumes the date the taxable event already carries — 006's assumption records the
  standing default (the date the proceeds are received) and any class-specific legal timing
  rule arrives as cited data — and looks the rate up on exactly that date. ⚙ Two modules
  each with their own opinion about which date a taxable event happens on is how a tax
  figure becomes unreproducible, and it is precisely the kind of drift the tuple principle
  is written against.
- **FR-009**: An event already denominated in the tax currency MUST NOT consult an official
  rate at all: its base is its amount, and no rate-unavailable reason may be attached to it.
- **FR-010**: Where no observation is declared for the event's date, the outcome MUST be a
  typed refusal naming the series, the currency pair and the date. The system MUST NOT
  interpolate between observations, extrapolate past either end, carry a previous date's
  value forward, or snap to the nearest observation. A missing rate is a gap, exactly as a
  missing CPI month is a gap (007 FR-004).
- **FR-011**: A series MAY declare a **non-publication-day rule** — a statement of which
  declared observation governs a date the publisher does not publish for — and that rule
  MUST be declared data carrying its own citation, never engine logic. **A paraphrase is not
  a citation and MUST NOT enter as one**: the citation MUST name a text that was read, and
  agreement between secondary sources restating a rule is not a substitute for it. ⚙ Not a
  style rule — the paraphrase this feature was offered turned out to merge two provisions
  the primary text keeps apart ("Owner verification tasks" quotes both). The engine MUST NOT
  contain any notion of a weekend, a public holiday or a banking calendar. Where a series
  declares no such rule, FR-010's refusal stands: the absence of a rule is not permission to
  choose one. Where a rule does apply, the output MUST state **which observation's date**
  supplied the rate alongside the event's own date, so a Friday rate applied to a Sunday
  event is visible rather than implied.

  ⚙ The Ukrainian rule's **content** is an owner verification task, not an open
  clarification: FR-010 and the sentence above specify the behaviour in the rule's absence
  completely. But the content turned out not to be the only thing missing — the retrieved
  text is written in working days and holidays, which nothing here can declare, so FR-018
  states plainly that declaring it is a feature and not a data entry. See "Owner
  verification tasks", which also records what retrieving it has already cost, so nobody
  spends the attempts twice.

**The prohibition, in both directions**

- **FR-012**: The amount **received** MUST NEVER be computed from an official rate. A
  realised amount comes from the declared channel that actually did the converting (002's
  machinery). This feature MUST NOT add any path — a fallback, a default, a "reference"
  option — by which an official rate could price a route leg, and the existing refusals at
  `core/routes/legs.py` and `data/declarations/resolver.py` MUST remain exactly as they are.
- **FR-013**: A channel's `reference_rate` MUST NEVER serve as a tax rate. ⚙ Two reasons,
  and the weaker one is that today's is a synthetic fixture. The stronger one is
  categorical: a reference rate is a mid-market number used to express a spread, chosen by
  whoever declared the channel; an official rate is set by an authority and named by law. A
  system that let one stand in for the other would be inventing a legal value from a
  costing convenience.
- **FR-014**: Switching the display currency MUST NOT change any tax base, any charge, or
  any ranking (Principle VI). ⚙ Restated here as a prohibition because this is the first
  feature that could plausibly break it: it introduces the first conversion the tax side
  performs, and a conversion module that does not know which role it is serving is exactly
  how the roles get conflated.

**Provenance and reporting**

- **FR-015**: Every figure derived through an official-rate conversion MUST carry the union
  of the converted amount's provenance and the rate observation's. An unverified mark or a
  staleness report on either side MUST appear on the base, on the charge and on everything
  derived from them. A transform that drops the mark is a defect of the highest severity.
- **FR-016**: Every converted tax base MUST report the series it used, the observation date
  whose rate was applied, the rate value and the quotation unit — enough for a reader to
  re-derive the base on paper without opening a data file. ⚙ Principle III's
  every-number-traceable rule, made concrete for the one conversion where the inputs are
  invisible in the result: a hryvnia figure gives no hint of which dollar amount and which
  date produced it.

**What ships**

- **FR-017**: This feature MUST ship with the Ukrainian series declaring **no**
  non-publication-day rule, so every date the National Bank does not publish for refuses
  under FR-010 from the first run. ⚙ A gap recorded only in a specification is a gap nobody
  meets; a gap that refuses is one the first run reports, to the person who can close it.
  This is the project's standing pattern — a declared absence with a visible consequence —
  and it is why the missing rule needs no placeholder.
- **FR-018**: **Declaring the Ukrainian rule is not a data-only change, and MUST NOT be
  planned as one.** Its text was retrieved on 2026-08-24 and reading it settled the
  question the other way: пункт 10 розділу III is expressed entirely in terms this system
  has no vocabulary for — *«останній робочий день тижня»*, *«передсвятковий день»*,
  *«вихідні або святкові дні»*, *«перший післясвятковий робочий день»* — and пункт 11 of the
  same розділ adds a fifth, the Cabinet's power to move working days. FR-011 forbids the
  engine from containing any notion of a weekend, a public holiday or a banking calendar,
  and it is right to; but that leaves the rule undeclarable, because **no entity in this
  feature supplies a working-day and holiday calendar** and the rule cannot be evaluated
  without one.

  The one encoding that avoids a calendar — *the latest observation on or before the event
  date* — MUST NOT be adopted as a substitute. It cannot distinguish a weekend from a gap in
  the series, which this feature's own edge cases say the engine cannot tell apart and must
  not try, and adopting it would make FR-010's refusal unreachable for exactly the dates
  FR-010 exists to refuse.

  What closing FR-011 for Ukraine actually needs is a **declared, cited working-day and
  holiday calendar** — a new kind of declaration, whose own provenance, jurisdiction and
  amendment history are a feature's worth of question, not a data entry. This feature MUST
  NOT design it. It is recorded as `specs/features.toml`'s `[[future]]` entry
  `declared-working-day-calendar`, and until it lands FR-017's refusal is what the Ukrainian
  series does.

### Key Entities

- **Official-rate series** — a declared, identified sequence of single-sided rate
  observations from one publishing authority for one ordered currency pair: its authority,
  its pair, its quotation unit, optionally its non-publication-day rule, and its
  observations. Shaped so a second series is a data-only addition.
- **Official-rate observation** — one date's published rate: the date, the value, source,
  retrieval date, verification date. The atom of the tax currency. One per date, one side,
  no spread.
- **Quotation unit** — the number of units the observation's value is stated per. Declared,
  never defaulted, and reported on every figure it scaled.
- **Non-publication-day rule** — a declared, cited statement of which observation governs a
  date the publisher does not publish for. Data with a citation; absent it, the date
  refuses. A rule whose text is written in working days or public holidays cannot be
  declared against the entities in this list, which is FR-018's subject.
- **Official-rate staleness kind** — the declared threshold governing when rate
  observations count as stale, following 002's per-kind pattern; its own kind, no permissive
  default.
- **Tax-currency conversion** — the record of one base being struck: the source amount, the
  series, the observation date used, the rate, the quotation unit, the resulting base, and
  the union of both sides' provenance. What FR-016 reports and what a hand check re-derives.
- **Official-rate-unavailable reason** — the typed refusal. Not an error, not a zero, and not
  a number. It is **two** entities rather than one, because they cannot name the same things
  and the fix for each is a different sentence:
  - *no rate on the date* — a declared series has no observation for the event's date and no
    declared rule reaching one. Names the series, the pair and the date, and the window it
    does cover — or that it declares no observation at all, which is what the Ukrainian series
    ships doing.
  - *no series for the pair* — the jurisdiction declares none, or the one it declares quotes
    something else. There is no series id to report where none is declared, and **no date to
    report it against**: the question failed before a date was consulted.

  ⚙ Corrected 2026-08-30, during implementation. This entry originally described only the
  first and was the specification's only description of either, so the second refusal had no
  entity and no requirement of its own. **The second still has no FR** — this correction gave
  it an entity, not a requirement — which is the remaining gap in this section. Which variant
  carries what is asserted per field in `tests/unit/test_official_rate_refusals.py`; prose
  points there rather than restating it, because every prose copy of it went false.
- Reused unchanged: the provenance record, the money record and its currency tag, the tax
  class and charge records of feature 001, the channels and legs of feature 002.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A dollar-denominated taxable event on a covered date produces a hryvnia base
  matching an independently hand-computed conversion within the single project tolerance,
  with the arithmetic recorded alongside the check. (FR-007)
- **SC-002**: The same amount taxed on two dates with different declared rates produces
  bases differing by exactly the declared rate difference times the amount — verified
  against hand arithmetic, not against the engine's own other answer. (FR-007)
- **SC-003**: Across a deliberate battery of uncovered dates — a gap in the middle, a date
  before the first observation, a date after the last — 100% produce typed refusals naming
  the series, the pair and the date, and zero produce a number. No configuration, flag or
  option exists that makes any of them interpolate, extrapolate or carry forward. (FR-010)
- **SC-004**: Across a deliberate battery of broken rate files — malformed value, unknown
  field, missing field, duplicate date, non-positive rate, missing quotation unit,
  future-dated observation, a two-sided observation, duplicated series identity — every
  case fails naming the file and the offending field or date, and no case substitutes a
  default. (FR-003, FR-004)
- **SC-005**: With one rate observation left unverified, 100% of tax bases and charges
  derived from it carry the unverified mark; with the converted amount's own inputs marked
  and the rate fully verified, the derived base still carries the mark. No derived figure
  appears unmarked in either direction. (FR-015)
- **SC-006**: An observation aged past its declared threshold marks every derived tax
  figure stale, naming the observation and its threshold; a rate kind declared without a
  threshold fails at load; fresh observations produce zero staleness warnings. (FR-006)
- **SC-007**: One dollar amount converted through a declared channel and struck as a tax
  base at a deliberately different official rate produces two separately reported,
  separately labelled figures, and no output presents either as the other. (Story 2)
- **SC-008**: No cost, route, leg or channel figure anywhere in the system is derived from
  an official rate, and no tax base anywhere is derived from a channel rate or a channel's
  reference rate — asserted as a standing property of the whole engine, not of one call
  site. (FR-012, FR-013)
- **SC-009**: A full run repeated with the display currency switched produces bit-identical
  tax bases, charges and rankings. (FR-014)
- **SC-010**: An event denominated in the tax currency produces its base with no official
  rate consulted and no rate-unavailable reason attached, in 100% of cases. (FR-009)
- **SC-011**: A second official-rate series with a distinct identity, declared purely as
  data, loads and is addressable with zero lines of source code changed; and the series a
  tax base used is named in its output rather than being whichever loaded first. (FR-005)
- **SC-012**: A rate declared per a quotation unit other than one produces a base matching
  hand arithmetic that applies the unit, and the unit appears in the output; omitting the
  unit fails at load. (FR-002)
- **SC-013**: `docs/METHODOLOGY.md` gains the tax-base conversion — its plain-language
  definition, the date-selection rule, and a worked example — in the same change that
  implements it, verified by that change's own diff rather than by a follow-up. (FR-016 and
  the constitution's documentation clause)
- **SC-014**: With no non-publication-day rule declared for the Ukrainian series, an event
  dated on a date that series does not cover refuses — so the missing rule is something a
  run reports, not something only this specification says. (FR-011, FR-017)
- **SC-015**: A **synthetic** series declaring a non-publication-day rule expressible
  without a calendar produces FR-011's applied-date output — the observation's date beside
  the event's — with zero source lines changed. The claim tested is that the declared-rule
  path exists and reports what it applied; it is deliberately **not** a claim about the
  Ukrainian rule, which FR-018 records as needing a declared calendar this feature does not
  build. ⚙ **Such a rule exists and the criterion is satisfiable**, which is worth one
  sentence because a planner reading FR-018 could otherwise conclude no calendar-free form
  is possible and skip the criterion. FR-011 defines the rule as *a statement of which
  declared observation governs a date the publisher does not publish for*, and an
  **explicitly enumerated mapping — this date's rate governs that date, listed** — is such a
  statement, needs no calendar, and is what a synthetic series declares here. What FR-018
  rules out is deriving the mapping from a rule written in working days; it does not rule
  out declaring the mapping. ⚙ Stated as two criteria because the earlier single one
  asserted both at once and the second half was false: a test written against it would have
  had to either build the calendar or pass by pretending пункт 10 says something simpler
  than it does. (FR-011, FR-018)

## Assumptions

- **No real rate values enter with this spec.** Acceptance examples run against
  clearly-labelled synthetic observations whose values are stated in the test itself,
  exactly as 001 did with its synthetic issue and 007 with its synthetic CPI. The examples
  test the conversion arithmetic, not the hryvnia. Real observations arrive later as a data
  file carrying its own provenance from the published source, and nothing is invented to
  make an example work.
- **How the real data arrives is tooling, and is out of this feature's scope.**
  `scripts/fetch_cpi.py` established the pattern: a repository script retrieves a series and
  writes a declaration with an **empty** `verified_on`, because automation retrieves and
  never verifies — `data/cpi/ua.toml`'s header says so in as many words, including "do not
  hand-edit: re-run the script and read the diff". The National Bank publishes official
  rates through an open developer API and the same pattern applies unchanged. Building that
  script is not part of this feature, and the general case is already recorded as the
  `provider-automation` `[[future]]` entry. What this feature owes it is only the data shape
  the script would write into.
- **One consuming jurisdiction, one pair.** UA is the only jurisdiction whose tax currency
  is served here, and UAH/USD the only pair exercised. The second series of FR-005 is
  declarable and addressable, not consumed.
- **Rate selection is by event date, not by settlement or booking date.** FR-008 defers to
  the date the taxable event already carries; this feature introduces no new timing rule and
  resolves no timing question. Any class-specific legal timing rule arrives as cited data,
  per 006's FR-011.
- **No FX gain or loss line.** This feature makes the asymmetry computable and reportable as
  two figures side by side. Attributing the difference as its own named line in a waterfall,
  and the flat-in-USD taxable-gain case itself, need a taxable foreign-currency position and
  belong to whichever feature declares one.
- **No delivery surface.** As in 001, 006 and 007: results are produced and asserted by the
  test suite; there is no UI and no CLI in this feature.

## Clarifications resolved

Two questions were raised while writing this specification, and both are resolved. The
first was answerable from the repository's own recorded decisions. The second was answered
by re-reading what it was actually asking: a behaviour was never in doubt, only a value.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Is the official rate a kind of `FxChannel` — a one-sided channel with a zero spread — or a separate thing? | **A separate thing, and the separation is the feature.** A channel is a market you transact in and decides an amount received; an official rate is a legal reference you never transact at and decides a tax base. Declaring the official rate as a channel would make the single most valuable finding in `SIMULATOR_SPEC.md` §4.4 inexpressible, because the two numbers it contrasts would be the same number. Settled by the constitution's own three-roles clause and by the two refusals already written into `legs.py` and `resolver.py`. | FR-003, FR-012, FR-013, SC-008; the whole "Why this feature exists" section |
| 2 | What governs an event dated on a day the publisher does not publish for? | **Resolved: this was never a clarification.** The *shape* is settled — a declared, cited, per-series rule or a refusal, never engine logic and never a weekend the engine knows about — and so is the *behaviour* when no rule is declared: FR-010's refusal stands, and FR-017 ships it live. What was missing was the rule's **content**; retrieving it on 2026-08-24 showed that the content is not all that is missing, because пункт 10 is written in working days and holidays and nothing here can declare one. Carried as owner verification task 1 for the reading, and FR-018 for the calendar. | FR-010, FR-011, FR-017, FR-018, SC-014, SC-015 |

## Owner verification tasks

One value is retrieved but not verified. It is recorded as a task, never filled with a
guess; until it closes — and until FR-018's calendar exists — FR-017's refusal is what the
feature does.

1. **The owner's own reading of the clause stating which official rate governs a day the
   National Bank does not set one.** The clause is **пункт 10 розділу III** of the
   *Положення про встановлення офіційного курсу гривні до іноземних валют та розрахунку
   довідкового значення курсу гривні до долара США й облікової ціни банківських металів*,
   **затверджене Постановою Правління Національного банку України від 10.12.2019 № 148**.
   It is a point of the Положення, not of the Постанова: the Постанова has seven points and
   its п. 7 is its own commencement, *«Постанова набирає чинності з 27 грудня 2019 року»*.
   Served on 2026-08-24 and re-read 2026-08-25 at
   <https://zakon.rada.gov.ua/laws/show/v0148500-19/print>:

   > Офіційний курс гривні до СПЗ та іноземних валют … починають діяти наступного робочого
   > дня після дня встановлення/розрахунку.
   >
   > Офіційний курс гривні до СПЗ та іноземних валют та облікова ціна банківських металів,
   > установлений/розрахована:
   >
   > 1) на останній робочий день тижня або на передсвятковий день, діють протягом наступних
   > вихідних або святкових днів;
   >
   > 2) в останній робочий день тижня або в передсвятковий день, починають діяти в перший
   > робочий день наступного тижня або в перший післясвятковий робочий день.

   ⚙ **Which of those words are № 148's, and which are not.** The page marks абзац перший
   *«{Абзац перший пункту 10 розділу III в редакції Постанови Національного банку № 36 від
   24.03.2025}»* and абзац другий *«{Абзац другий … із змінами, внесеними згідно з
   Постановою Національного банку № 36 від 24.03.2025}»*, and records that a fifth абзац was
   *виключено* by the same Постанова. **Підпункти 1) and 2) carry no marker at all**, so
   they are № 148's own text — and they are precisely the part that answers FR-011. The
   answer survives the amendment; the citation as this specification first wrote it did not.
   Anything citing this rule must therefore name three things: the Положення, Постанова
   № 148 that approved it, and **Постанова Національного банку № 36 від 24.03.2025** for the
   current wording of абзаци перший and другий.

   ⚙ Feature 012 carries a verification task specifically for the
   consolidated-versus-amending-text risk, and it is how Закон № 4835-IX was found. This
   citation is the one that needed the same read and did not have it until 2026-08-25. The
   general lesson is cheap to state and was expensive twice: **read the consolidated text,
   and read the amendment markers under the provision you are quoting.**

   ⚙ **What the retrieval cost, and the form that works.** Three routes were tried on
   2026-08-23 and all three failed: `bank.gov.ua` returns **HTTP 403** to automated
   retrieval; the NBU methodology PDF search engines surface —
   `.../Oficial_reference_rates_2019-12-27_method.pdf` — is a **dead link, HTTP 404**; and
   `zakon.rada.gov.ua` was recorded as serving only a table of contents. That third entry
   was **too broad, and it cost this feature a citation it could have had**.

   For the next retriever, in one line: **`https://zakon.rada.gov.ua/laws/show/<id>/print`,
   with `curl --compressed`.** That form served the full text of every document tried on
   2026-08-24 and 2026-08-25, this one included, and the compression flag is not optional —
   the consolidated Податковий кодекс (`2755-17/print`) arrives gzip-encoded and is
   unreadable without it.

   ⚙ Two things this specification previously advised are **false, and were re-tested on
   2026-08-25**. `/go/<id>` is not a different view: it is an HTTP **302 redirect to
   `/laws/show/<id>`**, so the two forms return byte-identical responses and choosing
   between them is choosing the same URL twice. And the *«Відбувається форматування
   тексту!»* shell is not a length effect: this Постанова is ~33k characters of text and its
   `/laws/show/` view serves the shell, while № 4015-IX is ~54k and serves in full. Whatever
   selects the shell, document length is not it — which is why the rule above is *always*
   `/print`, and never `/print` only when the document looks long.

   ⚙ **What the paraphrase lost.** Secondary sources restate the rule as *"the rate set on
   the last business day applies through the following non-working days and the first
   working day"*, one sentence covering what пункт 10 splits into two підпункти: a rate set
   **на** the last working day governs the weekend, and a rate set **в** the last working day
   governs the first working day after it. Whether the merged sentence reaches the same
   answer is precisely what a reader cannot settle from the paraphrase — which is why
   FR-011's prohibition kept it out.

   ⚙ This is **not** an UNSETTLED question in the sense feature 009 uses the word
   (`specs/009-tax-depth/spec.md`, "Legal grounding"). Nothing about the law is in dispute
   and no reading competes with another, so there is nothing for a labelled scenario switch
   to be a switch between. What was missing was a retrievable text; what is missing now is
   the owner's verification of it, and the interim behaviour is the same refusal.

## Required tests this feature relates to

- **F1** (*"A position flat in USD across a devaluation produces a positive taxable gain in
  UAH. This test is the reason the rewrite exists."*) is **not closed** by this feature.
  `features.toml` records its two blockers as *"a taxable foreign instrument + dated
  official rates"*; this feature removes the second and leaves the first. F1 needs a
  position with a cost basis struck at one date's official rate and proceeds struck at
  another's, and no instrument declared in the registry today is denominated in a foreign
  currency. The `fx-tax-asymmetry-f1` `[[future]]` entry therefore stays open, with its note
  narrowed to the remaining blocker when this feature lands.
- **F3** (*"Historical series convert at per-date rates, never at today's rate"*) is **not
  closed** either, and is deliberately not attempted: F3 is a statement about the display
  switch converting a chart, which is a channel-rate question about presentation, not a
  tax-currency question. Sharing the phrase "per-date rates" with this feature is a
  coincidence of wording, and treating it as the same requirement would conflate the display
  and tax roles in the one place the constitution names explicitly.
- **F2** (*"Switching display currency changes no realised amount, no tax figure, and no
  after-tax UAH ranking"*) is likewise not closed — there is no display switch — but FR-014
  and SC-009 establish the tax-figure half of it as a standing property before the switch
  exists, so the row cannot be closed later by a feature that never checked it.
- Per the constitution, every behaviour above lands with a hand-computed worked example (the
  conversion arithmetic, SC-001, SC-002, SC-012), load-failure coverage (SC-004), refusal
  coverage (SC-003), and propagation checks (SC-005, SC-006). SC-008's whole-engine property
  is a `contract` test, since it is a compliance statement about Principle VI rather than an
  assertion about one call site.

## Out of scope

Named explicitly so the plan does not drift into them: the declared working-day and holiday
calendar FR-018 records, and therefore the Ukrainian non-publication-day rule itself; the
display-currency switch and all of required tests F2, F3 and F4's presentation behaviour;
converting historical series for charts; any FX forecast, path or scenario
(`SIMULATOR_SPEC.md` §4.4's "UAH paths are scenarios, never forecasts" belongs to whichever
feature introduces one); the fetch script
and the `Provider` interface generally, already recorded as the `provider-automation`
`[[future]]` entry; a foreign-currency-denominated instrument and therefore F1 itself; the
FX gain or loss as a named attribution line; any change to how route legs, channels or
costs are computed, which this feature explicitly leaves untouched; the ФОП regime, the
income-stream tax class and the mandatory sale of foreign currency, all of which are feature
012; filing, payment timing and loss carryforward (required tests E2, E7); crypto tax
scenarios; and the web and command-line interfaces.
