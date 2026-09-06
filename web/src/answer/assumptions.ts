/**
 * FR-020: what every shown member rests on is stated once per screen, and what one member does
 * not share is 019's own `separating.per_member[].rests_on`.
 *
 * A set difference over served strings, never a similarity judgement: 019 computed the split and
 * a second client computing it again is where two readers get two answers.
 */
import type { MemberRestsOn, Separating, Tuple, TupleOutcome } from "@/api/shapes";
import { sameTuple } from "./keys";

/** The sentences every one of these outcomes rests on, in the first one's order. */
export function sharedAcross(outcomes: readonly (readonly string[])[]): readonly string[] {
  const [first, ...rest] = outcomes;
  if (first === undefined) return [];
  return first.filter((sentence) => rest.every((held) => held.includes(sentence)));
}

/** What this member rests on beyond the shared set — the lines its own disclosure carries. */
export function beyondShared(
  outcome: TupleOutcome,
  shared: readonly string[],
): readonly string[] {
  return outcome.rests_on.filter((sentence) => !shared.includes(sentence));
}

/** 019's per-member difference for one key, or nothing where the pass stated none. */
export function separatingFor(key: Tuple, separating: Separating): MemberRestsOn | undefined {
  if (separating.tag === "dominance.NoStatedAssumptionSeparatesThem") return undefined;
  return separating.per_member.find((held) => sameTuple(held.key, key));
}
