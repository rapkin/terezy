/**
 * The one place a request is described.
 *
 * Every read is keyed by the parameters that are in the URL, so changing one re-queries rather
 * than recomputing anything already held (FR-022). No request carries a scenario: 020 FR-007b's
 * default is *no scenario in force* and the response names what it resolved under, so the client
 * renders that statement instead of choosing a world.
 */
import { queryOptions } from "@tanstack/react-query";
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
