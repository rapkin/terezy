/**
 * What the API declares a series is, and what its values are in.
 *
 * FR-030: the axis states both, and the client infers neither -- a unit read as `1` where the
 * publisher quotes per `100` is wrong by two orders of magnitude and nothing downstream would
 * say so.
 */
import type { Declaration } from "@/api/shapes";

export type SeriesRecord = Extract<Declaration, { id: string; observations: readonly unknown[] }>;

export type SeriesIdentity = {
  readonly title: string;
  readonly valuesIn: string;
  readonly axis: string;
};

export function identityOf(series: SeriesRecord): SeriesIdentity {
  switch (series.tag) {
    case "series.CpiSeries":
      return {
        title: `${series.index} — ${series.country}, ${series.periodicity}`,
        valuesIn: series.base,
        axis: "period",
      };
    case "official_rate.OfficialRateSeries":
      return {
        title: `${series.pair[0]}/${series.pair[1]} — ${series.authority}`,
        valuesIn: `${series.pair[0]} per ${String(series.quotation_unit)} ${series.pair[1]}`,
        axis: "on_date",
      };
  }
}
