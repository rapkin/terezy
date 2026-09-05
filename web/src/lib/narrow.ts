/**
 * Guards from a decoded body to the generated shapes.
 *
 * Written as type predicates and not as casts: a guard tests and narrows, a cast asserts, and
 * FR-005 forbids the second. Each predicate checks the fields its renderer reads, so a body that
 * passes one is a body that renderer is total over.
 */
import type {
  FieldDescription,
  Listing,
  RecordRead,
  RegistrySummary,
  SeriesListing,
  SeriesWindow,
} from "@/api/shapes";

export function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function tagOf(value: unknown): string | null {
  if (!isRecord(value)) return null;
  const tag = value["tag"];
  return typeof tag === "string" ? tag : null;
}

function isFieldDescription(value: unknown): value is FieldDescription {
  return (
    tagOf(value) === "envelopes.FieldDescription" &&
    isRecord(value) &&
    typeof value["name"] === "string" &&
    typeof value["kind"] === "string" &&
    Array.isArray(value["of"])
  );
}

export function isRegistry(body: unknown): body is RegistrySummary {
  if (tagOf(body) !== "summary.RegistrySummary" || !isRecord(body)) return false;
  if (typeof body["as_of"] !== "string" || !Array.isArray(body["categories"])) return false;
  return body["categories"].every((held: unknown) => {
    const tag = tagOf(held);
    return (
      (tag === "summary.KeyedSummary" || tag === "summary.SingletonSummary") &&
      isRecord(held) &&
      typeof held["category"] === "string" &&
      isRecord(held["citations"]) &&
      isRecord(held["provenance"]) &&
      Array.isArray(held["files"])
    );
  });
}

export function isListing(body: unknown): body is Listing {
  const tag = tagOf(body);
  if (tag === null || !tag.startsWith("envelopes.ListingOf") || !isRecord(body)) return false;
  const ids: unknown = body["ids"];
  return Array.isArray(ids) && ids.every((held: unknown) => typeof held === "string");
}

export function isSeriesListing(body: unknown): body is SeriesListing {
  // Read before the narrowing, because a `Listing` has no `coverage` to index.
  const coverage: unknown = isRecord(body) ? body["coverage"] : undefined;
  return isListing(body) && isRecord(coverage);
}

const READ_TAGS = ["envelopes.ReadOf", "envelopes.DocumentOf"];

export function isRecordRead(body: unknown): body is RecordRead {
  const tag = tagOf(body);
  if (tag === null || !READ_TAGS.some((prefix) => tag.startsWith(prefix))) return false;
  if (!isRecord(body) || !("result" in body) || !("declared_in" in body)) return false;
  const fields: unknown = body["fields"];
  return Array.isArray(fields) && fields.every(isFieldDescription);
}

export function isSeriesWindow(body: unknown): body is SeriesWindow {
  const tag = tagOf(body);
  if (tag === null || !tag.startsWith("envelopes.WindowOf") || !isRecord(body)) return false;
  return "result" in body && tagOf(body["result"]) !== null;
}
