# The pure modules and the components, and what each owes

## Pure modules

**`key.ts`** — one exported function turning a served key into a string, total and injective
over its five terms. It is not the engine's canonical form and must not be asserted equal to it
(plan F3).

**`membership.ts`** — over two answers:
- horizons matched by `(start, end)` exactly, and horizons belonging to one column named as such
  (FR-008);
- per matched horizon, the union of the two `non_dominated` sets with one mark each (FR-010);
- for a member on one front only, the other column's placement by contracts/api-reads.md's
  ordered lookup (FR-011);
- keys the pass **evaluated** in both columns and put on neither front, as a group (FR-012) — not keys merely `ranked`, which would fold in a withheld candidate.

It returns records; it renders nothing and computes no arithmetic.

**`difference.ts`** — the two served question records compared field by field, excluding `id`
and `asked_on` (plan F4). Returns the differing field names and whether `regime_id` is the only
one (FR-019 to FR-021).

**`regime.ts`** — a served `regime_id` resolved against the served scenarios, as one of: the
implicit regime; declared by exactly one scenario; declared by several. There is no
*declared by none*: such an answer does not load. The several case names all of them and is not
resolved by preference (FR-015).

## Components

| Component | Owes |
|---|---|
| `MembershipMark` | one mark, in text as well as in colour (FR-024); for a one-column member, the other column's placement from `membership.ts` and never a blank |
| `HorizonPair` | one matched horizon: both fronts, the union with its marks, the folded *on neither front* group, and a horizon belonging to one column stated as such. A refusing section renders that column's own reason and no rows (FR-014) |
| `ColumnHead` | the question id and its declaring file; the regime in the served string's own words; where the regime is a scenario's, the scenario, its transition marked as an assumption with the full rationale behind a disclosure, and what it carries instead of a source (FR-015 to FR-018, FR-022) |
| `QuestionDifference` | the differing fields, and the sentence saying whether the regime is the only one (FR-019 to FR-021) |
| `ComparePicker` | one entry per other declared question, labelled by regime and scenario; the named state when fewer than two are declared (FR-004 to FR-006) |
| `CompareStates` | loading, one column failed, both failed, and an undeclared id rendered as the served refusal for that column alone (FR-003, FR-023) |

Reused from 026 unchanged: the candidate card, the refusal group, the figure slot, the mark, and
the formatting module. This feature adds a column and a mark; it restyles nothing.

The FR-017 gap sentence lives on `ColumnHead`, and its shape — a caveat, or a refusal to render
the column at all — is Clarification 2's to settle.
