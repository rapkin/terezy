import { http, HttpResponse } from "msw";
/**
 * FR-044: the default handler set is empty, and a test declares what its own route answers.
 *
 * The bodies tests hand these come from `tests/fixtures.ts`, which is typed from the generated
 * document -- so a fixture that has drifted from the contract fails to compile rather than
 * passing.
 */
export const handlers = [] as const;

export const ORIGIN = "http://127.0.0.1";

type JsonBody = Parameters<typeof HttpResponse.json>[0];

export function answersWith(path: string, body: JsonBody, status = 200) {
  return http.get(`${ORIGIN}${path}`, () => HttpResponse.json(body, { status }));
}

export function answersWithText(path: string, text: string, contentType: string, status = 200) {
  return http.get(`${ORIGIN}${path}`, () =>
    HttpResponse.text(text, { status, headers: { "content-type": contentType } }),
  );
}

export function refusesToConnect(path: string) {
  return http.get(`${ORIGIN}${path}`, () => HttpResponse.error());
}
