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

/**
 * The served `rests_on` sentences that name this belief, across the members the screen shows.
 *
 * Measured 2026-09-07 the sentence the core composes is the belief's own rationale with a
 * preamble and the id in brackets in front of it — so a card that listed its `rests_on` in full
 * would carry the whole statement beside a mark that says the same thing, which is the copy
 * FR-024 forbids. The id is a **typed field** and it is looked for inside prose the core wrote;
 * nothing typed is derived from the match, only which line is a duplicate of which.
 */
export function sentencesNaming(
  belief: Belief,
  outcomes: readonly TupleOutcome[],
): readonly string[] {
  const found = outcomes.flatMap((outcome) => outcome.rests_on).filter(names(belief));
  return [...new Set(found)];
}

/** The sentences left once the ones stated with a belief are folded into that belief's line. */
export function withoutBeliefs(
  sentences: readonly string[],
  beliefs: readonly Belief[],
): readonly string[] {
  return sentences.filter((sentence) => !beliefs.some((belief) => names(belief)(sentence)));
}

function names(belief: Belief): (sentence: string) => boolean {
  return (sentence) => sentence.includes(`(${belief.id})`);
}

function distinct(beliefs: readonly Belief[]): readonly Belief[] {
  const seen = new Map<string, Belief>();
  for (const belief of beliefs) if (!seen.has(belief.id)) seen.set(belief.id, belief);
  return [...seen.values()];
}
