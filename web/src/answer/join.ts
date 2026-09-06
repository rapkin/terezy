/**
 * FR-009: the key-equality join, and FR-010's named state where it finds nothing.
 *
 * The unmatched arm is not defensive: `non_dominated` and `ranked` are two arrays the API sends
 * separately, and a card built from `undefined` would render five empty figure slots rather than
 * say that the answer disagrees with itself.
 */
import type { Tuple, TupleOutcome } from "@/api/shapes";
import { sameTuple } from "./keys";

export type Joined =
  | { readonly tag: "joined"; readonly outcome: TupleOutcome }
  | { readonly tag: "no-ranked-outcome"; readonly key: Tuple };

export function joinToOutcome(key: Tuple, ranked: readonly TupleOutcome[]): Joined {
  const outcome = ranked.find((held) => sameTuple(held.key, key));
  return outcome === undefined ? { tag: "no-ranked-outcome", key } : { tag: "joined", outcome };
}
