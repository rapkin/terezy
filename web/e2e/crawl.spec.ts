import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";
import { SERIES } from "../src/routes/series-map";

/**
 * The regression net for the whole class of "several odd things": the overview, every category,
 * every record of a category small enough to open them all, three of a larger one, and both
 * series -- driven once, failing on anything the reader would see as broken rather than on one
 * shape somebody thought to assert. The sampling is why the name says *a screen of every kind*
 * rather than *every screen*: on the shipped registry nothing is over the threshold, so it opens
 * all of them today, and a category that grows past it is sampled rather than timing the suite
 * out.
 *
 * What it watches for is exactly what a reader reports and no existing test catches together: a
 * console error, a request the page made that answered 4xx or 5xx, a main region with nothing in
 * it, a spinner still spinning when the network went quiet, and a figure slot rendered empty
 * where the API sent a value, a mark or a refusal (FR-006, FR-007, FR-008).
 */

/** The whole crawl is one test because the browser and the API are the expensive part. */
test.describe.configure({ timeout: 900_000 });

const RECORDS_PER_LARGE_CATEGORY = 3;
const LARGE = 30;

type Fault = { readonly where: string; readonly what: string };

test("a screen of every kind renders without an error, a 4xx, or an empty slot", async ({
  page,
}) => {
  await offline(page);
  const faults: Fault[] = [];
  // The screen is read at the moment the event fires, never off a variable the next navigation
  // has already reassigned: a request the previous page started can settle after the next one
  // has loaded, and a fault attributed there sends the reader to a screen that is fine.
  const seen = (what: string): Fault => ({ where: page.url(), what });

  page.on("console", (message) => {
    if (message.type() === "error") faults.push(seen(`console: ${message.text()}`));
  });
  page.on("pageerror", (error) => {
    faults.push(seen(`uncaught: ${error.message}`));
  });
  page.on("response", (answer) => {
    if (answer.status() >= 400) {
      faults.push(seen(`${String(answer.status())} from ${answer.url()}`));
    }
  });

  async function visit(path: string): Promise<void> {
    await page.goto(path, { waitUntil: "networkidle" });
    const main = page.locator("main");
    await expect(main, `${path} rendered a main region with nothing in it`).not.toBeEmpty();
    await expect(
      page.locator("[data-awaiting]"),
      `${path} was still reading when the network went quiet`,
    ).toHaveCount(0);
    await expect(
      page.locator("[data-api-error]"),
      `${path} could not read what it asked the API for`,
    ).toHaveCount(0);
    const blank = await page.evaluate(() =>
      [...document.querySelectorAll("[data-figure]")]
        .filter((slot) => (slot.textContent ?? "").trim() === "")
        .map((slot) => slot.getAttribute("data-figure") ?? "?"),
    );
    expect(blank, `${path} rendered a figure slot with nothing in it`).toEqual([]);
  }

  await visit(`/?as_of=${AS_OF}`);
  await visit(`/data?as_of=${AS_OF}`);
  // Asked of the API rather than read off the page, so a category the overview failed to render
  // is a screen this crawl still opens.
  const categories: string[] = await page.evaluate(async (asOf: string) => {
    const answer = await fetch(`/api/registry?as_of=${asOf}`);
    const body: { categories: { category: string }[] } = await answer.json();
    return body.categories.map((held) => held.category);
  }, AS_OF);
  expect(categories.length).toBeGreaterThan(0);
  for (const category of categories) {
    await visit(`/data/${category}?as_of=${AS_OF}`);
    const links = await page
      .locator(`[data-records] li a`)
      .evaluateAll((anchors) => anchors.map((anchor) => anchor.getAttribute("href") ?? ""));
    const reachable = links.length <= LARGE ? links : links.slice(0, RECORDS_PER_LARGE_CATEGORY);
    for (const href of reachable) await visit(href);
  }
  for (const series of SERIES) await visit(`${series.to}?as_of=${AS_OF}`);

  // 027 FR-029: a card is a screen of its own kind, so it joins the crawl. One is enough — every
  // card is the same components over a different candidate — and the key is read off the answer
  // rather than composed, because a key this test built would address a candidate nobody ranked.
  await page.goto(`/?as_of=${AS_OF}`, { waitUntil: "networkidle" });
  const card = await page
    .locator("[data-open-card]")
    .first()
    .getAttribute("data-open-card");
  expect(card, "the answer screen offered no card to open").not.toBeNull();
  await visit(
    `/questions/fifty-thousand-hryvnia/candidates/${encodeURIComponent(card ?? "")}?as_of=${AS_OF}`,
  );

  expect(faults, "the crawl saw these").toEqual([]);
});
