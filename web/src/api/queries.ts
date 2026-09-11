/**
 * The one place a request is described.
 *
 * Every read is keyed by the parameters that are in the URL, so changing one re-queries rather
 * than recomputing anything already held (FR-022). No request carries a scenario: 020 FR-007b's
 * default is *no scenario in force* and the response names what it resolved under, so the client
 * renders that statement instead of choosing a world.
 */
import { queryOptions } from "@tanstack/react-query";
import { INSTRUMENTS, QUESTIONS } from "@/answer/endpoints";
import { API_PREFIX, request, type Answered } from "./client";

const STABLE = { staleTime: 30_000, retry: false } as const;

function path(...segments: readonly string[]): string {
  return [API_PREFIX, ...segments.map(encodeURIComponent)].join("/");
}

export function registryQuery(asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["registry", asOf],
    queryFn: () => request(path("registry"), { as_of: asOf }),
    ...STABLE,
  });
}

export function categoryQuery(category: string, asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["category", category, asOf],
    queryFn: () => request(path(category), { as_of: asOf }),
    ...STABLE,
  });
}

export function recordQuery(category: string, recordId: string, asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["record", category, recordId, asOf],
    queryFn: () => request(path(category, recordId), { as_of: asOf }),
    ...STABLE,
  });
}

export function observationsQuery(
  category: string,
  recordId: string,
  asOf: string,
  window: { readonly from: string; readonly to: string },
) {
  return queryOptions<Answered>({
    queryKey: ["observations", category, recordId, asOf, window.from, window.to],
    queryFn: () =>
      request(path(category, recordId, "observations"), {
        as_of: asOf,
        from: window.from,
        to: window.to,
      }),
    ...STABLE,
  });
}

/**
 * The answer to one declared question (026 FR-008).
 *
 * `/api/registry` is deliberately **not** read on this page: it is 2.6 MB and nothing on the
 * answer screen looks at a category index.
 */
export function answerQuery(questionId: string, asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["answer", questionId, asOf],
    queryFn: () => request(path(QUESTIONS, questionId, "answer"), { as_of: asOf }),
    ...STABLE,
  });
}

/** The declared question ids, so the screen reads which question it answers rather than naming one. */
export function declaredQuestionsQuery(asOf: string) {
  return categoryQuery(QUESTIONS, asOf);
}

/**
 * One instrument read, for the kind its tile is drawn from (026 FR-006).
 *
 * The same shape as `recordQuery` and a separate key on purpose: the answer screen asks for one
 * read per **distinct** member id, and sharing a key with the browser's record screen would make
 * a page that opened one instrument look like a page that had read them all.
 */
export function instrumentQuery(instrumentId: string, asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["instrument-kind", instrumentId, asOf],
    queryFn: () => request(path(INSTRUMENTS, instrumentId), { as_of: asOf }),
    ...STABLE,
  });
}

/**
 * One evaluated candidate's projection (027 FR-009, SC-006).
 *
 * Keyed by the three things in the URL, so opening a second card is a second request and
 * reopening the first is none. The key is the one the answer **published**: this client never
 * composes one, because a key it built would address a candidate the answer never evaluated.
 */
export function projectionQuery(questionId: string, candidateKey: string, asOf: string) {
  return queryOptions<Answered>({
    queryKey: ["projection", questionId, candidateKey, asOf],
    queryFn: () =>
      request(path(QUESTIONS, questionId, "candidates", candidateKey), { as_of: asOf }),
    ...STABLE,
  });
}
