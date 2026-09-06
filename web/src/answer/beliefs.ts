/**
 * FR-024: the early-exit belief, once per screen per distinct belief id.
 *
 * Measured 2026-09-06 every member of every front carries `the_clean_price_holds`, so it
 * separates nothing and is a line rather than a badge — but the rule is *per distinct id*, not
 * *once*, because a registry whose members differ on it turns the line back into a badge. The
 * **ranked** population is not the front: 21 of 22 rows carry it and one does not, so the row
 * that does not carries no mark.
 */
import type { TupleOutcome } from "@/api/shapes";

export type Belief = { readonly id: string; readonly rationale: string };

/** Every belief one outcome leans on: the one it carried, and the one a sale was struck under. */
export function beliefsOf(outcome: TupleOutcome): readonly Belief[] {
  const held = [outcome.carried_quotation, outcome.sold_early?.assumption ?? null];
  return distinct(held.filter((one) => one !== null));
}

/** The distinct beliefs across every member the screen shows, in first-seen order. */
export function beliefsAcross(outcomes: readonly TupleOutcome[]): readonly Belief[] {
  return distinct(outcomes.flatMap(beliefsOf));
}

function distinct(beliefs: readonly Belief[]): readonly Belief[] {
  const seen = new Map<string, Belief>();
  for (const belief of beliefs) if (!seen.has(belief.id)) seen.set(belief.id, belief);
  return [...seen.values()];
}
