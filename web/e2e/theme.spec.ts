import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";

/**
 * FR-042's first half, which no unit test can reach: jsdom applies no CSS, so *the theme follows
 * the operating system's setting* is a claim only a real browser can check.
 *
 * The default mode -- no `data-theme` attribute, the one every reader who never opens the select
 * is in -- is the case that matters, and it is the one an assertion that stamps the attribute
 * first would never render.
 */
async function background(page: import("@playwright/test").Page): Promise<string> {
  return await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
}

test("the default theme follows the OS setting", async ({ page }) => {
  await offline(page);

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto(`/?as_of=${AS_OF}`);
  await expect(page.locator("main")).toBeVisible();
  const light = await background(page);

  await page.emulateMedia({ colorScheme: "dark" });
  const dark = await background(page);

  expect(await page.locator("html").getAttribute("data-theme")).toBeNull();
  expect(dark).not.toBe(light);
});

test("an explicit choice wins over the OS setting, in both directions", async ({ page }) => {
  await offline(page);
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(`/?as_of=${AS_OF}`);
  await expect(page.locator("main")).toBeVisible();
  const followingDark = await background(page);

  await page.selectOption("select", "light");
  expect(await background(page)).not.toBe(followingDark);

  await page.selectOption("select", "dark");
  expect(await background(page)).toBe(followingDark);
});
