import { expect, test } from "@playwright/test";
import { offline } from "./offline";
import { openTheAnswer, servedAnswer } from "./answer";

/**
 * SC-001: each column's members equal the API's `non_dominated` for that section, by count and
 * by id.
 *
 * The API is asked in the same browser rather than pinned here, because `data/` moves and a
 * count copied out of it would make this a test of the registry.
 */
test("the three columns hold exactly the members the API placed on each front", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const served = await servedAnswer(page);
  expect(served.sections).toHaveLength(3);

  const columns = page.locator("[data-horizon]");
  await expect(columns).toHaveCount(served.sections.length);

  for (const [at, section] of served.sections.entries()) {
    const column = columns.nth(at);
    const drawn = await column
      .locator("[data-candidate]")
      .evaluateAll((cards) => cards.map((card) => card.getAttribute("data-candidate") ?? ""));
    expect(drawn).toEqual([...section.nonDominated]);
    // Read off the **dominance** record, not off `comparison.ranked`: a count taken from the
    // field the component renders is green whatever the pass placed.
    await expect(column.locator("[data-front-count]")).toHaveAttribute(
      "data-front-count",
      String(section.nonDominated.length),
    );
    for (const [name, many] of [
      ["dominated", section.dominated],
      ["not placed", section.notPlaced],
    ] as const) {
      await expect(column.locator(`[data-population='${name}']`)).toHaveAttribute(
        "data-count",
        String(many),
      );
    }
    const beating = await column
      .locator("[data-population='beating the benchmark'] [data-ranked-member]")
      .evaluateAll((held) => held.map((one) => one.getAttribute("data-ranked-member") ?? ""));
    expect(beating).toEqual([...section.beatsBenchmark]);
    await expect(column.locator("[data-benchmark-standing]")).toBeVisible();
  }
});

test("every card says what it is, in text, and carries one separating badge", async ({ page }) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const cards = page.locator("[data-candidate]");
  const many = await cards.count();
  expect(many).toBeGreaterThan(0);
  for (let at = 0; at < many; at += 1) {
    const card = cards.nth(at);
    await expect(card.locator("[data-kind]")).toHaveCount(1);
    await expect(card.locator("[data-separating]")).toHaveCount(1);
    await expect(card.locator("[data-money-back]")).toHaveCount(1);
  }
});
