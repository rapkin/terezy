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

## The lifecycle of one feature

Every feature goes through the same six steps. None is optional.

1. **Worktree.** Create a readable worktree and branch named for the work —
   `git worktree add .claude/worktrees/006-goals -b feat/006-goals` (spec-only work:
   `spec-006-goals` / `spec/006-goals`). Never work on `main`'s tree directly while
   another lane is active; never name a worktree after an agent id.
2. **Spec Kit, in order.** `/speckit-specify` → `/speckit-clarify` (owner answers every
   `[NEEDS CLARIFICATION]`; never guess, never resolve a legal/tax/fee value from
   memory) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Tests first —
   a test written before its module failing with `ImportError` counts.
3. **Gates at every checkpoint.** `ruff check` + `ruff format --check .`, `mypy`,
   `pytest --cov`, `lint-imports`, `check_provenance.py` — all green before any commit
   (the `/commit` skill runs them). Never loosen a gate to pass it.
4. **Review, then iterate. This is a blocking gate, not a courtesy pass.** Before
   landing: a `/code-review` pass over the branch diff (correctness, then quality), plus
   the two manual reviews no gate can do — provenance marks surviving every
   figure-producing site, and every tolerance being the imported one. Findings are fixed
   on the branch; iterate until the review comes back clean. **Nothing lands on `main`
   without it**, and a review that was skipped is reported as skipped rather than
   quietly omitted.

   **The review must cover the diff that is actually merged.** A review is spent the
   moment the branch changes after it — commits fixing its own findings, or `main`
   merged in. Both need reviewing before landing, and the second is the one that gets
   forgotten: merging `main` in can turn a green gate red (a gate that grew stricter on
   `main`, meeting a file only this branch has) and can change a function the branch's
   tests pin. "The earlier round was reviewed" is a statement about a diff that no
   longer exists.

   The gates and the review answer different questions. Green gates say the code runs,
   types and stays inside its layer. The review is what catches a guard whose refusal
   message is false, a test green because it asserts nothing, a docstring teaching a rule
   the code abandoned, and a passing property whose scope quietly excludes the case it
   claims to cover — every one of which has happened here, on work whose gates were green.
5. **Land on `main`.** Two shapes, by the size of the unit:
   - **Spec-only or doc-only work: squash** to one fresh commit per unit (one spec =
     one commit); the branch's draft commits never reach `main`.
   - **A full feature implementation: a regular merge** (`git merge --no-ff`), keeping
     the branch's checkpoint commits — the phases and their green points are history
     worth keeping. Because those commits reach `main`, every commit on the branch is
     written to the `/commit` standards from the start; the merge is not a laundry.

   Either way, the landing change also flips the feature's rows in
   `docs/REQUIRED_TESTS.md`, updates `docs/METHODOLOGY.md` for any new formula, and
   flips `status` in `features.toml`.
6. **Clean up.** Remove the worktree and delete the branch immediately after landing.
   `main` is the only long-lived branch.

## Adding a feature to the graph

A feature the owner has accepted may enter the graph early as `status = "queued"` so
ordering is plannable before its spec exists; otherwise add its `[[feature]]` entry
(id = its `specs/` directory name) in the same commit that lands its spec. Declare `needs` honestly — a dependency discovered late is a schedule
surprise; when a dependency is non-obvious, say `why`. Record known follow-up work as
`[[future]]` entries so deferrals stay visible instead of living only inside spec prose.
