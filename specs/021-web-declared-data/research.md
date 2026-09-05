# Research: the declared data, on a screen that can refuse

**Feature**: `021-web-declared-data` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)

Phase 0. Everything here is a decision taken against a named alternative, or a claim about a
package that implementation must check. Nothing here reopens the owner's stack decision
(`specs/decisions/2026-09-03-web-stack.toml`); what it does is find out what that stack can
actually be pointed at.

**The spec's three questions are answered** (`specs/decisions/2026-09-03-clarify-021.toml`, and the
spec now carries them): English only; the owner's own declarations are shown, each labelled as his
statement; and the display-currency selector question is **moot**, because the owner deferred the
display switch entirely. **D0** records what the deferral subtracts, what survives, and the part of
it that is a change 020 has not yet made; **D11** is the other two answers.

The largest finding is **D1**: of the obligations the spec puts on feature 020, **three** are unmet
by 020's specification as drafted, one is left ambiguous by it, and a separate claim of 020's rests
on a false premise about this feature. The spec's *Assumptions* already say what to do about that —
*"Where 020 does not satisfy an obligation, that is 020's requirement to add or this feature's
scope to cut — never a client-side workaround"* — so this section's job is to name each one
precisely enough that 020 can add it or 021 can cut it, before either is expensive.

---

## D0 — The display switch is deferred, and what that subtracts

**Owner decision 2026-09-03** (`specs/decisions/2026-09-03-clarify-021.toml`, answer 2): the
display-currency switch is deferred as a **subject**, on both sides of the wire.

