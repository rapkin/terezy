<!--
Sync Impact Report
==================
Version change: 1.4.0 → 1.5.0 (2026-09-05)
Rationale: MINOR — guidance on review and on making a claim checkable materially changed.
Review is capped at two rounds, a finding is one of three named classes, prose the change
falsified is deleted rather than rewritten and is not a finding, and merging `main` into a
branch spends the review only when the merge touches `src/`. "A prose enumeration is a check
or it is not written" becomes "made mechanical only where necessary", which also drops the
requirement that every layer carry a docstring charter. Added because an audit measured
features 015 and 016 at eight and seven review rounds, with rounds 3–7 of 016 changing zero
lines in `src/`: each code fix falsified a nearby comment, the stale comment was counted a
finding of the same weight as a false guard, and its rewrite fed the next round. Invalidates
no spec, plan or data file; removes `tests/unit/test_package_layout.py::test_layer_documents_its_charter`
and no other test.

Version change: 1.3.0 → 1.4.0 (2026-09-03)
Rationale: MINOR — a founding decision discharged, not removed. D-B deferred the web UI
framework until the result schema had stabilised against real output; the registry now
declares real securities and a real published rate series, and the owner chose on
2026-09-03 (specs/decisions/2026-09-03-web-stack.toml): an HTTP layer inside api/ (feature
020) and a web client at web/ that is a client of the published schema and of nothing else
(feature 021). The deferral's term — the schema, not a framework, is the contract —
survives as a rule. Principle VII's release gate is unchanged. Invalidates no spec, plan or
test; the layer line `ui/` becomes `web/` and leaves the Python import rule, which cannot
see a TypeScript tree.

Version change: 1.2.0 → 1.3.0 (2026-08-30)
Rationale: MINOR — guidance materially expanded. "Documentation is part of the feature"
gains a prose discipline: a comment states a contract or an inferable-only reason, no
comment narrates a change, a prose enumeration of things declared elsewhere is a check or
it is not written, and prose volume is ratcheted by scripts/check_prose_budget.py. Added
because the restraining rules existed only in CLAUDE.md, which is subordinate, while this
document carried only the obligation to document — and measurement on 2026-08-30 found
32.8% of src/ is prose, a third of it restating code, another module, or this file.
Invalidates no spec, plan or test; the `⚙` convention it retires is enforced by nothing.
No principle was removed or redefined.

Version change: 1.1.0 → 1.2.0 (2026-08-24)
Rationale: MINOR — guidance materially expanded. Principle V gains "a golden file is
evidence, never a freeze": a golden's authority is over results, and its recorded input
digests are witnesses rather than terms, so correcting an input is supposed to move them.
Added because the inverse reading was found three times in three days (006, 009, 010),
each time by review and never by a gate — a golden that does not move is a green build.
No principle was removed or redefined.

Version change: 1.0.0 → 1.1.0 (2026-08-21)
Rationale: MINOR — new guidance added. A functional-style clause was added to
Engineering Standards (owner decision D-E). No principle was removed or
redefined, so no MAJOR bump. Invalidates nothing already written except the
Phase-1 design artifacts of feature 001, which were restated as functions over
records in the same change.

Version change: (none) → 1.0.0
Rationale: initial ratification. No prior constitution existed; the template
placeholders are replaced with project-specific governance derived from
docs/reference/SIMULATOR_SPEC.md and docs/reference/REWRITE_BRIEF.md.

Modified principles: n/a (initial adoption)
Added sections:
  - Core Principles I–VII
  - Architecture Constraints
  - Engineering Standards
  - Development Workflow
  - Governance
Removed sections: none
Follow-up TODOs: none — all placeholders resolved.

Founding decisions recorded (owner-approved 2026-08-21):
  D-A  Money is float64 with a documented tolerance policy (Principle IV).
  D-B  Delivery surface at foundation stage is core + typed API + CLI; the web
       UI framework is deliberately deferred (Architecture Constraints).
       DISCHARGED 2026-09-03 by the HTTP + web-client choice recorded there; its
       term — the schema is the contract — survives it.
  D-C  Fresh rewrite from the reference docs. No code is carried over from
       stock-bond-inv-simulation (Engineering Standards → Provenance of behaviour).
  D-D  CI gates: property-based invariant tests, golden result files, strict
       typing, and a coverage floor. Mutation testing is out of scope for now.
  D-E  Functional style: free functions over immutable records; no inheritance,
       no ABCs, no Protocol classes with methods (Engineering Standards).
-->

# terezy Constitution

