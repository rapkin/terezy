import { expect, test } from "@playwright/test";
import { openFirstCard } from "./card";
import { offline } from "./offline";

/**
 * SC-001 and SC-004 on the screen: every bar's amount is the served flow of the same date and
 * kind, and the card's *money back* is the served `reaches`.
 */
test("each bar is the figure the API sent, and money back is `reaches`", async ({ page }) => {
  await offline(page);
  const served = await openFirstCard(page);

  const shown = await page.evaluate(() =>
    [...document.querySelectorAll("[data-bar]")].map((bar) => ({
      id: bar.getAttribute("data-bar") ?? "",
      // The thin space the formatter groups with, so a served amount can be matched plainly.
      text: (bar.textContent ?? "").replace(/\u2009/g, ""),
    })),
  );
  expect(shown.length).toBeGreaterThan(4);

  // The relation rather than a pinned figure: what the bar reads must be the served amount, to
  // the precision the one formatting module renders money at. Every served bar must be found —
  // a `continue` here made the whole loop vacuous once already.
  expect(served.bars.length).toBeGreaterThan(2);
  for (const bar of served.bars) {
    const drawn = shown.find((held) => held.id === bar.id);
    expect(drawn, `the card drew no bar ${bar.id}`).toBeDefined();
    // The grouping mark is stripped above, so the served amount reads as plain digits.
    expect(drawn?.text, `${bar.id} does not carry its served amount`).toContain(
      bar.amount.toFixed(2),
    );
  }

  const home = shown.find((bar) => bar.id === "home");
  expect(home?.text).toContain(served.reaches.toFixed(2).slice(-6));

  // SC-004: the card says the bars do not sum, rather than inviting the reader to add them.
  await expect(page.locator("[data-does-not-sum]")).toContainText("do not add up");
});

test("a card opens from any ranked row and closes back to the answer", async ({ page }) => {
  await offline(page);
  await openFirstCard(page);
  await page.locator("[data-close-card]").click();
  await expect(page.locator("[data-answer]")).toBeVisible({ timeout: 120_000 });
});
