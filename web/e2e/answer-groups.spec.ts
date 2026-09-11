import { expect, test } from "@playwright/test";
import { offline } from "./offline";
import { openTheAnswer, servedAnswer } from "./answer";

/**
 * SC-006: the no-candidate rows of one typed reason are one line and one count, and expanding it
 * yields every id the count counted.
 *
 * Measured 2026-09-07 there are 27, all sharing `(NothingConnects, route_in, contract_usd)` —
 * the count is read off the API here rather than written down, because it moved from 26 when
 * 023 landed.
 */
test("the no-candidate pairs fold to one line per typed reason, and expand to their ids", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const served = await servedAnswer(page);
  const column = page.locator("[data-horizon]").first();
  const population = column.locator("[data-population='no candidate']");
  const stated = await population.getAttribute("data-count");
  expect(Number((stated ?? "").replace(/\D/g, ""))).toBe(served.sections[0]?.noCandidate);

  const groups = population.locator("[data-group]");
  await expect(groups).toHaveCount(1);
  await expect(groups.first().locator("summary")).toContainText("candidates.NothingConnects");

  await groups.first().locator("summary").click();
  await expect(groups.first().locator("[data-no-candidate]")).toHaveCount(
    served.sections[0]?.noCandidate ?? 0,
  );
});

test("every population the API reports is one interaction from its own members", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await offline(page);
  await openTheAnswer(page);

  const mismatched = await page.evaluate(() => {
    const wrong: string[] = [];
    for (const held of document.querySelectorAll("[data-population]")) {
      const name = held.getAttribute("data-population") ?? "";
      const stated = Number((held.getAttribute("data-count") ?? "").replace(/\D/g, ""));
      // Its OWN members: `querySelectorAll` matches every descendant, so a population drawn
      // inside another one had its members counted twice — once for itself and once for its
      // host, whose stated count had never counted them.
      const members = [
        ...held.querySelectorAll("[data-population-members] > li, [data-group-members] > li"),
      ].filter((member) => member.closest("[data-population]") === held).length;
      if (stated !== members) wrong.push(`${name}: says ${String(stated)}, holds ${String(members)}`);
    }
    return wrong;
  });
  expect(mismatched).toEqual([]);
  // The held population is why this is scoped, and it is on the screen everywhere: the API is
  // started over a root that declares a holding.
  await expect(page.locator("[data-population='what the owner already holds']")).toHaveAttribute(
    "data-count",
    /[1-9]/,
  );
});
