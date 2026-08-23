# Feature Specification: The ФОП group 3 regime

**Feature Directory**: `specs/012-fop-group-3`

**Feature Branch**: `spec/011-012-fop` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-23

**Status**: Draft — **one open `[NEEDS CLARIFICATION]`** (FR-022, the tax treatment of
contract income credited somewhere other than the ФОП account) and **five owner
verification tasks**. The open item narrows scope rather than blocking it: until it is
answered, income declared as arriving anywhere but a ФОП account refuses rather than being
taxed at these rates.

**Input**: The regime the owner's contract income actually lands in. Contract income arrives
through Deel and is directed to a **ФОП account in USD**; Ukrainian currency restrictions
mean the dollars must be sold for hryvnia to be spent; and the tax is assessed at the
official rate on the **credit** date, not the sale date. Model the regime — єдиний податок
and військовий збір as two components on dated schedules, ЄСВ as a periodic obligation
rather than a rate — and retire `IncomeStream.income_tax_rate`.

---

## Why this feature exists

The owner's largest single cash flow is his contract income, and the system currently
models its tax with a `float | None` on the income stream.

That scalar was honest for what feature 002 needed. `core/streams/streams.py` argues its
one genuinely load-bearing decision carefully — an omitted rate means *the owner has not
stated one*, which is not zero, so `deployable` returns `IncomeTaxRateUndeclared` with no
net field for a caller to mistake for a figure. That reasoning is correct and this feature
keeps it. What it cannot survive is the actual shape of the regime the money lands in:

- **Two components with different commencement dates.** A scalar is one number. The regime
  charges єдиний податок and військовий збір, and the levy started on a different date from
  everything else in the same law.
- **A fixed-amount obligation that is not a percentage of anything.** ЄСВ is a statutory
  monthly sum, triggered by a month elapsing rather than by income arriving.
- **A per-month conditional exemption.** The ЄСВ exemption depends on a fact about each
  individual month. A scalar cannot say *which* months.
- **A base in a different currency from the amount.** The base is the credited dollars at
  the official rate on the credit date; the hryvnia actually received comes from a market
  rate on a different date. One number cannot be both.

Feature 006 already solved the general form of the first problem: it gave **instruments**
tax classes with dated rate schedules, and made adding a legislated change one entry in a
data file. It left the income stream behind with its scalar. **This feature closes that
inconsistency**: a stream names a tax treatment, exactly as an instrument does, and the
rates live in curated, cited tax data rather than as a bare number in per-owner data.

That relocation is worth stating on its own, because it repairs a boundary rather than just
moving a field. `data/README.md` exempts per-owner streams from the citation requirement
with a good argument: *an owner's own salary is not an observation needing a citation but a
statement of fact by the only person who can make it.* The argument holds for an amount and
a cadence. It never held for a **tax rate**, which is a public legal fact about the
Republic and not a statement about the owner — and the current schema lets one be written
into per-owner data uncited. After this feature, the owner declares *which regime he is in*
(a fact about him, uncited, correctly) and the regime's rates live in `data/tax/` with
their sources (public facts, cited, correctly). Principle VII's boundary comes out sharper
than it went in.

### One law, two commencement dates

The clearest justification in this repository for why rates had to become dated schedules
is sitting in the owner's own tax position, and it is a single statute.

**Закон України № 4015-IX від 10 жовтня 2024** introduced a військовий збір for ФОП of the
third group at **1% of income, from 1 January 2025**. The **same law** raised the levy on
ordinary personal income from 1.5% to **5%, from 1 December 2024**. One law, two rates, two
payers, two commencement dates a month apart.