terezy is a decision-support framework for a UAH-income investor: it declares the
rules that actually govern the money — instruments, funding routes, FX channels,
taxes, limits, risks — and searches the strategies those rules allow.

The product specification is `docs/reference/SIMULATOR_SPEC.md`. The engineering
audit and engine charter is `docs/reference/REWRITE_BRIEF.md`. This constitution
governs *how* that specification gets built; it does not restate it.

## Core Principles

### I. Honesty Over Precision (NON-NEGOTIABLE)

The tool must never present a number with more confidence than its inputs support.
This is the project's reason for existing, and it outranks every other principle.

- **No false optima.** Where a range of answers scores within noise, the output is
  the range. Reporting `51.3%` when anything in `40–60%` is indistinguishable is a
  defect, not a rounding choice.
- **Unverified values are marked, and the mark propagates.** Every rate, fee, yield
  and premium carries `value`, `source`, `retrieved_on`, `verified_on`. An empty
  `verified_on` renders visibly marked, and every figure derived from it inherits
  that mark. A derived figure that loses its parent's mark is a defect.
- **Assumption-driven and data-driven outputs are never mixed into one number.**
  Statistical metrics (volatility, Sharpe, Sortino) are emitted only for instruments
  with usable history. For an assumption-driven instrument the engine must refuse to
  emit them, not compute them from invented data.
- **Preference order for any answer**: dominance → range/distribution → break-even
  framing → point estimate. A point estimate is the last resort, permitted only
  where the inputs justify one.
- **Naive baselines are always scored and always shown**, and when nothing beats
  them the tool says so plainly.
- **Not advice.** The tool models tax to compare scenarios. It never produces
  filings, and no legal or tax value may originate from an implementer's or agent's
  memory — only from a cited source, entered as data.

*Rationale: the predecessor project produced confident charts that omitted the
largest terms in the real decision (a 23%-vs-0% tax split, a 5–10% one-way access
cost). A tool that is confidently wrong about money is worse than no tool.*

### II. Framework, Not Script (NON-NEGOTIABLE)

Adding an instrument, a venue, a route, a tax regime or a jurisdiction **must be a
data-only change**. If it requires an engine edit, the abstraction is wrong.

- Configurable domain knowledge lives in versioned, sourced, dated data files under
  `data/`, reviewed in git like code.
- Exactly four plugin interfaces sit behind that data: `Instrument`, `Provider`,
  `TaxRule`, `ReturnModel`. Adding a fifth requires an amendment to this
  constitution, not a pull request.
- There is an executable acceptance test for this property: a new instrument, route,
  tax class and jurisdiction added *in data only* must run the full pipeline and
  appear in the comparison. That test is the definition of "the abstraction is real".
- Data files **fail loudly at load time** on a malformed or unknown field, naming the
  file and the field. Silent defaulting is a defect.

*Rationale: this is the difference between a framework and one person's script, and
it is the only thing that makes the tool survive its own domain changing.*

### III. Pure Deterministic Core

The core is pure and deterministic. It performs no I/O, opens no network connection,
writes no file, renders nothing, and formats nothing.

- Same scenario + same data snapshot ⇒ identical results. Every stochastic path is
  explicitly seeded, and the seed is recorded in the run manifest.
- Orchestration lives in the API layer, never in the CLI and never in the core.
- Every displayed number is traceable to ledger events, and every ledger event to the
  rule and the input that produced it. A number that cannot be traced may not be
  displayed.
- Every run emits a **manifest**: scenario hash, code version, objective, seed, and
  the version and provenance of every input series and data file. A result without a
  manifest is not a result.

### IV. Reliability Through Stated Contracts

Reliability comes from invariants that are asserted, not from care.

- **Ledger invariants are executable, not documentary.** Cash conservation per
  currency per day; lot conservation; basis conservation; no negative quantities;
  realised gain = proceeds − consumed basis − allocated fees, in both currencies.
  These are property-based tests over generated event streams, not example tests.
- **Money is float64** (owner decision D-A), carried in a currency-tagged immutable
  record so values in different currencies can never be silently combined. The record
  constrains currency, not precision; the functions that combine money live beside it in
  its module (owner decision D-E), and they are the only way to combine it.
- **One tolerance policy, defined centrally.** Because money is float, the
  specification's "reproduces a hand-computed schedule exactly" is implemented as
  "within the project tolerance". That tolerance is defined in exactly one place and
  imported; a test that invents its own tolerance is a defect. Any comparison whose
  correctness depends on a tolerance looser than the project default must state why
  at the assertion site.
- **Failure is explicit.** No silent clamping, no silent truncation, no empty-dict
  "insufficient data" return, no synthetic fallback data. Every degraded outcome is a
  typed result carrying its reason, and every reason surfaces in the output.
