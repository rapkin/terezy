import { expect, test } from "@playwright/test";
import { offline } from "./offline";
import { openTheAnswer } from "./answer";

/**
 * SC-008: the home page issues no request for `/api/registry`.
 *
 * It is 2.6 MB and nothing on this screen reads a category index. Asserted by failing the run on
 * one rather than by reading the source, because a query added anywhere in the tree would be
 * invisible to a scan of this route's module.
 */
test("loading the answer asks for no category index", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  const asked: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/registry")) asked.push(request.url());
  });
  await openTheAnswer(page);
  expect(asked, "the answer screen asked for the registry").toEqual([]);
});
