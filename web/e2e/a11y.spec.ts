import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { AS_OF, offline } from "./offline";

/**
 * FR-043, SC-011: every rendered route, in **both** themes, blocking on any AA violation.
 *
 * Both, because a check that visits only the default theme passes on a broken one -- and the
 * theme is a runtime choice, so a token-level contrast check alone cannot see what a rendered
 * page composes. It is a floor and not a proof: FR-038 to FR-042 are the requirements, not this
 * ruleset.
 */
const ROUTES = [
  `/?as_of=${AS_OF}`,
  `/data?as_of=${AS_OF}`,
  `/data/goals?as_of=${AS_OF}`,
  `/data/goals/flat_deposit?as_of=${AS_OF}`,
  `/series/cpi?as_of=${AS_OF}&from=2025-01&to=2025-10`,
  `/series/official-rate?as_of=${AS_OF}&from=2026-08-01&to=2026-08-31`,
];

/**
 * `"system"` is the third case and the one a reader who never opens the select is in: stamping
 * the attribute first would render the same two palettes twice and never the default path.
 */
const MODES = [
  { theme: "light", stamp: true },
  { theme: "dark", stamp: true },
  { theme: "dark", stamp: false },
] as const;

for (const { theme, stamp } of MODES) {
  for (const route of ROUTES) {
    const named = stamp ? `chosen ${theme}` : `system ${theme}`;
    test(`${route} has no AA violation with the ${named} theme`, async ({ page }) => {
      await offline(page);
      await page.emulateMedia({ colorScheme: theme });
      await page.goto(route);
      if (stamp) {
        await page.evaluate((chosen: string) => {
          document.documentElement.setAttribute("data-theme", chosen);
        }, theme);
      }
      await expect(page.locator("main")).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(results.violations.map((held) => `${held.id}: ${held.help}`)).toEqual([]);
    });
  }
}

/**
 * 027 FR-029: the card in both themes.
 *
 * Opened from the answer rather than listed above, because its URL carries a key the **answer**
 * publishes — one this test composed would address a candidate nobody ranked.
 */
for (const { theme, stamp } of MODES) {
  const named = stamp ? `chosen ${theme}` : `system ${theme}`;
  test(`a candidate card has no AA violation with the ${named} theme`, async ({ page }) => {
    await offline(page);
    await page.emulateMedia({ colorScheme: theme });
    await page.goto(`/?as_of=${AS_OF}`);
    if (stamp) {
      await page.evaluate((chosen: string) => {
        document.documentElement.setAttribute("data-theme", chosen);
      }, theme);
    }
    await expect(page.locator("[data-answer]")).toBeVisible({ timeout: 120_000 });
    await page.locator("[data-open-card]").first().click();
    await expect(page.locator("[data-card]")).toBeVisible({ timeout: 120_000 });
    // Every disclosure open: a violation inside a folded one is a violation a reader meets.
    await page.evaluate(() => {
      for (const held of document.querySelectorAll("details")) held.setAttribute("open", "");
    });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations.flatMap((held) =>
        held.nodes.map((node) => `${held.id}: ${node.html.slice(0, 200)}`),
      ),
    ).toEqual([]);
  });
}
