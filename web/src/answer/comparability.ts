/**
 * FR-014's predicate: were this section's rows measured over spans of the same length?
 *
 * The one comparison this screen makes, and it yields a **boolean**. The span *range* the CLI
 * composes is OB-16 and belongs to the API; a second client composing the same sentence is where
 * two readers get two answers.
 */
import type { DateRange } from "@/api/shapes";

/**
 * Days since 1970-01-01 for an ISO date, by Howard Hinnant's civil algorithm.
 *
 * Not `Date`: `new Date` is refused under `src/` (021 FR-021a) because a second clock read is
 * how the `as_of` in the URL and a figure's age come to disagree — and `Date` would also read
 * `2026-10-04` as UTC midnight, which is the previous day in any negative offset.
 */
function daysFromCivil(iso: string): number | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (parts === null) return null;
  const [, year = "", month = "", date = ""] = parts;
  const y = Number(year) - (Number(month) <= 2 ? 1 : 0);
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const m = Number(month);
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + Number(date) - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

/** The length of a served range in days, or nothing where either end is not an ISO date. */
export function spanDays(range: DateRange): number | null {
  const start = daysFromCivil(range.start);
  const end = daysFromCivil(range.end);
  return start === null || end === null ? null : end - start;
}

/**
 * Whether the banner heads this column.
 *
 * A range this client cannot read counts as *different*, because the banner states a condition
 * and saying nothing would be the stronger claim.
 */
export function spansDiffer(spans: readonly DateRange[]): boolean {
  const lengths = spans.map(spanDays);
  if (lengths.some((held) => held === null)) return lengths.length > 1;
  return new Set(lengths).size > 1;
}