- **Caches never hold synthetic or fallback data.** Cache entries carry provenance;
  a fetch failure never writes.

*Rationale: every one of these clauses corresponds to a confirmed defect in the
predecessor (`REWRITE_BRIEF.md` §4.2, D2/D5/D10/D13) or a structural limit that made
those defects unreachable by tests (§4.3, L1/L6).*

### V. Test-First for Financial Logic (NON-NEGOTIABLE)

No financial behaviour is implemented before a test that would fail without it.

Every financial rule lands with at least one of:
- a **hand-computed worked example**, checked into the repository alongside its
  arithmetic, so a human can verify the engine rather than trust it;
- a **property-based invariant** over generated inputs; or
- a **golden result file** for an end-to-end run on the offline snapshot.

**A golden file is evidence, never a freeze.** Its recorded input digests exist so a run
that changed can say *which* input changed. It follows that correcting an input is
*supposed* to move them, and that regenerating deliberately — with the diff read and the
changed lines quoted in the commit message — is the correct response rather than a thing to
be avoided. Declining to fix a citation, add a declared field or correct a value because a
golden would move inverts the artefact: the evidence becomes a constraint on the input, and
the file stops recording what a run does and starts dictating what the run may be given.
A golden's authority is over **results**; an input digest is a witness, not a term.

*Rationale: this shape appeared three times in three days — a research decision that turned
a golden into a constraint on a date (006), a data model shaped around not disturbing an
instrument digest (010), and a cited legal source left unimproved (009). In the last two the
digest of results would not have moved at all: the canonical encoding excludes provenance
by design, precisely so that filling in a `verified_on` later cannot disturb a figure. Every
instance was caught by expensive review and none by a gate — because a golden that does not
move is a green build.*

**A test that reads source files as text is a last resort, not a way of making a claim
checkable.** It is written only where it catches a named defect that the type system, a
golden or an ordinary test cannot, and it states that necessity in one sentence at its site.
The default when a claim does not clear that bar is to delete the prose making it, not to
write a scan for it: a scan pins the shape of the code rather than its behaviour, so it goes
red on a rename and stays green on a wrong number. The scans already written stay.

The acceptance tests enumerated in `SIMULATOR_SPEC.md` §9 and `REWRITE_BRIEF.md` §7
are the standing definition of done. They are not aspirational: a feature they name
is incomplete until its tests are green.

Tests never reach the network. The offline data snapshot is checked in, and CI runs
with networking unavailable.

### VI. Model the Whole Tuple

An investment option is a tuple, and modelling four of its five terms is the mistake
the predecessor made:

```
(instrument) × (funding route in) × (tax treatment) × (exit route out) × (risk class)
```

- Access cost is **never** quoted per instrument — only per
  `(instrument × income stream × route)`. The same purchase is cheap from a USD
  stream and expensive from a UAH one.
- Round-trip cost is the number that belongs in a comparison. A one-way figure may
  never be reported as if it were round-trip.
- Currency has three distinct roles — **base** (UAH), **tax** (UAH at the official
  rate on the transaction date), and **display** (user-switchable). Conflating any
  two of them is a defect. Changing the display currency must never change a realised
  amount, a tax figure, or the after-tax ranking.
- An asset that cannot be liquidated into spendable base currency at a reasonable
  cost is not worth its NAV, and must not be reported as if it were.
- Feasibility is enforced, never assumed: caps, minimum tickets, lock-ups, latency
  and route status. An infeasible plan reports the binding constraint instead of
  results. Silent execution of an infeasible plan is a defect of the highest severity.

### VII. Owner-Scoped and Private From Day One

The system holds a complete picture of one person's finances.

- Every scenario, portfolio, seed, goal and assumption row carries an `owner_id`
  from the first commit, while there is exactly one owner. Retrofitting tenancy is
  the expensive mistake; an unused column is free.
- Curated data (instruments, routes, tax packs) is version-controlled and shared.
  Per-user data (holdings, goals, assumptions, results) is separate from it. That
  boundary is what makes multi-user cheap later.
- No third-party analytics. No CDN calls. No secrets in the repository. No telemetry.
- **Release gate:** authentication must exist *before* the application listens on any
  interface other than loopback. This is a blocking gate, not a backlog item.

## Architecture Constraints

**Layering.** Dependencies point one way only, and the direction is enforced
mechanically in CI, not by convention:

