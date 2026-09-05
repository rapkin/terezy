/**
 * What a chart may draw, read off the observations the API returned.
 *
 * FR-031a is the reason this is a tagged result rather than a list: a **retrieval** carries a
 * `retrieved_on` per row -- when somebody looked, not when the value held -- so it has no time
 * axis, and drawing it would mean the client supplying one (FR-001 broken in the most
 * convincing-looking way available to a chart).
 */
import type { Observation } from "@/api/shapes";
import { isRecord, tagOf } from "@/lib/narrow";
import { isProvenance } from "@/lib/provenance";

export type Point = {
  readonly at: string;
  readonly value: number;
  readonly observation: Observation;
};

export type Plotted =
  | { readonly tag: "points"; readonly points: readonly Point[] }
  | { readonly tag: "not-a-series"; readonly reason: string };

/** Where one observation sits on the axis it declares, by the field the API keys it on. */
function keyOf(observation: Observation): string {
  switch (observation.tag) {
    case "series.CpiObservation":
      return observation.period;
    case "official_rate.OfficialRateObservation":
      return observation.on_date;
  }
}

function isObservation(value: unknown): value is Observation {
  const tag = tagOf(value);
  if (tag !== "series.CpiObservation" && tag !== "official_rate.OfficialRateObservation") {
    return false;
  }
  return (
    isRecord(value) &&
    typeof value["value"] === "number" &&
    isProvenance(value["provenance"]) &&
    typeof value[tag === "series.CpiObservation" ? "period" : "on_date"] === "string"
  );
}

export function plotted(observations: readonly unknown[]): Plotted {
  const points: Point[] = [];
  for (const held of observations) {
    if (isObservation(held)) {
      points.push({ at: keyOf(held), value: held.value, observation: held });
      continue;
    }
    if (isRecord(held) && "retrieved_on" in held) {
      return {
        tag: "not-a-series",
        reason:
          "these rows carry a retrieved_on per row — when somebody looked, not when the value " +
          "held — so there is no time axis to draw them against.",
      };
    }
    return {
      tag: "not-a-series",
      reason: `${tagOf(held) ?? "an untagged row"} is not an observation this API declares.`,
    };
  }
  return { tag: "points", points };
}

export type Cell = { readonly at: string; readonly value: number | null };

/**
 * The chart's own rows: the returned points, with a break at every period the API **named** as
 * missing inside them.
 *
 * Only named-and-interior breaks are inserted. A period the API did not name is not a gap this
 * client knows about, and a break past the last observation would be a claim about coverage the
 * `outside` refusal already makes (FR-028, FR-029).
 */
export function cells(points: readonly Point[], missing: readonly string[]): readonly Cell[] {
  if (points.length === 0) return [];
  const first = points[0]?.at ?? "";
  const last = points[points.length - 1]?.at ?? "";
  const held = new Set(points.map((point) => point.at));
  const breaks = missing.filter((at) => at > first && at < last && !held.has(at));
  const rows: Cell[] = [
    ...points.map((point) => ({ at: point.at, value: point.value })),
    ...breaks.map((at) => ({ at, value: null })),
  ];
  return rows.sort((left, right) => (left.at < right.at ? -1 : left.at > right.at ? 1 : 0));
}

/** How many line segments the cells above actually draw: a run of two adjacent values. */
export function segments(rows: readonly Cell[]): number {
  let drawn = 0;
  for (let at = 1; at < rows.length; at += 1) {
    if (rows[at - 1]?.value !== null && rows[at]?.value !== null) drawn += 1;
  }
  return drawn;
}
