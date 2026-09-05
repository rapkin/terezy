# Quickstart: checking that the answer stopped having a head

Feature `019-decision-layer`. What to run, and what it must say.

## Prerequisites

`fix/coupon-inside-the-window` and `feat/real-only-registry` are on `main`. Without the second,
every section is `BenchmarkUnavailable` and the pass refuses under FR-018 rather than producing a
set; without the first, the money objective is read off a figure that is about to move
(research D12).

```bash
uv sync --all-extras --dev
```

## The gates

```bash
uv run pytest                                     # fast, no coverage instrumentation
uv run pytest --cov                               # the coverage floor is blocking
uv run pytest -m "contract or invariant"          # the constitution's compliance suites
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_prose_budget.py
uv run python scripts/check_enumerations.py
```

`check_provenance.py` must stay green **without an edit**: `data/objectives/` is already exempt
with its reason, and the new files carry no citation keys (FR-004).

## The answer, read

```bash
uv run terezy --data-root data --question fifty-thousand-hryvnia --as-of 2026-09-05
```

Per horizon section the output must carry, by **candidate id and never by position**
(FR-029, FR-029a, SC-016):

- the non-dominated set;
- every dominated candidate with at least one candidate that dominates it named, and the
  objectives that decided it;
- every *not placed* candidate with the objective it could not be read on;
- the incomparable pairs, each naming what made it so;
- each candidate's indistinguishable neighbours — a relation, **never** a partition;
- the benchmark's standing: *nothing dominates the hurdle*, or the members that dominate it;
- 010's tie groups, and its beats-the-hurdle verdict, both narrowed to the reported population.

`inzhur_miltech` is withheld from every section of the owner's question (015 FR-030) and must
appear in **none** of the above — it is inside `Comparison.beats_benchmark` at all three horizons,
which is the defect FR-029a exists to stop.

## What the numbers should be, and why none of them is written down

Measured on 2026-09-03 against the post-registry tree and **before** the coupon fix: the
non-dominated sets held 2, 3 and 10 members at one, three and twelve months, and 13, 18 and 23
reported candidates beat the hurdle. The coupon fix moves `TupleOutcome.reaches`, so the first
three are expected to move.

No test hard-codes any of them (SC-001). Every count is derived from the registry and the objective
set the test loads, which is what keeps the suite honest across a data change rather than pinning
the tool to a measurement.

## Regenerating the golden

```bash
TEREZY_UPDATE_GOLDEN=1 uv run pytest tests/golden/test_the_answer.py
git diff tests/golden/the_answer.golden.txt
```

Read the diff and quote the changed lines in the commit message. A golden is evidence, never a
freeze (Principle V): the answer digest moves because `of_section` now encodes the dominance
result, and that is what it is supposed to do.

## Checking the owner's own declaration is his

```bash
uv run pytest tests/worked_examples/test_the_owners_objectives.py
```

SC-001a asserts, **by value**, that `data/objectives/owner-001.toml` holds CL-1's two criteria in
their directions and CL-2's two bands — a fraction of `0.0001` on the money and `7` days on the
date. Every other criterion in this feature passes over *an* objective set; this is the only one
that notices his answers never reaching the file.
