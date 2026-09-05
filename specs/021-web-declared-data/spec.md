# Feature Specification: The declared data, on a screen that can refuse

**Feature Directory**: `specs/021-web-declared-data`

**Feature Branch**: `spec/021-web-declared-data`

**Created**: 2026-09-03

**Status**: **Clarified** — the three clarification markers this spec shipped with are answered by
the owner on 2026-09-03 and recorded in `specs/decisions/2026-09-03-clarify-021.toml`: **English only**; the
display-currency selector is **moot**, because the switch itself is deferred; and the owner's own
declarations **are shown**, each labelled as his statement rather than as an observation.

The second is not an answer to the question as asked, and the difference is load-bearing. Q2 asked
what a selector should list; the owner deferred the display switch as a **subject** the same day, on
both sides of the wire, so there is no selector to list anything. Every requirement that rested on
it is in *Deferred by owner decision* below — **moved, not deleted**, so that picking the switch up
later reads a scope rather than reconstructs one.

**One half of that decision is not yet done, and this spec does not pretend otherwise.**
`specs/020-http-api/spec.md` still requires the `display` request parameter (its FR-021 to FR-025,
and its clarification 1 keeps the parameter under either option). Withdrawing them is 020's change;
until it is made, a generated client would carry a parameter this spec has no requirement about,
which is the silent default FR-001 and FR-020 forbid arriving one level up.

**Where the owner decisions this spec cites are recorded.** The stack and the packaging are
`specs/decisions/2026-09-03-web-stack.toml`; the three clarification answers are
`specs/decisions/2026-09-03-clarify-021.toml`. Every appeal to "owner decision 2026-09-03" is
checked against one of those two. The `[[feature]]` entry and the constitution amendment lifting
D-B were drafted in the Appendix and are now **applied** — the entry is in `specs/features.toml`
and the constitution is at 1.4.0.

**Input**: A read-only web client at `web/` for browsing what `data/` declares: categories, a
record card carrying every field with its citation and its mark, and the two declared series as
charts. The client computes nothing. Owner decision of 2026-09-03 lifts the D-B deferral and
fixes the stack.

---

## Why this feature exists

Everything this repository knows is in `data/`, and the only way to read it is to open a TOML
file. That is fine for the person who wrote the file and useless for the question the tool
exists to answer, which is *what does the tool actually rest on, and how much of it has anybody
checked*. `scripts/check_provenance.py` reports every unverified value in the tree as a
per-file count — its own docstring records why it stopped listing them one by one — and a count
cannot say which of them matter. A screen can.

The second reason is the harder one. `docs/DIRECTION.md` names the failure mode of every
interface this project could grow: *"a chart that cannot express 'this figure refuses to exist,
and here is why' is worse than a table that can"*, and *"a tracker's interface has no place to
put a typed refusal, and flattening one into a blank cell is precisely the failure this project
exists to prevent."* The engine's refusal vocabulary is typed, closed and load-bearing. An
interface that renders a refusal as an empty cell throws all of it away at the last step, and
nothing upstream can detect that it did.

So this feature is not "a UI for the data". It is the **first surface on which a mark and a
refusal have to survive being looked at**, built while the only thing on it is declared data —
which is the cheapest possible place to get that wrong and find out.

### Why now, and why read-only

Owner decision **D-B** kept the delivery surface at core + API + CLI *until the result schema
had stabilised against real output*. Feature 015's note in `specs/features.toml` names that
feature as the one that stabilises it, and the owner lifted the deferral on 2026-09-03. The
constitution records the **discharge** (`.specify/memory/constitution.md` at 1.4.0, the D-B entry
and the `web/` layer line): the amendment this spec was written against is applied, and the
Appendix records what it changed and why.

The first thing built on the new surface is deliberately the smallest: browsing declarations
needs no answer, no ranking, no compare, and therefore cannot hide a UI defect behind an
interesting number.

## Decisions already taken

Owner, 2026-09-03. These are recorded here **once**, against the alternative each was taken
against, and are not reopened by planning.

| Decision | Taken against | Why |
|---|---|---|
| `web/` at the repository root, pnpm | a Python-templated server-rendered surface | The client is a client over the HTTP API and nothing else; putting it inside `src/terezy/` would put a build toolchain inside the package that `lint-imports` governs, and would make "the UI may not import the core" a convention rather than a physical fact. |
| Vite + React + TypeScript strict | a no-build-step surface | Strict TypeScript over generated types is the mechanism for FR-004: an unhandled refusal member is a compile error rather than a blank cell. Without a typechecker there is no mechanical form of this feature's central requirement. |
| Tailwind + shadcn/ui, components copied in | a component library as a runtime dependency | Copied components are owned code, reviewed in git, with no vendor's runtime and nothing to phone home. Principle VII's "no CDN calls, no telemetry" is satisfied structurally rather than by trusting a changelog. |
| TanStack Router, with **typed** search params — `as_of` globally, a window on the two series routes | React Router with string params, or client state | A parameter that decides what a figure *means* is in the URL, validated, and shareable. A run is reproducible from a link, which is the same argument that made a question a declaration in 015. `display` was the third and is deferred; the argument is why the router was chosen and does not depend on the count. |
| TanStack Query for all server state | `useEffect` + `fetch` | Caching, retry and staleness of a *request* belong in one place; hand-rolling them per screen is where a stale response silently outlives a parameter change. |
| No client-side store initially — URL + React context | Redux, or MobX from the start | There is no client state yet: everything on screen is a function of the URL and a response, so a store would be a cache of the router and of TanStack Query. Which store to reach for when that stops being true is a standing preference of the owner's and is recorded in `specs/decisions/2026-09-03-web-stack.toml`, not here. |
| Recharts | D3 by hand, or a canvas library | Two series, both simple, both needing an accessible DOM the a11y check can read. |
| `openapi-typescript` + `openapi-fetch` over the checked-in OpenAPI document of feature **020-http-api**, generated types committed, CI regenerating and failing on difference | hand-written response types | A hand-written type is a second copy of the contract, and the drift is silent in exactly the direction that matters: a refusal member added server-side and never rendered. |
| Vitest + React Testing Library, MSW handlers typed from the same document | untyped fixtures | A fixture that has drifted from the contract must fail to compile, not pass. |
| Playwright end-to-end against the **real** API on loopback over the shipped `data/`, offline | a mocked end-to-end run | A mocked E2E proves the mock. The whole claim of this feature is that a mark survives from a TOML file to a pixel, and only the real stack can be asked that question. |

### What this feature does not make possible

