import { isRecord, tagOf } from "@/lib/narrow";
import type { SeriesRecord } from "./identity";

/**
 * The series records the API declares, as a value.
 *
 * A mapped type over the union's own tags, so a third series type leaves this literal one key
 * short and the build red -- which is the same mechanism `identityOf`'s switch relies on.
 */
const SERIES_TAGS: { readonly [Tag in SeriesRecord["tag"]]: true } = {
  "series.CpiSeries": true,
  "official_rate.OfficialRateSeries": true,
};

export function isSeriesRecord(value: unknown): value is SeriesRecord {
  const tag = tagOf(value);
  return (
    tag !== null &&
    Object.hasOwn(SERIES_TAGS, tag) &&
    isRecord(value) &&
    Array.isArray(value["observations"])
  );
}
