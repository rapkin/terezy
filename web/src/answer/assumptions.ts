/**
 * FR-020: what every shown member rests on is stated once per screen, and what one member does
 * not share is 019's own `separating.per_member[].rests_on`.
 *
 * A set difference over served strings, never a similarity judgement, and never a second split:
 * 019 computed which sentences separate a member, so the shared half is what its `rests_on`
 * holds beyond them. Measured 2026-09-07 that difference is identical for every member of every
 * section — which is the condition under which a client that recomputed the split instead would
 * agree today and disagree the first time a front is not uniform.
 */
import type { MemberRestsOn, Separating, Tuple, TupleOutcome } from "@/api/shapes";
import { sameTuple } from "./keys";

/** 019's per-member difference for one key, or nothing where the pass stated none. */
export function separatingFor(key: Tuple, separating: Separating): MemberRestsOn | undefined {
  if (separating.tag === "dominance.NoStatedAssumptionSeparatesThem") return undefined;
  return separating.per_member.find((held) => sameTuple(held.key, key));
}

/** What this member rests on that 019 did not name as separating it from its neighbours. */
export function sharedFor(outcome: TupleOutcome, separating: Separating): readonly string[] {
  const unique = separatingFor(outcome.key, separating)?.rests_on ?? [];
  return outcome.rests_on.filter((sentence) => !unique.includes(sentence));
}

/** The sentences every one of these members shares, in the first one's order. */
export function sharedAcross(perMember: readonly (readonly string[])[]): readonly string[] {
  const [first, ...rest] = perMember;
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
