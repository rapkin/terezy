/**
 * Every request the client makes, and the three ways one can end.
 *
 * Same origin, always (FR-035): the paths carry the API's own `/api` prefix, so the browser
 * asks the origin that served the page in development behind a proxy and in production from one
 * container. Nothing here names a host.
 *
 * `not-json` is a state of its own rather than a parse failure folded into `unreachable`: a path
 * the API does not serve is answered by the SPA fallback with an HTML document, and reporting
 * that as a transport failure would name a healthy API as down (FR-006).
 */
export type Answered =
  | { readonly tag: "body"; readonly status: number; readonly body: unknown }
  | { readonly tag: "unreachable"; readonly detail: string }
  | { readonly tag: "not-json"; readonly status: number; readonly contentType: string | null };

export const API_PREFIX = "/api";

export function url(path: string, search: Readonly<Record<string, string>>): string {
  const query = new URLSearchParams(search).toString();
  return query === "" ? path : `${path}?${query}`;
}

export async function request(
  path: string,
  search: Readonly<Record<string, string>>,
): Promise<Answered> {
  let answer: Response;
  try {
    answer = await fetch(url(path, search), { headers: { accept: "application/json" } });
  } catch (failure) {
    return { tag: "unreachable", detail: failure instanceof Error ? failure.message : String(failure) };
  }
  const contentType = answer.headers.get("content-type");
  if (contentType === null || !contentType.includes("json")) {
    return { tag: "not-json", status: answer.status, contentType };
  }
  try {
    return { tag: "body", status: answer.status, body: await answer.json() };
  } catch {
    // A body that says it is JSON and is not is the API answering, not the API being down.
    return { tag: "not-json", status: answer.status, contentType };
  }
}
