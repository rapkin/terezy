# CLAUDE.md

Runtime guidance for coding agents. **Subordinate to
`.specify/memory/constitution.md`** — read that first; where this file and the
constitution disagree, the constitution wins and this file is the thing that gets fixed.

## What this project is

A decision-support framework for a UAH-income investor. It models the whole tuple —
`(instrument) × (funding route in) × (tax treatment) × (exit route out) × (risk class)`
— because the non-instrument terms are the largest numbers in the real decision.

- Product spec: `docs/reference/SIMULATOR_SPEC.md`
- Engine charter and predecessor audit: `docs/reference/REWRITE_BRIEF.md`
- Definition of done: `docs/REQUIRED_TESTS.md`

`docs/reference/` is read-only input material. Do not edit it; it is the record of what
was asked for.

## Workflow

Work flows through Spec Kit: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan`
→ `/speckit-tasks` → `/speckit-implement`. **Do not implement a feature that has no
specification in `specs/`.**

**Feature order and parallelism** are declared in `specs/features.toml` (parseable, no
dependencies), and the per-feature lifecycle — worktree, Spec Kit, gates, review,
squash-landing — is `specs/README.md`. Do not start implementing a feature whose
`needs` are not `done` on `main`; spec-writing is always parallelisable.

When a specification is ambiguous, clarify. Do not guess — and never guess a legal, tax
or fee value. Those come from a cited public source entered as data, or they do not go
in at all.

**Commit at green checkpoints.** Committing is authorised without asking; follow
`/commit`, which runs the gates and stops if any is red. A finished task or phase is a
checkpoint — a half-finished edit is not, and broken work never gets committed to
checkpoint it. Feature work lands on `main` by design; there are no feature branches.

**Every commit goes through the `/commit` skill** — in worktrees too. Never hand-roll
`git commit`: the skill owns the gates and the message standards (conventional commits,
concise body, no `Co-Authored-By` or other attribution trailers).

**Never `git push`**, never open a PR, and never amend, rebase or reset unless asked for
exactly that. The commit grant is about not making the user click a button, not about
rewriting history.

**`/condense` runs after the work is green and before the review.** It reads the branch diff
and cuts what does not earn its place, in prose **and** in code, on one rule: **one fact, one
place**. A comment claiming what another module does, a helper restating a computation, two
fields holding one truth — all the same shape, and in this repository the duplicate is where
the drift happened every time. It keeps what prevents a named defect and what makes a wrong
state unrepresentable; collapsing a tagged union into a flag is not simplification, it is
moving the complexity into the reader's head.

**Before the review, not after**, for two reasons: the review then reads what will land, and
its own check on unverifiable claims applies to the condensed version rather than to prose
about to be deleted. It is also the one pass that re-reads every comment on the branch, which
is where a stale claim otherwise survives.

**A code review is a blocking gate before anything lands on `main`.** Not a courtesy pass
and not something to note as skipped: run `/code-review` over the diff and iterate until it
comes back clean. It is the only gate that catches what the machine cannot — a guard whose
message is false, a test that passes for the wrong reason, a claim in a docstring that the
code stopped honouring. The commit grant does **not** extend to landing unreviewed work.

**The review must cover the diff that is actually merged.** If the branch changes after a
review — new commits fixing the findings, or `main` merged in — that review is spent, and
the new work is reviewed before landing. Merging `main` in counts: it can turn a gate red
that was green (a stricter gate on `main` meeting a file the branch added) and it can change
a function the branch's tests pin. "The earlier round was reviewed" is not a review of what
is being merged. Say plainly which diff was reviewed and which was not.

**Worktrees for parallel work.** Work that must not collide with `main`'s working tree
(parallel spec-writing, an isolated experiment) runs in a git worktree under
`.claude/worktrees/` (gitignored). Name the directory and the branch for the work, never
an agent id: `.claude/worktrees/spec-006-goals` on branch `spec/006-goals`. These are
short-lived plumbing, not feature branches: **spec-only work lands squashed** to one
commit per spec, while **a full feature implementation lands as a regular merge**
(`--no-ff`) keeping its checkpoint commits — which is why every branch commit follows
the `/commit` standards from the start. The worktree and its branch are removed right
after landing. Details: `specs/README.md`.

## Commands

```bash
uv sync --all-extras --dev
uv run pytest                                 # fast: no coverage instrumentation
uv run pytest --cov                           # coverage floor enforced (blocking in CI)
uv run pytest -m "contract or invariant"      # constitution compliance tests
uv run ruff check . && uv run ruff format .
uv run mypy                                   # strict
uv run lint-imports                           # architecture boundaries
uv run python scripts/check_provenance.py     # citations on curated data
uv run python scripts/check_prose_budget.py   # prose share ratchet (not in CI)
uv run python scripts/check_enumerations.py  # prose lists vs the sets they list (not in CI)
```

Every one but the last two is blocking in CI. Run them all before claiming a change is done.

## Non-negotiables, in the form you will actually hit them

**Never emit a number more confident than its inputs.** If a range of allocations
scores within noise, report the range. If an instrument is assumption-driven, refuse to
emit a Sharpe ratio for it rather than computing one from invented data. Prefer
dominance → distribution → break-even → point estimate, in that order.

**Provenance propagates.** A figure derived from an unverified value inherits the mark.
If you write a transform that drops the mark, that is a top-severity defect, not a
cosmetic one.

**Domain knowledge is data, not code.** Before adding a branch for a new instrument,
venue, tax rule or jurisdiction, stop: it belongs in `data/`. There are exactly four
plugin interfaces (`Instrument`, `Provider`, `TaxRule`, `ReturnModel`) and adding a
fifth requires a constitution amendment.

**The core stays pure.** No I/O, no network, no logging, no formatting, no `random`, no
`datetime.now()`. `.importlinter` will catch you, but understand *why*: determinism is
what makes results traceable and reproducible.

**Failure is explicit.** No silent clamp to zero, no silent default for a missing field,
no empty-dict "insufficient data", no synthetic fallback that gets cached. Every
degraded outcome is a typed result carrying its reason, and the reason surfaces in the
output.

**Money is `float64`** (owner decision D-A), wrapped in a currency-tagged value object.
The wrapper constrains *currency*, not precision — UAH and USD must never be silently
added. Because money is float, the spec's "reproduces a hand-computed schedule exactly"
is implemented as "within the project tolerance", and that tolerance is defined in
**one** place and imported. Do not invent a local tolerance; if you need a looser one,
say why at the assertion site.

**Cost is per `(instrument × income stream × route)`**, never per instrument. Round-trip
cost is what goes in a comparison; a one-way figure may never be presented as one.

**Currency has three roles** — base (UAH), tax (UAH at the official rate on the
transaction date), display (user-switchable). Conflating any two is a bug. The display
switch must never change a realised amount, a tax figure, or a ranking.

## Testing

Every financial behaviour lands with at least one of: a hand-computed worked example
with its arithmetic checked in, a property-based invariant, or a golden result file.
Write the test first — it must fail before the implementation exists.

Tests never reach the network. `tests/conftest.py` fails loudly on any socket attempt;
use the offline snapshot in `src/terezy/data/snapshot/`.

Test layout mirrors the definition of done:

```
tests/unit/            focused unit tests
tests/invariants/      property-based (Hypothesis) — ledger and tax invariants
tests/worked_examples/ hand-computed arithmetic, checked in beside the assertion
tests/golden/          end-to-end runs against checked-in golden results
tests/contract/        data-only extensibility and plugin/layer boundaries
```

Markers: `invariant`, `worked_example`, `golden`, `contract`, `slow`.

The `contract` and `invariant` suites are compliance tests for the constitution. Do not
skip, `xfail`, or delete one to get a build green — that requires an amendment.

**Update `docs/REQUIRED_TESTS.md`** when a required test lands: flip its box and record
the test path. That file is how we know what is actually covered.

## Documentation is part of the feature

The prose discipline is constitutional — read it there rather than here. What it means in
practice:

**Prose earns its place by preventing a named defect.** A decision taken against an obvious
alternative, a trap with a name, a gap stated with its date. Restating what the code says
earns nothing, and restating the constitution earns less: the copy is what drifts.

**Prefer the mechanical form.** A claim worth making is usually worth asserting — a scan
that pins how many places construct a record, an `emitted == applied` equality. A check
cannot go stale silently; a sentence can. That is why an enumeration of things declared
elsewhere is a check, or it is not written.

**`⚙` is retired.** Nothing reads it and nothing defines it; measured on 2026-08-30, the
blocks it introduced ran three times the length of ordinary prose and were five times as
likely to be changelog. Do not add one. Where you touch one, keep the decision it carries
and drop the marker and the history.

**Run `uv run python scripts/check_prose_budget.py`** before claiming a change is done. It
is a ratchet, not a cap: it fails only when a tree's prose share rises above the ceiling
recorded in the script, so deleting is never required and adding prose faster than code is.

Reviews treat prose that makes an unverifiable claim about elsewhere as a finding, at the
same weight as a guard whose message is false — because it is the same defect.

## Privacy

This repo will hold a complete picture of one person's finances. No analytics, no CDN
calls, no telemetry, no secrets committed. Do not add a dependency that phones home.
Authentication is a blocking gate before the app listens on anything but loopback.
