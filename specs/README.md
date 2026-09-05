# Features: order, parallelism, and how one gets built

`features.toml` in this directory is the dependency graph. It is TOML on purpose —
`tomllib` parses it with no dependencies — and it answers two questions mechanically:

- **What can run in parallel?** Two features are parallelisable iff neither
  transitively `needs` the other. Today: after 002 lands, **003 ∥ 005**; **004 waits
  for 003** (the spendable-endpoint list is 003's declaration).
- **What is blocked?** A feature's *implementation* may not start until everything in
  its `needs` is `done` on `main`. **Spec-writing ignores `needs`** — specifying is
  always parallelisable, and disagreements between draft specs are resolved by
  clarification, not by ordering.

Update the `status` field **in the same commit** that changes the fact — the landing
commit flips it to `done`, the first implementation commit flips it to `in-progress`.
A stale graph misdirects every agent that reads it.

The permitted values, and what each means, are declared in `features.toml`'s own header
beside the data they describe. That header is the one to change.

## The lifecycle of one feature

Every feature goes through the same seven steps. None is optional.

1. **Worktree.** Create a readable worktree and branch named for the work —
   `git worktree add .claude/worktrees/006-goals -b feat/006-goals` (spec-only work:
   `spec-006-goals` / `spec/006-goals`). Never work on `main`'s tree directly while
   another lane is active; never name a worktree after an agent id.
2. **Spec Kit, in order.** `/speckit-specify` → `/speckit-clarify` (owner answers every
   `[NEEDS CLARIFICATION]`; never guess, never resolve a legal/tax/fee value from
   memory) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Tests first —
   a test written before its module failing with `ImportError` counts.

   **A new spec runs to about 300 lines and at most 30 functional requirements.** Past
   that, split it into two features and declare the `needs` edge between them: the limit
   is not a style preference but the size at which a spec stops being reviewable in one
   sitting and its requirements start contradicting each other. Specs already landed are
   not rewritten to fit it.
3. **Gates, by stage.** At a checkpoint commit: `ruff check` + `ruff format --check .`,
   `mypy`, `lint-imports`, `pytest -x -q -n auto`, and `check_provenance.py` when `data/`
   changed — all green before any commit (the `/commit` skill runs them). The coverage
   floor is deliberately **not** a checkpoint gate: `pytest --cov` runs single-process at
   landing and in CI, because it answers a question about the branch rather than about one
   commit and costs an order of magnitude more — measured 2026-09-05, 297 s against 36 s for
   the parallel run. Never loosen a gate to pass it.
4. **Condense.** Once the work is green, `/condense` over the branch diff: cut what does not
   earn its place, in prose and in code, on one rule — **one fact, one place**. Keep what
   prevents a named defect and what makes a wrong state unrepresentable. Before the review, not after, so the
   review reads what will land. It is also the only pass that re-reads every comment on the
   branch, which is where a stale claim otherwise survives to be found expensively later.
5. **Review — a blocking gate, capped at two rounds.** Before landing: a `/code-review`
   pass over the branch diff, plus the two manual reviews no gate can do — provenance
   marks surviving every figure-producing site, and every tolerance being the imported
   one. **Nothing lands on `main` without it**, and a review that was skipped is reported
   as skipped rather than quietly omitted.

   **A finding is one of exactly three things:** a wrong number, lost provenance, or a
   false guard — a guard whose message does not match what it does, or a test that passes
   for the wrong reason (it asserts nothing, or would survive the mutation it claims to
   catch). **A stale comment or docstring is deleted, not rewritten, and is not a
   finding.** Rewriting one is what removed the exit: features 015 and 016 took eight and
   seven rounds, and rounds 3–7 of 016 changed no line of `src/` — every fix falsified a
   nearby comment and the rewrite supplied the next round.

   **After round two the branch lands.** What is still open is recorded in the branch's
   report, and as a `[[future]]` entry or an issue in the spec when it is a defect. A
   recorded gap is an honest artefact; a third round is not.

   **A review covers the diff that lands.** Round one's fixes are read by round two, and
   round two's own fixes are read before it closes — the round's last act, not a third
   round. The cap counts rounds over one diff, so merging `main` in afterwards makes a
   different diff: a merge touching `src/` — a conflict there, or a change auto-merged into
   it — gets a round of its own, because either can move a figure the branch's tests pin. A
   merge touching only docs, specs, tests or data needs the full gates re-run, not a round.

   The gates and the review answer different questions. Green gates say the code runs,
   types and stays inside its layer. The review is what catches a guard whose refusal
   message is false, a test green because it asserts nothing, and a passing property whose
   scope quietly excludes the case it claims to cover — every one of which has happened
   here, on work whose gates were green.
6. **Land on `main`.** Two shapes, by the size of the unit:
   - **Spec-only or doc-only work: squash** to one fresh commit per unit (one spec =
     one commit); the branch's draft commits never reach `main`.
   - **A full feature implementation: a regular merge** (`git merge --no-ff`), keeping
     the branch's checkpoint commits — the phases and their green points are history
     worth keeping. Because those commits reach `main`, every commit on the branch is
     written to the `/commit` standards from the start; the merge is not a laundry.

   Either way, the landing change also flips the feature's rows in
   `docs/REQUIRED_TESTS.md`, updates `docs/METHODOLOGY.md` for any new formula, and
   flips `status` in `features.toml`.
7. **Clean up.** Remove the worktree and delete the branch immediately after landing.
   `main` is the only long-lived branch.

## Adding a feature to the graph

A feature the owner has accepted may enter the graph early as `status = "queued"` so
ordering is plannable before its spec exists; otherwise add its `[[feature]]` entry
(id = its `specs/` directory name) in the same commit that lands its spec. Declare `needs` honestly — a dependency discovered late is a schedule
surprise; when a dependency is non-obvious, say `why`. Record known follow-up work as
`[[future]]` entries so deferrals stay visible instead of living only inside spec prose.

**A new `note` on a `[[feature]]` or `[[future]]` entry is at most two lines**, and points
at the spec or the decisions file that carries the reasoning. The graph is read to answer
what is blocked and what is deferred; a note that argues its case there duplicates the spec
and is where the two drift apart. Notes already written are not rewritten.
