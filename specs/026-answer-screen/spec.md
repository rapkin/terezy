# Feature Specification: The answer, on the home page, in one visual language

**Feature Directory**: `specs/026-answer-screen`

**Feature Branch**: `spec/026-answer-screen`

**Created**: 2026-09-06

**Status**: **Planned** — both clarifications answered by the owner on 2026-09-06
(`specs/decisions/2026-09-06-clarify-026.toml`). Q1 named the venue vocabulary, so `tasks.md`'s last
phase is unconditional. Q2 rejected all three offered options with a fact about the owner's broker
account, which moved the question into the engine: **implementation may not start until
`fix/undeployed-remainder` is on `main`**, because until then `reaches` does not yet carry the
remainder that FR-016 renders as one figure.

**Input**: `/` becomes the answer to the owner's declared question, drawn in the visual language he
chose on 2026-09-06: one muted hue per entity kind, tinted icon tiles, one badge system, three
horizon columns of non-dominated cards over folded groups. 021's data browser moves to secondary
navigation.

**Zero engine changes.** Owner constraint, 2026-09-06, taken against adding the fields the screen
wants to 020 first: the screen is what tells him whether the answer's shape is right, and waiting on
the shape to settle would invert that. It renders from what `/api/questions/{id}/answer` serves
**today**; a field it wants and does not get is a named state on the screen and an obligation listed
against 020 — never a blocker here and never a blank. **One exception, and it is a declaration rather
than a branch**: FR-007's venue `kind`, which is data plus the closed vocabulary that refuses an
unknown one.

The constraint survives Q2's answer, which is an engine change this feature does not make. The
undeployed remainder rides the declared exit route home and arrives inside `reaches` — branch
`fix/undeployed-remainder`, whose own decision file
`specs/decisions/2026-09-06-undeployed-remainder-returns.toml` is written there and does not exist
yet. 026 renders that served figure and still edits no engine file beyond FR-007.

---

## Why this feature exists

021 put the declared data on a screen and the owner read it: *not very useful and overloaded with
text*. The judgement is about the **shape** of the surface. Every screen 021 builds is a list of
fields, every field looks like every other, and the question the tool exists to answer — *what should
I do with 50 000 ₴* — is on no screen at all. `/` is a category index.

019 produced the honest answer's shape — the non-dominated set, with what separates its members —
and it reaches no reader: the CLI prints it as unrounded floats (`cli-renders-raw-floats`) and the
web client has no route for it. The visual language is the other half. Differentiating entities by
block, colour and icon is not decoration: it is what lets a reader tell a bond from a fund without
reading, which is 021 FR-009's argument for a mark carried in text. Colour carries no claim alone
here either — the icon or the words carry it and the hue distinguishes.

## Decisions already taken

Owner, 2026-09-06, from a three-option canvas. Recorded once against the alternative each was taken
against, and not reopened by planning.

| Decision | Taken against | Why |
|---|---|---|
| **Visual language A — muted categorical**: ink `oklch(40% 0.11 h)`, tint `oklch(94% 0.03 h)` in light, one hue per kind at equal chroma and lightness | saturated solid fills (B), monochrome shapes with one accent (C) | B's `oklch(55% 0.16 h)` makes every entity shout equally, which is the *overloaded* complaint in colour; C carries kind by shape alone and leaves the reader counting corners. |
| Hues: bank 250, exchange 60, broker 300, platform 170, payroll 340, bond 145, fund 200, cash achromatic, held asset 50, income stream 280, spendable endpoint 250 (a pill); 32 px tinted tiles, outline icons on a 24 grid at stroke 1.75 | a palette per screen; filled glyphs | Cash is achromatic **deliberately** — it is the do-nothing baseline and a colour makes it look like a choice. One outline weight reads at 16 px and at 32 px. |
| **One badge system**: unverified/stale amber (021's `--warn-*`), assumption violet (hue 300, new), refusal red (021's `--refuse-*`), owner's statement neutral | a badge vocabulary per screen | 021 owns three of the four; a second definition of a mark is where two of them drift. |
| **Answer screen A — three horizons side by side** | one table with a horizon tab strip (B) | Side by side is the comparison the question asks for; a tab strip makes the cross-horizon reading a memory exercise, and that reading is what a three-horizon question *is*. |

