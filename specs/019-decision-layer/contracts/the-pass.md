# Contract: the dominance pass

**Feature**: `019-decision-layer` | **Modules**: `terezy.core.decision.dominance`,
`terezy.core.primitives.tolerance`

## Signatures

```python
# terezy.core.decision.dominance


def dominance(
    outcome: SectionOutcome,
    *,
    withheld: Sequence[MoneyArrivesAfterHorizon],
    excludes: Sequence[StatedExclusion],
    objectives: ObjectiveSet,
    amounts: Mapping[str, Money],
) -> DominanceResult | DominanceRefused: ...


def relates(
    left: Sequence[Figure],
    right: Sequence[Figure],
    *,
    directions: Sequence[ObjectiveDirection],
    widths: Sequence[Width],
) -> PairVerdict: ...


Figure = MoneyFigure | DateFigure | FigureUnavailable
Width = MoneyWidth | DayWidth
```

`dominance` is pure: no clock, no I/O, no randomness, no solver, no seed (FR-024). `amounts` is
the question's own mapping of stream id to `Money`; it is what a fraction band resolves against
(FR-011d, research D6) and is read for nothing else.

**It takes the section's parts, not the section.** FR-027 puts the result **on** the frozen
`HorizonSection`, so a pass taking the finished record could not be called before the record
exists; `_section` already computes `withheld` and `excludes` before it constructs anything, and
passes the result into the constructor (research D9a). The parts are exactly what
`section_evaluated` reads off a finished section — the population less what 015 FR-030 withheld.

`relates` is FR-007's definition and **the only place it lives**. It takes figure vectors rather
than outcomes, which is what lets SC-004's battery run at three to five objectives over a
two-member criterion set (research D1).

**A figure carries its own kind, and the closeness rule follows it** (research D7a): two
`MoneyFigure`s go through `is_close` and a currency check, two `DateFigure`s compare exactly —
a date's slack is zero and a bare-float vector would silently apply the float comparison to an
ordinal. Two kinds at one position is a programmer error and raises.

`PairVerdict` is `LeftDominates | RightDominates | TooCloseToCall | Neither |
Incomparable(position, why)`. Two renames, both for the reason D10 gives: `TooCloseToCall` rather
than `Indistinguishable`, which names the per-candidate **record**; `PairVerdict` rather than
`Verdict`, which `core/tax/scheme.py` declares and `data/declarations/resolver.py` imports
unqualified.

`Incomparable`'s `why` is `FigureMissing(what) | DeliveredInTwoCurrencies(left, right)` — **no
criterion on either**, because `relates` is addressed by position and has no criterion to give.
The pass names the criterion when it lifts the verdict into an `IncomparablePair`, which carries it
once.

```python
# terezy.core.primitives.tolerance


def slack(left: float, right: float, *, tolerance: float = TOLERANCE) -> float: ...
```

The width `is_close` allows for those two figures: `max(tolerance · max(|left|, |right|),
tolerance)`. Not a redefinition of `is_close` — the two stand side by side and agree over finite
pairs by assertion (research D3).

## FR-007, stated once

*A* **dominates** *B* when, on every declared objective, *A* is **not worse than *B* by more than
the project comparison allows** — `is_close`, whose width is `slack` — and on **at least one** it is
**better by more than that objective's declared band**.

- The weak half goes through the project comparison so a last-bit difference on one objective does
  not withdraw a verdict a five-thousand-hryvnia gap on another earned.
- It goes through *that* comparison rather than a fresh absolute one because a second rule for when
  two amounts are the same money is a second tolerance policy.
- The band is in the **strict** half only. With the band in both halves the cycle window is
  *(p − 1)* **bands** wide and scales with the band, so no floor closes it; with the slack in the
  weak half it is *(p − 1)* **slacks** wide, which FR-011c's floor does close.

The relation is **irreflexive** while FR-011b holds and **asymmetric and acyclic** while FR-011c's
floor does — which is `band > slack` **and** `band >= (p − 1) · slack`, both conditions. The
second is vacuous at one and two objectives and is the whole guarantee above them (research D7).
It is **not transitive**, for any band, and the claim is not made: slack does not compose.
SC-004a plants a witness.

On a **date** objective the slack is exactly zero — the weak half is the project's float comparison
and a date is not a float — so FR-011c's floor reduces there to FR-011b's positivity.

## The three closeness rules, and their four sites (SC-007, FR-012)

| Rule | Where |
|---|---|
| the project comparison (`is_close`) | FR-007's weak half |
| its width (`slack`) | FR-011c's floor check |
| the declared band | FR-007's strict half, and the indistinguishability relation |

Nowhere else, and neither read where the other belongs. 010's tie groups are **read off** the
comparison record this feature carries through, never recomputed (FR-013).

## Where the result is carried

`HorizonSection.dominance`, beside the survey, replacing nothing in it (FR-027). The survey a
section reports equals, field for field, the one 014's `survey` returned (SC-016a).

`core/results/canonical.py::of_section` gains one element for it, so the answer digest is not blind
to what the section now reports. **This moves every answer digest**, and the golden is regenerated
deliberately with the diff read (Principle V, research D9).

## Rendered, and where (FR-029, FR-029a)

`cli/main.py` gains a block naming, per section: all three of FR-008's populations, the
incomparable pairs, each dominated candidate's dominator, each candidate's indistinguishable
neighbours, the benchmark's standing, and **010's tie groups**.

Both of 010's index fields address `Comparison.ranked`, which 015 FR-030 narrows afterwards.
`section_ties` and `section_beats_benchmark` resolve them to keys and drop the withheld, and the
CLI reads those rather than the indices. Where the narrowed count differs from the unnarrowed one
the difference is visible rather than silently taken.
