---
name: "commit"
description: "Stage and commit changes to git at a green checkpoint. Runs the repo gates first and stops if any is red."
argument-hint: "Optional commit message, and optional list of files to stage"
metadata:
  author: "Mikola Parfenyuck"
  source: "adapted from lg-worktrees/self-review-2026/.claude/commands/commit.md"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Stage and commit changes with a user-provided or generated message, at a point where the
work is finished and the gates are green.

## Execution Steps

1. **Inspect the changes.** `git status --short`, then `git diff` and
   `git diff --staged`. Read what actually changed — the message describes the change,
   not the file list.

2. **Determine files to stage.**
   - If `$ARGUMENTS` names files, stage exactly those.
   - Otherwise stage all modified and untracked files.

3. **Run the pre-commit gates** (see below). Measured on 2026-09-05: about 40 s when the
   suite runs, a few seconds otherwise.
   - All green → continue.
   - Anything red → **stop**, show the failure, and ask before committing. This repo's
     constitution requires that every change lands green, so a red commit needs an
     explicit decision from the user rather than a silent pass.

4. **Check the repo-specific guards** (see below) and mention anything they flag.

5. **Determine the commit message.**
   - If `$ARGUMENTS` supplies one, use it verbatim.
   - Otherwise write one following the standards below.

6. **Commit immediately** — invoking this skill is the confirmation. Do not ask for a
   yes/no.
   ```bash
   git add [files]
   git commit -m "[message]"
   ```
   This repo works on `main` by design; feature work landing there is normal and does
   not need flagging.

7. **Show the result** in the format below.

## Pre-commit gates

Each of these stands for a blocking gate in CI (`.github/workflows/ci.yml`), so a red
one here means a red build. Run the cheap subset that matches what changed:

```bash
uv run ruff check . && uv run ruff format --check .   # any Python change
uv run mypy                                          # any Python change
uv run lint-imports                                  # any src/ change
uv run pytest -x -q -n auto                          # any src/ or tests/ change
uv run python scripts/check_provenance.py            # any data/ change
```

**The coverage floor is not a checkpoint gate.** `pytest --cov` runs single-process at
landing and in CI: it costs an order of magnitude more than the parallel run above
(`specs/README.md` step 3 carries the measurement) and answers a question about the branch
rather than about one commit.

For a docs- or spec-only change, skip straight to the guards.

Never "fix" a red gate by loosening it — not the coverage floor, not an
`.importlinter` contract, not a `contract`/`invariant` test. Those are compliance
tests for the constitution; weakening one is an amendment, not a commit.

## Repo-specific guards

Mention any of these in the result; none of them blocks the commit on its own.

- **`docs/reference/` is read-only.** It is the carried-over record of what was asked
  for. A diff touching it is almost always a mistake — flag it prominently.
- **`docs/REQUIRED_TESTS.md` tracks the definition of done.** If the commit lands a
  test that satisfies a row there, that row's box should be flipped and its test path
  recorded in the same commit. If it wasn't, say so.
- **New data under `data/`** needs `source`, `retrieved_on` and `verified_on`. The
  provenance script enforces it; an empty `verified_on` is fine and expected.
- **Nothing secret, and no real personal data, ever.** No `.env`, no credentials, and no
  figure that describes the owner's actual position. The repository holds **public facts**
  (fees, tax rates, inflation data) and **synthetic fixtures labelled as such**; the owner's
  own declarations under `data/seeds/`, `data/goals/`, `data/streams/`, `data/spendable/` and
  `data/composition/` are committed *because* what ships in them is synthetic and says so on
  its face. A file in one of those that stops being synthetic stops being committable. What a
  run *produces* stays out regardless (`data/user/`, `cache/`, `runs/` are gitignored — keep
  it that way). See `data/README.md` rule 5.
- **New dependency in `core/`** wants a justification in the message; the constitution
  asks for one.

## Commit Message Standards

- **Concise.** Subject line, then 2–4 lines of summary at most.
- **No walls of text.** No bulleted change inventories, no 20-line bodies.
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`,
  `ci:`, `perf:`.
- **Scope by layer or domain** where it clarifies: `core`, `ledger`, `tax`, `routes`,
  `instruments`, `decision`, `metrics`, `data`, `api`, `cli`, `specs`, `docs`, `ci`.
- **Reference the spec-kit feature** when the work belongs to one — the feature
  directory name, e.g. `(001-ledger-core)`. This repo has no issue tracker; the
  feature directory is the unit of work.
- **Do NOT add `Co-Authored-By` trailers**, or any other co-author or attribution line.
- Say *what changed and why*, not which files moved. When a commit encodes a decision,
  the why is the valuable half.

### Good

```
feat(ledger): add tax lots and per-currency cash accounts (001-ledger-core)

Lots carry cost in trade and base currency plus the FX rate used, so a
disposal can compute gain in both. Replaces the average-cost scalar, which
made per-disposal basis and loss carryforward unimplementable.
```

```
fix(tax): credit foreign withholding against PIT but not the levy

The military levy is not creditable, so a foreign dividend can suffer 15%
abroad and 5% at home. Covers E3 in REQUIRED_TESTS.md.
```

### Bad (too verbose)

```
feat(ledger): add tax lots and cash accounts

Key Changes:
- Added Lot dataclass
- Modified Position to hold lots
- Updated tests
[20+ more lines...]
```

## Output Format

### Success

```
✅ Committed.

commit a64e9f7
feat(ledger): add tax lots and per-currency cash accounts (001-ledger-core)

Gates: ruff ✓  mypy ✓  imports ✓  pytest ✓ (no coverage — see above)

Files changed: 3
- src/terezy/core/ledger/lots.py
- tests/invariants/test_lot_conservation.py
- docs/REQUIRED_TESTS.md
```

### Gates failed

```
⚠️  Not committed — gates are red.

mypy: src/terezy/core/ledger/lots.py:42 — incompatible return type

Fix, or tell me to commit anyway.
```

### Nothing to do

```
Nothing to commit — working tree is clean.
```

## Behavior Rules

- **Commit at green checkpoints, not mid-work.** A finished task or phase whose gates
  pass is a checkpoint; a half-finished edit is not. Never commit to checkpoint broken
  work.
- **No yes/no confirmation needed** — commit authority is standing (granted 2026-08-21).
  The one exception is a red gate, per step 3.
- **Never `git push`**, never open a PR, never amend, rebase, reset --hard or force
  anything unless the user asks for exactly that. The standing grant covers `commit`
  only — it is about not making the user click a button, not about rewriting history.
- **Never `git add -A` blindly past a guard** — if something looks like a secret or
  like per-user data, stop and say so.
- **Keep messages concise** and use conventional commits consistently.
- **No `Co-Authored-By` trailers.**

## Example Usage

```
# User supplies the message and the files
/commit "docs: record the tolerance policy" docs/REQUIRED_TESTS.md

# User wants a generated message for everything staged-and-unstaged
/commit
```

## Context

User input: $ARGUMENTS