It does not put a number on the screen that the engine could not already produce, and it adds
no formula. Every figure it renders is one the API already returns; every refusal it renders is
one a core record already wrote. If the screen shows something new, that is a defect.

## What this feature requires of the API

Stated as obligations rather than assumptions, because a missing one turns a generic screen
into a per-category branch — which would be Principle II broken in a new layer.

- **OB-1** — A category index: what categories exist, how many records each holds, and the dates
  the API chooses to characterise each by. The client hard-codes no category id.
- **OB-2** — A record representation that is *self-describing*: an ordered list of fields, each
  with a label, a value and its type, and, where the value is observed, its citation, its
  `retrieved_on`, its `verified_on` and the observation kind it ages under. Without this the
  client must know each category's schema, and a new declaration kind becomes a client change.
- **OB-3** — The record's declaring file path, so a reader can go and check the thing he is
  looking at.
- **OB-4** — The mark and staleness state of every figure, as the closed vocabulary the API
  already owns, expressed in the document as a closed schema (an enumeration), never as a free
  string.
- **OB-5** — Every refusal expressed as a *tagged* member of a closed union carrying its reason
  and, where the record has one, what would supply it. A refusal encoded as an HTTP status alone
  is not enough: the status says the request failed, and the reason is the deliverable.
- **OB-6** — Whether a record's directory is sourced or exempt from the citation requirement,
  and for an exempt one the reason (`scripts/check_provenance.py` holds both lists, by name,
  fail-closed). See FR-013 for what the screen does with it.
- **OB-7** — For a series: the series identity, **whatever the values are in** — a quotation
  unit where the series declares one, and otherwise its declared base description, which is what
  a price index has instead of a unit (FR-030) — its coverage window, and, for a requested window, the observations inside it **together with** a
  typed refusal for whatever part of it falls outside coverage. Both in one response: a response
  that refuses the whole window makes FR-029 unimplementable, because trimming the window to
  what exists would be a computation the client is forbidden (FR-001, FR-027).
- **OB-8** — A default window per series, stated by the API. The client requests it and never
  invents one; see FR-027a.
- **OB-9** — *Deferred with the display switch.* It asked for the base currency and, per currency,
  whether a converted figure can be supplied; both existed to feed a redirect and a selector that
  are no longer built. Every amount renders in the currency the API returned it in, which needs no
  obligation. Scope: *Deferred by owner decision*.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — He can see what the tool rests on (Priority: P1)

The owner opens the app and sees the categories of declaration the tool loads, each with how
many records it holds. He opens one, sees the records, opens a record, and sees every field it
declares, what each observed value cites, when it was retrieved, whether anybody has verified
it, and the mark that follows from that.

**Why this priority**: it is the feature. Everything else is a refinement of this screen.

**Independent Test**: run the API over the shipped `data/`, open the app, reach a record card,
and read a citation off it that matches the file on disk.

**Acceptance Scenarios**:

1. **Given** the shipped registry, **When** the overview loads, **Then** every category the API
   indexes is listed with what the API reports for it — a count where it is keyed, a resolved
   statement where it is a singleton — and no category is listed that the API did not send.
2. **Given** a record whose `verified_on` is empty, **When** its card is opened, **Then** the
   unverified mark is present as **text**, and the field is not blank.
3. **Given** a record in a directory exempt from the citation requirement, **When** its card is
   opened, **Then** the absence of a citation is rendered as the exemption **with its reason**,
   and never as an empty citation block.
4. **Given** a record with a field the client has no special rendering for, **When** its card is
   opened, **Then** the field is displayed with its raw value rather than dropped.

---

### User Story 2 — A refusal arrives, and the screen says what it is (Priority: P1)

Something the owner asks for cannot be produced. The screen says which thing, why, and what
would supply it — in the words the engine used.

**Why this priority**: `docs/DIRECTION.md` names flattening a refusal into a blank cell as the
failure this project exists to prevent. A surface that gets this wrong is worse than no surface.

**Independent Test**: request a series window outside its declared coverage and read the reason
off the screen.

**Acceptance Scenarios**:

1. **Given** a CPI window running past the last observation, **When** the chart route loads,
   **Then** the refusal is shown with its reason and **no line is drawn** past the coverage —
   never a flat continuation and never an empty chart.
2. **Given** a response carrying a refusal member the client's code does not handle, **When**
   the project is typechecked, **Then** the build fails at the site that does not handle it.
3. **Given** any refusal, **When** it is rendered, **Then** it appears as its reason and as none
   of the placeholders FR-008 names.
4. **Given** the API is unreachable or returns a non-2xx status, **When** a route loads, **Then**
   that is itself a named state on the screen, not a spinner that never resolves.

---

### User Story 3 — The two series, drawn honestly (Priority: P2)

He opens the official-rate series over a window and sees the published rate per date, in the
unit the publisher quotes; he opens the CPI series and sees the same treatment.

**Why this priority**: the series are the only declarations whose shape is a picture, and they
are where a chart's habits — interpolating a gap, carrying a value forward, inventing a unit —
would do damage that a table would not.

**Independent Test**: open each series route with a window and compare the plotted points
against the declaration on disk.

**Acceptance Scenarios**:

1. **Given** a series with a gap between two observations, **When** it is charted, **Then** the
   gap is a break with its own label, never a straight line between the two points.
2. **Given** either routed series, **When** it is charted, **Then** the axis states what the
   values are in **as the API declared it** — the quotation unit for the one that declares a
   unit, the base description for the one that declares a base — and is never bare.
3. **Given** any chart, **When** it is on screen, **Then** the same rows are reachable as a
   table by keyboard, and the table carries each point's mark.
4. **Given** a window whose end is past the series' coverage, **When** the route loads, **Then**
   the in-coverage observations are plotted **and** the refusal for the rest is on screen — the
   two in one view, because a refusal that replaced the chart would throw away what does exist.

FR-031 and FR-031a — a one-observation series, and a retrieval that is not a series at all —
are asserted in the **unit** suite and not here. Neither shape is reachable from either routed
series, and an acceptance scenario no acceptance run can execute is a green box over an
unasserted claim.

---

### User Story 4 — Changing what the figure *means* changes only what it should (Priority: P1)

He edits `as_of` in the URL, and what changes is what that parameter is allowed to change.

**Why this priority**: the staleness verdict is where an interface can corrupt a correct engine
without touching it. Principle VI's three currency roles were the other such place; under the
display deferral the client has no display role at all, which is the strongest form of not
corrupting it.

**Independent Test**: two loads of one record card differing in one search parameter, compared
field by field.

**Acceptance Scenarios**:

