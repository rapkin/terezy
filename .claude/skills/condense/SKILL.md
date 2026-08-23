---
name: "condense"
description: "Cut prose that does not earn its place from a feature's diff, before it goes to review. Keeps what prevents a defect, removes what only restates."
argument-hint: "Optional diff target (default: the branch diff against main)"
metadata:
  author: "Mikola Parfenyuck"
user-invocable: true
disable-model-invocation: false
---

## Goal

Half of `core/` is prose. Most of it earns its place; some of it is restatement, and some of
it is a claim about elsewhere that nothing checks and that goes stale the moment anything
moves. This step removes the second and third kinds **before** review reads the branch, so
the review spends its attention on what actually lands.

## When it runs

**After the implementation is green, before `/code-review`.** In that order for two reasons:
the review then reads the text that will land, and the review's own check on unverifiable
claims applies to the condensed version rather than to prose about to be deleted.

Never on a half-finished branch. Condensing is an edit like any other and ends at a green
checkpoint.

## Cut

- **A claim about behaviour outside the thing being annotated.** What another module does,
  what the registry contains, how many cases exist elsewhere, what a sibling feature will do.
  These are the ones that go stale silently — `CLAUDE.md`, *Documentation is part of the
  feature*. If the claim is worth making, it becomes an assertion; otherwise it goes.
- **Restatement of the code.** "Returns the sum" over a function that returns a sum.
- **Restatement of the constitution or of `CLAUDE.md`.** Both are already written down, and
  the copy is what drifts out of step with the original.
- **The same rationale repeated in every place a rule applies.** State it once, at the
  definition; the call sites do not each need it.
- **Motivational or scene-setting framing** that would read the same in any project.
- **A count, a list or a cross-reference that duplicates something the code already
  enumerates** — `"the three shapes"` above a `match` with four arms is how a docstring
  starts lying.

## Keep

Cutting these is a worse defect than the verbosity:

- **Why a decision was taken against an obvious alternative.** These are the sentences that
  stop someone helpfully reintroducing a defect.
- **A named trap.** `Leg.index` being per-route, a sort key that ties, a tolerance that
  cannot absorb a particular error. Someone paid for that sentence.
- **A stated gap, deferral or limitation, with its date** and what would close it.
- **The plain-language definition of a formula or metric, and a tax figure's rule, source and
  verification date.** Required by the constitution; not this step's to touch.
- **A refusal message.** It is output, not commentary.
- **Anything a test reads.** Several tests scan source text — header wording, prose-stripped
  scans, `check_methodology_refs.py`. The gates will catch it, but know it going in.

## Steps

1. Read the diff (`git diff main...HEAD` unless a target is given).
2. Go file by file. For each block of prose ask one question: **does this describe its own
   subject, and does it prevent a specific defect?** Two noes means cut. One no means judge,
   and say which way in the report.
3. Where a cut removes a claim worth keeping, **convert it rather than delete it** — an
   assertion, a scan, a named constant. A check cannot go stale silently.
4. Run the gates. Prose is load-bearing more often than it looks.
5. Commit through `/commit` as one change, message `docs(<scope>): cut prose that did not
   earn its place (<feature>)`.

## Gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy && uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_methodology_refs.py
uv run pytest --cov
```

A red gate after condensing means a cut removed something real. Restore it and say so —
never adjust the test to match the cut.

## Report

- Lines of prose before and after, per file.
- Every claim converted into a check, and what the check is.
- Every block you judged rather than cut cleanly, and which way you went.
- Anything you found **false** while reading it. That is the point of the pass as much as the
  cutting is: prose nobody re-reads is where a stale claim survives, and this is the one step
  that re-reads all of it.

## Behaviour rules

- **Never cut to a line budget.** There is no target ratio. A dense module with a hard idea
  in it may be mostly prose and be right.
- **Never rewrite a kept sentence to be shorter at the cost of what it says.** Concision is
  not the goal; a comment that is true and needed is finished at whatever length it is.
- Cutting is not refactoring. Do not move code, rename anything, or change behaviour.
