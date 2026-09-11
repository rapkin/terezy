/**
 * The outcome a published key names, found in the answer the reader already holds.
 *
 * The projection deliberately does not repeat what the outcome carries — `reaches`, the rate,
 * the span, the horizon, the remainder — so the card reads both and the two are joined here, on
 * the key the **API** published rather than on a key this client composed.
 */
import type { Answer, TupleOutcome } from "@/api/shapes";

export type Located =
  | { readonly tag: "found"; readonly outcome: TupleOutcome }
  | { readonly tag: "not-in-this-answer"; readonly key: string };

/**
 * Every candidate this answer evaluated, ranked or not.
 *
 * `not_comparable` as well as `ranked`, and a `BenchmarkUnavailable`'s `scored` too: a candidate
 * whose rate refused is a complete outcome with a published key, and the reader who most needs
 * the reason for a figure is the one who was not shown it.
 */
export function evaluatedIn(answer: Answer): readonly TupleOutcome[] {
  return answer.sections.flatMap((section) => {
    if (section.outcome.tag !== "candidates.CandidateSurvey") return [];
    const comparison = section.outcome.comparison;
    return comparison.tag === "tuple.Comparison"
      ? [...comparison.ranked, ...comparison.not_comparable]
      : [...comparison.scored, ...comparison.not_comparable];
  });
}

export function outcomeFor(key: string, answer: Answer): Located {
  const outcome = evaluatedIn(answer).find((held) => held.projection_key === key);
  return outcome === undefined
    ? { tag: "not-in-this-answer", key }
    : { tag: "found", outcome };
}
