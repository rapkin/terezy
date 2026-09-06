import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";
import { START_COMMAND } from "../src/api/client";

/**
 * FR-006 for the state the reader actually hits first: the API is not running.
 *
 * The dev server answers a proxied request it cannot forward with a 500 whose body is not this
 * API's; in production the fetch itself fails. Each is its own named state, because what the
 * reader has to act on is the process, and a screen that named the routing instead would send
 * them to the one place the fault is not.
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
