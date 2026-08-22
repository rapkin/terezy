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

**Worktrees for parallel work.** Work that must not collide with `main`'s working tree
(parallel spec-writing, an isolated experiment) runs in a git worktree under
`.claude/worktrees/` (gitignored). Name the directory and the branch for the work, never
an agent id: `.claude/worktrees/spec-006-goals` on branch `spec/006-goals`. These are
short-lived plumbing, not feature branches: the work lands on `main` **squashed to one
commit per unit of work** (one spec, one feature) with a message written fresh to the
`/commit` standards — the branch's intermediate commits never reach `main`'s history —
and the worktree and its branch are removed right after.

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
```

All are blocking in CI. Run them before claiming a change is done.

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

An undocumented formula is an incomplete feature. Every metric carries a plain-language
definition; every tax figure links to its rule, source and verification date;
`docs/METHODOLOGY.md` is updated in the same change as the formula it describes.

## Privacy

This repo will hold a complete picture of one person's finances. No analytics, no CDN
calls, no telemetry, no secrets committed. Do not add a dependency that phones home.
Authentication is a blocking gate before the app listens on anything but loopback.
