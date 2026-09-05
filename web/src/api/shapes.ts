/**
 * The response vocabulary, derived from the generated types rather than listed.
 *
 * Every alias below is computed from the generated document, so a member the API adds joins the
 * union without an edit here and turns every non-exhaustive switch red (FR-004, FR-010). A
 * hand-written list would be the second copy of the schema this feature exists not to have.
 */
import type { components, operations } from "./schema";

type Schemas = components["schemas"];

/** Every record the document declares, as one union. */
export type Body = Schemas[keyof Schemas];

export type Provenance = Schemas["provenance_Provenance"];
export type SourceRef = Schemas["provenance_SourceRef"];
export type StaleSource = Schemas["staleness_StaleSource"];
export type StalenessVerdict = Schemas["staleness_StalenessVerdict"];
export type FieldDescription = Schemas["envelopes_FieldDescription"];
export type CitationPolicy = Schemas["summary_KeyedSummary"]["citations"];
export type RegistrySummary = Schemas["summary_RegistrySummary"];
export type CategorySummary = RegistrySummary["categories"][number];
export type SeriesCoverage = Schemas["envelopes_SeriesCoverage"];
export type Money = Schemas["money_Money"];
export type OutsideCoverage = Schemas["envelopes_WindowOutsideCoverage"];

/** Every `result` any envelope carries, as one union. */
export type Result = Extract<Body, { result: unknown }>["result"];

type Operation = operations[keyof operations];

type JsonBody<Answered> = Answered extends { content: { "application/json": infer Sent } }
  ? Sent
  : never;

/**
 * Every body an endpoint may answer a **failure** with.
 *
 * The 200 of every operation is dropped rather than filtered afterwards: `/api/openapi.json`
 * answers an untyped document, and one `unknown` in a union swallows the whole union.
 */
type Refused<Op> = Op extends { responses: infer Answers }
  ? JsonBody<Omit<Answers, 200>[keyof Omit<Answers, 200>]>
  : never;

/**
 * Everywhere a refusal can arrive: a result, a failure body, the part of a window that fell
 * outside coverage, and the declaring-file slot.
 */
export type FailureBody = Refused<Operation>;

type Refusable =
  | Result
  | FailureBody
  | Extract<Body, { outside: unknown }>["outside"]
  | Extract<Body, { declared_in: unknown }>["declared_in"];

/**
 * A refusal is one of those carrying the engine's own reason. Derived rather than enumerated: a
 * refusal added anywhere joins this union, and `Refusal.tsx`'s switch stops compiling until it
 * has an arm (FR-004, SC-003).
 */
export type Refusal = Extract<NonNullable<Refusable>, { reason: string }>;

/** What a result is when it is not a refusal: the declaration itself. */
export type Declaration = Exclude<Result, Refusal>;

/** An envelope carrying one record and the description of its fields. */
export type RecordRead = Extract<Body, { fields: readonly FieldDescription[] }>;

/**
 * An envelope carrying a category's declared ids.
 *
 * Keyed on the three fields the list screen reads, because `ids` alone also describes a record
 * nested inside an answer, and one of those on this union would make the screen's narrowing a
 * claim it cannot keep.
 */
export type Listing = Extract<Body, { ids: readonly string[]; category: string; as_of: string }>;

/** A listing that also states each series' declared coverage (FR-027a's input). */
export type SeriesListing = Extract<Listing, { coverage: unknown }>;

/** A windowed read of a series. */
export type SeriesWindow = Exclude<
  Extract<Body, { result: unknown; category: string; as_of: string }>,
  RecordRead
>;

/** The observations a windowed read returned, beside whatever fell outside coverage. */
export type Observations = Extract<Result, { checked: unknown; observations: readonly unknown[] }>;

export type Observation = Observations["observations"][number];

/** What a windowed read actually checked, which is not the same as what it returned. */
export type Checked = Observations["checked"];
