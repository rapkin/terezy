import { expect, test } from "@playwright/test";
import { openFirstCard } from "./card";
import { AS_OF, offline } from "./offline";

/** The separator the API renders a candidate key with. Nothing here composes a real one. */
const SEPARATOR = "|";

/** SC-008: no unrounded float reaches the card. SC-006: opening one issues one request. */
test("no unrounded float reaches a figure slot", async ({ page }) => {
  await offline(page);
  await openFirstCard(page);
  // The **slots**, not the whole card: a citation is served text and quotes legal prose with
  // numbers in it, so a scan over everything would fail on what the API sent rather than on
  // what this client rendered.
  const figures = await page
    .locator("[data-card] [data-figure]")
    .evaluateAll((held) => held.map((one) => one.textContent ?? ""));
  expect(figures.length).toBeGreaterThan(4);
  for (const figure of figures) expect(figure).not.toMatch(/\d\.\d{3,}/);
  expect(figures.some((figure) => /\d\.\d{2}/.test(figure))).toBe(true);
});

test("opening a card from the answer issues exactly one request", async ({ page }) => {
  await offline(page);
  const asked: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) asked.push(request.url());
  });
  await page.goto(`/?as_of=${AS_OF}`);
  await expect(page.locator("[data-answer]")).toBeVisible({ timeout: 120_000 });
  await page.waitForLoadState("networkidle");
  asked.length = 0;
  await page.locator("[data-open-card]").first().click();
  await expect(page.locator("[data-card]")).toBeVisible({ timeout: 120_000 });
  await page.waitForLoadState("networkidle");
  expect(asked.filter((url) => url.includes("/candidates/"))).toHaveLength(1);
  expect(asked).toHaveLength(1);
});

test("a key from another answer is a named state rather than an empty card", async ({ page }) => {
  await offline(page);
  const key = encodeURIComponent(`nope${SEPARATOR}nope`);
  await page.goto(`/questions/fifty-thousand-hryvnia/candidates/${key}?as_of=${AS_OF}`);
  const state = page.locator("[data-typed-state='card.NoSuchCandidate']");
  await expect(state).toBeVisible({ timeout: 120_000 });
  await expect(state).toContainText("reopen the answer");
});