```
core/     pure, deterministic, no I/O — instruments, routes, ledger, tax, metrics, analysis
data/     providers, caching with provenance, offline snapshot, run manifest
api/      orchestration + the typed result schema
cli/      thin client over api/
web/      a client over api/ over HTTP, never over core/ — a TypeScript tree outside the
          Python package (see below)
```

`core/` may not import from `data/`, `api/` or `cli/`. `data/` may not import from
`api/` upward. A violation fails the build. `web/` is absent from that rule deliberately:
`lint-imports` governs a Python package and cannot see a TypeScript one, and `core/` could
not import from it if it tried — so *the UI may not import the core* is enforced by the
client having no way to name it: its types are generated from the checked-in OpenAPI
document and from nothing else.

**Delivery surface (owner decision D-B, discharged 2026-09-03).** The foundation shipped
the core, a typed API exposing the result schema, and a thin CLI, with the web UI
framework deliberately unchosen until the result schema had stabilised against real
output. That condition is met — the registry declares real securities and a real
published rate series — and the owner has chosen: an HTTP layer inside `api/`, and a web
client at `web/` that is a client of its published schema and of nothing else
(`specs/decisions/2026-09-03-web-stack.toml`). **The deferral is discharged, not
deleted.** What it bought was that the schema, rather than a framework, is the contract,
and that survives the choice: the schema is a checked-in artefact regenerated under a
gate, so a client is generated from it and cannot drift from it; the client reads the
schema and never `core/`; and the UI computes no figure the schema does not carry,
because a figure computed in a client is a figure with no provenance. Principle VII's
release gate is unchanged — authentication before the application listens on anything
but loopback stays a blocking gate, and the delivery surface's job is to keep every
supported path from reaching that condition rather than to weaken it.

**Language and stack.** Python. The core keeps to the scientific stack (numpy,
pandas, scipy) and typed models for the declarative layer. Dependencies are pinned
and locked; adding one to `core/` requires justification in the pull request.

**Phasing** follows `SIMULATOR_SPEC.md` §10 (P0–P3). `REWRITE_BRIEF.md` P0 — ledger,
lots, cash accounts, multi-currency, provenance — is a prerequisite for the
specification's P0, not a parallel track.

## Engineering Standards

**Provenance of behaviour (owner decision D-C).** This is a fresh implementation from
the reference documents. No code is carried over from the predecessor project. The
knowledge that lived in its test suite is carried over as *requirements*, not as
code: the 12 preserved correctness behaviours (`REWRITE_BRIEF.md` §4.1) and the 18
confirmed defects (§4.2) are tracked as a checklist of required tests, each of which
must be independently re-derived and re-tested here. A behaviour on that list without
a test in this repository is an open gap, and the checklist states which.

**Quality gates in CI (owner decision D-D).** All are blocking:
- property-based invariant tests over the ledger and the tax engine;
- golden result files for end-to-end runs on the offline snapshot, so a refactor can
  be *proven* output-preserving;
- strict static typing on `core/`, and lint clean;
- a coverage floor, enforced by failing the build below it.

Mutation testing is explicitly out of scope for now, and may be proposed later as a
scheduled job rather than a per-change gate.

**Functional style (owner decision D-E).** Code is written as free functions over
immutable records. This is not a stylistic footnote — it is how Principle III's purity
requirement is actually achieved, since a function over a frozen record is trivially pure
while an object invites hidden state.

- **Records, not objects.** `@dataclass(frozen=True)` carrying only data is the
  encouraged shape. Behaviour attached to a record is not.
- **Free functions in modules, not methods.** `money.add(a, b)`, never `a.add(b)`.
  Modules provide the namespace that classes otherwise would.
- **No inheritance, no abstract base classes, no `Protocol` classes carrying methods.**
  A plugin interface is a *function signature*, or a frozen record of functions passed
  explicitly. The four permitted interfaces of Principle II are contracts on functions,
  not class hierarchies.
- **Tagged unions over exception hierarchies** for domain outcomes, dispatched with
  `match`. `raise` is for programmer errors — a currency mismatch, a violated invariant —
  never for a business result, which is a typed value per Principle IV.
- **Registries are mappings of functions**, not subclass dispatch.
- Enums and `Literal` are welcome: they are closed sum types, not objects.

`abc` sits in the core's forbidden imports in `.importlinter`, so the no-hierarchies rule
is mechanically enforced rather than merely stated.

**Documentation is part of the feature, and it is a cost.** An undocumented formula is
an incomplete feature; so is one buried in prose nobody can afford to read. Every metric
carries a plain-language definition; every tax figure links to its rule, its source and
its verification date; `docs/METHODOLOGY.md` is updated in the same change as the formula
it describes.

Beyond that, prose is held to the same standard as code:

