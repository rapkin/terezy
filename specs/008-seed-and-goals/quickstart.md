# Quickstart: verifying 008-seed-and-goals

**Date**: 2026-08-23

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. No network. **Every shipped seed and goal is a `SYNTHETIC FIXTURE`** — the
owner's real holdings and targets are unstated (§11 item 3) and will replace these files when
they arrive.

## The one-command check

```bash
uv run pytest -q
```

## 1. A seed is an ordinary ledger citizen

```bash
uv run pytest -m invariant -k "conservation or seed" -v
```

Cash, lot and basis conservation over **randomly seeded** ledgers (SC-005). This is the proof
of the feature's first design claim: a seed opens the ledger through the same path a purchase
takes, so the invariants count it without being taught it exists.

If a conservation property fails only for seeded ledgers, the seed is not going through the
ordinary opening path — do not add a special case to the invariant, fix the opening.

## 2. A guessed cost is a guessed tax

```bash
uv run pytest -m worked_example -k seeded -v
uv run pytest tests/contract/test_estimated_basis_propagates.py -v
```

- **SC-002** — disposing of a known-basis seed lot reproduces a hand-computed realised gain,
  arithmetic checked in beside the assertion.
- **SC-003** — with one lot's basis declared estimated, **100%** of the tax figures downstream
  carry the mark. Not most; all.

The mechanism to check if this fails: the estimated basis is a `SourceRef` in the lot's
provenance, so it rides the machinery that already propagates unverified market values. If a
figure is unmarked, something dropped a `Provenance` rather than something forgot a flag —
and the constitution calls that top severity.

## 3. The three modes agree, and none invents a tolerance

```bash
uv run pytest tests/invariants/test_goal_mode_consistency.py -v
```

**SC-001**, over a generated body of `(contribution, sum)` pairs — not one hand-picked pair.
Solve for the date, then for the sum from that date, and get the original back within the
**imported** tolerance. FR-013 forbids a mode defining its own, which is unusual enough to be
worth honouring literally: `grep` the module for a float literal near a comparison.

## 4. The date mode answers twice

```bash
uv run pytest tests/unit/test_solved_date_two_answers.py -v
```

The exact real-valued solution — the point at which the round trip above closes — **and** the
first calendar date the target is actually reached, each labelled. FR-015 forbids rounding
either into the other, so a test that finds only one field is finding a bug.

## 5. Shortfall honesty

```bash
uv run pytest tests/unit/test_goal_feasibility.py -v
```

| Case | Expected |
|---|---|
| All three fixed, target met | `Met` with the margin |
| All three fixed, target missed | `Missed` with **both** the amount short at the target date and the earliest date it would be reached |
| Target unreachable under the assumption | `Unreachable` with the reason — never a capped horizon, never a distant date |
| Solved contribution ≤ 0 | `NoContributionNeeded` with the margin — never a negative number as an instruction |
| Non-base target currency | Refused as **not yet modelled**, naming the missing FX modelling — never "invalid currency" |

No declared variable is ever adjusted to make a goal pass.

## 6. The owner boundary, and emptiness

```bash
uv run pytest -m contract -k "owner or empty or seed" -v
```

- **SC-007** — every seed and goal carries `owner_id`, and declaring or deleting them touches
  no curated file.
- **SC-008** — a run with **no** seeds and **no** goals completes normally: empty positions, no
  goal section, no refusal. This is deliberately unlike feature 003, where an empty registry
  dimension *is* a typed outcome — there an empty list and a mistyped path are
  indistinguishable, here they are not, and a person with no goal is an ordinary person.
- **SC-004** — the whole refusal battery: missing basis, unknown instrument, a reason on a
  known basis, fewer than two goal variables, a duplicate id, a malformed value.

## 7. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

`check_provenance.py` is fail-closed over the data tree: `data/seeds/` and `data/goals/` must
be in `EXEMPT_DIRS` **with their reasons recorded** — the owner's own records have nothing to
cite. If a reason there reads like a citation, a market value has got into a file that should
hold none.

## What "done" looks like

- All ten success criteria have a named test.
- `docs/REQUIRED_TESTS.md` flips **J1** and **J2** with their test paths recorded.
- `docs/METHODOLOGY.md` gains: what a seed lot is and why it needs a cost rather than a value;
  what an estimated basis marks and how far the mark travels; the solver's three modes with
  their stated conventions; and why the feasibility verdict is not a probability.
- Every shipped seed and goal file says `SYNTHETIC FIXTURE` on its face.
