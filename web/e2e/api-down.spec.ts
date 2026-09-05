import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";
import { START_COMMAND } from "../src/api/client";

/**
 * FR-006 for the state the reader actually hits first: the API is not running.
 *
 * The dev server answers a proxied request it cannot forward with a 500 whose body is not this
 * API's; in production nothing answers at all. Both used to reach the screen as a generic
 * non-JSON answer explained as *the client's own fallback document* — a sentence that is false
 * here, and pointed the reader at the routing rather than at the process that is not running.
 *
 * The API is intercepted rather than stopped: the suite starts one server for every worker, and
 * a test that killed it would decide the outcome of whatever ran beside it.
 */
test.beforeEach(async ({ page }) => {
  await offline(page);
});

test("a proxy that cannot reach the API names it, and says how to start it", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "text/plain",
      body: "Error: connect ECONNREFUSED 127.0.0.1:8000",
    });
  });

  await page.goto(`/?as_of=${AS_OF}`);

  const alert = page.locator("[data-api-error='not-answered']");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(START_COMMAND);
  await expect(page.locator("[data-shape]")).toHaveCount(0);
  await expect(page.locator("[data-awaiting]")).toHaveCount(0);
});

test("a request that reaches nothing at all names it, and says how to start it", async ({
  page,
}) => {
  await page.route("**/api/**", async (route) => {
    await route.abort("connectionrefused");
  });

  await page.goto(`/?as_of=${AS_OF}`);

  const alert = page.locator("[data-api-error='unreachable']");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(START_COMMAND);
  await expect(page.locator("main")).not.toBeEmpty();
});
