import { expect, test } from "@playwright/test";
import { openFirstCard } from "./card";
import { offline } from "./offline";

/** SC-007: every event and boundary the API sends is on the timeline — none dropped or merged. */
test("every served date is on the timeline, with both boundaries", async ({ page }) => {
  await offline(page);
  const served = await openFirstCard(page);

  const window = await page.locator("[data-window]").getAttribute("data-window");
  expect(window).toBe(`${served.window.start}/${served.window.end}`);
  await expect(page.locator("[data-event-kind='window-start']")).toHaveCount(1);
  await expect(page.locator("[data-event-kind='window-end']")).toHaveCount(1);

  const text = (await page.locator("[data-timeline]").textContent()) ?? "";
  for (const on of new Set(served.dates)) {
    const day = Number(on.slice(8, 10));
    expect(text, `${on} is on no marker`).toContain(`${String(day)} `);
    expect(text).toContain(on.slice(0, 4));
  }

  // FR-023: each wait is the **declared** days, not the gap between two dates.
  const segments = await page
    .locator("[data-segment]")
    .evaluateAll((held) => held.map((one) => one.textContent ?? ""));
  expect(segments.length).toBe(served.latencies.length);
  for (const [at, days] of served.latencies.entries()) {
    expect(segments[at]).toContain(`${String(days)} day(s)`);
  }
});
