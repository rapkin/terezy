import { expect, test } from "@playwright/test";
import { offline } from "./offline";

/**
 * SC-008a: a first load with a parameter missing ends at a URL carrying every parameter **that
 * route** takes.
 *
 * It asserts that the parameters arrive and that each is the one the route takes; it asserts no
 * parameter's *value*, which is the whole of FR-048's one exception for it -- the clock this
 * reads decides nothing the test looks at.
 */
test("a first load without as_of redirects once, with it written into the URL", async ({ page }) => {
  await offline(page);
  await page.goto("/");
  await expect(page).toHaveURL(/[?&]as_of=\d{4}-\d{2}-\d{2}/);
});

test("a series route without a window redirects with the API's own coverage in the URL", async ({ page }) => {
  await offline(page);
  await page.goto("/series/cpi");
  await expect(page).toHaveURL(/[?&]as_of=/);
  await expect(page).toHaveURL(/[?&]from=/);
  await expect(page).toHaveURL(/[?&]to=/);
  await expect(page.locator("[data-chart='drawn']")).toBeVisible();
});
