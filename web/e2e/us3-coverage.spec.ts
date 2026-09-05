import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";

/**
 * US3 scenario 4 and SC-007: a window past coverage plots the in-coverage observations **and**
 * shows the refusal for the rest, in one view.
 *
 * A refusal that replaced the chart would throw away what does exist; a chart that continued past
 * the last observation would draw what does not.
 */
test("a window past coverage plots what exists and refuses the rest, in one view", async ({ page }) => {
  await offline(page);
  await page.goto(`/series/cpi?as_of=${AS_OF}&from=2024-01&to=2030-01`);

  const chart = page.locator("[data-chart='drawn']");
  await expect(chart).toBeVisible();

  const refusal = page.locator("[data-refusal='envelopes.WindowOutsideCoverage']");
  await expect(refusal).toBeVisible();
  await expect(refusal).toContainText("interpolated");

  const covers = /covers ([\d-]+) \.\. ([\d-]+)/.exec((await refusal.textContent()) ?? "");
  expect(covers).not.toBeNull();
  const last = covers?.[2] ?? "";

  const rows = await page.locator("tbody tr").evaluateAll((held) =>
    held.map((row) => row.getAttribute("data-row") ?? ""),
  );
  expect(rows.length).toBeGreaterThan(0);
  expect(rows.filter((at) => at > last)).toEqual([]);
  expect(await chart.getAttribute("data-points")).toBe(String(rows.length));
});

test("a malformed window is the API's own refusal, not a window the client trimmed", async ({ page }) => {
  await offline(page);
  await page.goto(`/series/cpi?as_of=${AS_OF}&from=2030-01&to=2024-01`);
  await expect(page.locator("[data-parameter-error='from,to']")).toBeVisible();
});