**The language's edge strokes are not built here.** The mockup names transfer / FX / purchase /
redemption; the engine's declared leg vocabulary is `transfer | fx | trade | withdrawal`
(`core/routes/legs.py`) and purchase and redemption are stages of a tuple, not legs. This screen
draws no edges. The graph feature settles it.

## What this feature requires of the API

Numbered from **OB-10**; OB-1 to OB-9 are 021's. Each was measured on 2026-09-06 against the served
document — `GET /api/questions/fifty-thousand-hryvnia/answer?as_of=2026-09-06` over the shipped
`data/`. **None blocks this feature**; each row says what the screen does instead.

| | The obligation | State, as measured | What the screen does |
|---|---|---|---|
| **OB-10** | an answer sized for a screen | unmet: **8.0 MB on the wire**, 4.6 MB of it `dominance.dominated`, because every verdict carries both candidates' merged provenance and staleness | fetches it whole and names the wait (FR-013) |
| **OB-11** | a member's figures beside the member | unmet: `non_dominated` carries five-term keys, the outcomes are in `outcome.comparison.ranked` | joins by key equality (FR-009) |
| **OB-12** | a typed separating assumption per member | unmet: `separating.per_member[].rests_on` is prose the core composed | derives the badge from typed outcome fields (FR-019) |
| **OB-13** | the whole stated amount as one figure, and a verdict saying whether the remainder made it | unmet today, and **the one obligation that blocks implementation**: `fix/undeployed-remainder` is what meets it — served `reaches` then includes the remainder, and the record says whether it came home or could not | renders `reaches` as received (FR-016); renders FR-010's named state where the verdict says it did not (FR-017) |
| **OB-14** | the declared class on every instrument read, **as a closed enumeration** | unmet three ways: absent from the answer, dropped for a fund, and `str` rather than a `Literal` where it survives — so no client can be made red by widening it | keys exhaustiveness on the read's tag and renders an unnamed class raw (FR-006) |
| **OB-15** | a venue's declared kind | unmet; **this feature declares it** — the vocabulary is the owner's, answered 2026-09-06 | nothing here draws a venue; it binds the language, not the screen (FR-007) |
| **OB-16** | a section's span range, and that each rate is annualised over its own span | unmet: `cli/main.py` composes it from each row's `span` | states the condition and no derived figure (FR-014) |
| **OB-17** | a remedy on an undeclared subject | unmet: `answer.UndeclaredSubject` carries only the word the owner wrote | composes the remedy from a checked map (FR-021) |
| **OB-18** | the three populations, tie groups, `beats_benchmark`, the benchmark index, every refused and withheld candidate with its typed reason | **met**, all of it, per section | renders it |
| **OB-19** | which mark belongs to which figure | partly met: `reaches` is `Money` with its own provenance, `implied_rate` a bare `NominalRate` | a rate wears the outcome's merged mark and says so |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — He opens the tool and reads the answer (Priority: P1)

The owner opens `/` and sees his question in words, the date it was answered as of and which
instrument is the benchmark; then three columns, one per declared horizon, each headed by whether its
rows are comparable at all and by where the benchmark stands in **that** section, holding the
candidates nothing dominates.

**Why this priority**: it is the feature; everything else refines this screen. **Independent Test**:
run the API over the shipped `data/`, open `/`, read the columns' ids against `non_dominated`.

**Acceptance Scenarios**:

1. **Given** the shipped registry, **When** `/` loads, **Then** each column's cards are exactly that
   section's non-dominated members, in the API's order, and no card the API did not send.
2. **Given** a section whose rows span different lengths, **When** the column renders, **Then** the
   comparability banner heads that column and is visible without scrolling.
3. **Given** a section whose **survey** refused, or whose dominance pass did, or whose comparison has
   no benchmark, **When** the column renders, **Then** that typed refusal is on screen with its reason
   and no card is shown — a failed section is a section.