A system carrying a scalar per stream cannot express either change, let alone both. A
system carrying dated schedules (feature 006's E10) expresses both as data entries and
would have expressed them correctly on the day the law passed. This feature is where that
machinery meets the money.

⚙ Only the **first** of those two facts becomes a declared value here. The 1.5% → 5%
personal-income change is cited as the *argument*, not entered as a rate: no income stream
in this model is taxed under it, and entering a legal rate nothing consumes would be a
number nobody checked sitting in the data waiting to be believed.

## The verified legal facts

Every value below is entered as data with the citation shown and an **empty**
`verified_on`, in the repository's standing sense: retrieved and cited is not verified, and
the mark propagates to every figure derived from it (`SIMULATOR_SPEC.md` §11 item 2,
constitution Principle I). Nothing here originates from an implementer's or an agent's
memory.

| Fact | Value | Source | State |
|---|---|---|---|
| Єдиний податок, ФОП group 3, not a VAT payer | **5% of income** | zaxid.net instruction article — *«єдиний податок в сумі 5% від доходу»* | Retrieved 2026-08-23, unverified. Primary Tax Code article is an owner verification task |
| Військовий збір, ФОП group 3 | **1% of income, from 1 January 2025** | Закон України № 4015-IX від 10.10.2024; business.diia.gov.ua announcement; zaxid.net — *«Ставка військового збору для них – 1% від доходу»*, *«з 1 січня 2025 року»*; oschadbank.ua blog | Retrieved 2026-08-23, unverified |
| Reporting and payment cadence, group 3 | **Quarterly** | zaxid.net — group 3 pay *«за підсумками першого кварталу»* | Retrieved 2026-08-23, unverified. Context, not a modelled figure — see FR-004 |
| ЄСВ | **Exempt for the months an employer paid at least the minimum contribution** | частина шоста статті 4 Закону України № 2464-VI, <https://zakon.rada.gov.ua/go/2464-17> | Owner-supplied citation, unverified; verbatim text not retrieved (the statute renders client-side) |
| Personal-income levy 1.5% → 5% from 1 December 2024 | Cited as argument only | Закон України № 4015-IX від 10.10.2024 | **Not entered as a value.** See the ⚙ above |
| VAT-payer status | The owner states he is not one | The owner | A fact about him, not a legal value: per-owner data, uncited, like his salary |

**Sources**, all accessed 2026-08-23:
<https://business.diia.gov.ua/news/viiskovyi-zbir-dlia-fop-ta-iurydychnykh-osib-zaprovadzhuietsia-z-1-sichnia-2025-roku>
(title retrieved; body not returned to automated retrieval),
<https://zaxid.net/viyskoviy_zbir_fop_3_grupa_2025_koli_platiti_skilki_kudi_instruktsiya_termini_n1607266>
(retrieved in full; the quotes above are from it),
<https://www.oschadbank.ua/blog/vijskovij-zbir-2025-stavka-stroki-splati-j-pilgi>
(owner-supplied; automated retrieval hit a redirect loop),
<https://zakon.rada.gov.ua/go/2464-17>.

The 3% rate that applies to a VAT payer is **not** entered: the owner is not one, no
citation for it was retrieved, and a legal value nothing consumes is a value nobody checks.
The regime declaration names which variant applies (FR-002) so the second variant is a
data-only addition when it is ever cited.

## Design positions this specification is built on

Four decisions were taken before the requirements were written. Each is argued rather than
asserted, because each rules out a shape that would otherwise look reasonable.

**1. ЄСВ is not a tax on income and must not be modelled as a rate.** Three things
disagree, not one. Its *trigger* is a month elapsing, not income arriving — it is owed in a
month with no income at all. Its *base* is a statutory fixed amount, not a percentage of
anything. Its *exemption rule* is a fact about employment in that month, not a property of
the income. Folding it into an income-tax rate would misclassify it even in the cases where
the arithmetic happened to come out right, and it would come out wrong the first month
income is zero.

**2. "Currently zero" is the wrong shape.** The exemption is per month and conditional on a
fact about that month. If the owner leaves employment mid-year, some months are exempt and
others are not, and the system must be able to say which. A constant zero cannot express
that; it cannot even express the question. So the slot is reserved in **the shape the law
actually has** — a per-month obligation with a declared, dated exemption — and the fact that
it currently resolves to nil every month is an *output*, not a schema.

**3. `IncomeStream.income_tax_rate: float | None` is retired.** It cannot carry two
components with different commencement dates, a fixed-amount obligation, or a per-month
conditional exemption. The stream names a **tax treatment** instead — exactly what feature
006 did for instruments, and the inconsistency 006 left behind.

**4. The tax base and the money received are two different numbers.** The base is the
credited dollars at the official rate on the **credit** date (feature 011). The hryvnia the
owner ends up with comes from a market channel on the **sale** date. Different rate,
different date, different number. Keeping them apart is not a presentational nicety — it is
the difference between what he owes and what he has.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contract income taxed under the regime it lands in (Priority: P1)

The owner declares that his contract income arrives in a ФОП account in dollars. A month's
income is then charged єдиний податок and військовий збір as two separately named lines on
a hryvnia base — the dollars credited, at the official rate on the credit date — and the
output shows both charges, the base, the rate that struck it and the date that rate belongs
to.

**Why this priority**: This is the feature, and it is the first time the system taxes the
owner's actual largest cash flow with anything but a placeholder. Every deployable-capacity
figure in the model is currently either a zero or an explicit "unknown"; this is what makes
it a number.

**Independent Test**: Declare a synthetic monthly amount arriving on a known date, declare
a synthetic official rate for that date, and check both charges and the base against
arithmetic worked out by hand on paper.

**Acceptance Scenarios**:

1. **Given** a stream declared as arriving in a ФОП account in a foreign currency and a
   declared official rate for the credit date, **When** a month's income is charged,
   **Then** the taxable base is the credited amount at that date's official rate and both
   components are charged on it, matching hand-computed arithmetic within the single
   project tolerance.
2. **Given** the same charge, **When** it is inspected, **Then** the two components appear
   as separately named lines using the names the law uses, each naming its own rate, its
   own cited source and its own verification date — never as one blended percentage.
3. **Given** no official rate is declared for the credit date, **When** the charge is
   attempted, **Then** the outcome is the typed refusal feature 011 specifies, naming the
   date — no charge is produced and no rate is borrowed from another date.
4. **Given** the credited dollars are later sold for hryvnia through a declared channel on
   a different date, **When** results are produced, **Then** the hryvnia received and the
   hryvnia tax base are two separately reported figures, and neither is presented as the
   other even when they happen to be close.
5. **Given** any charge produced under this regime, **When** its provenance is inspected,
   **Then** it carries the marks of both the rate schedule and the official-rate
   observation that struck its base.

---

### User Story 2 - The stream names a regime, not a rate (Priority: P1)

The owner declares which tax treatment his income stream falls under, the way he declares
which tax classes an instrument falls under. The rates live in curated tax data with their
citations. A stream that names no treatment still reports what it reports today: the
deployable amount is unknown, and at most the gross.

**Why this priority**: Equal-highest, because Story 1 is unimplementable on the old shape
and because the migration is the part that can quietly break something. Two behaviours must
survive it verbatim — *undeclared is not zero*, and *no net figure quietly equals a gross
one* — and they are exactly the kind of behaviour a schema change deletes by accident.

**Independent Test**: Run feature 002's deployable-capacity cases against the new shape and
confirm the undeclared case still yields a result with no net field on it; then declare a
treatment and confirm the net figure is net of the regime's charge rather than of a scalar.

**Acceptance Scenarios**:

1. **Given** an income stream naming a declared tax treatment, **When** deployable capacity
   is computed, **Then** it is net of the charges that treatment produces, and every
   component of `gross − charged = net` is present in the result.
2. **Given** an income stream naming no tax treatment, **When** deployable capacity is
   computed, **Then** the result carries no net field at all and states that the owner has
   not declared a treatment — the same claim, the same shape and the same reason as feature
   002's undeclared-rate result.
3. **Given** an income stream naming a treatment no tax file declares, **When** the data is
   loaded, **Then** loading fails naming the file, the stream and the unknown treatment; no
   default treatment exists and none is substituted.
4. **Given** the migration, **When** the tax rates are located, **Then** they are in curated
   tax data carrying source, retrieval date and verification date — not in the per-owner
   stream file, whose citation exemption never covered a legal rate.

---

### User Story 3 - One law, two commencement dates (Priority: P1)

The owner projects income across 1 January 2025. Months before that date are charged
without the військовий збір; months from it are charged with it. Both in one run, from two
dated entries in a data file, with no source change.

**Why this priority**: Equal-highest because it is the correctness proof for the whole
dated-schedule mechanism against a real statute rather than a synthetic fixture, and
because getting it wrong is invisible: a projection that charged 1% for all of 2024 would
look entirely plausible.

**Independent Test**: Project monthly income across the commencement date and check both
sides' charges by hand; then confirm that a month before the schedule's earliest entry
refuses rather than being charged at whatever the earliest entry says.

**Acceptance Scenarios**:

1. **Given** a levy schedule whose entry is effective 1 January 2025, **When** income
   arrives in December 2024 and in January 2025, **Then** the December charge has no levy
   line and the January charge does, in one run, matching hand-computed arithmetic.
2. **Given** income dated before the earliest entry of a component's schedule, **When** the
   charge is attempted, **Then** the outcome is a typed error naming the component and the
   date (feature 006's FR-012). No rate is defaulted, no zero is silently charged, and no
   entry is backdated to make a projection run.
3. **Given** a future legislated change to either component, **When** it is entered,
   **Then** it is one dated entry added to a data file, carrying its own source, retrieval
   date and verification date, with no source-code change.

---

### User Story 4 - ЄСВ reserved in the shape the law has (Priority: P2)

The owner declares, per month, whether an employer paid at least the minimum contribution
for him. Every month he did is exempt and owes nothing. The obligation exists in the model
as an obligation — a monthly amount, not a rate — so that the first month the exemption
stops applying, the system charges it instead of discovering that it has nowhere to put it.

**Why this priority**: P2 because it charges nothing today, and P2 rather than P3 because
the reason it charges nothing is a *condition*, and a condition that is only ever true has
never been tested. The owner is employed elsewhere and that employer pays; the day that
changes, an unmodelled obligation becomes an unbudgeted bill.

**Independent Test**: Declare a year in which the exemption holds for some months and not
others, and confirm the exempt months charge nothing while the non-exempt months are
handled per FR-021 — and that nothing anywhere expresses the obligation as a percentage of
income.

**Acceptance Scenarios**:

1. **Given** a year in which every month is declared exempt, **When** the projection runs,
   **Then** the total obligation is nil, and the nil is reported as *exempted for these
   months under this cited rule* rather than as an absence.
2. **Given** a year in which some months are declared exempt and others are not, **When**
   the projection runs, **Then** the exempt and non-exempt months are distinguishable in
   the output by month, and the exempt months' nil never spreads to the others.
3. **Given** a month with zero income, **When** the obligation is evaluated, **Then** its
   treatment does not depend on the income being zero — the trigger is the month, not the
   income — which is the property that distinguishes it from a rate.
4. **Given** a non-exempt month for which no statutory amount is declared, **When** the
   obligation is evaluated, **Then** the outcome is a typed refusal naming the month and
   the missing amount — never a zero, and never a rate applied to income as a stand-in.

---

### User Story 5 - The mandatory sale, and the spread paid twice (Priority: P2)

The dollars on the ФОП account cannot be spent domestically; they are sold for hryvnia
through a declared channel, at a cost. If the owner later wants dollars again — on a debit
card — he pays a spread a second time. Both costs come out of machinery that already
exists, and this feature adds none of it.

**Why this priority**: P2 because the numbers already work — 002 costs the conversion and
forbids reporting a one-way figure as a round trip (required test G6) — but the *boundary*
needs stating in this spec or the plan will re-model routing here. What this feature owes
the sale is the tax consequence of it, which is precisely that there is none: the sale does
not change the base.

**Independent Test**: Declare the ФОП account and the sale as an ordinary route leg through
an existing channel; confirm the cost is produced by the existing costing path, that the
round-trip figure back to dollars is the existing round-trip figure, and that neither
changes the tax base by a digit.

**Acceptance Scenarios**:

1. **Given** the compulsory sale of dollars on the ФОП account, **When** it is modelled,
   **Then** it is a declared route leg through a declared channel at a declared venue, and
   this feature introduces no new leg kind, no new channel kind and no new cost mechanism.
2. **Given** the owner later converting hryvnia back to dollars, **When** the comparison is
   produced, **Then** it is the existing round-trip cost — the second spread is not a new
   concept, it is the half of the round trip feature 002 already refuses to omit.
3. **Given** a sale executed at any market rate whatsoever, **When** the tax figures are
   recomputed, **Then** the taxable base is unchanged: it was fixed at the credit date and
   nothing about the sale moves it.
4. **Given** the difference between the hryvnia the base implies and the hryvnia actually
   received, **When** results are produced, **Then** the difference is visible as its own
   reported figure and is explicitly labelled as *not part of the taxable base*.

---

### User Story 6 - A second regime is data (Priority: P3)

A different ФОП group, the general system, a VAT-payer variant, or another jurisdiction's
regime is a data-only addition. Nothing in the engine knows that group 3 exists.

**Why this priority**: Principle II applied to the tax regime, and P3 for the same reason
006's and 007's equivalents were: if the other stories are built correctly this already
works, and this story's job is to prove it — before required test E8 (the same scenario
under two jurisdictions) discovers otherwise.

**Independent Test**: Declare a second, differently identified synthetic regime with a
different component set and different schedules, point a second synthetic stream at it, and
confirm both produce complete results with no source file edited.

**Acceptance Scenarios**:

1. **Given** a second regime declared purely as data with a different set of components,
   **When** a stream names it, **Then** complete results are produced with zero lines of
   source code changed.
2. **Given** a regime declaring a component the engine has never seen a name for, **When**
   it is charged, **Then** the component is charged and reported under its declared name —
   no component name is hard-coded, and no engine branch exists for "the levy".

---

### Edge Cases

- **Income credited on a day the official rate is not published** — feature 011's behaviour
  applies unchanged: a refusal naming the date, unless the series declares a cited
  non-publication-day rule. This feature does not get its own answer to that question.
- **Income dated before a component's earliest schedule entry** — a typed error naming the
  component and the date (006 FR-012). In particular, income before 1 January 2025 is not
  charged a levy of zero: the schedule simply does not reach back, and saying so is
  different from saying the rate was nil.
- **A month with zero income under a regime with a periodic obligation** — the two
  components charge nothing (no income), and the obligation is evaluated anyway, because a
  month elapsed. This is the case a rate-shaped model gets wrong.
- **A month in which the owner both was and was not employed** — the exemption is declared
  per month and the declaration is the owner's; if the underlying condition is finer than a
  month, that is a fact about the law this feature does not model and must not pretend to.
  Recorded as an owner verification task rather than resolved by a guess.
- **A non-exempt month with no declared statutory amount** — a typed refusal naming the
  month, never a zero.
- **A stream naming a treatment that no tax file declares** — a load-time failure naming the
  file, the stream and the unknown treatment.
- **A stream naming no treatment at all** — not an error: the same "deployable capacity
  unknown, at most the gross" result feature 002 produces today, with no net field on it.
- **A stream in the tax currency naming this regime** — charged normally, with no official
  rate consulted (011 FR-009). The regime is not a foreign-currency feature; it is a regime
  that happens to receive foreign currency.
- **Two regimes declaring the same identifier** — a load-time collision, as everywhere else.
- **A regime declaring a component with a negative rate, an unordered schedule, or two
  entries on one effective date** — load failure naming the file and the field (006 FR-003).
- **The mandatory sale executed at a rate far from the official one** — the taxable base
  does not move. The gap is reported as its own figure and labelled as outside the base.
- **Contract income directed somewhere other than the ФОП account** — refused rather than
  charged, pending FR-022's clarification. Applying ФОП rates to income that may not be
  ФОП income at all would be inventing a legal position.

## Requirements *(mandatory)*

### Functional Requirements

**The regime as declared data**

- **FR-001**: A tax **regime** MUST be declarable purely as data: an identity, the
  components it charges, each component's dated rate schedule, its declared periodic
  obligations, and its reporting and payment cadence. Adding a regime — a different ФОП
  group, the general system, another jurisdiction's — MUST require no source-code change
  and MUST introduce no regime-specific engine behaviour. No engine branch may exist for a
  named component.
- **FR-002**: The declaration MUST name which variant of the regime applies where the law
  offers more than one (for group 3, the VAT-payer and non-VAT-payer rates). The variant
  the owner is in is a **fact about him** and is declared as per-owner data with no
  citation, exactly as his salary is; the **rates** of every variant are public legal facts
  and live in curated tax data with citations. ⚙ This split is the point of the feature's
  data-model change, not an incidental tidy-up: `data/README.md`'s citation exemption for
  per-owner data is argued for an owner's statement about himself, and it never covered a
  legal rate.
- **FR-003**: Every rate, amount, effective date and exemption rule MUST carry its value,
  source, retrieval date and verification date, and an empty verification date is permitted
  and expected. No legal value in this feature may originate from an implementer's or an
  agent's memory. The mark MUST propagate to every derived figure.
- **FR-004**: The regime MUST declare its reporting and payment cadence (quarterly, for
  group 3) as data, and this feature MUST record each liability against the period it
  accrues to. It MUST NOT model payment timing, filing deadlines or the cash movement that
  settles a liability — those change no figure here and belong to feature 009 (required
  test E7). ⚙ The cadence is declared now, unused, so that 009 inherits a declared fact
  rather than having to guess one; a filing deadline that moves no number is context and is
  recorded as such in the sources table above, not as a requirement.

**Two components, two commencement dates**

- **FR-005**: The regime MUST charge **єдиний податок** and **військовий збір** as two
  separately named components on one base. They MUST NOT be blended into a single
  percentage at any point — not in the data, not in the computation, and not in the output.
  ⚙ `core/tax/interface.py` already argues this for PIT and the levy: *"foreign withholding
  creditable against PIT but not against the levy cannot be expressed against a blended
  figure at all."* The same argument applies to any two components with independent legal
  lives, which these have — a different statute created one of them, on its own date.
- **FR-006**: Component lines MUST be reported under the names the law uses for them. ⚙ The
  existing charge record carries two fixed lines named for personal income tax and the
  military levy. A єдиний податок charge is neither, and putting it in a field named
  personal income tax would be a mislabelling that no downstream reader could detect.
  Whether that is met by generalising the charge record to named components or another way
  is a planning decision; what this requirement fixes is that the output may not lie about
  what was charged.
- **FR-007**: Each component's rates MUST be declared as a **dated schedule** in feature
  006's sense: ordered entries, each with its effective date, its rate and its own
  provenance. The rate applied to an income event is the entry in force on the event's date,
  effective date inclusive (006 FR-011).
- **FR-008**: The військовий збір component MUST be declared effective **1 January 2025**
  at **1% of income**, cited to Закон України № 4015-IX від 10.10.2024 and the sources
  listed above. Income dated before the schedule's earliest entry MUST produce a typed error
  naming the component and the date (006 FR-012) — it MUST NOT be charged a rate of zero,
  because *"the schedule does not reach this date"* and *"the rate was nil"* are different
  claims and only one of them is cited.
- **FR-009**: The єдиний податок component MUST be declared at **5% of income** for the
  non-VAT-payer variant of group 3, with an effective date taken from its citation. Where
  the available citation establishes only that the rate is in force as of the source's own
  date, the entry MUST be declared effective from that date, and earlier income MUST refuse
  under FR-008's rule rather than being charged at a backdated entry. The primary Tax Code
  article and the rate's actual commencement date are recorded as an owner verification
  task.
- **FR-010**: The 1.5% → 5% change to the levy on ordinary personal income (same law, from
  1 December 2024) MUST NOT be entered as a rate by this feature. It is cited in the
  specification as the argument for dated schedules; no income stream here is taxed under
  it, and a legal value nothing consumes is a number nobody checks.

**The base is in the tax currency**

- **FR-011**: The taxable base of a foreign-currency income event under this regime MUST be
  the amount credited, converted at the official rate for the **credit date**, through
  feature 011's machinery. This feature MUST NOT introduce its own conversion, its own rate
  lookup, or its own idea of which date applies.
- **FR-012**: The hryvnia the owner actually receives MUST be computed from the declared
  channel that performs the sale, on the sale's own date, through the existing costing
  machinery. It MUST NOT be computed from the official rate, and the taxable base MUST NOT
  be computed from the channel (011 FR-012, FR-013).
- **FR-013**: The difference between the hryvnia the base implies and the hryvnia actually
  received MUST be reported as its own figure and MUST be labelled as **not part of the
  taxable base**. ⚙ This is the owner's real exposure and it points either way: the base can
  exceed what he has, or fall short of it. Reporting only one of the two numbers would hide
  whichever direction it went in, and netting them would assert a deduction nobody cited.
- **FR-014**: No deduction of any kind MUST be applied to the base by this feature — not the
  conversion spread, not a fee, not a cost. This is an **absence, recorded**: whether any
  deduction exists under this regime is an owner verification task, and until it is
  answered with a citation the base is the credited amount and nothing is subtracted from
  it. A modelled zero deduction and an unasked question are different claims.

**The stream names a treatment**

- **FR-015**: `IncomeStream.income_tax_rate` MUST be retired. An income stream MUST instead
  name a declared tax treatment, exactly as an instrument names tax classes (feature 006).
  A stream MAY name none.
- **FR-016**: A stream naming **no** treatment MUST produce the same claim, the same shape
  and the same reason as feature 002's undeclared-rate result: no net field at all, the
  gross reported as a known upper bound, and a stated reason that the owner has not declared
  a treatment. ⚙ 002's argument survives the migration verbatim — *no treatment declared* is
  not *a treatment that charges zero* — and this requirement exists because a schema change
  is exactly what deletes a carefully argued distinction by accident.
- **FR-017**: A stream naming a treatment that no tax file declares MUST fail at load,
  naming the file, the stream and the unknown treatment. No default treatment exists and
  none may be substituted.
- **FR-018**: The landing change MUST carry the retirement through everything that records
  the old shape: `data/README.md`'s citation-exemption note, the declaration-schema
  contract, `docs/METHODOLOGY.md`'s deployable-capacity formula, and a ⚙ cross-reference on
  feature 002's FR-007 recording that this feature supersedes it. ⚙ Recorded here as an
  obligation because 002's spec is not edited from this specification's branch — the same
  pattern feature 007 used for 001's FR-022.

**ЄСВ as a periodic obligation**

- **FR-019**: A regime MUST be able to declare a **periodic obligation**: an amount owed per
  elapsed period rather than a rate applied to income. Its declaration carries the period,
  a dated schedule of statutory amounts, and its exemption rule, each with its own
  provenance. It MUST NOT be expressible as, or coerced into, a rate on income. ⚙ Three
  things differ, not one: the trigger is a period elapsing rather than income arriving; the
  base is a statutory sum rather than a percentage; and the exemption turns on a fact about
  the period rather than on the income. A rate-shaped model gets the zero-income month wrong
  and cannot answer *which months*.
- **FR-020**: The obligation's exemption MUST be declared **per period** and MUST be
  conditional on a declared fact about that period — for ЄСВ, whether an employer paid at
  least the minimum contribution for that month, under частина шоста статті 4 Закону України
  № 2464-VI. A single "currently zero" value MUST NOT be used: it cannot express a year in
  which some months are exempt and others are not, which is the situation the owner enters
  the day his employment ends.
- **FR-021**: An exempt period MUST report nil **as an exemption applied**, citing the rule,
  rather than as an absence — the same distinction feature 001 draws for an exempt tax class
  (*"a zero charge that cites its exemption is the evidence the exemption was applied"*). A
  **non-exempt** period for which no statutory amount is declared MUST produce a typed
  refusal naming the period and the missing amount — never a zero, and never a rate on
  income used as a stand-in.

  [NEEDS CLARIFICATION is **not** raised here as a blocker: see the owner verification
  tasks. The statutory monthly minimum-contribution amounts and their effective dates were
  not supplied and are not guessable, and частина шоста статті 4's verbatim text could not
  be retrieved. The consequence is specified rather than deferred: with the exemption
  declared for every month the owner is employed, the obligation resolves to nil throughout
  and the missing amounts are never reached; the first non-exempt month refuses, naming what
  is missing.]

**What this feature leaves to routing**

- **FR-022**: This feature MUST NOT re-model funding routes. The Deel → ФОП account versus
  Deel → Coinbase choice is a funding-route question that features 002, 003 and 004 already
  answer: 002 costs the corridor, 003 says whether the money can get back out to something
  spendable, 004 composes chains. What this feature contributes is the **tax consequence of
  arriving in a ФОП account**, and nothing else.

  [NEEDS CLARIFICATION: whether contract income credited somewhere other than a ФОП
  account — a personal crypto exchange account, say — falls under this regime at all, or
  under a different treatment entirely. This is a legal question about the owner's position,
  not a modelling choice, and no source was found for it. **What resolves it**: a cited
  public source, or the owner's accountant, stating the treatment of contract income
  received outside the ФОП account. **Until then**: a stream declaring a non-ФОП destination
  and naming this regime MUST be refused as a typed result naming the destination and the
  regime — never silently charged at these rates, and never silently charged at nothing.]

- **FR-023**: The compulsory sale of foreign currency on the ФОП account MUST be modelled
  with the existing route machinery — a declared leg through a declared channel at a
  declared venue — and this feature MUST introduce no new leg kind, no new channel kind and
  no new concept of compulsion. ⚙ Preferred because the compulsion changes nothing about
  what the conversion *costs*: a forced conversion and a chosen one price identically, and
  the only thing compulsion changes is which routes exist, which is already what a declared
  route registry says. The accepted limitation is that the data then records *that* only one
  route leaves the account and not *why*; if a later feature needs to distinguish "nobody
  declared a route" from "the law forbids one", that is 003's deficit vocabulary being
  extended, not a new mechanism here.
- **FR-024**: The second spread — converting hryvnia back to dollars on a card — MUST NOT be
  modelled as anything new. It is the return half of the round trip feature 002 already
  requires and required test G6 already pins: a one-way figure may never be presented as a
  round-trip one. This feature's obligation is to not accidentally present the sale's
  one-way cost as the whole cost.

### Key Entities

- **Tax regime** — a declared, identified treatment an income stream can name: its
  components, their dated rate schedules, its periodic obligations, its variant, and its
  reporting cadence. The stream-side counterpart of feature 006's instrument tax classes.
- **Regime component** — one separately named charge on the regime's base, with its own
  dated rate schedule and its own provenance. Єдиний податок and військовий збір are two of
  them; nothing in the engine knows either name.
- **Periodic obligation** — an amount owed per elapsed period rather than per unit of
  income: its period, its dated schedule of statutory amounts, and its exemption rule. ЄСВ
  is the instance; the shape is the law's, not ЄСВ's.
- **Period exemption declaration** — the owner's per-period statement of the fact the
  exemption turns on, and the cited rule it satisfies. The thing a constant zero cannot be.
- **Regime variant** — which of a regime's alternative rate sets applies (VAT payer or not).
  Declared per owner without a citation; the rates of every variant are curated and cited.
- **Tax treatment reference** — the field on an income stream naming its regime, replacing
  the retired scalar. Naming none is a permitted and meaningful state.
- **Credit-date base** — the record of the base being struck: the credited foreign amount,
  the credit date, the official rate applied and the resulting hryvnia figure (feature 011's
  conversion record, consumed unchanged).
- **Base-versus-received difference** — the reported gap between the hryvnia the base implies
  and the hryvnia the sale produced, labelled as outside the taxable base and signed in
  whichever direction it fell.
- Reused unchanged: the income stream, cadence and deployable-capacity records of feature
  002; the tax charge and provenance records of feature 001; the dated rate schedule of
  feature 006; the official-rate series and conversion of feature 011; the routes, legs and
  channels of features 002 and 003.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A month's foreign-currency income charged under the regime produces a hryvnia
  base and two component charges that match independently hand-computed arithmetic within
  the single project tolerance, with the arithmetic recorded alongside the check. (FR-005,
  FR-007, FR-011)
- **SC-002**: The two components are separately named in 100% of outputs, each naming its
  own rate, cited source and verification date; no output anywhere reports a blended
  percentage; and no component name appears in source code as a branch. (FR-005, FR-006,
  FR-001)
- **SC-003**: A projection straddling 1 January 2025 charges no levy before it and 1% from
  it, in one run, matching a hand-computed worked example. Income dated before the earliest
  schedule entry produces a typed error naming the component and the date, and no test
  passes by charging zero. (FR-008)
- **SC-004**: A legislated change to either component is entered as one dated entry in a
  data file with zero source lines changed, and takes effect in the next run. (FR-007)
- **SC-005**: Every deployable-capacity behaviour feature 002 asserts still holds after the
  scalar is retired: the undeclared case yields a result with no net field, the reason names
  the missing declaration, and no net figure quietly equals a gross one. (FR-015, FR-016)
- **SC-006**: A stream naming an unknown treatment fails at load naming the file, the stream
  and the treatment; across a battery of broken regime files — negative rate, unordered
  schedule, duplicate effective date, duplicate regime id, unknown component field — every
  case names the file and the field and no case substitutes a default. (FR-017, and 006's
  FR-003)
- **SC-007**: No tax rate consumed by this feature appears in per-owner data, and every one
  in curated data carries source, retrieval date and verification date — checked by the
  provenance gate rather than by reading. (FR-002, FR-003)
- **SC-008**: With any rate or official-rate observation left unverified, 100% of charges
  derived from it carry the unverified mark, and no derived figure appears unmarked.
  (FR-003)
- **SC-009**: For one credited amount, the hryvnia received and the hryvnia base are two
  separately reported figures; recomputing with the sale executed at a different market
  rate leaves the base bit-identical; and the difference is reported with the
  not-part-of-the-base label on its face. (FR-012, FR-013)
- **SC-010**: A year in which some months are exempt and others are not produces a
  per-month answer: exempt months report nil citing the exemption rule, non-exempt months
  without a declared amount produce a typed refusal naming the month, and no single constant
  can reproduce the result. A month with zero income evaluates the obligation regardless.
  (FR-019, FR-020, FR-021)
- **SC-011**: No representation anywhere in the system expresses the periodic obligation as
  a rate on income, and no exempt month's nil is indistinguishable from an absence.
  (FR-019, FR-021)
- **SC-012**: A second synthetic regime with a different component set, different schedules
  and a different periodic obligation produces complete results with zero lines of source
  code changed. (FR-001, SC-002's no-branch clause)
- **SC-013**: A stream declaring a non-ФОП destination while naming this regime is refused
  as a typed result naming both, in 100% of cases, until FR-022's clarification is answered.
  (FR-022)
- **SC-014**: The compulsory sale's cost is produced by the existing costing path with no
  new leg kind, channel kind or cost mechanism introduced; the return conversion appears
  only as the existing round-trip figure; and no output presents the sale's one-way cost as
  the whole cost. (FR-023, FR-024, required test G6)
- **SC-015**: `docs/METHODOLOGY.md` gains the regime's charge formula, the periodic
  obligation's definition, and a worked example of each, in the same change that implements
  them — verified by that change's own diff. (constitution's documentation clause)

## Assumptions

- **The owner's own facts are declarations, not observations.** That he is a ФОП of the
  third group, that he is not a VAT payer, that an employer paid his ЄСВ in a given month —
  these are statements by the only person who can make them, declared as per-owner data with
  no citation, exactly as his salary is. Every **legal** value they select is curated and
  cited.
- **Retrieved is not verified.** Every rate, date and rule below the table above enters with
  its citation, its retrieval date (2026-08-23) and an empty verification date until the
  owner checks it against the primary text. The hand-computed worked examples run on
  clearly-labelled **synthetic** amounts, rates and dates, following the precedent of 001,
  006 and 007: they test the engine's arithmetic, not Ukrainian tax law.
- **The stream data is wrong today and is being corrected elsewhere.**
  `data/streams/owner-001.toml` declares `contract_usd` as arriving at `coinbase`, which is
  not where it arrives. That correction is a separate change and is **not** made here; this
  specification assumes a ФОП account venue exists and that the stream points at it. ⚙ A
  personal account as a curated venue follows the precedent already set by `monobank_uah`
  and `coinbase` in `data/venues.toml`; whether curated venues should eventually split
  per-owner is a Principle VII question this feature does not open.
- **Amounts remain the honest placeholder.** The declared stream amounts are zero because
  the owner's real monthly figures have not been stated (`SIMULATOR_SPEC.md` §11 item 3).
  This feature produces zero charges on zero income and does not invent a salary to make an
  example interesting; the examples use labelled synthetic amounts instead.
- **One regime is consumed.** UA, ФОП group 3, non-VAT. The second regime of Story 6 is
  declarable and addressable, not consumed. Residency changes (required test E9) and
  multi-jurisdiction comparison (E8) are later features.
- **No payment timing, no filing.** Liabilities are recorded against their period. When they
  are paid, from what cash, and what happens when there is not enough, is feature 009 and
  required test E7.
- **No delivery surface.** As in every feature so far: results are produced and asserted by
  the test suite.

## Clarifications resolved

Four design questions were settled before the requirements were written, and are argued in
"Design positions this specification is built on" above rather than merely asserted. One
question remains open and is carried as FR-022's `[NEEDS CLARIFICATION]`.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Is ЄСВ a tax rate with a zero value? | **No — a periodic obligation.** Different trigger (a month elapsing, not income arriving), different base (a statutory fixed amount, not a percentage), different exemption rule (employment in that month). A rate-shaped model is wrong the first month income is zero. | FR-019, SC-011 |
| 2 | Can "currently zero" stand in for the exemption? | **No.** The exemption is per month and conditional on a fact about that month; the owner leaving employment mid-year makes some months exempt and others not. The slot is reserved in the shape the law has, and the nil is an output. | FR-020, FR-021, SC-010 |
| 3 | Does `IncomeStream.income_tax_rate` survive? | **Retired.** A scalar cannot carry two components with different commencement dates, a fixed-amount obligation, or a per-month conditional exemption. The stream names a treatment, as 006's instruments name tax classes — the inconsistency 006 left behind. The relocation also moves legal rates out of uncited per-owner data, which sharpens Principle VII's boundary. | FR-002, FR-015…FR-018, SC-005, SC-007 |
| 4 | Which hryvnia figure is the taxable base? | **The credited dollars at the official rate on the credit date**, and the hryvnia the sale produces is a different number at a different rate on a different date. Both are reported; the gap is labelled as outside the base; nothing nets them. | FR-011…FR-014, SC-009 |
| 5 | What if the income is credited outside the ФОП account? | **Open** — a legal question, not a modelling choice. The specified behaviour in the meantime is a refusal naming the destination and the regime. | FR-022, SC-013 |

## Owner verification tasks

Five facts that were cited but not verified, or not obtainable at all. Each is recorded as a
task, never filled with a guess; the affected values carry empty verification dates and the
mark propagates until the owner closes them.

1. **The statutory ЄСВ monthly minimum-contribution amounts and their effective dates.** Not
   supplied and not guessable. Until they arrive the obligation resolves to nil through the
   declared exemption and the amounts are never reached; the first non-exempt month refuses
   (FR-021).
2. **The verbatim text of частина шоста статті 4 Закону України № 2464-VI**, and whether its
   condition can be satisfied for part of a month. `zakon.rada.gov.ua` renders statute text
   client-side and no verbatim quote was retrievable on 2026-08-23.
3. **The primary Tax Code article for the 5% єдиний податок rate, and the date it took
   effect.** The rate is cited to a secondary source (zaxid.net) that establishes it is in
   force, not when it began. FR-009 specifies the consequence: the entry is dated from what
   the citation supports and earlier income refuses.
4. **Whether any deduction reduces the base under this regime** — the conversion spread in
   particular. FR-014 applies none and records the absence; a cited answer either way closes
   it.
5. **Confirmation that the two component rates and the 1 January 2025 commencement are still
   current**, read against the Tax Code rather than against news coverage. The
   business.diia.gov.ua page returned only its title to automated retrieval and the
   oschadbank.ua page a redirect loop, so of the three supplied sources only zaxid.net was
   read in full.

## Required tests this feature relates to

- **E10** (*a rate declared as a dated schedule changes on its effective date*) is closed by
  feature 006 on instrument tax classes. This feature is the first to exercise the same
  mechanism on **income**, against a real statute with a real commencement date, and the
  landing change should record that second exercise beside the row rather than re-flipping
  it.
- **E8** (*the same scenario under jurisdiction A vs B differs only in the tax terms*) is
  **not closed**: only one regime is consumed. Story 6 and SC-012 are its structural
  prerequisite — proving a second regime is a data-only addition — and the row stays
  unflipped.
- **E7** (*tax paid from cash in the following tax year*) is **not closed** and is not
  attempted; FR-004 declares the cadence 009 will need and stops there.
- **F1** is **not** closed by this feature either, and the reason is worth stating because
  it is easy to assume otherwise. F1 is about a *position* flat in USD across a devaluation
  posting a taxable UAH gain. What this feature produces is a different asymmetry: a base
  fixed at the credit-date official rate against hryvnia received at a market rate on the
  sale date, with no holding period and no cost basis anywhere in it. Both come from the
  same conflation this project exists to refuse, and they are not the same test.
- Per the constitution, every behaviour above lands with a hand-computed worked example
  (SC-001, SC-003), load-failure coverage (SC-006), refusal coverage (SC-010, SC-013), and
  propagation checks (SC-008). SC-002's no-branch clause and SC-012's data-only claim are
  `contract` tests, being compliance statements about Principle II.

## Out of scope

Named explicitly so the plan does not drift into them: funding-route modelling of any kind,
which features 002, 003 and 004 own (FR-022); any new leg kind, channel kind or cost
mechanism for the compulsory sale (FR-023); the official-rate machinery itself, which is
feature 011 and is consumed here unchanged; correcting `data/streams/owner-001.toml`, which
is a separate change; the owner's real income amounts; payment timing, filing deadlines,
declarations and the cash movement that settles a liability (feature 009, required test E7);
loss carryforward; a second jurisdiction or a residency change (E8, E9); the VAT-payer
variant's rate, which is not cited and is not entered; the general system and the other ФОП
groups beyond being declarable; employment income and the personal-income levy that
feature's own rates would need (FR-010); crypto tax scenarios; the display-currency switch;
the decision layer and candidate generation; and the web and command-line interfaces.
