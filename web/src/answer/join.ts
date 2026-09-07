/**
 * FR-009: the key-equality join, and FR-010's named state where it finds nothing.
 *
 * The unmatched arm is not defensive: `non_dominated` and the outcomes are arrays the API sends
 * separately, and a card built from `undefined` would render five empty figure slots rather than
 * say that the answer disagrees with itself.
 */
import type { Comparison, Tuple, TupleOutcome } from "@/api/shapes";
import { sameTuple } from "./keys";

/**
 * Every outcome the dominance pass could have placed.
 *
 * `not_comparable` as well as `ranked`, because `dominance.py::_population` is
 * `evaluated(comparison)` — a row whose `implied_rate` refused is a complete outcome and can be
 * non-dominated, since the objectives are money and date rather than the rate. Joining over
 * `ranked` alone would put "on the front and in no ranked row" on a card the API placed.
 */
export function placeable(comparison: Comparison): readonly TupleOutcome[] {
  return [...comparison.ranked, ...comparison.not_comparable];
}

export type Joined =
  | { readonly tag: "joined"; readonly outcome: TupleOutcome }
  | { readonly tag: "no-ranked-outcome"; readonly key: Tuple };

export function joinToOutcome(key: Tuple, ranked: readonly TupleOutcome[]): Joined {
  const outcome = ranked.find((held) => sameTuple(held.key, key));
  return outcome === undefined ? { tag: "no-ranked-outcome", key } : { tag: "joined", outcome };
}