4. **Given** the benchmark, **When** a column renders, **Then** that section's standing is in the
   API's own vocabulary — *nothing dominates the hurdle*, or dominated and by how many — and the
   header names the instrument without asserting one standing across three sections.

---

### User Story 2 — Every card says what it is, without being read (Priority: P1)

Each card carries a tinted tile for its instrument's declared class and one badge naming the
assumption that separates it from its neighbours.

**Why this priority**: two cards showing different numbers for reasons a reader cannot see is a
comparison of two different questions presented as one. **Independent Test**: render each
separating-assumption variant and each kind against fixtures; assert the tile and the badge.

**Acceptance Scenarios**:

1. **Given** a member sold at the horizon's end, **When** its card renders, **Then** the badge says
   so, and one whose own terms closed it says something else.
2. **Given** a separating assumption the client has no label for, **When** the card renders, **Then**
   the raw tag is displayed — never a blank badge and never no badge.
3. **Given** two cards of different instrument classes, **When** both render, **Then** their tiles
   differ in icon **and** hue, and stripping every style declaration leaves the kind readable as text.
4. **Given** a card, **When** its figures are read, **Then** each is the figure the API returned,
   formatted as money, percent or date, and no unrounded float appears in the document.

---

### User Story 3 — What was left out is one line, not a wall (Priority: P2)

Below each column's cards, two folded rows: the full ranking, with the benchmark row tinted and tie
groups shown; and the refused, withheld and no-candidate rows grouped by their typed reason with a
count each. What every shown member rests on is stated once for the screen.

**Why this priority**: the *overloaded with text* complaint answered directly. Nothing is removed —
removing it would be the silent exclusion 010 refuses — it is folded and counted. **Independent
Test**: open `/`, count the belief text's occurrences, expand each group against the API's populations.

**Acceptance Scenarios**:

1. **Given** 26 pairs that yielded no candidate for one typed reason, **When** the row is folded,
   **Then** it is one line with a count of 26 and an expandable list of the ids.
2. **Given** the shipped answer, **When** `/` loads, **Then** the early-exit belief appears exactly
   once and each card leaning on it carries a mark rather than a copy.
3. **Given** the full ranking expanded, **Then** the benchmark row is marked as the benchmark in
   **text** and every tie group is shown as a group.
4. **Given** `cash` and `btc`, **When** the header renders, **Then** each is a refusal carrying the
   remedy *a declaration* and what would supply it — never blank space.

---

### User Story 4 — The browser is still there, and is no longer the front door (Priority: P3)

Everything 021 built stays reachable under a secondary navigation entry.

**Why this priority**: the risk in a navigation change is losing a screen rather than gaining one.
**Independent Test**: 021's whole-UI crawl, extended to `/`, reaches every route it reached before.

**Acceptance Scenarios**:

1. **Given** the app, **When** any 021 route other than `/` is opened directly, **Then** it renders
   as it did, with `as_of` carried the same way; the category index renders at its new path.
2. **Given** `/`, **When** the API is unreachable, **Then** 021's named error state renders (its
   FR-006) — never an empty column and never an unresolved spinner.

---

### Edge Cases

- **An empty non-dominated set.** Legitimate — every pair incomparable places nobody — and rendered
  as the API's own member count, never as a column that failed to load.
- **A member whose rate is `RateNotComparable`.** The amount is real and the rate is not: the rate
  slot renders the typed refusal and the card stays.
- **A remainder in a currency `reaches` is not in.** It cannot join the headline — no exchange rate is
  consulted anywhere here — so the served record says it did not come home and the card says so beside
  the figure (FR-017), never by leaving the headline to stand for the whole amount.
- **A section with more members than fit.** Measured: 2, 3 and 10. A count and a disclosure, never a
  client-chosen truncation.
- **`NoStatedAssumptionSeparatesThem`.** Rendered as what it is — *the same beliefs are behind all of
  them* — never an empty badge row.
- **A `non_dominated` key no ranked outcome matches.** Impossible today and not assumed away: a named
  state carrying the key, never a card with empty figures.