**020 has not made that change yet, and this is the first thing to check before implementation.**
`specs/020-http-api/spec.md` on `main` still carries US4, **FR-021** (*"The display currency MUST be
a request parameter, resolved on the server"*), FR-022 to FR-025, and clarification 1 — whose
interim option B keeps the parameter and refuses the block by name. So the deferral is a **change
020 owes**, not a property of its draft, and until 020 makes it the generated `schema.d.ts` will
carry a `display` query parameter this feature has no requirement about. That is precisely the
*parameter with no stated origin* FR-001 and FR-020 call a silent default, arriving one level up.

Two ways out, and the first is the decision as taken: **020 withdraws the parameter** along with
FR-021 to FR-025 and clarification 1, and 021's deferral is then a fact. If instead the parameter
survives on 020's side, 021 needs one requirement saying it sends nothing and renders whatever the
API's own default produces — which is a smaller thing than a selector, and is still a requirement
rather than a silence. **Add it to D1's list of things to settle with 020.**

Everything below assumes the decision is carried out. The spec's *Deferred by owner decision*
section is the scope; what follows is what it means for the plan.

**What is struck from this feature.** Each of these is a requirement the spec states and the
deferral removes; none is a requirement this plan judged unnecessary.

| Struck | Spec text it comes from |
|---|---|
| The currency selector, and its option list | Q2 in full — **moot, resolved by deferral** rather than by an answer |
| `display` as a search parameter, its validation, its first-load redirect | FR-020's `display` half, FR-024a |
| The display slot's three states, and the unmet-conversion refusal | FR-024, FR-025, FR-026 |
| US4 acceptance scenarios 2 and 3, and SC-005 | the two that name `display` |
| The display clause of the end-to-end minimum | FR-046's fourth item |

**What survives, and is the reason the deferral costs this feature almost nothing.**

- **`as_of` is untouched**, and is now the **only** global typed search parameter. FR-020 applies
  to it in full, FR-021 and FR-021a still make it explicit-or-redirect with one clock read, and
  FR-023 and FR-023a are the staleness requirements — which were always the harder half of US4.
  020's clarification 2 recommends making `as_of` **required**, which is the same arrangement seen
  from the other side.
- **The two series routes keep their window parameter** (FR-027, FR-027a). Search-parameter
  validation is therefore still per route and still typed; only one parameter left the set.
- **The refusal and mark vocabulary is untouched.** FR-007's three states were never about
  currency: a refusal arrives on a series window, on a keyed read of an id nothing declares, and
  on any figure whose provenance the engine refused. The spec's own measurement said the display
  slot would be *"a refusal on the day this feature lands"*, so what the deferral removes is the
  least informative instance of the state, not the state.
- **Principle VI's three roles are unaffected.** Base and tax stay as the API returns them, and
  the display role now has no client at all — which is the strongest possible version of *the
  client converts nothing* (FR-025), holding by construction rather than by a rule.
- **`REQUIRED_TESTS` F2** stays open, and this feature no longer even builds the surface its
  remaining halves would be tested on. The spec's F2 row said the box stays open because a
  read-only browser has no realised amount and no ranking; under the deferral the reason is
  simply that there is no switch. Both readings leave the box where it is, and the second is
  shorter and truer.

**OB-9 goes with it.** D1's OB-9 row is the base currency for a redirect and an enumeration for a
selector; neither has a consumer now. What remains of OB-9 is nothing this feature needs, because
every amount renders in the currency the API returned it in, which is FR-001 with no special case.

**The `[[future]]` entry that tracks it is drafted once, in the spec's Appendix**, and T060 applies
that copy. It is not repeated here: two drafts of one entry is the shape this plan spends D2 and
the Appendix arguing against, and the second copy is the one that goes stale.

---

## D1 — The nine obligations, audited against 020's specification

020's spec is `drafted` and its own clarifications are open, so this is an audit of a draft
against a draft. It is worth doing now anyway: every unmet row is either a paragraph in 020 or a
scenario deleted from 021, and both are cheaper before `web/` exists than after.

| | Obligation, in one line | 020 as drafted | Verdict |
|---|---|---|---|
| **OB-1** | Category index: what exists, how many, characterising dates | FR-009 `/registry` — shape, id count or resolved-flag, files with digests, merged provenance, unverified count | **met in part.** The counts and the shape are there. "The dates the API characterises it by" is not a field; the nearest true reading is *the `retrieved_on`/`verified_on` of the sources in the category's merged provenance*, which FR-009 does return. FR-014 is implementable under that reading and under no other. |
| **OB-2** | A **self-describing record**: ordered fields, each with label, value, type, and provenance where observed | Nothing. FR-005 maps a category to a hand-written response **type**; a record is that type's JSON object | **unmet.** See D2 — this is the decision the whole generic browser turns on. |
| **OB-3** | The record's **declaring file path** | FR-009 lists files per **category**, with digests | **unmet.** `/instruments` is 33 files; a category-level list cannot say which one declares the record on screen. FR-018 and SC-001's third click have nothing to render. |
| **OB-4** | Mark and staleness as a **closed schema**, never a free string | FR-018 (`id`, `citation`, `retrieved_on`, `verified_on`, `kind`, and the derived `is_unverified`); FR-049 (a staleness verdict the engine computed is serialised, and the layer computes none) | **met in part.** The unverified half is a boolean and is closed. The staleness half has no stated wire shape, and `SourceRef.kind` is a data-declared id (`/observation-kinds` is a served category) rather than an enumeration — which is fine for a *label* and is not what FR-010 and FR-012 need to switch on. |
| **OB-5** | Refusals as **tagged members of a closed union**, with reason and what would supply it | FR-011–FR-014 (a tag on every record, `oneOf` + `discriminator`, members discovered by walking the response annotations); FR-015 (fields verbatim, nothing synthesised); FR-016 (in the body, same shape either way) | **met on the tag; partial on the reason.** 020's clarification 3 recommends `reason` optional in the schema, with nine reason-less members held by a checked-in list. "What would supply it" is not a declared field — it is whichever fields that refusal record happens to carry. Consequence for 021 in D5. |
| **OB-6** | Whether a record's directory is **sourced or exempt from the citation requirement**, and the exemption's reason | FR-006 has an exemption table, and it is a **different exemption** — directories no *category* covers (`data/observations/`, `data/instruments/nav/`, two empty ones). `scripts/check_provenance.py`'s own sourced/exempt lists are not exposed anywhere | **unmet.** FR-013 and US1 acceptance scenario 3 have nothing to read. This is also the obligation Q3's argument rests on, so it is the most consequential of the four. |
| **OB-7** | A series read returning the in-window observations **together with** a typed refusal for the part outside coverage | FR-045 (windowed reads, window optional, two-ended when given); FR-045a (declared coverage on the list read); FR-046: a given window reaching outside coverage *"MUST refuse by name … and MUST NOT return a truncated result **silently**"* | **ambiguous, and the ambiguity has to be closed before the series route is built.** Read strictly, *refuse by name* refuses the whole request and OB-7 is unimplementable. But the prohibition is only on a **silent** truncation, and a body carrying the in-coverage rows *beside* the named refusal is not silent — which is exactly OB-7. FR-046's own rationale supports the second reading: the four bad options it lists all *"produce a number indistinguishable from a correct one"*, and a stated refusal produces none. So the two specs probably agree, and what 020 owes is a sentence saying which body it means. Also genuinely unstated in 020: the series' **quotation unit or base description**, which FR-030 forbids the client to infer and forbids it to omit. |
| **OB-8** | A **default window** per series, stated by the API | FR-045 makes the window optional and an omitted window returns the whole declared coverage; FR-045a publishes that coverage on the list read | **met, differently.** The API's stated default is *all of it*, and it is discoverable before the request. FR-027a's redirect writes that coverage into the URL. See D8 for why this is a sizing risk rather than a gap. |
| **OB-9** | The **base currency**, and per currency whether a conversion can be supplied and why not | 020 FR-025 refuses the display block by name per figure; the base currency and the currency list are not declared anywhere | **withdrawn, by D0.** Both consumers — FR-024a's first-load redirect and Q2's selector — are deferred, so 021 no longer asks for it. Note this is 021 withdrawing an obligation, **not** 020 having dropped the parameter: that change is still owed, and it is D0's open item. |

**Three rows to raise with 020 before implementation** — OB-2, OB-3 and OB-6, each a field 020 does
not yet promise. **Three to settle between the two specs** — OB-7's ambiguity, the `display`
parameter 020 still requires and the owner deferred (D0), and the **base path** (D3a). None is a client-side workaround; each is a field 020 does not yet
promise, and the spec is explicit that inventing one here is the one response not available.

**Not a gap, and worth recording so nobody re-finds it:** 020 FR-007b makes a **scenario** a
request parameter on six categories, defaulting to *no scenario in force*, and requires the
response to name the scenario it resolved under including when that is none. 021's routing
declares two search parameters and not three. The client therefore sends no scenario, takes the
API's declared default, and **renders the resolved-scenario statement the response carries** —
so nothing is silent, and FR-001's rule about a parameter with no stated origin is satisfied by
the parameter not existing rather than by defaulting it. A third search parameter would be a
client choosing a world, which is what FR-007b's own reasoning rejects one level down.

**Also not a gap:** 020 FR-048 refuses to serve `data/observations/`, so `inzhur.toml` — the
retrieval FR-031a forbids charting — is not reachable from the API at all. FR-031a stays a unit
assertion on the chart component, which is where the spec already puts it.

---

## D2 — How a record card renders every field, given that 020 declares no field descriptor

**The problem.** FR-016 requires every field the API returns, in the order returned, with an
unrecognised one displayed generically. FR-015 forbids a per-category branch. OB-2 asks 020 for
an ordered list of `{label, value, type, provenance?}`. 020 instead returns, per category, a
hand-written response type serialised as a JSON object.

**Three ways to render that, and only one of them is honest.**

| Option | What it costs |
|---|---|
| **A — 020 adds OB-2's field-descriptor shape** *(recommended)* | One response envelope, built by walking the response dataclass's fields — which 020 already does twice, for FR-013's union discovery and FR-017's provenance sweep. The client's renderer is then a `map` over a typed array and knows nothing about any category. Cost: a paragraph and a test in 020. |
| **B — the client walks the JSON object generically** | Labels are the JSON keys (which under Q1-A is what is wanted: the label matches the field name in the TOML file), order is the object's key order, and an observed value is detected **structurally** by the presence of FR-018's provenance shape. Cost: the renderer's input is `unknown`, so the generated types stop governing the one screen the feature exists for — and FR-005 forbids a cast, so every step down the object is a runtime guard the typechecker learns nothing from. It is not literally a client-side workaround for a missing field; it is a client-side reconstruction of a missing *contract*, which is the same defect with better manners. |
| **C — a per-category renderer** | Rejected on the spot: FR-015. |

**Decision: A, raised with 020. B is the fallback and its cost is recorded above rather than
discovered later.** If 020 declines, this feature's scope is cut to what B can carry honestly —
which is a card that shows every key and value and marks the ones whose structure is provenance —
and FR-016's "with its type" is dropped rather than inferred from `typeof`.

Under **B**, the guards are written once, in one module, and each returns a narrowed type rather
than asserting one: a guard that *tests* `is_unverified in v && typeof v.citation === "string"` is
a narrowing, and `v as Provenance` is a cast. FR-005 forbids the second and not the first, and the
distinction is worth stating because they compile to the same thing and mean opposite things.

---

## D3 — The origin conflict, which is 020's reasoning resting on a false premise about 021

020 **FR-032a** requires the API to declare a CORS allowance naming exact loopback origins, and
argues for it against the alternative — the API serving the built client from its own origin —
on two grounds: it *"would give a read-only API a static-file responsibility"*, and it *"would
break 021's development loop, where the client runs on its own port against this service."*

**The second ground is false, and it is this feature's fact to correct.** 021 FR-033 puts a
**proxy** in the dev loop: the Vite dev server serves the app and forwards `/api` to the API, so
the browser makes same-origin requests in development too. Nothing in 021's development loop is
cross-origin. The first ground is true and is exactly what 021 **FR-049** requires anyway: one
production container, the API serving `web/dist` with SPA fallback. 021's *Assumptions* close it:
*"a cross-origin request would be a defect rather than a configuration."*

So the two specs disagree about whether a browser ever crosses an origin here, and the answer is
no, in either environment, under 021 as written.

**Proposed resolution, to be agreed with 020 rather than taken unilaterally:**

- 020 **FR-032b** (the `Host` allowlist) is untouched. Its justification is DNS rebinding, which
  is independent of any of this and is the only one of the two checks that survives it.
- 020 **FR-032a**'s allowance becomes empty, or the requirement is withdrawn. An allowance
  naming origins that never occur is a configuration nothing exercises, and 020's own rule
  against a requirement neither specification tests applies to it.
- The `api` image gains the static-serving stage FR-049 describes. 020 owns the `Dockerfile` and
  `docker-compose.yml`; 021 owns the requirement and the `web` build stage's contents.

**Blast radius if it goes the other way:** only the packaging tasks. Every route, component and
test in this plan is unchanged by a cross-origin arrangement — the client's `baseUrl` becomes a
build-time value instead of `/api`, FR-035's "no request to any origin other than its own" becomes
false as written, and FR-049's one-container claim is what actually breaks.

**In this branch nothing is edited.** `docker-compose.yml` and the `Dockerfile` do not exist yet
and belong to 020. The plan states what the `web` service and the build stage add; the tasks that
add them are the last ones and are marked as touching a file another feature owns.

---

## D3a — The base path, which the two specs have never reconciled

FR-033 puts the client's requests under **`/api`**. 020's endpoints are **root-relative** —
`/instruments`, `/registry`, `/cpi`, `/openapi.json` — and its FR-007a requires every category path
to be *a single flat segment*, so the document a generated client is built from has no `/api` in it.

In development a Vite proxy can rewrite the prefix and nothing shows. **In production there is no
proxy** (FR-049: the API serves the built client itself), so the client would ask for
`/api/instruments` and 020 serves `/instruments`.

**The failure mode is the reason this is a finding and not a footnote.** FR-033's SPA fallback
answers an unmatched path with `200 text/html`. So the miss is not a 404 that FR-006 renders as a
named state — it is a successful response containing the app's own HTML, handed to a JSON parser.
The screen would report a transport failure against a perfectly healthy API, which is FR-006 giving
a true-looking answer to the wrong question.

Two ways to close it, and **the choice is 020's to make with 021 rather than either's to assume**:

- **020 mounts its routes under `/api`.** One prefix in one place; the document then carries it and
  the generated client is right by construction. Costs 020 a sentence and touches its FR-007a's
  wording (the segment rule is about categories under the mount, not about the mount).
- **021's base path is `/`.** Nothing changes in 020, and the dev proxy then has to forward a list
  of first segments rather than one prefix — and that list is a copy of 020's route table living in
  a Vite config, which is the second copy of a contract this feature exists to avoid.

The first is better for exactly that reason. **Until it is settled, a task that wires the client to
a base path is blocked**, and the SPA-fallback trap is worth a test either way: a request to a path
the API does not serve must not present as a parse error.

---

## D4 — Exhaustiveness, which is FR-004 and is the reason the stack was chosen

FR-004 wants a member added to a union in the OpenAPI document to turn the build red at every
site that does not handle it. Three mechanisms, and the requirement needs all three because each
covers a hole the others leave.

1. **A `never`-typed exhaustiveness helper.** `function assertNever(x: never): never` called in
   the final arm of every discriminated `switch`. A new member makes `x` not `never` and the call
   fails to typecheck. This is the mechanism; it is plain TypeScript and carries no risk.
2. **A lint rule forbidding a `default` arm on a discriminated-union switch**, because a
   `default` arm silently absorbs the new member and switches mechanism 1 off. The
   `typescript-eslint` rule set has `switch-exhaustiveness-check`, which reports a switch over a
   union that does not handle every member and can be configured to require the union be handled
   rather than defaulted. **Risk R1**: the rule's exact name and the option that forbids
   `default` (rather than accepting it as coverage) must be read off the installed version's
   documentation at implementation time, not assumed.
3. **SC-003's demonstration**: a test that adds a member to a **copy** of the generator's output,
   regenerates types into a scratch directory, and asserts `tsc` fails. This is what proves 1 and
   2 are actually wired, and it is the only one of the three that cannot pass vacuously.

**Note the interaction with 020's clarification 3.** If `reason` is optional in the schema, the
generated `reason` is `string | undefined` on every refusal member, so the refusal component must
narrow on the **tag** before it can render a reason — which is what FR-004 makes it able to do,
and what 020's own table calls *"arguably the better client anyway"*. The component therefore has
two rendering paths, both of them full states and neither a placeholder: a reason where there is
one, and the refusal's own tag and verbatim fields where there is not. FR-008 forbids `—` in both.

---

## D5 — What the generated client actually generates, and the two things to check

**`openapi-typescript`** reads an OpenAPI document and emits a `.d.ts` of `paths`, `components`
and `operations`. It reads standard input or a local path, never a URL, which is what makes FR-003
a build step with no server running — the generation input is what
`uv run python scripts/generate_openapi.py` writes (020 FR-040, owner decision 2026-09-05).

**`openapi-fetch`** is a thin typed wrapper over `fetch`: a client is created with a `baseUrl`
and the generated `paths` as its type parameter, and `client.GET("/instruments", {...})` types
the path, the parameters and the response together. Its runtime is `fetch` and its own origin.

**Risk R2 — the discriminated union.** 020 FR-013 requires `oneOf` with a `discriminator` whose
mapping names every member. Whether `openapi-typescript` emits that as a TypeScript union whose
members each carry a **literal** tag type — the property `switch` narrowing needs — depends on
whether each member schema declares the tag as a `const`/single-valued `enum` rather than as a
plain `string`. If it emits `tag: string` on every member, narrowing is impossible and FR-004 has
no mechanical form. **This is the single most important thing to verify against the real
document, and it belongs in 020's generation tests, not in a client workaround.** The check is
mechanical and fast: generate, open the `.d.ts`, and read one refusal union.

**Risk R3 — `openapi-fetch`'s error channel.** It returns `{ data, error }` rather than throwing.
020 FR-016 says a refusal is carried in the **body** with the same shape either way, so a typed
refusal arrives in `data`, not in `error`; `error` is for the non-2xx cases FR-006 makes a named
state. Confirm which of the two a refusal lands in before writing the query layer, because
getting it backwards produces a screen that renders a refusal as a transport failure — which is
FR-006 and FR-007 both wrong at once, and both green.

---

## D6 — Typed search parameters, and the one clock read

TanStack Router validates a route's search parameters with a per-route `validateSearch`, which
takes the raw search object and returns the typed one; a route may redirect from a loader or a
`beforeLoad`. That is the shape FR-020, FR-021 and FR-027a need:

- `validateSearch` on the root route for `as_of` — the only global parameter, by D0 — and on the
  two series routes for the window (FR-020, FR-027). A value that does not validate produces a
  route error, which FR-020 requires to be **visible and to name the parameter**, so the
  validator's failure carries the parameter name and the route renders it rather than the router
  substituting anything.
- The **redirect** of FR-021 runs before render, so nothing is drawn from an implicit value. It
  needs no request: the date comes from the one clock read. FR-027a's window redirect **does** need
  a request — the series' declared coverage from the list read (OB-8) — which is the only
  redirect in the app that waits on the API.
- **FR-021a's lint.** The clock is read in exactly one module. An ESLint `no-restricted-syntax` /
  `no-restricted-globals` rule fails any other `new Date()` or `Date.now()` in `web/src`, with
  that one module the only exception, listed with its reason. A test that a second clock read
  fails the lint is what makes the rule real.

**Risk R4** — the exact names (`validateSearch`, `beforeLoad`, `throw redirect(...)`, the
generated route tree's file, whether the file-based plugin or code-based routes are used) must be
read off the installed version. The plan does not depend on any of them being spelled a
particular way; it depends on the router validating per route and permitting a pre-render
redirect, which is the feature's whole reason for choosing it.

---

## D7 — Offline end-to-end, and where the two piggy-backed checks live

FR-045 wants Playwright against the real API on loopback with no network reachable, the property
`tests/conftest.py` already asserts for Python (`K4`). The spec's own section argues this runs
**in-process** rather than through compose, and gives three reasons; nothing here reopens that.

What the plan has to settle is *how* "no network reachable" is asserted, because the Python
guard's mechanism — patching `socket.socket.connect` — is not available to a browser in another
process. Two layers, and both are cheap:

- **In the browser**: a Playwright context route handler that **aborts** every request whose URL
  is not the loopback base URL, installed for the whole suite. A test that fails because the page
  tried to reach a CDN is the check FR-035 wants, expressed as a test failure rather than as a
  silently-slow page.
- **In CI**: the job runs with no egress, so an escape shows up as a failure rather than as a
  green run that happened to be online. **Risk R5**: whether the runner can be given no network
  at all without also breaking `actions/checkout` and the dependency installs means the abort
  handler is the load-bearing half and the job-level isolation is the belt.

**Two checks run inside this job because both need what it already has** (the spec's table says
so): FR-043's accessibility pass, and FR-015's category-id scan, which needs the **running API's
own index** to know which strings to look for.

- **Accessibility** — `@axe-core/playwright` over every rendered route, in **both** themes.
  Both, because a check that visits only the default theme passes on a broken one. It is a floor
  (FR-043 says so); FR-038 to FR-042 are the requirements.
- **The category-id scan** — fetch `/registry`, take the category ids, grep `web/src` for each,
  fail on a hit outside a checked-in exception list of paths each carrying a one-line reason. The
  list is expected to hold the two series route modules, the routing map, and the generated route
  tree; it may hold no module under `/data/`. Scoped by **path**, not by token, because `cpi` is
  both a category id and a route segment (FR-015 says this explicitly).

---

## D8 — The size of the official-rate series, and why it is a risk and not a bug

OB-8 resolves to *the API's default window is the whole declared coverage*. The official-rate
series is one observation per calendar day since 2019-12-28 — roughly 2,400 rows today, growing
by one a day — and the CPI series carries 411 monthly observations (020 FR-045a).

FR-027a makes the client request the API's stated default and forbids it to choose a smaller one;
the *Edge Cases* entry forbids it to truncate what comes back and says a route that would render
the whole series **must be paged or windowed by the API**. Those two are consistent only while the
whole coverage is a size a route can render.

**So: not a blocker, and stated so it is not rediscovered as a performance bug.** 2,439 points is
a size Recharts renders and a size a table renders. If it stops being one, the fix is 020 stating
a smaller default window (OB-8's own words: *"stated by the API"*), never the client picking one.
The tasks that build the series routes carry this note; none of them acts on it.

---

## D9 — FR-036's bundle-URL check, and what "the built output" means twice

A Node script over the build output greps every emitted asset — JS, CSS, HTML, and the source maps
if they ship — for an absolute URL, and fails on any not listed in a checked-in allowlist file
with a one-line reason. A licence banner is the expected inhabitant; the spec says so.

FR-054 makes it run **twice**: over the local `web/dist`, and over the assets **extracted from the
built image**. The second is the one that matters, because it is the artefact that ships, and the
two can differ — a different build mode, a different base URL, an asset the Dockerfile copies from
somewhere else. The second run needs the image, so it belongs to the compose-smoke job rather
than to the bundle job; the spec's table puts both under *Bundle URLs* and the plan reads that as
one check with two inputs, one of which the smoke job supplies.

**A vendored font is what makes this passable at all** (FR-035): a Google Fonts `<link>` is an
absolute URL in the HTML and would fail the check on the first run, which is the check working.

---

## D10 — Tailwind, shadcn/ui, and the "copied in" property

shadcn/ui is not a runtime dependency: its CLI fetches component source at **authoring** time and
the result is committed as owned code (the spec's dependency table says so). What that means for
this plan is that adding a component is a **repository edit reviewed in git**, and the components
the feature needs are enumerated in the component inventory rather than pulled as needed — so a
reviewer can see the whole surface in one diff.

The runtime dependencies it drags in are Radix primitives, `class-variance-authority`, `clsx` and
`tailwind-merge`, all of which render locally and fetch nothing. The icon set ships icons as
components, never as fetched sprites.

**Risk R6** — Tailwind's configuration shape changed between major versions (a JS config file
versus a CSS-first `@import`), and which one applies depends on the version pinned at
implementation time. Nothing in this plan depends on the answer; the tasks name "the Tailwind
configuration" rather than a filename.

---

## D11 — The three questions, answered

`specs/decisions/2026-09-03-clarify-021.toml`. Nothing in this plan is built to a guess.

| | Answer | What it settles here |
|---|---|---|
| **Q1 — UI language** | **English only** | No translation layer and no key file is built. A label is the API's own field name, so a person reading a card and a person reading the TOML file see the same word. |
| **Q2 — the currency selector** | **Moot** — the switch is deferred (D0) | No selector is built, and the question is live again unchanged the day the `[[future]]` entry is picked up. Recorded as moot rather than as the recommended option, because a spec recording that option would have a component nobody built. |
| **Q3 — the owner's own declarations** | **Shown, each labelled as the owner's statement** | No client code turns on it — FR-015 forbids the client to know any category. What it settles is what is **exercisable**: every citation-exempt directory that ships records is an owner-statement directory, so US1 acceptance scenario 3 and FR-013 can now be asserted end-to-end against the shipped tree. The label is FR-013's exemption rendered with its reason, and that reason *is* "this directory holds the owner's own statements". |

---

## D12 — Neither prose script grows a TypeScript port

`scripts/check_prose_budget.py` measures with `tokenize` and `ast`; `scripts/check_enumerations.py`
takes its canonical sets from `data/*.toml` id columns, `Enum` members and `Literal[...]`
alternatives. Neither can see a `.ts` file and neither is extended by this feature. The spec
argues why, and the argument is not repeated here: the short of it is that in `web/` the
enumeration rule is enforced by FR-004 instead, and a ratchet with no history behind it is a
ratchet in name only.

What follows for this plan is only that **the two scripts must stay green on a tree that has
grown a `web/` directory** — they walk `src`, `tests` and `scripts` and will not look at it, and
a task confirms that rather than assuming it.

---

## Risks to verify at implementation time

Collected from above so the implementer has one list. None is guessed at here as a fact.

| | What to check | Why it matters |
|---|---|---|
| **R1** | The `typescript-eslint` rule that forbids a `default` arm on a union switch: its name and the option that treats `default` as *not* covering the union | Without it, mechanism 1 of D4 is switched off at any site somebody adds a `default` to |
| **R2** | That `openapi-typescript` emits each `oneOf` member with a **literal** tag type, from 020's real document | FR-004 has no mechanical form otherwise, and the fix belongs in 020's document, not in the client |
| **R3** | Whether a 020 typed refusal arrives in `openapi-fetch`'s `data` or its `error` | Getting it backwards renders a refusal as a transport failure — FR-006 and FR-007 both wrong, both green |
| **R4** | TanStack Router's exact API for per-route search validation and a pre-render redirect | The plan depends on the capability, not on the spelling |
| **R5** | Whether the CI job can run with no egress without breaking checkout and installs | Decides whether the browser-level abort handler is the belt or the only strap |
| **R6** | Tailwind's configuration shape at the pinned version | Filenames only; no requirement turns on it |
| **R7** | Whether 020's `/registry` returns enough per-category dated provenance for FR-014's "the dates the API characterises it by" | If not, FR-014 is a fourth row for the OB list |

## Versions

**No version is pinned in this plan, and none is asserted as a fact.** The lockfile is the
record, it is written by the task that scaffolds `web/`, and FR-050 makes the production build
fail rather than resolve anything the lockfile does not name. Every claim above about a package's
behaviour is a claim about its documented API, and each carries its verification above where it
was not read off an installed copy.
