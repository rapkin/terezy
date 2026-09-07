/**
 * *All of it by*: the served reading, and the two ways it is not a date.
 *
 * Read the way the dominance pass reads it (`core/decision/dominance.py::_figure`) — the last
 * arrival, refused where a remainder the way out would not carry is still behind. Taking
 * `span.end` instead would be a second reading of the same question: measured 2026-09-07 the two
 * agree on all 69 shipped rows, which is exactly the condition under which a disagreement ships
 * unnoticed.
 */
import type { TupleOutcome } from "@/api/shapes";

export type AllMoneyBack =
  | { readonly tag: "on"; readonly date: string }
  | { readonly tag: "not-all-of-it"; readonly mostOfItOn: string; readonly reason: string }
  | { readonly tag: "nothing-arrived" };

export function allMoneyBackOn(outcome: TupleOutcome): AllMoneyBack {
  const last = outcome.arrivals.at(-1);
  if (last === undefined) return { tag: "nothing-arrived" };
  const journey = outcome.undeployed?.journey;
  if (journey !== undefined && journey.tag === "tuple.RemainderStayed") {
    return { tag: "not-all-of-it", mostOfItOn: last.arrived_on, reason: journey.reason };
  }
  return { tag: "on", date: last.arrived_on };
}