## Requirements *(mandatory)*

### The visual language

- **FR-001**: The kind palette MUST be design tokens in one place, one hue per kind at equal chroma
  and lightness, with the dark pair derived the way `web/src/styles.css` derives every colour — each
  value once, in `light-dark()`.
- **FR-002**: A kind's tile MUST carry an outline icon **and** the kind as text (visible or
  accessible). Hue MUST NOT be the only carrier — 021 FR-040 applied to a tile.
- **FR-003**: The badge vocabulary MUST be exactly four tones — mark, assumption, refusal, owner's
  statement — reusing 021's `--warn-*` and `--refuse-*` tokens rather than declaring second copies.
  **The assumption tone's hue 300 is the broker kind's hue**, which this screen never draws; the two
  first meet in the graph feature, and settling which moves is that feature's — recorded here rather
  than discovered there, because a badge and a tile in one colour is the one thing *one hue per kind*
  exists to prevent.
- **FR-004**: The kind → hue map MUST be exhaustive over the declared vocabulary it keys on — a kind
  the API sends that it does not name fails the typecheck, asserted by a test enumerating the map
  against that vocabulary — and MUST NOT be keyed by a category id, a record id or a file path (021
  FR-015's scan already fails on the first).

### Where an entity's kind comes from

- **FR-005**: The client MUST NOT infer an entity kind from an id, a name, a file path or a prefix.
  An income stream and a spendable endpoint are the exception that proves it: each is one kind by what
  it is — being listed in `data/spendable/` is the whole claim — and no field is added for either.
- **FR-006**: An instrument's kind MUST come from the instrument read, and from **two** fields rather
  than one — only one of which is closed. Measured 2026-09-06: a bond answers
  `interface.InstrumentDeclaration` carrying `instrument_class`, and a fund answers
  `fund.FundDeclaration` carrying **none** — the class is consumed at load and dropped
  (`core/instruments/fund.py`). So the read's own **tag** decides bond-shaped from fund-shaped, and
  that is the vocabulary FR-004's exhaustiveness runs over: it is a literal union in the document.
  `instrument_class` is **not** — it is `str` on the core record (`core/instruments/interface.py`)
  and `string` in the generated document — so a class the map does not name renders **raw** (FR-019's
  rule, applied to a kind) and never as nothing. Both halves are OB-14.
- **FR-007**: A **venue's** kind MUST be a declared field. Measured 2026-09-06 `data/venues.toml`
  declares `id`, `name`, `currencies` and nothing else, while `core/routes/venues.py`'s docstring
  names the taxonomy in prose. So this feature adds a declared `kind` — a closed vocabulary in
  `core/`, refused at load by the `_known` mechanism every other closed field uses, naming file and
  field — rather than a client-side guess. The vocabulary is exactly five, owner 2026-09-06: `bank`,
  `exchange`, `broker`, `platform`, `payroll`. **Every shipped venue carries one**; the three the
  owner did not name himself are assigned in the decisions file so a wrong one is corrected there
  rather than found in a diff.

### The answer over HTTP

- **FR-008**: The screen MUST compute no displayed figure the API did not send, MUST NOT order a
  population the API ordered, MUST NOT derive a field to order by, and MUST NOT select which members
  to show. `/api/registry` MUST NOT be fetched for this page: it is 2.6 MB and nothing here reads it.
- **FR-009**: Joining a `non_dominated` key to its outcome by key equality, counting a population the
  API sent, and grouping its members by the typed fields they carry are **lookups over served data**
  — permitted, and named so they are not mistaken for FR-008's arithmetic. Every count MUST be
  checkable: the members it counted are reachable in one interaction.
- **FR-010**: A field the response does not carry MUST render as a named state saying which field is
  missing. Never a blank, a zero, a dash, or a card with an empty slot (021 FR-008).
- **FR-011**: The header sentence MUST be a template over typed fields the API returned — **every**
  amount in `question.amounts` with the stream it leaves, the subjects as the owner named them, the
  horizons, the benchmark id, `as_of` — every figure in it rendered as received. Measured 2026-09-06
  there are **two**: 50 000 UAH from `salary_uah` and 1.00 USD from `contract_usd`, and the second is
  the stream every one of the folded no-candidate refusals names, so a header showing one amount hides
  the reason for the largest refusal group on the screen. Composing a **sentence** from typed values is what the CLI already does
  over the same record; composing a **figure** is not.
- **FR-012**: Each column MUST show its section's population counts — non-dominated of ranked,
  beating the benchmark, refused, withheld, no-candidate, **not-placed, incomparable pairs and
  indistinguishable members** — and its own `benchmark_standing`, which is a section-level fact and
  MUST NOT be summarised into one header claim. Each expanded row MUST hold exactly the members its
  count counted. `outcome` is a **nine-member** union and `comparison` a two-member one, so a section
  whose survey refused, or whose comparison has no benchmark, MUST render that member's own reason
  rather than an empty column. `sections[].standings` and `sections[].reserves` MUST be rendered too: a standing is
  per named subject and a reserve verdict is a typed refusal, and neither has a count to hide behind.
  Nothing the API reports is left uncounted — measured 2026-09-06 the one-month section reports **4**
  indistinguishable members, and dropping them is Principle I's *report the range* broken at the last
  step.
- **FR-013**: Fetching the answer MUST have a named loading state and a named failure state. At
  OB-10's measured size that is a wait a reader must be able to tell from a hang.

### The column head, and the card

- **FR-014**: Where a section's rows were measured over spans of **different length**, a comparability
  banner MUST head that column and be visible without scrolling. It states the condition and its
  consequence — each rate is annualised over its own span, so rates are not comparable across rows —
  and **no derived figure**: the span range the CLI composes is OB-16, and a second client composing
  the same sentence is where two readers get two answers. Each row shows its own span.
- **FR-015**: A card MUST carry, in this order: the instrument's kind tile and id; *money back*; *all
  of it by*; the rate; **one** badge naming the separating assumption; and, where the member is
  `indistinguishable` from others, that fact with them named — the honest form of *these score within
  noise*, without which a set of cards reads as an ordering. Every figure slot MUST be 021's
  `FigureSlot` in one of its three states, so a refused rate and a marked amount already have
  somewhere to go.
- **FR-016**: *Money back* MUST be **one** figure — the served `reaches` for the candidate, rendered
  as received — and the client MUST neither add to it nor subtract from it. Measured 2026-09-06, before
  the fix, a one-month member reached **49 760.50 ₴** against 50 000 ₴ asked while reporting
  **+10.99 %**, because `reaches` was measured on what was deployed (whole units × price) and the
  remainder — 494.68 ₴ — was a separate field nothing brought home. The owner's answer was that his
  remainder *can* come home, so the engine brings it: it rides the declared exit route to a spendable
  endpoint, arrives inside `reaches`, and its arrival is what *all of it by* counts. **What that route
  charges it is the fix's to declare and cite** — the owner's statement that his own withdrawal costs
  neither fee nor tax is his account, not a fee value this spec may settle by inference.
- **FR-017**: The card MAY show, **on expansion**, the served `UndeployedCash` record beside
  `reaches` — its amount, the venue it was at, and the constraint that left it over — each figure as
  served. It MUST NOT compute the deployed part: `reaches` less the remainder is a figure the API does
  not send, which is FR-008 and not an exception to it. Where the served record says the remainder
  **could not** come home — the cross-currency case the *Edge Cases* name, since no rate is consulted
  anywhere here — the card MUST render FR-010's named state saying so, because a headline that quietly
  omits it is FR-016's measured defect back again. `undeployed` is `null` for a purchase that deployed
  everything — the ordinary whole-unit case, rendered as *nothing left over* and never as FR-010's
  missing field.
- **FR-018**: The screen MUST state **once** that a rate is measured on the money actually invested.
  Without it the rate is non-monotonic against *money back* across rows of equal span, and a reader
  takes the disagreement for an error.
- **FR-019**: The separating assumption MUST be derived from **typed** facts on the member's outcome —
  whether the position was sold at the horizon's end, or its own terms closed it inside the window
  with the proceeds sitting as cash under the declared continuation assumption — never by matching a
  sentence. Those two are the whole vocabulary the shipped data reaches; the plan says why the
  mockup's three labels are two conditions. The vocabulary MUST be
  closed and rendered exhaustively; a tag with no label renders **raw**, never blank and never absent.
- **FR-020**: An assumption every shown member of a section rests on MUST be stated **once per
  screen**, not on a card. 019 already separates the two: `separating.per_member[].rests_on` is what a
  member does **not** share, and what its outcome's `rests_on` holds beyond that is shared — as are
  the plan's choices, the consumption method, the coupon policy and the continuation assumption.
- **FR-021**: A subject the registry declares nothing by MUST render as a refusal carrying the remedy
  — *a declaration* — and what would supply it. The map from a subject word to that feature MUST live
  in one place, with a test that every undeclared subject the shipped answer reports has an entry, so
  a third one fails a test rather than rendering blank. The remedy belongs on the record (OB-17).

### Text, formatting, and what is folded

- **FR-022**: Refusals, withheld candidates and no-candidate pairs MUST be grouped by the **typed
  discriminants their members carry** — the tag and the typed fields other than the id of the thing
  refused — with a count per group and an expandable list of ids, never by matching reason text.
  Measured 2026-09-06, 26 `PairYieldedNoCandidate` rows share `(NothingConnects, route_in,
  contract_usd)` and differ only in the instrument id inside each reason's own sentence.
- **FR-023**: A group MUST collapse to one line carrying its typed reason, expandable to each member's
  own fields and full reason. Never to a count alone, and never to a blank.
- **FR-024**: The early-exit belief MUST be stated once per screen per distinct belief id, with a link
  to the full statement. A card leaning on it carries a mark, not a copy.
- **FR-025**: Long provenance text — a citation, a rationale, an exclusion's own words — MUST render
  behind a disclosure and be reachable in full. Eliding it to a fixed length is 021's *Edge Cases*
  prohibition, unchanged.
- **FR-026**: Formatting MUST live in **one** module — money to the kopeck with thin-space grouping in
  the currency the API returned it in, a rate as a percent to two decimals, a date as the API's ISO
  date rendered `4 Oct 2026` — with the precision stated there once and imported. That precision is a
  **rendering** precision and never a comparison tolerance: nothing here compares two figures for
  closeness, because `ties` and `beats_benchmark` are the engine's, struck at the project tolerance.
  A raw float reaching the document is a defect, asserted over the rendered page rather than over the
  formatter. This closes the **web** half of `cli-renders-raw-floats`; the CLI is untouched.

### Accessibility, navigation, and tests

- **FR-027**: 021's accessibility requirements (its FR-038 to FR-043) apply unchanged: keyboard reach
  with visible focus, WCAG 2.2 AA contrast in **both** themes — including every ink-on-tint pair the
  palette produces — and no information carried by colour alone. Every disclosure is keyboard-operable.
- **FR-028**: `/` becomes the answer, which changes what one path means — 021's category index lives
  there today. That index moves to its own path under the browser's prefix and is reachable from a
  secondary navigation entry. **Every other 021 route keeps its path and its meaning**, no route is
  removed. There is **no redirect from `/`**, and that is the honest reading rather than an omission:
  `/` now serves the answer, so a redirect there would send every visitor to the browser and defeat
  the feature. A bookmarked `/` reaches the answer — a change of meaning stated here rather than
  discovered.
- **FR-029**: Unit tests MUST cover each card state — value, marked, refused — each
  separating-assumption variant, each kind tile, each grouped-refusal shape and the number formatting,
  against mock handlers typed from the same document (021 FR-044).
- **FR-030**: An end-to-end scenario MUST run against the real API over the shipped `data/` and assert
  that the three columns' members match the API's `non_dominated` by count and by id, that the belief
  text appears exactly once, and that no unrounded float reaches the document. 021's whole-UI crawl
  extends to `/`.

## Success Criteria *(mandatory)*

- **SC-001**: The three horizons are on one screen with no navigation, and each column's members equal
  the API's `non_dominated` for that section by count and by id.
- **SC-002**: 100% of kinds the API can send have a hue, an icon and a word, asserted by a test
  enumerating the map against the declared vocabulary.
- **SC-003**: Zero unrounded floats reach the document, asserted over the rendered page.
- **SC-004**: The early-exit belief appears exactly once; each card leaning on it carries a mark.
- **SC-005**: Every population the API reports is reachable in one interaction from its column, and
  none is dropped.
- **SC-006**: 26 no-candidate rows of one typed reason render as one line and one count, and expanding
  it yields 26 ids.
- **SC-007**: A section whose rows span different lengths shows the banner above the fold, asserted
  end to end. The negative half — equal spans show no banner — is a **unit** assertion against a
  fixture, because measured 2026-09-06 all three shipped sections have rows of differing span, so an
  end-to-end negative would pass by asserting nothing.
- **SC-008**: The home page issues no request for `/api/registry`.
- **SC-009**: The accessibility check reports zero AA violations on `/` in both themes.
- **SC-010**: `web/src` derives no entity kind from an id, a name or a path.
- **SC-011**: Every screen 021 built is reachable after this feature; the only path whose meaning
  changes is `/`, and the index that lived there is reachable at its new path.

## Clarifications

Both answered by the owner on 2026-09-06; the questions as asked, the options offered and his words
are in `specs/decisions/2026-09-06-clarify-026.toml`. What is here is what each answer changed.

**Q1 — Is the venue `kind` vocabulary the owner's to name?** Yes, and it is the mockup's five:
`bank`, `exchange`, `broker`, `platform`, `payroll` — closed, in `core/`, an unknown one refused at
load. Every shipped venue carries one, six of them named by the owner and three assigned in the
decisions file for his correction. FR-007 and `tasks.md`'s last phase are unconditional.

**Q2 — What does a card call *money back*?** None of the three options, because all three assumed the
remainder stays where it was bought. It does not: the owner's account of his own broker account is
that he can withdraw it back to his bank without fee or tax, so the defect was in the engine rather
than in the rendering. The remainder rides the declared exit route home and arrives inside `reaches`
— branch `fix/undeployed-remainder`, which writes
`specs/decisions/2026-09-06-undeployed-remainder-returns.toml` and prices what that route charges.
*Money back* is therefore **one served figure**, with the served remainder record on expansion —
FR-016 and FR-017 — and the client neither adds nor subtracts. **That fix must land on `main` before
this feature's implementation starts**, because until it does `reaches` is the deployed part alone.

## Out of scope

- **The interactive graph** — entities as nodes, routes as edges, a candidate's path lit on selection.
  A later feature; it needs the edge-kind mismatch settled, and a `[[future]]` entry tracks it.
- **The display-currency switch.** Deferred by owner decision 2026-09-03, unchanged here.
- **Cash and BTC as subjects.** 023 and 025. Until they land they are refusals with their remedy
  (FR-021), which is what the answer already says in typed form.
- **Editing the question.** A declaration is changed in git and reviewed like code.
- **Restyling the 021 browser.** The tokens land here; applying tiles and hues to the record card and
  the category index is a separate change with its own scan to satisfy (FR-004).
- **Naming the assumption that *decides* between two members.** 019 FR-021 refuses it; required test
  I5 is its feature. This screen shows what the members do not share.
- **Any change to `src/terezy/`** beyond FR-007's venue `kind`. Owner constraint, 2026-09-06.

## Assumptions

- 019 and 021 are `done` on `main`; 020 publishes the document this client generates from. **OB-13 is
  the one obligation that blocks implementation**, and `fix/undeployed-remainder` is what meets it;
  every other obligation OB-10 to OB-19 is a named state on the screen rather than a blocker.
- The routing constraint 021's *Assumptions* stated — `/question/:id` and `/compare` fit under the
  same router and the same search parameters without restructuring — is what this feature spends.
- `as_of` is 021's, unchanged: typed, validated, in the URL on every route, one clock read.
- The screen shows **one** declared question. Which one, when there are two, is a later question.