- **A comment states its subject's contract, or the reason for a choice a reader could
  not infer. Nothing else.** Not what the next lines plainly say, not what another module
  does, not what this document already says.
- **No comment narrates a change.** Not what a previous version did, not which review
  found what, not what a paragraph used to say. The commit message holds that, and holds
  it without being read as a claim about the present.
- **A prose enumeration of things declared elsewhere is deleted.** A sentence counting
  cases, listing kinds, or naming what a registry contains is false the moment anything
  else moves, and nothing sees it. Making one mechanical instead is warranted only where
  the count catches a named defect nothing cheaper catches — `scripts/check_enumerations.py`
  exists because two modules put the observation kinds at five and at six while the data
  declared eleven.
- **Prose volume is ratcheted, not capped.** `scripts/check_prose_budget.py` records the
  comment-and-docstring share of each source tree and fails when it rises. Deleting is
  never required; adding prose faster than code is. Raising a ceiling is a deliberate
  edit, and the commit message says what the added prose prevents.

**Defect severity.** Wrong numbers, silently-swallowed failures, and lost provenance
are the top severity class regardless of how small the code change is. A silent
default, a silent clamp, and a silently stale value are all in that class.

## Development Workflow

**Specification first.** Work flows through Spec Kit: `/speckit-specify` →
`/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. A
feature without a specification in `specs/` does not get implemented. Ambiguity is
resolved by clarification before planning, not by an implementer's guess — and never
for a legal or tax value, which must come from a cited source.

**Every change lands green.** Each phase closes with a passing suite and updated
methodology docs.

**Review checklist, and a cap of two rounds.** Every change is reviewed before it lands,
against, at minimum: does it keep the core pure and deterministic; does provenance survive
end to end; is a new domain fact data rather than code; is every new number tested by a
worked example, an invariant, or a golden file; and does any new legal or tax value carry a
source.

The review runs **at most two rounds**, and a finding is one of exactly three things: a
wrong number, lost provenance, or a false guard — which includes a test that passes for the
wrong reason, meaning it asserts nothing or would survive the mutation it claims to catch.
**Prose is never a finding.** A comment or docstring the change falsified is deleted, not
rewritten. Whatever is still open after the second round is recorded — in the branch's
report, and as a `[[future]]` entry or an issue in the spec when it is a defect — and the
branch lands.

*Rationale: unbounded rounds have no exit. Features 015 and 016 took eight and seven rounds,
and rounds 3–7 of 016 changed no line of `src/` at all: each fix falsified a nearby comment,
the comment was scored like a false guard, and its rewrite supplied the next round's finding.
A cap converts that loop into a recorded gap, which is the honest artefact.*

**A review covers the diff that lands.** Round one's fixes are read by round two, and round
two's own fixes are read before it closes — that reading is the round's last act, not a third
round, and it is what keeps "covers the diff that lands" true under the cap.

**The cap counts rounds over one diff.** Merging `main` into the branch afterwards makes a
different diff, so when that merge touches `src/` — a conflict there, or a change auto-merged
into it — it gets one round of its own rather than being waved through as already reviewed. A
merge touching only docs, specs, tests or data needs the full gates re-run, not a round.

**Complexity must be justified.** The simple option is the default, and the pull
request says why it was insufficient when it is not taken.

## Governance

This constitution supersedes other practices and conventions in this repository.
Where it conflicts with a plan, a task list, or an implementer's preference, this
document wins; the correct response to a conflict is an amendment, not an exception.

**Amendment procedure.** An amendment is a pull request that changes this file,
states the rationale, and lists the artifacts it invalidates (specs, plans, tests,
data files). Amendments to a principle marked NON-NEGOTIABLE additionally require an
explicit statement of what the project gains by weakening it. Owner-approved founding
decisions are recorded in the header comment; superseding one is an amendment.

**Versioning policy.** Semantic versioning of this document:
- **MAJOR** — a principle removed or redefined in a backward-incompatible way.
- **MINOR** — a principle or section added, or guidance materially expanded.
- **PATCH** — clarification, wording, or non-semantic refinement.

**Compliance review.** Pull requests are verified against the review paragraphs above.
The `data-only extensibility` test (Principle II) and the ledger invariant suite
(Principle IV) are treated as compliance tests for this constitution and may not be
skipped, marked expected-to-fail, or deleted without an amendment.

**Runtime guidance.** Day-to-day development guidance for coding agents lives in
`CLAUDE.md`, which is subordinate to this document and may not contradict it.

**Version**: 1.5.0 | **Ratified**: 2026-08-21 | **Last Amended**: 2026-09-05
