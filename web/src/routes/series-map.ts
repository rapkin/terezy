/**
 * The routing map's series half: the two named exceptions FR-015a permits, and the only place in
 * `web/src` a category id is written down as a value.
 *
 * A chart is not a generic rendering -- it needs to know it has a date axis and a numeric axis,
 * and which series it is drawing -- so the exception is one file rather than a branch that can
 * grow back. `tools/category-scan-exceptions.txt` names this module and nothing under `/data/`.
 */
export const SERIES = [
  { to: "/series/official-rate", label: "official rate", category: "official-rates" },
  { to: "/series/cpi", label: "cpi", category: "cpi" },
] as const;

export type SeriesRoute = (typeof SERIES)[number];
