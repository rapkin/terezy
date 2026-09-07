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
import { day } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";

export type AllMoneyBack =
  | { readonly tag: "on"; readonly date: string }
  | { readonly tag: "not-all-of-it"; readonly mostOfItOn: string; readonly reason: string }
  | { readonly tag: "nothing-arrived" };

/**
 * The date as a figure slot: it carries no provenance of its own — an `Arrival`'s `arrived_on`
 * is a bare date — so it wears the **outcome's** merged provenance and staleness, which is
 * OB-19's rule applied to the second figure that has no mark of its own. Where the served record
 * refuses the date, the slot refuses with it rather than showing the last arrival as if it were
 * the whole of what came back.
 */
export function AllMoneyBackFigure({ outcome }: { outcome: TupleOutcome }) {
  const back = allMoneyBackOn(outcome);
  if (back.tag === "on") {
    return (
      <FigureSlot
        state={{
          kind: "marked",
          figure: day(back.date),
          marks: marksOf(outcome.provenance, outcome.staleness),
        }}
      />
    );
  }
  return (
    <FigureSlot
      state={{
        kind: "refused-in-answer",
        tag: "all money back on",
        reason:
          back.tag === "nothing-arrived"
            ? "the outcome records no arrival at all."
            : `there is no date on which every hryvnia is back — ${back.reason}. Most of it is ` +
              `back on ${day(back.mostOfItOn)}.`,
      }}
    />
  );
}

export function allMoneyBackOn(outcome: TupleOutcome): AllMoneyBack {
  const last = outcome.arrivals.at(-1);
  if (last === undefined) return { tag: "nothing-arrived" };
  const journey = outcome.undeployed?.journey;
  if (journey !== undefined && journey.tag === "tuple.RemainderStayed") {
    return { tag: "not-all-of-it", mostOfItOn: last.arrived_on, reason: journey.reason };
  }
  return { tag: "on", date: last.arrived_on };
}