1. **Given** a record card, **When** `as_of` moves past a source's staleness threshold, **Then**
   the stale mark appears, and every figure the API returned unchanged renders unchanged. A
   figure the API resolved differently — a dated schedule crossing an `effective_from` — changes
   with it (FR-023a); the client neither suppresses that nor produces it.
2. **Given** an `as_of` the router cannot validate, **When** the route loads, **Then** the
   parameter is named in a visible error and no default is silently substituted.

Two further scenarios named `display` — *"changing `display` leaves every base-role and tax-role
figure byte-identical"* and *"an unmet `display` renders as a refusal"*. Both are in *Deferred by
owner decision*, named there by those descriptions rather than by a number, because the two that
survive have been renumbered and a stale ordinal would now point at a live scenario.

---

### Edge Cases

- **A category with no records.** Rendered as a category with none, with the API's own statement
  of why where it has one. An empty list and an absent category must not look the same
  (`B10`'s reading, applied to a screen).
- **A record whose every field is unverified.** The normal case on the shipped tree, and the one
  a summarising banner is most tempting on. FR-011 settles it.
- **A very long series.** The official-rate series is one observation per calendar day over
  years. The window is bounded by the API and the client requests one; a route that would render
  the whole series must be paged or windowed by the API, never truncated by the client. A
  truncation the client performed and did not state is a silent clamp.
- **A field whose value is itself a citation string** — long, multi-sentence, sometimes carrying
  a legal provision. It is shown in full, not elided to a fixed number of characters with no way
  to see the rest.
- **Two records with the same id in different categories.** The route is
  `/data/:category/:id`; identity is the pair, and the client never assumes an id is globally
  unique.
- **A response field the generated types know and the screen has no place for.** Permitted for a
  scalar (it is displayed generically by OB-2) and **not** permitted for a member of a closed
  union (FR-004).
- **The browser is offline / the API stopped.** A named state (US2 scenario 4). The app is served
  from the same origin as the API, so this is the API being down, not a connectivity story.

## Requirements *(mandatory)*

### The contract with the API

- **FR-001**: The client MUST compute no **displayed** figure. Every number, date, currency,
  unit, mark and refusal reason on screen originates in a response body and is rendered as
  received. Locale formatting of a value the API already fixed is permitted; arithmetic,
  rounding, conversion, aggregation, interpolation and unit changes are not. A **request
  parameter** the client puts in the URL is not a displayed figure. There are **two** of them —
  `as_of` and a series window — and FR-021 and FR-027a each say where its value comes from,
  because a parameter with no stated origin is the silent default FR-020 forbids, arriving one
  level up. `display` was the third and is deferred.
- **FR-002**: The client MAY order a list by a field the API returned, and MUST NOT derive a
  field to order by. An ordering the client computed is a ranking the engine did not make.
- **FR-003**: Response types MUST be generated from the checked-in OpenAPI document of feature
  020-http-api, committed to the repository, and regenerated in CI with the build failing when
  the regenerated output differs from the committed one.
- **FR-004**: Every closed union the document declares MUST be consumed exhaustively, with no
  `default` arm and no fallthrough. A member added to the document MUST fail typecheck at every
  site that does not handle it. This is the mechanical form of *the UI has a place for every
  refusal*; a runtime check is not a substitute, because the case it would catch is the case
  nobody reaches.
- **FR-005**: The client MUST NOT declare a hand-written type for any response body, and MUST
  NOT cast or assert over one. A cast is FR-004 switched off at one site.
- **FR-006**: A transport failure and a non-2xx response MUST each be a rendered state naming
  what failed. Neither may present as an empty list, an empty chart, or an unresolved loading
  state.

### Refusal and mark are first-class values

- **FR-007**: Every component that shows a figure MUST have three states: a value; a **refusal**,
  carrying the engine's reason verbatim and, where the API supplies one, what would supply the
  figure; and a **marked value**, carrying its marks. A component with a figure slot and no
  refusal state does not satisfy this requirement.
- **FR-008**: A blank cell where a refusal belongs is a defect of the top severity class
  (constitution, *Defect severity* — a silent default). So is `0`, `—`, `n/a`, or an empty
  series in that position.
- **FR-009**: A mark MUST be carried in **text**. Styling may add emphasis and may never be the
  only carrier — the assertion strips every style declaration first, the reading
  `tests/contract/test_diagram_marks.py` already applies to diagrams.
- **FR-010**: The mark vocabulary MUST come from the generated types. A mark the API sends and
  the client cannot name MUST fail the build (FR-004) and MUST NOT render as nothing.
- **FR-011**: Marks MUST be per figure. A card-level or page-level banner MAY summarise and MUST
  NOT replace them: a banner is a claim about the page, and the requirement is a claim about each
  number on it.
- **FR-012**: Where the API distinguishes *unverified* from *stale*, the screen MUST too. They
  are different claims and neither implies the other.
- **FR-013**: For a record in a directory exempt from the citation requirement, the absent
  citation MUST render as the exemption with the API's reason for it (OB-6). An empty citation
  block on such a record reads as an uncited observation, which is the exact thing the exemption
  is argued against in `data/README.md`.

### Categories and records

- **FR-014**: The overview MUST list the categories the API indexes, each with **what the API
  reports for it** — for a keyed category its record count, for a singleton **whether its document
  resolved** — and the dates the API characterises it by. A singleton MUST NOT be rendered as a
  count. 020 FR-009 keeps the two apart deliberately: a singleton shown as `0` is the same cell a
  caller would get for a category the loader found nothing in, which is the `B10` distinction
  between *empty* and *absent* collapsing at the one screen whose job is to say what the registry
  holds. Measured 2026-09-03 this is **seven of the twenty-five** categories, so it is the ordinary
  case and not an edge.
- **FR-015**: The generic browser — everything under `/data/` — MUST NOT hard-code a category
  id, a category label, or a per-category rendering branch. A category added under `data/` and
  exposed by the API MUST appear there with no client change. Enforced mechanically: a test scans
  `web/src` for any category id **the running API's own index returns** — the scan therefore runs
  inside the end-to-end job, where the API is already up, rather than as a lint over a hard-coded
  list, which would be the very second copy it exists to forbid — and fails on a match outside an
  **exception list checked in beside the scan**, each entry a path with a one-line reason — the same ratchet
  shape as FR-036. The list is expected to hold the two series route modules and the routing map
  that names their paths; what it may not hold is a module under `/data/`.

  **The match rule is part of the requirement, because a substring grep would be useless.**
  Thirteen of the twenty-five ids are ordinary English words — `routes`, `access`, `groups`,
  `goals`, `seeds`, `streams`, `questions`, `venues`, `channels`, `calendars`, `scenarios`,
  `composition`, `spendable` — and the client's own layout puts every route module under
  `web/src/routes/`, so a grep for `routes` fires on an import path in a file that hard-codes
  nothing. So the scan MUST match **string and template literals only**, parsed rather than
  grepped, and MUST NOT count a literal that is a path segment of the file's own path or of an
  import specifier. What it is looking for is a category id **written down as a value**; anything
  else is a word that happens to collide, and a check that cannot tell the two apart gets silenced
  by exceptions until it holds nothing. A generated route tree is excluded by being generated
  rather than by being listed.
- **FR-015a**: The two series routes are the deliberate exception, and there are exactly two,
  named in the routing map and in the exception list of FR-015.
  A chart is not a generic rendering: it needs to know it has a date axis and a numeric axis, and
  which series it is drawing. So the routing map names them, each names its series, and a
  **third** per-category screen is a decision taken in review rather than a file somebody adds —
  which is the difference between one named exception and a category branch growing back.
- **FR-016**: A record card MUST show **every** field the API returns for that record, in the
  order returned. An unrecognised field is displayed generically; dropping it is a defect.
- **FR-017**: Every observed value on a card MUST show its citation, `retrieved_on` and
  `verified_on`. An empty `verified_on` renders as the unverified mark, never as an empty field.
- **FR-018**: A record card MUST show the path of the file that declares it (OB-3).
- **FR-019**: A record's synthetic flag, where the API sends one, MUST be rendered on the record
  and MUST NOT be inferable only from a directory name.

### `as_of`

- **FR-020**: `as_of` MUST be a typed search parameter validated by the router on every route. An invalid value is a visible error naming the parameter; substituting a default
  silently is a defect.
- **FR-021**: There MUST be no implicit `as_of`. On a first load without one, the app MUST read
  today's date from the browser clock **once**, redirect to the same route with it written into
  the URL, and render nothing until it is there — so every screen the owner can look at or send
  to somebody is explicit about the date it was read at. Taken against leaving it implicit and
  defaulting server-side: an implicit date makes a screenshot unreproducible and every later
  render clock-dependent instead of one redirect.
- **FR-021a**: That redirect MUST be the client's **only** read of a clock, enforced by a lint
  rule that fails on any other. A second clock read is how the parameter in the URL and the date
  a figure was aged at come to disagree, which is the whole defect FR-021 exists to prevent. A
  URL that already carries `as_of` reads no clock at all, which is why the end-to-end suite is
  deterministic (FR-048).
- **FR-022**: Changing either parameter MUST re-query the API. The client MUST NOT recompute,
  reconvert or re-age anything it already has.
- **FR-023**: Moving `as_of` across a source's staleness threshold MUST change that source's
  staleness state, and a move that crosses none MUST leave every staleness state alone. Stated
  as a biconditional because the one-directional reading — *`as_of` changes something* — is
  satisfied by a screen that re-renders on every date and says nothing true.
- **FR-023a**: Beyond staleness, `as_of` MUST change exactly what the API states is a function
  of it and nothing else. A dated schedule resolving to a different row across a legislated
  `effective_from` is a *correct* change and the screen shows it; the client neither suppresses
  it nor asserts it, because which figures are date-dependent is the engine's fact and not the
  client's. What may never change is a value the API returned identically twice.
- **FR-024 to FR-026** governed the display switch and are **deferred**, in *Deferred by owner
  decision*. What replaces them here is not a weaker rule but the absence of the thing they
  constrained: the client has no display role, so *the client converts nothing* holds by
  construction rather than by a prohibition.

### The two series

- **FR-027**: Each series route MUST take its window from the URL as a typed, validated search
  parameter and request exactly that window from the API.
- **FR-027a**: There MUST be no implicit window. A series route loaded without one MUST fetch the
  series' API-stated default window (OB-8), redirect with it written into the URL, and render
  from there. The client MUST NOT choose a window, and MUST NOT fall back to "recent" or to a
  fixed span: the official-rate series is one observation per calendar day over years, so a
  client-chosen span is a client-chosen truncation of the very thing the *Edge Cases* entry
  forbids it to truncate.
- **FR-028**: A chart MUST plot exactly the observations returned. A gap between observations is
  drawn as a break with its own label; the client MUST NOT interpolate across it, carry a value
  forward, or extend a series past its coverage.
- **FR-029**: A window reaching outside a series' declared coverage MUST render the API's typed
  refusal, in place of the missing part and never in place of the whole chart.
- **FR-030**: A series' axis MUST state the identity the API declares, and whatever the API
  declares the values are *in* — a quotation unit where the series has one, and otherwise the
  series' own base description, which is what a price index has instead. The client MUST NOT
  infer either and MUST NOT leave the axis bare: a unit read as `1` where the publisher quotes
  per `100` is wrong by two orders of magnitude and nothing downstream will say so
  (`data/README.md`), and a number with no stated basis is the same defect with the label
  missing rather than wrong.
- **FR-031**: The chart component MUST render a series of **one** observation as one point with
  its date: never a line, never a segment to a second point it invented, never a series of length
  one drawn as a trend. This is a property of the component and is asserted in the unit suite,
  because neither series routed by this feature has that shape — a requirement that waits for a
  route to exist is a requirement nothing holds.
- **FR-031a**: A **retrieval** is not a series and MUST NOT be charted as one.
  `data/observations/inzhur.toml` is the case: it carries a `retrieved_on` per observation, and
  a `retrieved_on` is when somebody looked, not when the value held. Its `buy` and `sell` are one
  snapshot of a current price, so there is no time axis to draw them against. Drawing it would mean the client supplying the axis, which is FR-001
  broken in the most convincing-looking way available to a chart.
- **FR-032**: Every chart MUST have a keyboard-reachable table of the same rows, and the table
  MUST carry each point's mark and any per-point refusal. A chart is an approximation of a table
  here, not the other way round.

### Serving, and privacy

- **FR-033**: In development the client's dev server proxies `/api` to the API; in production
  the API serves the built client with SPA fallback, from the same origin. How each of those is
  packaged is FR-049 to FR-054.
- **FR-034**: Every port the application publishes on the host MUST be published to `127.0.0.1`
  and to nothing else, in development and in production. Authentication before any other
  interface is the constitution's release gate, unchanged by this feature and out of its scope —
  and a container that publishes on `0.0.0.0` reaches that gate by accident, which is why the
  bind address is a requirement here rather than a deployment note.
- **FR-035**: The running application MUST make no request to any origin other than its own. No
  CDN, no web font fetched at runtime (fonts are vendored into the repository), no analytics, no
  telemetry, no error reporting, no source-map upload.
- **FR-036**: FR-035 MUST be checked mechanically over the **built** output: every absolute URL
  in the build fails the check unless it is listed in a checked-in allowlist file with a one-line
  reason (a licence banner is the expected inhabitant). An unlisted URL fails the build. A
  ratchet in the same shape as `scripts/check_prose_budget.py`: adding one is a visible edit.
- **FR-037**: Every npm dependency the feature adds MUST be listed with its network behaviour at
  install, build, test and run time (*Dependencies added* below). A dependency that makes a
  request at **run** time is refused rather than configured off.

### Accessibility

- **FR-038**: Every interactive element MUST be reachable and operable by keyboard, with a
  visible focus indicator. Focus MUST NOT be trapped, and each route MUST offer a skip link to
  its main content.
- **FR-039**: Text MUST meet WCAG 2.2 AA contrast (4.5:1, 3:1 for large text) and UI components
  and graphical objects 3:1, in **both** the light and the dark theme.
- **FR-040**: No information may be carried by colour alone — which FR-009 already requires of a
  mark and this extends to a refusal, a series and a status.
- **FR-041**: Chart series MUST be distinguishable without colour, and the table of FR-032 is the
  accessible equivalent of every chart.
- **FR-042**: The theme MUST follow the operating system's setting and be switchable. The theme
  switch is a display concern: it changes no value, no mark and no ordering.
- **FR-043**: An automated accessibility check MUST run in CI over every rendered route in
  **both** themes and be blocking. Both, because a check that visits only the default theme
  passes on a broken one — and the theme is a runtime choice, so a token-level contrast check
  alone cannot see what a rendered page composes. It remains a floor and not a proof: it catches
  what a machine can name, and FR-038 to FR-042 are the requirements, not this job's ruleset.

### Tests

- **FR-044**: Unit tests MUST use mock handlers typed from the same OpenAPI document, so a
  fixture that has drifted from the contract fails to compile rather than passing.
- **FR-045**: End-to-end tests MUST run against the real API on loopback over the shipped
  `data/`, with no network reachable — the same property `tests/conftest.py` asserts for the
  Python suite (`K4`).
- **FR-046**: The end-to-end suite MUST cover, at minimum: opening a category and seeing its
  records; opening a record and reading its source, `retrieved_on`, `verified_on` and mark;
  and opening the official-rate chart. A fourth item required switching `display` and asserting that a tax figure and a declared amount did not change while the display slot's state did; it is deferred.
- **FR-047**: End-to-end assertions MUST be about states and relations — present, marked,
  refused, unchanged, changed — and MUST NOT hard-code a figure copied out of `data/`. Files
  under `data/cpi/` and `data/official_rates/` are regenerated by fetch scripts and are supposed
  to move; a number pinned in a browser test is a second copy of a golden, in the one place
  nobody would look for one.
- **FR-048**: The end-to-end suite MUST be deterministic. Every URL from which a test asserts a
  figure, a mark or a refusal carries an explicit `as_of` (FR-021), so no such assertion depends
  on the wall clock. The **one** exception is the redirect test SC-008a names: it starts from a
  URL with a parameter missing and asserts *that the parameters arrive*, never a value — so the
  clock it reads decides nothing the test looks at.

### Packaging

Owner decision 2026-09-03: the API and the client ship together under `docker-compose.yml` at
the repository root. Feature 020 owns that file and its `api` service; what follows is this
feature's part of it.

- **FR-049**: Production MUST be **one running container**. The client is built in a `pnpm`
  stage whose only input is `web/`, and the built `web/dist` is copied into the API image, which
  serves it with SPA fallback (FR-033). Taken against a second container running a static
  server: a static server would be a second process binding a second host port for content that
  must be same-origin with the API anyway (the *Assumptions* rule out CORS), and same-origin
  through two containers means a reverse proxy — a third thing, to serve files the API is
  already serving.
- **FR-050**: The build stage MUST be reproducible from the lockfile — a frozen, offline-capable
  install — and MUST fail rather than resolve a version the lockfile does not name. A build that
  can pick a different dependency than CI typechecked is a build whose gates prove nothing.
- **FR-051**: The `web` service in `docker-compose.yml` is **development only**, behind a compose
  profile, and runs the Vite dev server with hot reload, proxying `/api` to the `api` service
  over the compose network. Bringing the stack up without that profile MUST start no `web`
  service, because in production there is nothing for it to do (FR-049).
- **FR-052**: Every host port either compose service publishes MUST name `127.0.0.1` explicitly.
  Checked **statically over `docker-compose.yml`**, across every service and every profile, and
  not only by the smoke job: the smoke job brings up the production stack, and the `web` service
  is dev-profile-only (FR-051), so a runtime check alone never looks at the stanza most likely to
  carry a blank host. This is FR-034 in the one place it is violated by *omission* rather than by
  choice — Docker's default host address is every interface, so a port published with a blank
  host is the constitution's authentication release gate bypassed by a missing field.
- **FR-053**: The image MUST contain no Node toolchain and no `web/` source: the final stage
  carries the built assets, the Python application and its runtime, and nothing that produced the
  assets. The Python source is what the container runs and stays.
- **FR-054**: FR-035 and FR-036 apply to the artefact **inside the image**, not only to a local
  build. The bundle-URL check runs over the same output that ships.

### Key Entities

- **Category** — a kind of declaration the API indexes, with a record count and the dates it is
  characterised by. Identity comes from the API; the client knows the shape and not the members.
- **Record** — one declaration, identified by `(category, id)`, carrying an ordered list of
  fields, its declaring file path, and its synthetic flag where it has one.
- **Field** — a label, a value, a type, and — for an observed value — its citation,
  `retrieved_on`, `verified_on` and observation kind.
- **Figure slot** — the unit FR-007 governs: the place a number appears, in one of three states.
- **Mark** — the closed vocabulary the API owns, rendered as text.
- **Refusal** — a tagged member of a closed union carrying its reason.
- **Series** — an identity, what its values are in (a quotation unit, or a base description), a
  coverage window, and observations in a requested window.
- **View parameters** — `as_of`, typed, in the URL, on every route; and a window on the two
  series routes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every category the API indexes is reachable in two clicks from the overview, and
  every record in three.
- **SC-002**: 100% of figure-bearing components have a refusal state and a marked state,
  asserted by a test that enumerates the components rather than by review.
- **SC-003**: Adding a member to any closed union in the OpenAPI document turns the build red
  until every site handles it. Demonstrated by a test that adds one to a copy of the document.
- **SC-004**: 100% of observed values on a record card display a citation, a `retrieved_on` and a
  `verified_on`, and every empty `verified_on` displays the unverified mark as text.
- **SC-006**: Moving `as_of` across a staleness threshold changes that source's staleness state;
  a move crossing none changes no staleness state. Neither is asserted over values, because
  FR-023a leaves the API free to resolve a dated schedule differently — what SC-006 pins is that
  a figure the API returned identically twice renders identically twice.
- **SC-007**: A series window reaching past coverage produces the API's reason on screen and
  zero plotted points past the last observation.
- **SC-008**: The chart component handed a one-observation series renders exactly one plotted
  point and zero line segments, asserted in the unit suite (FR-031).
- **SC-008a**: A first load of any route with a parameter missing ends at a URL carrying every
  parameter **that route** takes — `as_of` everywhere, plus the window on the two series routes. It asserts that the parameters arrive and that each is the one that route takes;
  it asserts no parameter's **value**, which is the whole of FR-048's exception for it.
- **SC-009**: The built output contains no absolute URL outside the allowlist, and the allowlist
  is empty of anything the running page would fetch.
- **SC-010**: The end-to-end suite passes with networking unavailable.
- **SC-011**: The accessibility check reports zero violations at the AA level on every route, in
  both themes.
- **SC-012**: `web/src` contains no category id declared by the API outside the paths in the
  scan's checked-in exception list, and that list contains no module under `/data/` (FR-015).
- **SC-013**: Regenerating the client types produces output identical to what is committed.
- **SC-014**: Bringing the production stack up starts exactly one container, publishes on
  `127.0.0.1` only, and serves both the API and the client from one origin.
- **SC-015**: The production image contains the built assets and no `node_modules`, no Node
  package manager and no file from `web/` that is not a build output.

## How `web/` enters the gates

**Seven CI jobs, all blocking**, and all of them **unconditional** rather than filtered on a
`web/` path. The path filter is the tempting half and the wrong one: the type-sync job exists
precisely to turn red when a *Python* change moves the OpenAPI document, and a filter that skips
it on a Python-only change disables it on the only change it was built for.

| Job | What it fails on |
|---|---|
| Typecheck | `tsc --noEmit` under `strict`. Carries FR-004 and FR-005. |
| Lint | ESLint over `web/`, including the rule set that forbids a `default` arm on a discriminated-union switch. |
| Unit | Vitest + React Testing Library, mocks typed from the document (FR-044), plus the component properties no route can reach (FR-031, FR-031a). |
| End-to-end | Playwright against the real API on loopback, offline (FR-045 to FR-048); the accessibility check of FR-043; and the category-id scan of FR-015, which needs the running API's index to know what to look for. |
| Type sync | Regenerate the client types; fail on any difference from the committed output (FR-003). |
| Bundle URLs | Absolute URLs against the allowlist, over the local build **and** over the assets extracted from the built image (FR-036, FR-054). |
| Compose smoke | Statically: every published port in `docker-compose.yml` names `127.0.0.1`, across every service and profile (FR-052). Then at runtime: the image builds from the lockfile with nothing resolved (FR-050), one container comes up, it serves the client and the API from one origin, and it carries no Node toolchain (FR-049, FR-053). |

Two checks run **inside** the end-to-end job rather than as jobs of their own, because both need
a browser or a running API that job already has: FR-043's accessibility pass over the rendered
routes, and FR-015's category-id scan. Every requirement with a mechanical form is in this table
or in one of those two; a requirement whose check has no job is a requirement nothing holds.

### Playwright runs against the in-process API, not against the compose stack

The end-to-end job starts `uvicorn` on `127.0.0.1` over the shipped `data/` and points Playwright
at it. Taken against running the suite through `docker compose up`, for three reasons, in
descending weight:

1. **The two jobs are asking different questions, and merging them loses one.** The compose smoke
   job's claim is *the image is correct*; the end-to-end suite's claim is *a mark survives from a
   TOML file to a pixel*. Run through compose, a red suite has two candidate causes, and the one
   that fires most often — a Dockerfile change — has nothing to do with what the suite tests.
2. **The Python environment already exists in CI.** Every other job builds it. The end-to-end job
   reuses it and starts a process; the compose route rebuilds the whole image to run a browser.
3. **The offline requirement (FR-045) is simpler to state and to hold on one host.** Networking
   is unavailable to the job and the only reachable address is loopback. Inside compose, "no
   network" needs a paragraph about which of the container networks counts, and a paragraph is
   what a gate is supposed to replace.

### The two prose scripts stay Python-only, deliberately

`scripts/check_prose_budget.py` walks `src/terezy`, `tests` and `scripts` and measures with
`tokenize` and `ast`; `scripts/check_enumerations.py` walks `src`, `tests` and `scripts` for
`*.py` and takes its canonical sets from `data/*.toml` `id` columns, `Enum` members and
`Literal[...]` alternatives. Neither can see a `.ts` or `.tsx` file, and **neither is extended
to `web/` by this feature.**

The reason is not cost. It is that a TypeScript port of each would be a second implementation of
a rule, and the rule each enforces is already enforced in `web/` by something stronger:

- The enumeration check exists because prose claimed a set had five members while the data
  declared eleven. In `web/` the equivalent claim is not made in prose at all — the sets come
  from the generated types, and a set that grows fails the typecheck at every non-exhaustive
  site (FR-004). A check that cannot go stale beats a check that scans for a stale sentence.
- The prose ratchet is a measurement whose value is the ground it holds on trees that have
  drifted. A new tree starts at whatever it starts at, so a ceiling recorded for `web/` on day
  one would be a number with no history behind it, which is a ratchet in name only.

If `web/` later grows prose that claims something about elsewhere, the answer is to re-measure
and record a ceiling then, as a deliberate edit — the same act the script's own docstring calls
"the act that holds ground".

## Required tests

**This feature closes no row in `docs/REQUIRED_TESTS.md`, and adds none.** No lettered behaviour
names a browsing surface, and stretching one to fit would be the inverse of what that file is
for. Two rows belong in *Rows a feature reinforced without closing* when this lands. One of them
is already `[x]`, and that is the section's normal traffic rather than an anomaly: the heading is
about reinforcing, and half a dozen features have recorded an E5 reinforcement there since E5 was
closed. A closed row still has to keep holding.

| Row | How, and why the box does not move |
|---|---|
| **F2** | *Switching display currency changes no realised amount, no tax figure, and no after-tax UAH ranking.* **Not approached, and the reason is now simpler than the one this row was first given here: there is no switch.** The owner deferred it on 2026-09-03, so this feature builds neither the control nor the assertion (020's side of the withdrawal is still owed -- see the Status header). Two things stay true and are why the row is named at all: the figure slot this feature does build has a refusal state, so the day a display conversion is declared the slot it lands in already exists; and the row's remaining halves need a realised amount and a ranking, which come from an answer and are out of scope here regardless. |
| **E5** | Closed since 2026-08-21 by `tests/contract/test_provenance_propagation.py`, and reinforced here on a third surface — after the tables and feature 005's diagrams. FR-009 and SC-004 carry the mark onto a rendered page with the same discipline of stripping every style declaration before asserting it. The box does not move because it has already moved; what this records is that the property still holds one surface further out, which is the only thing that keeps a closed row from quietly becoming false. |

**E11** — *a zero tax figure distinguishes exempted from not applicable when rendered* — is the
presentation row nearest this feature and is untouched by it: no screen here renders a tax
waterfall. The refusal-and-mark component vocabulary this feature builds is where E11 will
eventually be satisfied, and saying so is not a claim that this feature advances it.

## Clarifications

Three were open when this spec was written. All three are answered by the owner on 2026-09-03 and
recorded in `specs/decisions/2026-09-03-clarify-021.toml`, which is the artefact each appeal below
is checked against. The options each was offered are in that file; what is here is the answer and
what follows from it.

| | Question | Answer | What follows |
|---|---|---|---|
| **Q1** | What language is the interface written in? | **English only** | Nothing is translated and no key file exists. A label matches the field name in the TOML file, so a person reading a card and a person reading the file see the same word. The citation strings, refusal reasons and observation kinds arrive from the engine in English regardless, so a Ukrainian frame would have surrounded English content. |
| **Q2** | Is the display-currency selector offered while nothing can convert? | **Moot** | Not *option A*, and the difference matters: the question assumed a selector, and the owner deferred the display switch as a subject the same day. There is no control and nothing for it to list. 020's matching withdrawal is still owed, which the Status header states rather than assumes. The question is live again, unchanged, the day the switch is picked up. |
| **Q3** | Does the browser show the owner's own declarations? | **Yes, each labelled as his own statement** | Every category is shown. The label is the operative half and is not decoration: a per-owner figure must read as the owner's statement and never as an observation, and the mechanism already exists — FR-013 renders the citation exemption **with its reason** on every such record, and that reason *is* "this directory holds the owner's own statements" (OB-6). It changes who can reach the app not at all. |

**Q3 also decides what is exercisable.** Every directory `scripts/check_provenance.py` exempts
*and that ships records* is an owner-statement directory — its one other exemption is `user/`,
which is gitignored and ships none. So under the answer given, US1 acceptance scenario 3 and
FR-013 are exercisable on the shipped tree; under the alternative, no exempt record would have
been reachable at all and the scenario could not have been run.

## Deferred by owner decision

**The display-currency switch, deferred entirely on 2026-09-03** together with 020's `display`
request parameter. Moved here rather than deleted, so that picking it up later reads a scope
instead of reconstructing one from a diff. Nothing below is withdrawn as wrong; each is a
requirement about a thing that does not exist yet.

| Deferred | What it said |
|---|---|
| **OB-9** | The base currency, and per currency whether a converted figure can be supplied and, where it cannot, the reason. The first fed FR-024a's first-load redirect; the second fed FR-026's refusal. |
| **FR-020**, the `display` half | `display` typed and validated by the router on every route. |
| **FR-024** | Changing `display` MUST NOT change a base-role figure, a tax-role figure, or any ordering. Only a display-role slot may change. |
| **FR-024a** | No implicit `display`: a first load redirects with the base currency the API states, never one the client picked and never one inferred from the browser's locale — a locale-derived one would make the same link mean different things to two readers. |
| **FR-025** | The client MUST NOT convert a currency, and MUST NOT use an official rate for a display conversion: the official rate is the **tax** role, and a display conversion is a channel-rate question (`docs/REQUIRED_TESTS.md` F3). |
| **FR-026** | Where the API supplies no converted figure, the figure renders in its declared currency with the unmet display request shown as a refusal carrying its reason. **Measured 2026-09-03**: no module under `src/terezy/` reads a display currency at all — `tests/contract/test_the_rate_you_are_taxed_at.py::TestNoDisplayChoiceCanReachATaxFigure` pins the tax half, and F2, F3 and F4 record the rest as open. |
| The two `display` acceptance scenarios of US4 | Byte-identical base-role and tax-role figures across a `display` change; and an unmet `display` rendering as a refusal rather than as a conversion. Named rather than numbered: US4's surviving scenarios were renumbered, so the old ordinals now point at live ones. |
| **SC-005** | Switching `display` changes zero base-role and zero tax-role figures, compared field by field. |
| **FR-046's fourth item** | The end-to-end minimum's display clause. |
| **Q2** | What the selector lists. |

**What the deferral does not weaken.** FR-025's prohibition was the client converting nothing;
with no display role at all, that holds by construction rather than by a rule, which is stronger.
And FR-007's three states are untouched — the display slot was only ever going to be the least
informative instance of the refusal state, since FR-026's own measurement said it would be a
refusal on the day this feature landed. A refusal still arrives on a series window, on a keyed
read of an id nothing declares, and on any figure the engine refused.
## Dependencies added, and what each one touches the network for

Every entry states install / build / test / run. **Run** is the column FR-035 governs, and a
dependency with anything in it is refused.

| Dependency | Network behaviour |
|---|---|
| pnpm | Install: fetches from the configured registry, as any package manager does. Build/test/run: none. |
| Vite, `@vitejs/plugin-react` | Install only. Build and dev server are local, and the dev server proxies only to the API — `127.0.0.1` when both run on the host, the `api` service name when it runs under compose (FR-051). Never to a third party. |
| TypeScript | Install only. |
| React, React DOM | Install only. No runtime request. |
| Tailwind CSS (+ its Vite plugin) | Install only. CSS is generated at build time; **the CDN script build is not used**. |
| shadcn/ui | Its CLI fetches component source at **authoring** time, when a component is added, and the result is committed as owned code. Nothing at build, test or run. |
| Radix UI primitives, `class-variance-authority`, `clsx`, `tailwind-merge`, the icon set | Install only. All render locally; icons are components, never fetched. |
| TanStack Router, TanStack Query | Install only. Query issues exactly the requests the app asks it to, at the app's own origin. |
| Recharts | Install only. Renders from data passed in. |
| `openapi-typescript` | Install, plus **generation** time — reads the OpenAPI document **from the local filesystem**, not from a URL. |
| `openapi-fetch` | Install only. A thin typed wrapper over `fetch`; every request is the app's own. |
| Vitest, React Testing Library, jsdom | Install only. |
| MSW | Install only. Intercepts in-process for Node tests; where the browser worker is used, the worker file is generated into the repository rather than fetched. |
| Playwright | Install **downloads browser binaries** — the one entry with real install-time egress, and it is install-time, cached, and outside the test run. Tests themselves run with no network reachable (FR-045). |
| ESLint + the TypeScript ESLint packages | Install only. |
| Vendored fonts | No dependency at all: font files are committed and served from the app's own origin (FR-035). |

The container base images are the other install-time egress, alongside Playwright's browsers:
pulled when the image is built, pinned by digest, and reached by nothing at run time.

## Assumptions

- Feature 020-http-api ships the checked-in OpenAPI document this feature generates from, and
  satisfies OB-1 to OB-8 (OB-9 is withdrawn with the display switch). **020's spec exists and the document does not**, so every
  requirement here that names the document is unverifiable until 020 lands — the shape of the
  dependency rather than a gap in this spec. Which of OB-1 to OB-8 that draft satisfies is audited
  in `research.md`, and three of them it does not. Where 020 does not satisfy
  an obligation, that is 020's requirement to add or this feature's scope to cut — never a
  client-side workaround. Implementation may not start before 020 is `done` on `main`.
- Feature 020 owns `docker-compose.yml` and the `api` service in it, including the image that
  FR-049's build stage hands its output to. This feature owns the `web` service, the build stage,
  and the two properties that must hold of both: one production container, loopback-only ports.
- The API and the client are served from one origin in production, so nothing here needs CORS,
  and a cross-origin request would be a defect rather than a configuration.
- The routing map is the owner's: `/`, `/data/:category`, `/data/:category/:id`,
  `/series/official-rate`, `/series/cpi`, with `?as_of=` on every route (and a window on the two
  series routes). `/question/:id`
  and `/compare` are later features and must fit under the same router and the same search
  parameters — `as_of` globally, a window where a route needs one — without restructuring — which is a constraint on this feature's routing, not a
  promise about theirs.
- The API is the client's only source of truth. The client reads no TOML, ships no copy of
  `data/`, and derives nothing from a file path beyond displaying it (FR-018).

## Out of scope

- **Editing a declaration.** The screen is read-only. A declaration is changed in git, reviewed
  like code, and that is the property the whole `data/` design rests on.
- **Running a fetcher.** `scripts/fetch_*.py` stay command-line. A button that rewrites a
  declaration from a screen removes the step where somebody reads the diff.
- **Verifying a value from the UI.** `verified_on` records that a **person** checked a value
  against a primary source. A button that writes today's date into it would be the tool marking
  its own homework, and every fetch script in this repository is already forbidden from doing it.
- **Answer, compare and question screens.** Later features. This one's routing must accommodate
  them and must not anticipate them.
- **Authentication.** The constitution's release gate before the app listens on anything but
  loopback. Not this feature, and not weakened by it.
- **Internationalisation.** Q1 is answered: English only. A translation layer is a later,
  additive change around labels that already exist.
- **Mobile-specific layouts.** The pages must be usable at a narrow width and no mobile-only
  surface is designed.
- **The display-currency switch, entirely.** Deferred by owner decision 2026-09-03 together with
  020's `display` request parameter — not merely the conversion, but the selector, the parameter
  and the slot. *Deferred by owner decision* is its scope, and the `[[future]]` entry in the
  Appendix is where it is tracked.

## Appendix

### The two artefacts this spec depended on: both applied

The `[[feature]]` entry in `specs/features.toml` and the constitution amendment lifting D-B were
drafted here and are now **in force** — the entry is in the file (`020-http-api` beside it), and
the constitution is at **1.4.0** with the `web/` layer line. Neither draft is reproduced here any
longer: a copy of a live entry is a second place one fact lives, and the copy is where the drift
goes. What the amendment changed is recorded below because it is the argument, not the text.

### The `[[future]]` entry the display deferral needs, drafted

**Not applied by this branch.** Applied by the change that lands the implementation, so that
*Deferred by owner decision* above is tracked in the graph rather than only in prose.

```toml
[[future]]
id      = "web-display-currency-switch"
after   = ["021-web-declared-data"]
note    = "The display-currency selector, the `display` search parameter and the display slot's refusal state, deferred by owner decision 2026-09-03 (specs/decisions/2026-09-03-clarify-021.toml) together with 020's `display` request parameter. Its scope is the Deferred by owner decision table in 021's spec, which is why that table was moved rather than deleted. Additive to what 021 lands: a second global search parameter on a router that already validates one, and a fourth state on a figure slot that already has three. REQUIRED_TESTS F2's remaining halves need this AND an answer screen, so it does not close F2 on its own."
```

### The constitution amendment, as applied

**Three** edits in `.specify/memory/constitution.md`, all in *Architecture Constraints*, plus the
header record of D-B and a version bump to **1.4.0** — all applied. MINOR under the stated policy — a section's
guidance is expanded to cover a surface it deferred, and no principle is removed or redefined;
superseding a founding decision is what *Governance* calls an amendment rather than what
*Versioning policy* calls a MAJOR. **Artefacts invalidated: none.** No spec, plan, test or data
file rests on the deferral; feature 021's spec is written against the amended text and is the
reason for it, and every other feature's contract with the delivery surface is the API, which
this does not touch.

**The applied text is in the constitution and is not reproduced here.** A quote of a live document
is a second copy of it, and this Appendix's whole subject is what happens when one drifts. What is
recorded is the argument, which lives nowhere else:

1. **The layer-map line** stopped saying `ui/  deferred` and started naming `web/` as a client over
   `api/` over HTTP and never over `core/`, outside the Python package.
2. **The *Delivery surface* paragraph** records the deferral as **discharged, not deleted**: what it
   bought — that the schema rather than a framework is the contract — survives the choice, and the
   original deferral was not an omission being corrected. The API was designed as the UI's only
   contract precisely so that this choice would stay cheap, and it did.
3. **The sentence under the layer map** dropped `ui/` from `core/`'s forbidden-import list rather
   than renaming it to `web/`. `lint-imports` governs a Python package and cannot see a TypeScript
   tree, so `core/` could not import from `web/` if it tried. The sentence gains a clause saying so,
   because a layer named in the map and absent from the rule reads as an oversight, and a layer
   named in a rule that no gate can check reads as a gate that exists.
