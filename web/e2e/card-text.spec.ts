import { expect, test } from "@playwright/test";
import { openFirstCard } from "./card";
import { AS_OF, offline } from "./offline";

/** SC-008: no unrounded float reaches the card. SC-006: opening one issues one request. */
test("no unrounded float reaches the document", async ({ page }) => {
  await offline(page);
  await openFirstCard(page);
  const text = (await page.locator("[data-card]").textContent()) ?? "";
  // A float that escaped the formatter carries more decimals than any rendered precision does.
  expect(text).not.toMatch(/\d\.\d{3,}/);
  expect(text).toMatch(/\d\.\d{2}/);
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
  await page.goto(
    `/questions/fifty-thousand-hryvnia/candidates/${encodeURIComponent("nope|nope")}?as_of=${AS_OF}`,
  );
  const state = page.locator("[data-typed-state='card.NoSuchCandidate']");
  await expect(state).toBeVisible({ timeout: 120_000 });
  await expect(state).toContainText("reopen the answer");
});
