---
name: "condense"
description: "Cut what does not earn its place from a feature's diff — prose and code — before it goes to review. One fact, one place. Keeps what prevents a defect or makes a wrong state unrepresentable."
argument-hint: "Optional diff target (default: the branch diff against main)"
metadata:
  author: "Mikola Parfenyuck"
user-invocable: true
disable-model-invocation: false
---

## Goal

**One fact, one place.** Every defect this pass exists to catch is the same shape: a second
copy of something, drifting out of step with the first, with nothing checking that they
agree.

A comment claiming what another module does is a second copy of that module's behaviour. A
helper that restates a computation is a second copy of the computation. Two fields holding
one truth are two copies of the truth. In this repository the duplicate has been where the
drift happened every single time — two constants that claimed to be one, two functions
carrying the same loop whose divergence was a top-severity finding, a mark stored twice and
coupled by nothing, three names for one number.

So the pass covers prose **and** code, and the constitution already asks for the second:
*"Complexity must be justified. The simple option is the default."* It runs **before** review
reads the branch, so the review spends its attention on what actually lands.

## When it runs

**After the implementation is green, before `/code-review`.** In that order for two reasons:
the review then reads the text that will land, and the review's own check on unverifiable
claims applies to the condensed version rather than to prose about to be deleted.

Never on a half-finished branch. Condensing is an edit like any other and ends at a green
checkpoint.

## Cut — code

- **A second name for a value that already has one.** A helper returning `len(x.items)` where
  `x.count` exists is a third spelling of one number, and the day they disagree nobody knows
  which is right.
- **A helper that only forwards.** One caller, no name worth having, no boundary crossed.
- **A guard that cannot fire.** Trace the callers before deciding; a guard removed on a wrong
  reachability argument is worse than a redundant one, so the report must say how you traced
  it. But a guard that provably cannot fire reads as protection and is not.
- **A parameter that only ever takes one value**, and the branch behind it.
- **Duplicated logic where the duplication is what lets two copies diverge.** Hoist it. This
  is the one that has cost the most here.
- **An indirection with one implementation and no declared second.** A registry of one, an
  interface nothing else implements, a factory with a single branch.

## Cut — prose

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

Cutting these is a worse defect than the verbosity, and the first three are the ones a
simplifying pass gets wrong:

- **A tagged union that makes a wrong state unrepresentable.** It looks like ceremony next to
  a boolean and a nullable field; it is the constitution. Never collapse `A | B` into a flag,
  never merge two records that are separate because a boundary runs between them, never widen
  a closed `Literal` into `str`.
- **A refusal that is typed rather than raised**, and a distinct refusal per reason. Two
  refusals that read alike are not duplicates if they answer different questions — the
  reader needs to know which one fired.
- **Duplication that is deliberate and stated.** Where a comment says *why* two things stay
  apart, the comment is the design; unifying them is a design change and belongs in review,
  not here.
- **A named constant with one use**, where the name is what makes the call site readable.

And in the prose:

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
2. Go file by file. For prose: **does this describe its own subject, and does it prevent a
   specific defect?** For code: **is this fact stated anywhere else, and does this construct
   make a wrong state unrepresentable?** Two noes means cut. One no means judge, and say
   which way in the report.
3. Where a cut removes a claim worth keeping, **convert it rather than delete it** — an
   assertion, a scan, a named constant. A check cannot go stale silently.
4. Run the gates. Prose is load-bearing more often than it looks.
5. Commit through `/commit` as one change: `docs(<scope>)` where only prose moved,
   `refactor(<scope>)` where code did.

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

- Lines removed per file, prose and code counted separately.
- Every claim converted into a check, and what the check is.
- Every block you judged rather than cut cleanly, and which way you went.
- For every guard you removed: how you traced that it cannot fire.
- Anything you found **false** while reading it. That is the point of the pass as much as the
  cutting is: prose nobody re-reads is where a stale claim survives, and this is the one step
  that re-reads all of it.

## Behaviour rules

- **Never cut to a line budget.** There is no target ratio. A dense module with a hard idea
  in it may be mostly prose and be right.
- **Simplicity is not fewer types.** This codebase buys correctness with types that make
  wrong states unrepresentable, and that trade is already justified. A pass that collapses
  them has not simplified anything — it has moved the complexity into the set of states a
  reader must hold in their head, which is the expensive place.
- **Never rewrite a kept sentence to be shorter at the cost of what it says.** Concision is
  not the goal; a comment that is true and needed is finished at whatever length it is.
- **Behaviour does not change.** Hoisting a duplicated block and deleting a dead one are in
  scope; renaming, reorganising, or improving something you merely dislike are not. If a cut
  changes what a test asserts, it was not a cut.
