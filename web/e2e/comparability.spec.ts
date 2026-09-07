import { expect, test } from "@playwright/test";
import { offline } from "./offline";
import { openTheAnswer } from "./answer";

/**
 * SC-007: where a section's rows span different lengths, the banner heads that column and is
 * visible **without scrolling**.
 *
 * Only the positive half is here. Measured 2026-09-07 all three shipped sections have rows of
 * differing span, so an end-to-end negative would pass by asserting nothing — the negative is a
 * unit assertion against a fixture (`comparability-banner.test.tsx`).
 */
test("the comparability banner heads each column and is above the fold", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openTheAnswer(page);

  const banners = page.locator("[data-comparability-banner]");
  const many = await banners.count();
  expect(many).toBeGreaterThan(0);

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  for (let at = 0; at < many; at += 1) {
    const banner = banners.nth(at);
    await expect(banner).toContainText("annualised over its own span");
    const box = await banner.boundingBox();
    expect(box).not.toBeNull();
    expect(
      (box?.y ?? Number.POSITIVE_INFINITY) + (box?.height ?? 0),
      "the banner is below the fold",
    ).toBeLessThanOrEqual(viewport?.height ?? 0);
  }
});
