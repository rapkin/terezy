/**
 * What marks a figure, read off the response and never recomputed.
 *
 * `is_unverified` is the API's own field (020 FR-018): a client that computed it is free to get
 * the asymmetry backwards, and the answer would then depend on which client was reading.
 */
import type {
  Money,
  Provenance,
  Refusal,
  SourceRef,
  StaleSource,
  StalenessVerdict,
} from "@/api/shapes";
import { isRecord, tagOf } from "./narrow";

/**
 * The two claims a figure can carry. They are different claims and neither implies the other
 * (FR-012): a source verified last year is stale and not unverified; one retrieved this morning
 * and never checked is unverified and not stale.
 */
export type Mark =
  | { readonly tag: "unverified"; readonly source: SourceRef }
  | { readonly tag: "stale"; readonly source: SourceRef; readonly stale: StaleSource };

/**
 * The refusal tags, as a value.
 *
 * A mapped type over `Refusal["tag"]`, so a refusal the API adds leaves this object literal one
 * key short and the build red. That is FR-004's mechanism carried into the one place a tag has
 * to be tested at run time.
 */
const REFUSAL_TAGS: { readonly [Tag in Refusal["tag"]]: true } = {
  "envelopes.CategoryHasNoSuchId": true,
  "envelopes.FileNotRecorded": true,
  "envelopes.NothingDeclared": true,
  "envelopes.ScenarioNotDeclared": true,
  "envelopes.WindowMalformed": true,
  "envelopes.WindowOutsideCoverage": true,
  "middleware.HostNotDeclared": true,
  "middleware.NotOnLoopback": true,
  "service.PathNotServed": true,
};

export function isRefusal(value: unknown): value is Refusal {
  const tag = tagOf(value);
  return (
    tag !== null &&
    Object.hasOwn(REFUSAL_TAGS, tag) &&
    isRecord(value) &&
    typeof value["reason"] === "string"
  );
}

export function isProvenance(value: unknown): value is Provenance {
  return (
    tagOf(value) === "provenance.Provenance" &&
    isRecord(value) &&
    Array.isArray(value["sources"]) &&
    typeof value["is_unverified"] === "boolean"
  );
}

export function isMoney(value: unknown): value is Money {
  return (
    tagOf(value) === "money.Money" &&
    isRecord(value) &&
    typeof value["amount"] === "number" &&
    typeof value["currency"] === "string" &&
    isProvenance(value["provenance"])
  );
}

export function isStalenessVerdict(value: unknown): value is StalenessVerdict {
  return (
    tagOf(value) === "staleness.StalenessVerdict" &&
    isRecord(value) &&
    Array.isArray(value["stale"]) &&
    Array.isArray(value["assessed"])
  );
}

/**
 * Every mark the response puts on one provenance record.
 *
 * A source is marked *stale* only where the verdict names it, because staleness is a function of
 * `as_of` and a threshold the engine holds and the client does not.
 *
 * Measured 2026-09-05: 020 puts a verdict on an answer and on a candidate set, and on no
 * observations read -- so a series' points can render the unverified mark today and the stale one
 * only when that read starts carrying a verdict. The parameter exists so that day is a wiring
 * change rather than a rewrite.
 */
export function marksOf(
  provenance: Provenance,
  verdict?: StalenessVerdict,
): readonly Mark[] {
  const stale = new Map((verdict?.stale ?? []).map((held) => [held.source_id, held]));
  const marks: Mark[] = [];
  for (const source of provenance.sources) {
    if (source.verified_on === null) marks.push({ tag: "unverified", source });
    const overdue = stale.get(source.id);
    if (overdue !== undefined) marks.push({ tag: "stale", source, stale: overdue });
  }
  return marks;
}
