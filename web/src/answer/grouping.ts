/**
 * FR-022: refusals, withheld candidates and no-candidate pairs group by the **typed
 * discriminants their members carry**, never by matching reason text.
 *
 * Measured 2026-09-07, 27 `PairYieldedNoCandidate` rows share `(NothingConnects, route_in,
 * contract_usd)` and differ only in the instrument id inside each reason's own sentence — so a
 * grouping by text would put 27 lines on the screen and a grouping by reason **prefix** would be
 * a string match by another name.
 */
import type { PairYieldedNoCandidate, RefusedTuple } from "@/api/shapes";

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
 * The pair's own discriminants: the tag **first**, then the fields that member carries.
 *
 * The tag leads so that a second member added upstream forms its own groups rather than being
 * folded in with these; `side` is read after it, and a member that carries none turns this red
 * at the field rather than merging two reasons under one line.
 */
function noCandidateOn(row: PairYieldedNoCandidate): readonly Discriminant[] {
  return [
    { field: "why", value: row.why.tag },
    { field: "side", value: row.why.side },
    { field: "stream", value: row.stream_id },
  ];
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
