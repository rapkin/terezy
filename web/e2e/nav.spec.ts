import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";

/**
 * FR-027a, at the one place it is bypassed rather than broken.
 *
 * A window is a fact about the series it was read for. Carried onto the other one it arrives
 * already valid, so the destination's coverage redirect never fires and a chart is drawn for a
 * window the reader never chose for it — the implicit window with the parameter present.
 */
test("moving between the series routes takes each series' own coverage", async ({ page }) => {
  await offline(page);
  await page.goto(`/series/cpi?as_of=${AS_OF}&from=2025-01&to=2025-10`);
  await expect(page.locator("[data-chart='drawn']")).toBeVisible();

  await page.getByRole("link", { name: "official rate" }).click();
  // Awaited before the parameters are read: the destination redirects once to write its own
  // coverage in, and reading the URL before that lands would measure the click, not the route.
  await expect(page).toHaveURL(/\/series\/official-rate\?.*[?&]from=/);
  await expect(page.locator("[data-chart='drawn']")).toBeVisible();

  const url = new URL(page.url());
  expect(url.searchParams.get("from")).not.toBe("2025-01");
  expect(url.searchParams.get("to")).not.toBe("2025-10");
  // A rate series is keyed by calendar date; the window it arrived with was keyed by month.
  expect(url.searchParams.get("from")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(url.searchParams.get("to")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});
