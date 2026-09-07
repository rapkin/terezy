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
export type Currency = Schemas["Currency"];
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

// ---------------------------------------------------------------------------
// 026: the answer, and the instrument read the kind tile comes from
// ---------------------------------------------------------------------------

/**
 * One member of a tagged union, selected by its tag.
 *
 * A filter over the generated types and never a declaration of one, which is why the tag is a
 * type argument rather than a property: an object type spelling the tag out inline would be
 * indistinguishable — to a reader and to `no-hand-written-types` — from a second copy of the
 * schema.
 */
type Tagged<Union, Tag extends string> = Extract<Union, { tag: Tag }>;

/** The envelope `/api/questions/{id}/answer` returns. */
export type TheAnswer = Tagged<Body, "envelopes.TheAnswer">;

/** The answer and its manifest, or the refusal for a question nobody declared. */
export type AnsweredQuestion = Tagged<TheAnswer["result"], "answer.AnsweredQuestion">;

/** What a question was answered with: the answer, or one of the eight ways it could not be. */
export type AnswerOrRefusal = AnsweredQuestion["answer"];

export type Answer = Tagged<AnswerOrRefusal, "answer.Answer">;

/** The eight members of that union that are not an answer. Each is a state, never a blank. */
export type AnswerNotGiven = Exclude<AnswerOrRefusal, Answer>;

export type Question = Answer["question"];
export type Subject = Answer["subjects"][number];
export type UndeclaredSubject = Tagged<Subject, "answer.UndeclaredSubject">;
export type StatedExclusion = Answer["excludes"][number];

export type HeldPosition = Answer["held"][number];
export type Valuation = HeldPosition["valuation"];

export type HorizonSection = Answer["sections"][number];
export type DateRange = HorizonSection["horizon"];
export type Standing = HorizonSection["standings"][number];
export type Reserve = HorizonSection["reserves"][number];

export type SectionOutcome = HorizonSection["outcome"];
export type CandidateSurvey = Tagged<SectionOutcome, "candidates.CandidateSurvey">;
export type SurveyNotRun = Exclude<SectionOutcome, CandidateSurvey>;

export type ComparisonOrRefusal = CandidateSurvey["comparison"];
export type Comparison = Tagged<ComparisonOrRefusal, "tuple.Comparison">;
export type NoComparison = Exclude<ComparisonOrRefusal, Comparison>;

export type TupleOutcome = Comparison["ranked"][number];
export type Tuple = TupleOutcome["key"];
export type UndeployedCash = NonNullable<TupleOutcome["undeployed"]>;
export type ImpliedRate = TupleOutcome["implied_rate"];
export type NominalRate = Tagged<ImpliedRate, "rates.NominalRate">;
export type RateRefused = Exclude<ImpliedRate, NominalRate>;
export type RefusedTuple = Comparison["refused"][number];
export type PairYieldedNoCandidate = CandidateSurvey["enumerated"]["no_candidate"][number];

export type SectionDominance = HorizonSection["dominance"];
export type DominanceResult = Tagged<SectionDominance, "dominance.DominanceResult">;
export type NoDominancePass = Exclude<SectionDominance, DominanceResult>;
export type BenchmarkStanding = DominanceResult["benchmark_standing"];
export type Indistinguishable = DominanceResult["indistinguishable"][number];
export type Separating = DominanceResult["separating"];
export type MemberRestsOn = Tagged<
  Separating,
  "dominance.SeparatingAssumptions"
>["per_member"][number];

/** A declared venue, and the closed vocabulary its kind is drawn from (026 FR-007). */
export type Venue = Tagged<Body, "venues.Venue">;
export type VenueKind = Venue["kind"];

/** The envelope `/api/instruments/{id}` returns. */
export type InstrumentRead = Tagged<Body, "envelopes.ReadOfInstruments">;

/**
 * What an instrument read answers when it is not a refusal.
 *
 * Two members, and only one of them carries `instrument_class` — the fund's declaration drops it
 * at load. That asymmetry is FR-006: the **tag** is the closed vocabulary a kind is keyed on, and
 * the class is `string` in the document and can carry no exhaustiveness guard.
 */
export type InstrumentDeclared = Exclude<InstrumentRead["result"], Refusal>;
