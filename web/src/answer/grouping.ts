/**
 * FR-022: refusals, withheld candidates and no-candidate pairs group by the **typed
 * discriminants their members carry**, never by matching reason text.
 *
 * Measured 2026-09-06, 26 `PairYieldedNoCandidate` rows share `(NothingConnects, route_in,
 * contract_usd)` and differ only in the instrument id inside each reason's own sentence — so a
 * grouping by text would put 26 lines on the screen and a grouping by reason **prefix** would be
 * a string match by another name.
 */
import type { PairYieldedNoCandidate, RefusedTuple } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";

/** One field of the typed reason, and what it says. Rendered as the group's line. */
export type Discriminant = { readonly field: string; readonly value: string };

export type Group<Member> = {
  readonly id: string;
  readonly on: readonly Discriminant[];
  readonly members: readonly Member[];
};

function collect<Member>(
  rows: readonly Member[],
  discriminantsOf: (row: Member) => readonly Discriminant[],
): readonly Group<Member>[] {
  const found = new Map<string, { on: readonly Discriminant[]; members: Member[] }>();
  for (const row of rows) {
    const on = discriminantsOf(row);
    const id = on.map((held) => `${held.field}=${held.value}`).join("|");
    const group = found.get(id);
    if (group === undefined) found.set(id, { on, members: [row] });
    else group.members.push(row);
  }
  return [...found].map(([id, group]) => ({ id, on: group.on, members: group.members }));
}

/**
 * The pair's own discriminants, narrowed on `why.tag` **first**.
 *
 * `side` is read only inside the arm that has one: reading it before narrowing would put a
 * `NothingNeedsToConnect` row — which carries no side — in the same group as the connects one.
 */
function noCandidateOn(row: PairYieldedNoCandidate): readonly Discriminant[] {
  const why = row.why;
  const stream: Discriminant = { field: "stream", value: row.stream_id };
  switch (why.tag) {
    case "candidates.NothingConnects":
      return [{ field: "why", value: why.tag }, { field: "side", value: why.side }, stream];
    case "candidates.NothingNeedsToConnect":
      return [
        { field: "why", value: why.tag },
        { field: "refused", value: why.refusal.tag },
        stream,
      ];
  }
  assertNever(why);
}

export function groupNoCandidates(
  rows: readonly PairYieldedNoCandidate[],
): readonly Group<PairYieldedNoCandidate>[] {
  return collect(rows, noCandidateOn);
}

/**
 * A refused tuple groups on its refusal's tag alone.
 *
 * The refusal's other fields name the thing refused — an instrument id, a route id — so folding
 * on them would make every group a group of one, which is the wall of text this folding exists
 * to answer.
 */
export function groupRefusals(rows: readonly RefusedTuple[]): readonly Group<RefusedTuple>[] {
  return collect(rows, (row) => [{ field: "refusal", value: row.refusal.tag }]);
}
